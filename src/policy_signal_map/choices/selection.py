"""보완 선택 적용·취소·검증 (워크플로우 S03).

아직 없는 자료는 계획으로 남기고, 확보된 것처럼 바꾸지 않는다.
대안 D(정밀 분석)는 요청서 초안 상태로만 저장하며 계약·제공 확정 필드를 두지 않는다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from string import Formatter

from ..review.outcome import ReviewOutcome, ReviewResult
from ..review.rules import OptionSpec, merge_group_label, rules_by_id
from .models import Availability, Choice, ChoiceSet, Decision, ExecutionInput

REQUIRED_EXECUTION_FIELD = "collect_items"
# 문서 문장에서 공유 실행 조건 값을 쓰는 자리 (document/builder.py _values)
EXECUTION_PLACEHOLDERS = frozenset({"collect_items", "availability", "owner", "cycle"})


class ChoiceErrors(dict[str, str]):
    """필드 이름 → 사용자에게 보여줄 오류 문구."""


def _parse_decision(value: str | None) -> Decision | None:
    try:
        return Decision(value)  # type: ignore[arg-type]
    except ValueError:
        return None


def _parse_availability(value: str | None) -> tuple[Availability | None, bool]:
    if not value:
        return None, True
    try:
        return Availability(value), True
    except ValueError:
        return None, False


def parse_execution(single: Mapping[str, str], items: Sequence[str]) -> tuple[ExecutionInput, bool]:
    availability, ok = _parse_availability(single.get("availability"))
    execution = ExecutionInput(
        collect_items=tuple(item.strip() for item in items if item.strip()),
        availability=availability,
        owner=single.get("owner", "").strip(),
        cycle=single.get("cycle", "").strip(),
    )
    return execution, ok


def apply_choice(
    choice_set: ChoiceSet,
    outcome: ReviewOutcome,
    single: Mapping[str, str],
    collect_items: Sequence[str] = (),
    *,
    evidence_dataset_version: str | None = None,
    evidence_thresholds_version: str | None = None,
) -> ChoiceErrors:
    """검증에 통과하면 선택을 저장하고 빈 오류를 돌려준다."""
    errors = ChoiceErrors()

    decision = _parse_decision(single.get("decision"))
    if decision is None:
        errors["decision"] = "선택 항목을 골라 주세요."
        return errors

    option_id = (single.get("option_id") or "").strip() or None
    option = outcome.option(option_id) if option_id else None
    modified_text = (single.get("modified_text") or "").strip() or None

    if decision in (Decision.ADOPT, Decision.MODIFY):
        if option is None:
            errors["option_id"] = "대안을 골라 주세요."
        if decision is Decision.MODIFY and not modified_text:
            errors["modified_text"] = "수정할 내용을 적어 주세요."
    else:
        option_id, option, modified_text = None, None, None

    execution: ExecutionInput | None = None
    if option is not None and option.execution_fields:
        execution, availability_ok = parse_execution(single, collect_items)
        if not availability_ok:
            errors["availability"] = "확보 여부를 다시 골라 주세요."
        if REQUIRED_EXECUTION_FIELD in option.execution_fields and not execution.collect_items:
            errors["collect_items"] = "수집할 자료를 하나 이상 적어 주세요."

    if errors:
        return errors

    if execution is not None and outcome.merge_group:
        # 같은 묶음의 다른 질문도 이 입력을 함께 쓴다
        choice_set.set_execution(outcome.merge_group, execution)

    choice_set.put(
        Choice(
            question_key=outcome.question_key,
            rule_id=outcome.rule_id,
            decision=decision,
            merge_group=outcome.merge_group,
            option_id=option_id,
            modified_text=modified_text,
            reason=(single.get("reason") or "").strip(),
            evidence_ids=outcome.evidence_ids,
            needs_recheck=False,
            related_fields=outcome.related_fields,
            evidence_dataset_version=evidence_dataset_version,
            evidence_thresholds_version=evidence_thresholds_version,
        )
    )
    # 원안 유지·보류로 바꾸거나 실행 조건이 없는 대안으로 바꾸면 더 쓰지 않는 조건을 정리한다
    drop_unused_execution(choice_set, outcome.merge_group)
    return errors


def uses_execution(option: OptionSpec) -> bool:
    """공유 실행 조건을 쓰는 대안인지.

    입력칸이 있는 대안(R07·R03·R04의 A)뿐 아니라, 입력칸은 없어도 문서 문장에서 그 값을 가져다 쓰는 대안
    (R04 B의 "{cycle} 주기로 별도 확인")도 포함한다. 담당자가 입력한 값을 문서가 아직 쓰는 동안 지우지 않기 위해서다.
    """
    if option.execution_fields:
        return True
    lines = option.document.lines if option.document else ()
    return any(
        field in EXECUTION_PLACEHOLDERS for line in lines for _, field, _, _ in Formatter().parse(line) if field
    )


def drop_unused_execution(choice_set: ChoiceSet, merge_group: str | None) -> None:
    """묶음 안에 실행 조건을 쓰는 대안을 채택·수정한 선택이 하나도 없으면 실행 조건을 지운다.

    남겨 두면 문서 8장에 쓰지 않는 조건의 "추가 확정 필요"가 실린다 (6-5b: 질문이 사라졌을 때,
    채택을 원안 유지로 바꿨을 때, 대안 A를 B로 바꿨을 때 재현).
    """
    if not merge_group or merge_group not in choice_set.executions:
        return
    rules = rules_by_id()
    for choice in choice_set.choices.values():
        if choice.merge_group != merge_group or not choice.changes_document or not choice.option_id:
            continue
        option = rules[choice.rule_id].option(choice.option_id)
        if option is not None and uses_execution(option):
            return
    choice_set.executions.pop(merge_group, None)


def cancel_choice(choice_set: ChoiceSet, question_key: str) -> Choice | None:
    """선택을 지운다. 문서에도 그 변경이 남지 않는다 (워크플로우 12장)."""
    removed = choice_set.remove(question_key)
    if removed:
        drop_unused_execution(choice_set, removed.merge_group)
    return removed


def pending_from_choices(choice_set: ChoiceSet, result: ReviewResult) -> list[str]:
    """선택에서 생기는 "추가 확정 필요" 항목."""
    pending: list[str] = []
    for outcome in result.outcomes:
        choice = choice_set.get(outcome.question_key)
        if choice is None:
            continue
        if choice.decision is Decision.HOLD:
            pending.append(f"{outcome.title}: 보류")
    for merge_group, execution in choice_set.executions.items():
        for label in execution.pending_labels():
            pending.append(f"{merge_group_label(merge_group)}: {label}")
    return pending


def blocking_reasons(result: ReviewResult, choice_set: ChoiceSet) -> list[str]:
    """보완 기획안을 만들기 전에 해결해야 하는 것들 (4보완선택계획 결정 ⑥)."""
    reasons = []
    for outcome in result.questions:
        choice = choice_set.get(outcome.question_key)
        if choice is None:
            reasons.append(f"{outcome.title}: 아직 고르지 않았습니다")
        elif choice.needs_recheck:
            reasons.append(f"{outcome.title}: 기획 또는 근거 자료가 바뀌어 다시 확인이 필요합니다")
    return reasons
