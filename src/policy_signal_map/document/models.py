"""보완 기획안 문서 구조 (최종기획서 6장, 5보완기획안계획.md 2장)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

LineState = Literal["original", "changed", "added", "pending"]

SECTION_TITLES = {
    1: "사업 개요",
    2: "목적·대상",
    3: "일정",
    4: "혜택·사용처",
    5: "모집·정산",
    6: "예산 상태",
    7: "성과 측정계획",
    8: "추가 확인사항",
}

# 표시 마크업(Markdown 굵게)은 넣지 않는다. 문서로 내보낼 때 render.py가 강조로 바꾼다
PENDING_MARK = "[추가 확정 필요]"
NOT_IN_PLAN = f"원안에 기재 없음 {PENDING_MARK}"


@dataclass(frozen=True)
class Line:
    text: str
    key: str | None = None
    state: LineState = "original"
    change_id: str | None = None
    evidence_ids: tuple[str, ...] = ()


@dataclass
class Section:
    number: int
    lines: list[Line] = field(default_factory=list)

    @property
    def title(self) -> str:
        return SECTION_TITLES[self.number]

    @property
    def changed(self) -> bool:
        return any(line.state in ("changed", "added") for line in self.lines)

    def find(self, key: str) -> int | None:
        return next((i for i, line in enumerate(self.lines) if line.key == key), None)


@dataclass(frozen=True)
class Change:
    change_id: str
    section: int
    before: str | None
    after: str
    rule_id: str  # 기록용 내부 값. 화면·문서에는 rule_title을 쓴다
    rule_title: str
    option_id: str | None
    decision_label: str
    evidence_ids: tuple[str, ...] = ()
    modified: bool = False


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    data_kind: str
    dataset_version: str
    scope_label: str
    period_label: str
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class ProfileSummary:
    """별첨 2에 남기는 고른 지역의 소비 프로필 요약."""

    region_label: str
    dataset_version: str
    data_kind: str
    available: bool
    note: str | None = None
    period_label: str = ""
    basis_note: str = ""
    lines: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class RequestDraft:
    purpose: str
    targets: str
    period: str
    metrics: str
    to_confirm: tuple[str, ...]


@dataclass(frozen=True)
class PlanDocument:
    title: str
    created_on: str
    data_notice: str
    sections: tuple[Section, ...]
    changes: tuple[Change, ...]
    profile_summary: ProfileSummary
    evidence_refs: tuple[EvidenceRef, ...]
    pending: tuple[str, ...]
    request_draft: RequestDraft | None

    @property
    def unchanged_sections(self) -> int:
        return sum(1 for section in self.sections if not section.changed)


@dataclass(frozen=True)
class DocumentBlocked:
    """아직 문서를 만들 수 없는 상태 (미선택·재확인 필요)."""

    reasons: tuple[str, ...]
