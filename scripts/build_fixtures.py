"""테스트용 근거 파일 경계 사례 28개를 만든다.

실행: uv run python scripts/build_fixtures.py
사례 수치와 기대 결과: 1근거계산계층계획.md 6장. 모든 수치는 가상 규모다.
"""

from __future__ import annotations

import copy
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _evidence_builder import evidence_file, ok_month, record, status_month, write_json  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "evidence"
EVIDENCE_ID = "FX-01"


def _file(name: str, case: str, months: list[dict]) -> dict:
    return evidence_file([record(EVIDENCE_ID, months)], dataset_version=f"fixture-{name}", case=case)


# ---------------------------------------------------------------- 정상 사례 10개


def _valid_cases() -> dict[str, tuple[str, list[dict]]]:
    return {
        "amount_up_share_down": (
            "외국인 금액 증가, 전체 금액이 더 빠르게 증가 → 비교 A 반대 (8-5장 1행)",
            [ok_month("2026-01", 800, 10000, 1000), ok_month("2026-02", 900, 12000, 1200)],
        ),
        "amount_down_share_up": (
            "외국인 금액 감소, 전체 금액이 더 빠르게 감소 → 비교 A 반대 (8-5장 2행)",
            [ok_month("2026-01", 900, 12000, 1200), ok_month("2026-02", 800, 10000, 1000)],
        ),
        "same_direction": (
            "외국인 금액과 비중 모두 증가 → 반대 아님 (8-5장 3행)",
            [ok_month("2026-01", 800, 10000, 1000), ok_month("2026-02", 1000, 11000, 1100)],
        ),
        "flat_change": (
            "01→02 금액 변화 0, 02→03 비중 변화 0 → 반대 아님 (8-5장 4행)",
            [
                ok_month("2026-01", 800, 10000, 1000),
                ok_month("2026-02", 800, 11000, 1000),
                ok_month("2026-03", 1600, 22000, 2000),
            ],
        ),
        "prev_foreign_zero": (
            "이전 달 외국인 금액 0 → 증감률 계산 불가, 금액 차이는 유효 (8-5장 5행)",
            [
                ok_month("2026-01", 0, 10000, 1000, warnings=("외국인 집단 관측 행 없음 (실제 소비 0으로 단정하지 않음)",)),
                ok_month("2026-02", 500, 10000, 1000),
            ],
        ),
        "missing_month": (
            "02월 자료 없음 → 01→02, 02→03 보류, 01→03을 잇지 않음 (8-5장 6행)",
            [
                ok_month("2026-01", 800, 10000, 1000),
                status_month("2026-02", "no_data", warnings=("해당 월 관측 행 없음",)),
                ok_month("2026-03", 900, 12000, 1200),
            ],
        ),
        "tiny_change": (
            "비중 변화 −0.0004%p의 반대 방향 → 방향 유지, 표시는 0.01%p 미만",
            [ok_month("2026-01", 800, 10000, 1000), ok_month("2026-02", 801, 10013, 1000)],
        ),
        "known_only_differs": (
            "전체 분모 비중 감소, 미상 제외 비중 증가 → 비교 B만 반대",
            [ok_month("2026-01", 800, 10000, 1000), ok_month("2026-02", 790, 10500, 2000)],
        ),
        "large_amounts": (
            "소수점 계산은 비중 변화 없음, 정수 교차곱은 증가 → 교차곱 방식 필요",
            [
                ok_month("2026-01", 70_000_000_000_000, 1_000_000_000_000_000, 50_000_000_000_000),
                ok_month("2026-02", 70_000_000_000_004, 1_000_000_000_000_057, 50_000_000_000_000),
            ],
        ),
        "unknown_equals_total": (
            "02월 미상 금액 = 전체 금액 → 미상 제외 비중 null, 비교 B 계산 불가",
            [ok_month("2026-01", 800, 10000, 1000), ok_month("2026-02", 0, 5000, 5000)],
        ),
    }


# ---------------------------------------------------------------- 오류 사례 12개 (정상 ①에서 한 곳만 바꿈)


