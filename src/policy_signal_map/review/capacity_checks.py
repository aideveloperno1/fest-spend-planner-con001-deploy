"""목표 방문객 규모와 수용 여건 확인 R11.

주민등록인구는 방문객 수와 같은 집단이 아니다. 두 값을 직접 효과 지표로 비교하지 않고,
목표 규모를 가늠해 숙박·주차·교통 자료를 확인할지 묻는 데만 쓴다.
"""

from __future__ import annotations

from ..evidence.profile_schema import RegionProfile, Thresholds
from ..plan.models import PlanInput
from .basic_checks import _outcome
from .outcome import ReviewOutcome
from .rules import RuleInfo

NO_POPULATION_REASON = "이 지역의 외부 인구 자료가 아직 연결되지 않았습니다"
NO_THRESHOLD_REASON = "질문을 띄울 방문객·인구 비교 기준이 근거 파일에 없습니다"
THRESHOLD_KEY = "visitor_to_resident_ratio"


def run_r11(
    rule: RuleInfo,
    plan: PlanInput,
    profile: RegionProfile | None,
    thresholds: Thresholds | None,
) -> ReviewOutcome | None:
    """목표 방문객/주민등록인구 비율이 자료의 기준 이상이면 수용 여건을 묻는다."""
    if plan.visitor_goal is None:
        return None

    if profile is None or not profile.ready("external"):
        reason = profile.readiness_note("external") if profile else NO_POPULATION_REASON
        return _outcome(rule, "held", "held", reason=reason or NO_POPULATION_REASON)

    population = profile.external.population if profile.external else None
    if population is None or not population.has_value:
        return _outcome(rule, "held", "held", reason=NO_POPULATION_REASON)
    cutoff = thresholds.get(rule.id, THRESHOLD_KEY) if thresholds else None
    if cutoff is None or cutoff <= 0:
        return _outcome(rule, "held", "held", reason=NO_THRESHOLD_REASON)
    ratio = plan.visitor_goal / population.count
    if ratio < cutoff:
        return None

    outcome = _outcome(
        rule,
        "question",
        "question",
        visitor_goal=f"{plan.visitor_goal:,}",
        population=f"{population.count:,}",
        observed_at=population.observed_at,
        source_name=population.source_name,
    )
    return outcome.__class__(
        **{
            **outcome.__dict__,
            "observations": {
                "visitor_goal": plan.visitor_goal,
                "population": population.count,
                "visitor_to_resident_ratio": ratio,
                "cutoff_ratio": cutoff,
                "observed_at": population.observed_at,
                "source_name": population.source_name,
            },
        }
    )


RUNNERS = {"R11": run_r11}
