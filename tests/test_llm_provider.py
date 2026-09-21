"""LLM 제공자 계층 (6LLM참고의견계획.md C-2). 실제 모델을 부르지 않는다."""

import json
import urllib.error

import pytest

from policy_signal_map.config import DEFAULT_LLM_TIMEOUT_S, SettingsError, load_settings
from policy_signal_map.llm.base import FakeProvider, LLMError, Message, get_provider
from policy_signal_map.llm.local import LocalProvider, is_installed, list_models


def settings(**env: str):
    return load_settings(env)


def test_no_provider_by_default():
    assert get_provider(settings()) is None


def test_cloud_is_not_implemented_yet():
    with pytest.raises(LLMError) as exc:
        get_provider(settings(PSM_LLM_PROVIDER="cloud", PSM_LLM_MODEL="m", PSM_LLM_API_KEY="k"))
    assert "아직 구현하지 않았습니다" in str(exc.value)


def test_local_provider_is_built_from_settings():
    provider = get_provider(
        settings(
            PSM_LLM_PROVIDER="local",
            PSM_LLM_MODEL="exaone",
            PSM_LLM_BASE_URL="http://127.0.0.1:11434/v1",
        )
    )
    assert provider is not None
    assert provider.name == "local"
    assert provider.model == "exaone"


def test_timeout_default_and_override():
    assert settings().llm_timeout_s == DEFAULT_LLM_TIMEOUT_S
    assert settings(PSM_LLM_TIMEOUT_S="5.5").llm_timeout_s == 5.5


def test_bad_timeout_is_rejected():
    for value in ("빠르게", "0", "-3"):
        with pytest.raises(SettingsError):
            settings(PSM_LLM_TIMEOUT_S=value)


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def local_provider() -> LocalProvider:
    return LocalProvider(base_url="http://127.0.0.1:11434/v1", model="exaone")


def test_local_call_sends_openai_shape_and_reads_content(monkeypatch: pytest.MonkeyPatch):
    sent: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        sent["url"] = request.full_url
        sent["timeout"] = timeout
        sent["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(json.dumps({"choices": [{"message": {"content": "확인할 점"}}]}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    text = local_provider().generate([Message("user", "질문")], max_tokens=300, timeout_s=7)

    assert text == "확인할 점"
    assert sent["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert sent["timeout"] == 7
    assert sent["body"]["model"] == "exaone"
    assert sent["body"]["messages"] == [{"role": "user", "content": "질문"}]
    assert sent["body"]["stream"] is False
    # 생각 과정 출력을 끈다 (C-0: gemma4는 켜져 있으면 본문이 비었다)
    assert sent["body"]["reasoning_effort"] == "none"


def test_local_call_failure_becomes_llm_error(monkeypatch: pytest.MonkeyPatch):
    def refuse(request, timeout):
        raise urllib.error.URLError("연결 거부")

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    with pytest.raises(LLMError) as exc:
        local_provider().generate([Message("user", "질문")], max_tokens=300, timeout_s=1)
    # 화면에 그대로 보여도 서버 정보가 드러나지 않아야 한다
    assert "연결 거부" not in str(exc.value)
    assert "11434" not in str(exc.value)


def test_local_call_with_unexpected_shape_becomes_llm_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeResponse(b'{"choices": []}'),
    )
    with pytest.raises(LLMError):
        local_provider().generate([Message("user", "질문")], max_tokens=300, timeout_s=1)


def test_fake_provider_records_calls_and_can_fail():
    fake = FakeProvider(reply="확인할 점입니다")
    assert fake.generate([Message("user", "안녕")], max_tokens=100, timeout_s=1) == "확인할 점입니다"
    assert fake.calls[0][0].content == "안녕"

    broken = FakeProvider(error=LLMError("연결 실패"))
    with pytest.raises(LLMError):
        broken.generate([], max_tokens=100, timeout_s=1)


LOCAL = dict(PSM_LLM_PROVIDER="local", PSM_LLM_BASE_URL="http://127.0.0.1:11434/v1")


def test_provider_uses_the_chosen_model_from_the_list():
    provider = get_provider(settings(**LOCAL, PSM_LLM_MODELS="a,b"), "b")
    assert provider is not None and provider.model == "b"


def test_provider_refuses_a_model_outside_the_list():
    with pytest.raises(LLMError, match="선택할 수 없는 모델"):
        get_provider(settings(**LOCAL, PSM_LLM_MODELS="a,b"), "c")


def test_list_models_reads_openai_model_list(monkeypatch: pytest.MonkeyPatch):
    sent: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        sent["url"] = request.full_url
        sent["timeout"] = timeout
        return FakeResponse(json.dumps({"data": [{"id": "exaone3.5:7.8b"}, {"id": "gemma"}]}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    installed = list_models("http://127.0.0.1:11434/v1/")
    assert sent["url"] == "http://127.0.0.1:11434/v1/models"
    assert sent["timeout"] == 2.0
    assert is_installed("exaone3.5:7.8b", installed) is True
    # 태그 없는 이름은 :latest와 같다
    assert is_installed("gemma:latest", installed) is True
    assert is_installed("gemma4:26b-a4b-it-qat", installed) is False


def test_list_models_failure_is_unknown_not_empty(monkeypatch: pytest.MonkeyPatch):
    def refuse(request, timeout):
        raise urllib.error.URLError("연결 거부")

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    assert list_models("http://127.0.0.1:11434/v1") is None
    assert is_installed("a", None) is None


def test_reasoning_effort_can_be_left_out(monkeypatch: pytest.MonkeyPatch):
    sent: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        sent["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(json.dumps({"choices": [{"message": {"content": "확인할 점"}}]}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("policy_signal_map.llm.local.REASONING_EFFORT", None)
    local_provider().generate([Message("user", "질문")], max_tokens=300, timeout_s=1)
    assert "reasoning_effort" not in sent["body"]
