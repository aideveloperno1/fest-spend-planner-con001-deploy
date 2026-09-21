"""Google AI 제공자 계층. 실제 외부 API는 부르지 않는다."""

import json
import urllib.error

import pytest

from policy_signal_map.config import load_settings
from policy_signal_map.llm.base import FakeProvider, LLMError, Message, get_provider
from policy_signal_map.llm.google_ai import GoogleAIProvider, is_available, list_models


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def provider(model: str = "gemini-3.8-flash") -> GoogleAIProvider:
    return GoogleAIProvider(api_key="secret-test-key", model=model)


def response(text: str = "확인할 점") -> bytes:
    return json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]}).encode()


def test_no_provider_by_default():
    assert get_provider(load_settings({})) is None


def test_google_provider_is_built_from_settings():
    settings = load_settings({"PSM_LLM_PROVIDER": "google_ai", "GEMINI_API_KEY": "k"})
    built = get_provider(settings)
    assert built is not None
    assert built.name == "google_ai"
    assert built.model == "gemini-3.8-flash"


def test_provider_uses_chosen_model_and_refuses_outside_list():
    settings = load_settings(
        {
            "PSM_LLM_PROVIDER": "google_ai",
            "GEMINI_API_KEY": "k",
            "PSM_LLM_MODELS": "gemini-3.8-flash,gemma-4-31b-it",
        }
    )
    assert get_provider(settings, "gemma-4-31b-it").model == "gemma-4-31b-it"
    with pytest.raises(LLMError, match="선택할 수 없는 모델"):
        get_provider(settings, "gemini-3.5-flash-lite")


@pytest.mark.parametrize(
    ("model", "thinking"),
    [
        ("gemini-3.8-flash", {"thinkingLevel": "low"}),
        ("gemini-3.6-flash", {"thinkingLevel": "low"}),
        ("gemini-2.5-pro", {"thinkingBudget": 128}),
        ("gemma-4-31b-it", {"thinkingLevel": "minimal"}),
    ],
)
def test_call_uses_model_specific_google_shape(monkeypatch, model, thinking):
    sent: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        sent["url"] = request.full_url
        sent["timeout"] = timeout
        sent["headers"] = dict(request.header_items())
        sent["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(response())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    text = provider(model).generate(
        [Message("system", "보조자"), Message("user", "질문")],
        max_tokens=2048,
        timeout_s=7,
    )

    assert text == "확인할 점"
    assert sent["url"] == f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    assert "secret-test-key" not in str(sent["url"])
    assert sent["timeout"] == 7
    body = sent["body"]
    assert body["systemInstruction"] == {"parts": [{"text": "보조자"}]}
    assert body["contents"] == [{"role": "user", "parts": [{"text": "질문"}]}]
    assert body["generationConfig"] == {
        "maxOutputTokens": 2048,
        "thinkingConfig": thinking,
    }
    assert not {"temperature", "topP", "topK"} & body["generationConfig"].keys()
    assert "secret-test-key" not in json.dumps(body)
    assert dict(sent["headers"])["X-goog-api-key"] == "secret-test-key"


def test_response_ignores_thought_parts(monkeypatch):
    payload = {
        "candidates": [
            {"content": {"parts": [{"text": "내부 사고", "thought": True}, {"text": "표시 답변"}]}}
        ]
    }
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda request, timeout: FakeResponse(json.dumps(payload).encode())
    )
    assert provider().generate([Message("user", "질문")], max_tokens=100, timeout_s=1) == "표시 답변"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500])
def test_http_failures_become_safe_llm_errors(monkeypatch, status):
    def fail(request, timeout):
        raise urllib.error.HTTPError(request.full_url, status, "detail", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(LLMError) as exc:
        provider().generate([Message("user", "질문")], max_tokens=100, timeout_s=1)
    assert "secret-test-key" not in str(exc.value)
    assert "generativelanguage" not in str(exc.value)


def test_unexpected_response_becomes_llm_error(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse(b'{"candidates": []}'))
    with pytest.raises(LLMError):
        provider().generate([Message("user", "질문")], max_tokens=100, timeout_s=1)


def test_list_models_filters_generate_content(monkeypatch):
    payload = {
        "models": [
            {
                "name": "models/gemini-3.8-flash",
                "baseModelId": "gemini-3.8-flash",
                "supportedGenerationMethods": ["generateContent"],
            },
            {"name": "models/embed", "supportedGenerationMethods": ["embedContent"]},
        ]
    }
    sent: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        sent["url"] = request.full_url
        sent["headers"] = dict(request.header_items())
        return FakeResponse(json.dumps(payload).encode())

    list_models.cache_clear()
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    available = list_models("model-list-key")
    assert sent["url"].endswith("/v1beta/models?pageSize=1000")
    assert "model-list-key" not in str(sent["url"])
    assert dict(sent["headers"])["X-goog-api-key"] == "model-list-key"
    assert available == frozenset({"gemini-3.8-flash"})
    assert is_available("gemini-3.8-flash", available) is True
    assert is_available("gemma-4-31b-it", available) is False
    assert is_available("anything", None) is None


def test_list_models_failure_is_unknown(monkeypatch):
    def fail(request, timeout):
        raise urllib.error.URLError("연결 거부")

    list_models.cache_clear()
    monkeypatch.setattr("urllib.request.urlopen", fail)
    assert list_models("failing-key") is None


def test_fake_provider_records_calls_and_can_fail():
    fake = FakeProvider(reply="확인할 점입니다")
    assert fake.generate([Message("user", "안녕")], max_tokens=100, timeout_s=1) == "확인할 점입니다"
    assert fake.calls[0][0].content == "안녕"

    broken = FakeProvider(error=LLMError("연결 실패"))
    with pytest.raises(LLMError):
        broken.generate([], max_tokens=100, timeout_s=1)
