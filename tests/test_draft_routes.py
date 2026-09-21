"""5단계 보완 기획안 화면과 저장 (5보완기획안계획.md 5장)."""

import re
from datetime import date
from urllib.parse import quote

from evidence_helpers import fixture_path
from fastapi.testclient import TestClient
from helpers import VALID_FORM

from policy_signal_map.app import app
from policy_signal_map.paths import WEB_DIR

STATIC_DIR = WEB_DIR / "static"

ADOPT_A = {
    "question_key": "R07",
    "decision": "adopt",
    "option_id": "A",
    "collect_items": "쿠폰 사용 실적",
    "availability": "available",
    "owner": "관광과 김담당",
    "cycle": "월 1회",
}
TODAY = date.today().strftime("%Y%m%d")


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def answered_client(form: dict | None = None, choice: dict | None = None) -> TestClient:
    c = TestClient(app)
    c.post("/step/1", data=form or VALID_FORM)
    c.post("/step/4", data=choice or ADOPT_A)
    return c


def test_step_five_requires_original():
    response = TestClient(app).get("/step/5", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/step/1"


def test_unanswered_question_sends_back_to_step_four():
    c = TestClient(app)
    c.post("/step/1", data=VALID_FORM)
    response = c.get("/step/5", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/step/4"
    assert "아직 고르지 않았습니다" in text_of(c.get("/step/4").text)


def test_draft_screen_shows_summary_and_changed_lines():
    text = text_of(answered_client().get("/step/5").text)
    assert "보완 기획안 — 하반기 외국인 소비지원 쿠폰" in text
    assert "시연용 합성 수치 · 자료 버전 demo-001" in text
    assert "담당자 확인 전 초안입니다" in text
    assert "변경 5건" in text and "원안 유지" in text
    assert "주요 지표: 쿠폰 사용 실적" in text
    assert "1. 사업 개요" in text and "8. 추가 확인사항" in text


def test_changed_line_carries_evidence_chip_and_trace():
    html = answered_client().get("/step/5").text
    assert 'href="#trace-DEMO-R07-SIGUNGU-강원-강릉시"' in html
    assert 'id="trace-DEMO-R07-SIGUNGU-강원-강릉시"' in html
    text = text_of(html)
    assert "근거 DEMO-R07-SIGUNGU-강원-강릉시" in text
    assert "강원특별자치도 강릉시 범위 참고 — 선택 지역의 진단이 아님" in text


def test_pending_items_are_shown_without_being_filled():
    c = answered_client(choice={**ADOPT_A, "owner": "", "cycle": ""})
    text = text_of(c.get("/step/5").text)
    assert "추가 확정 필요" in text
    assert "수집 담당: [추가 확정 필요]" in text.replace("**", "")
    assert "서비스가 값을 채우지 않습니다" in text


def test_change_table_lists_rule_and_decision():
    text = text_of(answered_client().get("/step/5").text)
    assert "변경 전후 5건" in text
    assert "금액·비중과 성과지표 확인 · 대안 A" in text and "채택" in text


def test_full_document_screen_shows_markdown_source():
    text = answered_client().get("/step/5/document").text
    assert "# 보완 기획안 — 하반기 외국인 소비지원 쿠폰" in text
    assert "## 별첨 1. 변경 전후" in text


def test_download_sends_markdown_with_korean_filename():
    response = answered_client().get("/step/5/download")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    expected = quote(f"보완기획안_하반기_외국인_소비지원_쿠폰_{TODAY}.md")
    assert f"filename*=UTF-8''{expected}" in response.headers["content-disposition"]
    assert response.text.startswith("# 보완 기획안")
    assert "별첨 2. 근거와 해석 한계" in response.text


def test_download_is_blocked_while_questions_remain():
    c = TestClient(app)
    c.post("/step/1", data=VALID_FORM)
    response = c.get("/step/5/download")
    assert response.status_code == 409
    assert "아직 고르지 않았습니다" in response.text


def test_request_draft_only_reachable_after_option_d():
    c = answered_client()
    assert "정밀 분석 요청서 초안" not in text_of(c.get("/step/5").text)
    response = c.get("/step/5/request", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/step/5"

    c.post("/step/4", data={"question_key": "R07", "decision": "adopt", "option_id": "D"})
    assert "정밀 분석 요청서 초안" in text_of(c.get("/step/5").text)
    text = text_of(c.get("/step/5/request").text)
    assert "계약이나 자료 제공이 확정된 것이 아닙니다" in text
    assert "참여 점포 목록" in text


def test_request_download_uses_its_own_filename():
    c = answered_client(choice={"question_key": "R07", "decision": "adopt", "option_id": "D"})
    response = c.get("/step/5/download?kind=request")
    assert response.status_code == 200
    assert quote(f"정밀분석요청서_하반기_외국인_소비지원_쿠폰_{TODAY}.md") in response.headers["content-disposition"]
    assert response.text.startswith("# 정밀 분석 요청서 (초안)")


def test_request_download_without_option_d_is_not_found():
    response = answered_client().get("/step/5/download?kind=request")
    assert response.status_code == 404


def test_pdf_button_is_on_every_result_screen():
    c = answered_client(choice={"question_key": "R07", "decision": "adopt", "option_id": "D"})
    for path in ("/step/5", "/step/5/document", "/step/5/request"):
        html = c.get(path).text
        assert "data-print-button" in html, path
        assert "PDF로 저장" in html, path
        assert "js/print.js" in html, path


def test_print_stylesheet_hides_screen_only_parts():
    css = (STATIC_DIR / "css" / "style.css").read_text(encoding="utf-8")
    print_block = css[css.index("@media print") :]
    for selector in (".topbar", ".rail", ".head-actions", ".btn"):
        assert selector in print_block
    assert ".site-foot" in print_block  # 합성 수치·공모전 고지는 인쇄본에도 남는다


def test_step_five_error_page_when_evidence_fails(use_evidence):
    c = answered_client()
    use_evidence(fixture_path("relation_broken"))
    response = c.get("/step/5")
    assert response.status_code == 503
    assert "분석 근거 파일을 불러오지 못했습니다" in response.text


def test_step_five_has_no_score_or_judgement_wording():
    text = text_of(answered_client().get("/step/5").text)
    for word in ("점수", "성공 확률", "부적절", "오류입니다"):
        assert word not in text


# ---------------------------------------------------------------- 쓰지 않는 실행 조건이 8장에 남지 않음 (6-5b)

PARTIAL_A = {"question_key": "R07", "decision": "adopt", "option_id": "A", "collect_items": "쿠폰 사용 실적"}
STALE = "참여 실적 자료: 수집 담당자"


def test_disappeared_question_leaves_no_execution_pending():
    c = answered_client(choice=PARTIAL_A)
    c.post("/step/1", data={**VALID_FORM, "metrics": ["coupon_usage"]})
    assert STALE not in c.get("/step/5/download").text


def test_keep_original_after_adopt_leaves_no_execution_pending():
    c = answered_client(choice=PARTIAL_A)
    assert STALE in c.get("/step/5/download").text
    c.post("/step/4", data={"question_key": "R07", "decision": "keep_original"})
    assert STALE not in c.get("/step/5/download").text


def test_switching_a_to_b_leaves_no_execution_pending():
    c = answered_client(choice=PARTIAL_A)
    c.post("/step/4", data={"question_key": "R07", "decision": "adopt", "option_id": "B"})
    assert STALE not in c.get("/step/5/download").text


def test_shared_execution_stays_while_another_question_adopts_a():
    c = answered_client({**VALID_FORM, "target": "외국인 관광객"}, PARTIAL_A)
    c.post("/step/4", data={**PARTIAL_A, "question_key": "R03"})
    c.post("/step/4", data={"question_key": "R03", "decision": "keep_original"})
    assert STALE in c.get("/step/5/download").text


def test_r04_b_keeps_entered_cycle_after_r07_is_kept_original():
    c = answered_client({**VALID_FORM, "period_start": "2026-10-01", "period_end": "2026-10-20"})
    c.post("/step/4", data={"question_key": "R04-period", "decision": "adopt", "option_id": "B"})
    c.post("/step/4", data={"question_key": "R07", "decision": "keep_original"})
    text = c.get("/step/5/download").text
    assert "사업 기간 성과는 월 1회 주기로 별도 확인" in text


def test_save_script_does_not_download_recheck_response():
    # 5단계를 연 뒤 원안이 바뀌면 내려받기가 409다. 오류 문장을 .md로 저장하지 않고 안내만 한다 (6-5d)
    script = (STATIC_DIR / "js" / "save.js").read_text(encoding="utf-8")
    assert "response.status === 409" in script
    assert "4단계 보완 선택으로 가서 확인한 뒤 저장해 주세요" in script
    # 문서를 먼저 받아 확인한 뒤에만 파일로 쓴다 (주소를 바로 내려받는 방식 없음)
    assert "link.href = url;" in script and "createObjectURL" in script
