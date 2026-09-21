"""AI 모델 표시 이름·설명 (resources/llm/models.json).

고를 수 있는 모델 자체는 설정(PSM_LLM_MODELS)이 정한다. 이 파일은 화면에 보일 문구만 담는다.
문구를 코드에 두지 않는 것은 규칙 문구와 같은 원칙이다 (resources/README.md).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache

from ..paths import RESOURCES_DIR
from ..review.rules import FORBIDDEN_WORDS

CATALOG_PATH = RESOURCES_DIR / "llm" / "models.json"


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class ModelInfo:
    id: str
    label: str
    description: str


def parse_catalog(data: object) -> dict[str, ModelInfo]:
    if not isinstance(data, dict) or not isinstance(data.get("version"), str):
        raise CatalogError("모델 목록 파일에 version이 없습니다")
    items = data.get("models")
    if not isinstance(items, list):
        raise CatalogError("모델 목록 파일의 models는 목록이어야 합니다")

    result: dict[str, ModelInfo] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise CatalogError(f"models[{index}]는 객체여야 합니다")
        values = {key: item.get(key) for key in ("id", "label", "description")}
        for key, value in values.items():
            if not isinstance(value, str) or not value.strip():
                raise CatalogError(f"models[{index}].{key}가 비어 있습니다")
        if values["id"] in result:
            raise CatalogError(f'모델 "{values["id"]}"가 중복됩니다')
        # 모델 설명도 화면 문구이므로 판정 표현을 쓰지 않는다 (N10)
        for word in FORBIDDEN_WORDS:
            if word in values["label"] or word in values["description"]:
                raise CatalogError(f'모델 "{values["id"]}" 문구에 판정 표현 "{word}"가 있습니다')
        result[values["id"]] = ModelInfo(**values)  # type: ignore[arg-type]
    return result


@cache
def load_catalog() -> dict[str, ModelInfo]:
    return parse_catalog(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))


def model_info(model_id: str) -> ModelInfo:
    """목록 파일에 없는 모델은 이름을 그대로 쓰고 설명은 비운다."""
    return load_catalog().get(model_id) or ModelInfo(model_id, model_id, "")
