"""3단계 AI 참고 의견 화면·주소 (6LLM참고의견계획.md C-5). 실제 모델을 부르지 않는다."""

import pytest
from evidence_helpers import fixture_path
from fastapi.testclient import TestClient
from helpers import VALID_FORM

from policy_signal_map.app import app
from policy_signal_map.llm.base import FakeProvider, LLMError
from policy_signal_map.web.routes import opinions as opinion_routes
from policy_signal_map.web.session import COOKIE_NAME, store

CLEAN = "- 참여자 확인 자료를 어디서 모을지 정해 두세요 [R07]\n- 사용처 범위를 적어 두세요 [R07]"


@pytest.fixture
def local_llm(use_evidence):
    """설정만 local로 바꾼다. 실제 호출은 가짜 제공자가 대신한다."""

    def _use(provider: FakeProvider | None = None, **env: str):
        settings = {
            "PSM_LLM_PROVIDER": "local",
            "PSM_LLM_MODEL": "시험모델",
            "PSM_LLM_BASE_URL": "http://127.0.0.1:11434/v1",
            **env,
        }
        use_evidence(None, **settings)
        fake = provider or FakeProvider(reply=CLEAN)
        return fake

    return _use


def reviewed_client() -> TestClient:
    client = TestClient(app)
    client.post("/step/1", data=VALID_FORM)
    return client


def use_provider(monkeypatch: pytest.MonkeyPatch, fake: FakeProvider) -> list[str | None]:
    """가짜 제공자를 끼운다. 돌려주는 목록에 요청마다 고른 모델이 쌓인다."""
    asked: list[str | None] = []

    def _get(settings, model=None):
        asked.append(model)
        return fake

    monkeypatch.setattr(opinion_routes, "get_provider", _get)
    return asked


def state_of(client: TestClient):
    return store.get_or_create(client.cookies.get(COOKIE_NAME))[1]


MODELS_ENV = {"PSM_LLM_MODELS": "시험모델,두번째모델"}


def test_ai_area_is_absent_when_provider_is_none():
    html = reviewed_client().get("/step/3").text
    assert "AI 참고 의견" not in html
    assert "js/opinions.js" not in html


def test_ai_area_appears_when_provider_is_set(local_llm):
    local_llm()
    html = reviewed_client().get("/step/3").text
    assert "AI 참고 의견" in html
    assert "js/opinions.js" in html
    assert "결정하지 않습니다" in html


def test_opinions_are_off_without_provider():
    client = reviewed_client()
    assert client.get("/step/3/opinions").json() == {"state": "off", "opinions": []}


def test_opinions_are_off_before_review_starts(local_llm):
    local_llm()
    assert TestClient(app).get("/step/3/opinions").json()["state"] == "off"


def test_opinions_are_returned_with_rule_ids(local_llm, monkeypatch):
    fake = local_llm()
    use_provider(monkeypatch, fake)
    data = reviewed_client().get("/step/3/opinions").json()

    assert data["state"] == "ok"
    # 화면 문장에서는 [R07] 표기를 빼고 근거 배지로만 보여 준다 (9/18)
    assert [o["text"] for o in data["opinions"]] == [
        "참여자 확인 자료를 어디서 모을지 정해 두세요",
        "사용처 범위를 적어 두세요",
    ]
    assert data["opinions"][0]["rule_labels"] == ["금액·비중과 성과지표 확인"]
    assert data["model"] == "시험모델"


def test_prompt_gets_no_numbers(local_llm, monkeypatch):
    fake = local_llm()
    use_provider(monkeypatch, fake)
    reviewed_client().get("/step/3/opinions")

    sent = fake.calls[0][1].content
    assert "비교 가능한" not in sent
    assert "금액과 비중의 변화 방향이 서로 달랐던" in sent


def test_same_plan_is_not_asked_twice(local_llm, monkeypatch):
    fake = local_llm()
    use_provider(monkeypatch, fake)
    client = reviewed_client()
    client.get("/step/3/opinions")
    client.get("/step/3/opinions")
    assert len(fake.calls) == 1


def test_changed_plan_asks_again(local_llm, monkeypatch):
    fake = local_llm()
    use_provider(monkeypatch, fake)
    client = reviewed_client()
    client.get("/step/3/opinions")
    client.post("/step/1", data={**VALID_FORM, "indicator_use": "reference"})
    client.get("/step/3/opinions")
    assert len(fake.calls) == 2


