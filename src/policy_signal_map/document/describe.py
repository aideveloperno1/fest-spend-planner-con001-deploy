"""입력한 원안을 사람이 읽는 문장으로 옮긴다. 화면 요약과 문서가 같은 함수를 쓴다.

입력에 없는 값은 추측해 채우지 않고 "원안에 기재 없음 [추가 확정 필요]"로 적는다 (최종기획서 3장).
"""

from __future__ import annotations

from ..formatting import amount
from ..labels import DATA_STATUS_LABELS, GOAL_LABELS, INDICATOR_USE_LABELS, METRIC_LABELS
from ..plan.models import BudgetStatus, Goal, Metric, PlanInput
from ..plan.regions import region_label
from .models import NOT_IN_PLAN, PENDING_MARK, Line, Section


def goal_labels(plan: PlanInput, exclude: Goal | None = None) -> str:
    labels = [
        plan.goal_other if goal is Goal.OTHER else GOAL_LABELS[goal]
        for goal in plan.goals
        if goal is not exclude
    ]
    return ", ".join(label for label in labels if label) or NOT_IN_PLAN


def metric_labels(plan: PlanInput) -> str:
    labels = [METRIC_LABELS[metric] for metric in plan.metrics if metric is not Metric.OTHER]
    labels.extend(plan.metric_others)
    return ", ".join(label for label in labels if label) or NOT_IN_PLAN


def budget_text(plan: PlanInput) -> str:
    if plan.budget.status is BudgetStatus.AMOUNT and plan.budget.krw is not None:
        return amount(plan.budget.krw, "원")
    if plan.budget.status is BudgetStatus.UNDECIDED:
        return f"미정 {PENDING_MARK}"
    return NOT_IN_PLAN


def period_text(plan: PlanInput) -> str:
    """사업 기간은 날짜 단위라 그대로 적는다 (근거 자료의 월 단위 표기와 다르다)."""
    if not plan.period_start or not plan.period_end:
        return NOT_IN_PLAN
    return f"{plan.period_start} ~ {plan.period_end}"


def describe_plan(plan: PlanInput) -> list[Section]:
    period = period_text(plan)
    data_status = DATA_STATUS_LABELS[plan.data_status] if plan.data_status else NOT_IN_PLAN
    indicator_use = INDICATOR_USE_LABELS[plan.indicator_use] if plan.indicator_use else NOT_IN_PLAN

    sections = [
        Section(
            1,
            [
                Line(f"사업명: {plan.name or NOT_IN_PLAN}", key="name"),
                Line(f"사업 기간: {period}", key="period"),
                Line(f"지역: {region_label(plan.region) or NOT_IN_PLAN}", key="region"),
            ],
        ),
        Section(
            2,
            [
                Line(f"사업 목표: {goal_labels(plan)}", key="goals"),
                Line(f"사업 대상: {plan.target or NOT_IN_PLAN}", key="target"),
            ],
        ),
        Section(
            3,
            [
                Line(f"사업 기간: {period}", key="period_detail"),
                Line(f"세부 일정: {NOT_IN_PLAN}", key="schedule"),
            ],
        ),
        Section(
            4,
            [
                Line(f"쿠폰 사용처: {plan.usage_place or NOT_IN_PLAN}", key="usage_place"),
            ],
        ),
        Section(
            5,
            [
                Line(f"모집·정산 방법: {NOT_IN_PLAN}", key="recruit"),
            ],
        ),
        Section(
            6,
            [
                Line(f"예산: {budget_text(plan)}", key="budget"),
            ],
        ),
        Section(
            7,
            [
                Line(f"현재 성과지표: {metric_labels(plan)}", key="metrics"),
                Line(f"지표 용도: {indicator_use}", key="indicator_use"),
                Line(f"성과 자료 확보 상태: {data_status}", key="data_status"),
                Line(f"자료 수집 방법: {NOT_IN_PLAN}", key="collection"),
            ],
        ),
        Section(8, []),
    ]
    if plan.fixed_conditions:
        sections[0].lines.append(Line(f"변경 불가 조건: {plan.fixed_conditions}", key="fixed_conditions"))
    return sections
