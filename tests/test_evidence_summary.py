from fractions import Fraction

from evidence_helpers import base_data, fixture_path

from policy_signal_map.evidence.compare import compare_record
from policy_signal_map.evidence.loader import load_evidence
from policy_signal_map.evidence.schema import parse_evidence
from policy_signal_map.evidence.summary import period_totals, summarize_pairs


def record_of(name: str):
    return load_evidence(fixture_path(name)).file.records[0]


def test_period_share_uses_summed_amounts_not_average():
    record = record_of("flat_change")
    totals = period_totals(record)
    assert (totals.foreign_amount, totals.total_amount, totals.unknown_amount) == (3200, 43000, 4000)
    assert totals.foreign_share_pct == Fraction(3200, 43000) * 100
    monthly_average = sum(Fraction(m.foreign_amount, m.total_amount) * 100 for m in record.months) / 3
    assert totals.foreign_share_pct != monthly_average


def test_period_totals_exclude_non_ok_months():
    totals = period_totals(record_of("missing_month"))
    assert totals.months_used == ("2026-01", "2026-03")
    assert totals.months_excluded == ("2026-02",)
    assert (totals.foreign_amount, totals.total_amount, totals.unknown_amount) == (1700, 22000, 2200)


def test_pair_summary_counts():
    summary = summarize_pairs(compare_record(record_of("flat_change")))
    assert summary.pair_count == 2
    assert summary.comparable_count == 2
    assert summary.opposite_a_count == 0
    assert summary.same_a_count == 2


def test_pair_summary_with_skipped():
    summary = summarize_pairs(compare_record(record_of("missing_month")))
    assert summary.pair_count == 2
    assert summary.skipped_count == 2
    assert summary.comparable_count == 0
    assert summary.opposite_a_count == summary.same_a_count == 0


def test_pair_summary_counts_undetermined_b():
    summary = summarize_pairs(compare_record(record_of("unknown_equals_total")))
    assert summary.comparable_count == 1
    assert summary.same_a_count == 1
    assert summary.undetermined_b_count == 1


def test_no_ok_months_gives_none_shares():
    data = base_data()
    for month in data["records"][0]["months"]:
        month.update(
            calculation_status="no_data",
            foreign_amount=None,
            total_amount=None,
            unknown_amount=None,
            transaction_count=None,
            foreign_share_pct=None,
            known_only_share_pct=None,
            unknown_share_pct=None,
        )
    record = parse_evidence(data).file.records[0]
    totals = period_totals(record)
    assert totals.months_used == ()
    assert totals.foreign_share_pct is None
    assert totals.known_only_share_pct is None
