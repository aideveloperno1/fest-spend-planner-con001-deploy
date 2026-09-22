"""랜딩 화면 (`/`). 서비스가 무엇을 하는지 보여 주고 1단계로 넘긴다.

세션을 만들지 않는다 — 소개 화면을 보기만 해도 작업 상태가 생기면 안 되기 때문이다.
화면에 쓰는 값은 모두 여기서 고정한다. 근거 파일을 읽지 않으므로 실제 자료가 섞일 수 없다.
수치·문구는 시연용 계층 합성 자료 기준이며, 바뀌면 tests/test_landing.py가 잡는다.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from ..landing_content import LANDING
from ..templating import render_plain

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def landing(request: Request) -> Response:
    return render_plain(request, "landing.html", {"c": LANDING})
