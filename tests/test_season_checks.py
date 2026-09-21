"""사업 시기 확인(R04 시기)과 외국인 대상 기반 확인(R12).

값 기반 질문이라 고른 지역 자료만 쓴다. 자료가 없으면 넓히지 않는다.
"""

import re
from dataclasses import replace

from fastapi.testclient import TestClient
from helpers import VALID_FORM

from policy_signal_map.app import app
from policy_signal_map.evidence.profile_schema import Rank, RegionProfile, SeasonMonth, Thresholds
from policy_signal_map.plan.models import BusinessType, sample_plan
from policy_signal_map.review.rules import get_rule
from policy_signal_map.review.season_checks import plan_months, run_r04_season, run_r12, targets_foreign

R04 = get_rule("R04")
R12 = get_rule("R12")
THRESHOLDS = Thresholds(
    version="t1",
    rules={"R04": {"season_index": 1.10, "season_index_small_region": 1.25}, "R12": {"low_foreign_percentile": 20.0}},
)


def profile(
    *,
    months=(("2026-05", 1.20), ("2026-06", 1.00)),
    small: bool | None = False,
    foreign_percentile: float | None = 10.0,
    readiness: dict | None = None,
) -> RegionProfile:
    return RegionProfile(
        region_key="5115000000",
        geographic_scope="sigungu",
        region_basis="unconfirmed",
        period_start="2026-01",
        period_end="2026-06",
        months=tuple(
            SeasonMonth(month=m, status="ok" if v is not None else "no_data", season_index=v) for m, v in months
        ),
        ranks={"foreign_share": Rank(percentile=foreign_percentile, regions=286)} if foreign_percentile else {},
        small_region=small,
        readiness=readiness or {"profile": "ok", "season": "ok", "foreign": "ok"},
    )


def plan(**changes):
    base = replace(sample_plan(), period_start="2026-05-01", period_end="2026-05-31")
    return replace(base, **changes)


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


# ---------------------------------------------------------------- 기간에 든 달


def test_한_달짜리_사업은_그_달만_본다():
    assert plan_months(plan()) == ("2026-05",)


def test_여러_달에_걸치면_모두_본다():
    assert plan_months(plan(period_start="2026-04-20", period_end="2026-06-03")) == ("2026-04", "2026-05", "2026-06")


def test_해가_바뀌어도_이어_센다():
    assert plan_months(plan(period_start="2026-12-20", period_end="2027-01-05")) == ("2026-12", "2027-01")


def test_날짜가_뒤집히면_보지_않는다():
    assert plan_months(plan(period_start="2026-06-01", period_end="2026-05-01")) == ()


# ---------------------------------------------------------------- 시기 질문


def test_평소보다_컸던_달이_있으면_묻는다():
    outcome = run_r04_season(R04, plan(), profile(), THRESHOLDS)
    assert outcome.kind == "question"
    assert outcome.question_key == "R04-season"
    assert "5월" in outcome.message


def test_평소_수준이면_묻지_않는다():
    assert run_r04_season(R04, plan(), profile(months=(("2026-05", 1.00),)), THRESHOLDS) is None


def test_자료에_없는_달은_판단하지_않는다():
    """사업 시기가 제공 기간 밖이면 그 달은 보지 않는다."""
    outcome = run_r04_season(R04, plan(period_start="2026-10-01", period_end="2026-10-31"), profile(), THRESHOLDS)
    assert outcome is None


def test_결제_규모가_작은_지역은_기준을_더_높게_쓴다():
    작은지역 = profile(months=(("2026-05", 1.20),), small=True)
    assert run_r04_season(R04, plan(), 작은지역, THRESHOLDS) is None
    큰지역 = profile(months=(("2026-05", 1.20),), small=False)
    assert run_r04_season(R04, plan(), 큰지역, THRESHOLDS) is not None


def test_작은_지역_기준이_없으면_기본_기준을_쓴다():
    only_base = Thresholds(version="t1", rules={"R04": {"season_index": 1.10}})
    assert run_r04_season(R04, plan(), profile(small=True), only_base) is not None


def test_자료가_없으면_시기를_묻지_않는다():
    assert run_r04_season(R04, plan(), None, THRESHOLDS) is None
    없음 = profile(readiness={"profile": "ok", "season": "unlinked"})
    assert run_r04_season(R04, plan(), 없음, THRESHOLDS) is None


def test_기준값이_없으면_서비스가_정하지_않는다():
    assert run_r04_season(R04, plan(), profile(), None) is None


def test_기간_질문과_시기_질문은_대안이_다르다():
    assert [o.id for o in R04.options_for("period")] == ["A", "B"]
    season = R04.options_for("season")
    assert [o.document.section for o in season] == [3, 7]


# ---------------------------------------------------------------- 외국인 대상 기반


def test_외국인_대상일_때만_본다():
    assert targets_foreign(plan(target="외국인 전체")) is True
    assert targets_foreign(plan(target="방한 관광객")) is True
    # 국내 방문객은 외국인이 아니다
    assert targets_foreign(plan(target="국내 방문객")) is False


def test_외국인_비중이_낮은_편이면_묻는다():
    outcome = run_r12(R12, plan(target="외국인 전체"), profile(), THRESHOLDS)
    assert outcome.kind == "question"
    assert "방문 가능성을 뜻하지 않습니다" in outcome.message
    assert "286곳" in outcome.message


def test_외국인_비중이_높은_편이면_묻지_않는다():
    assert run_r12(R12, plan(target="외국인 전체"), profile(foreign_percentile=70.0), THRESHOLDS) is None


def test_대상이_외국인이_아니면_묻지_않는다():
    assert run_r12(R12, plan(target="국내 방문객"), profile(), THRESHOLDS) is None


def test_외국인_자료가_없으면_보류한다():
    outcome = run_r12(R12, plan(target="외국인 전체"), None, THRESHOLDS)
    assert outcome.kind == "held"


def test_전국에서의_자리를_모르면_낮은_편을_정하지_않는다():
    assert run_r12(R12, plan(target="외국인 전체"), profile(foreign_percentile=None), THRESHOLDS) is None


# ---------------------------------------------------------------- 화면


def test_축제_기획에서_두_질문이_함께_뜬다():
    c = TestClient(app)
    c.post(
        "/step/1",
        data={
            **VALID_FORM,
            "business_type": "festival",
            "target": "방한 관광객",
            "period_start": "2026-05-08",
            "period_end": "2026-05-10",
        },
    )
    text = text_of(c.get("/step/3").text)
    assert "외국인 대상 기반 확인" in text
    assert "R12" not in text and "R04" not in text


def test_축제_유형에만_켜진다():
    from policy_signal_map.review.packs import pack_rules

    assert "R12" in pack_rules(BusinessType.FESTIVAL)
    assert "R12" not in pack_rules(BusinessType.COUPON)
