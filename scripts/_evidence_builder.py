"""근거 파일 JSON 조립 도우미. build_fixtures.py와 build_demo_evidence.py가 함께 쓴다.

비중은 손으로 적지 않고 정수 금액에서 계산해 넣는다 (9-3장 예시처럼 소수 10자리).
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

DEFAULT_APPLICABILITY = {
    "R07": {"status": "allowed", "reason": "합성 전국 금액·비중 및 분모 점검 예시로만 사용"},
    "R06": {"status": "blocked", "reason": "업종·월 보정 자료 없음"},
    "R02": {"status": "needs_review", "reason": "지역 기준과 업종 후보 자료 미확인"},
}

DEFAULT_LIMITATIONS = [
    "합성 자료",
    "전국 참고 예시이며 선택 지역 진단이 아님",
    "미상 제외 비중을 정답으로 해석하지 않음",
]


def pct(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(float(Fraction(numerator, denominator) * 100), 10)


def ok_month(month: str, F: int, T: int, U: int, C: int | None = None, warnings: tuple[str, ...] = ()) -> dict:
    notes = list(warnings)
    known = pct(F, T - U)
    if T - U == 0:
        notes.append("미상 제외 분모 0")
    return {
        "month": month,
        "calculation_status": "ok",
        "foreign_amount": F,
        "total_amount": T,
        "unknown_amount": U,
        "transaction_count": T // 20 if C is None else C,
        "foreign_share_pct": pct(F, T),
        "known_only_share_pct": known,
        "unknown_share_pct": pct(U, T),
        "warnings": notes,
    }


def status_month(
    month: str,
    status: str,
    *,
    F: int | None = None,
    T: int | None = None,
    U: int | None = None,
    C: int | None = None,
    warnings: tuple[str, ...] = (),
) -> dict:
    return {
        "month": month,
        "calculation_status": status,
        "foreign_amount": F,
        "total_amount": T,
        "unknown_amount": U,
        "transaction_count": C,
        "foreign_share_pct": None,
        "known_only_share_pct": None,
        "unknown_share_pct": None,
        "warnings": list(warnings),
    }


def record(
    evidence_id: str,
    months: list[dict],
    *,
    data_kind: str = "synthetic",
    geographic_scope: str = "national",
    region_key: str = "ALL",
    region_basis: str = "unknown",
    applicability: dict | None = None,
    limitations: list[str] | None = None,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "data_kind": data_kind,
        "scope": {
            "geographic_scope": geographic_scope,
            "region_key": region_key,
            "population": "foreign_code_3",
            "industry_scope": "all_provided",
            "age_scope": "all",
            "period_start": months[0]["month"],
            "period_end": months[-1]["month"],
        },
        "region_basis": region_basis,
        "applicability": json.loads(json.dumps(applicability or DEFAULT_APPLICABILITY)),
        "amount_unit": "KRW",
        "months": months,
        "limitations": list(limitations or DEFAULT_LIMITATIONS),
    }


def evidence_file(records: list[dict], *, dataset_version: str, schema_version: str = "2.0", case: str | None = None) -> dict:
    data: dict = {}
    if case:
        data["_case"] = case
    data.update({"schema_version": schema_version, "dataset_version": dataset_version, "records": records})
    return data


def to_json_text(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_json_text(data), encoding="utf-8", newline="\n")
