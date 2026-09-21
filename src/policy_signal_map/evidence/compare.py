"""인접 월의 금액·비중 비교 (워크플로우 8-2장).

- 비교 A: 외국인 금액 방향 vs 전체 분모 외국인 비중 방향
- 비교 B: 전체 분모 비중 방향 vs 미상 제외 분모 비중 방향

방향은 반올림한 퍼센트가 아니라 정수 교차곱의 부호로 정한다. 수치는 Fraction으로 돌려주고
반올림은 화면 표시 단계에서만 한다. 두 비교를 합친 점수는 만들지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from .schema import STATUS_LABELS, EvidenceRecord, MonthValue

Direction = Literal["up", "down", "flat"]


@dataclass(frozen=True)
class DirectionComparison:
    left: Direction | None
    right: Direction | None
    opposite: bool | None


@dataclass(frozen=True)
class MonthPair:
    month_0: str
    month_1: str
    status: Literal["ok", "skipped"]
    skip_reason: str | None
    foreign_amount_diff: int | None
    foreign_amount_growth_pct: Fraction | None
    total_amount_growth_pct: Fraction | None
    share_change_pp: Fraction | None
    known_only_share_change_pp: Fraction | None
    comparison_a: DirectionComparison
    comparison_b: DirectionComparison


_NOT_COMPARED = DirectionComparison(None, None, None)


def direction_of(value: int) -> Direction:
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "flat"


def opposite_of(left: Direction | None, right: Direction | None) -> bool | None:
    if left is None or right is None:
        return None
    if "flat" in (left, right):
        return False
    return left != right


def next_month(month: str) -> str:
    year, number = int(month[:4]), int(month[5:])
    return f"{year + 1:04d}-01" if number == 12 else f"{year:04d}-{number + 1:02d}"


def _ok_amounts(month: MonthValue) -> tuple[int, int, int]:
    # 검증을 통과한 ok 월은 F·T·U가 정수이고 T > 0이다
    F, T, U = month.foreign_amount, month.total_amount, month.unknown_amount
    if F is None or T is None or U is None or T <= 0:
        raise ValueError(f"{month.month} 월은 검증을 통과한 계산 가능 월이 아닙니다")
    return F, T, U


def _skipped(m0: MonthValue, m1: MonthValue, reason: str) -> MonthPair:
    return MonthPair(
        month_0=m0.month,
        month_1=m1.month,
        status="skipped",
        skip_reason=reason,
        foreign_amount_diff=None,
        foreign_amount_growth_pct=None,
        total_amount_growth_pct=None,
        share_change_pp=None,
        known_only_share_change_pp=None,
        comparison_a=_NOT_COMPARED,
        comparison_b=_NOT_COMPARED,
    )


def compare_months(m0: MonthValue, m1: MonthValue) -> MonthPair:
    # 누락 월을 건너뛰어 다음 달을 인접 월처럼 잇지 않는다
    if m1.month != next_month(m0.month):
        return _skipped(m0, m1, f"연속되지 않은 월 ({m0.month} → {m1.month})")

    not_ok = [m for m in (m0, m1) if m.calculation_status != "ok"]
    if not_ok:
        reason = ", ".join(
            f"{m.month} {STATUS_LABELS[m.calculation_status]}({m.calculation_status})" for m in not_ok
        )
        return _skipped(m0, m1, reason)

    F0, T0, U0 = _ok_amounts(m0)
    F1, T1, U1 = _ok_amounts(m1)

    amount_direction = direction_of(F1 - F0)
    share_direction = direction_of(F1 * T0 - F0 * T1)

    K0, K1 = T0 - U0, T1 - U1
    known_direction: Direction | None = None
    known_change: Fraction | None = None
    if K0 > 0 and K1 > 0:
        known_direction = direction_of(F1 * K0 - F0 * K1)
        known_change = (Fraction(F1, K1) - Fraction(F0, K0)) * 100

    return MonthPair(
        month_0=m0.month,
        month_1=m1.month,
        status="ok",
        skip_reason=None,
        foreign_amount_diff=F1 - F0,
        foreign_amount_growth_pct=None if F0 == 0 else Fraction(F1 - F0, F0) * 100,
        total_amount_growth_pct=Fraction(T1 - T0, T0) * 100,
        share_change_pp=(Fraction(F1, T1) - Fraction(F0, T0)) * 100,
        known_only_share_change_pp=known_change,
        comparison_a=DirectionComparison(amount_direction, share_direction, opposite_of(amount_direction, share_direction)),
        comparison_b=DirectionComparison(share_direction, known_direction, opposite_of(share_direction, known_direction)),
    )


def compare_record(record: EvidenceRecord) -> tuple[MonthPair, ...]:
    """레코드 하나의 인접 월 구간 전체. 서로 다른 레코드끼리는 비교하지 않는다."""
    months = record.months
    return tuple(compare_months(m0, m1) for m0, m1 in zip(months, months[1:]))
