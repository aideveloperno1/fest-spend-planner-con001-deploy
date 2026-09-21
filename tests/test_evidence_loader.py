import json
import re
from pathlib import Path

import pytest
from evidence_helpers import (
    FIXTURE_DIR,
    VALID_FIXTURES,
    WARNING_FIXTURES,
    base_data,
    fixture_data,
    fixture_path,
)

from policy_signal_map.evidence.loader import (
    EvidenceError,
    find_record,
    has_real_records,
    is_real_evidence,
    load_evidence,
)
from policy_signal_map.evidence.schema import parse_evidence

INVALID_FIXTURES = {
    "invalid_status_value": '[FX-01 / 2026-02 / calculation_status] 허용되지 않는 값 "okay"',
    "invalid_applicability": '[FX-01 / applicability.R07 / status] 허용되지 않는 값 "maybe"',
    "missing_reason": "[FX-01 / applicability.R06 / reason] 사유(reason)가 비어 있습니다",
    "relation_broken": "[FX-01 / 2026-02 / amounts] 외국인+미상 금액이 전체 금액보다 큽니다",
    "negative_amount": "[FX-01 / 2026-01 / foreign_amount] 0 이상이어야 합니다",
    "decimal_amount": "[FX-01 / 2026-01 / foreign_amount] 원 단위 정수여야 합니다 (받은 형식: 소수)",
    "no_data_with_zero": "[FX-01 / 2026-02 / amounts] 자료 없음(no_data) 월의 금액은 null이어야 합니다",
    "month_omitted": "[FX-01 / months] 2026-03 월이 없습니다",
    "schema_version_unsupported": '[파일 / schema_version] 지원하지 않는 형식 버전 "1.0"',
    "mixed_data_kind": "[파일] 합성 자료와 실제 자료가 한 파일에 섞여 있습니다",
    "national_region_key_wrong": '[FX-01 / scope / region_key] 전국 범위의 region_key는 "ALL"여야 합니다',
    "profiles_version_mismatch": '[파일 / profiles] 형식 버전이 "2.0"인데 profiles가 들어 있습니다',
}


def parse(data: dict):
    return parse_evidence(json.loads(json.dumps(data)))


@pytest.mark.parametrize("name", VALID_FIXTURES)
def test_valid_fixtures_load(name):
    result = load_evidence(fixture_path(name))
    assert result.file.records
    assert result.warnings == ()


@pytest.mark.parametrize("name, expected", INVALID_FIXTURES.items())
def test_invalid_fixture_reports_expected_error(name, expected):
    with pytest.raises(EvidenceError) as caught:
        load_evidence(fixture_path(name))
    messages = caught.value.messages
    assert len(messages) == 1, messages
    assert messages[0].startswith(expected), messages[0]


def test_every_fixture_file_is_covered_by_a_test():
    names = {p.stem for p in FIXTURE_DIR.glob("*.json")}
    assert names == set(VALID_FIXTURES) | set(WARNING_FIXTURES) | set(INVALID_FIXTURES)


@pytest.mark.parametrize("name", WARNING_FIXTURES)
def test_warning_fixtures_load_with_a_reason(name):
    """프로필이 고장 나도 파일은 읽히고, 버린 자리는 경고로 남는다."""
    result = load_evidence(fixture_path(name))
    assert result.file.records
    assert result.warnings


def test_amount_errors_do_not_print_values():
    for name, value in (("decimal_amount", "800.5"), ("negative_amount", "800")):
        with pytest.raises(EvidenceError) as caught:
            load_evidence(fixture_path(name))
        text = caught.value.messages[0]
        # 위치의 연·월 숫자를 뺀 나머지에 금액이 나오면 안 된다
        assert value not in text.replace("2026-01", "")


def test_relation_error_does_not_print_values():
    with pytest.raises(EvidenceError) as caught:
        load_evidence(fixture_path("relation_broken"))
    assert not re.search(r"\d{3,}", caught.value.messages[0].replace("2026-02", ""))


def test_wrong_type_does_not_crash_relation_checks():
    data = base_data()
    data["records"][0]["months"][1]["total_amount"] = "12000"
    result = parse(data)
    assert result.file is None
    assert result.errors == ("[FX-01 / 2026-02 / total_amount] 원 단위 정수여야 합니다 (받은 형식: 글자)",)


def test_list_value_in_choice_field_does_not_crash():
    data = base_data()
    data["records"][0]["data_kind"] = ["synthetic"]
    data["schema_version"] = ["2.0"]
    result = parse(data)
    assert len(result.errors) == 2


def test_errors_are_collected_not_first_only():
    data = base_data()
    data["records"][0]["months"][0]["foreign_amount"] = 800.5
    data["records"][0]["applicability"]["R02"]["reason"] = ""
    result = parse(data)
    assert len(result.errors) == 2


def test_bool_is_not_accepted_as_amount():
    data = base_data()
    data["records"][0]["months"][0]["foreign_amount"] = True
    result = parse(data)
    assert result.errors == ("[FX-01 / 2026-01 / foreign_amount] 원 단위 정수여야 합니다 (받은 형식: 참/거짓)",)


