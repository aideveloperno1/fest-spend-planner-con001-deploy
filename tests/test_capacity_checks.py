"""규모와 수용 여건 R11 (7지역확장계획.md 6장, docs/review_rules.md)."""

import re
from dataclasses import replace

from fastapi.testclient import TestClient
from helpers import VALID_FORM

from policy_signal_map.app import app
from policy_signal_map.config import (
    LEGACY_DEMO_EVIDENCE_PATH as DEFAULT_EVIDENCE_PATH,
)
from policy_signal_map.evidence.loader import load_evidence
from policy_signal_map.evidence.profile_schema import ExternalData, ExternalMeasure, RegionProfile, Thresholds
from policy_signal_map.plan.models import BusinessType, Region, RegionLevel, sample_plan
from policy_signal_map.review.capacity_checks import run_r11
from policy_signal_map.review.engine import run_review
from policy_signal_map.review.rules import get_rule

DEMO = load_evidence(DEFAULT_EVIDENCE_PATH)
GANGNEUNG = "5115000000"
GANGWON = "5100000000"
RULE = get_rule("R11")
THRESHOLDS = Thresholds("test", {"R11": {"visitor_to_resident_ratio": 1.0}})


def population(status: str = "ok", count: int | None = 1000) -> ExternalMeasure:
    return ExternalMeasure(
        status=status,
        count=count,
        observed_at="2026-06-30" if status == "ok" else None,
        source_name="시연용 합성 인구" if status == "ok" else None,
    )


def profile(*, measure: ExternalMeasure | None = None, readiness: str = "ok") -> RegionProfile:
    return RegionProfile(
        region_key=GANGNEUNG,
        geographic_scope="sigungu",
        region_basis="unconfirmed",
        period_start="2026-01",
        period_end="2026-06",
        external=ExternalData(population=measure or population()),
        readiness={"profile": "ok", "external": readiness},
    )


def plan(goal: int | None):
    return replace(sample_plan(), business_type=BusinessType.FESTIVAL, visitor_goal=goal)


def run(goal: int | None, item: RegionProfile | None = None):
    return run_r11(RULE, plan(goal), item if item is not None else profile(), THRESHOLDS)


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_목표_방문객_수를_적지_않으면_묻지_않는다():
    assert run(None) is None


def test_0명이나_인구보다_작은_목표는_묻지_않는다():
    assert run(0) is None
    assert run(999) is None


def test_인구와_같거나_큰_목표이면_묻는다():
    assert run(1000).kind == "question"
    assert run(1001).kind == "question"


def test_질문에_두_집단이_같지_않고_규모_참고라는_한계를_적는다():
    outcome = run(1000)
    assert "같은 집단이 아니며" in outcome.message
    assert "규모를 가늠하는 참고" in outcome.message
    assert "2026-06-30" in outcome.message and "시연용 합성 인구" in outcome.message


def test_지역_프로필이나_외부_자료가_없으면_보류한다():
    assert run_r11(RULE, plan(1000), None, THRESHOLDS).kind == "held"
    unavailable = profile(readiness="unlinked")
    assert run(1000, unavailable).kind == "held"


def test_인구_항목이_사용_가능하지_않으면_보류한다():
    unavailable = profile(measure=population("no_data", None))
    assert run(1000, unavailable).kind == "held"


def test_운영_기준이_없으면_하드코딩하지_않고_보류한다():
    assert run_r11(RULE, plan(1000), profile(), None).kind == "held"


def test_시연_자료의_외부_인구로_R11을_실행한다():
    demo_profile = DEMO.profile(GANGNEUNG)
    goal = demo_profile.external.population.count
    festival = replace(
        sample_plan(),
        business_type=BusinessType.FESTIVAL,
        region=Region(RegionLevel.SIGUNGU, sido_code=GANGWON, sigungu_code=GANGNEUNG),
        visitor_goal=goal,
    )
    outcome = next(item for item in run_review(festival, DEMO).outcomes if item.rule_id == "R11")
    assert outcome.kind == "question"


def test_대안_셋과_문서_문장이_있다():
    assert [option.id for option in RULE.options] == ["A", "B", "C"]
    assert RULE.option("A").execution_fields


def test_3단계_화면에_보이고_규칙_번호는_없다():
    client = TestClient(app)
    client.post(
        "/step/1",
        data={**VALID_FORM, "business_type": "festival", "visitor_goal": "99999999"},
    )
    text = text_of(client.get("/step/3").text)
    assert "규모와 수용 여건" in text
    assert "R11" not in text
