"""원안 + 담당자 선택 → 보완 기획안 구조 (워크플로우 S04).

AI를 쓰지 않고 확인된 값만 양식에 채운다. 선택하지 않은 항목은 원안을 그대로 둔다.
"""

from __future__ import annotations

from datetime import date

from ..choices.models import AVAILABILITY_LABELS, Choice, ChoiceSet, Decision
from ..choices.selection import blocking_reasons, pending_from_choices
from ..evidence.loader import LoadResult
from ..evidence.profile_schema import ShareItem
from ..formatting import month_label, period_label
from ..labels import DECISION_LABELS_FOR_DOCUMENT
from ..plan.models import Goal, PlanInput
from ..plan.regions import region_label
from ..plan.validation import validate_plan
from ..review.context import exact_region_key, scope_label
from ..review.outcome import ReviewOutcome, ReviewResult
from ..review.rules import OptionSpec
from .describe import describe_plan, goal_labels, metric_labels
from .models import (
    PENDING_MARK,
    Change,
    DocumentBlocked,
    EvidenceRef,
    Line,
    PlanDocument,
    ProfileSummary,
    RequestDraft,
    Section,
)

DATA_KIND_LABELS = {"synthetic": "시연용 합성 수치", "real": "실제 분석 자료"}
PROFILE_BASIS_NOTES = {
    "merchant": "그 지역 가맹점에서 결제된 금액 기준",
    "cardholder": "그 지역에 사는 사람이 결제한 금액 기준",
    "unconfirmed": "지역 구분 기준 확인 중",
}
PROFILE_RANK_LABELS = {
    "foreign_share": "외국인 결제 비중",
    "payment_amount": "결제금액 규모",
    "payment_count": "결제건수",
}


def _values(plan: PlanInput, choice: Choice, choice_set: ChoiceSet) -> dict[str, str]:
    execution = choice_set.execution_for(choice.merge_group)
    availability = (
        AVAILABILITY_LABELS[execution.availability]
        if execution and execution.availability is not None
        else PENDING_MARK
    )
    return {
        "collect_items": ", ".join(execution.collect_items) if execution and execution.collect_items else PENDING_MARK,
        "owner": execution.owner if execution and execution.owner else PENDING_MARK,
        "cycle": execution.cycle if execution and execution.cycle else PENDING_MARK,
        "availability": availability,
        "usage_place": plan.usage_place or PENDING_MARK,
        "target": plan.target or PENDING_MARK,
        "goals": goal_labels(plan),
        "goals_without_store_usage": goal_labels(plan, exclude=Goal.STORE_USAGE),
        "metrics": metric_labels(plan),
    }


def _option_lines(option: OptionSpec, choice: Choice, values: dict[str, str]) -> list[str]:
    if choice.decision is Decision.MODIFY and choice.modified_text:
        # 담당자가 고친 문장이 대안 문장을 대체한다 (5보완기획안계획 결정 ③)
        return [choice.modified_text]
    return [line.format(**values) for line in option.document.lines] if option.document else []


def _apply_choice(
    sections: dict[int, Section],
    plan: PlanInput,
    choice: Choice,
    choice_set: ChoiceSet,
    outcome: ReviewOutcome,
    changes: list[Change],
) -> None:
    option = outcome.option(choice.option_id) if choice.option_id else None
    if option is None or option.document is None:
        return

    document = option.document
    section = sections[document.section]
    values = _values(plan, choice, choice_set)
    lines = _option_lines(option, choice, values)
    decision_label = DECISION_LABELS_FOR_DOCUMENT[choice.decision]

    for index, text in enumerate(lines):
        # 문서 안에서 변경 문장과 별첨 표를 잇는 공개용 번호다. 내부 규칙 번호는
        # Change.rule_id에만 보관하고 화면·Markdown에는 내보내지 않는다.
        change_id = f"변경 {len(changes) + 1:03d}"
        replace_at = section.find(document.replace_key) if document.mode == "replace" and index == 0 else None

        if replace_at is not None:
            before = section.lines[replace_at].text
            section.lines[replace_at] = Line(text, key=document.replace_key, state="changed", change_id=change_id, evidence_ids=choice.evidence_ids)
        else:
            before = None
            if any(line.text == text for line in section.lines):
                continue  # 같은 장에 같은 문장은 한 번만 (대안을 여러 개 채택한 경우)
            section.lines.append(Line(text, state="added", change_id=change_id, evidence_ids=choice.evidence_ids))

        changes.append(
            Change(
                change_id=change_id,
                section=document.section,
                before=before,
                after=text,
                rule_id=choice.rule_id,
                rule_title=outcome.title,
                option_id=option.id,
                decision_label=decision_label,
                evidence_ids=choice.evidence_ids,
                modified=choice.decision is Decision.MODIFY,
            )
        )


