"""원안을 다시 제출했을 때 무엇이 바뀌었는지 (워크플로우 S05·11장).

항목 이름은 규칙 JSON의 related_fields와 같게 둔다. 이 이름이 겹치는 선택만 재확인 대상이 된다.
"""

from __future__ import annotations

from collections.abc import Callable

from .models import PlanInput

# 항목 이름 → 비교할 값
COMPARERS: dict[str, Callable[[PlanInput], object]] = {
    "name": lambda plan: plan.name,
    "business_type": lambda plan: plan.business_type,
    "goals": lambda plan: (tuple(plan.goals), plan.goal_other),
    "metrics": lambda plan: (tuple(plan.metrics), plan.metric_other),
    "indicator_use": lambda plan: plan.indicator_use,
    "target": lambda plan: plan.target,
    "region": lambda plan: plan.region,
    "period": lambda plan: (plan.period_start, plan.period_end),
    "budget": lambda plan: plan.budget,
    "usage_place": lambda plan: plan.usage_place,
    "usage_industries": lambda plan: tuple(plan.usage_industries),
    "target_ages": lambda plan: tuple(plan.target_ages),
    "data_status": lambda plan: plan.data_status,
    "fixed_conditions": lambda plan: plan.fixed_conditions,
    # 적지 않은 것(None)과 0명이라고 적은 것을 다르게 본다
    "visitor_goal": lambda plan: (plan.visitor_goal, plan.visitor_goal_raw),
}

CHANGE_FIELDS = tuple(COMPARERS)


def diff_plan(before: PlanInput | None, after: PlanInput) -> frozenset[str]:
    """바뀐 항목 이름. 원안이 없으면(첫 검토) 빈 집합."""
    if before is None:
        return frozenset()
    return frozenset(name for name, value_of in COMPARERS.items() if value_of(before) != value_of(after))
