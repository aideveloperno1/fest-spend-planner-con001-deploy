"""지역(시도) 근거 선택과 표시 (데이터시나리오코드.md 5장·6장, 시나리오 19~24·26~30).

원칙: 지역 자료가 있으면 쓰되 **쓸 수 있을 때만** 쓰고, 되돌렸으면 되돌렸다고 밝힌다 (워크플로우 8-4).
지역 레코드가 없는 파일은 지역 확장 전과 결과가 같아야 한다.
"""

import re
from dataclasses import replace

from evidence_helpers import fixture_path

from policy_signal_map.evidence.loader import load_evidence
from policy_signal_map.plan.models import BusinessType, PlanInput, Region, RegionLevel, sample_plan
from policy_signal_map.review.engine import run_review
from policy_signal_map.web.evidence_view import build_evidence_view

SEOUL = "1100000000"
SEOUL_JONGNO = "1111000000"
GANGWON = "5100000000"
BUSAN = "2600000000"


def plan_in(region: Region | None, **changes) -> PlanInput:
    base = sample_plan()
    base.region = region
    for key, value in changes.items():
        setattr(base, key, value)
    return base


def view(fixture: str, region: Region | None, **changes):
    return build_evidence_view(plan_in(region, **changes), load_evidence(fixture_path(fixture)))


def r07(fixture: str, region: Region | None):
    result = run_review(plan_in(region), load_evidence(fixture_path(fixture)))
    return next((o for o in result.outcomes if o.rule_id == "R07"), None)


# ---------------------------------------------------------------- 1~2. 지역 자료를 쓴다


def test_sido_plan_uses_that_sido_record():
    """시나리오 19: 시도를 고르면 그 시도 레코드의 수치가 나온다."""
    v = view("sido_allowed", Region(RegionLevel.SIDO, sido_code=SEOUL))
    assert v.main.evidence_id == "FX-SIDO-SEOUL"
    assert v.main_scope_label == "서울특별시 범위 참고 — 선택 지역의 진단이 아님"
    assert v.show_numbers and v.show_summary
    assert v.summary_sentence.startswith("2026년 1~6월 서울특별시 자료에서")
    # 같은 레코드를 3단계 검토도 쓴다
    assert r07("sido_allowed", Region(RegionLevel.SIDO, sido_code=SEOUL)).evidence_ids == ("FX-SIDO-SEOUL",)


def test_sigungu_plan_uses_its_sido_record_with_wider_scope_note():
    """시나리오 20 (C-2): 시군구를 고르면 그 시도 자료를 쓰되 '넓은 범위'라고 밝힌다."""
    region = Region(RegionLevel.SIGUNGU, sido_code=SEOUL, sigungu_code=SEOUL_JONGNO)
    v = view("sido_allowed", region)
    assert v.main.evidence_id == "FX-SIDO-SEOUL"
    assert v.region_note == (
        "넓은 범위의 참고자료입니다. 선택한 서울특별시 종로구의 소비를 진단한 결과가 아닙니다."
    )


# ---------------------------------------------------------------- 3~4. 되돌리고 밝힌다


def test_missing_region_falls_back_to_national_and_says_so():
    """시나리오 21 (C-3): 그 지역 레코드가 없으면 전국으로 되돌리고 되돌렸다고 밝힌다."""
    v = view("sido_allowed", Region(RegionLevel.SIDO, sido_code=BUSAN))
    assert v.main.evidence_id == "FX-01"
    assert v.main_scope_label == "전국 참고 — 특정 지역의 진단이 아님"
    assert v.region_note == (
        "선택한 부산광역시의 근거 자료가 없어 전국 참고 자료를 보여 줍니다. "
        "선택한 지역의 소비를 진단한 결과가 아닙니다."
    )


def test_blocked_region_falls_back_with_reason():
    """시나리오 22·26 (C-4): 사용 불가 지역은 수치를 쓰지 않고 사유와 함께 되돌린다."""
    region = Region(RegionLevel.SIDO, sido_code=SEOUL)
    v = view("sido_blocked", region)
    assert v.main.evidence_id == "FX-01"
    assert "사유: 지역 기준 미확인으로 사용 불가" in v.region_note
    assert v.region_note.startswith("선택한 서울특별시의 자료는 사용할 수 없어")
    # 사용 불가 지역의 수치는 화면 어디에도 없다
    assert all(rv.evidence_id != "FX-SIDO-SEOUL-BLOCKED" for rv in v.hold_examples)
    assert r07("sido_blocked", region).evidence_ids == ("FX-01",)


