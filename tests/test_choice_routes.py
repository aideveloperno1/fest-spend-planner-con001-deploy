"""4단계 보완 선택 화면 (4보완선택계획.md 6장)."""

import re

from evidence_helpers import fixture_path
from fastapi.testclient import TestClient
from helpers import VALID_FORM

from policy_signal_map.app import app

TOURIST_FORM = {**VALID_FORM, "target": "방한 관광객"}
ADOPT_A = {
    "question_key": "R07",
    "decision": "adopt",
    "option_id": "A",
    "collect_items": "쿠폰 사용 실적, 정산 자료",
    "availability": "available",
    "owner": "관광과 김담당",
    "cycle": "월 1회",
}


def reviewed_client(form: dict | None = None) -> TestClient:
    c = TestClient(app)
    c.post("/step/1", data=form or VALID_FORM)
    return c


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_step_four_requires_original():
    response = TestClient(app).get("/step/4", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/step/1"


def test_step_four_shows_question_with_options():
    text = text_of(reviewed_client().get("/step/4").text)
    assert "보완 방법 고르기" in text
    assert "서비스는 정답을 고르지 않습니다" in text
    assert "A 참여 실적 추가 바뀌는 곳 · 7. 성과 측정계획 필요 자료 · 쿠폰 발급·사용·정산 자료 운영 부담 · 중" in text
    assert "원안 유지" in text and "보류" in text


def test_saving_choice_keeps_it_after_reload():
    c = reviewed_client()
    response = c.post("/step/4", data=ADOPT_A)
    assert response.status_code == 200
    assert str(response.url).endswith("/step/4")

    text = text_of(c.get("/step/4").text)
    # 제목에는 관리 번호를 쓰지 않고 작은 번호 배지로만 보여 준다 (사용자 결정 9/18)
    assert "금액·비중과 성과지표 확인" in text and "채택" in text
    assert "R07 금액·비중과 성과지표 확인" not in text
    assert "관광과 김담당" in c.get("/step/4").text
    assert "쿠폰 사용 실적" in c.get("/step/4").text


def test_validation_error_is_shown_and_choice_not_saved():
    c = reviewed_client()
    response = c.post("/step/4", data={**ADOPT_A, "collect_items": ""})
    assert response.status_code == 422
    assert "수집할 자료를 하나 이상 적어 주세요." in response.text
    assert "채택" not in text_of(c.get("/step/4").text).split("보완 방법 고르기")[1][:200]


def test_cancel_removes_choice():
    c = reviewed_client()
    c.post("/step/4", data=ADOPT_A)
    c.post("/step/4/cancel", data={"question_key": "R07"})
    assert "관광과 김담당" not in c.get("/step/4").text


def test_shared_execution_input_is_filled_for_related_question():
    c = reviewed_client(TOURIST_FORM)
    c.post("/step/4", data=ADOPT_A)
    html = c.get("/step/4").text
    # R03 카드에도 같은 수집자료가 채워져 있고, 함께 쓰는 입력임을 알린다
    assert html.count("쿠폰 사용 실적") >= 2
    assert "같은 자료를 묻는 질문(금액·비중과 성과지표 확인)과 함께 쓰는 입력입니다" in text_of(html)


def test_next_step_is_blocked_until_every_question_is_answered():
    c = reviewed_client(TOURIST_FORM)
    text = text_of(c.get("/step/4").text)
    assert "보완 기획안을 만들기 전에 확인할 것" in text
    assert "아직 고르지 않았습니다" in text
    assert "보완 기획안 만들기" not in text

    c.post("/step/4", data=ADOPT_A)
    c.post("/step/4", data={"question_key": "R03", "decision": "hold"})
    text = text_of(c.get("/step/4").text)
    assert "보완 기획안 만들기" in text  # 보류도 결정으로 인정
    assert "아직 고르지 않았습니다" not in text


def test_pending_items_are_listed():
    c = reviewed_client()
    c.post("/step/4", data={**ADOPT_A, "owner": "", "cycle": "", "availability": "negotiating"})
    text = text_of(c.get("/step/4").text)
    assert "추가 확정 필요" in text
    assert "참여 실적 자료: 수집 담당자" in text  # 내부 묶음 키를 그대로 보여주지 않는다


def test_notice_does_not_block_next_step():
    c = reviewed_client({**VALID_FORM, "indicator_use": "reference"})
    text = text_of(c.get("/step/4").text)
    assert "보완 기획안 만들기" in text
    assert "B 해석 조건 명시" in text


def test_changed_plan_marks_choice_for_recheck():
    c = reviewed_client()
    c.post("/step/4", data=ADOPT_A)
    c.post("/step/1", data={**VALID_FORM, "metrics": ["foreign_amount"]})
    text = text_of(c.get("/step/4").text)
    assert "기획 또는 근거 자료가 바뀌어 다시 확인이 필요한 선택이 1건" in text
    assert "다시 확인이 필요합니다" in text
    assert "보완 기획안 만들기" not in text


def test_changed_evidence_version_marks_saved_value_choice_for_recheck(use_evidence):
    c = reviewed_client()
    c.post("/step/4", data=ADOPT_A)

    use_evidence(fixture_path("amount_down_share_up"))
    text = text_of(c.get("/step/4").text)
    assert "기획 또는 근거 자료가 바뀌어 다시 확인이 필요한 선택이 1건" in text
    assert "금액·비중과 성과지표 확인" in text
    assert "보완 기획안 만들기" not in text


def test_choice_for_disappeared_question_is_archived():
    c = reviewed_client(TOURIST_FORM)
    c.post("/step/4", data={"question_key": "R03", "decision": "keep_original"})
    c.post("/step/1", data=VALID_FORM)  # 대상을 되돌려 R03 질문이 사라짐
    text = text_of(c.get("/step/4").text)
    assert "더 이상 해당하지 않는 선택 1건을 보관했습니다" in text
    assert "보완 기획안에는 반영하지 않습니다" in text


def test_step_four_error_page_when_evidence_fails(use_evidence):
    c = reviewed_client()
    use_evidence(fixture_path("relation_broken"))
    response = c.get("/step/4")
    assert response.status_code == 503
    assert "분석 근거 파일을 불러오지 못했습니다" in response.text


def test_step_four_has_no_score_or_warning_wording():
    html = reviewed_client().get("/step/4").text
    for word in ("점수", "성공 확률", "danger", "text-warn"):
        assert word not in text_of(html).replace("성공 확률이나 점수를 표시하지 않습니다", "")


def test_step_four_uses_the_shared_sticky_navigation():
    html = reviewed_client().get("/step/4").text
    assert 'class="stack step-with-sticky"' in html
    assert 'class="workflow-sticky-bar"' in html
    assert 'href="/step/3"' in html


# ---------------------------------------------------------------- 원안 변경 후 선택 정리 (6-5a)

CHANGED_FORM = {**VALID_FORM, "metrics": ["foreign_amount"]}


def test_saving_again_clears_recheck_and_opens_step_five():
    c = reviewed_client()
    c.post("/step/4", data=ADOPT_A)
    c.post("/step/1", data=CHANGED_FORM)
    assert "다시 확인이 필요합니다" in text_of(c.get("/step/4").text)

    c.post("/step/4", data=ADOPT_A)
    assert "다시 확인이 필요합니다" not in text_of(c.get("/step/4").text)
    assert c.get("/step/5", follow_redirects=False).status_code == 200


def test_step_five_without_step_four_still_asks_for_recheck():
    c = reviewed_client()
    c.post("/step/4", data=ADOPT_A)
    c.post("/step/1", data=CHANGED_FORM)

    response = c.get("/step/5", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/step/4"
    assert "다시 확인이 필요합니다" in text_of(c.get("/step/4").text)


def test_download_without_step_four_is_blocked_after_plan_change():
    c = reviewed_client()
    c.post("/step/4", data=ADOPT_A)
    c.post("/step/1", data=CHANGED_FORM)
    response = c.get("/step/5/download")
    assert response.status_code == 409
    assert "다시 확인이 필요합니다" in response.text


def test_saving_from_a_page_opened_before_the_change_counts_as_recheck():
    c = reviewed_client()
    c.post("/step/4", data=ADOPT_A)
    c.post("/step/1", data=CHANGED_FORM)
    # 4단계를 다시 열지 않고, 바뀌기 전에 열어 둔 화면에서 그대로 저장
    c.post("/step/4", data=ADOPT_A)
    assert c.get("/step/5", follow_redirects=False).status_code == 200


def test_archive_notice_shows_only_the_latest_plan_change():
    # 대상에 관광객을 넣었다 뺐다 반복해도 같은 질문이 쌓이지 않고, 관계없는 변경에는 안내가 없다 (6-5e)
    def notice(c):
        match = re.search(r"더 이상 해당하지 않는 선택 (\d+)건을 보관했습니다: ([^(]*)\(", text_of(c.get("/step/4").text))
        return (match.group(1), match.group(2).strip()) if match else None

    c = reviewed_client(TOURIST_FORM)
    c.post("/step/4", data={"question_key": "R03", "decision": "keep_original"})
    c.post("/step/1", data=VALID_FORM)
    assert notice(c) == ("1", "대상과 자료 확인")

    c.post("/step/1", data=TOURIST_FORM)
    c.post("/step/4", data={"question_key": "R03", "decision": "keep_original"})
    assert notice(c) is None

    c.post("/step/1", data=VALID_FORM)
    assert notice(c) == ("1", "대상과 자료 확인")

    c.post("/step/1", data={**VALID_FORM, "name": "사업명만 바꿈"})
    assert notice(c) is None


def test_shared_input_note_is_omitted_without_related_question():
    # 예시 기획에는 R07과 같은 자료를 묻는 질문이 없다. "(없음)"으로 채운 문장을 보이지 않는다 (6-4a)
    text = text_of(reviewed_client().get("/step/4").text)
    assert "같은 자료를 묻는" not in text
    assert "(없음)" not in text


def test_failed_save_keeps_what_the_user_just_picked():
    """저장에 실패해도 방금 고른 값이 남아야 한다.

    비워서 다시 그리면 실행 조건 칸이 접히고 그 안의 오류 문구까지 감춰져,
    "저장을 눌러도 아무 일도 안 일어난다"로 보인다 (사용자 확인 2026-09-19).
    """
    c = reviewed_client()
    response = c.post("/step/4", data={
        "question_key": "R07", "decision": "adopt", "option_id": "A",
        "collect_items": "", "owner": "관광정책과", "cycle": "월 1회",
    })
    assert response.status_code == 422
    html = response.text
    assert "수집할 자료를 하나 이상 적어 주세요." in html
    # 고른 결정·대안이 그대로 체크돼 있어야 실행 조건 칸이 펼쳐진 채로 보인다
    assert '<input type="radio" name="decision" value="adopt" checked />' in html
    assert 'value="관광정책과"' in html and 'value="월 1회"' in html
