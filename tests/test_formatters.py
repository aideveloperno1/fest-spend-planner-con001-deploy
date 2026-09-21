import ast
from fractions import Fraction
from pathlib import Path

import pytest

from policy_signal_map import formatting as fmt
from policy_signal_map.web.templating import templates


def test_amount_unit_switches_at_one_hundred_million():
    assert fmt.amount_unit(99_999_999) == "원"
    assert fmt.amount_unit(100_000_000) == "억원"
    assert fmt.amount_unit(None) == "원"


def test_amount_in_eok_and_won():
    assert fmt.amount(210_618_000_000, "억원") == "2,106.18억원"
    assert fmt.amount(820, "원") == "820원"
    assert fmt.amount(1_234_567, "원") == "1,234,567원"
    assert fmt.amount(0, "억원") == "0원"


@pytest.mark.parametrize(
    "func",
    [
        lambda: fmt.amount(None, "원"),
        lambda: fmt.amount(None, "억원"),
        lambda: fmt.pct(None),
        lambda: fmt.growth(None),
        lambda: fmt.pp_change(None),
        lambda: fmt.direction(None),
        lambda: fmt.comparison(None),
    ],
)
def test_none_is_never_zero(func):
    text = func()
    assert "0" not in text


def test_pct_rounds_half_up_exactly():
    assert round(2.675, 2) == 2.67  # float 반올림은 경계에서 틀린다
    assert fmt.pct(Fraction(2675, 1000)) == "2.68%"
    assert fmt.pct(Fraction(640, 77)) == "8.31%"


def test_pp_change_sign_and_zero():
    assert fmt.pp_change(Fraction(2043, 10000)) == "+0.20%p"
    assert fmt.pp_change(Fraction(-547, 10000)) == "-0.05%p"
    assert fmt.pp_change(Fraction(0)) == "0.00%p"


def test_pp_change_below_display_precision():
    assert fmt.pp_change(Fraction(22, 10000)) == "0.01%p 미만 (증가)"
    assert fmt.pp_change(Fraction(-4, 10013)) == "0.01%p 미만 (감소)"


def test_pp_change_just_below_point_zero_one_is_not_rounded_up():
    assert fmt.pp_change(Fraction(9, 1000)) == "0.01%p 미만 (증가)"
    assert fmt.pp_change(Fraction(1, 100)) == "+0.01%p"


def test_small_nonzero_values_are_not_shown_as_zero():
    assert fmt.pct(Fraction(3, 1000)) == "0.01% 미만"
    assert fmt.growth(Fraction(1, 2000)) == "0.01% 미만 (증가)"
    assert fmt.amount(400_000, "억원") == "0.01억원 미만"


def test_growth_values():
    assert fmt.growth(Fraction(25, 2)) == "+12.50%"
    assert fmt.growth(Fraction(-6)) == "-6.00%"
    assert fmt.growth(Fraction(0)) == "0.00%"
    assert fmt.growth(None) == "계산 불가"


def test_direction_and_comparison_labels():
    assert [fmt.direction(v) for v in ("up", "down", "flat", None)] == ["증가", "감소", "변화 없음", "계산 불가"]
    assert fmt.comparison(True) == "방향 다름"
    assert fmt.comparison(False) == "방향 같음"
    assert fmt.comparison(None) == "판단 불가"
    assert fmt.comparison(None, skipped=True) == "보류"


def test_calc_status_labels():
    assert [fmt.calc_status(s) for s in ("ok", "no_data", "invalid_input", "invalid_denominator")] == [
        "계산됨",
        "자료 없음",
        "입력 확인 필요",
        "분모 0 · 계산 불가",
    ]


def test_month_pair_period_labels():
    assert fmt.month_label("2026-04") == "4월"
    assert fmt.month_label("2026-04", same_year=False) == "2026년 4월"
    assert fmt.pair_label("2026-01", "2026-02") == "1→2월"
    assert fmt.pair_label("2026-12", "2027-01") == "2026-12→2027-01"
    assert fmt.period_label("2026-01", "2026-06") == "2026년 1~6월"
    assert fmt.period_label("2025-12", "2026-02") == "2025년 12월~2026년 2월"
    assert fmt.period_label("2026-03", "2026-03") == "2026년 3월"


def test_filters_registered_in_templates():
    for name in fmt.FILTERS:
        assert templates.env.filters[name] is fmt.FILTERS[name]


def test_formatting_module_has_no_web_imports():
    source = Path(fmt.__file__).read_text(encoding="utf-8")
    modules = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add("." * node.level + (node.module or ""))
    assert not any(m.split(".")[0] in {"fastapi", "starlette", "jinja2"} or "web" in m for m in modules)