def test_ok_month_with_zero_total_must_use_invalid_denominator():
    data = base_data()
    month = data["records"][0]["months"][1]
    month.update(foreign_amount=0, total_amount=0, unknown_amount=0)
    result = parse(data)
    assert any("invalid_denominator로 표시하세요" in e for e in result.errors)


def test_invalid_month_number():
    data = base_data()
    data["records"][0]["months"][0]["month"] = "2026-13"
    result = parse(data)
    assert len(result.errors) == 1
    assert "실제 월이어야 합니다" in result.errors[0]


def test_integer_share_is_accepted():
    data = base_data()
    data["records"][0]["months"][0]["foreign_share_pct"] = 8
    result = parse(data)
    assert result.file is not None
    assert result.warnings == ()


def test_share_mismatch_is_warning_not_error():
    data = base_data()
    data["records"][0]["months"][0]["foreign_share_pct"] = 8.01
    result = parse(data)
    assert result.file is not None
    assert result.warnings == (
        "[FX-01 / 2026-01 / foreign_share_pct] 파일의 비중이 금액으로 다시 계산한 값과 다릅니다 (계산에는 금액을 사용합니다)",
    )
    assert result.file.records[0].months[0].foreign_share_pct == 8.01


def test_unknown_fields_are_warnings():
    data = base_data()
    data["records"][0]["note"] = "설명"
    data["records"][0]["months"][0]["extra"] = 1
    data["quality_status"] = "old"
    result = parse(data)
    assert result.file is not None
    assert len(result.warnings) == 3


def test_underscore_top_level_is_ignored():
    data = base_data()
    assert "_case" in data
    assert parse(data).warnings == ()


def test_missing_months_must_be_listed_not_omitted_duplicates_and_order():
    data = base_data()
    months = data["records"][0]["months"]
    months.reverse()
    assert parse(data).errors == ("[FX-01 / months] 월 순서가 기간 순서와 다릅니다",)
    months.append(dict(months[0]))
    assert any("중복됩니다" in e for e in parse(data).errors)


def test_no_data_month_with_share_values_is_error():
    data = fixture_data("missing_month")
    data["records"][0]["months"][1]["foreign_share_pct"] = 0.0
    assert parse(data).errors == (
        "[FX-01 / 2026-02 / shares] 자료 없음(no_data) 월의 비중은 null이어야 합니다 (값이 있는 필드: foreign_share_pct)",
    )


def test_known_only_share_must_be_null_when_denominator_is_zero():
    data = fixture_data("unknown_equals_total")
    data["records"][0]["months"][1]["known_only_share_pct"] = 0.0
    assert parse(data).errors == ("[FX-01 / 2026-02 / known_only_share_pct] 미상 제외 분모가 0이면 null이어야 합니다",)


def test_invalid_input_without_reason_warns():
    data = base_data()
    data["records"][0]["months"][1].update(
        calculation_status="invalid_input",
        foreign_share_pct=None,
        known_only_share_pct=None,
        unknown_share_pct=None,
        warnings=[],
    )
    result = parse(data)
    assert result.file is not None
    assert result.warnings == ("[FX-01 / 2026-02 / warnings] 입력 오류 사유를 warnings에 적어 주세요",)


def test_missing_file_and_bad_json(tmp_path: Path):
    with pytest.raises(EvidenceError, match="찾을 수 없습니다"):
        load_evidence(tmp_path / "none.json")

    broken = tmp_path / "broken.json"
    broken.write_text('{"schema_version": "2.0",', encoding="utf-8")
    with pytest.raises(EvidenceError, match="JSON 형식 오류"):
        load_evidence(broken)

    nan = tmp_path / "nan.json"
    nan.write_text('{"a": NaN}', encoding="utf-8")
    with pytest.raises(EvidenceError, match="NaN"):
        load_evidence(nan)


def test_utf8_bom_is_accepted(tmp_path: Path):
    path = tmp_path / "bom.json"
    path.write_bytes(b"\xef\xbb\xbf" + fixture_path("same_direction").read_bytes())
    assert load_evidence(path).file.records


def test_find_record_does_not_fall_back_to_national():
    file = load_evidence(fixture_path("amount_up_share_down")).file
    assert find_record(file, "national", "ALL") is file.records[0]
    assert find_record(file, "sido", "DEMO-SIDO-A") is None


def test_is_real_evidence_uses_path_and_name():
    synthetic = load_evidence(fixture_path("same_direction")).file
    assert not has_real_records(synthetic)
    assert not is_real_evidence(Path("resources/evidence/review_evidence_demo_v1.json"), synthetic)
    assert is_real_evidence(Path("private/anything.json"), synthetic)
    assert is_real_evidence(Path("data/review_evidence_real_v1.json"), synthetic)
    assert is_real_evidence(Path("private/failed.json"), None)

    data = base_data()
    data["records"][0]["data_kind"] = "real"
    real = parse(data).file
    assert real is not None and is_real_evidence(Path("x.json"), real)


def test_fixtures_match_generator():
    import build_fixtures
    from _evidence_builder import to_json_text

    generated = build_fixtures.build_all()
    committed = {p.name for p in FIXTURE_DIR.glob("*.json")}
    assert set(generated) == committed
    for name, data in generated.items():
        assert (FIXTURE_DIR / name).read_text(encoding="utf-8") == to_json_text(data), name
