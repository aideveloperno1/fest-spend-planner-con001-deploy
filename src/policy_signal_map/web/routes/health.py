"""Vercel 배포 상태 확인. 비밀값과 서버 경로는 반환하지 않는다."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response

from ..dependencies import evidence_state_dep
from ..evidence_state import EvidenceState
from ..session import SessionStoreError, configured_session_store, load_session_config

router = APIRouter()
Evidence = Annotated[EvidenceState, Depends(evidence_state_dep)]


@router.get("/health", include_in_schema=False)
def health(evidence: Evidence) -> Response:
    errors: list[str] = []
    try:
        config = load_session_config()
        configured_session_store().ping()
        backend = config.backend
    except SessionStoreError:
        backend = "unavailable"
        errors.append("session")

    if not evidence.ok or evidence.result is None:
        errors.append("evidence")
        evidence_version = None
    else:
        evidence_version = evidence.result.file.dataset_version

    provider = evidence.settings.llm_provider if evidence.settings else "invalid"
    payload = {
        "status": "degraded" if errors else "ok",
        "evidence": evidence_version,
        "session_backend": backend,
        "llm_provider": provider,
    }
    if errors:
        payload["errors"] = errors
    return JSONResponse(payload, status_code=503 if errors else 200)
