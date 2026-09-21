"""사용처 업종 확인 R02와 대상·고객 구성 R08 (7지역확장계획.md 6장).

담당자가 고른 사용처 업종이 **그 지역 카드 결제**에서 어느 정도인지 본다.

지키는 선
- **고른 지역 자료만 쓴다.** 자료가 없으면 넓히지 않고 보류한다 (다른 지역 값을 그 지역 것처럼 쓰지 않는다).
- **결제 0원과 자료 없음을 구분한다.** 0원은 "카드 결제가 잡히지 않았다"는 뜻이지 상점이 없다는 뜻이 아니다.
- **기준값은 코드에 적지 않고 근거 파일에서 받는다.** 기준값이 없으면 질문하지 않고 보류한다.
- 순위는 **몇 곳 중인지**를 아는 항목만 쓴다.
"""

from __future__ import annotations

from ..evidence.profile_schema import RegionProfile, ShareItem, Thresholds
from ..plan.models import PlanInput
from .basic_checks import _outcome
from .outcome import ReviewOutcome
from .rules import RuleInfo

THRESHOLD_KEY = "low_share_percentile"

NO_PROFILE_REASON = "이 지역의 업종별 자료가 아직 연결되지 않았습니다"
NO_THRESHOLD_REASON = "질문을 띄울 운영 기준이 근거 파일에 없습니다"
NO_INDUSTRY_AGE_REASON = "이 지역의 업종별 연령 구성 자료가 아직 연결되지 않았습니다"


def _picked(profile: RegionProfile, codes: list[str]) -> list[ShareItem]:
    """고른 업종 코드에 해당하는 항목. 자료에 없는 코드는 건너뛴다."""
    by_code = {item.code: item for item in profile.industry}
    return [by_code[code] for code in codes if code in by_code]


def run_r02(
    rule: RuleInfo,
    plan: PlanInput,
    profile: RegionProfile | None,
    thresholds: Thresholds | None,
) -> ReviewOutcome | None:
    if not plan.usage_industries:
        return None

    if profile is None or not profile.ready("industry"):
        reason = profile.readiness_note("industry") if profile else NO_PROFILE_REASON
        return _outcome(rule, "held", "held", reason=reason or NO_PROFILE_REASON)

    cutoff = thresholds.get(rule.id, THRESHOLD_KEY) if thresholds else None
    items = _picked(profile, plan.usage_industries)
    if not items:
        return _outcome(rule, "held", "held", reason=NO_PROFILE_REASON)
    if cutoff is None:
        # 기준값을 모르면 "낮은 편"을 서비스가 정하지 않는다. 결제 0원만 알린다
        zero = [item for item in items if item.no_payment]
        if not zero:
            return _outcome(rule, "held", "held", reason=NO_THRESHOLD_REASON)
        return _outcome(rule, "question", "question_zero", zero_list=", ".join(i.label for i in zero))

    zero = [item for item in items if item.no_payment]
    low = [
        item
        for item in items
        if not item.no_payment and item.has_rank and item.percentile is not None and item.percentile <= cutoff
    ]
    if not zero and not low:
        return None

    values = {"zero_list": ", ".join(i.label for i in zero), "low_list": ", ".join(i.label for i in low)}
    if zero and low:
        key = "question_both"
    elif zero:
        key = "question_zero"
    else:
        key = "question_low"
    outcome = _outcome(rule, "question", key, **{k: v for k, v in values.items() if v})

    # 화면에 함께 적을 수치. AI에는 넘기지 않는다 (outcome.to_llm_summary)
    return outcome.__class__(
        **{
            **outcome.__dict__,
            "observations": {
                "cutoff_percentile": cutoff,
                "regions": next((i.regions for i in (*zero, *low) if i.regions), None),
                "low": [(i.label, i.percentile) for i in low],
                "zero": [i.label for i in zero],
            },
        }
    )


def _unique(values: list[str]) -> list[str]:
    """입력 순서를 유지하면서 같은 선택을 한 번만 본다."""
    return list(dict.fromkeys(values))


def _picked_industry_ages(
    profile: RegionProfile,
    industry_codes: list[str],
    age_codes: list[str],
) -> tuple[list[tuple[str, ShareItem]], int]:
    """고른 업종×연령 항목과 원래 확인해야 할 조합 수."""
    picked_industries = _unique(industry_codes)
    picked_ages = _unique(age_codes)
    expected = len(picked_industries) * len(picked_ages)
    industry_labels = {item.code: item.label for item in profile.industry}
    groups = {group.industry_code: group for group in profile.industry_age}

    result: list[tuple[str, ShareItem]] = []
    for industry_code in picked_industries:
        group = groups.get(industry_code)
        if group is None:
            continue
        ages = {item.code: item for item in group.ages}
        industry_label = industry_labels.get(industry_code, industry_code)
        for age_code in picked_ages:
            item = ages.get(age_code)
            if item is not None:
                result.append((industry_label, item))
    return result, expected


def run_r08(
    rule: RuleInfo,
    plan: PlanInput,
    profile: RegionProfile | None,
    thresholds: Thresholds | None,
) -> ReviewOutcome | None:
    """고른 업종 안에서 선택한 대상 연령의 전국 자리가 운영 기준 이하인지 묻는다."""
    if not plan.usage_industries or not plan.target_ages:
        return None

    if profile is None or not profile.ready("industry_age"):
        reason = profile.readiness_note("industry_age") if profile else NO_INDUSTRY_AGE_REASON
        return _outcome(rule, "held", "held", reason=reason or NO_INDUSTRY_AGE_REASON)

    cutoff = thresholds.get(rule.id, THRESHOLD_KEY) if thresholds else None
    if cutoff is None:
        return _outcome(rule, "held", "held", reason=NO_THRESHOLD_REASON)

    picked, expected = _picked_industry_ages(profile, plan.usage_industries, plan.target_ages)
    comparable = [(industry, item) for industry, item in picked if item.has_value and item.has_rank]
    low = [
        (industry, item)
        for industry, item in comparable
        if item.percentile is not None and item.percentile <= cutoff
    ]
    if low:
        outcome = _outcome(
            rule,
            "question",
            "question",
            low_list=", ".join(f"{industry} · {item.label}" for industry, item in low),
        )
        return outcome.__class__(
            **{
                **outcome.__dict__,
                "display_level": "reference" if rule.id in profile.reference_rules else "standard",
                "observations": {
                    "cutoff_percentile": cutoff,
                    "low": [(industry, item.label, item.percentile) for industry, item in low],
                    "compared": len(comparable),
                    "expected": expected,
                },
            }
        )

    # 일부 조합이 없거나 순위의 분모를 모르면, 확인한 조합만으로 "해당 없음"이라 하지 않는다.
    if len(comparable) < expected:
        return _outcome(rule, "held", "held", reason=NO_INDUSTRY_AGE_REASON)
    return None


RUNNERS = {"R02": run_r02, "R08": run_r08}
