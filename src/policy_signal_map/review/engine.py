"""검토 규칙 실행. 같은 입력이면 항상 같은 결과를 낸다 (난수·시간 사용 금지)."""

from __future__ import annotations

from dataclasses import replace

from ..evidence.loader import LoadResult
from ..plan.models import PlanInput
from . import basic_checks, capacity_checks, industry_checks, metric_checks, r07_indicator, season_checks
from .context import RecordSelection, exact_region_key, select_main
from .outcome import NoFinding, NotApplicable, ReviewOutcome, ReviewResult, not_reviewed_from
from .packs import NOT_IN_PACK_REASON, active_rules, check_pack_rules
from .rules import RuleInfo, load_rule_catalog, rules_by_id  # noqa: F401  (rules_by_id는 run_review에서 사용)

# 화면에 보여줄 순서: 성과지표 → 지표 범위 → 사용처 업종 → 대상 연령 → 대상 → 규모 → 기간 → 목표·사용처 → 운영 조건
RUN_ORDER = ("R07", "R10", "R02", "R08", "R03", "R12", "R11", "R04", "R01", "R05")

# 규칙 ID → 실행 함수. 파일이 함수 이름을 지정하지 못하게, 코드에 등록된 것만 부른다.
# 입력만 보는 규칙과, 지역 자료 값까지 보는 규칙을 나눈다
RUNNERS = {**basic_checks.RUNNERS, **metric_checks.RUNNERS}
VALUE_RUNNERS = {**industry_checks.RUNNERS, **season_checks.RUNNERS, **capacity_checks.RUNNERS}


def check_rule_functions() -> None:
    """실행해야 하는 규칙에 코드가 있는지 확인한다 (JSON과 코드가 어긋나지 않게).

    이 모듈을 불러올 때 한 번 실행한다. 화면을 여는 순간이 아니라 서버가 시작할 때 멈추게 하려는 것이다.
    """
    missing = [
        rule.id
        for rule in load_rule_catalog()
        if rule.scope in ("implement", "basic") and rule.id not in RUN_ORDER
    ]
    if missing:
        raise ValueError(f"실행 함수가 없는 규칙: {', '.join(missing)} (review_rules.json과 engine.RUN_ORDER 확인)")


def _with_related(outcomes: list[ReviewOutcome]) -> tuple[ReviewOutcome, ...]:
    """같은 merge_group 질문끼리 서로를 가리킨다. 카드를 합치지는 않는다 (3검토질문계획 결정 ④)."""
    result = []
    for outcome in outcomes:
        others = (
            tuple(
                other
                for other in outcomes
                if other is not outcome and other.merge_group == outcome.merge_group and other.kind == "question"
            )
            if outcome.merge_group and outcome.kind == "question"
            else ()
        )
        related = tuple(other.rule_id for other in others)
        titles = tuple(other.title for other in others)
        result.append(
            outcome
            if not related
            else replace(outcome, related_rule_ids=related, related_titles=titles)
        )
    return tuple(result)


def _run_rule(
    rule: RuleInfo, plan: PlanInput, result: LoadResult | None, selection: RecordSelection
) -> list[ReviewOutcome]:
    """규칙 하나가 내는 질문들. 한 규칙이 질문을 둘 낼 수도 있다 (예: 기간과 시기)."""
    found: list[ReviewOutcome | None] = []

    if rule.id == "R07":
        found.append(
            r07_indicator.run(
                rule,
                plan,
                result.file if result else None,
                selection.record,
                scope_label=selection.scope_label,
                region_note=selection.region_note,
            )
        )
    if rule.id in RUNNERS:
        found.append(RUNNERS[rule.id](rule, plan))
    if rule.id in VALUE_RUNNERS:
        # 지역 자료 값을 보는 규칙. 고른 지역 자료만 쓰고 넓히지 않는다
        key = exact_region_key(plan)
        profile = result.profile(key) if (result is not None and key) else None
        found.append(VALUE_RUNNERS[rule.id](rule, plan, profile, result.thresholds if result else None))

    return [outcome for outcome in found if outcome is not None]


def run_review(plan: PlanInput, evidence: LoadResult | None) -> ReviewResult:
    rules = rules_by_id()

    # 레코드는 한 번만 고른다. 2단계 화면과 같은 기준을 쓰게 하려는 것이다 (review/context.py)
    selection = select_main(evidence.file if evidence else None, plan)

    # 고른 사업 유형에 맞는 질문만 켠다. 유형을 고르지 않았으면 모두 켠다
    running = active_rules(plan.business_type, RUN_ORDER)

    outcomes: list[ReviewOutcome] = []
    no_finding: list[NoFinding] = []
    not_applicable = tuple(
        NotApplicable(rules[rule_id].id, rules[rule_id].title, NOT_IN_PACK_REASON)
        for rule_id in RUN_ORDER
        if rule_id not in running
    )
    for rule_id in running:
        rule = rules[rule_id]
        found = _run_rule(rule, plan, evidence, selection)
        if not found:
            # 조건을 확인했지만 물을 것이 없음 ("검토하지 않음"과 구분)
            no_finding.append(NoFinding(rule.id, rule.title))
        else:
            outcomes.extend(found)

    not_reviewed = tuple(
        not_reviewed_from(rule) for rule in load_rule_catalog() if rule.scope in ("example", "future")
    )

    return ReviewResult(
        outcomes=_with_related(outcomes),
        no_finding=tuple(no_finding),
        not_reviewed=not_reviewed,
        evidence_id=selection.record.evidence_id if selection.record else None,
        not_applicable=not_applicable,
    )


# 규칙 파일과 코드가 어긋나면 화면을 여는 순간이 아니라 서버가 시작할 때 멈춘다
check_rule_functions()
# 사업 유형 파일에 없는 규칙 번호가 적혀 있어도 마찬가지로 시작할 때 멈춘다
check_pack_rules(frozenset(rule.id for rule in load_rule_catalog()))
