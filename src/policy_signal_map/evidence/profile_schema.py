"""근거 파일 2.1의 지역 프로필(`profiles`)과 운영 기준(`thresholds`) 형태와 검증.

형식 기준과 결정 이유: `7지역확장계획.md` 3장.

**2.0과의 관계:** `records`는 2.0과 완전히 같고 `schema.py`가 그대로 읽는다. 여기서는 더해진 묶음만 본다.

**고장 났을 때의 태도가 `schema.py`와 다르다.**
- `records`가 틀리면 파일 전체를 거부한다 (2~5단계가 잘못된 수치를 보여 주면 안 되므로).
- 프로필이 틀리면 **그 지역의 프로필만 버리고 경고로 남긴다.** 프로필 한 곳이 틀렸다고
  기존 검토까지 멈추면 자료 한 칸 때문에 서비스 전체가 서는 셈이다 (7지역확장계획.md 3-4장).

오류 문구에 금액·비중 **값을 적지 않는다.** 형식과 자리만 적는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------- 허용 값

PROFILE_SCHEMA_VERSION = "2.1"

GEOGRAPHIC_SCOPES = ("national", "sido", "sigungu")
# 자료의 지역이 가맹점 자리 기준인지 이용자 기준인지는 아직 확인 전이다 (7지역확장계획.md 8장 1번).
# 확인 전에는 unconfirmed로 받고, 화면에서 단정하지 않는다
REGION_BASES = ("merchant", "cardholder", "unconfirmed")
ITEM_STATUSES = ("ok", "no_data")
# 기능별 준비 상태 (7지역확장계획.md 3-3장)
READINESS_STATES = ("ok", "insufficient", "unlinked", "blocked")
READINESS_KEYS = ("profile", "industry", "age", "industry_age", "season", "foreign", "peers", "external")
AGE_DENOMINATORS = ("known_only", "all")

PROFILE_FIELDS = (
    "region_key",
    "geographic_scope",
    "region_basis",
    "period_start",
    "period_end",
    "industry",
    "age",
    "industry_age",
    "external",
    "age_denominator",
    "months",
    "season_threshold",
    "foreign_share_pct",
    "foreign_type",
    "foreign_type_status",
    "unknown_share_pct",
    "ranks",
    "small_region",
    "reference_rules",
    "peers",
    "peer_method",
    "readiness",
    "limitations",
)
ITEM_FIELDS = ("code", "label", "amount", "share_pct", "status", "percentile", "regions")
INDUSTRY_AGE_FIELDS = ("industry_code", "age_denominator", "ages")
EXTERNAL_FIELDS = ("population", "registered_foreigners", "registered_foreigners_monthly")
EXTERNAL_ITEM_FIELDS = ("status", "count", "observed_at", "source_name")
EXTERNAL_SERIES_FIELDS = ("status", "values", "source_name", "period")
EXTERNAL_SERIES_VALUE_FIELDS = ("month", "count")
EXTERNAL_STATUSES = ("ok", "no_data", "unlinked", "blocked")
MONTH_FIELDS = ("month", "status", "season_index")
RANK_FIELDS = ("percentile", "regions")
PEER_FIELDS = ("region_key", "distance")

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
# 구성비 합이 100에서 이만큼 넘게 벗어나면 경고만 한다 (반올림 오차를 오류로 보지 않는다)
SHARE_SUM_TOLERANCE_PP = 0.5

READINESS_LABELS = {
    "ok": "",
    "insufficient": "이 지역은 자료가 부족해 보여 드리지 않습니다.",
    "unlinked": "이 지역은 아직 연결되지 않았습니다.",
    "blocked": "이 자료는 쓸 수 없습니다.",
}


# ---------------------------------------------------------------- 데이터 형태


@dataclass(frozen=True)
class ShareItem:
    """업종 하나 또는 연령 구간 하나의 금액과 비중.

    `percentile`은 같은 지표를 가진 지역들 사이에서 이 지역이 어디쯤인지다(0에 가까울수록 낮은 편).
    **`regions`(몇 곳 중인지) 없이는 순위를 쓰지 않는다.** 둘 다 없으면 '판단할 자료가 없음'으로 본다.
    """

    code: str
    label: str
    amount: int | None
    share_pct: float | None
    status: str
    percentile: float | None = None
    regions: int | None = None

    @property
    def has_value(self) -> bool:
        return self.status == "ok" and self.share_pct is not None

    @property
    def has_rank(self) -> bool:
        return self.percentile is not None and self.regions is not None

    @property
    def no_payment(self) -> bool:
        """결제가 0원이다. "자료 없음"과 다르며, 상점이 없다는 뜻도 아니다."""
        return self.status == "ok" and self.amount == 0


@dataclass(frozen=True)
class SeasonMonth:
    """그 달의 결제가 평소보다 얼마나 컸는지. 전국 공통 흐름은 뺀 값이다."""

    month: str
    status: str
    season_index: float | None


@dataclass(frozen=True)
class Rank:
    """같은 지표를 가진 지역들 사이의 자리. 유효 지역 수를 반드시 함께 둔다."""

    percentile: float
    regions: int


@dataclass(frozen=True)
class IndustryAgeBreakdown:
    """업종 하나 안에서 본 연령 구성. R08은 순위와 유효 지역 수가 있는 연령만 비교한다."""

    industry_code: str
    age_denominator: str
    ages: tuple[ShareItem, ...]


@dataclass(frozen=True)
class ExternalMeasure:
    """관측 시점과 출처를 잃지 않는 외부 인구 항목."""

    status: str
    count: int | None = None
    observed_at: str | None = None
    source_name: str | None = None

    @property
    def has_value(self) -> bool:
        return self.status == "ok" and self.count is not None


@dataclass(frozen=True)
class ExternalData:
    population: ExternalMeasure | None = None
    registered_foreigners: ExternalMeasure | None = None
    registered_foreigners_monthly: "ExternalSeries | None" = None


@dataclass(frozen=True)
class ExternalMonth:
    month: str
    count: int


@dataclass(frozen=True)
class ExternalSeries:
    """월별 외부 자료. 기간·출처를 원문과 함께 보존한다."""

    status: str
    values: tuple[ExternalMonth, ...] = ()
    source_name: str | None = None
    period: str | None = None


@dataclass(frozen=True)
class Peer:
    """분석 전달본이 계산해 준 유사 지역과 거리."""

    region_key: str
    distance: float


@dataclass(frozen=True)
class RegionProfile:
    region_key: str
    geographic_scope: str
    region_basis: str
    period_start: str
    period_end: str
    industry: tuple[ShareItem, ...] = ()
    age: tuple[ShareItem, ...] = ()
    industry_age: tuple[IndustryAgeBreakdown, ...] = ()
    external: ExternalData | None = None
    age_denominator: str = "known_only"
    months: tuple[SeasonMonth, ...] = ()
    # 전달본은 지역 규모 구간까지 반영한 최종 기준을 지역별로 준다.
    season_threshold: float | None = None
    foreign_share_pct: float | None = None
    foreign_type: str | None = None
    foreign_type_status: str | None = None
    unknown_share_pct: float | None = None
    ranks: dict[str, Rank] = field(default_factory=dict)
    # 결제 규모가 작은 지역인지. 작은 지역은 달마다 값이 크게 흔들려 질문 기준을 따로 쓴다.
    # 분석 쪽이 적어 주지 않으면 None이며, 그때는 기본 기준만 쓴다
    small_region: bool | None = None
    reference_rules: tuple[str, ...] = ()
    peers: tuple[Peer, ...] = ()
    peer_method: str | None = None
    readiness: dict[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()

    def ready(self, key: str) -> bool:
        """그 부분을 화면에 보여 줘도 되는지. 적지 않았으면 보여 주지 않는다 (모르면 보여 주지 않는다)."""
        return self.readiness.get(key) == "ok"

    def readiness_note(self, key: str) -> str:
        """보여 주지 못하는 이유 한 줄. 이유를 모르면 '아직 연결되지 않았습니다'로 적는다."""
        state = self.readiness.get(key, "unlinked")
        return READINESS_LABELS.get(state, READINESS_LABELS["unlinked"])


@dataclass(frozen=True)
class Thresholds:
    """질문을 띄우는 운영 기준. 값을 코드에 적지 않고 여기서 받는다 (7지역확장계획.md 7장)."""

    version: str
    rules: dict[str, dict[str, float]] = field(default_factory=dict)

    def get(self, rule_id: str, key: str) -> float | None:
        return self.rules.get(rule_id, {}).get(key)


@dataclass(frozen=True)
class ProfileParseResult:
    profiles: tuple[RegionProfile, ...]
    thresholds: Thresholds | None
    # 프로필은 고장 나도 파일을 거부하지 않는다. 버린 자리는 모두 여기에 남는다
    warnings: tuple[str, ...]


# ---------------------------------------------------------------- 검증 도우미


class _Dropped(Exception):
    """이 프로필은 버린다. 사유는 경고로 남는다."""


def _where(*parts: object) -> str:
    return " > ".join(str(p) for p in parts)


def _text(raw: Any, at: str, name: str, allowed: tuple[str, ...] | None = None) -> str:
    value = raw.get(name)
    if not isinstance(value, str) or not value.strip():
        raise _Dropped(f"{at} > {name}: 글자여야 합니다")
    if allowed is not None and value not in allowed:
        raise _Dropped(f"{at} > {name}: 허용하지 않는 값입니다 (가능한 값: {', '.join(allowed)})")
    return value


def _number(raw: Any, at: str, name: str, *, low: float, high: float | None = None) -> float | None:
    """비중·지수처럼 소수를 받는 칸. 없거나 null이면 None."""
    value = raw.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _Dropped(f"{at} > {name}: 숫자여야 합니다")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise _Dropped(f"{at} > {name}: 숫자로 쓸 수 없는 값입니다")
    if number < low or (high is not None and number > high):
        bound = f"{low} 이상" + (f" {high} 이하" if high is not None else "")
        raise _Dropped(f"{at} > {name}: {bound}여야 합니다")
    return number


def _amount(raw: Any, at: str, name: str) -> int | None:
    value = raw.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise _Dropped(f"{at} > {name}: 원 단위 정수여야 합니다")
    if value < 0:
        raise _Dropped(f"{at} > {name}: 0 이상이어야 합니다")
    return value


def _unknown_fields(raw: dict, allowed: tuple[str, ...], at: str, warnings: list[str]) -> None:
    for key in raw:
        if key not in allowed and not key.startswith("_"):
            warnings.append(f"{at} > {key}: 알 수 없는 필드입니다 (무시하고 읽음)")


# ---------------------------------------------------------------- 묶음별 읽기


def _parse_items(raw: Any, at: str, warnings: list[str]) -> tuple[ShareItem, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise _Dropped(f"{at}: 목록이어야 합니다")

    items: list[ShareItem] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        spot = _where(at, index + 1)
        if not isinstance(entry, dict):
            raise _Dropped(f"{spot}: 객체여야 합니다")
        _unknown_fields(entry, ITEM_FIELDS, spot, warnings)
        code = _text(entry, spot, "code")
        if code in seen:
            raise _Dropped(f"{spot} > code: 같은 코드가 두 번 있습니다")
        seen.add(code)
        status = _text(entry, spot, "status", ITEM_STATUSES)
        amount = _amount(entry, spot, "amount")
        share = _number(entry, spot, "share_pct", low=0.0, high=100.0)
        if status == "ok" and share is None:
            raise _Dropped(f"{spot}: 계산했다고 적혀 있는데 비중이 비어 있습니다")
        percentile = _number(entry, spot, "percentile", low=0.0, high=100.0)
        regions = entry.get("regions")
        if regions is not None and (isinstance(regions, bool) or not isinstance(regions, int) or regions < 1):
            raise _Dropped(f"{spot} > regions: 1 이상의 정수여야 합니다 (몇 곳 중인지)")
        if (percentile is None) != (regions is None):
            # 분모를 모르면 순위를 쓸 수 없다. 한쪽만 온 값은 지어내지 않고 거부한다
            raise _Dropped(f"{spot}: 순위는 percentile과 regions를 함께 적어야 합니다")
        if status == "no_data" and any(value is not None for value in (amount, share, percentile, regions)):
            # 자료 없음과 0원을 섞지 않는다. 0원이면 status는 ok이고 금액이 0이다
            raise _Dropped(f"{spot}: 자료 없음인데 값이 들어 있습니다")

        items.append(
            ShareItem(
                code=code,
                label=_text(entry, spot, "label"),
                amount=amount,
                share_pct=share,
                status=status,
                percentile=percentile,
                regions=regions,
            )
        )

    values = [item.share_pct for item in items if item.has_value]
    if values and abs(sum(values) - 100.0) > SHARE_SUM_TOLERANCE_PP:
        warnings.append(f"{at}: 구성비 합이 100%에서 벗어납니다 (그대로 읽음)")
    return tuple(items)


def _parse_industry_age(
    raw: Any,
    at: str,
    warnings: list[str],
    *,
    industry_codes: set[str],
    age_codes: set[str],
) -> tuple[IndustryAgeBreakdown, ...]:
    """업종 안의 연령 구성을 읽는다. 틀리면 호출부가 이 지역의 R08만 끈다."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise _Dropped(f"{at}: 목록이어야 합니다")

    groups: list[IndustryAgeBreakdown] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        spot = _where(at, index + 1)
        if not isinstance(entry, dict):
            raise _Dropped(f"{spot}: 객체여야 합니다")
        _unknown_fields(entry, INDUSTRY_AGE_FIELDS, spot, warnings)
        industry_code = _text(entry, spot, "industry_code")
        if industry_code in seen:
            raise _Dropped(f"{spot} > industry_code: 같은 업종 코드가 두 번 있습니다")
        if industry_code not in industry_codes:
            raise _Dropped(f"{spot} > industry_code: 이 프로필의 업종 목록에 없는 코드입니다")
        seen.add(industry_code)

        denominator = _text(entry, spot, "age_denominator", AGE_DENOMINATORS)
        items = _parse_items(entry.get("ages"), _where(spot, "ages"), warnings)
        if not items:
            raise _Dropped(f"{spot} > ages: 한 개 이상의 연령 항목이 있어야 합니다")
        if any(item.code not in age_codes for item in items):
            raise _Dropped(f"{spot} > ages: 이 프로필의 연령 목록에 없는 코드가 있습니다")
        groups.append(IndustryAgeBreakdown(industry_code, denominator, items))
    return tuple(groups)


