from typing import Any

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .paths import DOCS_DIR, WEB_DIR
from .web.routes import choices as choice_routes
from .web.routes import draft as draft_routes
from .web.routes import evidence as evidence_routes
from .web.routes import input as input_routes
from .web.routes import landing as landing_routes
from .web.routes import opinions as opinion_routes
from .web.routes import questions as question_routes

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
app.mount("/static", RevalidatingStaticFiles(directory=WEB_DIR / "static"), name="static")
# 랜딩이 쓰는 화면 캡처. docs/screenshots를 그대로 내보낸다 (static으로 복사하지 않는다 —
# 복사하면 캡처를 다시 찍을 때마다 두 곳을 맞춰야 하고 저장소에 같은 파일이 두 벌 남는다)
app.mount("/shots", RevalidatingStaticFiles(directory=DOCS_DIR / "screenshots"), name="shots")
app.include_router(landing_routes.router)
app.include_router(input_routes.router)
app.include_router(evidence_routes.router)
app.include_router(question_routes.router)
app.include_router(opinion_routes.router)
app.include_router(choice_routes.router)
app.include_router(draft_routes.router)
