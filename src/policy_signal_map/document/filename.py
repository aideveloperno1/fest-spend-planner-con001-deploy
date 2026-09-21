"""저장 파일 이름 (보완기획안_{사업명}_{날짜}.docx)."""

from __future__ import annotations

import re
from datetime import date

FORBIDDEN = re.compile(r'[\\/:*?"<>|\r\n\t]')
MAX_NAME = 60


def _stem(plan_name: str) -> str:
    cleaned = FORBIDDEN.sub("", plan_name).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)[:MAX_NAME].strip("_")
    return cleaned.rstrip(". ")  # 윈도에서 마침표·공백으로 끝나는 이름은 저장이 막힌다


def _named(prefix: str, plan_name: str, today: date) -> str:
    stem = _stem(plan_name)
    stamp = today.strftime("%Y%m%d")
    return f"{prefix}_{stem}_{stamp}.docx" if stem else f"{prefix}_{stamp}.docx"


def document_filename(plan_name: str, today: date) -> str:
    return _named("보완기획안", plan_name, today)


def request_filename(plan_name: str, today: date) -> str:
    return _named("정밀분석요청서", plan_name, today)
