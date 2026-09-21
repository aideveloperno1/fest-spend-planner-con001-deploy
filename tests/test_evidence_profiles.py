"""근거 파일 2.1의 지역 프로필 읽기 (7지역확장계획.md 3장).

핵심 두 가지를 고정한다.
① 2.0 파일은 지금까지와 똑같이 동작하고 프로필만 비어 있다.
② 프로필이 고장 나도 **그 지역만** 빠지고 파일 전체가 거부되지 않는다. 다만 2.0에 프로필을
   넣은 경우는 조용히 무시하면 안 되므로 거부한다.
"""

import copy
from pathlib import Path

import pytest
from evidence_helpers import fixture_path

from policy_signal_map.evidence.loader import EvidenceError, load_evidence
from policy_signal_map.evidence.profile_schema import parse_profiles
from policy_signal_map.paths import RESOURCES_DIR

DEMO = RESOURCES_DIR / "evidence" / "review_evidence_demo_v1.json"
SEOUL = "1100000000"


def profile(**changes) -> dict:
    base = {
        "region_key": "ALL",
        "geographic_scope": "national",
        "region_basis": "unconfirmed",
        "period_start": "2026-01",
        "period_end": "2026-06",
        "industry": [
            {"code": "IND01", "label": "가상업종 가", "amount": 600, "share_pct": 60.0, "status": "ok"},
            {"code": "IND02", "label": "가상업종 나", "amount": 400, "share_pct": 40.0, "status": "ok"},
        ],
        "age": [{"code": "AGE1", "label": "가상연령", "amount": 1000, "share_pct": 100.0, "status": "ok"}],
        "months": [{"month": "2026-01", "status": "ok", "season_index": 1.0}],
        "foreign_share_pct": 4.0,
        "unknown_share_pct": 2.0,
        "ranks": {"foreign_share": {"percentile": 40.0, "regions": 12}},
        "readiness": {"profile": "ok", "industry": "ok", "peers": "unlinked"},
        "limitations": [],
    }
    base.update(changes)
    return base


def parsed(*profiles, thresholds: dict | None = None):
    data = {"profiles": [copy.deepcopy(p) for p in profiles]}
    if thresholds is not None:
        data["thresholds"] = thresholds
    return parse_profiles(data)


# ---------------------------------------------------------------- 2.0 그대로


def test_이_전_형식_파일은_그대로_읽히고_프로필만_비어_있다():
    """2.0 파일을 넣으면 지금까지와 똑같이 동작하고 지역 화면만 '자료 없음'이 된다."""
    result = load_evidence(fixture_path("amount_up_share_down"))
    assert result.file.schema_version == "2.0"
    assert result.file.records
    assert result.profiles == ()
    assert result.thresholds is None


def test_시연용_합성_파일은_2_1이고_프로필을_함께_읽는다():
    result = load_evidence(DEMO)
    assert result.file.schema_version == "2.1"
    assert result.warnings == ()
    assert len(result.profiles) > 1
    assert result.thresholds is not None


def test_이_전_형식에_프로필을_넣으면_조용히_무시하지_않고_거부한다():
    with pytest.raises(EvidenceError) as caught:
        load_evidence(fixture_path("profiles_version_mismatch"))
    message = caught.value.messages[0]
    assert "2.0" in message and "2.1" in message


# ---------------------------------------------------------------- 2.1 정상


def test_정상_파일은_프로필과_운영_기준을_함께_읽는다():
    result = load_evidence(fixture_path("profiles_ok"))
    assert len(result.profiles) == 2
    assert result.thresholds is not None
    assert result.thresholds.get("R04", "season_index") == 1.10


def test_업종별_연령_구성을_분모와_순위까지_읽는다():
    result = parsed(
        profile(
            industry_age=[
                {
                    "industry_code": "IND01",
                    "age_denominator": "known_only",
                    "ages": [
                        {
                            "code": "AGE1",
                            "label": "가상연령",
                            "amount": 100,
                            "share_pct": 100.0,
                            "status": "ok",
                            "percentile": 15.0,
                            "regions": 12,
                        }
                    ],
                }
            ],
            readiness={"profile": "ok", "industry_age": "ok"},
        )
    )
    group = result.profiles[0].industry_age[0]
    assert group.industry_code == "IND01"
    assert group.age_denominator == "known_only"
    assert group.ages[0].has_rank is True


