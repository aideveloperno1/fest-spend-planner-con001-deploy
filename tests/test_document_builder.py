"""보완 기획안 생성 (5보완기획안계획.md 2~3장, 워크플로우 S04·12장)."""

from datetime import date

from document_helpers import ADOPT_A, EVIDENCE, choose, document_for, plan_with, review_of, section_of, texts

from policy_signal_map.choices.models import ChoiceSet
from policy_signal_map.choices.selection import cancel_choice
from policy_signal_map.document.models import DocumentBlocked, PlanDocument
from policy_signal_map.evidence.loader import load_evidence
from policy_signal_map.plan.models import Budget, BudgetStatus, DataStatus, Goal, IndicatorUse


def test_without_choices_document_keeps_original_and_has_no_changes():
    document, _ = document_for(plan_with(indicator_use=IndicatorUse.REFERENCE))
    assert isinstance(document, PlanDocument)
    assert document.changes == ()
    assert texts(document, 2)[0] == "사업 목표: 외국인 결제 비중 확대"
    assert document.unchanged_sections >= 7


def test_blocked_while_questions_are_unanswered():
    document, _ = document_for(plan_with())
    assert isinstance(document, DocumentBlocked)
    assert any("아직 고르지 않았습니다" in reason for reason in document.reasons)


def test_adopted_option_adds_lines_and_records_change():
    plan = plan_with()
    result = review_of(plan)
    choice_set = ChoiceSet()
    assert choose(result, choice_set, "R07", ADOPT_A, ["쿠폰 사용 실적"]) == {}

    document, _ = document_for(plan, choice_set)
    lines = texts(document, 7)
    assert "주요 지표: 쿠폰 사용 실적" in lines
    assert "수집 담당: 관광과 김담당" in lines
    assert len(document.changes) == 5
    first = document.changes[0]
    assert first.section == 7 and first.rule_id == "R07" and first.option_id == "A"
    assert first.decision_label == "채택" and first.before is None
    assert first.evidence_ids == ("DEMO-R07-SIGUNGU-강원-강릉시",)


def test_empty_owner_and_cycle_become_pending_marks():
    plan = plan_with()
    result = review_of(plan)
    choice_set = ChoiceSet()
    choose(result, choice_set, "R07", {"decision": "adopt", "option_id": "A"}, ["쿠폰 사용 실적"])

    document, _ = document_for(plan, choice_set)
    lines = texts(document, 7)
    # 문서 구조에는 표시 기호를 넣지 않는다 (Markdown 굵게는 render.py가 붙인다)
    assert "수집 담당: [추가 확정 필요]" in lines
    assert "확인 주기: [추가 확정 필요]" in lines
    assert any("수집 담당자" in item for item in document.pending)


def test_replace_mode_changes_original_line():
    plan = plan_with(target="방한 관광객")
    result = review_of(plan)
    choice_set = ChoiceSet()
    choose(result, choice_set, "R07", {"decision": "keep_original"})
    choose(result, choice_set, "R03", {"decision": "adopt", "option_id": "B"})
    choose(result, choice_set, "R12", {"decision": "keep_original"})

    document, _ = document_for(plan, choice_set)
    target_line = next(line for line in section_of(document, 2).lines if line.key == "target")
    assert target_line.state == "changed"
    assert "관광객과 거주 외국인을 구분하지 않음" in target_line.text
    change = next(c for c in document.changes if c.rule_id == "R03")
    assert change.before == "사업 대상: 방한 관광객"


def test_goal_exclusion_option_rewrites_goal_line():
    plan = plan_with(goals=[Goal.FOREIGN_SHARE, Goal.STORE_USAGE], usage_place="")
    result = review_of(plan)
    choice_set = ChoiceSet()
    choose(result, choice_set, "R07", {"decision": "keep_original"})
    choose(result, choice_set, "R01", {"decision": "adopt", "option_id": "B"})

    document, _ = document_for(plan, choice_set)
    goal_line = next(line for line in section_of(document, 2).lines if line.key == "goals")
    assert goal_line.text == "사업 목표: 외국인 결제 비중 확대"
    assert goal_line.state == "changed"


def test_modify_replaces_option_lines_with_user_text():
    plan = plan_with()
    result = review_of(plan)
    choice_set = ChoiceSet()
    choose(
        result,
        choice_set,
        "R07",
        {"decision": "modify", "option_id": "B", "modified_text": "분모 기준만 문서에 적는다"},
    )

    document, _ = document_for(plan, choice_set)
    lines = texts(document, 7)
    assert "분모 기준만 문서에 적는다" in lines
    assert "카드 지표는 단독 성과 판정에 사용하지 않음" not in lines
    assert document.changes[0].decision_label == "대안을 고쳐서 적용"
    assert document.changes[0].modified is True


def test_cancelled_choice_leaves_no_trace():
    plan = plan_with()
    result = review_of(plan)
    choice_set = ChoiceSet()
    choose(result, choice_set, "R07", ADOPT_A, ["쿠폰 사용 실적"])
    cancel_choice(choice_set, "R07")
    choose(result, choice_set, "R07", {"decision": "keep_original"})

    document, _ = document_for(plan, choice_set)
    assert document.changes == ()
    assert all("쿠폰 사용 실적" not in text for text in texts(document, 7))


