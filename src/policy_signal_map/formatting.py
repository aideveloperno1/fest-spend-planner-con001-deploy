"""숫자·상태 표시 형식 (워크플로우 8-3장). 화면과 보완 기획안 문서가 함께 쓴다.

웹 객체에 의존하지 않는 순수 함수만 둔다. 반올림은 여기서만 한다.
- Fraction을 float로 바꾸지 않고 Decimal로 사사오입해 경계 값도 정확하다
- None은 어떤 함수에서도 0으로 표시하지 않는다
- 0이 아닌데 절대값이 0.01 미만이면 "0.01 미만"으로 적어 0처럼 보이지 않게 한다
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction

HUNDRED_MILLION = 100_000_000
_CENT = Decimal("0.01")
_DISPLAY_PRECISION = Fraction(1, 100)

NOT_COMPUTABLE = "계산 불가"
NO_DATA = "자료 없음"

DIRECTION_LABELS = {"up": "증가", "down": "감소", "flat": "변화 없음"}
CALCULATION_STATUS_LABELS = {
    "ok": "계산됨",
    "no_data": "자료 없음",
    "invalid_input": "입력 확인 필요",
    "invalid_denominator": "분모 0 · 계산 불가",
}


def _round_cent(value: Fraction) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 50
        return (Decimal(value.numerator) / Decimal(value.denominator)).quantize(_CENT, rounding=ROUND_HALF_UP)


def _two_decimals(value: Fraction | int, unit: str, *, signed: bool, show_direction: bool) -> str:
    number = Fraction(value)
    if number == 0:
        return f"0.00{unit}"
    if abs(number) < _DISPLAY_PRECISION:
        note = f" ({'증가' if number > 0 else '감소'})" if show_direction else ""
        return f"0.01{unit} 미만{note}"
    rounded = _round_cent(number)
    sign = "+" if signed and rounded > 0 else ""
    return f"{sign}{rounded:,}{unit}"


def amount_unit(max_total_amount: int | None) -> str:
    """레코드의 최대 전체 금액이 1억 원 이상이면 억원, 아니면 원."""
    return "억원" if max_total_amount is not None and max_total_amount >= HUNDRED_MILLION else "원"


def amount(value: int | None, unit: str) -> str:
    if value is None:
        return NO_DATA
    if unit == "억원":
        if value == 0:
            return "0원"
        return _two_decimals(Fraction(value, HUNDRED_MILLION), "억원", signed=False, show_direction=False)
    return f"{value:,}원"


def pct(value: Fraction | None) -> str:
    if value is None:
        return NOT_COMPUTABLE
    return _two_decimals(value, "%", signed=False, show_direction=False)


def growth(value: Fraction | None) -> str:
    if value is None:
        return NOT_COMPUTABLE
    return _two_decimals(value, "%", signed=True, show_direction=True)


def pp_change(value: Fraction | None) -> str:
    """비중 변화. "0.01%p 미만"은 중요성 기준이 아니라 표시 정밀도다 (8-3장)."""
    if value is None:
        return NOT_COMPUTABLE
    return _two_decimals(value, "%p", signed=True, show_direction=True)


def direction(value: str | None) -> str:
    return NOT_COMPUTABLE if value is None else DIRECTION_LABELS[value]


def comparison(opposite: bool | None, skipped: bool = False) -> str:
    if skipped:
        return "보류"
    if opposite is None:
        return "판단 불가"
    return "방향 다름" if opposite else "방향 같음"


def calc_status(status: str) -> str:
    return CALCULATION_STATUS_LABELS[status]


def _year_month(month: str) -> tuple[int, int]:
    return int(month[:4]), int(month[5:])


def month_label(month: str, same_year: bool = True) -> str:
    year, number = _year_month(month)
    return f"{number}월" if same_year else f"{year}년 {number}월"


def pair_label(month_0: str, month_1: str) -> str:
    (y0, m0), (y1, m1) = _year_month(month_0), _year_month(month_1)
    return f"{m0}→{m1}월" if y0 == y1 else f"{month_0}→{month_1}"


def period_label(start: str, end: str) -> str:
    (y0, m0), (y1, m1) = _year_month(start), _year_month(end)
    if (y0, m0) == (y1, m1):
        return f"{y0}년 {m0}월"
    if y0 == y1:
        return f"{y0}년 {m0}~{m1}월"
    return f"{y0}년 {m0}월~{y1}년 {m1}월"


FILTERS = {
    "amount": amount,
    "pct": pct,
    "growth": growth,
    "pp_change": pp_change,
    "direction": direction,
    "comparison": comparison,
    "calc_status": calc_status,
    "month_label": month_label,
    "pair_label": pair_label,
    "period_label": period_label,
}
