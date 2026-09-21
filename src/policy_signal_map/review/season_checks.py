"""사업 시기 확인(R04 시기)과 외국인 대상 기반 확인(R12).

둘 다 **고른 지역 자료 값**을 보고 묻는다. 자료가 없으면 넓히지 않고 보류하거나 묻지 않는다.

시기 질문
- 사업 기간에 든 달 가운데, 그 지역에서 결제가 평소보다 컸던 달이 있으면 묻는다.
- 자료에 없는 달(제공 기간 밖)은 **판단하지 않는다.** 6개월 자료라 계절성으로 단정하지 않는다.
- 결제 규모가 작은 지역은 달마다 크게 흔들려 기준을 따로 쓴다(근거 파일이 알려 줄 때만).

외국인 대상 기반
- "비중이 낮다"를 "방문 가능성이 낮다"로 쓰지 않는다. 지금 카드 결제에 잡힌 규모를 말할 뿐이다.
"""

from __future__ import annotations

from datetime import date

from ..evidence.profile_schema import RegionProfile, Thresholds
from ..formatting import month_label
from ..plan.models import PlanInput
from .basic_checks import _outcome
from .outcome import ReviewOutcome
from .rules import RuleInfo

SEASON_KEY = "season_index"
SEASON_SMALL_KEY = "season_index_small_region"
FOREIGN_KEY = "low_foreign_percentile"

# 외국인 대상일 때만 묻는다. "국내 방문객"처럼 외국인이 아닌 대상에는 걸리지 않게 한다
FOREIGN_WORDS = ("외국인", "방한")
NO_PROFILE_REASON = "이 지역의 자료가 아직 연결되지 않았습니다"


def plan_months(plan: PlanInput) -> tuple[str, ...]:
    """사업 기간에 걸친 달 목록 (YYYY-MM). 날짜를 읽지 못하면 빈 값."""
    try:
        start = date.fromisoformat(plan.period_start)
        end = date.fromisoformat(plan.period_end)
    except ValueError:
        return ()
    if end < start:
        return ()

    months: list[str] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        if len(months) > 120:  # 안전장치: 기간 입력이 이상해도 끝없이 돌지 않게
            break
    return tuple(months)


def _cutoff(rule: RuleInfo, thresholds: Thresholds | None, profile: RegionProfile) -> float | None:
    if profile.season_threshold is not None:
        # 전달본이 지역 규모 구간까지 반영해 확정한 지역별 기준을 우선한다.
        return profile.season_threshold
    if thresholds is None:
        return None
    if profile.small_region:
        # 작은 지역은 흔들림이 커서 더 높은 기준을 쓴다. 따로 정해 주지 않았으면 기본 기준
        return thresholds.get(rule.id, SEASON_SMALL_KEY) or thresholds.get(rule.id, SEASON_KEY)
    return thresholds.get(rule.id, SEASON_KEY)


def run_r04_season(
    rule: RuleInfo,
    plan: PlanInput,
    profile: RegionProfile | None,
    thresholds: Thresholds | None,
) -> ReviewOutcome | None:
    months = plan_months(plan)
    if not months:
        return None
    if profile is None or not profile.ready("season"):
        # 자료가 없으면 묻지 않는다. 기간 질문은 따로 돌기 때문에 여기서 보류 카드를 더 만들지 않는다
        return None

    cutoff = _cutoff(rule, thresholds, profile)
    if cutoff is None:
        return None

    by_month = {item.month: item for item in profile.months}
    high = [
        by_month[month]
        for month in months
        # 자료에 없는 달(제공 기간 밖)은 판단하지 않는다
        if month in by_month and by_month[month].season_index is not None and by_month[month].season_index >= cutoff
    ]
    if not high:
        return None

    outcome = _outcome(
        rule,
        "question",
        "question_season",
        question="season",
        month_list=", ".join(month_label(item.month) for item in high),
    )
    return outcome.__class__(
        **{
            **outcome.__dict__,
            "observations": {
                "cutoff": cutoff,
                "small_region": profile.small_region,
                "months": [(item.month, item.season_index) for item in high],
            },
        }
    )


def targets_foreign(plan: PlanInput) -> bool:
    """사업 대상에 외국인·관광객이 들어 있는지. 담당자가 쓴 문장을 그대로 본다."""
    return any(word in plan.target for word in FOREIGN_WORDS)


def run_r12(
    rule: RuleInfo,
    plan: PlanInput,
    profile: RegionProfile | None,
    thresholds: Thresholds | None,
) -> ReviewOutcome | None:
    if not targets_foreign(plan):
        return None
    if profile is None or not profile.ready("foreign"):
        reason = profile.readiness_note("foreign") if profile else NO_PROFILE_REASON
        return _outcome(rule, "held", "held", reason=reason or NO_PROFILE_REASON)

    cutoff = thresholds.get(rule.id, FOREIGN_KEY) if thresholds else None
    rank = profile.ranks.get("foreign_share")
    if cutoff is None or rank is None:
        # 기준값이나 전국에서의 자리를 모르면 "낮은 편"을 서비스가 정하지 않는다
        return None
    if rank.percentile > cutoff:
        return None

    outcome = _outcome(rule, "question", "question", regions=rank.regions, percentile=rank.percentile)
    return outcome.__class__(
        **{
            **outcome.__dict__,
            "observations": {"cutoff_percentile": cutoff, "percentile": rank.percentile, "regions": rank.regions},
        }
    )


RUNNERS = {"R04": run_r04_season, "R12": run_r12}
