"""보완 선택 로직 (4보완선택계획.md 3~5장)."""

from evidence_helpers import fixture_path

from policy_signal_map.choices.models import Availability, Choice, ChoiceSet, Decision, ExecutionInput
from policy_signal_map.choices.recheck import archive_missing, mark_evidence_recheck, mark_recheck, sync_after_review
from policy_signal_map.choices.selection import (
    apply_choice,
    blocking_reasons,
    cancel_choice,
    pending_from_choices,
    uses_execution,
)
from policy_signal_map.review.rules import rules_by_id
from policy_signal_map.config import (
    LEGACY_DEMO_EVIDENCE_PATH as DEFAULT_EVIDENCE_PATH,
)
from policy_signal_map.evidence.loader import load_evidence
from policy_signal_map.plan.models import IndicatorUse, Metric, sample_plan
from policy_signal_map.review.engine import run_review

DEMO = load_evidence(DEFAULT_EVIDENCE_PATH)
ADOPT_A = {"decision": "adopt", "option_id": "A", "owner": "관광과 김담당", "cycle": "월 1회", "availability": "available"}


def review(**changes):
    plan = sample_plan()
    for key, value in changes.items():
        setattr(plan, key, value)
    return plan, run_review(plan, DEMO)


def outcome_of(result, rule_id: str):
    return next(o for o in result.outcomes if o.rule_id == rule_id)


def test_adopt_option_a_saves_choice_and_execution():
    _, result = review()
    choice_set = ChoiceSet()
    errors = apply_choice(choice_set, outcome_of(result, "R07"), ADOPT_A, ["쿠폰 사용 실적"])

    assert errors == {}
    choice = choice_set.get("R07")
    assert choice.decision is Decision.ADOPT and choice.option_id == "A"
    assert choice.evidence_ids == ("DEMO-R07-SIGUNGU-강원-강릉시",)
    execution = choice_set.execution_for("participation_data")
    assert execution.collect_items == ("쿠폰 사용 실적",)
    assert execution.owner == "관광과 김담당"


def test_decision_must_be_known():
    _, result = review()
    errors = apply_choice(ChoiceSet(), outcome_of(result, "R07"), {"decision": "maybe"})
    assert errors == {"decision": "선택 항목을 골라 주세요."}


def test_adopt_requires_known_option():
    _, result = review()
    outcome = outcome_of(result, "R07")
    assert apply_choice(ChoiceSet(), outcome, {"decision": "adopt"}) == {"option_id": "대안을 골라 주세요."}
    assert apply_choice(ChoiceSet(), outcome, {"decision": "adopt", "option_id": "Z"}) == {
        "option_id": "대안을 골라 주세요."
    }


def test_modify_requires_text():
    _, result = review()
    outcome = outcome_of(result, "R07")
    assert apply_choice(ChoiceSet(), outcome, {"decision": "modify", "option_id": "B"}) == {
        "modified_text": "수정할 내용을 적어 주세요."
    }

    choice_set = ChoiceSet()
    assert apply_choice(
        choice_set, outcome, {"decision": "modify", "option_id": "B", "modified_text": "분모 기준만 적는다"}
    ) == {}
    assert choice_set.get("R07").modified_text == "분모 기준만 적는다"


def test_execution_requires_collect_items():
    _, result = review()
    errors = apply_choice(ChoiceSet(), outcome_of(result, "R07"), ADOPT_A, [])
    assert errors == {"collect_items": "수집할 자료를 하나 이상 적어 주세요."}


def test_unknown_availability_is_rejected():
    _, result = review()
    form = {**ADOPT_A, "availability": "언젠가"}
    assert apply_choice(ChoiceSet(), outcome_of(result, "R07"), form, ["쿠폰 사용 실적"]) == {
        "availability": "확보 여부를 다시 골라 주세요."
    }


def test_owner_and_cycle_may_be_empty_and_become_pending():
    _, result = review()
    choice_set = ChoiceSet()
    form = {"decision": "adopt", "option_id": "A", "availability": "negotiating"}
    assert apply_choice(choice_set, outcome_of(result, "R07"), form, ["쿠폰 사용 실적"]) == {}

    pending = pending_from_choices(choice_set, result)
    assert "참여 실적 자료: 수집 담당자" in pending
    assert "참여 실적 자료: 확인 주기" in pending
    assert "참여 실적 자료: 자료 확보 협의 (협의 중)" in pending


def test_keep_original_and_hold_clear_option_fields():
    _, result = review()
    choice_set = ChoiceSet()
    apply_choice(choice_set, outcome_of(result, "R07"), {"decision": "keep_original", "option_id": "A"})
    choice = choice_set.get("R07")
    assert choice.decision is Decision.KEEP_ORIGINAL
    assert choice.option_id is None and not choice.changes_document

    apply_choice(choice_set, outcome_of(result, "R07"), {"decision": "hold"})
    assert choice_set.get("R07").decision is Decision.HOLD
    assert "금액·비중과 성과지표 확인: 보류" in pending_from_choices(choice_set, result)