def test_needs_review_region_hides_summary_but_keeps_numbers():
    """시나리오 27: 검토 필요 지역은 요약 문장을 감추고, 지역 안내와 함께 나와도 화면이 엉키지 않는다."""
    v = view("sido_blocked", Region(RegionLevel.SIDO, sido_code=GANGWON))
    assert v.main.evidence_id == "FX-SIDO-GANGWON-REVIEW"
    assert v.status_kind == "needs_review"
    assert v.show_numbers and not v.show_summary and v.summary_sentence is None
    assert v.held_message == "근거 기반 결론을 보류합니다. 확인할 내용: 표본 대표성 확인 중"
    assert v.main_scope_label == "강원특별자치도 범위 참고 — 선택 지역의 진단이 아님"


# ---------------------------------------------------------------- 5~6. 표본·기간


def test_sparse_region_hides_numbers_and_lists_held_months():
    """시나리오 23·28: 표본이 부족한 지역은 차트·요약 없이 계산하지 못한 달만 보여 준다."""
    v = view("sido_sparse", Region(RegionLevel.SIDO, sido_code=GANGWON))
    assert v.main.evidence_id == "FX-SIDO-GANGWON-SPARSE"
    assert not v.show_numbers and not v.show_summary and v.chart_data == {}
    assert v.show_held_months
    assert "6개월 중 계산 가능한 달이 3개월로 기준 4개월에 못 미침" in v.held_message
    assert [m.label for m in v.main.months if m.held] == ["2월", "3월", "5월"]


def test_plan_period_after_data_period_gets_one_line():
    """시나리오 24·30: 사업 기간이 자료 기간보다 뒤면 한 줄로 알린다 (자료를 막지는 않는다)."""
    v = view("sido_allowed", Region(RegionLevel.SIDO, sido_code=SEOUL))  # 예시 기획은 2026-10~12
    assert v.period_note == "이 자료는 사업 기간 이전의 흐름입니다. (자료 2026년 1~6월 / 사업 2026년 10~12월)"
    assert v.show_numbers  # 안내만 하고 수치는 그대로 보여 준다

    overlap = view("sido_allowed", Region(RegionLevel.SIDO, sido_code=SEOUL),
                   period_start="2026-03-01", period_end="2026-08-31")
    assert overlap.period_note is None


# ---------------------------------------------------------------- 7~8. 지켜야 할 선과 회귀


def test_industry_rule_holds_without_region_profile():
    """사용처 업종 확인은 고른 지역의 업종 자료가 있어야 한다. 없으면 넓히지 않고 보류한다."""
    plan = plan_in(Region(RegionLevel.SIDO, sido_code=SEOUL))
    plan.usage_industries = ["IND01"]
    # 사용처 업종은 쿠폰·연령·축제 유형에서 켜진다 (review/packs.py)
    plan.business_type = BusinessType.COUPON
    # 이 사례 파일은 2.0이라 지역 프로필이 없다
    result = run_review(plan, load_evidence(fixture_path("sido_allowed")))
    item = next(o for o in result.outcomes if o.rule_id == "R02")
    assert item.kind == "held"
    assert "연결되지 않았습니다" in item.message or "자료가" in item.message


def test_national_only_file_is_unchanged_by_region_selection():
    """회귀 방지: 지역 레코드가 없는 파일은 지역을 골라도 결과가 하나도 바뀌지 않는다."""
    national = Region(RegionLevel.NATIONAL)
    sigungu = Region(RegionLevel.SIGUNGU, sido_code=GANGWON, sigungu_code="5115000000")

    base = view("amount_up_share_down", national)
    picked = view("amount_up_share_down", sigungu)

    # 고른 지역을 적는 두 칸(안내 문장·고른 지역 이름)만 다르고 나머지는 같다
    def without_region_text(view):
        return replace(view, region_note=None, plan_region_label=None)

    assert without_region_text(base) == without_region_text(picked)
    assert base.plan_region_label == "전국"
    assert picked.plan_region_label == "강원특별자치도 강릉시"
    assert base.region_note is None
    assert picked.region_note == (
        "전국 참고 자료입니다. 선택한 강원특별자치도 강릉시의 소비를 진단한 결과가 아닙니다."
    )
    assert picked.main.evidence_id == "FX-01"


# ---------------------------------------------------------------- 시군구 사다리 (시연 파일)

from policy_signal_map.config import (  # noqa: E402
    LEGACY_DEMO_EVIDENCE_PATH as DEFAULT_EVIDENCE_PATH,
)

CHUNCHEON = "5111000000"
TAEBAEK = "5119000000"   # 시연 파일에 일부러 레코드를 두지 않은 곳
GANGNEUNG = "5115000000"
JONGNO = "1111000000"
JEJUSI = "5011000000"


def demo_view(sido_code: str, sigungu_code: str):
    region = Region(RegionLevel.SIGUNGU, sido_code=sido_code, sigungu_code=sigungu_code)
    return build_evidence_view(plan_in(region), load_evidence(DEFAULT_EVIDENCE_PATH))