def _base() -> dict:
    case, months = _valid_cases()["amount_up_share_down"]
    return _file("base", case, months)


def _month(data: dict, index: int) -> dict:
    return data["records"][0]["months"][index]


def _set_no_data_with_zero(data: dict) -> None:
    m = _month(data, 1)
    m.update(
        calculation_status="no_data",
        foreign_amount=0,
        total_amount=0,
        unknown_amount=0,
        transaction_count=None,
        foreign_share_pct=None,
        known_only_share_pct=None,
        unknown_share_pct=None,
    )


def _set_mixed_data_kind(data: dict) -> None:
    real = copy.deepcopy(data["records"][0])
    real["evidence_id"] = "FX-02-REAL-LABEL-ONLY"
    real["data_kind"] = "real"  # 수치는 가짜이며 이름표만 real이다
    data["records"].append(real)


def _set_denominator_zero(data: dict) -> None:
    _month(data, 1).update(
        calculation_status="invalid_denominator",
        foreign_amount=0,
        total_amount=0,
        unknown_amount=0,
        transaction_count=0,
        foreign_share_pct=None,
        known_only_share_pct=None,
        unknown_share_pct=None,
        warnings=["전체 금액 0으로 비중 계산 불가"],
    )


def _invalid_cases() -> dict[str, tuple[str, Callable[[dict], None]]]:
    return {
        "invalid_status_value": (
            "02월 calculation_status가 목록에 없는 값",
            lambda d: _month(d, 1).update(calculation_status="okay"),
        ),
        "invalid_applicability": (
            "R07 applicability status가 목록에 없는 값",
            lambda d: d["records"][0]["applicability"]["R07"].update(status="maybe"),
        ),
        "missing_reason": (
            "R06 applicability reason이 빈 문자열",
            lambda d: d["records"][0]["applicability"]["R06"].update(reason=""),
        ),
        "relation_broken": (
            "02월 외국인+미상 금액이 전체 금액보다 큼",
            lambda d: _month(d, 1).update(unknown_amount=11200),
        ),
        "negative_amount": (
            "01월 외국인 금액 음수",
            lambda d: _month(d, 0).update(foreign_amount=-800),
        ),
        "decimal_amount": (
            "01월 외국인 금액이 소수",
            lambda d: _month(d, 0).update(foreign_amount=800.5),
        ),
        "no_data_with_zero": (
            "02월 자료 없음인데 금액을 0으로 적음 (비중·건수는 null)",
            _set_no_data_with_zero,
        ),
        "month_omitted": (
            "기간은 03월까지인데 03월 항목이 없음",
            lambda d: d["records"][0]["scope"].update(period_end="2026-03"),
        ),
        "schema_version_unsupported": (
            "지원하지 않는 형식 버전",
            lambda d: d.update(schema_version="1.0"),
        ),
        "mixed_data_kind": (
            "합성 레코드와 실제 표시 레코드가 한 파일에 섞임 (실제 레코드 수치도 가짜)",
            _set_mixed_data_kind,
        ),
        "denominator_zero": (
            "02월 전체 금액 0, invalid_denominator → 로드 성공, 비교는 보류",
            _set_denominator_zero,
        ),
        "national_region_key_wrong": (
            "전국 범위인데 region_key가 ALL이 아님",
            lambda d: d["records"][0]["scope"].update(region_key="11"),
        ),
    }


# ---------------------------------------------------------------- 지역 사례 3개

# 행정표준코드 10자리를 그대로 region_key로 쓴다 (연결 키 C-1). 서울 1100000000 / 강원 5100000000
SEOUL = "1100000000"
GANGWON = "5100000000"


def _six_ok_months(base_f: int, base_t: int, base_u: int) -> list[dict]:
    """6개월 모두 계산 가능한 달. 수치는 가상이며 방향 확인용으로만 쓴다."""
    return [
        ok_month(f"2026-0{i}", base_f + i * 5, base_t + i * 40, base_u + i * 3)
        for i in range(1, 7)
    ]


