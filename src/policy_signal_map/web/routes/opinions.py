"""3단계 AI 참고 의견 (6LLM참고의견계획.md C-5).

화면과 따로 부른다. 담당자가 버튼을 눌렀을 때만 외부 API 할당량을 사용한다.
근거 파일에 문제가 있거나 설정 조합이 막힌 상태면 부르지 않는다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response

from ...llm.base import LLMError, get_provider
from ...llm.opinions import safe_collect
from ...llm.catalog import model_info
from ...review.engine import run_review
from ...review.rules import rules_by_id
from ..ai_models import current_model
from ..dependencies import evidence_state_dep, session_dep
from ..evidence_state import EvidenceState
from ..session import WorkState

router = APIRouter()
Session = Annotated[tuple[str, WorkState], Depends(session_dep)]
Evidence = Annotated[EvidenceState, Depends(evidence_state_dep)]

FAILED = {"state": "failed", "message": "AI 의견을 불러오지 못했습니다"}
OFF = {"state": "off", "opinions": []}


@router.post("/step/3/opinions")
def opinions(session: Session, evidence: Evidence) -> Response:
    _, state = session
    if state.original is None or evidence.blocked or not evidence.ok or evidence.result is None:
        return JSONResponse(OFF)

    settings = evidence.settings
    if settings is None or settings.llm_provider == "none":
        return JSONResponse(OFF)

    model = current_model(settings, state)
    cached = state.cached_opinions(model)
    if cached is None:
        try:
            provider = get_provider(settings, model)
        except LLMError:
            return JSONResponse(FAILED)
        if provider is None:
            return JSONResponse(OFF)

        # 요청을 시작한 원안. 응답을 기다리는 동안 담당자가 원안을 다시 제출할 수 있다
        asked_for = state.original
        result = run_review(asked_for, evidence.result)
        cached = safe_collect(
            provider,
            result,
            asked_for,
            timeout_s=settings.llm_timeout_s,
            model=model,
        )
        if cached is None:
            return JSONResponse(FAILED)
        state.remember_opinions(model, cached, asked_for)

    titles = {rule_id: rule.title for rule_id, rule in rules_by_id().items()}
    return JSONResponse(
        {
            "state": "ok",
            "opinions": [
                {
                    "text": opinion.display_text,
                    # 화면 배지는 관리 번호가 아니라 규칙 제목으로 보여 준다 (사용자 결정 9/18)
                    "rule_labels": [titles.get(rule_id, rule_id) for rule_id in opinion.cited_rule_ids],
                }
                for opinion in cached.opinions
            ],
            "model": cached.model,
            "model_label": model_info(cached.model).label,
            "created_at": cached.created_at,
            "dropped_count": cached.dropped_count,
        }
    )