def test_duplicate_lines_are_written_once():
    plan = plan_with(target="방한 관광객")
    result = review_of(plan)
    choice_set = ChoiceSet()
    choose(result, choice_set, "R07", ADOPT_A, ["쿠폰 사용 실적"])
    # 같은 묶음이라 화면에서도 같은 실행 입력을 다시 보낸다
    choose(result, choice_set, "R03", ADOPT_A, ["쿠폰 사용 실적"])
    choose(result, choice_set, "R12", {"decision": "keep_original"})

    document, _ = document_for(plan, choice_set)
    lines = texts(document, 7)
    assert lines.count("수집 담당: 관광과 김담당") == 1
    assert "참여자 확인 자료: 쿠폰 사용 실적" in lines


def test_hold_is_recorded_in_section_eight():
    plan = plan_with(target="방한 관광객")
    result = review_of(plan)
    choice_set = ChoiceSet()
    choose(result, choice_set, "R07", {"decision": "keep_original"})
    choose(result, choice_set, "R03", {"decision": "hold"})
    choose(result, choice_set, "R12", {"decision": "keep_original"})

    document, _ = document_for(plan, choice_set)
    # 8장 본문은 제목만 쓴다. 관리 번호는 별첨 변경 표·근거 추적에만 남는다 (9/18)
    assert any("대상과 자료 확인: 보류" in text for text in texts(document, 8))
    assert not any("R03 대상과 자료 확인" in text for text in texts(document, 8))


def test_held_outcome_is_recorded_without_choice():
    plan = plan_with(indicator_use=IndicatorUse.REFERENCE)
    evidence = load_evidence(__import__("evidence_helpers").fixture_path("missing_month"))
    document, _ = document_for(plan, ChoiceSet(), evidence=evidence)
    assert any("비교 가능한 인접 월 구간이 없어" in text for text in texts(document, 8))


def test_plan_pending_items_are_listed_once():
    plan = plan_with(indicator_use=IndicatorUse.REFERENCE)
    document, _ = document_for(plan)
    section8 = texts(document, 8)
    assert sum(1 for text in section8 if text.startswith("예산 (미정)")) == 1
    assert any(text.startswith("자료 확보 상태") for text in section8)


def test_filled_budget_and_data_status_reduce_pending():
    plan = plan_with(
        indicator_use=IndicatorUse.REFERENCE,
        budget=Budget(BudgetStatus.AMOUNT, krw=50_000_000, raw="50000000"),
        data_status=DataStatus.SECURED,
    )
    document, _ = document_for(plan)
    assert texts(document, 6)[0] == "예산: 50,000,000원"
    assert not any(text.startswith("예산") for text in texts(document, 8))


def test_request_draft_only_when_option_d_chosen():
    plan = plan_with()
    result = review_of(plan)
    choice_set = ChoiceSet()
    choose(result, choice_set, "R07", {"decision": "adopt", "option_id": "C"})
    document, _ = document_for(plan, choice_set)
    assert document.request_draft is None

    choose(result, choice_set, "R07", {"decision": "adopt", "option_id": "D"})
    document, _ = document_for(plan, choice_set)
    assert document.request_draft is not None
    assert "참여 점포 목록" in document.request_draft.targets


def test_evidence_refs_come_from_used_records():
    plan = plan_with()
    result = review_of(plan)
    choice_set = ChoiceSet()
    choose(result, choice_set, "R07", ADOPT_A, ["쿠폰 사용 실적"])
    document, _ = document_for(plan, choice_set)

    assert [ref.evidence_id for ref in document.evidence_refs] == ["DEMO-R07-SIGUNGU-강원-강릉시"]
    ref = document.evidence_refs[0]
    assert ref.scope_label == "강원특별자치도 강릉시 범위 참고 — 선택 지역의 진단이 아님"
    assert ref.data_kind == "synthetic" and ref.dataset_version == "demo-001"
    assert "합성 자료" in ref.limitations


def test_profile_summary_uses_only_the_selected_region_without_fallback():
    plan = plan_with(indicator_use=IndicatorUse.REFERENCE)
    document, _ = document_for(plan)
    summary = document.profile_summary
    assert summary.available is True
    assert summary.region_label == "강원특별자치도 강릉시"
    assert summary.dataset_version == "demo-001"
    assert any(line.startswith("업종 구성에서") for line in summary.lines)

    evidence = load_evidence(__import__("evidence_helpers").fixture_path("amount_up_share_down"))
    document, _ = document_for(plan, evidence=evidence)
    assert document.profile_summary.available is False
    assert "다른 지역 자료로 대신하지 않습니다" in document.profile_summary.note


def test_data_notice_shows_kind_and_version():
    document, _ = document_for(plan_with(indicator_use=IndicatorUse.REFERENCE))
    assert document.data_notice == "시연용 합성 수치 · 자료 버전 demo-001"
    assert document.created_on == "2026-09-17"


def test_created_on_is_injected():
    document, _ = document_for(plan_with(indicator_use=IndicatorUse.REFERENCE), today=date(2026, 12, 25))
    assert document.created_on == "2026-12-25"


def test_title_uses_plan_name():
    document, _ = document_for(plan_with(indicator_use=IndicatorUse.REFERENCE))
    assert document.title == "보완 기획안 — 하반기 외국인 소비지원 쿠폰"


def test_notice_choice_can_change_document():
    plan = plan_with(indicator_use=IndicatorUse.REFERENCE)
    result = review_of(plan)
    choice_set = ChoiceSet()
    choose(result, choice_set, "R07", {"decision": "adopt", "option_id": "B"})

    document, _ = document_for(plan, choice_set)
    assert "지표 해석 조건: 분모 기준(전체·미상 제외)과 전국 참고 범위를 함께 기록" in texts(document, 7)
