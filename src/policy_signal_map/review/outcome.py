"""검토 결과 형태.

서비스는 판정하지 않는다. 관측을 질문으로 전달하고 결정은 담당자가 한다 (최종기획서 1장).
'문제없음'(no_finding)과 '검토하지 않음'(not_reviewed)을 구분한다 (워크플로우 S02).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .rules import OptionSpec, RuleInfo, get_rule

OutcomeKind = Literal["question", "notice", "pending", "held", "not_reviewed"]


def question_key_of(rule_id: str, question: str | None = None) -> str:
    """4단계 선택이 참조하는 이름표를 만든다 (7지역확장계획.md 5장).

    규칙 하나가 질문 하나면 규칙 ID를 그대로 쓴다(지금까지와 같다).
    질문을 둘 이상 내는 규칙만 이름을 붙여 나눈다 — 같은 이름표를 쓰면 선택이 서로 덮어쓴다.
    """
    return rule_id if question is None else f"{rule_id}-{question}"


@dataclass(frozen=True)
class ReviewOutcome:
    rule_id: str
    # 4단계 선택이 참조하는 키. 질문마다 달라야 선택이 섞이지 않는다 (question_key_of)
    question_key: str
    # 같은 값을 가진 질문끼리 4단계에서 추가 입력(수집자료·담당자·주기)을 공유한다
    merge_group: str | None
    kind: OutcomeKind
    title: str
    message: str
    # 전달본이 확정 판정보다 참고 표시를 요구하는 규칙인지
    display_level: Literal["standard", "reference"] = "standard"
    why: str | None = None
    evidence_ids: tuple[str, ...] = ()
    scope_label: str | None = None
    region_note: str | None = None
    options: tuple[OptionSpec, ...] = ()
    related_fields: tuple[str, ...] = ()
    # 같은 자료를 묻는 다른 규칙 (3단계는 카드를 합치지 않고 서로를 가리킨다).
    # 화면 문구에는 번호가 아니라 related_titles를 쓴다 (사용자 결정 9/18)
    related_rule_ids: tuple[str, ...] = ()
    related_titles: tuple[str, ...] = ()
    # 문장 조립에 쓴 수치. 화면 표시용이며 LLM에는 넘기지 않는다
    observations: dict[str, Any] = field(default_factory=dict)
    # 이 결과를 만들 때 고른 문구 키. AI 참고 의견이 수치 없는 상황 설명을 찾는 데 쓴다
    context_keys: tuple[str, ...] = ()

    @property
    def needs_choice(self) -> bool:
        """질문만 선택이 필수다. 안내는 고를 수 있지만 필수가 아니다 (4보완선택계획 결정 ④·⑥)."""
        return self.kind == "question"

    def option(self, option_id: str) -> OptionSpec | None:
        return next((o for o in self.options if o.id == option_id), None)

    def to_llm_summary(self) -> dict[str, Any]:
        """AI 참고 의견용 요약. 금액·비중·구간 수 같은 수치를 넣지 않는다."""
        rule = get_rule(self.rule_id)
        lines = [rule.context(key) for key in self.context_keys]
        return {
            "rule_id": self.rule_id,
            "kind": self.kind,
            "title": self.title,
            "has_evidence": bool(self.evidence_ids),
            "scope_label": self.scope_label,
            "related_rule_ids": list(self.related_rule_ids),
            "context": [line for line in lines if line],
        }


@dataclass(frozen=True)
class NotReviewed:
    rule_id: str
    title: str
    scope_label: str
    reason: str


@dataclass(frozen=True)
class NoFinding:
    rule_id: str
    title: str


@dataclass(frozen=True)
class NotApplicable:
    """사업 유형이 달라 이번 기획에서는 실행하지 않은 질문 (7지역확장계획.md 6-2장).

    '물을 것이 없음'(no_finding)과도, '이번 범위에서 만들지 않음'(not_reviewed)과도 다르다.
    """

    rule_id: str
    title: str
    reason: str


@dataclass(frozen=True)
class ReviewResult:
    outcomes: tuple[ReviewOutcome, ...]
    # 조건을 확인했지만 물을 것이 없는 규칙 ("검토하지 않음"과 다름)
    no_finding: tuple[NoFinding, ...]
    not_reviewed: tuple[NotReviewed, ...]
    evidence_id: str | None
    # 사업 유형이 달라 실행하지 않은 질문. 기본값을 둬서 옛 호출부가 그대로 동작한다
    not_applicable: tuple[NotApplicable, ...] = ()

    @property
    def questions(self) -> tuple[ReviewOutcome, ...]:
        return tuple(o for o in self.outcomes if o.kind == "question")

    def by_key(self, question_key: str) -> ReviewOutcome | None:
        return next((o for o in self.outcomes if o.question_key == question_key), None)

    def in_merge_group(self, merge_group: str) -> tuple[ReviewOutcome, ...]:
        """4단계에서 추가 입력을 공유할 질문들."""
        return tuple(o for o in self.outcomes if o.merge_group == merge_group and o.kind == "question")


def not_reviewed_from(rule: RuleInfo) -> NotReviewed:
    return NotReviewed(
        rule_id=rule.id,
        title=rule.title,
        scope_label=rule.scope_label,
        reason=rule.message("not_reviewed"),
    )
