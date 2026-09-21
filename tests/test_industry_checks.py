"""사용처 업종 확인 R02 (docs/review_rules.md, 7지역확장계획.md 6장).

고른 사용처 업종이 그 지역 카드 결제에서 어느 정도인지 본다. 판정하지 않고 묻는다.
"""

import re
from dataclasses import replace

from fastapi.testclient import TestClient
from helpers import VALID_FORM

from policy_signal_map.app import app
from policy_signal_map.config import (
    LEGACY_DEMO_EVIDENCE_PATH as DEFAULT_EVIDENCE_PATH,
)
from policy_signal_map.evidence.loader import load_evidence
from policy_signal_map.evidence.profile_schema import (
    IndustryAgeBreakdown,
    RegionProfile,
    ShareItem,
    Thresholds,
)
from policy_signal_map.plan.models import BusinessType, Region, RegionLevel, sample_plan
from policy_signal_map.review.engine import run_review
from policy_signal_map.review.industry_checks import run_r02, run_r08
from policy_signal_map.review.rules import get_rule

DEMO = load_evidence(DEFAULT_EVIDENCE_PATH)
GANGNEUNG = "5115000000"  # 시연 자료에서 첫 업종의 결제가 0인 지역
GANGWON = "5100000000"
RULE = get_rule("R02")
RULE_R08 = get_rule("R08")


def item(code: str, *, share: float = 10.0, amount: int = 100, percentile: float | None = 50.0) -> ShareItem:
    return ShareItem(
        code=code,
        label=f"시연 {code}",
        amount=amount,
        share_pct=share,
        status="ok",
        percentile=percentile,
        regions=286 if percentile is not None else None,
    )


def profile(items, *, readiness: str = "ok") -> RegionProfile:
    return RegionProfile(
        region_key="ALL",
        geographic_scope="national",
        region_basis="unconfirmed",
        period_start="2026-01",
        period_end="2026-06",
        industry=tuple(items),
        readiness={"profile": "ok", "industry": readiness},
    )


def plan_with(codes: list[str]):
    return replace(sample_plan(), business_type=BusinessType.COUPON, usage_industries=codes)


THRESHOLDS = Thresholds(version="t1", rules={"R02": {"low_share_percentile": 20.0}})
R08_THRESHOLDS = Thresholds(version="t1", rules={"R08": {"low_share_percentile": 20.0}})


def run(codes: list[str], items, thresholds=THRESHOLDS, readiness: str = "ok"):
    return run_r02(RULE, plan_with(codes), profile(items, readiness=readiness), thresholds)


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def age_profile(groups, *, readiness: str = "ok") -> RegionProfile:
    industries = tuple(
        item(code, percentile=50.0) for code in dict.fromkeys(group.industry_code for group in groups)
    )
    return RegionProfile(
        region_key="ALL",
        geographic_scope="national",
        region_basis="unconfirmed",
        period_start="2026-01",
        period_end="2026-06",
        industry=industries,
        industry_age=tuple(groups),
        readiness={"profile": "ok", "industry_age": readiness},
    )


def age_group(industry_code: str, items) -> IndustryAgeBreakdown:
    return IndustryAgeBreakdown(industry_code, "known_only", tuple(items))


def run_age(
    industry_codes: list[str],
    age_codes: list[str],
    groups,
    thresholds=R08_THRESHOLDS,
    readiness: str = "ok",
):
    plan = replace(
        sample_plan(),
        business_type=BusinessType.AGE_TARGET,
        usage_industries=industry_codes,
        target_ages=age_codes,
    )
    return run_r08(RULE_R08, plan, age_profile(groups, readiness=readiness), thresholds)


# ---------------------------------------------------------------- 실행 조건


def test_업종을_고르지_않으면_묻지_않는다():
    assert run([], [item("IND01")]) is None


def test_비중이_높은_편이면_묻지_않는다():
    assert run(["IND01"], [item("IND01", percentile=80.0)]) is None


def test_기준값_이하면_묻는다():
    outcome = run(["IND01"], [item("IND01", percentile=12.0)])
    assert outcome.kind == "question"
    assert "낮은 편" in outcome.message


def test_기준값과_같으면_묻는다():
    assert run(["IND01"], [item("IND01", percentile=20.0)]).kind == "question"


def test_결제가_0이면_상점이_없다는_뜻이_아니라고_적는다():
    outcome = run(["IND01"], [item("IND01", amount=0, share=0.0, percentile=0.0)])
    assert outcome.kind == "question"
    assert "상점이 없다는 뜻은 아닙니다" in outcome.message


def test_결제_0과_비중_낮음이_함께_있으면_둘_다_적는다():
    outcome = run(
        ["IND01", "IND02"],
        [item("IND01", amount=0, share=0.0, percentile=0.0), item("IND02", percentile=5.0)],
    )
    assert "시연 IND01" in outcome.message and "시연 IND02" in outcome.message


def test_고른_업종만_본다():
    assert run(["IND02"], [item("IND01", percentile=1.0), item("IND02", percentile=90.0)]) is None


# ---------------------------------------------------------------- 자료가 없을 때


def test_지역_업종_자료가_없으면_보류한다():
    outcome = run_r02(RULE, plan_with(["IND01"]), None, THRESHOLDS)
    assert outcome.kind == "held"


def test_자료가_부족하다고_적혀_있으면_사유를_그대로_알린다():
    outcome = run(["IND01"], [item("IND01")], readiness="insufficient")
    assert outcome.kind == "held"
    assert "자료가 부족" in outcome.message


