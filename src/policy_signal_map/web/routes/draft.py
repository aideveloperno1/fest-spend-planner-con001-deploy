"""5단계: 보완 기획안과 저장 (워크플로우 S04·S05, 5보완기획안계획.md 5장)"""

from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from ...document.builder import build_document
from ...document.filename import document_filename, request_filename
from ...document.models import DocumentBlocked, PlanDocument
from ...document.docx import render_docx, render_request_docx
from ...review.engine import run_review
from ..dependencies import evidence_state_dep, session_dep
from ..evidence_state import EvidenceState
from ..session import WorkState
from ..templating import redirect, render

router = APIRouter()
Session = Annotated[tuple[str, WorkState], Depends(session_dep)]
Evidence = Annotated[EvidenceState, Depends(evidence_state_dep)]


def _document(state: WorkState, evidence: EvidenceState) -> PlanDocument | DocumentBlocked:
    result = run_review(state.original, evidence.result)
    # 4단계를 거치지 않고 와도 원안 변경 후 재확인이 빠지지 않게 한다 (6-5a)
    state.sync_choices(result, evidence.result)
    return build_document(state.original, result, state.choices, evidence.result, date.today())


def _attachment(content: bytes, filename: str) -> Response:
    # 한글 파일 이름은 filename*(RFC 5987)로 보낸다. 옛 브라우저용 이름도 함께 둔다.
    disposition = f"attachment; filename=\"document.docx\"; filename*=UTF-8''{quote(filename)}"
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": disposition},
    )


@router.get("/step/5", response_class=HTMLResponse)
def show(request: Request, session: Session, evidence: Evidence) -> Response:
    session_id, state = session
    common = {"step": 5, "session_id": session_id, "state": state, "evidence": evidence}
    if state.original is None:
        return redirect("/step/1", session_id)
    if not evidence.ok or evidence.result is None:
        return render(request, "error.html", {}, status_code=503, **common)

    document = _document(state, evidence)
    if isinstance(document, DocumentBlocked):
        # 고르지 않은 질문이 남았으면 4단계에서 사유를 보여준다
        return redirect("/step/4", session_id)
    return render(
        request,
        "steps/draft.html",
        {"document": document, "filename": document_filename(state.original.name, date.today())},
        **common,
    )


@router.get("/step/5/document", response_class=HTMLResponse)
def full_document(request: Request, session: Session, evidence: Evidence) -> Response:
    # Step 5 자체가 전체 보고서다. 이전 Markdown 원문 주소는 보고서로 돌려보낸다.
    session_id, _ = session
    return redirect("/step/5", session_id)


@router.get("/step/5/request", response_class=HTMLResponse)
def request_draft(request: Request, session: Session, evidence: Evidence) -> Response:
    session_id, state = session
    common = {"step": 5, "session_id": session_id, "state": state, "evidence": evidence}
    if state.original is None:
        return redirect("/step/1", session_id)
    if not evidence.ok or evidence.result is None:
        return render(request, "error.html", {}, status_code=503, **common)

    document = _document(state, evidence)
    if isinstance(document, DocumentBlocked) or document.request_draft is None:
        return redirect("/step/5", session_id)
    return render(
        request,
        "steps/request.html",
        {
            "document": document,
            "draft": document.request_draft,
            "filename": request_filename(state.original.name, date.today()),
        },
        **common,
    )


@router.get("/step/5/download")
def download(session: Session, evidence: Evidence, kind: str = "plan") -> Response:
    session_id, state = session
    if state.original is None:
        return redirect("/step/1", session_id)
    if not evidence.ok or evidence.result is None:
        return PlainTextResponse("근거 자료를 읽지 못해 문서를 만들 수 없습니다.", status_code=503)

    document = _document(state, evidence)
    if isinstance(document, DocumentBlocked):
        return PlainTextResponse("\n".join(document.reasons), status_code=409)

    today = date.today()
    if kind == "request":
        if document.request_draft is None:
            return PlainTextResponse("정밀 분석 요청서 초안이 없습니다.", status_code=404)
        return _attachment(render_request_docx(document), request_filename(state.original.name, today))
    return _attachment(render_docx(document), document_filename(state.original.name, today))