def _auto_records(result: ReviewResult) -> list[str]:
    """보류·추가 확정 필요 결과는 선택 없이 8장에 기록한다 (4보완선택계획 결정 ⑤)."""
    records = []
    for outcome in result.outcomes:
        if outcome.kind == "held":
            # 8장 본문에는 관리 번호를 쓰지 않는다. 번호는 별첨 변경 표·근거 추적에만 남긴다
            records.append(f"{outcome.title}: {outcome.message}")
    return records


def _evidence_refs(result: ReviewResult, evidence: LoadResult) -> tuple[EvidenceRef, ...]:
    used = {evidence_id for outcome in result.outcomes for evidence_id in outcome.evidence_ids}
    refs = []
    for record in evidence.file.records:
        if record.evidence_id not in used:
            continue
        refs.append(
            EvidenceRef(
                evidence_id=record.evidence_id,
                data_kind=record.data_kind,
                dataset_version=evidence.file.dataset_version,
                scope_label=scope_label(record) or "",
                period_label=period_label(record.scope.period_start, record.scope.period_end),
                limitations=record.limitations,
            )
        )
    return tuple(refs)


def _largest_share_line(label: str, items: tuple[ShareItem, ...]) -> str | None:
    available = [item for item in items if item.has_value and item.share_pct is not None]
    if not available:
        return None
    item = max(available, key=lambda row: row.share_pct)
    return f"{label}에서 비중이 가장 큰 항목: {item.label} ({item.share_pct:.2f}%)"


def _profile_summary(plan: PlanInput, evidence: LoadResult) -> ProfileSummary:
    """고른 지역 프로필을 넓히지 않고 별첨용 문장으로 줄인다."""
    label = region_label(plan.region) or "선택한 지역"
    key = exact_region_key(plan)
    profile = evidence.profile(key) if key else None
    common = {
        "region_label": label,
        "dataset_version": evidence.file.dataset_version,
        "data_kind": evidence.file.data_kind,
    }
    if profile is None:
        return ProfileSummary(
            **common,
            available=False,
            note="이 지역은 아직 지역 소비 프로필에 연결되지 않았습니다. 다른 지역 자료로 대신하지 않습니다.",
        )
    if not profile.ready("profile"):
        return ProfileSummary(
            **common,
            available=False,
            note=profile.readiness_note("profile"),
        )

    lines: list[str] = []
    if profile.ready("industry"):
        line = _largest_share_line("업종 구성", profile.industry)
        if line:
            lines.append(line)
    if profile.ready("age"):
        line = _largest_share_line("연령 구성", profile.age)
        if line:
            lines.append(line)
            denominator = (
                "연령을 알 수 없는 결제를 뺀 구성비"
                if profile.age_denominator == "known_only"
                else "연령을 알 수 없는 결제를 포함한 구성비"
            )
            lines.append(f"연령 구성 분모: {denominator}")
    if profile.ready("season"):
        months = [month for month in profile.months if month.season_index is not None]
        if months:
            month = max(months, key=lambda row: row.season_index)
            lines.append(
                f"제공 기간 중 지역 평소 대비 지수가 가장 큰 달: "
                f"{month_label(month.month)} ({month.season_index:.2f}) — 계절성을 확정하는 값이 아님"
            )
    if profile.ready("foreign") and profile.foreign_share_pct is not None:
        lines.append(f"외국인 결제 비중: {profile.foreign_share_pct:.1f}%")
    if profile.unknown_share_pct is not None:
        lines.append(
            f"성별·연령 미상 비중: {profile.unknown_share_pct:.1f}% — 미상 제외 비중이 더 정확하다는 뜻이 아님"
        )
    for name, rank in profile.ranks.items():
        rank_label = PROFILE_RANK_LABELS.get(name)
        if rank_label:
            lines.append(
                f"{rank_label}: 자료가 있는 {rank.regions}곳 중 아래에서 {rank.percentile:.1f}% 지점"
            )
    if profile.ready("external") and profile.external:
        population = profile.external.population
        if population and population.has_value:
            lines.append(
                f"주민등록인구(규모 참고): {population.count:,}명 · "
                f"{population.observed_at} · {population.source_name}"
            )
        registered = profile.external.registered_foreigners
        if registered and registered.has_value:
            lines.append(
                f"등록외국인 수(규모 참고): {registered.count:,}명 · "
                f"{registered.observed_at} · {registered.source_name}"
            )

    return ProfileSummary(
        **common,
        available=True,
        period_label=f"{month_label(profile.period_start)} ~ {month_label(profile.period_end)}",
        basis_note=PROFILE_BASIS_NOTES.get(profile.region_basis, PROFILE_BASIS_NOTES["unconfirmed"]),
        lines=tuple(lines),
        limitations=profile.limitations,
    )


