"""성과지표와 자료 범위 확인 R10 (docs/review_rules.md, 7지역확장계획.md 6장).

카드 자료에는 결제금액과 거래건수가 있고 사람 수는 없다. 담당자가 사람 수 지표를 골랐으면
그 사실을 알리고 어떤 자료로 확인할지 묻는다. 판정하지 않는다.
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
from policy_signal_map.plan.models import Metric, sample_plan
from policy_signal_map.review.engine import RUN_ORDER, run_review
from policy_signal_map.review.metric_checks import unsupported_metrics
from policy_signal_map.review.rules import get_rule


def review(metrics: list[Metric]):
    plan = replace(sample_plan(), metrics=metrics)
    return run_review(plan, load_evidence(DEFAULT_EVIDENCE_PATH))


def outcome_of(result, rule_id: str):
    return next((o for o in result.outcomes if o.rule_id == rule_id), None)


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


# ---------------------------------------------------------------- 실행 조건


def test_사람_수_지표를_고르면_묻는다():
    outcome = outcome_of(review([Metric.VISITORS]), "R10")
    assert outcome is not None and outcome.kind == "question"
    assert "방문객 수" in outcome.message


def test_고른_사람_수_지표를_모두_적는다():
    outcome = outcome_of(review([Metric.VISITORS, Metric.PARTICIPANTS]), "R10")
    assert "방문객 수" in outcome.message and "참여자 수" in outcome.message


def test_카드로_잴_수_있는_지표만_고르면_묻지_않는다():
    result = review([Metric.PAYMENT_AMOUNT])
    assert outcome_of(result, "R10") is None
    # "확인했으나 해당 없음"으로 남는다 ("검토하지 않음"과 다르다)
    assert "R10" in {item.rule_id for item in result.no_finding}


def test_고른_순서를_지킨다():
    plan = replace(sample_plan(), metrics=[Metric.CUSTOMERS, Metric.VISITORS])
    assert unsupported_metrics(plan) == ("고객 수", "방문객 수")


def test_결제건수는_사람_수가_아니지만_카드로_산출된다():
    assert outcome_of(review([Metric.PAYMENT_COUNT]), "R10") is None


# ---------------------------------------------------------------- 규칙 정의


def test_실행_순서에_들어_있다():
    assert "R10" in RUN_ORDER


def test_대안_둘과_문서_문장이_있다():
    rule = get_rule("R10")
    assert [o.id for o in rule.options] == ["A", "B"]
    for option in rule.options:
        assert option.document is not None and option.document.section == 7


def test_별도_자료_대안은_수집_계획을_받는다():
    option = get_rule("R10").option("A")
    assert "collect_items" in option.execution_fields
    assert "owner" in option.execution_fields and "cycle" in option.execution_fields


def test_쿠폰_정산_실적과_다른_묶음이다():
    """사람 수 실적과 쿠폰 정산 실적은 다른 자료다. 입력을 함께 쓰지 않는다."""
    assert get_rule("R10").merge_group == "performance_data"
    assert get_rule("R07").merge_group == "participation_data"


def test_재확인은_성과지표가_바뀔_때만():
    assert get_rule("R10").related_fields == ("metrics",)


# ---------------------------------------------------------------- 화면


def test_3단계에_질문이_보이고_규칙_번호는_보이지_않는다():
    c = TestClient(app)
    c.post("/step/1", data={**VALID_FORM, "metrics": ["visitors"]})
    text = text_of(c.get("/step/3").text)
    assert "성과지표와 자료 범위 확인" in text
    assert "카드 자료로 산출되지 않는" in text
    assert "R10" not in text


def test_전국_기획에서도_동작한다():
    """자료의 성격만 보는 규칙이라 지역 자료가 없어도 질문할 수 있다."""
    c = TestClient(app)
    c.post("/step/1", data={**VALID_FORM, "region_level": "national", "metrics": ["participants"]})
    assert "참여자 수" in text_of(c.get("/step/3").text)
