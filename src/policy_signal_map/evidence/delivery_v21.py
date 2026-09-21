"""분석팀 전달본 2.1을 서비스 내부 2.1 형태로 바꾼다.

전달본과 서비스 내부 파일은 같은 ``schema_version=2.1``을 쓰지만 구조가 다르다.
원본 수치를 다시 계산하지 않고 이름과 묶음만 바꾸며, 실자료 지역은 검증된
``private/region_mapping.json``으로만 연결한다.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DELIVERY_REQUIRED_RULES = ("R07", "R06")
DELIVERY_ACCEPTED_RULES = ("R07", "R06", "R02")
PEER_METHOD_ID = "delivery-v2.1-standardized-euclidean-v1"


@dataclass(frozen=True)
class DeliveryAdaptResult:
    document: dict[str, Any] | None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def is_delivery_v21(data: Any) -> bool:
    """내부 2.1이 아니라 분석 전달본 2.1인지 구조로 구분한다."""
    return (
        isinstance(data, dict)
        and data.get("schema_version") == "2.1"
        and "profiles" not in data
        and isinstance(data.get("records"), list)
        and isinstance(data.get("industry_codes"), dict)
        and isinstance(data.get("age_labels"), dict)
        and isinstance(data.get("national_distribution"), dict)
        and any(isinstance(row, dict) and isinstance(row.get("profile"), dict) for row in data["records"])
    )


def _mapping_index(path: Path | None) -> tuple[dict[str, dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if path is None:
        return {}, ["지역 대응표 경로가 없어 실자료는 전국 레코드만 연결합니다"]
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}, ["지역 대응표 파일이 없어 실자료는 전국 레코드만 연결합니다"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return {}, ["지역 대응표를 읽을 수 없어 실자료는 전국 레코드만 연결합니다"]
    if not isinstance(raw, dict) or not isinstance(raw.get("rows"), list):
        return {}, ["지역 대응표 형식이 맞지 않아 실자료는 전국 레코드만 연결합니다"]

    index: dict[str, dict[str, Any]] = {}
    for row in raw["rows"]:
        if not isinstance(row, dict) or row.get("link_status") not in ("linked", "composed"):
            continue
        source_key, region_key = row.get("source_key"), row.get("region_code10")
        if isinstance(source_key, str) and source_key and isinstance(region_key, str) and region_key:
            index[source_key] = row
    counts = raw.get("counts")
    if isinstance(counts, dict) and isinstance(counts.get("unlinked"), int) and counts["unlinked"]:
        warnings.append(f"지역 대응표에서 서비스 지역 {counts['unlinked']}곳은 아직 자료와 연결되지 않았습니다")
    return index, warnings


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _mapped_key(
    source_key: Any,
    *,
    real: bool,
    mapping: dict[str, dict[str, Any]],
) -> tuple[str | None, dict[str, Any] | None]:
    if source_key == "ALL":
        return "ALL", None
    if not isinstance(source_key, str) or not source_key:
        return None, None
    if not real:
        return source_key, None
    row = mapping.get(source_key)
    if row is None:
        return None, None
    key = row.get("region_code10")
    return (key, row) if isinstance(key, str) and key else (None, row)


def _base_record(record: dict[str, Any], region_key: str, index: int) -> dict[str, Any]:
    scope = _dict(record.get("scope"))
    applicability = {
        rule: value
        for rule, value in _dict(record.get("applicability")).items()
        if rule in DELIVERY_ACCEPTED_RULES
    }
    months = []
    month_fields = (
        "month",
        "calculation_status",
        "foreign_amount",
        "total_amount",
        "unknown_amount",
        "transaction_count",
        "foreign_share_pct",
        "known_only_share_pct",
        "unknown_share_pct",
        "warnings",
    )
    for month in _list(record.get("months")):
        if isinstance(month, dict):
            months.append({name: month.get(name) for name in month_fields})
    return {
        "evidence_id": f"D21-{index + 1:04d}",
        "data_kind": record.get("data_kind"),
        "scope": {
            "geographic_scope": scope.get("geographic_scope"),
            "region_key": region_key,
            "population": scope.get("population"),
            "industry_scope": scope.get("industry_scope"),
            "age_scope": scope.get("age_scope"),
            "period_start": scope.get("period_start"),
            "period_end": scope.get("period_end"),
        },
        "region_basis": record.get("region_basis"),
        "applicability": applicability,
        "amount_unit": record.get("amount_unit"),
        "months": months,
        "limitations": _list(record.get("limitations")),
    }


def _rank_parts(rank: Any, distribution: Any) -> tuple[Any, Any]:
    rank_dict, distribution_dict = _dict(rank), _dict(distribution)
    percentile, regions = rank_dict.get("percentile"), distribution_dict.get("n")
    if isinstance(percentile, (int, float)) and not isinstance(percentile, bool) and isinstance(regions, int):
        return percentile, regions
    return None, None


def _share_items(
    labels: dict[str, Any],
    shares: Any,
    ranks: Any,
    distributions: Any,
    *,
    zero_labels: set[str] | None = None,
) -> list[dict[str, Any]]:
    share_map, rank_map, distribution_map = _dict(shares), _dict(ranks), _dict(distributions)
    zero_labels = zero_labels or set()
    items: list[dict[str, Any]] = []
    for code, label in labels.items():
        if not isinstance(code, str) or not isinstance(label, str):
            continue
        share = share_map.get(label if label in share_map else code)
        if not isinstance(share, (int, float)) or isinstance(share, bool):
            items.append(
                {"code": code, "label": label, "amount": None, "share_pct": None, "status": "no_data", "percentile": None, "regions": None}
            )
            continue
        rank_entry = rank_map.get(label if label in rank_map else code)
        dist_entry = distribution_map.get(label if label in distribution_map else code)
        percentile, regions = _rank_parts(rank_entry, dist_entry)
        items.append(
            {
                "code": code,
                "label": label,
                # 전달본은 항목별 금액을 주지 않는다. 결제 0원 표지만 예외적으로 보존한다.
                "amount": 0 if label in zero_labels else None,
                "share_pct": share,
                "status": "ok",
                "percentile": percentile,
                "regions": regions,
            }
        )
    return items


def _industry_age(
    industry_labels: dict[str, Any],
    age_labels: dict[str, Any],
    profile: dict[str, Any],
    ranks: dict[str, Any],
    distributions: dict[str, Any],
) -> list[dict[str, Any]]:
    share_groups = _dict(profile.get("industry_age_share_pct"))
    rank_groups = _dict(ranks.get("industry_age_share_percentile"))
    dist_groups = _dict(distributions.get("industry_age_share_pct"))
    result: list[dict[str, Any]] = []
    for industry_code, industry_label in industry_labels.items():
        if not isinstance(industry_code, str) or not isinstance(industry_label, str):
            continue
        shares = _dict(share_groups.get(industry_label))
        rank_values = _dict(rank_groups.get(industry_label))
        dist_values = _dict(dist_groups.get(industry_label))
        ages = []
        for age_code, age_label in age_labels.items():
            if not isinstance(age_code, str) or not isinstance(age_label, str):
                continue
            share = shares.get(age_code)
            percentile = rank_values.get(age_code)
            regions = _dict(dist_values.get(age_code)).get("n")
            if not isinstance(share, (int, float)) or isinstance(share, bool):
                ages.append({"code": age_code, "label": age_label, "amount": None, "share_pct": None, "status": "no_data", "percentile": None, "regions": None})
            else:
                ranked = isinstance(percentile, (int, float)) and not isinstance(percentile, bool) and isinstance(regions, int)
                ages.append({"code": age_code, "label": age_label, "amount": None, "share_pct": share, "status": "ok", "percentile": percentile if ranked else None, "regions": regions if ranked else None})
        if ages:
            result.append({"industry_code": industry_code, "age_denominator": "known_only", "ages": ages})
    return result


def _external(record: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any] | None:
    raw = _dict(record.get("external"))
    population = raw.get("population_total")
    population_date = raw.get("population_base_date")
    population_source = _dict(sources.get("population")).get("source")
    result: dict[str, Any] = {}
    if isinstance(population, int) and population > 0:
        result["population"] = {
            "status": "ok",
            "count": population,
            "observed_at": population_date,
            "source_name": population_source,
        }

    monthly = raw.get("registered_foreign_by_month")
    registered_source = _dict(sources.get("registered_foreign"))
    if isinstance(monthly, dict) and monthly and all(
        isinstance(month, str)
        and isinstance(count, int)
        and not isinstance(count, bool)
        and count >= 0
        for month, count in monthly.items()
    ):
        result["registered_foreigners_monthly"] = {
            "status": "ok",
            "values": [{"month": month, "count": count} for month, count in monthly.items()],
            "source_name": registered_source.get("source"),
            "period": registered_source.get("period"),
        }
    elif isinstance(monthly, dict):
        # 달별 값 중 하나라도 없으면 부분값으로 합계를 지어내지 않고 상태만 보존한다.
        result["registered_foreigners_monthly"] = {
            "status": "no_data",
            "values": [],
            "source_name": registered_source.get("source"),
            "period": registered_source.get("period"),
        }
    return result or None


def _profile(
    record: dict[str, Any],
    region_key: str,
    mapping_row: dict[str, Any] | None,
    data: dict[str, Any],
    peer_keys: dict[str, str],
) -> dict[str, Any]:
    scope = _dict(record.get("scope"))
    profile = _dict(record.get("profile"))
    foreign = _dict(record.get("foreign_profile"))
    ranks = _dict(record.get("national_rank"))
    distributions = _dict(data.get("national_distribution"))
    flags = _dict(record.get("derived_flags"))
    size = _dict(record.get("size_flag"))
    season = _dict(record.get("season_summary"))
    industry_labels = _dict(data.get("industry_codes"))
    age_labels = _dict(data.get("age_labels"))
    zeros = {value for value in _list(flags.get("no_payment_industries")) if isinstance(value, str)}

    industry = _share_items(
        industry_labels,
        profile.get("industry_share_pct"),
        ranks.get("industry_share_pct"),
        distributions.get("industry_share_pct"),
        zero_labels=zeros,
    )
    age = _share_items(
        age_labels,
        profile.get("age_share_pct"),
        ranks.get("age_share_pct"),
        distributions.get("age_share_pct"),
    )
    industry_age = _industry_age(industry_labels, age_labels, profile, ranks, distributions)

    months = []
    for month in _list(record.get("months")):
        if not isinstance(month, dict):
            continue
        index_value = month.get("season_index")
        usable = month.get("calculation_status") == "ok" and isinstance(index_value, (int, float)) and not isinstance(index_value, bool)
        months.append({"month": month.get("month"), "status": "ok" if usable else "no_data", "season_index": index_value if usable else None})

    rank_result: dict[str, Any] = {}
    for name, rank_name, dist_name in (
        ("foreign_share", "foreign_share_pct", "foreign_share_pct"),
        ("payment_amount", "total_amount", "total_amount"),
        ("unknown_share", "unknown_share_pct", "unknown_share_pct"),
    ):
        percentile, regions = _rank_parts(ranks.get(rank_name), distributions.get(dist_name))
        if percentile is not None and regions is not None:
            rank_result[name] = {"percentile": percentile, "regions": regions}

    external = _external(record, _dict(data.get("external_sources")))
    peer_rows = []
    for peer in _list(record.get("peers")):
        if not isinstance(peer, dict):
            continue
        source_peer = peer.get("region_key")
        mapped_peer = peer_keys.get(source_peer) if isinstance(source_peer, str) else None
        if mapped_peer and mapped_peer != region_key:
            peer_rows.append({"region_key": mapped_peer, "distance": peer.get("distance")})

    reference_rules = [
        rule
        for rule, policy in _dict(data.get("display_policy")).items()
        if isinstance(rule, str) and _dict(policy).get("level") == "reference"
    ]
    limitations = [line for line in _list(record.get("limitations")) if isinstance(line, str)]
    if mapping_row is not None and mapping_row.get("link_status") == "composed":
        limitations.append("행정구역 개편에 따라 분석 원자료의 여러 구역을 합산해 연결했습니다.")

    readiness = {
        "profile": "ok",
        "industry": "ok" if industry else "insufficient",
        "age": "ok" if age else "insufficient",
        "industry_age": "ok" if industry_age else "insufficient",
        "season": "ok" if any(row["status"] == "ok" for row in months) else "unlinked",
        "foreign": "ok" if isinstance(foreign.get("foreign_share_pct"), (int, float)) else "insufficient",
        "peers": "ok" if peer_rows else "unlinked",
        "external": "ok" if external and "population" in external else "unlinked",
    }
    basis = record.get("region_basis")
    if basis not in ("merchant", "cardholder", "unconfirmed"):
        basis = "unconfirmed"
    return {
        "region_key": region_key,
        "geographic_scope": scope.get("geographic_scope"),
        "region_basis": basis,
        "period_start": scope.get("period_start"),
        "period_end": scope.get("period_end"),
        "industry": industry,
        "age": age,
        "industry_age": industry_age,
        "external": external,
        "age_denominator": "known_only",
        "months": months,
        "season_threshold": season.get("threshold"),
        "foreign_share_pct": foreign.get("foreign_share_pct"),
        "foreign_type": foreign.get("type"),
        "foreign_type_status": foreign.get("type_status"),
        "unknown_share_pct": size.get("unknown_share_pct"),
        "ranks": rank_result,
        "small_region": size.get("is_small"),
        "reference_rules": reference_rules,
        "peers": peer_rows,
        "peer_method": PEER_METHOD_ID if peer_rows else None,
        "readiness": readiness,
        "limitations": limitations,
    }


def _thresholds(data: dict[str, Any]) -> dict[str, Any]:
    raw = _dict(data.get("thresholds"))
    canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    version = f"{data.get('dataset_version', 'delivery-v2.1')}:{digest}"
    result: dict[str, Any] = {"version": version}
    mappings = (
        ("R02", "low_share_percentile", "R02_R08_low_percentile"),
        ("R08", "low_share_percentile", "R02_R08_low_percentile"),
        ("R04", "season_index", "R04_season_index_min"),
        ("R04", "season_index_small_region", "R04_season_index_min_small"),
        ("R12", "low_foreign_percentile", "R12_low_foreign_share_percentile"),
        ("R11", "visitor_to_resident_ratio", "R11_visitor_to_resident_ratio"),
    )
    for rule, target, source in mappings:
        value = raw.get(source)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result.setdefault(rule, {})[target] = value
    return result


def adapt_delivery_v21(data: Any, region_mapping_path: Path | None = None) -> DeliveryAdaptResult:
    if not is_delivery_v21(data):
        return DeliveryAdaptResult(None, ("분석 전달본 2.1 형식이 아닙니다",))
    assert isinstance(data, dict)
    records = data.get("records")
    if not isinstance(records, list) or not records:
        return DeliveryAdaptResult(None, ("전달본에 레코드가 없습니다",))

    real = data.get("data_kind") == "real" or any(
        isinstance(record, dict) and record.get("data_kind") == "real" for record in records
    )
    mapping, warnings = _mapping_index(region_mapping_path) if real else ({}, [])

    included: list[tuple[dict[str, Any], str, dict[str, Any] | None, int]] = []
    omitted = 0
    peer_keys: dict[str, str] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        source_key = _dict(record.get("scope")).get("region_key")
        region_key, mapping_row = _mapped_key(source_key, real=real, mapping=mapping)
        if region_key is None:
            omitted += 1
            continue
        if isinstance(source_key, str):
            peer_keys[source_key] = region_key
        included.append((record, region_key, mapping_row, index))
    if omitted:
        warnings.append(f"검증된 지역 대응표로 연결되지 않은 전달 레코드 {omitted}건은 사용하지 않았습니다")
    if not included:
        return DeliveryAdaptResult(None, ("서비스에 연결할 수 있는 전달 레코드가 없습니다",), tuple(warnings))

    normalized_records = [_base_record(record, key, index) for record, key, _, index in included]
    normalized_profiles = [
        _profile(record, key, mapping_row, data, peer_keys)
        for record, key, mapping_row, _ in included
    ]
    document = {
        "schema_version": "2.1",
        "dataset_version": data.get("dataset_version"),
        "records": normalized_records,
        "profiles": normalized_profiles,
        "thresholds": _thresholds(data),
    }
    return DeliveryAdaptResult(document, warnings=tuple(warnings))
