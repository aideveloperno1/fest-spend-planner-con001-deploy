"""로컬 LLM 호출 (Ollama·LM Studio 등 OpenAI 호환 서버).

표준 라이브러리만 쓴다. 실행 의존성을 늘리지 않기 위해서다 (6LLM참고의견계획.md 결정 ⑤).
요청 본문은 로그에 남기지 않는다. 남기면 사용자의 기획 내용이 로그 파일에 쌓인다.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

from .base import LLMError, Message

log = logging.getLogger(__name__)

# 모델의 "생각 과정" 출력을 끈다. Ollama의 OpenAI 호환 주소가 받는 값이다.
# 왜 끄는가 (C-0 측정, 2026-09-17): gemma4:26b-a4b-it-qat는 기본으로 생각 과정을 먼저 쓰느라
# 응답 한도(prompt.MAX_TOKENS=400)를 모두 써 버려 본문이 비었다(6번 모두). "none"이면 2~3초에 본문이 왔다.
# 생각 기능이 없는 exaone3.5도 이 값을 보내도 오류 없이 답한다(확인).
# 다른 서버(LM Studio 등)가 이 필드를 거부하면 None으로 바꾸면 요청에서 빠진다.
REASONING_EFFORT: str | None = "none"

# 받아 둔 모델 목록을 물을 때 기다릴 시간(초). 3단계 화면을 그리면서 부르므로 짧게 둔다.
# Ollama가 꺼져 있으면 연결 거부로 바로 돌아오고, 이 시간은 응답이 멈춘 경우에만 쓰인다.
LIST_MODELS_TIMEOUT_S = 2.0


def _same_model(name: str) -> str:
    # Ollama는 태그 없는 이름을 ":latest"로 돌려준다. 설정의 "모델"과 목록의 "모델:latest"를 같게 본다
    return name if ":" in name else f"{name}:latest"


def list_models(base_url: str, timeout_s: float = LIST_MODELS_TIMEOUT_S) -> frozenset[str] | None:
    """OpenAI 호환 서버에 받아 둔 모델 이름. 확인하지 못하면 None (없다고 단정하지 않는다)."""
    request = urllib.request.Request(f"{base_url.rstrip('/')}/models", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
        return frozenset(_same_model(item["id"]) for item in payload["data"])
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError, TypeError):
        log.info("로컬 LLM 모델 목록을 확인하지 못함")
        return None


def is_installed(model: str, installed: frozenset[str] | None) -> bool | None:
    """True·False, 목록을 확인하지 못했으면 None."""
    if installed is None:
        return None
    return _same_model(model) in installed


@dataclass
class LocalProvider:
    base_url: str
    model: str
    name: str = "local"

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def generate(self, messages: list[Message], *, max_tokens: int, timeout_s: float) -> str:
        fields: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "stream": False,
        }
        if REASONING_EFFORT is not None:
            fields["reasoning_effort"] = REASONING_EFFORT
        body = json.dumps(fields).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            log.warning("로컬 LLM 호출 실패: %s (%s)", type(exc).__name__, self.model)
            raise LLMError("로컬 LLM을 부르지 못했습니다") from exc
        except json.JSONDecodeError as exc:
            log.warning("로컬 LLM 응답을 읽지 못함: %s", self.model)
            raise LLMError("로컬 LLM 응답 형식이 올바르지 않습니다") from exc

        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            log.warning("로컬 LLM 응답에 내용이 없음: %s", self.model)
            raise LLMError("로컬 LLM 응답에 내용이 없습니다") from exc
