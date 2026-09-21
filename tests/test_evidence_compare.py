"""워크플로우 8-2·8-5장 비교 규칙. 기대값은 1근거계산계층계획.md 6장."""

from dataclasses import replace
from fractions import Fraction

import pytest
from evidence_helpers import fixture_path

from policy_signal_map.evidence.compare import (
    compare_months,
    compare_record,
    next_month,
    opposite_of,
)
from policy_signal_map.evidence.loader import load_evidence


def pairs_of(name: str):
    return compare_record(load_evidence(fixture_path(name)).file.records[0])


def directions(pair):
    return (pair.comparison_a.left, pair.comparison_a.right, pair.comparison_b.right)


def test_amount_up_share_down_is_opposite():
    (pair,) = pairs_of("amount_up_share_down")
    assert pair.status == "ok"
    assert directions(pair) == ("up", "down", "down")
    assert pair.comparison_a.opposite is True
    assert pair.comparison_b.opposite is False
    assert pair.foreign_amount_diff == 100
    assert pair.foreign_amount_growth_pct == Fraction(25, 2)
    assert pair.total_amount_growth_pct == 20
    assert pair.share_change_pp == Fraction(-1, 2)
    assert pair.known_only_share_change_pp == Fraction(-5, 9)


def test_amount_down_share_up_is_opposite():
    (pair,) = pairs_of("amount_down_share_up")
    assert directions(pair) == ("down", "up", "up")
    assert pair.comparison_a.opposite is True
    assert pair.foreign_amount_growth_pct == Fraction(-100, 9)
    assert pair.total_amount_growth_pct == Fraction(-50, 3)
    assert pair.share_change_pp == Fraction(1, 2)


def test_same_direction_is_not_opposite():
    (pair,) = pairs_of("same_direction")
    assert directions(pair) == ("up", "up", "up")
    assert pair.comparison_a.opposite is False


def test_flat_amount_or_share_is_not_opposite():
    first, second = pairs_of("flat_change")
    assert directions(first) == ("flat", "down", "down")
    assert first.comparison_a.opposite is False
    assert first.foreign_amount_growth_pct == 0
    assert directions(second) == ("up", "flat", "flat")
    assert second.comparison_a.opposite is False
    assert second.comparison_b.opposite is False
    assert second.share_change_pp == 0


def test_previous_zero_foreign_amount_has_no_growth_rate():
    (pair,) = pairs_of("prev_foreign_zero")
    assert pair.foreign_amount_growth_pct is None
    assert pair.foreign_amount_diff == 500
    assert pair.comparison_a.left == "up"
    assert pair.total_amount_growth_pct == 0


def test_missing_month_skips_both_pairs_and_does_not_bridge():
    pairs = pairs_of("missing_month")
    assert [(p.month_0, p.month_1) for p in pairs] == [("2026-01", "2026-02"), ("2026-02", "2026-03")]
    for pair in pairs:
        assert pair.status == "skipped"
        assert pair.skip_reason == "2026-02 자료 없음(no_data)"
        assert pair.comparison_a.opposite is None
        assert pair.share_change_pp is None


def test_tiny_change_keeps_direction():
    (pair,) = pairs_of("tiny_change")
    assert pair.comparison_a.opposite is True
    assert pair.share_change_pp == Fraction(-4, 10013)
    assert abs(pair.share_change_pp) < Fraction(1, 100)


def test_comparison_b_is_independent_from_a():
    (pair,) = pairs_of("known_only_differs")
    assert directions(pair) == ("down", "down", "up")
    assert pair.comparison_a.opposite is False
    assert pair.comparison_b.opposite is True


def test_large_amounts_use_exact_cross_product():
    record = load_evidence(fixture_path("large_amounts")).file.records[0]
    (pair,) = compare_record(record)
    assert pair.comparison_a.right == "up"

    # 소수점 계산으로 판정하면 틀린다: 이 사례가 교차곱 방식이 필요한 이유
    m0, m1 = record.months
    float_change = m1.foreign_amount / m1.total_amount - m0.foreign_amount / m0.total_amount
    assert float_change == 0.0


def test_zero_known_only_denominator_gives_none():
    (pair,) = pairs_of("unknown_equals_total")
    assert pair.status == "ok"
    assert pair.comparison_a.opposite is False
    assert pair.comparison_b.right is None
    assert pair.comparison_b.opposite is None
    assert pair.known_only_share_change_pp is None


def test_invalid_denominator_month_is_skipped():
    (pair,) = pairs_of("denominator_zero")
    assert pair.status == "skipped"
    assert pair.skip_reason == "2026-02 분모 0(invalid_denominator)"


def test_skip_reason_lists_both_months():
    record = load_evidence(fixture_path("missing_month")).file.records[0]
    no_data = record.months[1]
    pair = compare_months(no_data, replace(no_data, month="2026-03"))
    assert pair.skip_reason == "2026-02 자료 없음(no_data), 2026-03 자료 없음(no_data)"


def test_non_consecutive_months_are_not_compared():
    record = load_evidence(fixture_path("missing_month")).file.records[0]
    pair = compare_months(record.months[0], record.months[2])
    assert pair.status == "skipped"
    assert pair.skip_reason.startswith("연속되지 않은 월")


@pytest.mark.parametrize(
    "left, right, expected",
    [
        ("up", "down", True),
        ("down", "up", True),
        ("up", "up", False),
        ("down", "down", False),
        ("flat", "down", False),
        ("up", "flat", False),
        ("flat", "flat", False),
        (None, "up", None),
        ("down", None, None),
    ],
)
def test_opposite_of_truth_table(left, right, expected):
    assert opposite_of(left, right) is expected


def test_next_month_crosses_year():
    assert next_month("2026-12") == "2027-01"
    assert next_month("2026-09") == "2026-10"


def test_results_are_exact_fractions():
    (pair,) = pairs_of("amount_up_share_down")
    for value in (pair.foreign_amount_growth_pct, pair.total_amount_growth_pct, pair.share_change_pp):
        assert isinstance(value, Fraction)
