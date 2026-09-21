"""라우트 공통 의존성. 테스트는 app.dependency_overrides로 evidence_state_dep를 교체한다."""

from typing import Annotated

from fastapi import Cookie, Request

from .evidence_state import EvidenceState, get_evidence_state
from .session import COOKIE_NAME, WorkState, configured_session_store

SessionCookie = Annotated[str | None, Cookie(alias=COOKIE_NAME)]


def session_dep(request: Request, session: SessionCookie = None) -> tuple[str, WorkState]:
    loaded = configured_session_store().load_or_create(session)
    # 응답을 만들고 난 뒤 middleware가 변경된 상태를 Redis에 확정한다.
    request.state.work_session = loaded
    return loaded.session_id, loaded.state


def evidence_state_dep() -> EvidenceState:
    return get_evidence_state()
