"""LLM 제공자 공통 계층. 실패해도 규칙 기반 흐름은 그대로 유지한다."""

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
    from .google_ai import GoogleAIProvider

    return GoogleAIProvider(
        api_key=settings.llm_api_key or "",
        model=model or settings.llm_model or "",
    )
