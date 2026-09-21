"""분석팀 전달본 2.1과 서비스 내부 2.1의 경계 회귀 시험."""

import json
from copy import deepcopy
from pathlib import Path

from policy_signal_map.evidence.delivery_v21 import PEER_METHOD_ID
from policy_signal_map.evidence.loader import load_evidence
from policy_signal_map.plan.models import sample_plan
from policy_signal_map.review.industry_checks import run_r08
from policy_signal_map.review.rules import get_rule


def month(label: str = "2026-01") -> dict:
    return {
        "month": label,
        "calculation_status": "ok",
        "foreign_amount": 10,
        "total_amount": 100,
        "unknown_amount": 0,
        "transaction_count": 2,
        "foreign_share_pct": 10.0,
        "known_only_share_pct": 10.0,
        "unknown_share_pct": 0.0,
        "warnings": [],
        "season_index": 1.3,
        "season_flag": True,
    }


def record(key: str, *, national: bool = False, data_kind: str = "synthetic") -> dict:
    rank = None if national else {
        "total_amount": {"percentile": 40.0},
        "foreign_share_pct": {"percentile": 10.0},
        "unknown_share_pct": {"percentile": 30.0},
        "industry_share_pct": {"업종 하나": {"percentile": 10.0}, "업종 둘": {"percentile": 90.0}},
        "age_share_pct": {"1": {"percentile": 10.0}, "2": {"percentile": 90.0}},
        "industry_age_share_percentile": {
            "업종 하나": {"1": 10.0, "2": 90.0},
            "업종 둘": {"1": 90.0, "2": 10.0},
        },
    }
    return {
        "evidence_id": f"source-{key}",
        "data_kind": data_kind,
        "scope": {
            "geographic_scope": "national" if national else "sigungu",
            "region_key": key,
            "population": "foreign_code_3",
            "industry_scope": "all_provided",
            "age_scope": "all",
            "period_start": "2026-01",
            "period_end": "2026-01",
        },
        "region_basis": "merchant_location_assumed",
        "applicability": {
            "R07": {"status": "allowed", "reason": "시험"},
            "R06": {"status": "allowed", "reason": "시험"},
            **({} if national else {"R02": {"status": "allowed", "reason": "시험"}}),
            "R11": {"status": "allowed", "reason": "전달본의 추가 규칙"},
        },
        "amount_unit": "KRW",
        "months": [month()],
        "limitations": ["합성 시험 자료"],
        "profile": {
            "industry_share_pct": {"업종 하나": 20.0, "업종 둘": 80.0},
            "age_share_pct": {"1": 25.0, "2": 75.0},
            "industry_age_share_pct": {
                "업종 하나": {"1": 30.0, "2": 70.0},
                "업종 둘": {"1": 20.0, "2": 80.0},
            },
        },
        "foreign_profile": {"foreign_share_pct": 10.0, "type": "관광형", "type_status": "shown"},
        "season_summary": {"threshold": 1.25},
        "national_rank": rank,
        "size_flag": {"is_small": False, "unknown_share_pct": 0.0},
        "derived_flags": {"no_payment_industries": []},
        "external": None if national else {
            "population_total": 1000,
            "population_base_date": "2026-08-31",
            "registered_foreign_by_month": {"2026-01": 10},
            # 이 파생값들은 서비스가 가져오면 안 된다.
            "payments_per_resident_krw_6m": 999,
            "foreign_payment_per_registered_foreign_krw_6m": 999,
        },
        "peers": [] if national else [{"region_key": "DEMO-B", "distance": 0.5}],
    }


