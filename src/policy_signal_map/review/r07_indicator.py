"""R07 금액·비중과 성과지표 확인 (최종기획서 4장 첫 사례).

판단 순서와 문구 기준: docs/review_rules.md, 3검토질문계획.md 4장.
"""

from __future__ import annotations

from ..evidence.compare import compare_record
from ..evidence.schema import EvidenceFile, EvidenceRecord
from ..evidence.summary import summarize_pairs
from ..formatting import period_label
from ..plan.models import Goal, IndicatorUse, Metric, PlanInput
from .context import source_label
from .outcome import ReviewOutcome, question_key_of
from .rules import RuleInfo

CARD_METRICS = (Metric.FOREIGN_SHARE, Metric.FOREIGN_AMOUNT)
# 참고 현황으로 쓰는 기획에는 "해석 조건 명시"만 고를 수 있게 한다 (4보완선택계획 결정 ④)
NOTICE_OPTION_IDS = ("B",)

# 목표와 지표가 서로 다른 것을 가리키는 조합 (금액 확대 목표 + 비중 지표 등)
MISMATCH = {
    (Goal.FOREIGN_AMOUNT, Metric.FOREIGN_SHARE): ("외국인 결제금액 확대", "외국인 결제 비중"),
    (Goal.FOREIGN_SHARE, Metric.FOREIGN_AMOUNT): ("외국인 결제 비중 확대", "외국인 결제금액"),
}


def applies_to(plan: PlanInput) -> bool:
    return any(metric in CARD_METRICS for metric in plan.metrics)


def _held(rule: RuleInfo, key: str, scope_label: str | None, region_note: str | None, **values: object) -> ReviewOutcome:
    return ReviewOutcome(
        rule_id=rule.id,
        question_key=question_key_of(rule.id),
        merge_group=rule.merge_group,
        kind="held",
        title=rule.title,
        message=rule.message(key, **values),
        scope_label=scope_label,
        region_note=region_note,
        related_fields=rule.related_fields_for(),
        context_keys=(key,),
    )


def _mismatch_prefix(rule: RuleInfo, plan: PlanInput) -> str:
    """목표와 지표가 다른 것을 가리키면 앞에 붙일 문장. 없으면 빈 문자열."""
    for (goal, metric), (goal_label, metric_label) in MISMATCH.items():
        if goal in plan.goals and metric in plan.metrics:
            return rule.message("goal_mismatch_prefix", goal_label=goal_label, metric_label=metric_label)
    return ""


def run(
    rule: RuleInfo,
    plan: PlanInput,
    file: EvidenceFile | None,
    record: EvidenceRecord | None,
    *,
    scope_label: str | None,
    region_note: str | None,
) -> ReviewOutcome | None:
    if not applies_to(plan):
        return None
    if record is None:
        return _held(rule, "held_no_record", scope_label, region_note)

    applicability = record.applicability["R07"]
    if applicability.status == "blocked":
        return _held(rule, "held_blocked", scope_label, region_note, reason=applicability.reason)
    if applicability.status == "needs_review":
        return _held(rule, "held_needs_review", scope_label, region_note, reason=applicability.reason)

    pairs = compare_record(record)
    summary = summarize_pairs(pairs)
    if summary.comparable_count == 0:
        return _held(rule, "held_no_pairs", scope_label, region_note)

    period = period_label(record.scope.period_start, record.scope.period_end)
    why_key = "why_opposite" if summary.opposite_a_count >= 1 else "why_same"
    why = rule.message(
        why_key,
        period=period,
        source=source_label(record),
        comparable_count=summary.comparable_count,
        opposite_count=summary.opposite_a_count,
    )

    if plan.indicator_use is IndicatorUse.REFERENCE:
        kind, message_key = "notice", "notice_reference"
    elif plan.indicator_use is IndicatorUse.UNKNOWN:
        kind, message_key = "question", "question_unknown"
    else:
        kind, message_key = "question", "question_direct"

    message = rule.message(message_key)
    context_keys = [message_key, why_key]
    if kind == "question":
        prefix = _mismatch_prefix(rule, plan)
        message = prefix + message
        if prefix:
            context_keys.append("goal_mismatch_prefix")

    return ReviewOutcome(
        rule_id=rule.id,
        question_key=question_key_of(rule.id),
        merge_group=rule.merge_group,
        kind=kind,
        title=rule.title,
        message=message,
        why=why,
        evidence_ids=(record.evidence_id,),
        scope_label=scope_label,
        region_note=region_note,
        options=(
            rule.options
            if kind == "question"
            else tuple(o for o in rule.options if o.id in NOTICE_OPTION_IDS)
        ),
        related_fields=rule.related_fields_for(),
        observations={
            "comparable_count": summary.comparable_count,
            "opposite_a_count": summary.opposite_a_count,
            "skipped_count": summary.skipped_count,
            "period": period,
            "dataset_version": file.dataset_version if file else None,
        },
        context_keys=tuple(context_keys),
    )
