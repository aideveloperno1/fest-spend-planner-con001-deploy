"""검토 규칙 실행 (3검토질문계획.md 4장, docs/review_rules.md)."""

import json
import re
from pathlib import Path

import pytest
from evidence_helpers import base_data, fixture_path

from policy_signal_map.config import (
    LEGACY_DEMO_EVIDENCE_PATH as DEFAULT_EVIDENCE_PATH,
)
from policy_signal_map.evidence.loader import load_evidence
from policy_signal_map.plan.models import (
    Budget,
    BudgetStatus,
    DataStatus,
    Goal,
    IndicatorUse,
    Metric,
    PlanInput,
    Region,
    RegionLevel,
    sample_plan,
)
from policy_signal_map.review.engine import RUN_ORDER, check_rule_functions, run_review
from policy_signal_map.review.rules import (
    FORBIDDEN_WORDS,
    load_rule_catalog,
    merge_group_label,
    rules_by_id,
)

DEMO = load_evidence(DEFAULT_EVIDENCE_PATH)


def plan(**changes) -> PlanInput:
    base = sample_plan()
    # 규칙의 실행 조건만 보는 시험이라 사업 유형으로 질문을 걸러내지 않는다
    # (유형을 고르지 않은 기획은 실행할 수 있는 질문을 모두 켠다 — review/packs.py)
    base.business_type = None
    # 기본 예시는 R05 추가 확정 필요가 있으므로, 조건별 테스트에서 값을 채워 끌 수 있게 한다
    for key, value in changes.items():
        setattr(base, key, value)
    return base


def outcome(result, rule_id: str):
    return next((o for o in result.outcomes if o.rule_id == rule_id), None)


def test_rule_functions_exist_for_every_implemented_rule():
    check_rule_functions()
    ids = {rule.id for rule in load_rule_catalog() if rule.scope in ("implement", "basic")}
    assert ids == set(RUN_ORDER)


def test_rule_without_code_is_caught_at_startup_not_on_request(monkeypatch):
    """규칙만 추가하고 코드를 만들지 않으면 화면을 열 때가 아니라 시작할 때 멈춰야 한다."""
    from dataclasses import replace

    import policy_signal_map.review.engine as engine_module

    extra = replace(rules_by_id()["R05"], id="R99", title="새 규칙")
    monkeypatch.setattr(engine_module, "load_rule_catalog", lambda: (*load_rule_catalog(), extra))

    with pytest.raises(ValueError, match="R99"):
        engine_module.check_rule_functions()

    # 요청 처리(run_review)는 이 검사를 다시 하지 않는다 (시작 때 이미 확인)
    assert run_review(plan(), DEMO).outcomes


def test_startup_check_runs_when_module_is_imported():
    import ast
    from pathlib import Path

    source = Path(__file__).parent.parent / "src" / "policy_signal_map" / "review" / "engine.py"
    module = ast.parse(source.read_text(encoding="utf-8"))
    top_level_calls = [
        node.value.func.id
        for node in module.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
    ]
    assert "check_rule_functions" in top_level_calls


def test_docs_and_json_share_rule_ids():
    text = (Path(__file__).parent.parent / "docs" / "review_rules.md").read_text(encoding="utf-8")
    for rule in load_rule_catalog():
        assert f"## {rule.id} " in text, rule.id


def test_direct_indicator_use_asks_question():
    result = run_review(plan(), DEMO)
    r07 = outcome(result, "R07")
    assert r07.kind == "question"
    assert "외국인 결제금액 확대인가요" in r07.message
    assert r07.evidence_ids == ("DEMO-R07-SIGUNGU-강원-강릉시",)
    assert [o.id for o in r07.options] == ["A", "B", "C", "D"]


def test_reference_indicator_use_is_notice_without_error_wording():
    r07 = outcome(run_review(plan(indicator_use=IndicatorUse.REFERENCE), DEMO), "R07")
    assert r07.kind == "notice"
    assert "그대로 두어도 됩니다" in r07.message
    # 참고 현황으로 써도 "해석 조건 명시"는 고를 수 있어야 한다 (선택은 필수 아님)
    assert [o.id for o in r07.options] == ["B"]


