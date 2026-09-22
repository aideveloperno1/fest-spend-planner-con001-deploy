"""시연용 합성 근거 파일 (1근거계산계층계획.md 9장)."""

from fractions import Fraction

import build_demo_evidence
from _evidence_builder import to_json_text

from policy_signal_map.config import (
    DEFAULT_EVIDENCE_PATH,
    LEGACY_DEMO_EVIDENCE_PATH,
    load_settings,
)
from policy_signal_map.evidence.compare import compare_record
from policy_signal_map.evidence.loader import find_record, is_real_evidence, load_evidence
from policy_signal_map.evidence.summary import period_totals, summarize_pairs


def demo():
    return load_evidence(LEGACY_DEMO_EVIDENCE_PATH)


def test_default_settings_point_to_demo_file_and_it_loads_without_warnings():
    result = load_evidence(load_settings({}).evidence_path)
    assert result.warnings == ()
    assert result.source_path == DEFAULT_EVIDENCE_PATH
    assert result.file.dataset_version == "demo-hierarchy-002"
    assert result.file.data_kind == "synthetic"
    assert (len(result.file.records), len(result.profiles)) == (285, 285)
    assert not is_real_evidence(result.source_path, result.file)


def test_demo_file_matches_generator():
    assert LEGACY_DEMO_EVIDENCE_PATH.read_text(encoding="utf-8") == to_json_text(
        build_demo_evidence.build()
    )


def test_national_record_mixes_opposite_and_same_directions():
    record = find_record(demo().file, "national", "ALL")
    pairs = compare_record(record)
    summary = summarize_pairs(pairs)
    assert (summary.pair_count, summary.comparable_count) == (5, 5)
    assert (summary.opposite_a_count, summary.same_a_count) == (2, 3)
    assert [p.comparison_a.opposite for p in pairs] == [True, True, False, False, False]
    # 04→05는 0.01%p 미만의 같은 방향 변화 (표시 규칙 확인용)
    assert 0 < pairs[3].share_change_pp < Fraction(1, 100)


def test_national_period_share_differs_from_monthly_average():
    record = find_record(demo().file, "national", "ALL")
    totals = period_totals(record)
    assert (totals.foreign_amount, totals.total_amount, totals.unknown_amount) == (5185, 61890, 3730)
    assert round(float(totals.foreign_share_pct), 10) == 8.3777670060
    average = sum(Fraction(m.foreign_amount, m.total_amount) * 100 for m in record.months) / 6
    assert round(float(average), 10) == 8.3759582834


def test_sido_hold_record_has_one_comparable_pair():
    record = find_record(demo().file, "sido", "DEMO-SIDO-A")
    summary = summarize_pairs(compare_record(record))
    assert (summary.comparable_count, summary.skipped_count) == (1, 4)
    assert record.applicability["R07"].status == "needs_review"


def test_demo_uses_synthetic_scale_only():
    # 실제 분석은 억원 단위(수천억 원)다. 합성 파일은 수만 원 이하 가상 규모만 쓴다
    for record in demo().file.records:
        assert record.data_kind == "synthetic"
        assert "합성 자료" in record.limitations
        for month in record.months:
            assert (month.total_amount or 0) < 100_000
