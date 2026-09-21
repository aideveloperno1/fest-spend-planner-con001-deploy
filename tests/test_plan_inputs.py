"""1단계에 더한 입력: 사업 유형, 성과지표 선택지, 목표 방문객 수 (7지역확장계획.md 5-1장).

이 파일은 값을 제대로 받아 두고 빈칸과 0을 구분하는 입력 계약을 고정한다. 목표 방문객 수를 쓰는
규모와 수용 여건 질문(R11)의 조건은 `test_capacity_checks.py`에서 확인한다.
"""

from dataclasses import replace

from fastapi.testclient import TestClient
from helpers import VALID_FORM, parse

from policy_signal_map.app import app
from policy_signal_map.labels import BUSINESS_TYPE_LABELS, METRIC_GROUPS, METRIC_LABELS
from policy_signal_map.plan.changes import diff_plan
from policy_signal_map.plan.models import (
    CARD_DERIVABLE_METRICS,
    NON_CARD_METRICS,
    BusinessType,
    Metric,
    sample_plan,
)
from policy_signal_map.plan.validation import validate_plan


def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------- 사업 유형


def test_사업_유형을_고르지_않으면_묻는다():
    assert "business_type" in validate_plan(parse({})).errors


def test_고르지_않은_기획을_한_유형으로_분류하지_않는다():
    assert parse({}).business_type is None


def test_목록에_없는_유형은_버린다():
    assert parse({"business_type": "없는유형"}).business_type is None


def test_고른_유형을_그대로_읽는다():
    assert parse({"business_type": "festival"}).business_type is BusinessType.FESTIVAL


def test_유형이_바뀌면_재확인_대상이_된다():
    before = sample_plan()
    after = replace(before, business_type=BusinessType.FESTIVAL)
    assert diff_plan(before, after) == {"business_type"}


def test_유형마다_한글_이름과_설명이_있다():
    for key in BusinessType:
        assert BUSINESS_TYPE_LABELS[key]


# ---------------------------------------------------------------- 성과지표 선택지


def test_카드로_잴_수_없는_지표를_고를_수_있다():
    plan = parse({**VALID_FORM, "metrics": ["visitors"]})
    assert plan.metrics == [Metric.VISITORS]


def test_잴_수_있는_지표와_없는_지표가_겹치지_않는다():
    assert not (CARD_DERIVABLE_METRICS & NON_CARD_METRICS)


def test_모든_지표에_한글_이름이_있다():
    for key in Metric:
        assert METRIC_LABELS[key]


def test_지표_묶음이_모든_지표를_한_번씩_담는다():
    listed = [metric for _, metrics in METRIC_GROUPS for metric in metrics]
    assert sorted(listed, key=lambda m: m.value) == sorted(Metric, key=lambda m: m.value)


# ---------------------------------------------------------------- 목표 방문객 수


def test_적지_않은_것과_0명을_구분한다():
    assert parse({}).visitor_goal is None
    zero = parse({"visitor_goal": "0"})
    assert zero.visitor_goal == 0


def test_쉼표가_섞인_숫자를_읽는다():
    assert parse({"visitor_goal": "30,000"}).visitor_goal == 30_000


def test_숫자로_읽지_못하면_원문을_남기고_묻는다():
    plan = parse({**VALID_FORM, "visitor_goal": "3만 명"})
    assert plan.visitor_goal is None
    assert plan.visitor_goal_raw == "3만 명"
    assert "visitor_goal" in validate_plan(plan).errors


def test_빈칸은_오류가_아니다():
    assert "visitor_goal" not in validate_plan(parse(VALID_FORM)).errors


def test_축제에서_적지_않으면_추가_확정_필요로_남는다():
    plan = parse({**VALID_FORM, "business_type": "festival"})
    assert "목표 방문객 수 (미입력)" in validate_plan(plan).pending


def test_다른_유형에서는_빠진_항목으로_보지_않는다():
    plan = parse({**VALID_FORM, "business_type": "coupon"})
    assert not [item for item in validate_plan(plan).pending if "방문객" in item]


def test_축제라도_0명이라고_적었으면_빠진_항목이_아니다():
    plan = parse({**VALID_FORM, "business_type": "festival", "visitor_goal": "0"})
    assert not [item for item in validate_plan(plan).pending if "방문객" in item]


def test_방문객_목표가_바뀌면_재확인_대상이_된다():
    before = sample_plan()
    after = replace(before, visitor_goal=0, visitor_goal_raw="0")
    assert diff_plan(before, after) == {"visitor_goal"}


def test_쿠폰_유형에서만_사용처가_추가_확정_필요로_남는다():
    coupon = validate_plan(parse({**VALID_FORM, "business_type": "coupon"}))
    tourism = validate_plan(parse({**VALID_FORM, "business_type": "foreign_tourism"}))
    assert "쿠폰 사용처" in coupon.pending
    assert "쿠폰 사용처" not in tourism.pending


