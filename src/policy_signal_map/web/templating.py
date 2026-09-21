from typing import Any

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from .. import formatting, labels
from ..paths import WEB_DIR
from ..plan.regions import region_label
from .evidence_state import EvidenceState
from .session import COOKIE_NAME, WorkState, cookie_max_age, cookie_secure

def _asset_version() -> str:
    """정적 파일 주소 뒤에 붙일 버전. 파일이 바뀌면 주소가 바뀌어 브라우저가 새로 받는다.

    화면을 고쳐도 브라우저가 옛 CSS·JS를 계속 쓰던 문제를 막는다 (2026-09-18).
    서버를 시작할 때 한 번 계산하므로, 파일을 고치면 서버를 다시 시작한다.
    """
    files = (p for p in (WEB_DIR / "static").rglob("*") if p.is_file())
    return str(int(max((p.stat().st_mtime for p in files), default=0)))


templates = Jinja2Templates(directory=WEB_DIR / "templates")
templates.env.globals.update(labels=labels, region_label=region_label, asset_version=_asset_version())
templates.env.filters.update(formatting.FILTERS)


def with_cookie(response: Response, session_id: str) -> Response:
    response.set_cookie(
        COOKIE_NAME,
        session_id,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        max_age=cookie_max_age(),
    )
    return response


def redirect(url: str, session_id: str) -> Response:
    return with_cookie(RedirectResponse(url, status_code=303), session_id)


def render(
    request: Request,
    template: str,
    context: dict[str, Any],
    *,
    step: int,
    session_id: str,
    state: WorkState,
    evidence: EvidenceState,
    status_code: int = 200,
) -> Response:
    """모든 화면은 이 함수로 그린다. base.html이 쓰는 값(step·state·evidence)을 빠뜨리면 페이지 전체가 오류가 난다."""
    full_context = {**context, "step": step, "state": state, "evidence": evidence}
    response = templates.TemplateResponse(request, template, full_context, status_code=status_code)
    return with_cookie(response, session_id)


def render_plain(request: Request, template: str, context: dict[str, Any] | None = None) -> Response:
    """세션·단계가 없는 화면(랜딩)을 그린다.

    render()는 base.html이 쓰는 step·state·evidence를 반드시 받는데, 랜딩에는 그런 값이 없다.
    쿠키도 붙이지 않는다 — 소개 화면을 보기만 해도 작업 상태가 생기면 안 되기 때문이다.
    """
    return templates.TemplateResponse(request, template, context or {})
