from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .paths import WEB_DIR
from .web.routes import choices as choice_routes
from .web.routes import draft as draft_routes
from .web.routes import evidence as evidence_routes
from .web.routes import health as health_routes
from .web.routes import input as input_routes
from .web.routes import landing as landing_routes
from .web.routes import opinions as opinion_routes
from .web.routes import questions as question_routes
from .web.session import COOKIE_NAME, SessionConflict, SessionStoreError
from .web.templating import with_cookie


class RevalidatingStaticFiles(StaticFiles):
    """CSS·JS를 브라우저가 매번 다시 확인하게 한다 (2026-09-18).

    기본 설정에서는 브라우저가 옛 파일을 계속 써서, 화면을 고쳐도 새로고침 전까지
    옛 동작이 보였다(입력 상태 패널이 갱신되지 않던 문제). `no-cache`는 "쓰지 말라"가
    아니라 "쓰기 전에 바뀌었는지 물어보라"는 뜻이라, 바뀐 게 없으면 304로 끝나 느려지지 않는다.
    """

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app = FastAPI(title="콕콕")


@app.middleware("http")
async def persist_work_session(request: Request, call_next):
    """라우트가 바꾼 상태를 응답 전 Redis에 저장한다."""
    response = await call_next(request)
    loaded = getattr(request.state, "work_session", None)
    if loaded is None:
        return response
    try:
        await run_in_threadpool(loaded.repository.commit, loaded)
    except SessionConflict as exc:
        return PlainTextResponse(str(exc), status_code=409)
    except SessionStoreError:
        return PlainTextResponse("작업 상태를 저장하지 못했습니다. 잠시 뒤 다시 시도해 주세요.", status_code=503)
    # JSON 응답(AI 의견)도 Redis와 브라우저의 만료 시간이 함께 연장되게 한다.
    if COOKIE_NAME not in response.headers.get("set-cookie", ""):
        with_cookie(response, loaded.session_id)
    return response


@app.exception_handler(SessionStoreError)
async def session_store_error(_request: Request, _exc: SessionStoreError) -> Response:
    return PlainTextResponse("작업 상태 저장소에 연결하지 못했습니다. 잠시 뒤 다시 시도해 주세요.", status_code=503)


app.mount("/static", RevalidatingStaticFiles(directory=WEB_DIR / "static"), name="static")
app.include_router(health_routes.router)
app.include_router(landing_routes.router)
app.include_router(input_routes.router)
app.include_router(evidence_routes.router)
app.include_router(question_routes.router)
app.include_router(opinion_routes.router)
app.include_router(choice_routes.router)
app.include_router(draft_routes.router)
