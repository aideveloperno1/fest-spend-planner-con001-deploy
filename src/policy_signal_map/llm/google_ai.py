"""Google AI Studio의 Gemini API를 호출하는 단일 요청 제공자."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from functools import cache
from typing import Any
from urllib.parse import quote

from .base import LLMError, Message

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
LIST_MODELS_TIMEOUT_S = 3.0

# 모델마다 Google API가 받는 사고 제어 방식이 다르다.
THINKING_CONFIG: dict[str, dict[str, str | int]] = {
    "gemini-3.8-flash": {"thinkingLevel": "low"},
    "gemini-3.6-flash": {"thinkingLevel": "low"},
    "gemini-2.5-pro": {"thinkingBudget": 128},
    "gemma-4-31b-it": {"thinkingLevel": "minimal"},
}


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }


def _read_json(response: Any) -> dict[str, Any]:
    try:
        payload = json.loads(response.read().decode("utf-8"))
    except (UnicodeDecodeError, ValueError, AttributeError):
        raise LLMError("Google AI가 해석할 수 없는 응답을 반환했습니다") from None
    if not isinstance(payload, dict):
        raise LLMError("Google AI가 해석할 수 없는 응답을 반환했습니다")
    return payload


def _request_error(exc: BaseException) -> LLMError:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (401, 403):
            return LLMError("Google AI 인증에 실패했습니다")
        if exc.code == 429:
            return LLMError("Google AI 사용 가능량을 초과했습니다")
        if exc.code == 404:
            return LLMError("선택한 Google AI 모델을 사용할 수 없습니다")
        return LLMError("Google AI 요청에 실패했습니다")
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return LLMError("Google AI 응답 시간이 초과되었습니다")
    return LLMError("Google AI에 연결하지 못했습니다")


@dataclass(frozen=True)
class GoogleAIProvider:
    api_key: str = field(repr=False)
    model: str
    name: str = field(default="google_ai", init=False)

    def generate(self, messages: list[Message], *, max_tokens: int, timeout_s: float) -> str:
        system_text = "\n\n".join(message.content for message in messages if message.role == "system")
        contents = [
            {
                "role": "model" if message.role == "assistant" else "user",
                "parts": [{"text": message.content}],
            }
            for message in messages
            if message.role != "system"
        ]
        if not contents:
            raise LLMError("Google AI에 보낼 사용자 요청이 없습니다")

        generation_config: dict[str, Any] = {"maxOutputTokens": max_tokens}
        thinking = THINKING_CONFIG.get(self.model)
        if thinking is not None:
            generation_config["thinkingConfig"] = thinking

        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_text:
            body["systemInstruction"] = {"parts": [{"text": system_text}]}

        model = quote(self.model, safe="")
        request = urllib.request.Request(
            f"{API_ROOT}/models/{model}:generateContent",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=_headers(self.api_key),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                payload = _read_json(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise _request_error(exc) from None

        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise LLMError("Google AI가 표시할 답변을 반환하지 않았습니다")
        content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            raise LLMError("Google AI가 표시할 답변을 반환하지 않았습니다")
        text = "".join(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and not part.get("thought") and isinstance(part.get("text"), str)
        ).strip()
        if not text:
            raise LLMError("Google AI가 표시할 답변을 반환하지 않았습니다")
        return text


@cache
def list_models(api_key: str, timeout_s: float = LIST_MODELS_TIMEOUT_S) -> frozenset[str] | None:
    """이 API 키에서 generateContent를 지원하는 모델 목록. 실패하면 알 수 없음(None)."""
    request = urllib.request.Request(
        f"{API_ROOT}/models?pageSize=1000",
        headers=_headers(api_key),
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = _read_json(response)
    except (LLMError, urllib.error.HTTPError, urllib.error.URLError, TimeoutError, socket.timeout, OSError):
        return None

    rows = payload.get("models")
    if not isinstance(rows, list):
        return None
    available: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        methods = row.get("supportedGenerationMethods")
        name = row.get("baseModelId") or row.get("name")
        if not isinstance(methods, list) or "generateContent" not in methods or not isinstance(name, str):
            continue
        available.add(name.removeprefix("models/"))
    return frozenset(available)


def is_available(model: str, available: frozenset[str] | None) -> bool | None:
    if available is None:
        return None
    return model in available