def test_sigungu_record_is_used_when_available():
    """가장 좁은 범위부터 쓴다: 춘천시 자료가 있으면 춘천시 자료를 쓴다."""
    v = demo_view(GANGWON, CHUNCHEON)
    assert v.main.evidence_id == "DEMO-R07-SIGUNGU-강원-춘천시"
    assert v.main_scope_label == "강원특별자치도 춘천시 범위 참고 — 선택 지역의 진단이 아님"
    assert v.region_note is None  # 고른 지역 그대로라 넓혔다는 안내가 없다
    assert v.summary_sentence.startswith("2026년 1~6월 강원특별자치도 춘천시 자료에서")


def test_missing_sigungu_widens_to_its_sido_and_says_so():
    """시연 파일에 레코드를 두지 않은 태백시는 강원 자료로 한 칸 넓히고, 넓힌 사실을 밝힌다."""
    v = demo_view(GANGWON, TAEBAEK)
    assert v.main.evidence_id == "DEMO-R07-SIDO-GANGWON"
    assert v.region_note == (
        "선택한 강원특별자치도 태백시의 근거 자료가 없어 강원특별자치도 자료를 보여 줍니다. "
        "넓은 범위의 참고자료이며 선택한 지역의 소비를 진단한 결과가 아닙니다."
    )


def test_sparse_sigungu_widens_to_its_sido():
    """시군구 표본이 부족하면 같은 지역의 더 넓은 범위를 쓴다 (수치를 접는 대신)."""
    v = demo_view(SEOUL, JONGNO)
    assert v.main.evidence_id == "DEMO-R07-SIDO-SEOUL"
    assert v.show_numbers and not v.show_held_months
    assert v.region_note.startswith("선택한 서울특별시 종로구의 자료는 표본이 부족해(")
    assert "계산 가능한 달이 3개월" in v.region_note


def test_blocked_sigungu_widens_with_reason():
    """시군구 자료가 사용 불가면 수치를 쓰지 않고 시도로 넓히며 사유를 밝힌다."""
    v = demo_view("5000000000", JEJUSI)
    assert v.main.evidence_id == "DEMO-R07-SIDO-JEJU"
    assert v.region_note.startswith("선택한 제주특별자치도 제주시의 자료는 사용할 수 없어(사유: ")
    assert all(rv.evidence_id != "DEMO-R07-SIGUNGU-제주-제주시" for rv in v.hold_examples)


def test_administrative_codes_never_appear_in_region_text():
    """화면 글자에는 행정표준코드가 나오지 않는다 (이름으로만 표시)."""
    for sido_code, sigungu_code in ((GANGWON, CHUNCHEON), (GANGWON, GANGNEUNG), (SEOUL, JONGNO)):
        v = demo_view(sido_code, sigungu_code)
        text = " ".join(filter(None, [v.main_scope_label, v.region_note, v.summary_sentence, v.held_message]))
        assert not re.search(r"\d{10}", text), text


def test_selected_region_is_named_on_screen():
    """자료가 없어 시도 자료를 쓰게 되어도, 무엇을 골랐는지 화면에 적는다."""
    taebaek = demo_view(GANGWON, TAEBAEK)
    assert taebaek.main.evidence_id == "DEMO-R07-SIDO-GANGWON"
    assert taebaek.plan_region_label == "강원특별자치도 태백시"
    assert "태백시" in taebaek.region_note

    # 같은 시도 안이어도 자기 자료가 있는 시군구는 다른 근거를 쓴다
    gangneung = demo_view(GANGWON, GANGNEUNG)
    assert gangneung.main.evidence_id == "DEMO-R07-SIGUNGU-강원-강릉시"
    assert gangneung.plan_region_label == "강원특별자치도 강릉시"


def test_demo_covers_every_sigungu_in_the_region_list():
    """시연 자료는 입력 화면의 시군구를 모두 덮는다 (사다리 시연용 한 곳만 일부러 비움)."""
    from policy_signal_map.plan.regions import sido_list

    file = load_evidence(DEFAULT_EVIDENCE_PATH).file
    have = {r.scope.region_key for r in file.records if r.scope.geographic_scope == "sigungu"}
    # 공개 전달본의 DEMO-* 가상 지역은 별도 공개 파일이 담당한다. 기본 합성본은 실제 행정코드만 본다.
    want = {gu["code"] for sido in sido_list() for gu in sido["sigungu"] if gu["code"].isdigit()}
    assert want - have == {TAEBAEK}


def test_evidence_ids_never_contain_administrative_codes():
    """근거 이름은 화면에 그대로 보인다. 10자리 행정표준코드를 쓰지 않는다."""
    file = load_evidence(DEFAULT_EVIDENCE_PATH).file
    assert [r.evidence_id for r in file.records if re.search(r"\d{10}", r.evidence_id)] == []