def test_기준값이_없으면_낮은_편을_서비스가_정하지_않는다():
    outcome = run(["IND01"], [item("IND01", percentile=1.0)], thresholds=None)
    assert outcome.kind == "held"


def test_기준값이_없어도_결제_0은_알린다():
    outcome = run(["IND01"], [item("IND01", amount=0, share=0.0, percentile=0.0)], thresholds=None)
    assert outcome.kind == "question"


def test_몇_곳_중인지_모르는_항목은_순위로_판단하지_않는다():
    assert run(["IND01"], [item("IND01", percentile=None)]) is None


# ---------------------------------------------------------------- 시연 자료와 화면


def test_시연_자료에서_결제_0_업종을_고르면_질문이_뜬다():
    plan = replace(
        sample_plan(),
        business_type=BusinessType.COUPON,
        region=Region(RegionLevel.SIGUNGU, sido_code=GANGWON, sigungu_code=GANGNEUNG),
        usage_industries=["IND01"],
    )
    outcome = next(o for o in run_review(plan, DEMO).outcomes if o.rule_id == "R02")
    assert outcome.kind == "question"


def test_대안_셋과_문서_문장이_있다():
    assert [o.id for o in RULE.options] == ["A", "B", "C"]
    assert RULE.option("C").execution_fields  # 참여 상점 현황은 수집 계획을 받는다


def test_3단계_화면에_보이고_규칙_번호는_없다():
    c = TestClient(app)
    c.post("/step/1", data={**VALID_FORM, "business_type": "coupon", "usage_industries": ["IND01"]})
    text = text_of(c.get("/step/3").text)
    assert "사용처 업종 확인" in text
    assert "R02" not in text


# ---------------------------------------------------------------- 대상과 고객 구성 R08


def test_R08은_업종과_대상_연령을_모두_골라야_확인한다():
    group = age_group("IND01", [item("AGE1", percentile=5.0)])
    assert run_age([], ["AGE1"], [group]) is None
    assert run_age(["IND01"], [], [group]) is None


def test_R08은_선택한_업종_안의_대상_연령_자리만_본다():
    groups = [
        age_group("IND01", [item("AGE1", percentile=80.0), item("AGE2", percentile=5.0)]),
        age_group("IND02", [item("AGE1", percentile=5.0)]),
    ]
    assert run_age(["IND01"], ["AGE1"], groups) is None


def test_R08은_운영_기준_이하이면_묻고_조합_이름을_적는다():
    outcome = run_age(["IND01"], ["AGE1"], [age_group("IND01", [item("AGE1", percentile=20.0)])])
    assert outcome.kind == "question"
    assert "시연 IND01 · 시연 AGE1" in outcome.message


def test_R08은_지역_자료가_없거나_준비되지_않으면_보류한다():
    plan = replace(
        sample_plan(), usage_industries=["IND01"], target_ages=["AGE1"], business_type=BusinessType.AGE_TARGET
    )
    assert run_r08(RULE_R08, plan, None, R08_THRESHOLDS).kind == "held"
    outcome = run_age(
        ["IND01"],
        ["AGE1"],
        [age_group("IND01", [item("AGE1")])],
        readiness="insufficient",
    )
    assert outcome.kind == "held" and "자료가 부족" in outcome.message


def test_R08은_기준값이_없으면_낮은_편을_정하지_않는다():
    outcome = run_age(
        ["IND01"], ["AGE1"], [age_group("IND01", [item("AGE1", percentile=1.0)])], thresholds=None
    )
    assert outcome.kind == "held"


def test_R08은_순위_분모가_없거나_조합이_빠지면_보류한다():
    no_rank = run_age(
        ["IND01"], ["AGE1"], [age_group("IND01", [item("AGE1", percentile=None)])]
    )
    missing = run_age(["IND01"], ["AGE2"], [age_group("IND01", [item("AGE1")])])
    assert no_rank.kind == "held"
    assert missing.kind == "held"


def test_R08은_일부_조합이_비어도_낮은_조합이_있으면_그_사실을_묻는다():
    outcome = run_age(
        ["IND01"],
        ["AGE1", "AGE2"],
        [age_group("IND01", [item("AGE1", percentile=5.0)])],
    )
    assert outcome.kind == "question"
    assert "AGE1" in outcome.message


def test_R08_대안_셋과_문서_문장이_있다():
    assert [option.id for option in RULE_R08.options] == ["A", "B", "C"]
    assert RULE_R08.option("C").execution_fields


def test_시연_자료의_업종별_연령_구성으로_R08_질문이_뜬다():
    plan = replace(
        sample_plan(),
        business_type=BusinessType.AGE_TARGET,
        region=Region(RegionLevel.SIGUNGU, sido_code=GANGWON, sigungu_code=GANGNEUNG),
        usage_industries=["IND02"],
        target_ages=["AGE1"],
    )
    outcome = next(outcome for outcome in run_review(plan, DEMO).outcomes if outcome.rule_id == "R08")
    assert outcome.kind == "question"


def test_R08이_3단계_화면에_보이고_규칙_번호는_없다():
    client = TestClient(app)
    client.post(
        "/step/1",
        data={
            **VALID_FORM,
            "business_type": "age_target",
            "usage_industries": ["IND02"],
            "target_ages": ["AGE1"],
        },
    )
    text = text_of(client.get("/step/3").text)
    assert "대상과 고객 구성" in text
    assert "R08" not in text