def test_cancel_removes_choice_and_unused_execution():
    _, result = review()
    choice_set = ChoiceSet()
    apply_choice(choice_set, outcome_of(result, "R07"), ADOPT_A, ["쿠폰 사용 실적"])
    assert cancel_choice(choice_set, "R07").rule_id == "R07"
    assert choice_set.get("R07") is None
    assert choice_set.execution_for("participation_data") is None


def test_shared_execution_is_kept_while_another_question_uses_it():
    plan, result = review(target="방한 관광객")
    choice_set = ChoiceSet()
    apply_choice(choice_set, outcome_of(result, "R07"), ADOPT_A, ["쿠폰 사용 실적"])
    apply_choice(choice_set, outcome_of(result, "R03"), {"decision": "adopt", "option_id": "A"}, ["정산 자료"])

    assert choice_set.execution_for("participation_data").collect_items == ("정산 자료",)
    cancel_choice(choice_set, "R07")
    assert choice_set.execution_for("participation_data") is not None  # R03이 아직 쓰고 있음
    cancel_choice(choice_set, "R03")
    assert choice_set.execution_for("participation_data") is None


def test_notice_can_be_chosen_but_is_not_required():
    _, result = review(indicator_use=IndicatorUse.REFERENCE)
    outcome = outcome_of(result, "R07")
    assert outcome.kind == "notice" and not outcome.needs_choice

    choice_set = ChoiceSet()
    assert blocking_reasons(result, choice_set) == []  # 고르지 않아도 다음 단계로 간다
    assert apply_choice(choice_set, outcome, {"decision": "adopt", "option_id": "B"}) == {}


def test_blocking_reasons_list_unanswered_questions():
    _, result = review(target="방한 관광객")
    choice_set = ChoiceSet()
    reasons = blocking_reasons(result, choice_set)
    assert len(reasons) == 2
    assert any(r.startswith("금액·비중과 성과지표 확인") and "아직 고르지" in r for r in reasons)

    apply_choice(choice_set, outcome_of(result, "R07"), {"decision": "hold"})
    apply_choice(choice_set, outcome_of(result, "R03"), {"decision": "keep_original"})
    assert blocking_reasons(result, choice_set) == []  # 보류도 결정으로 인정


def test_recheck_marks_only_related_choices():
    _, result = review(target="방한 관광객")
    choice_set = ChoiceSet()
    apply_choice(choice_set, outcome_of(result, "R07"), {"decision": "hold"})
    apply_choice(choice_set, outcome_of(result, "R03"), {"decision": "keep_original"})

    assert mark_recheck(choice_set, frozenset({"name"})) == ()
    assert not any(c.needs_recheck for c in choice_set.choices.values())

    assert set(mark_recheck(choice_set, frozenset({"target"}))) == {"R07", "R03"}
    assert blocking_reasons(result, choice_set)[0].endswith("다시 확인이 필요합니다")


def test_recheck_marks_budget_change_only_for_r05_related_choice():
    _, result = review()
    choice_set = ChoiceSet()
    apply_choice(choice_set, outcome_of(result, "R07"), {"decision": "hold"})
    assert mark_recheck(choice_set, frozenset({"budget"})) == ()  # R07은 예산과 무관


def test_dataset_version_change_marks_only_value_based_questions():
    choice_set = ChoiceSet()
    for key in ("R07", "R11", "R04-period"):
        choice_set.put(
            Choice(
                question_key=key,
                rule_id=key.split("-")[0],
                decision=Decision.KEEP_ORIGINAL,
                evidence_dataset_version="demo-old",
                evidence_thresholds_version="threshold-same",
            )
        )

    assert set(mark_evidence_recheck(choice_set, "demo-new", "threshold-same")) == {"R07", "R11"}
    assert choice_set.get("R04-period").needs_recheck is False


def test_threshold_version_change_does_not_mark_non_threshold_question():
    choice_set = ChoiceSet()
    for key in ("R02", "R08", "R04-season", "R11"):
        choice_set.put(
            Choice(
                question_key=key,
                rule_id=key.split("-")[0],
                decision=Decision.KEEP_ORIGINAL,
                evidence_dataset_version="demo-same",
                evidence_thresholds_version="threshold-old",
            )
        )

    assert set(mark_evidence_recheck(choice_set, "demo-same", "threshold-new")) == {
        "R02", "R08", "R04-season"
    }
    assert choice_set.get("R11").needs_recheck is False


def test_saving_choice_records_evidence_versions():
    _, result = review()
    choice_set = ChoiceSet()
    apply_choice(
        choice_set,
        outcome_of(result, "R07"),
        {"decision": "hold"},
        evidence_dataset_version="demo-current",
        evidence_thresholds_version="threshold-current",
    )
    choice = choice_set.get("R07")
    assert choice.evidence_dataset_version == "demo-current"
    assert choice.evidence_thresholds_version == "threshold-current"


