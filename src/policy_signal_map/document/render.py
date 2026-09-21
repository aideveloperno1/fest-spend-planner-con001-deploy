"""문서 구조 → Markdown. 양식은 resources/documents/에 둔다.

사용자가 적은 문장은 Markdown 표·링크를 깨뜨리지 않게 이스케이프한다.
"""

from __future__ import annotations

import re

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..paths import RESOURCES_DIR
from .models import PENDING_MARK, PlanDocument

TEMPLATE_DIR = RESOURCES_DIR / "documents"
# 표 칸과 코드 표기를 깨뜨리는 글자만 막는다. 대괄호는 [추가 확정 필요] 표기에 쓰므로 그대로 둔다
_ESCAPE = re.compile(r"([|`])")


def md_escape(value: object) -> str:
    return _ESCAPE.sub(r"\\\1", str(value))


def mark_pending(value: object) -> str:
    """담당자가 채워야 하는 자리를 문서에서 굵게 표시한다 (화면에는 표시 기호를 두지 않는다)."""
    return str(value).replace(PENDING_MARK, f"**{PENDING_MARK}**")


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=False,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["md_escape"] = md_escape
    env.filters["mark_pending"] = mark_pending
    return env


def render_markdown(document: PlanDocument) -> str:
    return _environment().get_template("plan.md.j2").render(doc=document)


def render_request(document: PlanDocument) -> str:
    """대안 D를 고른 경우에만 만든다. 요청서만 따로 보내는 일이 있어 파일을 나눈다."""
    if document.request_draft is None:
        raise ValueError("정밀 분석 요청서 초안이 없는 문서입니다")
    return _environment().get_template("request.md.j2").render(doc=document, draft=document.request_draft)