def test_failure_does_not_break_step_three(local_llm, monkeypatch):
    fake = local_llm(FakeProvider(error=LLMError("연결 실패")))
    use_provider(monkeypatch, fake)
    client = reviewed_client()

    data = client.get("/step/3/opinions").json()
    assert data == {"state": "failed", "message": "AI 의견을 불러오지 못했습니다"}
    assert "연결 실패" not in str(data)
    assert "검토 질문" in client.get("/step/3").text


def test_dropped_lines_are_not_shown(local_llm, monkeypatch):
    fake = local_llm(FakeProvider(reply="- 3개 구간에서 방향이 달랐습니다 [R07]\n- 성공합니다 [R07]"))
    use_provider(monkeypatch, fake)
    data = reviewed_client().get("/step/3/opinions").json()
    assert data["state"] == "ok" and data["opinions"] == []
    assert data["dropped_count"] == 2


def test_evidence_error_stops_the_call(local_llm, monkeypatch, use_evidence):
    fake = local_llm()
    use_provider(monkeypatch, fake)
    client = reviewed_client()
    use_evidence(
        fixture_path("relation_broken"),
        PSM_LLM_PROVIDER="local",
        PSM_LLM_MODEL="시험모델",
        PSM_LLM_BASE_URL="http://127.0.0.1:11434/v1",
    )
    assert client.get("/step/3/opinions").json()["state"] == "off"
    assert fake.calls == []


def test_selected_model_is_used_and_labelled(local_llm, monkeypatch):
    fake = local_llm(**MODELS_ENV)
    asked = use_provider(monkeypatch, fake)
    client = reviewed_client()
    state_of(client).llm_model = "두번째모델"

    data = client.get("/step/3/opinions").json()
    assert asked == ["두번째모델"]
    assert data["model"] == "두번째모델"
    # 모델 목록 파일에 없는 모델은 이름을 그대로 표시
    assert data["model_label"] == "두번째모델"


def test_opinions_are_cached_per_model(local_llm, monkeypatch):
    fake = local_llm(**MODELS_ENV)
    asked = use_provider(monkeypatch, fake)
    client = reviewed_client()

    client.get("/step/3/opinions")
    state_of(client).llm_model = "두번째모델"
    client.get("/step/3/opinions")
    state_of(client).llm_model = "시험모델"
    client.get("/step/3/opinions")
    # 처음 모델로 돌아오면 앞서 받은 의견을 다시 쓴다
    assert asked == ["시험모델", "두번째모델"]
    assert len(fake.calls) == 2


def test_plan_change_clears_every_model_cache(local_llm, monkeypatch):
    fake = local_llm(**MODELS_ENV)
    use_provider(monkeypatch, fake)
    client = reviewed_client()
    client.get("/step/3/opinions")
    state_of(client).llm_model = "두번째모델"
    client.get("/step/3/opinions")

    client.post("/step/1", data={**VALID_FORM, "indicator_use": "reference"})
    client.get("/step/3/opinions")
    state_of(client).llm_model = "시험모델"
    client.get("/step/3/opinions")
    assert len(fake.calls) == 4


def test_model_removed_from_settings_falls_back_to_default(local_llm, monkeypatch):
    fake = local_llm()
    asked = use_provider(monkeypatch, fake)
    client = reviewed_client()
    state_of(client).llm_model = "지워진모델"
    client.get("/step/3/opinions")
    assert asked == ["시험모델"]


# ---------------------------------------------------------------- 3단계 모델 선택 (C-8-3)

CATALOG_ENV = {"PSM_LLM_MODELS": "exaone3.5:7.8b,gemma4:26b-a4b-it-qat", "PSM_LLM_MODEL": ""}


def test_model_select_appears_only_with_two_or_more_models(local_llm):
    local_llm()
    assert 'name="model"' not in reviewed_client().get("/step/3").text

    local_llm(**CATALOG_ENV)
    html = reviewed_client().get("/step/3").text
    assert 'action="/step/3/ai-model"' in html
    # 표시 이름은 resources/llm/models.json에서
    assert "EXAONE 3.5 7.8B (4비트)" in html
    assert "Gemma 4 26B A4B (QAT 4비트)" in html
    # 모델별 설명은 화면에 쓰지 않는다 — 고르는 데 도움이 되지 않고 안내가 길어진다 (사용자 확인 9/19)
    assert "LG AI연구원" not in html
    assert "어떤 모델의 의견도 검토 결과·보완 선택·보완 기획안을 바꾸지 않습니다" in html


