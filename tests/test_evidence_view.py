"""2단계 화면 데이터 (2근거확인화면계획.md 6장, 9장)."""

import json
from fractions import Fraction
from pathlib import Path

import pytest
from evidence_helpers import VALID_FIXTURES, base_data, fixture_data, fixture_path

from policy_signal_map.config import (
    LEGACY_DEMO_EVIDENCE_PATH as DEFAULT_EVIDENCE_PATH,
)
from policy_signal_map.evidence.loader import load_evidence
from policy_signal_map.plan.models import PlanInput, Region, RegionLevel, sample_plan
from policy_signal_map.web.evidence_view import build_evidence_view

JUDGMENT_WORDS = ("문제", "오류", "위험", "실패", "성공", "잘못")
NATIONAL_PLAN = PlanInput(region=Region(RegionLevel.NATIONAL))


def view_of(path: Path, plan: PlanInput = NATIONAL_PLAN):
    return build_evidence_view(plan, load_evidence(path))


def write(tmp_path: Path, data: dict, name: str = "case.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def demo_data() -> dict:
    return json.loads(DEFAULT_EVIDENCE_PATH.read_text(encoding="utf-8"))


def test_demo_summary_sentence():
    view = view_of(DEFAULT_EVIDENCE_PATH)
    assert view.summary_sentence == (
        "2026년 1~6월 전국 자료에서 비교 가능한 5개 인접 월 구간 중 2개 구간에서 "
        "외국인 결제금액과 전체 분모 비중의 변화 방향이 달랐습니다."
    )
    assert view.status_kind == "allowed" and view.show_numbers and view.show_summary


def test_same_direction_sentence_has_no_opposite_wording():
    sentence = view_of(fixture_path("flat_change")).summary_sentence
    assert sentence == (
        "2026년 1~3월 전국 자료에서 비교 가능한 2개 인접 월 구간에서는 "
        "외국인 결제금액과 전체 분모 비중이 서로 반대 방향으로 움직이지 않았습니다."
    )
    assert "달랐" not in sentence


def test_all_skipped_sentence():
    assert view_of(fixture_path("missing_month")).summary_sentence == (
        "비교 가능한 인접 월 구간이 없어 금액·비중 방향 비교를 보류합니다."
    )


def test_skipped_pairs_are_mentioned(tmp_path: Path):
    data = fixture_data("flat_change")
    data["records"][0]["months"][2].update(
        calculation_status="no_data",
        foreign_amount=None,
        total_amount=None,
        unknown_amount=None,
        transaction_count=None,
        foreign_share_pct=None,
        known_only_share_pct=None,
        unknown_share_pct=None,
    )
    sentence = view_of(write(tmp_path, data)).summary_sentence
    assert sentence.endswith(" 자료가 부족한 1개 구간은 비교하지 않았습니다.")
    assert "1개 인접 월 구간에서는" in sentence


@pytest.mark.parametrize("name", [*VALID_FIXTURES, "demo"])
def test_sentences_avoid_judgment_words(name):
    # 데이터에 따라 달라지는 문장만 검사한다. 해석 한계 고정 문구는 판정을 부정하는 문장이라 대상이 아니다
    path = DEFAULT_EVIDENCE_PATH if name == "demo" else fixture_path(name)
    view = view_of(path)
    for text in (view.summary_sentence or "", view.held_message or "", *view.method_lines):
        for word in JUDGMENT_WORDS:
            assert word not in text, (word, text)


def test_region_note_for_sigungu_plan():
    """예시 기획(강원 강릉시)은 강릉시 자료가 있어 그대로 쓴다. 넓히지 않았으므로 안내가 없다."""
    view = view_of(DEFAULT_EVIDENCE_PATH, sample_plan())
    assert view.main.evidence_id == "DEMO-R07-SIGUNGU-강원-강릉시"
    assert view.main_scope_label == "강원특별자치도 강릉시 범위 참고 — 선택 지역의 진단이 아님"
    assert view.region_note is None
    assert view.plan_region_label == "강원특별자치도 강릉시"
    assert view.summary_sentence.startswith("2026년 1~6월 강원특별자치도 강릉시 자료에서")


def test_no_region_note_for_national_plan():
    assert view_of(DEFAULT_EVIDENCE_PATH).region_note is None


def test_unit_is_won_for_small_amounts_and_eok_for_large():
    assert view_of(DEFAULT_EVIDENCE_PATH).main.unit == "원"
    assert view_of(fixture_path("large_amounts")).main.unit == "억원"


def test_needs_review_hides_summary(tmp_path: Path):
    data = base_data()
    data["records"][0]["applicability"]["R07"] = {"status": "needs_review", "reason": "지역 기준 확인 중"}
    view = view_of(write(tmp_path, data))
    assert view.summary_sentence is None and not view.show_summary
    assert view.show_numbers
    assert view.held_message == "근거 기반 결론을 보류합니다. 확인할 내용: 지역 기준 확인 중"


def test_blocked_hides_all_numbers(tmp_path: Path):
    data = base_data()
    data["records"][0]["applicability"]["R07"] = {"status": "blocked", "reason": "범위 불일치"}
    view = view_of(write(tmp_path, data))
    assert not view.show_numbers and not view.show_summary
    assert view.chart_data == {}
    assert view.held_message == "현재 자료로 금액·비중 비교를 사용할 수 없습니다. 사유: 범위 불일치"


def test_hold_examples_from_demo():
    view = view_of(DEFAULT_EVIDENCE_PATH)
    assert [e.evidence_id for e in view.hold_examples] == ["DEMO-R07-SIDO-HOLD"]
    example = view.hold_examples[0]
    assert example.summary.skipped_count == 4
    assert example.scope_label == "시도 DEMO-SIDO-A"


def test_no_hold_examples_when_only_national():
    assert view_of(fixture_path("amount_up_share_down")).hold_examples == ()


def test_no_hold_examples_for_real_files(tmp_path: Path):
    data = demo_data()
    for record in data["records"]:
        record["data_kind"] = "real"
    assert view_of(write(tmp_path, data)).hold_examples == ()


def test_blocked_record_is_not_a_hold_example(tmp_path: Path):
    """사용 불가 레코드는 예시로도 보여 주지 않는다 (수치를 감춰야 하므로)."""
    data = demo_data()
    hold = next(r for r in data["records"] if r["evidence_id"] == "DEMO-R07-SIDO-HOLD")
    hold["applicability"]["R07"]["status"] = "blocked"
    shown = [e.evidence_id for e in view_of(write(tmp_path, data)).hold_examples]
    assert "DEMO-R07-SIDO-HOLD" not in shown


def test_hold_examples_show_only_one():
    """지역 레코드가 늘어도 예시는 한 건만 (여러 건이면 '예시'가 자료처럼 읽힌다)."""
    assert len(view_of(DEFAULT_EVIDENCE_PATH).hold_examples) == 1


def test_missing_national_record(tmp_path: Path):
    data = base_data()
    data["records"][0]["scope"].update(geographic_scope="sido", region_key="DEMO-SIDO-A")
    view = view_of(write(tmp_path, data))
    assert view.main is None
    assert view.status_kind == "missing"
    assert not view.show_numbers
    assert view.missing_main_message.startswith("전국 근거 레코드가 없어")


def test_chart_data_keeps_nulls():
    chart = view_of(fixture_path("missing_month")).chart_data
    assert chart["foreign_amount"] == [800, None, 900]
    assert chart["share_all_pct"][1] is None and chart["share_known_pct"][1] is None


def test_chart_data_contains_only_json_types():
    chart = view_of(DEFAULT_EVIDENCE_PATH).chart_data
    json.dumps(chart)
    for key, values in chart.items():
        items = values if isinstance(values, list) else [values]
        assert all(v is None or type(v) in (int, float, str) for v in items), key
    assert chart["foreign_amount"] == [820, 790, 860, 905, 930, 880]
    assert chart["labels"] == ["1월", "2월", "3월", "4월", "5월", "6월"]


def test_chart_amounts_in_eok_are_floats():
    chart = view_of(fixture_path("large_amounts")).chart_data
    assert chart["unit"] == "억원"
    assert chart["foreign_amount"] == [700000.0, 700000.0]


def test_shares_are_recomputed_from_amounts(tmp_path: Path):
    data = base_data()
    data["records"][0]["months"][0]["foreign_share_pct"] = 8.01
    view = view_of(write(tmp_path, data))
    assert view.main.months[0].foreign_share_pct == Fraction(8)


def test_demo_rows_match_expected_screen_values():
    main = view_of(DEFAULT_EVIDENCE_PATH).main
    assert [m.label for m in main.months] == ["1월", "2월", "3월", "4월", "5월", "6월"]
    assert [p.label for p in main.pairs] == ["1→2월", "2→3월", "3→4월", "4→5월", "5→6월"]
    assert main.totals.foreign_amount == 5185
    hold = view_of(DEFAULT_EVIDENCE_PATH).hold_examples[0]
    assert hold.months[4].foreign_amount == 0
    assert hold.months[4].foreign_share_pct is None
    assert hold.months[2].foreign_amount is None


def test_data_limitations_and_service_notes_are_kept_apart():
    view = view_of(DEFAULT_EVIDENCE_PATH)
    demo_record = demo_data()["records"][0]
    assert view.data_limitations == tuple(demo_record["limitations"])
    # 서비스 고정 원칙은 파일과 상관없이 따로 있고, 파일 문장과 섞이지 않는다
    assert view.service_notes and not set(view.service_notes) & set(view.data_limitations)
