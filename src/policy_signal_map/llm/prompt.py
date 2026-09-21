"""규칙 검토 결과 → 요청 문장 (6LLM참고의견계획.md C-3).

넘기는 것은 규칙 ID·결과 종류·수치 없는 상황 설명뿐이다.
금액·비중·구간 수 같은 수치와 근거 파일 원문은 넘기지 않는다 (최종기획서 8장).
사용자가 적은 문장은 지시가 아니라 자료로 구분해 넣는다.
"""

from __future__ import annotations

from ..labels import GOAL_LABELS, INDICATOR_USE_LABELS, METRIC_LABELS
from ..paths import RESOURCES_DIR
from ..plan.models import Goal, Metric, PlanInput
from ..review.outcome import ReviewResult
from .base import Message

TEMPLATE_PATH = RESOURCES_DIR / "prompts" / "opinion.txt"
# 사용자가 길게 적어도 요청 문장이 흔들리지 않게 자른다
MAX_FIELD_CHARS = 120
# Google 사고 모델은 사고 토큰도 maxOutputTokens 안에서 쓴다. 화면 표시는 검사에서 최대 3줄로 제한한다.
MAX_TOKENS = 2048

KIND_WORDS = {
    "question": "질문",
    "notice": "안내",
    "pending": "추가 확정 필요",
    "held": "보류",
}


def _short(text: str) -> str:
    """줄바꿈을 없애고 길이를 자른다. 여러 줄은 지시문처럼 보이기 쉽다."""
    single = " ".join(text.split())
    return single[:MAX_FIELD_CHARS]


def _outcome_lines(result: ReviewResult) -> str:
    lines = []
    for outcome in result.outcomes:
        summary = outcome.to_llm_summary()
        parts = [f"[{summary['rule_id']}] {KIND_WORDS.get(summary['kind'], summary['kind'])}", summary["title"]]
        parts.extend(summary["context"])
        if summary["scope_label"]:
            parts.append(f"적용 범위: {summary['scope_label']}")
        lines.append(" · ".join(parts))
    return "\n".join(lines) or "없음"


def _not_reviewed_lines(result: ReviewResult) -> str:
    lines = [f"[{item.rule_id}] {item.title} — {item.scope_label}" for item in result.not_reviewed]
    return "\n".join(lines) or "없음"


def _plan_lines(plan: PlanInput) -> str:
    goals = ", ".join(
        plan.goal_other if goal is Goal.OTHER else GOAL_LABELS[goal] for goal in plan.goals
    )
    metric_names = [METRIC_LABELS[metric] for metric in plan.metrics if metric is not Metric.OTHER]
    metric_names.extend(plan.metric_others)
    metrics = ", ".join(metric_names)
    use = INDICATOR_USE_LABELS[plan.indicator_use] if plan.indicator_use else "정하지 않음"
    return "\n".join(
        [
            f"사업 목표: {_short(goals) or '입력 없음'}",
            f"사업 대상: {_short(plan.target) or '입력 없음'}",
            f"성과지표: {_short(metrics) or '입력 없음'}",
            f"지표 용도: {use}",
        ]
    )


def build_messages(result: ReviewResult, plan: PlanInput) -> list[Message]:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    body = template.format(
        outcomes=_outcome_lines(result),
        not_reviewed=_not_reviewed_lines(result),
        plan=_plan_lines(plan),
    )
    return [
        Message("system", "확인할 점만 제시하는 보조자입니다. 결정하지 않고 수치를 만들지 않습니다."),
        Message("user", body),
    ]
