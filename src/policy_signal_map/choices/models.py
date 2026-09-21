"""보완 선택 데이터 형태 (워크플로우 S03, 4보완선택계획.md 3장).

서비스는 대신 고르지 않는다. 비어 있는 값은 추측해 채우지 않고 "추가 확정 필요"로 남긴다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Decision(StrEnum):
    KEEP_ORIGINAL = "keep_original"
    ADOPT = "adopt"
    MODIFY = "modify"
    HOLD = "hold"


class Availability(StrEnum):
    AVAILABLE = "available"
    NEGOTIATING = "negotiating"
    UNAVAILABLE = "unavailable"


DECISION_LABELS = {
    Decision.KEEP_ORIGINAL: "원안 유지",
    Decision.ADOPT: "채택",
    Decision.MODIFY: "수정",
    Decision.HOLD: "보류",
}

AVAILABILITY_LABELS = {
    Availability.AVAILABLE: "확보 가능",
    Availability.NEGOTIATING: "협의 중",
    Availability.UNAVAILABLE: "확보 어려움",
}


@dataclass(frozen=True)
class ExecutionInput:
    """실행 조건. 같은 merge_group 질문들이 한 번만 입력해 함께 쓴다."""

    collect_items: tuple[str, ...] = ()
    availability: Availability | None = None
    owner: str = ""
    cycle: str = ""

    def pending_labels(self) -> list[str]:
        pending = []
        if not self.owner:
            pending.append("수집 담당자")
        if not self.cycle:
            pending.append("확인 주기")
        if self.availability is None:
            pending.append("자료 확보 여부")
        elif self.availability is not Availability.AVAILABLE:
            pending.append(f"자료 확보 협의 ({AVAILABILITY_LABELS[self.availability]})")
        return pending


@dataclass(frozen=True)
class Choice:
    question_key: str
    rule_id: str
    decision: Decision
    merge_group: str | None = None
    option_id: str | None = None
    modified_text: str | None = None
    reason: str = ""
    evidence_ids: tuple[str, ...] = ()
    needs_recheck: bool = False
    # 이 선택이 어떤 입력 항목에 달려 있는지. 질문 단위로 재확인하려고 질문에서 받아 둔다
    # (7지역확장계획.md 5장). 비어 있으면 규칙 값을 쓴다 — 옛 방식과 같다
    related_fields: tuple[str, ...] = ()
    # 이 선택을 저장할 때 사용한 근거 문맥. 자료 자체가 바뀌면 입력 원안이 같아도
    # 값 기반 질문의 결론이 달라질 수 있어 다시 확인한다. dataset_version이 None이면
    # 버전 문맥을 저장하기 전의 선택으로 보고 호환을 위해 버전 비교를 건너뛴다.
    evidence_dataset_version: str | None = None
    evidence_thresholds_version: str | None = None

    @property
    def changes_document(self) -> bool:
        return self.decision in (Decision.ADOPT, Decision.MODIFY)


@dataclass(frozen=True)
class ArchivedChoice:
    choice: Choice
    reason: str = "기획 또는 근거 변경으로 더 이상 해당하지 않음"


@dataclass
class ChoiceSet:
    choices: dict[str, Choice] = field(default_factory=dict)
    executions: dict[str, ExecutionInput] = field(default_factory=dict)
    # 지금까지 보관한 선택 전체 (기록용)
    archived: list[ArchivedChoice] = field(default_factory=list)
    # 가장 최근 기획·근거 변경으로 보관한 선택. 4단계 안내는 이것만 보여 준다.
    # 전체를 보여 주면 원안을 여러 번 바꿀 때 같은 질문이 쌓이고, 다시 답한 질문도 계속 보관됐다고 나온다 (6-5e)
    last_archived: list[ArchivedChoice] = field(default_factory=list)

    def get(self, question_key: str) -> Choice | None:
        return self.choices.get(question_key)

    def put(self, choice: Choice) -> None:
        self.choices[choice.question_key] = choice

    def remove(self, question_key: str) -> Choice | None:
        return self.choices.pop(question_key, None)

    def execution_for(self, merge_group: str | None) -> ExecutionInput | None:
        return self.executions.get(merge_group) if merge_group else None

    def set_execution(self, merge_group: str, execution: ExecutionInput) -> None:
        self.executions[merge_group] = execution

    @property
    def needs_recheck_keys(self) -> tuple[str, ...]:
        return tuple(key for key, choice in self.choices.items() if choice.needs_recheck)