def test_basic_check_questions_have_options():
    result = run_review(plan(target="방한 관광객", goals=[Goal.STORE_USAGE], usage_place="", period_start="2026-10-01", period_end="2026-10-20"), DEMO)
    for rule_id in ("R01", "R03", "R04"):
        item = outcome(result, rule_id)
        assert item.kind == "question"
        assert [o.id for o in item.options] == ["A", "B"], rule_id
        assert all(o.where and o.need and o.load for o in item.options), rule_id


def test_shared_execution_fields_span_participation_group():
    result = run_review(plan(target="방한 관광객", period_start="2026-10-01", period_end="2026-10-20"), DEMO)
    with_execution = {
        item.rule_id
        for item in result.outcomes
        for option in item.options
        if option.execution_fields
    }
    assert with_execution == {"R07", "R03", "R04", "R12"}


def test_held_and_pending_have_no_options():
    held = outcome(run_review(plan(), load_evidence(fixture_path("missing_month"))), "R07")
    assert held.kind == "held" and held.options == ()
    pending = outcome(run_review(plan(), DEMO), "R05")
    assert pending.kind == "pending" and pending.options == ()


def test_unknown_indicator_use_offers_choices_without_conclusion():
    r07 = outcome(run_review(plan(indicator_use=IndicatorUse.UNKNOWN), DEMO), "R07")
    assert r07.kind == "question"
    assert "어느 쪽에 가까운지" in r07.message


def test_why_uses_observed_counts():
    r07 = outcome(run_review(plan(), DEMO), "R07")
    assert r07.why == (
        "2026년 1~6월 강원특별자치도 강릉시 자료에서 비교 가능한 5개 인접 월 구간 중 2개 구간에서 "
        "외국인 결제금액과 전체 분모 비중의 변화 방향이 달랐습니다."
    )
    assert r07.observations["opposite_a_count"] == 2


def test_why_names_the_national_source_for_national_plan():
    """지역을 고르지 않으면 문장도 '전국 자료에서'로 남는다 (출처를 글자로 고정하지 않는다)."""
    r07 = outcome(run_review(plan(region=Region(RegionLevel.NATIONAL)), DEMO), "R07")
    assert r07.why.startswith("2026년 1~6월 전국 자료에서")


def test_same_direction_does_not_reuse_opposite_wording(tmp_path: Path):
    evidence = load_evidence(fixture_path("same_direction"))
    r07 = outcome(run_review(plan(), evidence), "R07")
    assert "달랐습니다" not in r07.why
    assert "반대 방향으로 움직이지 않았습니다" in r07.why


def test_goal_and_metric_mismatch_is_mentioned_first():
    r07 = outcome(run_review(plan(goals=[Goal.FOREIGN_AMOUNT], metrics=[Metric.FOREIGN_SHARE]), DEMO), "R07")
    assert r07.message.startswith("입력한 목표는 ‘외국인 결제금액 확대’인데 성과지표는 ‘외국인 결제 비중’입니다.")


def test_rule_does_not_apply_without_card_metric():
    result = run_review(plan(metrics=[Metric.COUPON_USAGE]), DEMO)
    assert outcome(result, "R07") is None
    assert "R07" in [n.rule_id for n in result.no_finding]


def test_blocked_and_needs_review_are_held(tmp_path: Path):
    for status, expected in (("blocked", "사용할 수 없습니다"), ("needs_review", "결론을 보류합니다")):
        data = base_data()
        data["records"][0]["applicability"]["R07"] = {"status": status, "reason": "지역 기준 확인 중"}
        path = tmp_path / f"{status}.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        r07 = outcome(run_review(plan(), load_evidence(path)), "R07")
        assert r07.kind == "held"
        assert expected in r07.message
        assert "지역 기준 확인 중" in r07.message
        assert r07.options == ()


def test_no_comparable_pairs_is_held():
    r07 = outcome(run_review(plan(), load_evidence(fixture_path("missing_month"))), "R07")
    assert r07.kind == "held"
    assert "비교 가능한 인접 월 구간이 없어" in r07.message


def test_missing_national_record_is_held(tmp_path: Path):
    data = base_data()
    data["records"][0]["scope"].update(geographic_scope="sido", region_key="DEMO-SIDO-A")
    path = tmp_path / "sido_only.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    r07 = outcome(run_review(plan(), load_evidence(path)), "R07")
    assert r07.kind == "held"
    assert "전국 근거 자료가 없어" in r07.message


