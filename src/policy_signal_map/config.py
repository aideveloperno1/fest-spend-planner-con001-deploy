"""환경변수 설정. 앱 시작 시 한 번 읽어 변경 불가 객체로 보관한다.

실행 예: uv run --env-file .env policy-signal-map
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

from .paths import PROJECT_ROOT, RESOURCES_DIR

LEGACY_DEMO_EVIDENCE_PATH = RESOURCES_DIR / "evidence" / "review_evidence_demo_v1.json"
DEFAULT_EVIDENCE_PATH = RESOURCES_DIR / "evidence" / "review_evidence_hierarchy_v1.json"
DEFAULT_REGION_MAPPING_PATH = PROJECT_ROOT / "private" / "region_mapping.json"

GOOGLE_AI_MODELS = (
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-2.5-pro",
    "gemma-4-31b-it",
)
LLM_PROVIDERS = ("none", "google_ai")
LlmProvider = Literal["none", "google_ai"]


class SettingsError(Exception):
    pass


# Google AI Studio API가 이 시간 안에 응답하지 않으면 AI 영역만 실패로 표시한다.
# 자동 재시도는 같은 요청으로 무료 할당량을 더 쓸 수 있어 하지 않는다.
DEFAULT_LLM_TIMEOUT_S = 45.0


@dataclass(frozen=True)
class Settings:
    evidence_path: Path
    region_mapping_path: Path
    llm_provider: LlmProvider
    # 기본 모델. 담당자가 3단계에서 다른 모델을 고르기 전까지 쓴다
    llm_model: str | None
    # 로그·오류 출력에 키가 찍히지 않게 repr에서 뺀다
    llm_api_key: str | None = field(repr=False)
    llm_timeout_s: float = DEFAULT_LLM_TIMEOUT_S
    # 담당자가 고를 수 있는 모델 목록 (기본 모델 포함). 이 목록 밖의 모델은 부르지 않는다
    llm_models: tuple[str, ...] = ()


def _value(environ: Mapping[str, str], name: str) -> str | None:
    # 빈 문자열은 설정하지 않은 것으로 본다 (.env.example을 그대로 복사한 경우)
    raw = environ.get(name, "").strip()
    return raw or None


def _timeout(raw: str | None) -> float:
    if raw is None:
        return DEFAULT_LLM_TIMEOUT_S
    try:
        seconds = float(raw)
    except ValueError:
        raise SettingsError(f'PSM_LLM_TIMEOUT_S 값 "{raw}"는 숫자가 아닙니다.') from None
    if seconds <= 0:
        raise SettingsError("PSM_LLM_TIMEOUT_S는 0보다 커야 합니다.")
    return seconds


def _model_list(raw: str | None) -> tuple[str, ...]:
    """쉼표 목록에서 빈 칸과 중복을 빼고 적은 순서를 지킨다."""
    if raw is None:
        return ()
    names = [name.strip() for name in raw.split(",")]
    return tuple(dict.fromkeys(name for name in names if name))


def load_settings(environ: Mapping[str, str] = os.environ) -> Settings:
    provider = _value(environ, "PSM_LLM_PROVIDER") or "none"
    if provider not in LLM_PROVIDERS:
        raise SettingsError(
            f'PSM_LLM_PROVIDER 값 "{provider}"는 사용할 수 없습니다. '
            "none, google_ai 중 하나로 설정하세요."
        )

    models = _model_list(_value(environ, "PSM_LLM_MODELS"))
    if provider == "google_ai" and not models:
        models = GOOGLE_AI_MODELS
    model = _value(environ, "PSM_LLM_MODEL") or (models[0] if models else None)
    if model and models and model not in models:
        raise SettingsError(f'PSM_LLM_MODEL "{model}"이 PSM_LLM_MODELS 목록에 없습니다.')
    if model and not models:
        models = (model,)

    settings = Settings(
        evidence_path=Path(_value(environ, "PSM_EVIDENCE_PATH") or DEFAULT_EVIDENCE_PATH),
        region_mapping_path=Path(
            _value(environ, "PSM_REGION_MAPPING_PATH") or DEFAULT_REGION_MAPPING_PATH
        ),
        llm_provider=cast(LlmProvider, provider),
        llm_model=model,
        llm_api_key=_value(environ, "GEMINI_API_KEY"),
        llm_timeout_s=_timeout(_value(environ, "PSM_LLM_TIMEOUT_S")),
        llm_models=models,
    )

    missing: list[str] = []
    if settings.llm_provider == "google_ai" and not settings.llm_model:
        missing.append("PSM_LLM_MODEL")
    if settings.llm_provider == "google_ai" and not settings.llm_api_key:
        missing.append("GEMINI_API_KEY")
    if missing:
        raise SettingsError(
            f"PSM_LLM_PROVIDER={settings.llm_provider}에는 다음 설정이 필요합니다: "
            f"{', '.join(missing)}"
        )
    return settings