def _parse_external_measure(raw: Any, at: str, warnings: list[str], *, minimum: int) -> ExternalMeasure:
    if not isinstance(raw, dict):
        raise _Dropped(f"{at}: 객체여야 합니다")
    _unknown_fields(raw, EXTERNAL_ITEM_FIELDS, at, warnings)
    status = _text(raw, at, "status", EXTERNAL_STATUSES)
    count = raw.get("count")
    observed_at = raw.get("observed_at")
    source_name = raw.get("source_name")

    if status == "ok":
        if isinstance(count, bool) or not isinstance(count, int) or count < minimum:
            raise _Dropped(f"{at} > count: {minimum} 이상의 정수여야 합니다")
        if not isinstance(observed_at, str) or not _DATE_RE.match(observed_at):
            raise _Dropped(f"{at} > observed_at: YYYY-MM-DD 형식이어야 합니다")
        if not isinstance(source_name, str) or not source_name.strip():
            raise _Dropped(f"{at} > source_name: 글자여야 합니다")
    else:
        if count is not None:
            raise _Dropped(f"{at}: 사용할 수 없는 상태인데 count가 들어 있습니다")
        if observed_at is not None and (not isinstance(observed_at, str) or not _DATE_RE.match(observed_at)):
            raise _Dropped(f"{at} > observed_at: YYYY-MM-DD 형식이어야 합니다")
        if source_name is not None and (not isinstance(source_name, str) or not source_name.strip()):
            raise _Dropped(f"{at} > source_name: 글자여야 합니다")

    return ExternalMeasure(status, count, observed_at, source_name)


