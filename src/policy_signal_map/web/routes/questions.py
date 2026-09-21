"""3단계: 검토 질문 (워크플로우 S02·11장, 3검토질문계획.md)"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from ...llm.catalog import model_info
from ...llm.google_ai import is_available
from ...review.engine import run_review
from ..ai_models import available_models, current_model, model_options
from ..dependencies import evidence_state_dep, session_dep
from ..evidence_state import EvidenceState
from ..session import WorkState
from ..templating import redirect, render

router = APIRouter()
Session = Annotated[tuple[str, WorkState], Depends(session_dep)]
Evidence = Annotated[EvidenceState, Depends(evidence_state_dep)]

KIND_LABELS = {
    "question": "질문",
    "notice": "안내",
    "pending": "추가 확정 필요",
    "held": "보류",
    "not_reviewed": "검토하지 않음",
}


MODEL_NOT_ALLOWED = "선택할 수 없는 모델입니다."
MODEL_UNAVAILABLE = "이 API 키의 Google AI 프로젝트에서 사용할 수 없는 모델입니다."


def _context(state: WorkState, evidence: EvidenceState, model_error: str | None = None) -> dict[str, Any]:
    assert evidence.result is not None and state.original is not None
    # 검토 결과는 저장하지 않고 요청마다 다시 계산한다 (같은 입력이면 같은 결과)
    result = run_review(state.original, evidence.result)
    # AI 의견은 담당자가 버튼을 누를 때 /step/3/opinions로 따로 받는다.
    settings = evidence.settings
    ai_enabled = settings is not None and settings.llm_provider != "none"
    context: dict[str, Any] = {"result": result, "kind_labels": KIND_LABELS, "ai_enabled": ai_enabled}
    if ai_enabled and settings is not None:
        model = current_model(settings, state)
        # 목록 확인 실패는 선택을 막지 않는다. 실제 생성 요청에서 다시 결과를 안내한다.
        available = available_models(settings) if len(settings.llm_models) > 1 else None
        context.update(
            ai_models=model_options(settings, available),
            ai_current=model,
            ai_current_info=model_info(model),
            ai_model_error=model_error,
        )
    return context


@router.get("/step/3", response_class=HTMLResponse)
def show(request: Request, session: Session, evidence: Evidence) -> Response:
    session_id, state = session
    common = {"step": 3, "session_id": session_id, "state": state, "evidence": evidence}

    if state.original is None:
        return redirect("/step/1", session_id)
    if not evidence.ok or evidence.result is None:
        return render(request, "error.html", {}, status_code=503, **common)
    return render(request, "steps/questions.html", _context(state, evidence), **common)


@router.post("/step/3/ai-model")
async def choose_model(request: Request, session: Session, evidence: Evidence) -> Response:
    """담당자가 AI 참고 의견 모델을 고른다 (C-8). 검토 결과·선택·기획안에는 영향이 없다."""
    session_id, state = session
    common = {"step": 3, "session_id": session_id, "state": state, "evidence": evidence}
    if state.original is None:
        return redirect("/step/1", session_id)
    if not evidence.ok or evidence.result is None:
        return render(request, "error.html", {}, status_code=503, **common)

    settings = evidence.settings
    form = await request.form()
    model = str(form.get("model", "")).strip()
    if settings is None or settings.llm_provider == "none" or model not in settings.llm_models:
        return render(request, "steps/questions.html", _context(state, evidence, MODEL_NOT_ALLOWED), status_code=422, **common)
    # 사용할 수 없는 것이 확실할 때만 막는다. 확인 실패(None)는 생성 요청에서 처리한다.
    if is_available(model, available_models(settings)) is False:
        return render(
            request,
            "steps/questions.html",
            _context(state, evidence, MODEL_UNAVAILABLE),
            status_code=422,
            **common,
        )

    state.llm_model = model
    return redirect("/step/3", session_id)