def test_region_note_and_scope_label_match_evidence_screen():
    r07 = outcome(run_review(plan(), DEMO), "R07")
    assert r07.scope_label == "강원특별자치도 강릉시 범위 참고 — 선택 지역의 진단이 아님"
    assert r07.region_note is None  # 고른 지역 자료를 그대로 써서 넓혔다는 안내가 없다

    national = plan(region=Region(RegionLevel.NATIONAL))
    assert outcome(run_review(national, DEMO), "R07").region_note is None


def test_r01_asks_when_store_goal_has_no_usage_place():
    assert outcome(run_review(plan(goals=[Goal.STORE_USAGE], usage_place=""), DEMO), "R01").kind == "question"
    assert outcome(run_review(plan(goals=[Goal.STORE_USAGE]), DEMO), "R01") is None
    assert outcome(run_review(plan(usage_place=""), DEMO), "R01") is None


def test_r03_asks_when_target_is_tourist_with_card_metric():
    r03 = outcome(run_review(plan(target="방한 관광객"), DEMO), "R03")
    assert r03.kind == "question"
    assert "관광객과 거주 외국인을 구분하지 않습니다" in r03.message
    assert outcome(run_review(plan(target="외국인 전체"), DEMO), "R03") is None
    assert outcome(run_review(plan(target="방한 관광객", metrics=[Metric.COUPON_USAGE]), DEMO), "R03") is None


def test_r04_asks_for_short_period_with_direct_evaluation():
    short = plan(period_start="2026-10-01", period_end="2026-10-20")
    assert outcome(run_review(short, DEMO), "R04").kind == "question"
    assert outcome(run_review(plan(), DEMO), "R04") is None

    reference = plan(period_start="2026-10-01", period_end="2026-10-20", indicator_use=IndicatorUse.REFERENCE)
    assert outcome(run_review(reference, DEMO), "R04") is None


def test_r05_lists_pending_items():
    r05 = outcome(run_review(plan(), DEMO), "R05")
    assert r05.kind == "pending"
    assert "예산 (미정)" in r05.message and "자료 확보 상태" in r05.message

    filled = plan(budget=Budget(BudgetStatus.AMOUNT, krw=1000, raw="1000"), data_status=DataStatus.SECURED)
    assert outcome(run_review(filled, DEMO), "R05") is None


def test_r06_is_not_reviewed():
    """고액 소비 근거는 이번 범위에서 분석 예시로만 둔다. 사용처 업종(R02)은 이제 실행한다."""
    result = run_review(plan(), DEMO)
    not_reviewed = {n.rule_id: n for n in result.not_reviewed}
    assert set(not_reviewed) == {"R06"}
    assert not_reviewed["R06"].scope_label == "분석 예시"


def test_related_questions_point_to_each_other_without_merging_cards():
    result = run_review(plan(target="방한 관광객", period_start="2026-10-01", period_end="2026-10-20"), DEMO)
    r07, r03, r04 = outcome(result, "R07"), outcome(result, "R03"), outcome(result, "R04")
    assert {o.merge_group for o in (r07, r03, r04)} == {"participation_data"}
    assert set(r07.related_rule_ids) == {"R03", "R04"}
    assert set(r03.related_rule_ids) == {"R07", "R04"}
    # 외국인 대상 기반 확인은 다른 묶음이라 서로 가리키지 않는다
    assert "R12" not in set(r07.related_rule_ids)


def test_every_merge_group_has_a_readable_name():
    """묶음 이름은 보완 기획안에 그대로 실린다. 내부 키가 사용자에게 보이면 안 된다."""
    assert merge_group_label("participation_data") == "참여 실적 자료"
    for rule in load_rule_catalog():
        if rule.merge_group:
            assert merge_group_label(rule.merge_group) != rule.merge_group


def test_question_keys_are_unique_so_choices_do_not_mix():
    """4단계 선택이 질문마다 따로 저장되려면 키가 겹치면 안 된다."""
    result = run_review(plan(target="방한 관광객", period_start="2026-10-01", period_end="2026-10-20"), DEMO)
    keys = [o.question_key for o in result.outcomes]
    assert keys == sorted(set(keys), key=keys.index)
    # 규칙 하나가 질문 하나면 이름표는 규칙 번호 그대로, 둘 이상이면 `규칙ID-이름`
    assert result.by_key("R03").rule_id == "R03"
    assert result.by_key("R04-period").rule_id == "R04"
    assert {o.rule_id for o in result.in_merge_group("participation_data")} == {"R07", "R03", "R04"}