def test_외부_인구는_관측일과_출처를_함께_읽는다():
    result = parsed(
        profile(
            external={
                "population": {
                    "status": "ok",
                    "count": 1000,
                    "observed_at": "2026-06-30",
                    "source_name": "시연용 합성 인구",
                },
                "registered_foreigners": {
                    "status": "ok",
                    "count": 0,
                    "observed_at": "2026-06-30",
                    "source_name": "시연용 합성 등록외국인",
                },
            },
            readiness={"profile": "ok", "external": "ok"},
        )
    )
    external = result.profiles[0].external
    assert external.population.count == 1000
    assert external.population.observed_at == "2026-06-30"
    assert external.registered_foreigners.count == 0


def test_그_지역의_프로필만_돌려준다():
    result = load_evidence(fixture_path("profiles_ok"))
    assert result.profile(SEOUL) is not None
    # 없는 지역을 다른 지역 값으로 대신하지 않는다
    assert result.profile("9999999999") is None


def test_운영_기준에_없는_값을_물으면_None():
    result = load_evidence(fixture_path("profiles_ok"))
    assert result.thresholds.get("R99", "없는기준") is None


# ---------------------------------------------------------------- 고장 났을 때


def test_한_지역이_고장_나도_파일은_읽히고_그_지역만_빠진다():
    result = load_evidence(fixture_path("profiles_one_broken"))
    assert len(result.file.records) == 2  # 기존 검토는 그대로 동작한다
    assert [p.region_key for p in result.profiles] == ["ALL"]
    assert any("보여 주지 않습니다" in w for w in result.warnings)


def test_순위에_몇_곳_중인지_없으면_버린다():
    result = parsed(profile(ranks={"foreign_share": {"percentile": 40.0}}))
    assert result.profiles == ()
    assert any("몇 곳 중인지" in w for w in result.warnings)


def test_같은_지역이_두_번이면_뒤의_것을_버린다():
    result = parsed(profile(), profile(foreign_share_pct=9.0))
    assert len(result.profiles) == 1
    assert result.profiles[0].foreign_share_pct == 4.0
    assert any("두 번" in w for w in result.warnings)


def test_비중이_0에서_100_밖이면_버린다():
    assert parsed(profile(foreign_share_pct=140.0)).profiles == ()


def test_자료_없음인데_값이_들어_있으면_버린다():
    broken = profile(
        industry=[{"code": "IND01", "label": "가상업종", "amount": 10, "share_pct": 10.0, "status": "no_data"}]
    )
    assert parsed(broken).profiles == ()


def test_자료_없음인데_순위가_들어_있어도_버린다():
    broken = profile(
        industry=[
            {
                "code": "IND01",
                "label": "가상업종",
                "amount": None,
                "share_pct": None,
                "status": "no_data",
                "percentile": 10.0,
                "regions": 12,
            }
        ]
    )
    assert parsed(broken).profiles == ()


def test_업종별_연령_구성이_틀리면_그_기능만_끄고_프로필은_남긴다():
    result = parsed(
        profile(
            industry_age=[
                {
                    "industry_code": "없는업종",
                    "age_denominator": "known_only",
                    "ages": [],
                }
            ],
            readiness={"profile": "ok", "industry": "ok", "industry_age": "ok"},
        )
    )
    assert len(result.profiles) == 1
    assert result.profiles[0].industry
    assert result.profiles[0].industry_age == ()
    assert result.profiles[0].readiness["industry_age"] == "blocked"
    assert any("업종별 연령 구성은 사용하지 않습니다" in warning for warning in result.warnings)


def test_외부_인구가_틀리면_외부_기능만_끄고_프로필은_남긴다():
    result = parsed(
        profile(
            external={
                "population": {
                    "status": "ok",
                    "count": 0,
                    "observed_at": "2026-06-30",
                    "source_name": "시연용 합성 인구",
                }
            },
            readiness={"profile": "ok", "industry": "ok", "external": "ok"},
        )
    )
    assert len(result.profiles) == 1
    assert result.profiles[0].industry
    assert result.profiles[0].external is None
    assert result.profiles[0].readiness["external"] == "blocked"
    assert any("외부 자료는 사용하지 않습니다" in warning for warning in result.warnings)


