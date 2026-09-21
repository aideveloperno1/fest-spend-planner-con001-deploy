"""배포본이 공개 합성 전달본만으로 실제 화면 흐름을 시작할 수 있는지 확인한다."""

from pathlib import Path

from policy_signal_map.evidence.loader import load_evidence
from policy_signal_map.paths import RESOURCES_DIR
from policy_signal_map.plan.regions import find_sido
from policy_signal_map.review.engine import run_review
from policy_signal_map.web.evidence_state import EvidenceState
from policy_signal_map.web.evidence_view import build_evidence_view
from policy_signal_map.web.profile_view import build_profile_view
from policy_signal_map.web.routes.input import sample_plan_for

PUBLIC_EVIDENCE = RESOURCES_DIR / "evidence" / "review_evidence_public_v2.1.json"


def public_state() -> EvidenceState:
    result = load_evidence(PUBLIC_EVIDENCE)
    return EvidenceState(None, result, (), is_real=False, blocked=False)


def test_배포본은_공개_합성_전달본을_포함한다():
    result = load_evidence(PUBLIC_EVIDENCE)
    assert result.file.data_kind == "synthetic"
    assert len(result.file.records) == 13
    assert len(result.profiles) == 13


def test_공개_시연_지역_12개를_입력화면에서_고를_수_있다():
    demo = find_sido("DEMO")
    assert demo is not None
    assert len(demo["sigungu"]) == 12
    assert {row["code"] for row in demo["sigungu"]} == {f"DEMO-SGG-{letter}" for letter in "ABCDEFGHIJKL"}


def test_예시_기획이_공개_전달본의_가상_지역과_기간을_쓴다():
    state = public_state()
    plan = sample_plan_for(state)
    assert plan.region.sigungu_code == "DEMO-SGG-A"
    assert plan.period_start == "2026-05-01"
    assert plan.period_end == "2026-06-30"
    assert build_profile_view(plan, state.result).available is True


def test_공개_전달본으로_근거화면과_검토질문을_완성한다():
    state = public_state()
    plan = sample_plan_for(state)

    evidence = build_evidence_view(plan, state.result)
    review = run_review(plan, state.result)

    assert evidence.main is not None
    assert evidence.main.scope_label == "시군구 공개 시연 지역 A · 대도시 기본형"
    assert evidence.dataset_version == "demo-2.1-003"
    assert review.evidence_id == evidence.main.evidence_id
    assert review.outcomes


def test_배포_실행_스크립트는_공개자료와_Google_AI만_지정한다():
    script = (Path(__file__).resolve().parent.parent / "run_deploy.ps1").read_text(encoding="utf-8")
    assert "review_evidence_public_v2.1.json" in script
    assert 'PSM_LLM_PROVIDER = "google_ai"' in script
    assert "GEMINI_API_KEY" in script
    assert "gemini-3.5-flash-lite" not in script
    assert script.index("gemini-3.8-flash") < script.index("gemma-4-31b-it")
    assert "review_evidence_real" not in script
    assert "region_mapping.json" not in script
