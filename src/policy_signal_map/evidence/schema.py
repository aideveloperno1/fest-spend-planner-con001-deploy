"""분석 근거 파일(review_evidence.json)의 형태와 검증.

형식 기준: 개발업무 워크플로우 8-1, 9-1~9-3장. 상세 규칙: 1근거계산계층계획.md 5장·7장.
허용 값이 바뀌면 아래 상수만 고친다.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from types import MappingProxyType
from typing import Any

# ---------------------------------------------------------------- 허용 값

# 2.1은 2.0에 지역 프로필(profiles)과 운영 기준(thresholds)을 **더한** 형식이다.
# records 계약은 둘이 완전히 같아 이 모듈이 그대로 읽고, 더해진 묶음은 profile_schema.py가 읽는다
SUPPORTED_SCHEMA_VERSIONS = frozenset({"2.0", "2.1"})
PROFILE_VERSION = "2.1"
DATA_KINDS = ("synthetic", "real")
GEOGRAPHIC_SCOPES = ("national", "sido", "sigungu")
POPULATIONS = ("foreign_code_3",)
INDUSTRY_SCOPES = ("all_provided",)
AGE_SCOPES = ("all",)
CALCULATION_STATUSES = ("ok", "no_data", "invalid_input", "invalid_denominator")
APPLICABILITY_STATUSES = ("allowed", "needs_review", "blocked")
REQUIRED_RULES = ("R07", "R06", "R02")
AMOUNT_UNITS = ("KRW",)
NATIONAL_REGION_KEY = "ALL"
# 파일 비중과 정수 금액으로 다시 계산한 비중의 허용 차이 (%p)
SHARE_TOLERANCE_PP = Fraction(1, 10**6)

STATUS_LABELS = {
    "ok": "계산 가능",
    "no_data": "자료 없음",
    "invalid_input": "입력 확인 필요",
    "invalid_denominator": "분모 0",
}

FILE_FIELDS = ("schema_version", "dataset_version", "records", "profiles", "thresholds")
RECORD_FIELDS = (
    "evidence_id",
    "data_kind",
    "scope",
    "region_basis",
    "applicability",
    "amount_unit",
    "months",
    "limitations",
)
SCOPE_FIELDS = (
    "geographic_scope",
    "region_key",
    "population",
    "industry_scope",
    "age_scope",
    "period_start",
    "period_end",
)
AMOUNT_FIELDS = ("foreign_amount", "total_amount", "unknown_amount")
COUNT_FIELD = "transaction_count"
SHARE_FIELDS = ("foreign_share_pct", "known_only_share_pct", "unknown_share_pct")
MONTH_FIELDS = ("month", "calculation_status", *AMOUNT_FIELDS, COUNT_FIELD, *SHARE_FIELDS, "warnings")

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


# ---------------------------------------------------------------- 데이터 형태


# evidence_id는 데이터 담당이 붙이는 근거 자료 이름이다(예: "REAL-R07-NATIONAL").
# 이름에 규칙 번호가 들어가도 서비스가 해석하지 않으며, 화면에는 근거 칩으로 그대로 보여 준다.
# 규칙 관리 번호(R01~R07) 자체는 화면·보완 기획안에 쓰지 않는다 (사용자 결정 2026-09-18).

@dataclass(frozen=True)
class Scope:
    geographic_scope: str
    region_key: str
    population: str
    industry_scope: str
    age_scope: str
    period_start: str
    period_end: str


@dataclass(frozen=True)
class Applicability:
    status: str
    reason: str


@dataclass(frozen=True)
class MonthValue:
    month: str
    calculation_status: str
    foreign_amount: int | None
    total_amount: int | None
    unknown_amount: int | None
    transaction_count: int | None
    foreign_share_pct: float | None
    known_only_share_pct: float | None
    unknown_share_pct: float | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    data_kind: str
    scope: Scope
    region_basis: str
    applicability: Mapping[str, Applicability]
    amount_unit: str
    months: tuple[MonthValue, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceFile:
    schema_version: str
    dataset_version: str
    records: tuple[EvidenceRecord, ...]

    @property
    def data_kind(self) -> str:
        # 검증에서 한 파일 안의 종류가 모두 같음을 확인했다
        return self.records[0].data_kind


@dataclass(frozen=True)
class ParseResult:
    file: EvidenceFile | None
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


# ---------------------------------------------------------------- 도우미


def month_range(start: str, end: str) -> list[str]:
    year, month = int(start[:4]), int(start[5:])
    end_year, end_month = int(end[:4]), int(end[5:])
    result = []
    while (year, month) <= (end_year, end_month):
        result.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return result


def is_valid_month(value: Any) -> bool:
    return isinstance(value, str) and bool(_MONTH_RE.match(value))


def is_int(value: Any) -> bool:
    # bool은 int의 하위 타입이라 type으로 비교한다
    return type(value) is int


def is_number(value: Any) -> bool:
    return (type(value) is int or type(value) is float) and math.isfinite(value)


def kind_of(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "참/거짓"
    if isinstance(value, int):
        return "정수"
    if isinstance(value, float):
        return "소수"
    if isinstance(value, str):
        return "글자"
    if isinstance(value, list):
        return "목록"
    if isinstance(value, dict):
        return "객체"
    return type(value).__name__


def _shown(value: Any) -> str:
    text = str(value)
    return text if len(text) <= 40 else text[:40] + "…"


@dataclass
class _Issues:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @staticmethod
    def _where(*parts: str) -> str:
        return "[" + " / ".join(p for p in parts if p) + "]"

    def error(self, where: tuple[str, ...], message: str) -> None:
        self.errors.append(f"{self._where(*where)} {message}")

    def warn(self, where: tuple[str, ...], message: str) -> None:
        self.warnings.append(f"{self._where(*where)} {message}")

    # 수치 필드는 값을 출력하지 않고 형식만 알린다 (실제 금액 노출 방지)
    def wrong_type(self, where: tuple[str, ...], expected: str, value: Any) -> None:
        self.error(where, f"{expected} (받은 형식: {kind_of(value)})")

    # 글자 필드는 값을 보여줘도 수치가 새지 않는다
    def not_allowed(self, where: tuple[str, ...], value: Any, allowed: tuple[str, ...] | frozenset[str]) -> None:
        if isinstance(value, str):
            choices = ", ".join(sorted(allowed))
            self.error(where, f'허용되지 않는 값 "{_shown(value)}"입니다 (허용: {choices})')
        else:
            self.wrong_type(where, "글자여야 합니다", value)


def _require_text(issues: _Issues, where: tuple[str, ...], data: dict, key: str) -> str | None:
    if key not in data:
        issues.error((*where, key), "필수 필드가 없습니다")
        return None
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        if isinstance(value, str):
            issues.error((*where, key), "비어 있지 않은 글자여야 합니다")
        else:
            issues.wrong_type((*where, key), "비어 있지 않은 글자여야 합니다", value)
        return None
    return value


def _require_choice(
    issues: _Issues, where: tuple[str, ...], data: dict, key: str, allowed: tuple[str, ...] | frozenset[str]
) -> str | None:
    if key not in data:
        issues.error((*where, key), "필수 필드가 없습니다")
        return None
    value = data[key]
    # 목록·객체는 해시할 수 없어 형식을 먼저 확인한다
    if not isinstance(value, str) or value not in allowed:
        issues.not_allowed((*where, key), value, allowed)
        return None
    return value


def _text_list(issues: _Issues, where: tuple[str, ...], value: Any) -> tuple[str, ...] | None:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        issues.wrong_type(where, "글자 목록이어야 합니다", value)
        return None
    return tuple(value)


# ---------------------------------------------------------------- 파일


def parse_evidence(
    data: Any,
    *,
    required_rules: tuple[str, ...] = REQUIRED_RULES,
    accepted_rules: tuple[str, ...] = REQUIRED_RULES,
) -> ParseResult:
    issues = _Issues()
    file = _parse_file(data, issues, required_rules, accepted_rules)
    if issues.errors:
        file = None
    return ParseResult(file, tuple(issues.errors), tuple(issues.warnings))


def _parse_file(
    data: Any,
    issues: _Issues,
    required_rules: tuple[str, ...],
    accepted_rules: tuple[str, ...],
) -> EvidenceFile | None:
    where = ("파일",)
    if not isinstance(data, dict):
        issues.wrong_type(where, "최상위는 JSON 객체여야 합니다", data)
        return None

    for key in data:
        # _로 시작하는 최상위 필드는 사례 설명 등 참고용이라 무시한다
        if key not in FILE_FIELDS and not key.startswith("_"):
            issues.warn((*where, key), "알 수 없는 필드입니다 (무시하고 읽음)")

    schema_version = None
    if "schema_version" not in data:
        issues.error((*where, "schema_version"), "필수 필드가 없습니다")
    elif not isinstance(data["schema_version"], str) or data["schema_version"] not in SUPPORTED_SCHEMA_VERSIONS:
        value = data["schema_version"]
        if isinstance(value, str):
            issues.error(
                (*where, "schema_version"),
                f'지원하지 않는 형식 버전 "{_shown(value)}"입니다. 데이터 담당에게 형식 버전을 확인하세요',
            )
        else:
            issues.wrong_type((*where, "schema_version"), "글자여야 합니다", value)
    else:
        schema_version = data["schema_version"]

    dataset_version = _require_text(issues, where, data, "dataset_version")

    # 2.0 파일에 프로필이 들어 있으면 조용히 무시하지 않고 알린다.
    # 모르는 필드는 경고 후 무시하는 것이 기본이라, 이 자리를 막지 않으면
    # 담당자가 프로필을 넣었는데 화면에는 "자료 없음"만 뜨는 일이 생긴다
    if schema_version is not None and schema_version != PROFILE_VERSION:
        for key in ("profiles", "thresholds"):
            if key in data:
                issues.error(
                    (*where, key),
                    f'형식 버전이 "{schema_version}"인데 {key}가 들어 있습니다. '
                    f'형식 버전을 "{PROFILE_VERSION}"로 올려 주세요',
                )

    if "records" not in data:
        issues.error((*where, "records"), "필수 필드가 없습니다")
        return None
    raw_records = data["records"]
    if not isinstance(raw_records, list) or not raw_records:
        if isinstance(raw_records, list):
            issues.error((*where, "records"), "레코드가 1개 이상 있어야 합니다")
        else:
            issues.wrong_type((*where, "records"), "레코드 목록이어야 합니다", raw_records)
        return None

    records = [
        _parse_record(raw, index, issues, required_rules, accepted_rules)
        for index, raw in enumerate(raw_records)
    ]

    seen: set[str] = set()
    for raw in raw_records:
        evidence_id = raw.get("evidence_id") if isinstance(raw, dict) else None
        if isinstance(evidence_id, str) and evidence_id:
            if evidence_id in seen:
                issues.error((*where, "records"), f'evidence_id "{_shown(evidence_id)}"가 중복됩니다')
            seen.add(evidence_id)

    kinds = {
        raw["data_kind"]
        for raw in raw_records
        if isinstance(raw, dict) and isinstance(raw.get("data_kind"), str) and raw["data_kind"] in DATA_KINDS
    }
    if len(kinds) > 1:
        issues.error(where, "합성 자료와 실제 자료가 한 파일에 섞여 있습니다. 파일을 나눠 주세요")

    if schema_version is None or dataset_version is None or any(r is None for r in records):
        return None
    return EvidenceFile(schema_version, dataset_version, tuple(r for r in records if r is not None))


# ---------------------------------------------------------------- 레코드


def _parse_record(
    raw: Any,
    index: int,
    issues: _Issues,
    required_rules: tuple[str, ...],
    accepted_rules: tuple[str, ...],
) -> EvidenceRecord | None:
    position = f"records[{index}]"
    if not isinstance(raw, dict):
        issues.wrong_type((position,), "레코드는 객체여야 합니다", raw)
        return None

    start_errors = len(issues.errors)
    evidence_id = raw.get("evidence_id")
    label = evidence_id if isinstance(evidence_id, str) and evidence_id.strip() else position
    where = (label,)

    for key in raw:
        if key not in RECORD_FIELDS:
            issues.warn((*where, key), "알 수 없는 필드입니다 (무시하고 읽음)")

    evidence_id = _require_text(issues, where, raw, "evidence_id")
    data_kind = _require_choice(issues, where, raw, "data_kind", DATA_KINDS)
    scope = _parse_scope(raw, where, issues)

    region_basis = None
    if "region_basis" not in raw:
        issues.error((*where, "region_basis"), "필수 필드가 없습니다")
    elif not isinstance(raw["region_basis"], str):
        issues.wrong_type((*where, "region_basis"), "글자여야 합니다", raw["region_basis"])
    else:
        region_basis = raw["region_basis"]

    applicability = _parse_applicability(raw, where, issues, required_rules, accepted_rules)
    amount_unit = _require_choice(issues, where, raw, "amount_unit", AMOUNT_UNITS)
    months = _parse_months(raw, where, scope, issues)

    limitations = None
    if "limitations" not in raw:
        issues.error((*where, "limitations"), "필수 필드가 없습니다")
    else:
        limitations = _text_list(issues, (*where, "limitations"), raw["limitations"])

    if len(issues.errors) > start_errors:
        return None
    assert evidence_id and data_kind and scope and region_basis is not None
    assert applicability is not None and amount_unit and months is not None and limitations is not None
    return EvidenceRecord(evidence_id, data_kind, scope, region_basis, applicability, amount_unit, months, limitations)


def _parse_scope(raw: dict, where: tuple[str, ...], issues: _Issues) -> Scope | None:
    if "scope" not in raw:
        issues.error((*where, "scope"), "필수 필드가 없습니다")
        return None
    data = raw["scope"]
    if not isinstance(data, dict):
        issues.wrong_type((*where, "scope"), "객체여야 합니다", data)
        return None

    where = (*where, "scope")
    for key in data:
        if key not in SCOPE_FIELDS:
            issues.warn((*where, key), "알 수 없는 필드입니다 (무시하고 읽음)")

    start_errors = len(issues.errors)
    geographic = _require_choice(issues, where, data, "geographic_scope", GEOGRAPHIC_SCOPES)
    region_key = _require_text(issues, where, data, "region_key")
    population = _require_choice(issues, where, data, "population", POPULATIONS)
    industry = _require_choice(issues, where, data, "industry_scope", INDUSTRY_SCOPES)
    age = _require_choice(issues, where, data, "age_scope", AGE_SCOPES)

    if geographic == "national" and region_key is not None and region_key != NATIONAL_REGION_KEY:
        issues.error((*where, "region_key"), f'전국 범위의 region_key는 "{NATIONAL_REGION_KEY}"여야 합니다')
    if geographic in ("sido", "sigungu") and region_key == NATIONAL_REGION_KEY:
        issues.error((*where, "region_key"), f'지역 범위의 region_key는 "{NATIONAL_REGION_KEY}"일 수 없습니다')

    periods: dict[str, str | None] = {}
    for key in ("period_start", "period_end"):
        value = data.get(key)
        if key not in data:
            issues.error((*where, key), "필수 필드가 없습니다")
            periods[key] = None
        elif not is_valid_month(value):
            if isinstance(value, str):
                issues.error((*where, key), f'"YYYY-MM" 형식의 실제 월이어야 합니다 (받은 값: "{_shown(value)}")')
            else:
                issues.wrong_type((*where, key), '"YYYY-MM" 형식의 글자여야 합니다', value)
            periods[key] = None
        else:
            periods[key] = value

    start, end = periods["period_start"], periods["period_end"]
    if start and end and start > end:
        issues.error((*where, "period_end"), "기간 끝이 시작보다 빠릅니다")

    if len(issues.errors) > start_errors:
        return None
    assert geographic and region_key and population and industry and age and start and end
    return Scope(geographic, region_key, population, industry, age, start, end)


def _parse_applicability(
    raw: dict,
    where: tuple[str, ...],
    issues: _Issues,
    required_rules: tuple[str, ...],
    accepted_rules: tuple[str, ...],
) -> Mapping[str, Applicability] | None:
    if "applicability" not in raw:
        issues.error((*where, "applicability"), "필수 필드가 없습니다")
        return None
    data = raw["applicability"]
    if not isinstance(data, dict):
        issues.wrong_type((*where, "applicability"), "객체여야 합니다", data)
        return None

    start_errors = len(issues.errors)
    result: dict[str, Applicability] = {}
    for rule in data:
        if rule not in accepted_rules:
            issues.warn((*where, f"applicability.{rule}"), "이번 형식에서 쓰지 않는 규칙입니다 (무시하고 읽음)")

    for rule in accepted_rules:
        rule_where = (*where, f"applicability.{rule}")
        if rule not in data:
            if rule in required_rules:
                issues.error(rule_where, "필수 필드가 없습니다")
            continue
        item = data[rule]
        if not isinstance(item, dict):
            issues.wrong_type(rule_where, "객체여야 합니다", item)
            continue
        status = _require_choice(issues, (*where, f"applicability.{rule}"), item, "status", APPLICABILITY_STATUSES)
        reason = item.get("reason")
        if "reason" not in item:
            issues.error((*rule_where, "reason"), "사유(reason)가 없습니다")
        elif not isinstance(reason, str):
            issues.wrong_type((*rule_where, "reason"), "사유(reason)는 글자여야 합니다", reason)
        elif not reason.strip():
            issues.error((*rule_where, "reason"), "사유(reason)가 비어 있습니다")
        elif status:
            result[rule] = Applicability(status, reason)

    if len(issues.errors) > start_errors:
        return None
    return MappingProxyType(result)


# ---------------------------------------------------------------- 월


def _parse_months(
    raw: dict, where: tuple[str, ...], scope: Scope | None, issues: _Issues
) -> tuple[MonthValue, ...] | None:
    if "months" not in raw:
        issues.error((*where, "months"), "필수 필드가 없습니다")
        return None
    data = raw["months"]
    if not isinstance(data, list):
        issues.wrong_type((*where, "months"), "월 목록이어야 합니다", data)
        return None

    start_errors = len(issues.errors)
    months = [_parse_month(item, where, index, issues) for index, item in enumerate(data)]

    # 기간의 모든 월이 순서대로 한 번씩 있어야 한다 (누락 월도 상태와 null로 포함, 9-3장)
    labels = [item.get("month") if isinstance(item, dict) else None for item in data]
    if scope is not None and all(is_valid_month(m) for m in labels):
        expected = month_range(scope.period_start, scope.period_end)
        actual = [m for m in labels if isinstance(m, str)]
        month_where = (*where, "months")
        problems = False
        for month in expected:
            if month not in actual:
                issues.error(month_where, f"{month} 월이 없습니다 (누락 월도 상태와 null로 포함해야 합니다)")
                problems = True
        for month in sorted(set(actual)):
            if actual.count(month) > 1:
                issues.error(month_where, f"{month} 월이 중복됩니다")
                problems = True
            if month not in expected:
                issues.error(month_where, f"{month} 월은 기간 밖입니다")
                problems = True
        if not problems and actual != expected:
            issues.error(month_where, "월 순서가 기간 순서와 다릅니다")

    if len(issues.errors) > start_errors:
        return None
    return tuple(m for m in months if m is not None)


def _parse_month(raw: Any, where: tuple[str, ...], index: int, issues: _Issues) -> MonthValue | None:
    position = f"months[{index}]"
    if not isinstance(raw, dict):
        issues.wrong_type((*where, position), "월 값은 객체여야 합니다", raw)
        return None

    start_errors = len(issues.errors)
    month = raw.get("month")
    label = month if is_valid_month(month) else position
    mwhere = (*where, label)

    for key in raw:
        if key not in MONTH_FIELDS:
            issues.warn((*mwhere, key), "알 수 없는 필드입니다 (무시하고 읽음)")

    missing = [key for key in MONTH_FIELDS if key not in raw]
    for key in missing:
        issues.error((*mwhere, key), "필수 필드가 없습니다 (값이 없으면 null로 적어 주세요)")
    if missing:
        return None

    if not is_valid_month(month):
        if isinstance(month, str):
            issues.error((*mwhere, "month"), f'"YYYY-MM" 형식의 실제 월이어야 합니다 (받은 값: "{_shown(month)}")')
        else:
            issues.wrong_type((*mwhere, "month"), '"YYYY-MM" 형식의 글자여야 합니다', month)

    warnings = _text_list(issues, (*mwhere, "warnings"), raw["warnings"])

    status = raw["calculation_status"]
    if not isinstance(status, str) or status not in CALCULATION_STATUSES:
        issues.not_allowed((*mwhere, "calculation_status"), status, CALCULATION_STATUSES)
        # 상태를 알 수 없으면 상태별 규칙을 적용하지 않는다 (A-4)
        return None

    if status == "ok":
        _check_ok_month(raw, mwhere, issues)
    elif status == "no_data":
        _check_no_data_month(raw, mwhere, issues)
    else:
        _check_unusable_month(raw, mwhere, status, warnings, issues)

    if len(issues.errors) > start_errors:
        return None
    return MonthValue(
        month=month,
        calculation_status=status,
        foreign_amount=raw["foreign_amount"],
        total_amount=raw["total_amount"],
        unknown_amount=raw["unknown_amount"],
        transaction_count=raw[COUNT_FIELD],
        foreign_share_pct=raw["foreign_share_pct"],
        known_only_share_pct=raw["known_only_share_pct"],
        unknown_share_pct=raw["unknown_share_pct"],
        warnings=warnings or (),
    )


def _check_ok_month(raw: dict, where: tuple[str, ...], issues: _Issues) -> None:
    # M4·M5: 금액·건수는 0 이상의 정수
    counts_ok = True
    for key in (*AMOUNT_FIELDS, COUNT_FIELD):
        value = raw[key]
        expected = "원 단위 정수여야 합니다" if key != COUNT_FIELD else "정수여야 합니다"
        if not is_int(value):
            issues.wrong_type((*where, key), expected, value)
            counts_ok = False
        elif value < 0:
            issues.error((*where, key), "0 이상이어야 합니다")
            counts_ok = False

    # M8: 전체 분모 비중과 미상 비중은 숫자
    shares_ok = True
    for key in ("foreign_share_pct", "unknown_share_pct"):
        if not is_number(raw[key]):
            issues.wrong_type((*where, key), "숫자여야 합니다", raw[key])
            shares_ok = False

    F, T, U = raw["foreign_amount"], raw["total_amount"], raw["unknown_amount"]
    known = raw["known_only_share_pct"]

    if not counts_ok:
        # 금액이 틀리면 관계·비중 검사를 하지 않는다 (A-4). 미상 제외 비중은 형식만 확인
        if known is not None and not is_number(known):
            issues.wrong_type((*where, "known_only_share_pct"), "숫자 또는 null이어야 합니다", known)
        return

    # M6·M7: 금액 관계
    if T == 0:
        issues.error(
            (*where, "total_amount"),
            "계산 가능(ok) 월의 전체 금액은 0보다 커야 합니다. 0이면 invalid_denominator로 표시하세요",
        )
        return
    if F > T:
        issues.error((*where, "amounts"), "외국인 금액이 전체 금액보다 큽니다")
        return
    if U > T:
        issues.error((*where, "amounts"), "미상 금액이 전체 금액보다 큽니다")
        return
    if F + U > T:
        issues.error((*where, "amounts"), "외국인+미상 금액이 전체 금액보다 큽니다")
        return

    # M9: 미상 제외 분모가 0이면 null, 아니면 숫자
    K = T - U
    if K == 0 and known is not None:
        issues.error((*where, "known_only_share_pct"), "미상 제외 분모가 0이면 null이어야 합니다")
        return
    if K > 0 and not is_number(known):
        issues.wrong_type((*where, "known_only_share_pct"), "숫자여야 합니다", known)
        return
    if not shares_ok:
        return

    # M10: 파일 비중과 재계산 비중 대조. 다르면 경고만 하고 숫자를 고치지 않는다
    expected = {
        "foreign_share_pct": Fraction(F, T) * 100,
        "unknown_share_pct": Fraction(U, T) * 100,
    }
    if K > 0:
        expected["known_only_share_pct"] = Fraction(F, K) * 100
    for key, exact in expected.items():
        if abs(Fraction(raw[key]) - exact) > SHARE_TOLERANCE_PP:
            issues.warn(
                (*where, key),
                "파일의 비중이 금액으로 다시 계산한 값과 다릅니다 (계산에는 금액을 사용합니다)",
            )


def _check_no_data_month(raw: dict, where: tuple[str, ...], issues: _Issues) -> None:
    # M11: 자료 없음은 0이 아니라 null (관측 0과 구분, 8-1장)
    filled_amounts = [key for key in (*AMOUNT_FIELDS, COUNT_FIELD) if raw[key] is not None]
    if filled_amounts:
        issues.error(
            (*where, "amounts"),
            f"자료 없음(no_data) 월의 금액은 null이어야 합니다 (값이 있는 필드: {', '.join(filled_amounts)})",
        )
    filled_shares = [key for key in SHARE_FIELDS if raw[key] is not None]
    if filled_shares:
        issues.error(
            (*where, "shares"),
            f"자료 없음(no_data) 월의 비중은 null이어야 합니다 (값이 있는 필드: {', '.join(filled_shares)})",
        )


def _check_unusable_month(
    raw: dict, where: tuple[str, ...], status: str, warnings: tuple[str, ...] | None, issues: _Issues
) -> None:
    # M12: 계산할 수 없는 월의 비중은 null
    filled_shares = [key for key in SHARE_FIELDS if raw[key] is not None]
    if filled_shares:
        issues.error(
            (*where, "shares"),
            f"{status} 월의 비중은 null이어야 합니다 (값이 있는 필드: {', '.join(filled_shares)})",
        )
    # M13·M5: 금액이 있으면 정수, invalid_denominator는 0 이상
    for key in (*AMOUNT_FIELDS, COUNT_FIELD):
        value = raw[key]
        if value is None:
            continue
        if not is_int(value):
            issues.wrong_type((*where, key), "정수 또는 null이어야 합니다", value)
        elif status == "invalid_denominator" and value < 0:
            issues.error((*where, key), "0 이상이어야 합니다")
    # M14
    if status == "invalid_input" and warnings is not None and not warnings:
        issues.warn((*where, "warnings"), "입력 오류 사유를 warnings에 적어 주세요")
