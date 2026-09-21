"""원안 → 문장 (5보완기획안계획.md 2장). 입력에 없는 값을 추측하지 않는지 확인한다."""

from document_helpers import plan_with

from policy_signal_map.document.describe import budget_text, describe_plan, goal_labels, metric_labels, period_text
from policy_signal_map.document.models import NOT_IN_PLAN
from policy_signal_map.plan.models import Budget, BudgetStatus, Goal, Metric


def test_goal_other_uses_typed_text():
    plan = plan_with(goals=[Goal.OTHER], goal_other="야시장 활성화")
    assert goal_labels(plan) == "야시장 활성화"


def test_goal_exclusion_drops_one_goal():
    plan = plan_with(goals=[Goal.FOREIGN_SHARE, Goal.STORE_USAGE])
    assert goal_labels(plan, exclude=Goal.STORE_USAGE) == "외국인 결제 비중 확대"


def test_empty_goals_are_marked_not_in_plan():
    assert goal_labels(plan_with(goals=[])) == NOT_IN_PLAN
    assert metric_labels(plan_with(metrics=[])) == NOT_IN_PLAN


def test_metric_other_uses_typed_text():
    plan = plan_with(metrics=[Metric.OTHER], metric_other="점포 만족도")
    assert metric_labels(plan) == "점포 만족도"


def test_budget_text_by_status():
    assert budget_text(plan_with(budget=Budget(BudgetStatus.AMOUNT, krw=1_200_000, raw="1200000"))) == "1,200,000원"
    assert budget_text(plan_with(budget=Budget(BudgetStatus.UNDECIDED))) == "미정 [추가 확정 필요]"


def test_period_text_keeps_day_level_dates():
    assert period_text(plan_with()) == "2026-10-01 ~ 2026-12-31"
    assert period_text(plan_with(period_start="", period_end="")) == NOT_IN_PLAN


def test_describe_plan_has_eight_sections_with_keys():
    sections = describe_plan(plan_with())
    assert [section.number for section in sections] == [1, 2, 3, 4, 5, 6, 7, 8]
    keys = [line.key for section in sections for line in section.lines]
    assert "target" in keys and "goals" in keys and keys.count(None) == 0
    assert all(line.state == "original" for section in sections for line in section.lines)


def test_fixed_conditions_are_kept_in_section_one():
    sections = describe_plan(plan_with(fixed_conditions="예산 증액 불가"))
    texts = [line.text for line in sections[0].lines]
    assert "변경 불가 조건: 예산 증액 불가" in texts
