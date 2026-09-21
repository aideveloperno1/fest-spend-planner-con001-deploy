"""검토 결과 → AI 참고 의견 (6LLM참고의견계획.md C-5).

여기서 만든 의견은 화면에만 쓴다. 담당자가 채택하기 전에는 선택·문서에 반영하지 않는다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from ..plan.models import PlanInput
from ..review.outcome import ReviewResult
from .base import LLMError, LLMProvider
from .guard import Opinion, check
from .prompt import MAX_TOKENS, build_messages

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpinionSet:
    opinions: tuple[Opinion, ...]
    provider_name: str
    model: str
    created_at: str
    dropped_count: int = 0


def collect(
    provider: LLMProvider,
    result: ReviewResult,
    plan: PlanInput,
    *,
    timeout_s: float,
    model: str = "",
    now: datetime | None = None,
) -> OpinionSet:
    """의견을 만들고 검사한다. 호출 실패는 LLMError로 올린다."""
    messages = build_messages(result, plan)
    raw = provider.generate(messages, max_tokens=MAX_TOKENS, timeout_s=timeout_s)

    available = {outcome.rule_id for outcome in result.outcomes}
    not_reviewed = {item.rule_id for item in result.not_reviewed}
    checked = check(raw, available, not_reviewed)
    for line, reason in checked.dropped:
        # 버린 줄 자체는 남기지 않는다. 사유만 세어 둔다
        log.info("AI 의견 폐기: %s (%d자)", reason, len(line))

    return OpinionSet(
        opinions=checked.kept,
        provider_name=provider.name,
        model=model,
        created_at=(now or datetime.now()).strftime("%Y-%m-%d %H:%M"),
        dropped_count=len(checked.dropped),
    )


def safe_collect(
    provider: LLMProvider, result: ReviewResult, plan: PlanInput, *, timeout_s: float, model: str = ""
) -> OpinionSet | None:
    """실패하면 None. 규칙 기반 흐름은 그대로 두고 화면에 안내만 띄운다."""
    try:
        return collect(provider, result, plan, timeout_s=timeout_s, model=model)
    except LLMError:
        return None
    except Exception:  # 제공자가 예상 밖의 오류를 낼 수 있다. 화면을 막지 않는다
        log.exception("AI 의견 생성 중 예상 밖의 오류")
        return None
