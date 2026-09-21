"""성과지표 점검 R10 (7지역확장계획.md 6장).

담당자가 고른 성과지표 가운데 **카드 자료로 산출되지 않는 것**이 있으면 묻는다.
카드 자료에는 결제금액과 거래건수가 있고 사람 수는 없다. 거래건수는 고객 수가 아니다.

자료의 성격만 보는 규칙이라 지역 자료가 없어도 동작한다 (최종검토v3 8-2).
사람이 자유 문장으로 적은 지표(기타)는 낱말만 보고 단정하지 않는다 — 다루는 방법은 묶음 3에서 정한다.
"""

from __future__ import annotations

from ..labels import METRIC_LABELS
from ..plan.models import NON_CARD_METRICS, PlanInput
from .basic_checks import _outcome
from .outcome import ReviewOutcome
from .rules import RuleInfo


def unsupported_metrics(plan: PlanInput) -> tuple[str, ...]:
    """고른 지표 가운데 카드 자료로 산출되지 않는 것의 화면 이름. 고른 순서를 지킨다."""
    return tuple(METRIC_LABELS[metric] for metric in plan.metrics if metric in NON_CARD_METRICS)


def run_r10(rule: RuleInfo, plan: PlanInput) -> ReviewOutcome | None:
    names = unsupported_metrics(plan)
    if not names:
        return None
    return _outcome(rule, "question", "question", metric_list=", ".join(names))


RUNNERS = {"R10": run_r10}
