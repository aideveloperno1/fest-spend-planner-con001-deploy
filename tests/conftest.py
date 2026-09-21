"""모든 테스트 공통 준비.

셸이나 .env의 PSM_ 환경변수가 테스트에 들어오지 않게 하고, 근거 상태를 합성 파일로 고정한다.
실제 분석 파일로 테스트가 돌아 실패 출력에 수치가 찍히는 일을 막는다.
"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from policy_signal_map.app import app
from policy_signal_map.config import LEGACY_DEMO_EVIDENCE_PATH
from policy_signal_map.web.dependencies import evidence_state_dep
from policy_signal_map.web.evidence_state import EvidenceState, get_evidence_state, load_evidence_state
from policy_signal_map.web.session import store


@pytest.fixture(autouse=True)
def no_real_llm_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """화면 테스트가 실제 Google AI 모델 목록 API에 닿지 않게 한다."""
    monkeypatch.setattr("policy_signal_map.llm.google_ai.list_models", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def isolated_evidence(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in list(os.environ):
        if key.startswith("PSM_") or key == "GEMINI_API_KEY":
            monkeypatch.delenv(key)
    # Vercel CI에서 테스트해도 실제 Redis를 사용하지 않는다.
    monkeypatch.setenv("PSM_SESSION_BACKEND", "memory")
    store.clear()
    get_evidence_state.cache_clear()
    saved = dict(app.dependency_overrides)
    demo = load_evidence_state(
        {"PSM_EVIDENCE_PATH": str(LEGACY_DEMO_EVIDENCE_PATH)}
    )
    app.dependency_overrides[evidence_state_dep] = lambda: demo
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)
    get_evidence_state.cache_clear()
    store.clear()


@pytest.fixture
def use_evidence() -> Callable[..., EvidenceState]:
    """사례 파일이나 설정으로 근거 상태를 바꾼다. 테스트가 끝나면 isolated_evidence가 되돌린다."""

    def _use(path: Path | None = None, **env: str) -> EvidenceState:
        environ = dict(env)
        if path is not None:
            environ["PSM_EVIDENCE_PATH"] = str(path)
        state = load_evidence_state(environ)
        app.dependency_overrides[evidence_state_dep] = lambda: state
        return state

    return _use
