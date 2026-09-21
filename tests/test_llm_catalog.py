"""AI 모델 표시 이름·설명 (C-8-1)."""

import pytest

from policy_signal_map.llm.catalog import CatalogError, load_catalog, model_info, parse_catalog


def test_catalog_file_loads():
    catalog = load_catalog()
    assert tuple(catalog) == (
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-2.5-pro",
        "gemma-4-31b-it",
    )
    assert "gemini-3.5-flash-lite" not in catalog
    assert all(info.label and info.description for info in catalog.values())


def test_unknown_model_uses_its_name():
    info = model_info("unknown-model:1b")
    assert (info.label, info.description) == ("unknown-model:1b", "")


def test_duplicate_or_empty_entries_are_rejected():
    base = {"id": "a", "label": "A", "description": "설명"}
    with pytest.raises(CatalogError, match="중복"):
        parse_catalog({"version": "1.0", "models": [base, base]})
    with pytest.raises(CatalogError, match="label"):
        parse_catalog({"version": "1.0", "models": [{**base, "label": " "}]})


def test_judgment_words_are_rejected():
    with pytest.raises(CatalogError, match="판정 표현"):
        parse_catalog({"version": "1.0", "models": [{"id": "a", "label": "A", "description": "오류가 적은 모델"}]})
