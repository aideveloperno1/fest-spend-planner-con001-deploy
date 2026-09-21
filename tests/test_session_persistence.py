"""Vercel 인스턴스가 바뀌어도 작업 상태가 이어지는지 검증한다."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from policy_signal_map.choices.models import (
    ArchivedChoice,
    Availability,
    Choice,
    Decision,
    ExecutionInput,
)
from policy_signal_map.llm.guard import Opinion
from policy_signal_map.llm.opinions import OpinionSet
from policy_signal_map.plan.models import BusinessType, Goal, IndicatorUse, sample_plan
from policy_signal_map.web.session import (
    RedisSessionStore,
    SessionConflict,
    SessionStoreError,
    WorkState,
    load_session_config,
)
from policy_signal_map.web.session_codec import SessionDataError, decode_session, encode_session


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.deleted: list[str] = []
        self.pinged = False

    def get(self, key: str):
        return self.values.get(key)

    def delete(self, key: str):
        self.deleted.append(key)
        self.values.pop(key, None)

    def expire(self, key: str, ttl: int):
        self.ttls[key] = ttl
        return key in self.values

    def eval(self, script: str, keys: list[str], args: list[str]):
        del script
        key = keys[0]
        expected, payload, ttl = args
        current = self.values.get(key)
        if expected == "-1":
            if current is not None:
                return 0
        else:
            if current is None or str(json.loads(current)["revision"]) != expected:
                return 0
        self.values[key] = payload
        self.ttls[key] = int(ttl)
        return 1

    def ping(self):
        self.pinged = True
        return "PONG"


def rich_state() -> WorkState:
    plan = sample_plan()
    plan.business_type = BusinessType.FOREIGN_TOURISM
    plan.goals = [Goal.FOREIGN_SHARE, Goal.OTHER]
    plan.goal_other = "체류 경험 개선"
    plan.indicator_use = IndicatorUse.REFERENCE
    state = WorkState(plan=plan, original=replace(plan), changed_fields=frozenset({"goals"}))
    choice = Choice(
        question_key="R07:main",
        rule_id="R07",
        decision=Decision.MODIFY,
        merge_group="foreign-data",
        option_id="collect",
        modified_text="담당 부서와 확인",
        reason="시연용 선택",
        evidence_ids=("E-1",),
        needs_recheck=True,
        related_fields=("goals",),
        evidence_dataset_version="public-v2.1",
        evidence_thresholds_version="threshold-v1",
    )
    state.choices.put(choice)
    state.choices.set_execution(
        "foreign-data",
        ExecutionInput(
            collect_items=("국적", "업종"),
            availability=Availability.NEGOTIATING,
            owner="관광과",
            cycle="월 1회",
        ),
    )
    state.choices.archived.append(ArchivedChoice(choice=choice, reason="이전 선택"))
    state.choices.last_archived.append(ArchivedChoice(choice=choice, reason="방금 보관"))
    state.llm_model = "gemini-3.8-flash"
    opinion_set = OpinionSet(
        opinions=(Opinion("자료 확보 범위를 확인해 보세요. [R07]", ("R07",)),),
        provider_name="google_ai",
        model="gemini-3.8-flash",
        created_at="2026-09-21 12:00",
        dropped_count=1,
    )
    state.opinions = {"gemini-3.8-flash": opinion_set}
    state.opinions_for = replace(plan)
    state.choices_synced = True
    state.choices_evidence_versions = ("public-v2.1", "threshold-v1")
    return state


def test_work_state_json_round_trip_preserves_all_nested_values():
    state = rich_state()
    raw = encode_session(state, 7)
    restored, revision = decode_session(raw)
    assert revision == 7
    assert restored == state
    assert "시연용 선택" in raw


def test_session_json_rejects_unknown_schema_and_bad_values():
    with pytest.raises(SessionDataError):
        decode_session('{"schema_version":999,"revision":0,"state":{}}')
    with pytest.raises(SessionDataError):
        decode_session("not-json")


def test_redis_store_survives_a_new_repository_instance():
    redis = FakeRedis()
    first_instance = RedisSessionStore(redis, ttl_s=120)
    loaded = first_instance.load_or_create(None)
    loaded.state.plan.name = "인스턴스 사이에 유지"
    first_instance.commit(loaded)

    second_instance = RedisSessionStore(redis, ttl_s=120)
    restored = second_instance.load_or_create(loaded.session_id)
    assert restored.state.plan.name == "인스턴스 사이에 유지"
    assert restored.revision == 0
    assert redis.ttls[f"psm:session:{loaded.session_id}"] == 120


def test_redis_store_detects_concurrent_writes():
    redis = FakeRedis()
    repository = RedisSessionStore(redis)
    initial = repository.load_or_create(None)
    repository.commit(initial)

    first = repository.load_or_create(initial.session_id)
    second = repository.load_or_create(initial.session_id)
    first.state.plan.name = "먼저 저장"
    repository.commit(first)
    second.state.plan.name = "늦게 저장"
    with pytest.raises(SessionConflict):
        repository.commit(second)


def test_redis_store_refreshes_ttl_without_rewriting_unchanged_state():
    redis = FakeRedis()
    repository = RedisSessionStore(redis, ttl_s=55)
    loaded = repository.load_or_create(None)
    repository.commit(loaded)
    key = f"psm:session:{loaded.session_id}"
    before = redis.values[key]
    same = repository.load_or_create(loaded.session_id)
    repository.commit(same)
    assert redis.values[key] == before
    assert redis.ttls[key] == 55


def test_redis_store_reports_a_session_that_expired_during_request():
    redis = FakeRedis()
    repository = RedisSessionStore(redis)
    loaded = repository.load_or_create(None)
    repository.commit(loaded)
    existing = repository.load_or_create(loaded.session_id)
    redis.values.clear()
    with pytest.raises(SessionConflict, match="만료"):
        repository.commit(existing)


def test_corrupt_redis_session_is_deleted_and_replaced():
    redis = FakeRedis()
    repository = RedisSessionStore(redis)
    session_id = "a" * 32
    key = f"psm:session:{session_id}"
    redis.values[key] = "broken"
    loaded = repository.load_or_create(session_id)
    assert loaded.session_id != session_id
    assert key in redis.deleted


def test_session_config_defaults_and_vercel_requirements():
    assert load_session_config({}).backend == "memory"
    assert load_session_config({"VERCEL": "0"}).backend == "memory"
    with pytest.raises(SessionStoreError, match="Upstash Redis"):
        load_session_config({"VERCEL": "1"})
    config = load_session_config(
        {
            "VERCEL": "1",
            "UPSTASH_REDIS_REST_URL": "https://example.upstash.io",
            "UPSTASH_REDIS_REST_TOKEN": "secret",
            "PSM_SESSION_TTL_S": "90",
        }
    )
    assert config.backend == "redis"
    assert config.ttl_s == 90
    assert "secret" not in repr(config)


@pytest.mark.parametrize("ttl", ["zero", "0", "-1"])
def test_bad_session_ttl_is_rejected(ttl):
    with pytest.raises(SessionStoreError):
        load_session_config({"PSM_SESSION_TTL_S": ttl})
