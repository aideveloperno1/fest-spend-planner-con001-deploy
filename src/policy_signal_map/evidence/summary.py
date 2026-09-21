"""기간 합산과 구간 요약. 문장은 만들지 않는다 (review/·web/의 몫).

반대 방향 구간만 골라내는 함수는 두지 않는다 (워크플로우 8-3장: 모든 인접 구간 제공).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from .compare import MonthPair
from .schema import EvidenceRecord


@dataclass(frozen=True)
class PeriodTotals:
    months_used: tuple[str, ...]
    months_excluded: tuple[str, ...]
    foreign_amount: int
    total_amount: int
    unknown_amount: int
    foreign_share_pct: Fraction | None
    known_only_share_pct: Fraction | None
    unknown_share_pct: Fraction | None


@dataclass(frozen=True)
class PairSummary:
    pair_count: int
    comparable_count: int
    skipped_count: int
    opposite_a_count: int
    same_a_count: int
    undetermined_a_count: int
    opposite_b_count: int
    same_b_count: int
    undetermined_b_count: int


def _pct(numerator: int, denominator: int) -> Fraction | None:
    return None if denominator <= 0 else Fraction(numerator, denominator) * 100


def period_totals(record: EvidenceRecord) -> PeriodTotals:
    """계산 가능한 월의 F·T·U를 각각 더한 뒤 비중을 계산한다. 월 비중의 평균이 아니다 (8-1장)."""
    used = [m for m in record.months if m.calculation_status == "ok"]
    # 검증을 통과한 ok 월의 금액은 정수다
    F = sum(m.foreign_amount or 0 for m in used)
    T = sum(m.total_amount or 0 for m in used)
    U = sum(m.unknown_amount or 0 for m in used)
    return PeriodTotals(
        months_used=tuple(m.month for m in used),
        months_excluded=tuple(m.month for m in record.months if m.calculation_status != "ok"),
        foreign_amount=F,
        total_amount=T,
        unknown_amount=U,
        foreign_share_pct=_pct(F, T),
        known_only_share_pct=_pct(F, T - U),
        unknown_share_pct=_pct(U, T),
    )


def summarize_pairs(pairs: Sequence[MonthPair]) -> PairSummary:
    compared = [p for p in pairs if p.status == "ok"]
    return PairSummary(
        pair_count=len(pairs),
        comparable_count=len(compared),
        skipped_count=len(pairs) - len(compared),
        opposite_a_count=sum(p.comparison_a.opposite is True for p in compared),
        same_a_count=sum(p.comparison_a.opposite is False for p in compared),
        undetermined_a_count=sum(p.comparison_a.opposite is None for p in compared),
        opposite_b_count=sum(p.comparison_b.opposite is True for p in compared),
        same_b_count=sum(p.comparison_b.opposite is False for p in compared),
        undetermined_b_count=sum(p.comparison_b.opposite is None for p in compared),
    )