def _request_draft(plan: PlanInput, choice_set: ChoiceSet, result: ReviewResult) -> RequestDraft | None:
    wants_request = any(
        (outcome := result.by_key(choice.question_key))
        and (option := outcome.option(choice.option_id or ""))
        and option.document
        and option.document.appendix == "request"
        for choice in choice_set.choices.values()
        if choice.changes_document and choice.option_id
    )
    if not wants_request:
        return None
    return RequestDraft(
        purpose="참여 점포의 외국인 결제 실적 확인",
        targets=f"참여 점포 목록 {PENDING_MARK}",
        period=f"{plan.period_start} ~ {plan.period_end}",
        metrics="참여 점포 외국인 결제금액·건수, 사업 전후 비교",
        to_confirm=(
            "점포 식별 가능 여부",
            "자료 제공·계약 조건과 비용",
            "참여자 결제와 점포 전체 결제의 차이",
        ),
    )


def build_document(
    plan: PlanInput,
    result: ReviewResult,
    choice_set: ChoiceSet,
    evidence: LoadResult,
    today: date,
) -> PlanDocument | DocumentBlocked:
    blocked = blocking_reasons(result, choice_set)
    if blocked:
        return DocumentBlocked(tuple(blocked))

    sections = {section.number: section for section in describe_plan(plan)}
    changes: list[Change] = []
    for outcome in result.outcomes:
        choice = choice_set.get(outcome.question_key)
        if choice is not None and choice.changes_document:
            _apply_choice(sections, plan, choice, choice_set, outcome, changes)

    pending = [*validate_plan(plan).pending, *pending_from_choices(choice_set, result), *_auto_records(result)]
    section8 = sections[8]
    for item in dict.fromkeys(pending):  # 중복 제거, 순서 유지
        if not any(line.text.startswith(item) for line in section8.lines):
            section8.lines.append(Line(f"{item} {PENDING_MARK}", state="pending"))

    data_kind = evidence.file.data_kind
    return PlanDocument(
        title=f"보완 기획안 — {plan.name}" if plan.name else "보완 기획안",
        created_on=today.isoformat(),
        data_notice=f"{DATA_KIND_LABELS[data_kind]} · 자료 버전 {evidence.file.dataset_version}",
        sections=tuple(sections[number] for number in sorted(sections)),
        changes=tuple(changes),
        profile_summary=_profile_summary(plan, evidence),
        evidence_refs=_evidence_refs(result, evidence),
        pending=tuple(dict.fromkeys(pending)),
        request_draft=_request_draft(plan, choice_set, result),
    )
