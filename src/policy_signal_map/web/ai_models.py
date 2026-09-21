"""3단계 AI 모델 선택 화면 데이터 (C-8).

고를 수 있는 모델은 설정(PSM_LLM_MODELS)이 정하고, 표시 문구는 resources/llm/models.json에서 읽는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings
from ..llm import google_ai
from ..llm.catalog import model_info
from .session import WorkState


@dataclass(frozen=True)
class ModelOption:
    id: str
    label: str
    description: str
    # True: API 키로 사용 가능 / False: 사용 불가 / None: Google에 확인하지 못함
    available: bool | None


def current_model(settings: Settings, state: WorkState) -> str:
    """담당자가 고른 모델. 설정이 바뀌어 목록에서 빠졌으면 기본 모델로 돌아간다."""
    if state.llm_model in settings.llm_models:
        return state.llm_model  # type: ignore[return-value]
    return settings.llm_model or ""


def available_models(settings: Settings) -> frozenset[str] | None:
    if settings.llm_provider != "google_ai" or not settings.llm_api_key:
        return None
    return google_ai.list_models(settings.llm_api_key)


def model_options(settings: Settings, available: frozenset[str] | None) -> list[ModelOption]:
    options = []
    for model_id in settings.llm_models:
        info = model_info(model_id)
        options.append(
            ModelOption(model_id, info.label, info.description, google_ai.is_available(model_id, available))
        )
    return options
