"""1단계: 기획 입력 (워크플로우 S01)"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from ...plan.models import BudgetStatus, PlanInput, Region, RegionLevel, sample_plan
from ...plan.regions import load_regions, sido_list
from ...plan.validation import ValidationResult, validate_plan
from ...review.rules import load_rule_catalog
from ..dependencies import evidence_state_dep, session_dep
from ..evidence_state import EvidenceState
from ..forms import parse_plan_form
from ..profile_view import option_catalog
from ..session import WorkState
from ..templating import redirect, render

router = APIRouter()
Session = Annotated[tuple[str, WorkState], Depends(session_dep)]
Evidence = Annotated[EvidenceState, Depends(evidence_state_dep)]


def sample_plan_for(evidence: EvidenceState) -> PlanInput:
    """공개 전달본을 쓰면 선택 가능한 가상 지역과 제공 기간으로 예시를 맞춘다."""
    plan = sample_plan()
    if evidence.result is None or evidence.result.profile("DEMO-SGG-A") is None:
        return plan
    plan.region = Region(RegionLevel.SIGUNGU, sido_code="DEMO", sigungu_code="DEMO-SGG-A")
    plan.period_start = "2026-05-01"
    plan.period_end = "2026-06-30"
    return plan


def _render(
    request: Request,
    session: tuple[str, WorkState],
    evidence: EvidenceState,
    result: ValidationResult | None = None,
    status_code: int = 200,
) -> Response:
    session_id, state = session
    plan = state.plan
    context = {
        "plan": plan,
        # 제출 전에는 오류를 보여주지 않고, 요약만 현재 입력 기준으로 보여준다
        "errors": result.errors if result else {},
        "summary": result or validate_plan(plan),
        "sido_list": sido_list(),
        "regions_json": load_regions(),
        "rules": load_rule_catalog(),
        "budget_status": BudgetStatus,
        # 고를 수 있는 업종·연령은 근거 파일이 알려 준다. 없으면 그 입력칸을 두지 않는다
        "catalog": option_catalog(evidence.result),
        # 아직 아무것도 입력하지 않았으면 필수 항목을 "확인 필요"로 겁주지 않는다 (9/18)
        "plan_touched": plan != PlanInput(),
    }
    return render(
        request,
        "steps/input.html",
        context,
        step=1,
        session_id=session_id,
        state=state,
        evidence=evidence,
        status_code=status_code,
    )


@router.get("/step/1", response_class=HTMLResponse)
def show(request: Request, session: Session, evidence: Evidence) -> Response:
    return _render(request, session, evidence)


@router.post("/step/1")
async def submit(request: Request, session: Session, evidence: Evidence) -> Response:
    session_id, state = session
    form = await request.form()
    action = form.get("action")

    if action == "sample":
        state.plan = sample_plan_for(evidence)
        return redirect("/step/1", session_id)
    if action == "clear":
        state.plan = PlanInput()
        return redirect("/step/1", session_id)

    single = {k: v for k, v in form.items() if isinstance(v, str)}
    multi = {
        k: [v for v in form.getlist(k) if isinstance(v, str)]
        for k in ("goals", "metrics", "usage_industries", "target_ages")
    }
    catalog = option_catalog(evidence.result)
    state.plan = parse_plan_form(
        single, multi, industry_codes=catalog.industry_codes(), age_codes=catalog.age_codes()
    )

    result = validate_plan(state.plan)
    if not result.ok:
        return _render(request, session, evidence, result, status_code=422)

    state.start_review()
    return redirect("/step/2", session_id)


@router.post("/reset")
def reset(session: Session) -> Response:
    session_id, state = session
    state.reset()
    return redirect("/step/1", session_id)
