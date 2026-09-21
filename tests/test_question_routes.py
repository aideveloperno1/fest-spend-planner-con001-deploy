"""3단계 검토 질문 화면 (3검토질문계획.md 5장)."""

import re

from evidence_helpers import fixture_path
from fastapi.testclient import TestClient
from helpers import VALID_FORM

from policy_signal_map.app import app

TOURIST_FORM = {**VALID_FORM, "target": "방한 관광객"}


def reviewed_client(form: dict | None = None) -> TestClient:
    c = TestClient(app)
    c.post("/step/1", data=form or VALID_FORM)
    return c


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_step_three_requires_original():
    response = TestClient(app).get("/step/3", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/step/1"


def test_step_three_route_shows_its_own_screen():
    html = reviewed_client().get("/step/3").text
    assert "검토 질문" in html


def test_step_three_shows_question_with_evidence_and_scope():
    text = text_of(reviewed_client().get("/step/3").text)
    assert "검토 질문 1건" in text
    assert "금액·비중과 성과지표 확인" in text and "R07" in text  # 제목 + 작은 번호 배지
    assert "외국인 결제금액 확대인가요" in text
    assert "왜 묻나요? 2026년 1~6월 강원특별자치도 강릉시 자료에서 비교 가능한 5개 인접 월 구간 중 2개 구간에서" in text
    assert "강원특별자치도 강릉시 범위 참고 — 선택 지역의 진단이 아님" in text
    assert "근거 DEMO-R07-SIGUNGU-강원-강릉시" in text
    assert "" in text


def test_step_three_shows_pending_items():
    text = text_of(reviewed_client().get("/step/3").text)
    assert "빠진 운영 조건 확인" in text and "추가 확정 필요" in text
    # 예시 폼은 예산을 비워 두므로 "미입력"이다 ([미정] 체크 시에는 "미정")
    assert "예산 (미입력), 자료 확보 상태" in text


def test_step_three_does_not_preview_options():
    # 대안은 4단계에서만 보여준다 (3단계는 확인할 점만)
    text = text_of(reviewed_client().get("/step/3").text)
    assert "참여 실적 추가" not in text
    assert "운영 부담" not in text


def test_step_three_separates_no_finding_and_not_reviewed():
    """세 가지를 구분해 보여 준다: 물을 것 없음 / 유형이 달라 확인 안 함 / 이번 범위에서 만들지 않음."""
    # 쿠폰 유형이면 목표·사용처와 기간은 실행하고, 대상과 자료 확인(외국인·관광)은 실행하지 않는다
    text = text_of(reviewed_client({**VALID_FORM, "business_type": "coupon"}).get("/step/3").text)
    assert "확인했으나 해당 없음" in text
    # 화면에는 관리 번호를 쓰지 않고 규칙 제목만 보여 준다 (사용자 결정 9/18)
    assert "목표와 사용처 확인" in text and "기간 확인" in text
    assert "사업 유형이 달라 확인하지 않음" in text and "대상과 자료 확인" in text
    assert "R01" not in text and "R03" not in text
    assert "검토하지 않음 분석 예시" in text
    assert "R06" not in text and "R02" not in text


def cards_text(html: str) -> str:
    # 판정 단어 검사는 규칙 카드 안만 본다 (오른쪽 패널에는 "‘문제없음’과 ‘검토하지 않음’은 다릅니다" 설명이 있다)
    return " ".join(text_of(card) for card in re.findall(r'<article class="rule-card.*?</article>', html, re.S))


def test_reference_indicator_use_shows_notice_without_question():
    html = reviewed_client({**VALID_FORM, "indicator_use": "reference"}).get("/step/3").text
    text = text_of(html)
    assert "검토 질문 0건" in text
    assert "그대로 두어도 됩니다" in text
    for word in ("문제", "오류", "위험", "실패", "성공", "잘못"):
        assert word not in cards_text(html), word


def test_related_questions_are_shown_without_merging():
    text = text_of(reviewed_client(TOURIST_FORM).get("/step/3").text)
    assert "검토 질문 2건" in text
    # 함께 확인 안내도 번호가 아니라 규칙 제목으로 (사용자 결정 9/18)
    assert "함께 확인: 대상과 자료 확인" in text
    assert "함께 확인: 금액·비중과 성과지표 확인" in text


def test_step_three_error_page_when_evidence_fails(use_evidence):
    c = reviewed_client()
    use_evidence(fixture_path("relation_broken"))
    response = c.get("/step/3")
    assert response.status_code == 503
    assert "분석 근거 파일을 불러오지 못했습니다" in response.text


def test_step_three_has_no_warning_classes():
    html = reviewed_client().get("/step/3").text
    for word in ("danger", "text-warn", "error-red"):
        assert word not in html


def test_step_three_uses_single_column_collapsed_inactive_rules():
    html = reviewed_client().get("/step/3").text

    assert '<div class="questions-page step-with-sticky">' in html
    assert "layout-main-side" not in html
    assert '<aside class="side">' not in html

    details = re.search(
        r'<details class="card review-accordion"([^>]*)>(.*?)</details>',
        html,
        re.S,
    )
    assert details is not None
    assert "open" not in details.group(1)
    assert details.group(2).count('class="review-accordion-section"') == 3

    count = re.search(r"미적용 규칙 \(총 (\d+)건\)", details.group(2))
    assert count is not None
    listed_rules = re.findall(r'class="rule(?:\s|\")', details.group(2))
    assert int(count.group(1)) == len(listed_rules)
    assert html.index('class="card review-accordion"') < html.index('class="workflow-sticky-bar questions-nav"')
    assert 'href="/step/2"' in html and 'href="/step/4"' in html
