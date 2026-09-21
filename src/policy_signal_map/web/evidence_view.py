"""2단계 근거 확인 화면에 넘길 데이터 조립.

계산은 evidence/ 결과를 그대로 쓰고, 여기서는 레코드 선택·표시 여부·문장만 정한다.
템플릿에는 원래 값(int·Fraction·None)을 넘겨 formatting 필터로 표시한다.
규칙 상세: 2근거확인화면계획.md 6장.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from ..evidence.compare import MonthPair, compare_record
from ..evidence.loader import LoadResult, find_record
from ..evidence.schema import STATUS_LABELS, Applicability, EvidenceFile, EvidenceRecord
from ..evidence.summary import PairSummary, PeriodTotals, period_totals, summarize_pairs
from ..formatting import HUNDRED_MILLION, amount_unit, month_label, pair_label, period_label
from ..plan.models import PlanInput
from ..plan.regions import region_label
from ..review.context import region_display, select_main, sparse_reason

METHOD_LINES = (
    "전체 분모 외국인 비중 = 외국인 결제금액 ÷ 전체 결제금액 × 100",
    "미상 제외 외국인 비중 = 외국인 결제금액 ÷ (전체 결제금액 − 미상 금액) × 100",
    "변화 방향은 반올림한 비중이 아니라 원래 금액의 교차곱으로 판정합니다",
    "기간 합산 비중은 월별 비중의 평균이 아니라 금액을 모두 더한 뒤 계산합니다",
    "비교 A(금액 vs 전체 분모 비중)와 비교 B(전체 분모 vs 미상 제외 비중)는 따로 계산하며 하나의 점수로 합치지 않습니다",
)

FIXED_INTERPRETATION_NOTES = (
    "금액과 비중은 서로 다른 질문에 답합니다. 방향이 다르다고 비중이 잘못된 지표라는 뜻은 아닙니다.",
    "이 자료는 계획 중인 사업이 시행되기 전의 관측이며, 사업의 성과가 아닙니다.",
    "‘미상’은 성별 코드가 확인되지 않은 결제이며, 미상 제외 비중이 더 정확한 값이라는 뜻은 아닙니다.",
)

MISSING_MAIN_MESSAGE = "전국 근거 레코드가 없어 비교를 표시하지 않습니다. 데이터 담당에게 확인해 주세요."

HOLD_EXAMPLE_NOTE = "사용자가 입력한 지역의 자료가 아닙니다. 자료가 부족할 때 화면이 어떻게 보이는지 보여주는 예시입니다."


@dataclass(frozen=True)
class MonthRow:
    month: str
    label: str
    status: str
    foreign_amount: int | None
    total_amount: int | None
    foreign_share_pct: Fraction | None
    unknown_share_pct: Fraction | None
    known_only_share_pct: Fraction | None
    warnings: tuple[str, ...]

    @property
    def held(self) -> bool:
        return self.status != "ok"

    @property
    def status_label(self) -> str:
        return STATUS_LABELS[self.status]


@dataclass(frozen=True)
class PairRow:
    label: str
    pair: MonthPair

    @property
    def held(self) -> bool:
        return self.pair.status == "skipped"


@dataclass(frozen=True)
class RecordView:
    evidence_id: str
    scope_label: str
    period_label: str
    unit: str
    months: tuple[MonthRow, ...]
    pairs: tuple[PairRow, ...]
    summary: PairSummary
    totals: PeriodTotals
    applicability: Applicability
    limitations: tuple[str, ...]

    @property
    def source_label(self) -> str:
        """문장 안에서 쓰는 자료 출처 이름 ("전국" / "강원특별자치도")."""
        return self.scope_label.removeprefix("시도 ").removeprefix("시군구 ")


@dataclass(frozen=True)
class EvidenceView:
    main: RecordView | None
    status_kind: str  # allowed | needs_review | blocked | missing
    show_numbers: bool
    show_summary: bool
    summary_sentence: str | None
    held_message: str | None
    missing_main_message: str | None
    # 주 근거 칩에 쓰는 범위 글자 (전국 / 지역 이름). review/context.py가 정한 것을 그대로 쓴다
    main_scope_label: str | None
    # 사용자가 1단계에서 고른 지역. 자료 범위와 다를 수 있어 화면에 함께 보여 준다 —
    # 같은 시도 안의 시군구는 자료가 같아서, 무엇을 골랐는지 적어 두지 않으면 화면이 안 바뀐 것처럼 보인다
    plan_region_label: str | None
    region_note: str | None
    # 사업 기간과 자료 기간이 겹치지 않을 때 한 줄 (시나리오 24·30)
    period_note: str | None
    # 표본이 부족해 수치를 접었을 때, 어떤 달을 계산하지 못했는지만 보여 준다
    show_held_months: bool
    hold_examples: tuple[RecordView, ...]
    chart_data: dict[str, Any]
    dataset_version: str
    data_kind: str
    method_lines: tuple[str, ...] = METHOD_LINES
    # 해석 한계는 누가 쓴 문장인지 나눠 보여 준다. 근거 파일의 한계(분석 담당)와 서비스 고정 원칙이
    # 비슷한 뜻을 담을 수 있는데, 분석 담당 문장을 서비스가 고치거나 골라 빼지 않기 위해서다 (S2, 2026-09-17)
    data_limitations: tuple[str, ...] = ()
    service_notes: tuple[str, ...] = field(default=FIXED_INTERPRETATION_NOTES)


# ---------------------------------------------------------------- 레코드


def _share(numerator: int | None, denominator: int | None) -> Fraction | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return Fraction(numerator, denominator) * 100


def build_record_view(record: EvidenceRecord) -> RecordView:
    scope = record.scope
    same_year = scope.period_start[:4] == scope.period_end[:4]

    months = []
    for m in record.months:
        # 비중은 파일 값이 아니라 정수 금액으로 다시 계산한다 (계산과 표시가 같은 원천을 쓰게)
        ok = m.calculation_status == "ok"
        T, U = m.total_amount, m.unknown_amount
        months.append(
            MonthRow(
                month=m.month,
                label=month_label(m.month, same_year),
                status=m.calculation_status,
                foreign_amount=m.foreign_amount,
                total_amount=T,
                foreign_share_pct=_share(m.foreign_amount, T) if ok else None,
                unknown_share_pct=_share(U, T) if ok else None,
                known_only_share_pct=_share(m.foreign_amount, None if T is None or U is None else T - U) if ok else None,
                warnings=m.warnings,
            )
        )

    pairs = compare_record(record)
    ok_totals = [m.total_amount for m in record.months if m.calculation_status == "ok" and m.total_amount is not None]
    # 행정표준코드는 화면에 쓰지 않는다. 지역은 이름으로 바꿔 보여 준다 (review/context.py)
    kind = {"national": "", "sido": "시도 ", "sigungu": "시군구 "}[scope.geographic_scope]
    scope_label = f"{kind}{region_display(scope.geographic_scope, scope.region_key)}"

    return RecordView(
        evidence_id=record.evidence_id,
        scope_label=scope_label,
        period_label=period_label(scope.period_start, scope.period_end),
        unit=amount_unit(max(ok_totals) if ok_totals else None),
        months=tuple(months),
        pairs=tuple(PairRow(pair_label(p.month_0, p.month_1), p) for p in pairs),
        summary=summarize_pairs(pairs),
        totals=period_totals(record),
        applicability=record.applicability["R07"],
        limitations=record.limitations,
    )


# ---------------------------------------------------------------- 문장


def summary_sentence(record_view: RecordView) -> str:
    """요약 문장. 판정 단어를 쓰지 않고, 반대 구간이 없을 때 '달랐다'는 문구를 쓰지 않는다 (8-3, 12장)."""
    s = record_view.summary
    period = record_view.period_label
    N, k, m = s.comparable_count, s.opposite_a_count, s.skipped_count

    if N == 0:
        return "비교 가능한 인접 월 구간이 없어 금액·비중 방향 비교를 보류합니다."
    if k >= 1:
        sentence = (
            f"{period} {record_view.source_label} 자료에서 비교 가능한 {N}개 인접 월 구간 중 {k}개 구간에서 "
            "외국인 결제금액과 전체 분모 비중의 변화 방향이 달랐습니다."
        )
    else:
        sentence = (
            f"{period} {record_view.source_label} 자료에서 비교 가능한 {N}개 인접 월 구간에서는 "
            "외국인 결제금액과 전체 분모 비중이 서로 반대 방향으로 움직이지 않았습니다."
        )
    if m >= 1:
        sentence += f" 자료가 부족한 {m}개 구간은 비교하지 않았습니다."
    return sentence


# ---------------------------------------------------------------- 차트


def _chart_amount(value: int | None, unit: str) -> int | float | None:
    if value is None:
        return None
    if unit == "억원":
        return round(float(Fraction(value, HUNDRED_MILLION)), 2)
    return value


def _chart_share(value: Fraction | None) -> float | None:
    return None if value is None else round(float(value), 4)


def chart_data(record_view: RecordView) -> dict[str, Any]:
    """JSON으로 넘길 값. int·float·None·str만 쓴다 (Fraction은 JSON 변환 오류)."""
    return {
        "unit": record_view.unit,
        "labels": [m.label for m in record_view.months],
        "status": [m.status for m in record_view.months],
        "foreign_amount": [
            _chart_amount(m.foreign_amount, record_view.unit) if not m.held else None for m in record_view.months
        ],
        "share_all_pct": [_chart_share(m.foreign_share_pct) for m in record_view.months],
        "share_known_pct": [_chart_share(m.known_only_share_pct) for m in record_view.months],
    }


# ---------------------------------------------------------------- 전체


def _hold_examples(file: EvidenceFile, main: EvidenceRecord | None) -> tuple[RecordView, ...]:
    """"자료가 부족한 경우 보기"에 넣을 예시. 합성 파일에서만, 한 건만 보여 준다.

    실제 파일에서는 표시하지 않는다: 사용자 지역과 무관한 실제 지역 수치가 "예시"로 보이지 않게.
    한 건으로 제한하는 이유: 시연 파일에 지역 레코드가 늘면서 계산 불가 월이 있는 레코드가 여럿이 됐다.
    여러 건을 늘어놓으면 "예시"가 사용자 지역의 자료처럼 읽히고 화면도 길어진다. 다른 지역의 보류
    화면은 그 지역을 직접 골라서 보면 된다 (파일 순서상 앞에 둔 레코드를 예시로 쓴다).
    """
    if file.data_kind != "synthetic":
        return ()
    for record in file.records:
        if record is main or record.applicability["R07"].status == "blocked":
            continue
        if any(m.calculation_status != "ok" for m in record.months):
            return (build_record_view(record),)
    return ()


def period_note(plan: PlanInput, record: EvidenceRecord | None) -> str | None:
    """사업 기간이 자료 기간과 겹치지 않으면 한 줄로 알린다. 자료를 막지는 않는다 (시나리오 24·30)."""
    if record is None or not plan.period_start or not plan.period_end:
        return None
    scope = record.scope
    plan_start, plan_end = plan.period_start[:7], plan.period_end[:7]
    if plan_start > plan_end:
        return None  # 기간 입력 오류는 1단계에서 이미 잡는다
    data_period = period_label(scope.period_start, scope.period_end)
    plan_period = period_label(plan_start, plan_end)
    if plan_start > scope.period_end:
        return f"이 자료는 사업 기간 이전의 흐름입니다. (자료 {data_period} / 사업 {plan_period})"
    if plan_end < scope.period_start:
        return f"이 자료는 사업 기간 이후의 흐름입니다. (자료 {data_period} / 사업 {plan_period})"
    return None


def build_evidence_view(plan: PlanInput, result: LoadResult) -> EvidenceView:
    file = result.file
    selection = select_main(file, plan)
    main_record = selection.record
    main = build_record_view(main_record) if main_record else None

    if main is None:
        status_kind = "missing"
        held = None
    else:
        status_kind = main.applicability.status
        reason = main.applicability.reason
        held = {
            "allowed": None,
            "needs_review": f"근거 기반 결론을 보류합니다. 확인할 내용: {reason}",
            "blocked": f"현재 자료로 금액·비중 비교를 사용할 수 없습니다. 사유: {reason}",
        }[status_kind]

    # blocked는 기능을 실행하지 않으므로 수치를 하나도 보여주지 않는다 (워크플로우 9-2)
    show_numbers = main is not None and status_kind != "blocked"
    show_summary = main is not None and status_kind == "allowed"

    # 표본이 부족한 지역 자료는 차트·요약을 접고 계산하지 못한 달만 알린다
    sparse = sparse_reason(main_record) if main_record else None
    if sparse:
        sparse = f"자료가 부족해 이 지역의 월별 비교를 보여 주지 않습니다. (사유: {sparse})"
    if sparse:
        show_numbers = False
        show_summary = False
        held = sparse if held is None else f"{held} {sparse}"

    return EvidenceView(
        main=main,
        status_kind=status_kind,
        show_numbers=show_numbers,
        show_summary=show_summary,
        summary_sentence=summary_sentence(main) if show_summary and main else None,
        held_message=held,
        missing_main_message=MISSING_MAIN_MESSAGE if main is None else None,
        main_scope_label=selection.scope_label,
        plan_region_label=region_label(plan.region) or None,
        region_note=selection.region_note,
        period_note=period_note(plan, main_record),
        show_held_months=bool(sparse),
        hold_examples=_hold_examples(file, main_record),
        chart_data=chart_data(main) if show_numbers and main else {},
        dataset_version=file.dataset_version,
        data_kind=file.data_kind,
        data_limitations=main.limitations if main else (),
    )
