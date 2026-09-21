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
DEFAULT_EVIDENCE_PATH = (
    RESOURCES_DIR / "evidence" / "review_evidence_public_v2.1.json"
)
DEFAULT_REGION_MAPPING_PATH = PROJECT_ROOT / "private" / "region_mapping.json"
LLM_PROVIDERS = ("none", "cloud", "local")

LlmProvider = Literal["none", "cloud", "local"]


class SettingsError(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# AI 참고 의견 응답을 기다리는 최대 시간(초). 넘기면 "AI 의견을 불러오지 못했습니다"를 보여 준다.
#
# 120초로 둔 이유: 모델을 바꾸면 Ollama가 모델 파일을 메모리에 새로 올린다 (C-0 측정, 2026-09-17).
#   - exaone3.5:7.8b(4.8GB) 전환 후 첫 응답 약 40초, gemma4:26b-a4b-it-qat(15GB)는 PC를 켠 뒤 처음 부를 때 약 74초
#   - 같은 모델을 이어 쓰면 2~10초
#   처음에는 60초로 정했으나 Gemma 첫 호출이 넘을 수 있어 사용자 결정으로 120초로 늘렸다 (2026-09-17).
#   의견 요청은 3단계 화면과 따로 가므로(/step/3/opinions) 오래 기다려도 검토 질문 화면은 막히지 않는다.
#
# 바꾸는 방법 (둘 중 하나):
#   1) 코드 수정 없이: .env에 PSM_LLM_TIMEOUT_S=90 처럼 적고 서버를 다시 시작한다 (이 값보다 우선)
#   2) 기본값 자체를 바꾸려면: 아래 숫자만 고친다. tests/test_llm_provider.py는 이 상수를 참조하므로 따로 고칠 필요 없다
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_LLM_TIMEOUT_S = 120.0


@dataclass(frozen=True)
class Settings:
    evidence_path: Path
    region_mapping_path: Path
    llm_provider: LlmProvider
    llm_base_url: str | None
    # 기본 모델. 담당자가 3단계에서 다른 모델을 고르기 전까지 쓴다
    llm_model: str | None
    # 로그·오류 출력에 키가 찍히지 않게 repr에서 뺀다
    llm_api_key: str | None = field(repr=False)
    # 위 DEFAULT_LLM_TIMEOUT_S 설명 참고
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
    """PSM_LLM_MODELS="a,b,c" → ("a", "b", "c"). 빈 칸과 중복은 빼고 적은 순서를 지킨다 (화면 선택지 순서)."""
    if raw is None:
        return ()
    names = [name.strip() for name in raw.split(",")]
    return tuple(dict.fromkeys(name for name in names if name))


def load_settings(environ: Mapping[str, str] = os.environ) -> Settings:
    provider = _value(environ, "PSM_LLM_PROVIDER") or "none"
    if provider not in LLM_PROVIDERS:
        raise SettingsError(
            f'PSM_LLM_PROVIDER 값 "{provider}"는 사용할 수 없습니다. none, cloud, local 중 하나로 설정하세요.'
        )

    models = _model_list(_value(environ, "PSM_LLM_MODELS"))
    # 기본 모델을 따로 적지 않으면 목록의 첫 모델을 쓴다
    model = _value(environ, "PSM_LLM_MODEL") or (models[0] if models else None)
    if model and models and model not in models:
        raise SettingsError(f'PSM_LLM_MODEL "{model}"이 PSM_LLM_MODELS 목록에 없습니다.')
    if model and not models:
        # 목록을 적지 않은 예전 설정: 기본 모델 하나만 쓸 수 있다 (선택 칸이 나오지 않음)
        models = (model,)

    settings = Settings(
        evidence_path=Path(_value(environ, "PSM_EVIDENCE_PATH") or DEFAULT_EVIDENCE_PATH),
        region_mapping_path=Path(_value(environ, "PSM_REGION_MAPPING_PATH") or DEFAULT_REGION_MAPPING_PATH),
        llm_provider=cast(LlmProvider, provider),
        llm_base_url=_value(environ, "PSM_LLM_BASE_URL"),
        llm_model=model,
        llm_api_key=_value(environ, "PSM_LLM_API_KEY"),
        llm_timeout_s=_timeout(_value(environ, "PSM_LLM_TIMEOUT_S")),
        llm_models=models,
    )

    missing: list[str] = []
    if settings.llm_provider in ("cloud", "local") and not settings.llm_model:
        missing.append("PSM_LLM_MODEL")
    if settings.llm_provider == "cloud" and not settings.llm_api_key:
        missing.append("PSM_LLM_API_KEY")
    if settings.llm_provider == "local" and not settings.llm_base_url:
        missing.append("PSM_LLM_BASE_URL")
    if missing:
        raise SettingsError(
            f"PSM_LLM_PROVIDER={settings.llm_provider}에는 다음 설정이 필요합니다: {', '.join(missing)}"
        )
    return settings


def check_llm_data_combination(settings: Settings, is_real_evidence: bool) -> None:
    """실제 분석 근거와 클라우드 LLM의 조합을 막는다 (checks.md LLM 전달 자료).

    is_real_evidence는 evidence.loader.is_real_evidence()로 판단한 값을 넘긴다.
    로컬 LLM + 실제 자료는 허용한다 (사용자 결정 2026-09-17, checks.md 1장).
    로컬 모델은 PC 밖으로 보내지 않고, 모델에는 수치 없이 규칙 결과와 상황 설명만 넘기기 때문이다 (llm/prompt.py).
    """
    if is_real_evidence and settings.llm_provider == "cloud":
        raise SettingsError(
            "실제 분석 근거 파일과 클라우드 LLM은 함께 사용할 수 없습니다. "
            "PSM_LLM_PROVIDER를 none으로 바꾸거나 합성 근거 파일을 사용하세요."
        )
