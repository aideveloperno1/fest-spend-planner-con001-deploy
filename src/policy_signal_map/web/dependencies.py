"""라우트 공통 의존성. 테스트는 app.dependency_overrides로 evidence_state_dep를 교체한다."""

from typing import Annotated

from fastapi import Cookie

from .evidence_state import EvidenceState, get_evidence_state
from .session import COOKIE_NAME, WorkState, store

SessionCookie = Annotated[str | None, Cookie(alias=COOKIE_NAME)]


def session_dep(session: SessionCookie = None) -> tuple[str, WorkState]:
    return store.get_or_create(session)


def evidence_state_dep() -> EvidenceState:
    return get_evidence_state()
