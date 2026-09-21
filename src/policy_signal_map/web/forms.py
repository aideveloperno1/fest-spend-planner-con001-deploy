"""기획 입력 폼 값을 PlanInput으로 읽는다. 목록에 없는 선택값은 버린다."""

from collections.abc import Mapping, Sequence

from ..plan.models import (
    Budget,
    BudgetStatus,
    BusinessType,
    DataStatus,
    Goal,
    IndicatorUse,
    Metric,
    PlanInput,
    Region,
    RegionLevel,
)


def _one[E](enum: type[E], value: str | None) -> E | None:
    try:
        return enum(value)  # type: ignore[call-arg]
    except ValueError:
        return None


def _many[E](enum: type[E], values: Sequence[str]) -> list[E]:
    picked = [_one(enum, v) for v in values]
    # 순서를 유지하며 중복 제거
    return list(dict.fromkeys(p for p in picked if p is not None))


def parse_choice_form(form: Mapping[str, object]) -> tuple[dict[str, str], list[str]]:
    """보완 선택 폼: 단일 값과 수집자료 목록. 검증은 choices/selection.py가 한다."""
    single = {key: value for key, value in form.items() if isinstance(value, str)}
    raw_items = single.pop("collect_items", "")
    collect_items = [line.strip() for line in raw_items.replace(",", "\n").splitlines() if line.strip()]
    return single, collect_items


def _codes(values: Sequence[str], allowed: Sequence[str]) -> list[str]:
    """근거 파일이 알려 준 코드만 남긴다. 순서를 지키고 중복은 없앤다.

    자료에 없는 업종·연령을 기획안에 담지 않으려는 것이다. 알려진 목록이 비어 있으면
    (근거 파일이 없거나 프로필이 없으면) 화면에 입력칸도 없으므로 모두 버린다.
    """
    known = set(allowed)
    return list(dict.fromkeys(value for value in values if value in known))


def parse_plan_form(
    single: Mapping[str, str],
    multi: Mapping[str, Sequence[str]],
    *,
    industry_codes: Sequence[str] = (),
    age_codes: Sequence[str] = (),
) -> PlanInput:
    def text(name: str) -> str:
        return single.get(name, "").strip()

    level = _one(RegionLevel, single.get("region_level"))
    region = None
    if level is RegionLevel.NATIONAL:
        region = Region(level)
    elif level is RegionLevel.SIDO:
        region = Region(level, sido_code=text("sido"))
    elif level is RegionLevel.SIGUNGU:
        region = Region(level, sido_code=text("sido"), sigungu_code=text("sigungu"))

    raw_krw = text("budget_krw").replace(",", "")
    if single.get("budget_undecided"):
        # 금액을 함께 보냈으면 원문을 남겨 화면에서 고칠 수 있게 한다 (validation이 오류로 안내)
        budget = Budget(BudgetStatus.UNDECIDED, raw=text("budget_krw"))
    elif raw_krw == "":
        budget = Budget(BudgetStatus.UNSET)
    elif raw_krw.isdigit():
        budget = Budget(BudgetStatus.AMOUNT, krw=int(raw_krw), raw=raw_krw)
    else:
        budget = Budget(BudgetStatus.AMOUNT, krw=None, raw=text("budget_krw"))

    raw_visitors = text("visitor_goal").replace(",", "")
    # 빈칸은 적지 않은 것(None), 숫자로 읽지 못하면 원문만 남겨 화면에서 고치게 한다
    visitor_goal = int(raw_visitors) if raw_visitors.isdigit() else None

    return PlanInput(
        name=text("name"),
        business_type=_one(BusinessType, single.get("business_type")),
        goals=_many(Goal, multi.get("goals", [])),
        goal_other=text("goal_other"),
        target=text("target"),
        region=region,
        period_start=text("period_start"),
        period_end=text("period_end"),
        budget=budget,
        usage_place=text("usage_place"),
        usage_industries=_codes(multi.get("usage_industries", []), industry_codes),
        target_ages=_codes(multi.get("target_ages", []), age_codes),
        metrics=_many(Metric, multi.get("metrics", [])),
        metric_other=text("metric_other"),
        indicator_use=_one(IndicatorUse, single.get("indicator_use")),
        data_status=_one(DataStatus, single.get("data_status")),
        fixed_conditions=text("fixed_conditions"),
        visitor_goal=visitor_goal,
        visitor_goal_raw=text("visitor_goal"),
    )