def _region_cases() -> dict[str, tuple[str, list[dict]]]:
    national = record(EVIDENCE_ID, _six_ok_months(800, 10000, 500))

    allowed_seoul = record(
        "FX-SIDO-SEOUL",
        _six_ok_months(300, 4000, 200),
        geographic_scope="sido",
        region_key=SEOUL,
        region_basis="merchant_location",
    )
    allowed_gangwon = record(
        "FX-SIDO-GANGWON",
        _six_ok_months(120, 1500, 90),
        geographic_scope="sido",
        region_key=GANGWON,
        region_basis="merchant_location",
    )

    blocked_seoul = record(
        "FX-SIDO-SEOUL-BLOCKED",
        _six_ok_months(300, 4000, 200),
        geographic_scope="sido",
        region_key=SEOUL,
        region_basis="unknown",
        applicability={
            "R07": {"status": "blocked", "reason": "지역 기준 미확인으로 사용 불가"},
            "R06": {"status": "blocked", "reason": "업종·월 보정 자료 없음"},
            "R02": {"status": "blocked", "reason": "업종 후보 자료 미확인"},
        },
    )
    review_gangwon = record(
        "FX-SIDO-GANGWON-REVIEW",
        _six_ok_months(120, 1500, 90),
        geographic_scope="sido",
        region_key=GANGWON,
        region_basis="merchant_location",
        applicability={
            "R07": {"status": "needs_review", "reason": "표본 대표성 확인 중"},
            "R06": {"status": "blocked", "reason": "업종·월 보정 자료 없음"},
            "R02": {"status": "blocked", "reason": "업종 후보 자료 미확인"},
        },
    )

    sparse_gangwon = record(
        "FX-SIDO-GANGWON-SPARSE",
        [
            ok_month("2026-01", 120, 1500, 90),
            status_month("2026-02", "no_data", warnings=("해당 월 관측 행 없음",)),
            status_month("2026-03", "no_data", warnings=("해당 월 관측 행 없음",)),
            ok_month("2026-04", 128, 1540, 95),
            status_month("2026-05", "invalid_denominator", F=0, T=0, U=0, C=0, warnings=("전체 금액 0으로 비중 계산 불가",)),
            ok_month("2026-06", 131, 1560, 98),
        ],
        geographic_scope="sido",
        region_key=GANGWON,
        region_basis="merchant_location",
    )

    return {
        "sido_allowed": (
            "전국 + 사용 가능한 시도 2곳 (서울·강원) — 지역 선택과 시군구 안내 확인",
            [national, allowed_seoul, allowed_gangwon],
        ),
        "sido_blocked": (
            "전국 + 사용 불가 시도(서울) + 검토 필요 시도(강원) — 되돌림과 요약 보류 확인",
            [national, blocked_seoul, review_gangwon],
        ),
        "sido_sparse": (
            "전국 + 표본이 부족한 시도(강원, 6개월 중 계산 가능 3개월)",
            [national, sparse_gangwon],
        ),
    }


# ---------------------------------------------------------------- 2.1 프로필 사례 3개


def _items(prefix: str, labels: list[str], shares: list[float]) -> list[dict]:
    """구성비 항목. 합이 100이 되도록 마지막 항목으로 맞춘다."""
    rows = []
    for index, (label, share) in enumerate(zip(labels, shares, strict=True), start=1):
        rows.append(
            {
                "code": f"{prefix}{index:02d}",
                "label": label,
                "amount": int(share * 100),
                "share_pct": share,
                "status": "ok",
            }
        )
    return rows


