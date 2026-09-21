from pathlib import Path

import pytest

from policy_signal_map.config import (
    DEFAULT_EVIDENCE_PATH,
    DEFAULT_REGION_MAPPING_PATH,
    GOOGLE_AI_MODELS,
    SettingsError,
    load_settings,
)


GOOGLE = {"PSM_LLM_PROVIDER": "google_ai", "GEMINI_API_KEY": "test-key"}


def test_defaults_use_public_evidence_and_no_llm():
    settings = load_settings({})
    assert settings.evidence_path == DEFAULT_EVIDENCE_PATH
    assert settings.region_mapping_path == DEFAULT_REGION_MAPPING_PATH
    assert settings.llm_provider == "none"
    assert settings.llm_models == ()


def test_empty_values_are_treated_as_unset():
    settings = load_settings({"PSM_EVIDENCE_PATH": "  ", "PSM_LLM_PROVIDER": ""})
    assert settings.evidence_path == DEFAULT_EVIDENCE_PATH
    assert settings.llm_provider == "none"


def test_paths_can_be_overridden():
    settings = load_settings(
        {"PSM_EVIDENCE_PATH": "data/demo.json", "PSM_REGION_MAPPING_PATH": "data/map.json"}
    )
    assert settings.evidence_path == Path("data/demo.json")
    assert settings.region_mapping_path == Path("data/map.json")


def test_unknown_and_removed_providers_are_rejected():
    for provider in ("gpt", "local", "cloud"):
        with pytest.raises(SettingsError, match=provider):
            load_settings({"PSM_LLM_PROVIDER": provider})


def test_google_ai_requires_server_key():
    with pytest.raises(SettingsError, match="GEMINI_API_KEY"):
        load_settings({"PSM_LLM_PROVIDER": "google_ai"})


def test_google_defaults_to_the_fixed_model_order():
    settings = load_settings(GOOGLE)
    assert settings.llm_models == GOOGLE_AI_MODELS
    assert settings.llm_model == "gemini-3.8-flash"
    assert settings.llm_models[-1] == "gemma-4-31b-it"
    assert "gemini-3.5-flash-lite" not in settings.llm_models


def test_api_key_not_in_repr():
    settings = load_settings({**GOOGLE, "GEMINI_API_KEY": "secret-key-123"})
    assert "secret-key-123" not in repr(settings)


def test_model_list_keeps_order_and_drops_blanks_and_duplicates():
    settings = load_settings({**GOOGLE, "PSM_LLM_MODELS": " b , a,,b "})
    assert settings.llm_models == ("b", "a")
    assert settings.llm_model == "b"


def test_default_model_can_be_any_model_in_the_list():
    settings = load_settings({**GOOGLE, "PSM_LLM_MODELS": "a,b", "PSM_LLM_MODEL": "b"})
    assert settings.llm_model == "b"


def test_default_model_outside_the_list_is_rejected():
    with pytest.raises(SettingsError, match="PSM_LLM_MODELS"):
        load_settings({**GOOGLE, "PSM_LLM_MODELS": "a,b", "PSM_LLM_MODEL": "c"})


def test_timeout_default_and_override():
    assert load_settings({}).llm_timeout_s == 45.0
    assert load_settings({"PSM_LLM_TIMEOUT_S": "5.5"}).llm_timeout_s == 5.5


def test_bad_timeout_is_rejected():
    for value in ("빠르게", "0", "-3"):
        with pytest.raises(SettingsError):
            load_settings({"PSM_LLM_TIMEOUT_S": value})