def test_archive_moves_choices_for_questions_that_disappeared():
    _, result = review(target="방한 관광객")
    choice_set = ChoiceSet()
    apply_choice(choice_set, outcome_of(result, "R03"), {"decision": "keep_original"})

    _, narrowed = review()  # 대상을 되돌려 R03 질문이 사라진 검토
    assert archive_missing(choice_set, narrowed) == ("R03",)
    assert choice_set.get("R03") is None
    assert choice_set.archived[0].reason == "기획 또는 근거 변경으로 더 이상 해당하지 않음"


def test_sync_after_review_archives_and_marks():
    _, result = review(target="방한 관광객")
    choice_set = ChoiceSet()
    apply_choice(choice_set, outcome_of(result, "R07"), {"decision": "hold"})
    apply_choice(choice_set, outcome_of(result, "R03"), {"decision": "keep_original"})

    _, narrowed = review()
    sync_after_review(choice_set, narrowed, frozenset({"target"}))
    assert [a.choice.rule_id for a in choice_set.archived] == ["R03"]
    assert [a.choice.rule_id for a in choice_set.last_archived] == ["R03"]

    # 다음 원안 변경에서 보관한 것이 없으면 최근 보관 목록은 비고, 전체 기록은 남는다
    sync_after_review(choice_set, narrowed, frozenset({"name"}))
    assert choice_set.last_archived == []
    assert len(choice_set.archived) == 1
    assert choice_set.get("R07").needs_recheck


def test_held_question_has_no_options_so_cannot_be_adopted():
    plan = sample_plan()
    held = run_review(plan, load_evidence(fixture_path("missing_month")))
    outcome = outcome_of(held, "R07")
    assert outcome.kind == "held"
    assert apply_choice(ChoiceSet(), outcome, {"decision": "adopt", "option_id": "A"}) == {
        "option_id": "대안을 골라 주세요."
    }


def test_execution_pending_labels():
    assert ExecutionInput(collect_items=("자료",), availability=Availability.AVAILABLE, owner="담당", cycle="월 1회").pending_labels() == []
    assert ExecutionInput().pending_labels() == ["수집 담당자", "확인 주기", "자료 확보 여부"]


def test_rule_without_card_metric_has_no_question_to_answer():
    _, result = review(metrics=[Metric.COUPON_USAGE])
    assert all(o.rule_id != "R07" for o in result.outcomes)
    assert blocking_reasons(result, ChoiceSet()) == []


# ---------------------------------------------------------------- 쓰지 않는 실행 조건 (6-5b)


def test_which_options_use_shared_execution():
    rules = rules_by_id()
    used = {(r.id, o.id) for r in rules.values() for o in r.options if uses_execution(o)}
    # 입력칸이 있는 A들 + 문장에서 {cycle}을 쓰는 R04 B
    assert used == {
        ("R07", "A"),
        ("R03", "A"),
        ("R04", "A"),
        ("R04", "B"),
        ("R10", "A"),
        ("R02", "C"),
        ("R08", "C"),
        ("R11", "A"),
        ("R12", "A"),
    }


def test_keep_original_after_adopt_drops_execution():
    _, result = review()
    choice_set = ChoiceSet()
    apply_choice(choice_set, outcome_of(result, "R07"), ADOPT_A, ["쿠폰 사용 실적"])
    apply_choice(choice_set, outcome_of(result, "R07"), {"decision": "keep_original"})
    assert choice_set.execution_for("participation_data") is None


def test_switching_to_option_without_execution_drops_it():
    _, result = review()
    choice_set = ChoiceSet()
    apply_choice(choice_set, outcome_of(result, "R07"), ADOPT_A, ["쿠폰 사용 실적"])
    apply_choice(choice_set, outcome_of(result, "R07"), {"decision": "adopt", "option_id": "B"})
    assert choice_set.execution_for("participation_data") is None
    assert pending_from_choices(choice_set, result) == []


def test_archived_question_drops_execution():
    _, result = review()
    choice_set = ChoiceSet()
    apply_choice(choice_set, outcome_of(result, "R07"), ADOPT_A, ["쿠폰 사용 실적"])
    _, without_r07 = review(metrics=[Metric.COUPON_USAGE])
    archive_missing(choice_set, without_r07)
    assert choice_set.execution_for("participation_data") is None


def test_execution_is_kept_while_option_text_still_uses_it():
    # R04 B는 입력칸이 없지만 문서 문장에서 공유 주기를 쓴다 (사용자 결정 가, 9/17)
    _, result = review(period_start="2026-10-01", period_end="2026-10-20")
    choice_set = ChoiceSet()
    apply_choice(choice_set, outcome_of(result, "R07"), ADOPT_A, ["쿠폰 사용 실적"])
    apply_choice(choice_set, outcome_of(result, "R04"), {"decision": "adopt", "option_id": "B"})
    apply_choice(choice_set, outcome_of(result, "R07"), {"decision": "keep_original"})
    assert choice_set.execution_for("participation_data").cycle == "월 1회"
