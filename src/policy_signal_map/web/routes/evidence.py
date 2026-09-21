"""2단계: 근거 확인 (워크플로우 S02, 2근거확인화면계획.md 7장)"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from ..dependencies import evidence_state_dep, session_dep
from ..evidence_state import EvidenceState
from ..evidence_view import HOLD_EXAMPLE_NOTE, build_evidence_view
from ..profile_view import build_profile_view
from ..session import WorkState
from ..templating import redirect, render

router = APIRouter()
Session = Annotated[tuple[str, WorkState], Depends(session_dep)]
Evidence = Annotated[EvidenceState, Depends(evidence_state_dep)]


@router.get("/step/2", response_class=HTMLResponse)
def show(request: Request, session: Session, evidence: Evidence) -> Response:
    session_id, state = session
    common = {"step": 2, "session_id": session_id, "state": state, "evidence": evidence}

    if state.original is None:
        return redirect("/step/1", session_id)
    if not evidence.ok or evidence.result is None:
        return render(request, "error.html", {}, status_code=503, **common)

    view = build_evidence_view(state.original, evidence.result)
    # 프로필은 고른 지역 자료만 쓴다. 금액·비중 비교와 달리 범위를 넓히지 않는다
    profile = build_profile_view(state.original, evidence.result)
    return render(
        request,
        "steps/evidence.html",
        {"view": view, "profile": profile, "hold_note": HOLD_EXAMPLE_NOTE},
        **common,
    )