def test_choosing_a_model_is_saved_and_shown_selected(local_llm):
    local_llm(**CATALOG_ENV)
    client = reviewed_client()
    response = client.post("/step/3/ai-model", data={"model": "gemma4:26b-a4b-it-qat"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/step/3"
    assert state_of(client).llm_model == "gemma4:26b-a4b-it-qat"
    html = client.get("/step/3").text
    assert 'value="gemma4:26b-a4b-it-qat" selected' in html
    assert "Google의 다국어 모델" not in html  # 모델 설명은 화면에 쓰지 않는다


def test_model_outside_the_list_is_refused(local_llm):
    local_llm(**CATALOG_ENV)
    client = reviewed_client()
    response = client.post("/step/3/ai-model", data={"model": "qwen2.5:7b"})
    assert response.status_code == 422
    assert "선택할 수 없는 모델입니다" in response.text
    assert state_of(client).llm_model is None


def test_model_choice_is_refused_when_ai_is_off():
    client = reviewed_client()
    response = client.post("/step/3/ai-model", data={"model": "exaone3.5:7.8b"})
    assert response.status_code == 422


def test_model_choice_before_review_goes_to_step_one(local_llm):
    local_llm(**CATALOG_ENV)
    response = TestClient(app).post("/step/3/ai-model", data={"model": "exaone3.5:7.8b"}, follow_redirects=False)
    assert response.headers["location"] == "/step/1"


def test_models_not_installed_are_marked_and_refused(local_llm, monkeypatch):
    local_llm(**CATALOG_ENV)
    monkeypatch.setattr(
        "policy_signal_map.llm.local.list_models", lambda *args, **kwargs: frozenset({"exaone3.5:7.8b"})
    )
    client = reviewed_client()
    html = client.get("/step/3").text
    assert "Gemma 4 26B A4B (QAT 4비트) (받아 두지 않음)" in html
    assert 'value="gemma4:26b-a4b-it-qat" disabled' in html

    response = client.post("/step/3/ai-model", data={"model": "gemma4:26b-a4b-it-qat"})
    assert response.status_code == 422
    assert "받아 두지 않은 모델입니다" in response.text


def test_unknown_install_state_does_not_block_choice(local_llm):
    # conftest가 모델 목록 확인을 None(확인 못 함)으로 둔다: 선택은 막지 않는다
    local_llm(**CATALOG_ENV)
    client = reviewed_client()
    assert "받아 두지 않음" not in client.get("/step/3").text
    response = client.post("/step/3/ai-model", data={"model": "gemma4:26b-a4b-it-qat"}, follow_redirects=False)
    assert response.status_code == 303


def test_opinion_is_not_kept_when_plan_changes_while_waiting(local_llm, monkeypatch):
    local_llm()
    client = reviewed_client()
    state = state_of(client)

    class PlanChangesWhileWaiting(FakeProvider):
        def generate(self, messages, *, max_tokens, timeout_s):
            # 모델 응답을 기다리는 사이 담당자가 원안을 다시 제출한 상황
            client.post("/step/1", data={**VALID_FORM, "target": "외국인 관광객"})
            return super().generate(messages, max_tokens=max_tokens, timeout_s=timeout_s)

    fake = PlanChangesWhileWaiting(reply=CLEAN)
    use_provider(monkeypatch, fake)

    assert client.get("/step/3/opinions").json()["state"] == "ok"
    assert state.cached_opinions("시험모델") is None
    # 다음 요청은 새 원안으로 다시 부른다
    client.get("/step/3/opinions")
    assert len(fake.calls) == 2


def test_ai_notes_sit_below_the_opinions(local_llm):
    """안내 문구는 의견을 읽은 뒤에 보도록 맨 아래에 둔다 (사용자 확인 2026-09-19)."""
    local_llm()
    html = reviewed_client().get("/step/3").text
    guide = html.index("확인할 점을 제시하며 결정하지 않습니다")
    assert html.index("data-ai-list") < guide
    assert html.index("data-ai-message") < guide
    assert 'class="ai-foot"' in html