def _parse_external_series(raw: Any, at: str, warnings: list[str]) -> ExternalSeries:
    if not isinstance(raw, dict):
        raise _Dropped(f"{at}: 객체여야 합니다")
    _unknown_fields(raw, EXTERNAL_SERIES_FIELDS, at, warnings)
    status = _text(raw, at, "status", EXTERNAL_STATUSES)
    source_name = raw.get("source_name")
    period = raw.get("period")
    for name, value in (("source_name", source_name), ("period", period)):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise _Dropped(f"{at} > {name}: 글자여야 합니다")

    values_raw = raw.get("values", [])
    if not isinstance(values_raw, list):
        raise _Dropped(f"{at} > values: 목록이어야 합니다")
    values: list[ExternalMonth] = []
    seen: set[str] = set()
    for index, entry in enumerate(values_raw):
        spot = _where(at, "values", index + 1)
        if not isinstance(entry, dict):
            raise _Dropped(f"{spot}: 객체여야 합니다")
        _unknown_fields(entry, EXTERNAL_SERIES_VALUE_FIELDS, spot, warnings)
        month = _text(entry, spot, "month")
        if not _MONTH_RE.match(month) or month in seen:
            raise _Dropped(f"{spot} > month: YYYY-MM 형식의 겹치지 않는 달이어야 합니다")
        count = entry.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise _Dropped(f"{spot} > count: 0 이상의 정수여야 합니다")
        seen.add(month)
        values.append(ExternalMonth(month, count))
    if status == "ok" and (not values or source_name is None or period is None):
        raise _Dropped(f"{at}: 사용할 수 있는 월별 자료에는 값·출처·기간이 모두 있어야 합니다")
    if status != "ok" and values:
        raise _Dropped(f"{at}: 사용할 수 없는 상태인데 월별 값이 들어 있습니다")
    return ExternalSeries(status, tuple(values), source_name, period)


