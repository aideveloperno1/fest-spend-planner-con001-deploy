from dataclasses import replace

from policy_signal_map.plan.changes import CHANGE_FIELDS, diff_plan
from policy_signal_map.plan.models import (
    Budget,
    BudgetStatus,
    DataStatus,
    Goal,
    IndicatorUse,
    Metric,
    PlanInput,
    Region,
    RegionLevel,
    sample_plan,
)
from policy_signal_map.review.rules import load_rule_catalog


def changed(**values) -> frozenset[str]:
    before = sample_plan()
    after = replace(before, **values)
    return diff_plan(before, after)


def test_no_original_means_no_change():
    assert diff_plan(None, sample_plan()) == frozenset()


def test_same_plan_has_no_change():
    assert diff_plan(sample_plan(), sample_plan()) == frozenset()


def test_each_field_is_detected():
    assert changed(name="다른 사업") == {"name"}
    assert changed(goals=[Goal.FOREIGN_AMOUNT]) == {"goals"}
    assert changed(goal_other="기타 설명") == {"goals"}
    assert changed(metrics=[Metric.COUPON_USAGE]) == {"metrics"}
    assert changed(metric_others=["점포 만족도"]) == {"metrics"}
    assert changed(indicator_use=IndicatorUse.REFERENCE) == {"indicator_use"}
    assert changed(target="방한 관광객") == {"target"}
    assert changed(region=Region(RegionLevel.NATIONAL)) == {"region"}
    assert changed(period_end="2026-11-30") == {"period"}
    assert changed(budget=Budget(BudgetStatus.AMOUNT, krw=100, raw="100")) == {"budget"}
    assert changed(usage_place="다른 사용처") == {"usage_place"}
    assert changed(data_status=DataStatus.SECURED) == {"data_status"}
    assert changed(fixed_conditions="조건") == {"fixed_conditions"}


def test_several_changes_at_once():
    assert changed(target="방한 관광객", period_start="2026-10-05") == {"target", "period"}


def test_region_detail_change_is_detected():
    before = sample_plan()
    after = replace(before, region=Region(RegionLevel.SIGUNGU, sido_code="5100000000", sigungu_code="5111000000"))
    assert diff_plan(before, after) == {"region"}


def test_rule_related_fields_use_known_names():
    """규칙이 참조하는 항목 이름이 모두 여기 정의돼 있어야 재확인이 동작한다."""
    for rule in load_rule_catalog():
        for field in rule.related_fields:
            assert field in CHANGE_FIELDS, (rule.id, field)


def test_question_related_fields_use_known_names():
    """질문마다 따로 적은 항목 이름도 같은 목록 안에 있어야 한다 (7지역확장계획.md 5장)."""
    for rule in load_rule_catalog():
        for name, question in rule.questions.items():
            for field in question.related_fields:
                assert field in CHANGE_FIELDS, (rule.id, name, field)


def test_plan_fields_are_all_compared():
    """입력 항목이 늘어나면 비교 목록에도 넣어야 한다."""
    compared = set()
    for name in CHANGE_FIELDS:
        compared.add(name)
    plan_fields = {f for f in PlanInput.__dataclass_fields__}
    # goal_other·metric_others는 goals·metrics와 함께 비교하고, period_start/end는 period로 묶는다
    covered = compared | {"goal_other", "metric_others", "period_start", "period_end", "visitor_goal_raw"}
    assert plan_fields <= covered, plan_fields - covered
