from datetime import date

from policy_signal_map.choices.models import ChoiceSet
from policy_signal_map.choices.selection import apply_choice
from policy_signal_map.config import (
    LEGACY_DEMO_EVIDENCE_PATH as DEFAULT_EVIDENCE_PATH,
)
from policy_signal_map.document.builder import build_document
from policy_signal_map.evidence.loader import load_evidence
from policy_signal_map.plan.models import sample_plan
from policy_signal_map.review.engine import run_review

TODAY = date(2026, 9, 17)
EVIDENCE = load_evidence(DEFAULT_EVIDENCE_PATH)
ADOPT_A = {
    "decision": "adopt",
    "option_id": "A",
    "owner": "관광과 김담당",
    "cycle": "월 1회",
    "availability": "available",
}


def plan_with(**changes):
    plan = sample_plan()
    # 문서 생성만 보는 시험이라 사업 유형으로 질문을 걸러내지 않는다 (review/packs.py)
    plan.business_type = None
    # 대상 기본값에서 '외국인'을 빼 둔다. 두면 외국인 대상 기반 확인까지 답해야 해서
    # 문서 생성과 상관없는 선택이 시험마다 늘어난다. 그 질문이 필요한 시험은 대상을 직접 적는다
    plan.target = "관내 주민"
    for key, value in changes.items():
        setattr(plan, key, value)
    return plan


def review_of(plan, evidence=EVIDENCE):
    return run_review(plan, evidence)


def choose(result, choice_set: ChoiceSet, rule_id: str, form: dict, collect_items=()) -> dict:
    outcome = next(o for o in result.outcomes if o.rule_id == rule_id)
    return apply_choice(choice_set, outcome, form, list(collect_items))


def document_for(plan, choice_set: ChoiceSet | None = None, evidence=EVIDENCE, today=TODAY):
    result = review_of(plan, evidence)
    return build_document(plan, result, choice_set or ChoiceSet(), evidence, today), result


def section_of(document, number: int):
    return next(section for section in document.sections if section.number == number)


def texts(document, number: int) -> list[str]:
    return [line.text for line in section_of(document, number).lines]