def _parse_external(raw: Any, at: str, warnings: list[str]) -> ExternalData | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise _Dropped(f"{at}: 객체여야 합니다")
    _unknown_fields(raw, EXTERNAL_FIELDS, at, warnings)
    population = (
        _parse_external_measure(raw["population"], _where(at, "population"), warnings, minimum=1)
        if "population" in raw
        else None
    )
    registered = (
        _parse_external_measure(
            raw["registered_foreigners"],
            _where(at, "registered_foreigners"),
            warnings,
            minimum=0,
        )
        if "registered_foreigners" in raw
        else None
    )
    registered_monthly = (
        _parse_external_series(
            raw["registered_foreigners_monthly"],
            _where(at, "registered_foreigners_monthly"),
            warnings,
        )
        if "registered_foreigners_monthly" in raw
        else None
    )
    return ExternalData(population, registered, registered_monthly)


def _parse_months(raw: Any, at: str, warnings: list[str]) -> tuple[SeasonMonth, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise _Dropped(f"{at}: 목록이어야 합니다")

    months: list[SeasonMonth] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        spot = _where(at, index + 1)
        if not isinstance(entry, dict):
            raise _Dropped(f"{spot}: 객체여야 합니다")
        _unknown_fields(entry, MONTH_FIELDS, spot, warnings)
        month = _text(entry, spot, "month")
        if not _MONTH_RE.match(month):
            raise _Dropped(f"{spot} > month: YYYY-MM 형식이어야 합니다")
        if month in seen:
            raise _Dropped(f"{spot} > month: 같은 달이 두 번 있습니다")
        seen.add(month)
        status = _text(entry, spot, "status", ITEM_STATUSES)
        index_value = _number(entry, spot, "season_index", low=0.0)
        if status == "ok" and index_value is None:
            raise _Dropped(f"{spot}: 계산했다고 적혀 있는데 값이 비어 있습니다")
        if status == "no_data" and index_value is not None:
            raise _Dropped(f"{spot}: 자료 없음인데 값이 들어 있습니다")
        months.append(SeasonMonth(month=month, status=status, season_index=index_value))
    return tuple(months)


def _parse_ranks(raw: Any, at: str, warnings: list[str]) -> dict[str, Rank]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _Dropped(f"{at}: 객체여야 합니다")

    ranks: dict[str, Rank] = {}
    for name, entry in raw.items():
        spot = _where(at, name)
        if not isinstance(entry, dict):
            raise _Dropped(f"{spot}: 객체여야 합니다")
        _unknown_fields(entry, RANK_FIELDS, spot, warnings)
        percentile = _number(entry, spot, "percentile", low=0.0, high=100.0)
        if percentile is None:
            raise _Dropped(f"{spot} > percentile: 값이 있어야 합니다")
        regions = entry.get("regions")
        if isinstance(regions, bool) or not isinstance(regions, int) or regions < 1:
            # 분모를 모르면 순위를 보여 줄 수 없다. "255곳 중"을 지어내지 않는다
            raise _Dropped(f"{spot} > regions: 1 이상의 정수여야 합니다 (몇 곳 중인지)")
        ranks[name] = Rank(percentile=percentile, regions=regions)
    return ranks


def _parse_peers(raw: Any, at: str, warnings: list[str]) -> tuple[Peer, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise _Dropped(f"{at}: 목록이어야 합니다")
    peers: list[Peer] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        spot = _where(at, index + 1)
        if not isinstance(entry, dict):
            raise _Dropped(f"{spot}: 객체여야 합니다")
        _unknown_fields(entry, PEER_FIELDS, spot, warnings)
        region_key = _text(entry, spot, "region_key")
        distance = _number(entry, spot, "distance", low=0.0)
        if distance is None:
            raise _Dropped(f"{spot} > distance: 값이 있어야 합니다")
        if region_key in seen:
            raise _Dropped(f"{spot} > region_key: 같은 지역이 두 번 있습니다")
        seen.add(region_key)
        peers.append(Peer(region_key, distance))
    return tuple(peers)


def _optional_text(raw: dict, at: str, name: str) -> str | None:
    value = raw.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _Dropped(f"{at} > {name}: 글자여야 합니다")
    return value


def _text_tuple(raw: Any, at: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(value, str) and value.strip() for value in raw):
        raise _Dropped(f"{at}: 비어 있지 않은 글자 목록이어야 합니다")
    return tuple(dict.fromkeys(raw))


def _parse_readiness(raw: Any, at: str, warnings: list[str]) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _Dropped(f"{at}: 객체여야 합니다")

    states: dict[str, str] = {}
    for name, value in raw.items():
        spot = _where(at, name)
        if name not in READINESS_KEYS:
            warnings.append(f"{spot}: 알 수 없는 기능 이름입니다 (무시하고 읽음)")
            continue
        if value not in READINESS_STATES:
            raise _Dropped(f"{spot}: 허용하지 않는 상태입니다 (가능한 값: {', '.join(READINESS_STATES)})")
        states[name] = value
    return states


def _parse_profile(raw: Any, index: int, warnings: list[str]) -> RegionProfile:
    at = _where("프로필", index + 1)
    if not isinstance(raw, dict):
        raise _Dropped(f"{at}: 객체여야 합니다")
    _unknown_fields(raw, PROFILE_FIELDS, at, warnings)

    region_key = _text(raw, at, "region_key")
    scope = _text(raw, at, "geographic_scope", GEOGRAPHIC_SCOPES)
    period_start = _text(raw, at, "period_start")
    period_end = _text(raw, at, "period_end")
    for name, value in (("period_start", period_start), ("period_end", period_end)):
        if not _MONTH_RE.match(value):
            raise _Dropped(f"{at} > {name}: YYYY-MM 형식이어야 합니다")
    if period_end < period_start:
        raise _Dropped(f"{at} > period_end: 시작 달보다 빠릅니다")

    small_region = raw.get("small_region")
    if small_region is not None and not isinstance(small_region, bool):
        raise _Dropped(f"{at} > small_region: 참/거짓이어야 합니다")

    age_denominator = raw.get("age_denominator", "known_only")
    if age_denominator not in AGE_DENOMINATORS:
        raise _Dropped(f"{at} > age_denominator: 허용하지 않는 값입니다 (가능한 값: {', '.join(AGE_DENOMINATORS)})")

    industry = _parse_items(raw.get("industry"), _where(at, "industry"), warnings)
    age = _parse_items(raw.get("age"), _where(at, "age"), warnings)
    readiness = _parse_readiness(raw.get("readiness"), _where(at, "readiness"), warnings)
    try:
        industry_age = _parse_industry_age(
            raw.get("industry_age"),
            _where(at, "industry_age"),
            warnings,
            industry_codes={item.code for item in industry},
            age_codes={item.code for item in age},
        )
    except _Dropped as exc:
        warnings.append(f"{exc} — 이 지역의 업종별 연령 구성은 사용하지 않습니다")
        industry_age = ()
        readiness = {**readiness, "industry_age": "blocked"}
    try:
        external = _parse_external(raw.get("external"), _where(at, "external"), warnings)
    except _Dropped as exc:
        warnings.append(f"{exc} — 이 지역의 외부 자료는 사용하지 않습니다")
        external = None
        readiness = {**readiness, "external": "blocked"}
    try:
        peers = _parse_peers(raw.get("peers"), _where(at, "peers"), warnings)
    except _Dropped as exc:
        warnings.append(f"{exc} — 이 지역의 유사 지역 목록은 사용하지 않습니다")
        peers = ()
        readiness = {**readiness, "peers": "blocked"}

    return RegionProfile(
        region_key=region_key,
        geographic_scope=scope,
        region_basis=_text(raw, at, "region_basis", REGION_BASES),
        period_start=period_start,
        period_end=period_end,
        industry=industry,
        age=age,
        industry_age=industry_age,
        external=external,
        age_denominator=age_denominator,
        months=_parse_months(raw.get("months"), _where(at, "months"), warnings),
        season_threshold=_number(raw, at, "season_threshold", low=0.0),
        foreign_share_pct=_number(raw, at, "foreign_share_pct", low=0.0, high=100.0),
        foreign_type=_optional_text(raw, at, "foreign_type"),
        foreign_type_status=_optional_text(raw, at, "foreign_type_status"),
        unknown_share_pct=_number(raw, at, "unknown_share_pct", low=0.0, high=100.0),
        ranks=_parse_ranks(raw.get("ranks"), _where(at, "ranks"), warnings),
        small_region=small_region,
        reference_rules=_text_tuple(raw.get("reference_rules"), _where(at, "reference_rules")),
        peers=peers,
        peer_method=_optional_text(raw, at, "peer_method"),
        readiness=readiness,
        limitations=tuple(str(line) for line in raw.get("limitations", []) if str(line).strip()),
    )


def _parse_thresholds(raw: Any, warnings: list[str]) -> Thresholds | None:
    if raw is None:
        return None
    at = "운영 기준"
    if not isinstance(raw, dict):
        warnings.append(f"{at}: 객체여야 합니다 (읽지 않음)")
        return None
    version = raw.get("version")
    if not isinstance(version, str) or not version.strip():
        warnings.append(f"{at} > version: 글자여야 합니다 (읽지 않음)")
        return None

    rules: dict[str, dict[str, float]] = {}
    for rule_id, values in raw.items():
        if rule_id == "version":
            continue
        if not isinstance(values, dict):
            warnings.append(f"{_where(at, rule_id)}: 객체여야 합니다 (읽지 않음)")
            continue
        picked: dict[str, float] = {}
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                warnings.append(f"{_where(at, rule_id, name)}: 숫자여야 합니다 (읽지 않음)")
                continue
            picked[name] = float(value)
        if picked:
            rules[rule_id] = picked
    return Thresholds(version=version, rules=rules)


# ---------------------------------------------------------------- 바깥에서 쓰는 함수


def parse_profiles(data: Any) -> ProfileParseResult:
    """2.1 파일의 `profiles`·`thresholds`를 읽는다. 고장 난 프로필은 버리고 경고로 남긴다."""
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ProfileParseResult((), None, ("프로필: 파일을 읽을 수 없습니다",))

    raw_profiles = data.get("profiles")
    profiles: list[RegionProfile] = []
    if raw_profiles is None:
        warnings.append("프로필: 형식 버전이 2.1인데 프로필 묶음이 없습니다 (지역 화면은 '자료 없음'으로 둡니다)")
    elif not isinstance(raw_profiles, list):
        warnings.append("프로필: 목록이어야 합니다 (읽지 않음)")
    else:
        seen: set[str] = set()
        for index, entry in enumerate(raw_profiles):
            try:
                profile = _parse_profile(entry, index, warnings)
            except _Dropped as exc:
                warnings.append(f"{exc} — 이 지역의 프로필은 보여 주지 않습니다")
                continue
            if profile.region_key in seen:
                warnings.append(f"프로필 {index + 1} > region_key: 같은 지역이 두 번 있습니다 — 뒤의 것은 버립니다")
                continue
            seen.add(profile.region_key)
            profiles.append(profile)

    return ProfileParseResult(tuple(profiles), _parse_thresholds(data.get("thresholds"), warnings), tuple(warnings))
