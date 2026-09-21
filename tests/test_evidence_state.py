import json
import shutil
from pathlib import Path

from evidence_helpers import base_data, fixture_path

from policy_signal_map.config import (
    LEGACY_DEMO_EVIDENCE_PATH as DEFAULT_EVIDENCE_PATH,
)
from policy_signal_map.web.evidence_state import load_evidence_state

CLOUD = {"PSM_LLM_PROVIDER": "cloud", "PSM_LLM_MODEL": "some-model", "PSM_LLM_API_KEY": "k"}


def test_default_state_loads_demo():
    state = load_evidence_state({})
    assert state.ok
    assert state.badge == "시연용 합성 수치 · demo-2.1-003"
    assert not state.is_real and not state.blocked


def test_invalid_file_is_error_state_not_exception():
    state = load_evidence_state({"PSM_EVIDENCE_PATH": str(fixture_path("relation_broken"))})
    assert not state.ok
    assert len(state.errors) == 1
    assert state.badge == "근거 파일 오류"


def test_missing_file_is_error_state(tmp_path: Path):
    state = load_evidence_state({"PSM_EVIDENCE_PATH": str(tmp_path / "없는파일.json")})
    assert not state.ok
    assert "찾을 수 없습니다" in state.errors[0]


def test_error_messages_do_not_expose_full_path(tmp_path: Path):
    missing = tmp_path / "secret_folder" / "review_evidence_x.json"
    state = load_evidence_state({"PSM_EVIDENCE_PATH": str(missing)})
    message = state.errors[0]
    assert "review_evidence_x.json" in message
    assert "secret_folder" not in message
    assert str(tmp_path) not in message


def test_invalid_settings_is_error_state():
    state = load_evidence_state({"PSM_LLM_PROVIDER": "gpt"})
    assert not state.ok
    assert state.result is None
    assert "gpt" in state.errors[0]


def test_real_with_cloud_is_blocked(tmp_path: Path):
    private_copy = tmp_path / "private" / "demo_copy.json"
    private_copy.parent.mkdir()
    shutil.copy(DEFAULT_EVIDENCE_PATH, private_copy)

    state = load_evidence_state({"PSM_EVIDENCE_PATH": str(private_copy), **CLOUD})
    assert state.is_real
    assert state.blocked
    assert not state.ok
    assert state.result is None

    assert load_evidence_state({"PSM_EVIDENCE_PATH": str(DEFAULT_EVIDENCE_PATH), **CLOUD}).ok


def test_real_badge(tmp_path: Path):
    data = base_data()
    data["records"][0]["data_kind"] = "real"
    path = tmp_path / "labelled.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    state = load_evidence_state({"PSM_EVIDENCE_PATH": str(path)})
    assert state.ok and state.is_real
    assert state.badge == "실제 분석 자료 · fixture-amount_up_share_down · 내부 검증용"


def test_unknown_data_kind_is_treated_as_real_even_when_file_is_rejected(tmp_path: Path):
    # 폴더·이름에 실제 자료 표시가 없고, data_kind가 약속과 달라 검증에 실패하는 파일
    data = base_data()
    data["records"][0]["data_kind"] = "actual_internal"
    path = tmp_path / "review_evidence.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    state = load_evidence_state({"PSM_EVIDENCE_PATH": str(path)})
    assert not state.ok and state.is_real

    blocked = load_evidence_state({"PSM_EVIDENCE_PATH": str(path), **CLOUD})
    assert blocked.blocked
    assert any("클라우드 LLM" in message for message in blocked.errors)


def test_rejected_synthetic_file_is_not_real(tmp_path: Path):
    data = base_data()
    data["records"][0]["months"][0]["month"] = "202601"
    path = tmp_path / "review_evidence.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    state = load_evidence_state({"PSM_EVIDENCE_PATH": str(path)})
    assert not state.ok and not state.is_real
