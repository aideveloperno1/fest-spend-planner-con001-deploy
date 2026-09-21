"""2단계 근거 확인 화면 (2근거확인화면계획.md 7장, 9장, 10장)."""

import json
import re
from pathlib import Path

from evidence_helpers import base_data, fixture_path
from fastapi.testclient import TestClient
from helpers import VALID_FORM

from policy_signal_map.app import app

CHART_SRI = "sha384-jb8JQMbMoBUzgWatfe6COACi2ljcDdZQ2OxczGA3bGNeWe+6DChMTBJemed7ZnvJ"


# 예시 폼은 강원 강릉시라 지역 자료로 열린다. 전국 자료 표시를 확인하는 시험은 전국 기획을 쓴다
NATIONAL_FORM = {**VALID_FORM, "region_level": "national"}


def reviewed_client() -> TestClient:
    c = TestClient(app)
    c.post("/step/1", data=VALID_FORM)
    return c


def national_client() -> TestClient:
    c = TestClient(app)
    c.post("/step/1", data=NATIONAL_FORM)
    return c


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_step_two_requires_original():
    response = TestClient(app).get("/step/2", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/step/1"


def test_step_two_route_shows_its_own_screen():
    response = reviewed_client().get("/step/2")
    assert "근거 확인" in response.text


def test_step_two_shows_demo_evidence():
    html = national_client().get("/step/2").text
    text = text_of(html)
    assert (
        "2026년 1~6월 전국 자료에서 비교 가능한 5개 인접 월 구간 중 2개 구간에서 "
        "외국인 결제금액과 전체 분모 비중의 변화 방향이 달랐습니다." in text
    )
    assert "전국 참고 — 특정 지역의 진단이 아님" in text
    assert html.count('data-row="month"') == 6 + 6  # 전국 6행 + 보류 예시 6행
    assert html.count('data-row="pair"') == 5 + 5


def test_step_two_shows_region_evidence_for_sigungu_plan():
    """예시 기획(강원 강릉시)은 강원 시도 자료로 열리고, 시군구 진단이 아니라고 밝힌다 (C-2·C-5)."""
    text = text_of(reviewed_client().get("/step/2").text)
    assert (
        "2026년 1~6월 강원특별자치도 강릉시 자료에서 비교 가능한 5개 인접 월 구간 중 2개 구간에서 "
        "외국인 결제금액과 전체 분모 비중의 변화 방향이 달랐습니다." in text
    )
    assert "강원특별자치도 강릉시 범위 참고 — 선택 지역의 진단이 아님" in text
    assert "" in text
    assert "5100000000" not in text  # 행정표준코드는 화면에 쓰지 않는다


def test_step_two_expected_values():
    text = text_of(national_client().get("/step/2").text)
    for expected in (
        "1월 820원 8.20% 4.50% 8.59% 계산됨",
        "4월 905원 8.54% 5.09% 9.00% 계산됨",
        "1→2월 -3.66% -6.00% +0.20%p 방향 다름 +0.31%p 방향 같음",
        "5→6월 -5.38% -1.74% -0.32%p 방향 같음 -0.46%p 방향 같음",
        "외국인 결제금액 5,185원",
        "5월 0원 계산 불가 계산 불가 계산 불가 분모 0 · 계산 불가",
        "2→3월 보류 — 2026-03 자료 없음(no_data)",
    ):
        assert expected in text, expected


def test_step_two_shows_tiny_change_label():
    assert "4→5월 +2.76% +2.74% 0.01%p 미만 (증가) 방향 같음" in text_of(national_client().get("/step/2").text)


def test_step_two_has_no_red_warning_classes():
    html = reviewed_client().get("/step/2").text
    for word in ("danger", "text-warn", "alert", "error-red"):
        assert word not in html


def test_step_two_chart_data_is_escaped_json():
    html = national_client().get("/step/2").text
    match = re.search(r'<script type="application/json" id="chart-data">(.*?)</script>', html, re.S)
    assert match
    data = json.loads(match.group(1))
    assert data["foreign_amount"] == [820, 790, 860, 905, 930, 880]


def test_chart_script_has_integrity():
    html = reviewed_client().get("/step/2").text
    assert f'integrity="{CHART_SRI}"' in html
    assert 'crossorigin="anonymous"' in html


def test_step_two_error_page_when_evidence_fails(use_evidence):
    c = reviewed_client()
    use_evidence(fixture_path("relation_broken"))
    response = c.get("/step/2")
    assert response.status_code == 503
    assert "분석 근거 파일을 불러오지 못했습니다" in response.text
    assert "외국인+미상 금액이 전체 금액보다 큽니다" in response.text
    assert not re.search(r"\d{3,}원", response.text)


def test_step_one_still_works_when_evidence_fails(use_evidence):
    use_evidence(fixture_path("relation_broken"))
    assert TestClient(app).get("/step/1").status_code == 200


def test_blocked_evidence_page_has_no_numbers(use_evidence, tmp_path: Path):
    data = base_data()
    data["records"][0]["applicability"]["R07"] = {"status": "blocked", "reason": "범위 불일치"}
    path = tmp_path / "blocked.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    use_evidence(path)

    html = reviewed_client().get("/step/2").text
    assert "현재 자료로 금액·비중 비교를 사용할 수 없습니다. 사유: 범위 불일치" in html
    assert 'data-row="month"' not in html
    assert 'id="chart-data"' not in html
    assert "800원" not in html


def test_unknown_step_is_not_served():
    assert reviewed_client().get("/step/9", follow_redirects=False).status_code == 404


def test_step_two_shows_who_wrote_each_limitation():
    text = text_of(reviewed_client().get("/step/2").text)
    assert "자료의 한계 분석 담당 작성" in text
    assert "서비스 해석 원칙" in text
    assert text.index("자료의 한계") < text.index("서비스 해석 원칙")