def _profile(region_key: str, scope: str, *, readiness: dict | None = None) -> dict:
    return {
        "region_key": region_key,
        "geographic_scope": scope,
        "region_basis": "unconfirmed",
        "period_start": "2026-01",
        "period_end": "2026-06",
        "industry": _items("IND", ["가상업종 가", "가상업종 나", "가상업종 다"], [50.0, 30.0, 20.0]),
        "age": _items("AGE", ["가상연령 1", "가상연령 2"], [60.0, 40.0]),
        "age_denominator": "known_only",
        "months": [
            {"month": "2026-01", "status": "ok", "season_index": 1.0},
            {"month": "2026-02", "status": "no_data", "season_index": None},
            {"month": "2026-03", "status": "ok", "season_index": 1.2},
            {"month": "2026-04", "status": "ok", "season_index": 0.9},
            {"month": "2026-05", "status": "ok", "season_index": 1.1},
            {"month": "2026-06", "status": "ok", "season_index": 1.0},
        ],
        "foreign_share_pct": 4.0,
        "unknown_share_pct": 2.0,
        "ranks": {"foreign_share": {"percentile": 40.0, "regions": 12}},
        "readiness": readiness
        or {"profile": "ok", "industry": "ok", "age": "ok", "season": "ok", "foreign": "ok", "peers": "unlinked"},
        "limitations": ["시연용 가상 수치입니다."],
    }


THRESHOLDS = {
    "version": "fixture-th-1",
    "R02": {"low_share_percentile": 20.0},
    "R04": {"season_index": 1.10, "season_index_small_region": 1.25},
}


def _profile_cases() -> dict[str, dict]:
    national = record(EVIDENCE_ID, _six_ok_months(800, 10000, 500))
    seoul = record(
        "FX-SIDO-SEOUL",
        _six_ok_months(300, 4000, 200),
        geographic_scope="sido",
        region_key=SEOUL,
        region_basis="merchant_location",
    )

    ok_file = evidence_file(
        [national, seoul],
        dataset_version="fixture-profiles_ok",
        schema_version="2.1",
        case="2.1 정상 — 전국·시도 프로필과 운영 기준",
    )
    ok_file["profiles"] = [_profile("ALL", "national"), _profile(SEOUL, "sido")]
    ok_file["thresholds"] = THRESHOLDS

    # 한 곳만 고장 난 파일. 파일은 그대로 읽히고 그 지역만 빠져야 한다
    broken = evidence_file(
        [national, seoul],
        dataset_version="fixture-profiles_one_broken",
        schema_version="2.1",
        case="2.1 — 프로필 한 곳이 고장 남 (그 지역만 빠지고 파일은 읽힌다)",
    )
    bad = _profile(SEOUL, "sido")
    bad["ranks"] = {"foreign_share": {"percentile": 40.0}}  # 몇 곳 중인지 없음
    broken["profiles"] = [_profile("ALL", "national"), bad]

    # 형식 버전은 2.0인데 프로필이 들어 있는 파일 — 조용히 무시하지 않고 거부한다
    mismatch = evidence_file(
        [national],
        dataset_version="fixture-profiles_version_mismatch",
        case="형식 버전 2.0인데 프로필이 들어 있음 — 거부",
    )
    mismatch["profiles"] = [_profile("ALL", "national")]

    return {"profiles_ok": ok_file, "profiles_one_broken": broken, "profiles_version_mismatch": mismatch}


def build_all() -> dict[str, dict]:
    files: dict[str, dict] = {}
    for name, (case, months) in _valid_cases().items():
        files[f"{name}.json"] = _file(name, case, months)
    for name, (case, records) in _region_cases().items():
        files[f"{name}.json"] = evidence_file(records, dataset_version=f"fixture-{name}", case=case)
    for name, data in _profile_cases().items():
        files[f"{name}.json"] = data
    for name, (case, mutate) in _invalid_cases().items():
        data = _base()
        data["_case"] = case
        data["dataset_version"] = f"fixture-{name}"
        mutate(data)
        files[f"{name}.json"] = data
    return files


def main() -> int:
    files = build_all()
    for name, data in files.items():
        write_json(OUT_DIR / name, data)
    stale = sorted(p.name for p in OUT_DIR.glob("*.json") if p.name not in files)
    print(f"경계 사례 {len(files)}개 -> {OUT_DIR}")
    if stale:
        print("생성 목록에 없는 파일 (확인 후 삭제):", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
