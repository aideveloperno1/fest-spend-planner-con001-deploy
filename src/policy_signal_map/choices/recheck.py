"""원안이 바뀌었을 때 선택을 재확인 대상으로 표시하고, 사라진 질문의 선택을 보관한다.

(워크플로우 11장: 목표·지역·지표가 바뀌면 영향받는 선택을 재확인 필요로 바꾸고 최종 문서 생성 전에 확인받는다)
"""

from __future__ import annotations

from dataclasses import replace

from ..review.outcome import ReviewResult
from ..review.rules import rules_by_id
from .models import ArchivedChoice, ChoiceSet
from .selection import drop_unused_execution

# 자료 값이 질문 조건에 직접 들어가는 질문. R04의 기간 질문은 원안 입력만 보므로
# 제외하고 시기 질문만 넣는다. R11은 인구값을 쓰지만 운영 기준값은 쓰지 않는다.
DATASET_QUESTION_KEYS = frozenset({"R07", "R02", "R08", "R04-season", "R11", "R12"})
THRESHOLD_QUESTION_KEYS = frozenset({"R02", "R08", "R04-season", "R12"})


def mark_recheck(choice_set: ChoiceSet, changed_fields: frozenset[str]) -> tuple[str, ...]:
    """바뀐 입력 항목과 관련 있는 선택만 재확인 대상으로 바꾼다.

    관련 항목은 **질문에서 받아 둔 값**을 먼저 쓴다. 한 규칙이 질문을 둘 이상 낼 때
    한쪽만 바뀌었는데 양쪽에 재확인 표시가 붙지 않게 하려는 것이다 (7지역확장계획.md 5장).
    값이 없는 선택(옛 방식으로 만든 것)은 규칙 값을 쓴다.
    """
    if not changed_fields:
        return ()
    rules = rules_by_id()
    marked = []
    for key, choice in list(choice_set.choices.items()):
        related = set(choice.related_fields or rules[choice.rule_id].related_fields)
        if related & changed_fields:
            choice_set.choices[key] = replace(choice, needs_recheck=True)
            marked.append(key)
    return tuple(marked)


def mark_evidence_recheck(
    choice_set: ChoiceSet,
    dataset_version: str,
    thresholds_version: str | None,
) -> tuple[str, ...]:
    """자료나 운영 기준 버전이 달라진 값 기반 선택만 재확인 대상으로 바꾼다."""
    marked = []
    for key, choice in list(choice_set.choices.items()):
        # 버전 문맥을 저장하기 전 선택은 비교할 기준이 없다. 서버 메모리 방식인 현재
        # 서비스에서는 새 선택에 항상 값이 들어가며, 기본값은 옛 호출부 호환용이다.
        if choice.evidence_dataset_version is None:
            continue
        dataset_changed = (
            key in DATASET_QUESTION_KEYS and choice.evidence_dataset_version != dataset_version
        )
        thresholds_changed = (
            key in THRESHOLD_QUESTION_KEYS
            and choice.evidence_thresholds_version != thresholds_version
        )
        if dataset_changed or thresholds_changed:
            choice_set.choices[key] = replace(choice, needs_recheck=True)
            marked.append(key)
    return tuple(marked)


def archive_missing(choice_set: ChoiceSet, result: ReviewResult) -> tuple[str, ...]:
    """다시 실행한 검토에 없는 질문의 선택을 보관함으로 옮긴다 (조용히 사라지지 않게)."""
    current = {outcome.question_key for outcome in result.outcomes}
    archived = []
    choice_set.last_archived = []
    for key in list(choice_set.choices):
        if key not in current:
            choice = choice_set.remove(key)
            if choice is not None:
                item = ArchivedChoice(choice)
                choice_set.archived.append(item)
                choice_set.last_archived.append(item)
                drop_unused_execution(choice_set, choice.merge_group)
                archived.append(key)
    return tuple(archived)


def sync_after_review(
    choice_set: ChoiceSet,
    result: ReviewResult,
    changed_fields: frozenset[str],
    dataset_version: str | None = None,
    thresholds_version: str | None = None,
) -> None:
    archive_missing(choice_set, result)
    mark_recheck(choice_set, changed_fields)
    if dataset_version is not None:
        mark_evidence_recheck(choice_set, dataset_version, thresholds_version)
