"""사업 유형별로 켜지는 질문 (7지역확장계획.md 6-2장, review/packs.py).

담당자가 고른 유형에 맞는 질문만 켠다. 유형을 고르지 않은 기획은 아무 질문도 숨기지 않는다.
"""

import re
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from helpers import VALID_FORM

from policy_signal_map.app import app
from policy_signal_map.config import (
    LEGACY_DEMO_EVIDENCE_PATH as DEFAULT_EVIDENCE_PATH,
)
from policy_signal_map.evidence.loader import load_evidence
from policy_signal_map.plan.models import BusinessType, Goal, sample_plan
from policy_signal_map.review.engine import RUN_ORDER, run_review
from policy_signal_map.review.packs import active_rules, common_rules, pack_rules
from policy_signal_map.review.rules import load_rule_catalog

DEMO = load_evidence(DEFAULT_EVIDENCE_PATH)


def ran(business_type, **changes) -> set[str]:
    plan = replace(sample_plan(), business_type=business_type, **changes)
    result = run_review(plan, DEMO)
    return {o.rule_id for o in result.outcomes} | {n.rule_id for n in result.no_finding}


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


# ---------------------------------------------------------------- 목록


def test_공통_질문은_유형과_상관없이_켠다():
    for business_type in BusinessType:
        assert set(common_rules()) <= set(active_rules(business_type, RUN_ORDER))


def test_유형을_고르지_않으면_아무_질문도_숨기지_않는다():
    assert active_rules(None, RUN_ORDER) == RUN_ORDER


def test_실행_순서는_화면_순서를_따른다():
    picked = active_rules(BusinessType.FOREIGN_TOURISM, RUN_ORDER)
    assert list(picked) == [rule_id for rule_id in RUN_ORDER if rule_id in picked]


def test_같은_규칙이_두_유형에_있어도_한_번만_실행한다():
    picked = active_rules(BusinessType.FESTIVAL, RUN_ORDER)
    assert len(picked) == len(set(picked))


def test_사업_유형_파일에_적힌_번호는_모두_규칙_파일에_있다():
    known = {rule.id for rule in load_rule_catalog()}
    listed = set(common_rules())
    for business_type in BusinessType:
        listed |= set(pack_rules(business_type))
    assert listed <= known


# ---------------------------------------------------------------- 실제 실행


def test_쿠폰_유형은_목표와_사용처를_확인한다():
    assert "R01" in ran(BusinessType.COUPON, goals=[Goal.STORE_USAGE], usage_place="")


def test_쿠폰_유형에서는_외국인_질문을_켜지_않는다():
    assert "R07" not in ran(BusinessType.COUPON)
    assert "R03" not in ran(BusinessType.COUPON, target="방한 관광객")


def test_외국인_관광_유형은_금액_비중을_확인한다():
    assert "R07" in ran(BusinessType.FOREIGN_TOURISM)


def test_축제_유형도_금액_비중과_대상을_확인한다():
    picked = ran(BusinessType.FESTIVAL, target="방한 관광객")
    assert "R07" in picked and "R03" in picked and "R11" in picked


def test_유형과_상관없이_기간과_운영_조건과_지표는_확인한다():
    for business_type in BusinessType:
        picked = ran(business_type)
        assert {"R04", "R05", "R10"} <= picked, business_type


def test_켜지_않은_질문은_유형이_달라_확인하지_않음으로_남는다():
    plan = replace(sample_plan(), business_type=BusinessType.COUPON)
    result = run_review(plan, DEMO)
    titles = {item.title for item in result.not_applicable}
    assert "금액·비중과 성과지표 확인" in titles
    # 조용히 사라지지 않는다 — 사유도 함께 남는다
    assert all(item.reason for item in result.not_applicable)


def test_물을_것이_없음과_유형이_달라_확인하지_않음은_다르다():
    result = run_review(replace(sample_plan(), business_type=BusinessType.COUPON), DEMO)
    no_finding = {item.rule_id for item in result.no_finding}
    not_applicable = {item.rule_id for item in result.not_applicable}
    assert not (no_finding & not_applicable)


# ---------------------------------------------------------------- 화면


@pytest.mark.parametrize("business_type", [t.value for t in BusinessType])
def test_어떤_유형이든_3단계가_열린다(business_type):
    c = TestClient(app)
    c.post("/step/1", data={**VALID_FORM, "business_type": business_type})
    response = c.get("/step/3")
    assert response.status_code == 200
    # 규칙 관리 번호는 화면에 쓰지 않는다. 근거 칩의 자료 이름(DEMO-R07-…)은 데이터 담당이 붙인 것이라 예외다
    text = text_of(response.text)
    assert "R01" not in text and "R03" not in text and "R10" not in text