# ---------------------------------------------------------------- 화면


def test_입력_화면에_새_칸이_보인다():
    text = client().get("/step/1").text
    assert "사업 유형" in text and "축제·행사" in text
    assert "목표 방문객 수" in text
    assert "카드 자료에 없어 별도 자료가 필요한 지표" in text and "방문객 수" in text


def test_방문객_수가_사용처보다_먼저_나오고_사용처는_쿠폰_유형에만_보인다():
    c = client()
    empty = c.get("/step/1").text
    assert empty.index("목표 방문객 수") < empty.index("쿠폰 사용처")
    assert 'data-business-field="coupon" hidden' in empty
    assert 'name="usage_place"' in empty and " disabled" in empty

    coupon = c.post("/step/1", data={**VALID_FORM, "business_type": "coupon", "target": ""})
    assert 'data-business-field="coupon" hidden' not in coupon.text


def test_입력_화면은_단일_컬럼과_하단_고정_상태_바를_쓴다():
    text = client().get("/step/1").text
    assert 'class="plan-input-layout"' in text
    assert 'class="plan-sticky-bar"' in text
    assert 'data-summary="progress-track"' in text
    assert 'form="plan-form"' in text and "검토 시작 →" in text
    assert "검토 예정 규칙" not in text
    assert '<aside class="side">' not in text


def test_예시_기획의_고정_바는_완료_8개와_확정_필요_2건을_보인다():
    c = client()
    response = c.post("/step/1", data={"action": "sample"}, follow_redirects=True)
    text = response.text
    assert 'data-summary="required-completed" class="text-ok">8</strong>/8' in text
    assert 'data-summary="pending-count">2</strong>건' in text
    assert 'data-summary="pending-names">예산, 자료 확보</span>' in text


def test_예시_기획에도_사업_유형이_들어_있다():
    assert sample_plan().business_type is not None
    assert validate_plan(sample_plan()).ok


# ---------------------------------------------------------------- 사용처 업종·대상 연령


def catalog():
    from policy_signal_map.config import (
        LEGACY_DEMO_EVIDENCE_PATH as DEFAULT_EVIDENCE_PATH,
    )
    from policy_signal_map.evidence.loader import load_evidence
    from policy_signal_map.web.profile_view import option_catalog

    return option_catalog(load_evidence(DEFAULT_EVIDENCE_PATH))


def parse_with_catalog(form: dict):
    from policy_signal_map.web.forms import parse_plan_form

    c = catalog()
    single = {k: v for k, v in form.items() if isinstance(v, str)}
    multi = {k: v for k, v in form.items() if isinstance(v, list)}
    return parse_plan_form(single, multi, industry_codes=c.industry_codes(), age_codes=c.age_codes())


def test_고를_수_있는_목록은_근거_파일이_알려_준다():
    c = catalog()
    assert c.ready is True
    assert len(c.industries) == 11 and len(c.ages) == 6
    assert c.label_of(c.industries[0].code) == c.industries[0].label


def test_자료에_없는_업종_코드는_버린다():
    plan = parse_with_catalog({**VALID_FORM, "usage_industries": ["IND01", "없는코드"]})
    assert plan.usage_industries == ["IND01"]


def test_고른_순서를_지키고_중복은_없앤다():
    plan = parse_with_catalog({**VALID_FORM, "usage_industries": ["IND03", "IND01", "IND03"]})
    assert plan.usage_industries == ["IND03", "IND01"]


def test_대상_연령도_같은_방식으로_받는다():
    plan = parse_with_catalog({**VALID_FORM, "target_ages": ["AGE2", "AGE9"]})
    assert plan.target_ages == ["AGE2"]


def test_아무것도_고르지_않아도_된다():
    plan = parse_with_catalog(VALID_FORM)
    assert plan.usage_industries == [] and plan.target_ages == []
    assert validate_plan(plan).ok


def test_업종이나_연령이_바뀌면_재확인_대상이_된다():
    before = sample_plan()
    assert diff_plan(before, replace(before, usage_industries=["IND01"])) == {"usage_industries"}
    assert diff_plan(before, replace(before, target_ages=["AGE2"])) == {"target_ages"}


def test_입력_화면에_업종과_연령_칸이_보인다():
    text = client().get("/step/1").text
    assert 'name="usage_industries"' in text and 'name="target_ages"' in text
    assert "시연 업종 A" in text and "60대 이상" in text


def test_근거_파일에_프로필이_없으면_입력칸을_두지_않는다(use_evidence):
    """옛 형식(2.0) 파일을 쓰면 고를 목록이 없다. 서비스가 목록을 지어내지 않는다."""
    from evidence_helpers import fixture_path

    use_evidence(fixture_path("amount_up_share_down"))
    text = client().get("/step/1").text
    assert 'name="usage_industries"' not in text and 'name="target_ages"' not in text
    assert "시연 업종 A" not in text