def delivery() -> dict:
    distribution_item = {"n": 2, "p10": 1.0}
    return {
        "schema_version": "2.1",
        "dataset_version": "fixture-003",
        "data_kind": "synthetic",
        "industry_codes": {"I1": "업종 하나", "I2": "업종 둘"},
        "age_labels": {"1": "20대 이하", "2": "30대 이상"},
        "national_distribution": {
            "total_amount": distribution_item,
            "foreign_share_pct": distribution_item,
            "unknown_share_pct": distribution_item,
            "industry_share_pct": {"업종 하나": distribution_item, "업종 둘": distribution_item},
            "age_share_pct": {"1": distribution_item, "2": distribution_item},
            "industry_age_share_pct": {
                "업종 하나": {"1": distribution_item, "2": distribution_item},
                "업종 둘": {"1": distribution_item, "2": distribution_item},
            },
        },
        "thresholds": {
            "R02_R08_low_percentile": 20.0,
            "R04_season_index_min": 1.1,
            "R04_season_index_min_small": 1.2,
            "R11_visitor_to_resident_ratio": 0.5,
            "R12_low_foreign_share_percentile": 20.0,
            "derived_cutoffs": {"do_not_import": 999},
        },
        "display_policy": {"R08": {"level": "reference", "reason": "시험"}},
        "external_sources": {
            "population": {"source": "합성 인구", "base_date": "2026-08-31"},
            "registered_foreign": {"source": "합성 등록외국인", "period": "2026-01"},
        },
        "records": [record("DEMO-A"), record("DEMO-B"), record("ALL", national=True)],
    }


def write(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_전달본을_내부_프로필과_운영기준으로_변환한다(tmp_path: Path):
    result = load_evidence(write(tmp_path / "delivery.json", delivery()))

    assert len(result.file.records) == 3
    # 전국 레코드는 전달 계약상 R02가 없어도 읽힌다.
    assert "R02" not in result.file.records[-1].applicability
    assert set(result.thresholds.rules) == {"R02", "R04", "R08", "R11", "R12"}
    assert "derived_cutoffs" not in result.thresholds.rules

    profile = result.profile("DEMO-A")
    assert profile.region_basis == "unconfirmed"
    assert profile.season_threshold == 1.25
    assert profile.foreign_type == "관광형"
    assert profile.reference_rules == ("R08",)
    assert profile.peer_method == PEER_METHOD_ID
    assert profile.peers[0].region_key == "DEMO-B"
    assert profile.external.population.count == 1000
    assert profile.external.registered_foreigners_monthly.values[0].count == 10
    # 인당 결제액 파생값은 내부 모델에 없다.
    assert not hasattr(profile.external, "payments_per_resident_krw_6m")

    plan = sample_plan()
    plan.usage_industries = ["I1"]
    plan.target_ages = ["1"]
    outcome = run_r08(get_rule("R08"), plan, profile, result.thresholds)
    assert outcome.kind == "question"
    assert outcome.display_level == "reference"


def test_실자료는_대응표에_있는_지역만_연결한다(tmp_path: Path):
    data = delivery()
    data["data_kind"] = "real"
    for row in data["records"]:
        row["data_kind"] = "real"
    data["records"][0]["scope"]["region_key"] = "source-a"
    data["records"][1]["scope"]["region_key"] = "source-b"
    data["records"][0]["peers"] = [{"region_key": "source-b", "distance": 0.5}]
    mapping = {
        "rows": [
            {"source_key": "source-a", "region_code10": "1111000000", "link_status": "linked"},
            {"source_key": "source-b", "region_code10": "1114000000", "link_status": "composed"},
        ],
        "counts": {"linked": 1, "composed": 1, "unlinked": 0},
    }
    mapping_path = write(tmp_path / "mapping.json", mapping)
    result = load_evidence(write(tmp_path / "real.json", data), mapping_path)

    assert {row.scope.region_key for row in result.file.records} == {"1111000000", "1114000000", "ALL"}
    assert result.profile("1111000000").peers[0].region_key == "1114000000"
    assert any("행정구역 개편" in line for line in result.profile("1114000000").limitations)


def test_실자료_대응표가_없으면_지역을_추정하지_않는다(tmp_path: Path):
    data = deepcopy(delivery())
    data["data_kind"] = "real"
    for row in data["records"]:
        row["data_kind"] = "real"
    result = load_evidence(write(tmp_path / "real.json", data))

    assert [row.scope.region_key for row in result.file.records] == ["ALL"]
    assert [profile.region_key for profile in result.profiles] == ["ALL"]
    assert any("전국 레코드만" in warning for warning in result.warnings)
