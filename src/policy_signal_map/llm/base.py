"""LLM 제공자 공통 계층 (6LLM참고의견계획.md 결정 ①·⑤).

로컬 LLM만 구현한다. 클라우드는 여기 한 곳만 고치면 붙도록 자리를 남겨 둔다.
실패는 예외로 올리고, 화면은 규칙 기반 흐름을 그대로 보여 준다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..config import Settings


class LLMError(Exception):
    """호출 실패. 화면에는 사유를 적지 않고 안내 문구만 보여 준다."""


@dataclass(frozen=True)
class Message:
    role: str  # "system" 또는 "user"
    content: str


class LLMProvider(Protocol):
    name: str

    def generate(self, messages: list[Message], *, max_tokens: int, timeout_s: float) -> str: ...


@dataclass
class FakeProvider:
    """테스트와 화면 확인용. 실제 호출을 하지 않는다."""

    reply: str = ""
    name: str = "fake"
    error: Exception | None = None
    calls: list[list[Message]] = field(default_factory=list)

    def generate(self, messages: list[Message], *, max_tokens: int, timeout_s: float) -> str:
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        return self.reply


def get_provider(settings: Settings, model: str | None = None) -> LLMProvider | None:
    """설정에 맞는 제공자. 사용하지 않으면 None.

    model을 주면 그 모델로 부른다(담당자가 3단계에서 고른 모델). 설정 목록 밖의 모델은 부르지 않는다.
    화면 요청값을 그대로 넘겨 PC에 받아 둔 다른 모델을 부르는 일을 막기 위해서다.
    """
    if settings.llm_provider == "none":
        return None
    if model is not None and model not in settings.llm_models:
        raise LLMError("선택할 수 없는 모델입니다")
    if settings.llm_provider == "cloud":
        # 확장 지점: cloud.py를 만들고 여기서 돌려주면 된다 (6LLM참고의견계획.md 결정 ①)
        raise LLMError(
            "클라우드 LLM은 아직 구현하지 않았습니다. PSM_LLM_PROVIDER를 none 또는 local로 설정하세요."
        )

    from .local import LocalProvider

    return LocalProvider(
        base_url=settings.llm_base_url or "",
        model=model or settings.llm_model or "",
    )
