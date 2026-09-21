"""4단계: 보완 선택 (워크플로우 S03, 4보완선택계획.md 6장)"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from ...choices.models import AVAILABILITY_LABELS, DECISION_LABELS, Availability, Decision
from ...choices.selection import apply_choice, blocking_reasons, cancel_choice, pending_from_choices
from ...review.engine import run_review
from ..dependencies import evidence_state_dep, session_dep
from ..evidence_state import EvidenceState
from ..forms import parse_choice_form
from ..session import WorkState
from ...review.rules import rules_by_id
from ..templating import redirect, render

router = APIRouter()
Session = Annotated[tuple[str, WorkState], Depends(session_dep)]
Evidence = Annotated[EvidenceState, Depends(evidence_state_dep)]


def _context(
    state: WorkState,
    evidence: EvidenceState,
    errors: dict[str, str] | None = None,
    key: str = "",
    submitted: dict[str, str] | None = None,
):
    result = run_review(state.original, evidence.result)
    state.sync_choices(result, evidence.result)
    rule_titles = {rule_id: rule.title for rule_id, rule in rules_by_id().items()}
    rule_titles.update({outcome.question_key: outcome.title for outcome in result.outcomes})
    return {
        "result": result,
        "choice_set": state.choices,
        "pending": pending_from_choices(state.choices, result),
        "blocking": blocking_reasons(result, state.choices),
        # 안내 문구에 관리 번호(R07) 대신 제목을 쓰기 위한 표 (사용자 결정 9/18)
        "rule_titles": rule_titles,
        "decisions": DECISION_LABELS,
        "availabilities": AVAILABILITY_LABELS,
        "errors": errors or {},
        "error_key": key,
        # 저장에 실패했을 때 방금 고른 값. 없으면 화면이 빈 상태로 다시 그려져
        # "저장을 눌러도 아무 일도 안 일어난다"로 보인다 (사용자 확인 2026-09-19)
        "submitted": submitted or {},
    }


@router.get("/step/4", response_class=HTMLResponse)
def show(request: Request, session: Session, evidence: Evidence) -> Response:
    session_id, state = session
    common = {"step": 4, "session_id": session_id, "state": state, "evidence": evidence}
    if state.original is None:
        return redirect("/step/1", session_id)
    if not evidence.ok or evidence.result is None:
        return render(request, "error.html", {}, status_code=503, **common)
    return render(request, "steps/choices.html", _context(state, evidence), **common)


@router.post("/step/4")
async def save(request: Request, session: Session, evidence: Evidence) -> Response:
    session_id, state = session
    common = {"step": 4, "session_id": session_id, "state": state, "evidence": evidence}
    if state.original is None:
        return redirect("/step/1", session_id)
    if not evidence.ok or evidence.result is None:
        return render(request, "error.html", {}, status_code=503, **common)

    form = await request.form()
    single, collect_items = parse_choice_form(form)
    question_key = single.get("question_key", "")

    result = run_review(state.original, evidence.result)
    # 원안이 바뀌기 전에 열어 둔 화면에서 저장해도, 정리를 먼저 해야 이 저장이 재확인을 푼 상태로 남는다
    state.sync_choices(result, evidence.result)
    outcome = result.by_key(question_key)
    if outcome is None:
        return redirect("/step/4", session_id)

    errors = apply_choice(
        state.choices,
        outcome,
        single,
        collect_items,
        evidence_dataset_version=evidence.result.file.dataset_version,
        evidence_thresholds_version=evidence.result.thresholds.version if evidence.result.thresholds else None,
    )
    if errors:
        # 폼 원문을 그대로 돌려준다 (collect_items는 쪼개기 전 글자여야 사용자가 고쳐 쓸 수 있다)
        raw = {key: value for key, value in form.items() if isinstance(value, str)}
        context = _context(state, evidence, errors, question_key, raw)
        return render(request, "steps/choices.html", context, status_code=422, **common)
    return redirect("/step/4", session_id)


@router.post("/step/4/cancel")
async def cancel(request: Request, session: Session, evidence: Evidence) -> Response:
    session_id, state = session
    if state.original is None:
        return redirect("/step/1", session_id)
    if evidence.ok and evidence.result is not None:
        state.sync_choices(run_review(state.original, evidence.result), evidence.result)
    form = await request.form()
    question_key = form.get("question_key")
    if isinstance(question_key, str):
        cancel_choice(state.choices, question_key)
    return redirect("/step/4", session_id)
