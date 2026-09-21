"""2단계 지역 소비 프로필 카드 (7지역확장계획.md 3장).

가장 중요한 약속: **고른 지역의 자료만 쓴다.** 금액·비중 비교는 자료가 없으면 한 칸 넓히지만
프로필은 넓히지 않는다. 다른 지역 구성을 그 지역 것처럼 보여 주게 되기 때문이다.
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
from policy_signal_map.plan.models import PlanInput, Region, RegionLevel, sample_plan
from policy_signal_map.web.profile_view import build_profile_view, region_key_for

GANGNEUNG = "5115000000"  # 예시 기획이 고르는 지역
CHUNCHEON = "5111000000"  # 일부러 "자료 부족"으로 둔 지역
TAEBAEK = "5119000000"  # 근거 파일에 레코드가 없는 지역
GANGWON = "5100000000"


def demo():
    return load_evidence(DEFAULT_EVIDENCE_PATH)


def plan_for(level: RegionLevel, sido: str = "", sigungu: str = "") -> PlanInput:
    return replace(sample_plan(), region=Region(level, sido_code=sido, sigungu_code=sigungu))


def view_for(level: RegionLevel, sido: str = "", sigungu: str = ""):
    return build_profile_view(plan_for(level, sido, sigungu), demo())


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


# ---------------------------------------------------------------- 어느 지역 자료를 쓰나


def test_고른_지역의_키를_그대로_쓴다():
    assert region_key_for(plan_for(RegionLevel.NATIONAL)) == "ALL"
    assert region_key_for(plan_for(RegionLevel.SIDO, GANGWON)) == GANGWON
    assert region_key_for(plan_for(RegionLevel.SIGUNGU, GANGWON, GANGNEUNG)) == GANGNEUNG


def test_시군구를_고르면_그_시군구_프로필이_나온다():
    view = view_for(RegionLevel.SIGUNGU, GANGWON, GANGNEUNG)
    assert view.available is True
    assert view.industry.rows and view.age.rows


def test_자료가_없는_지역은_넓히지_않고_없다고_적는다():
    view = view_for(RegionLevel.SIGUNGU, GANGWON, TAEBAEK)
    assert view.available is False
    assert "연결되지 않았습니다" in view.note


def test_자료가_부족한_지역은_이유를_적고_수치를_보여_주지_않는다():
    view = view_for(RegionLevel.SIGUNGU, GANGWON, CHUNCHEON)
    assert view.available is False
    assert "자료가 부족" in view.note
    assert view.industry is None


def test_전국을_고르면_전국_프로필():
    assert view_for(RegionLevel.NATIONAL).available is True


def test_시도를_고르면_시도_프로필():
    assert view_for(RegionLevel.SIDO, GANGWON).available is True


# ---------------------------------------------------------------- 무엇을 보여 주나


def test_기간과_지역_구분_기준을_함께_적는다():
    view = view_for(RegionLevel.SIGUNGU, GANGWON, GANGNEUNG)
    assert view.period
    # 주최 측 확인 전이라 가맹점 자리 기준이라고 단정하지 않는다
    assert "확인 중" in view.basis_note


def test_연령_구성의_분모를_밝힌다():
    view = view_for(RegionLevel.SIGUNGU, GANGWON, GANGNEUNG)
    assert "알 수 없는 결제" in view.age_denominator_note


def test_순위에_몇_곳_중인지_함께_담는다():
    view = view_for(RegionLevel.SIGUNGU, GANGWON, GANGNEUNG)
    assert view.ranks
    for rank in view.ranks:
        assert rank.regions > 0


def test_아직_만들지_않은_유사_지역은_보여_주지_않는다():
    """시연 파일의 유사 지역은 미연결이다. 없는 것을 있는 것처럼 두지 않는다."""
    profile = demo().profile(GANGNEUNG)
    assert profile.ready("peers") is False


def test_모르는_순위_칸_이름은_화면에_내보내지_않는다():
    result = demo()
    profile = result.profile(GANGNEUNG)
    labels = {rank.label for rank in build_profile_view(plan_for(RegionLevel.SIGUNGU, GANGWON, GANGNEUNG), result).ranks}
    assert "없는칸" not in labels
    assert labels <= {"외국인 결제 비중", "결제금액 규모", "결제건수"}
    assert profile.ranks  # 원본에는 값이 있다


# ---------------------------------------------------------------- 화면


def test_2단계_화면에_프로필_카드가_보인다():
    c = TestClient(app)
    c.post("/step/1", data=VALID_FORM)
    text = text_of(c.get("/step/2").text)
    assert "지역 소비 프로필" in text
    assert "업종 구성" in text and "연령 구성" in text
    assert "월별 소비 흐름" in text
    # 규칙 관리 번호는 화면에 쓰지 않는다 (사용자 결정 2026-09-18)
    assert "R07" not in text and "R02" not in text


def test_자료가_없는_지역을_골라도_화면은_열린다():
    c = TestClient(app)
    c.post("/step/1", data={**VALID_FORM, "sigungu": TAEBAEK})
    response = c.get("/step/2")
    assert response.status_code == 200
    text = text_of(response.text)
    assert "연결되지 않았습니다" in text
    assert "다른 지역 자료로 대신 보여 주지 않습니다" in text