def test_all_json_messages_avoid_judgment_words():
    """실행되지 않은 문구도 검사한다 (보류·검토하지 않음 등). 상황 설명도 같은 기준이다."""
    for rule in load_rule_catalog():
        for key, text in {**rule.messages, **rule.llm_context}.items():
            for word in FORBIDDEN_WORDS:
                assert word not in text, (rule.id, key, word)


def test_llm_context_has_no_numbers():
    """AI에 넘기는 상황 설명에 수치가 들어가면 안 된다 (6LLM참고의견계획.md 3장)."""
    for rule in load_rule_catalog():
        for key, text in rule.llm_context.items():
            assert not re.search(r"\d|[%원]", text), (rule.id, key)
            assert "{" not in text, (rule.id, key)  # 값을 채워 넣는 자리도 두지 않는다


def test_every_context_key_used_in_review_has_a_sentence():
    """실행 중 나온 키가 상황 설명을 못 찾으면 AI가 맥락 없이 답하게 된다."""
    cases = [
        {},
        {"indicator_use": IndicatorUse.REFERENCE},
        {"indicator_use": IndicatorUse.UNKNOWN},
        {"goals": [Goal.FOREIGN_AMOUNT]},
        {"target": "방한 관광객"},
        {"goals": [Goal.STORE_USAGE], "usage_place": ""},
        {"period_start": "2026-10-01", "period_end": "2026-10-20"},
    ]
    seen: set[tuple[str, str]] = set()
    for case in cases:
        for item in run_review(plan(**case), DEMO).outcomes:
            for key in item.context_keys:
                assert rules_by_id()[item.rule_id].context(key), (item.rule_id, key)
                seen.add((item.rule_id, key))
    assert ("R07", "why_opposite") in seen and ("R07", "goal_mismatch_prefix") in seen


def test_llm_summary_carries_context_lines():
    result = run_review(plan(), DEMO)
    summary = outcome(result, "R07").to_llm_summary()
    assert summary["context"] == [
        "카드 지표를 사업 성과의 직접 평가 기준으로 쓰려 한다",
        "금액과 비중의 변화 방향이 서로 달랐던 인접 월 구간이 있었다 (수치는 화면에 있음)",
    ]


def test_notice_is_not_related_to_questions():
    result = run_review(plan(indicator_use=IndicatorUse.REFERENCE, target="방한 관광객"), DEMO)
    assert outcome(result, "R07").related_rule_ids == ()


def test_outcome_order_follows_run_order():
    result = run_review(plan(target="방한 관광객", goals=[Goal.STORE_USAGE], usage_place=""), DEMO)
    assert [o.question_key for o in result.outcomes] == ["R07", "R03", "R12", "R01", "R05"]


@pytest.mark.parametrize(
    "case",
    [
        {},
        {"indicator_use": IndicatorUse.REFERENCE},
        {"indicator_use": IndicatorUse.UNKNOWN},
        {"target": "방한 관광객"},
        {"goals": [Goal.STORE_USAGE], "usage_place": ""},
        {"period_start": "2026-10-01", "period_end": "2026-10-20"},
    ],
)
def test_messages_avoid_judgment_words(case):
    result = run_review(plan(**case), DEMO)
    for item in result.outcomes:
        for word in FORBIDDEN_WORDS:
            assert word not in item.message, (word, item.rule_id)
            assert word not in (item.why or ""), (word, item.rule_id)


def test_same_input_gives_same_result():
    first, second = run_review(plan(), DEMO), run_review(plan(), DEMO)
    assert first == second


def test_llm_summary_has_no_numbers():
    r07 = outcome(run_review(plan(), DEMO), "R07")
    summary = r07.to_llm_summary()
    assert "observations" not in summary
    assert not any(isinstance(v, int) and not isinstance(v, bool) for v in summary.values())
    assert summary["rule_id"] == "R07" and summary["kind"] == "question"


def test_evidence_errors_do_not_break_review():
    result = run_review(plan(), None)
    assert outcome(result, "R07").kind == "held"
    assert outcome(result, "R05").kind == "pending"
