"""문서 구조 → Markdown (5보완기획안계획.md 3장)."""

import re

from document_helpers import ADOPT_A, choose, document_for, plan_with, review_of

from policy_signal_map.choices.models import ChoiceSet
from policy_signal_map.document.render import md_escape, render_markdown
from policy_signal_map.plan.models import IndicatorUse


def adopted_document():
    plan = plan_with()
    result = review_of(plan)
    choice_set = ChoiceSet()
    choose(result, choice_set, "R07", ADOPT_A, ["쿠폰 사용 실적"])
    document, _ = document_for(plan, choice_set)
    return document


def test_header_shows_date_data_and_draft_notice():
    text = render_markdown(adopted_document())
    first = text.splitlines()[0]
    assert first == "# 보완 기획안 — 하반기 외국인 소비지원 쿠폰"
    assert "생성일 2026-09-17" in text
    assert "시연용 합성 수치 · 자료 버전 demo-001" in text
    assert "담당자 확인 전 초안입니다" in text


def test_every_section_heading_is_written():
    text = render_markdown(adopted_document())
    for number, title in [(1, "사업 개요"), (7, "성과 측정계획"), (8, "추가 확인사항")]:
        assert f"## {number}. {title}" in text


def test_each_line_is_its_own_list_item():
    text = render_markdown(adopted_document())
    assert "- 사업명: 하반기 외국인 소비지원 쿠폰" in text.splitlines()
    assert "- 사업 기간: 2026-10-01 ~ 2026-12-31" in text.splitlines()


def test_added_line_carries_change_mark():
    text = render_markdown(adopted_document())
    assert "- 주요 지표: 쿠폰 사용 실적 〔추가 · 변경 001〕" in text.splitlines()
    assert "R07-A-1" not in text


def test_change_table_lists_every_change():
    document = adopted_document()
    text = render_markdown(document)
    assert "| 장 | 원안 | 보완안 | 변경 이름표·검토 질문·대안 | 담당자 선택 | 근거 |" in text
    rows = [line for line in text.splitlines() if line.startswith("| 7 |")]
    assert len(rows) == len(document.changes)
    # 별첨 표도 관리 번호 대신 규칙 제목을 쓴다 (사용자 결정 9/18)
    assert "변경 001 · 금액·비중과 성과지표 확인 · 대안 A" in rows[0] and "채택" in rows[0] and "DEMO-R07-SIGUNGU-강원-강릉시" in rows[0]
    assert "R07 · 대안 A" not in rows[0]


def test_evidence_appendix_shows_scope_and_limits():
    text = render_markdown(adopted_document())
    assert "### DEMO-R07-SIGUNGU-강원-강릉시" in text
    assert "강원특별자치도 강릉시 범위 참고 — 선택 지역의 진단이 아님" in text
    assert "합성 · 버전 demo-001" in text
    assert "금액과 비중은 서로 다른 질문에 답합니다" in text


def test_evidence_appendix_always_has_selected_region_profile_summary():
    text = render_markdown(adopted_document())
    assert "### 지역 소비 프로필 — 강원특별자치도 강릉시" in text
    assert "업종 구성에서 비중이 가장 큰 항목" in text
    assert "연령 구성 분모" in text
    assert "주민등록인구(규모 참고)" in text
    assert "1인당" not in text


def test_document_without_changes_says_so():
    document, _ = document_for(plan_with(indicator_use=IndicatorUse.REFERENCE))
    text = render_markdown(document)
    assert "변경한 항목이 없습니다. 원안을 그대로 유지했습니다." in text
    assert "별첨 3" not in text


def test_request_appendix_only_with_option_d():
    plan = plan_with()
    result = review_of(plan)
    choice_set = ChoiceSet()
    choose(result, choice_set, "R07", {"decision": "adopt", "option_id": "D"})
    document, _ = document_for(plan, choice_set)
    text = render_markdown(document)
    assert "## 별첨 3. 정밀 분석 요청서 (초안)" in text
    assert "계약·자료 제공이 확정된 것이 아닙니다" in text


def test_user_text_cannot_break_the_change_table():
    plan = plan_with()
    result = review_of(plan)
    choice_set = ChoiceSet()
    choose(
        result,
        choice_set,
        "R07",
        {"decision": "modify", "option_id": "B", "modified_text": "분모 | 기준 [주의]"},
    )
    document, _ = document_for(plan, choice_set)
    text = render_markdown(document)
    row = next(line for line in text.splitlines() if line.startswith("| 7 |"))
    assert len(re.findall(r"(?<!\\)\|", row)) == 7  # 칸 구분선은 6개 칸 기준 7개
    assert r"분모 \| 기준 [주의]" in row  # 대괄호는 [추가 확정 필요] 표기에 쓰므로 그대로 둔다


def test_pending_mark_is_bold_only_in_the_document():
    document, _ = document_for(plan_with(indicator_use=IndicatorUse.REFERENCE))
    text = render_markdown(document)
    assert "- 세부 일정: 원안에 기재 없음 **[추가 확정 필요]**" in text.splitlines()
    # 문서 구조 자체에는 표시 기호가 없다 (화면은 이 값을 그대로 쓴다)
    assert all("**" not in line.text for section in document.sections for line in section.lines)


def test_md_escape_keeps_plain_text():
    assert md_escape("외국인 결제 비중") == "외국인 결제 비중"
    assert md_escape("a|b") == r"a\|b"