def test_외부_자료_미연결_상태에는_수를_넣지_않는다():
    result = parsed(
        profile(
            external={"population": {"status": "unlinked", "count": 1000}},
            readiness={"external": "ok"},
        )
    )
    assert result.profiles[0].external is None
    assert result.profiles[0].readiness["external"] == "blocked"


def test_0원은_자료_없음이_아니다():
    zero = profile(
        industry=[
            {"code": "IND01", "label": "가상업종 가", "amount": 0, "share_pct": 0.0, "status": "ok"},
            {"code": "IND02", "label": "가상업종 나", "amount": 1000, "share_pct": 100.0, "status": "ok"},
        ]
    )
    items = parsed(zero).profiles[0].industry
    assert items[0].status == "ok" and items[0].amount == 0


def test_구성비_합이_맞지_않으면_경고만_하고_읽는다():
    odd = profile(
        industry=[{"code": "IND01", "label": "가상업종", "amount": 100, "share_pct": 10.0, "status": "ok"}]
    )
    result = parsed(odd)
    assert len(result.profiles) == 1
    assert any("구성비 합" in w for w in result.warnings)


def test_경고_문구에_자료의_값을_적지_않는다():
    """오류 문구에 금액·비중을 넣지 않는다 (2.0 파서와 같은 원칙)."""
    leaky = profile(
        industry=[{"code": "IND01", "label": "가상업종", "amount": 987654321, "share_pct": 33.33, "status": "no_data"}]
    )
    for warning in parsed(leaky).warnings:
        assert "987654321" not in warning and "33.33" not in warning


# ---------------------------------------------------------------- 준비 상태


def test_준비됐다고_적힌_것만_보여_준다():
    item = parsed(profile()).profiles[0]
    assert item.ready("industry") is True
    assert item.ready("peers") is False
    # 아예 적지 않은 기능은 보여 주지 않는다 (모르면 보여 주지 않는다)
    assert item.ready("season") is False


def test_보여_주지_못하는_이유를_한_줄로_알려_준다():
    item = parsed(profile()).profiles[0]
    assert "연결되지 않았습니다" in item.readiness_note("peers")
    assert "연결되지 않았습니다" in item.readiness_note("season")
    assert item.readiness_note("industry") == ""


def test_허용하지_않는_준비_상태는_버린다():
    assert parsed(profile(readiness={"industry": "좋음"})).profiles == ()


def test_모르는_기능_이름은_경고만_하고_넘어간다():
    result = parsed(profile(readiness={"industry": "ok", "없는기능": "ok"}))
    assert len(result.profiles) == 1
    assert any("알 수 없는 기능" in w for w in result.warnings)


# ---------------------------------------------------------------- 운영 기준


def test_기준값에_버전이_없으면_읽지_않는다():
    result = parsed(profile(), thresholds={"R02": {"low": 20.0}})
    assert result.thresholds is None


def test_숫자가_아닌_기준값은_경고하고_버린다():
    result = parsed(profile(), thresholds={"version": "t1", "R02": {"low": "스무%"}})
    assert result.thresholds is not None and result.thresholds.rules == {}
    assert any("숫자여야" in w for w in result.warnings)


# ---------------------------------------------------------------- 파일이 없을 때


def test_프로필_묶음이_없으면_알려_준다():
    result = parse_profiles({"schema_version": "2.1"})
    assert result.profiles == ()
    assert any("프로필 묶음이 없습니다" in w for w in result.warnings)


def test_아직_읽지_않는_유사_지역은_알_수_없는_필드로_보지_않는다():
    """유사 지역은 목록이 확정되기 전이라 읽지 않는다. 있어도 경고를 내지 않는다."""
    later = profile(peers=[{"region_key": "x"}])
    result = parsed(later)
    assert len(result.profiles) == 1
    assert not [w for w in result.warnings if "알 수 없는 필드" in w]


def test_경로가_없는_파일은_지금처럼_오류():
    with pytest.raises(EvidenceError):
        load_evidence(Path("없는파일.json"))
