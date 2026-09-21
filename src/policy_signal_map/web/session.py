"""작업 상태와 실행 환경별 세션 저장소.

로컬 개발과 테스트는 프로세스 메모리를 쓰고, Vercel은 Upstash Redis를 쓴다.
브라우저 쿠키에는 무작위 세션 ID만 들어가며 실제 기획 내용은 서버 저장소에 둔다.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from functools import cache
from threading import Lock
from typing import Any, Literal, Protocol

from ..choices.models import ChoiceSet
from ..choices.recheck import sync_after_review
from ..evidence.loader import LoadResult
from ..llm.opinions import OpinionSet
from ..plan.changes import diff_plan
from ..plan.models import PlanInput
from ..review.outcome import ReviewResult
from .session_codec import SessionDataError, decode_session, encode_session

log = logging.getLogger(__name__)

COOKIE_NAME = "psm_session"
DEFAULT_SESSION_TTL_S = 86_400
SESSION_KEY_PREFIX = "psm:session:"
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{24,64}$")
SessionBackend = Literal["memory", "redis"]


class SessionStoreError(RuntimeError):
    """세션 저장소를 사용할 수 없을 때 화면에 비밀값 없이 전달하는 오류."""


class SessionConflict(SessionStoreError):
    """같은 세션의 다른 요청이 먼저 상태를 바꾼 경우."""


@dataclass(frozen=True)
class SessionConfig:
    backend: SessionBackend
    ttl_s: int
    redis_url: str | None = None
    redis_token: str | None = field(default=None, repr=False)


def _env_enabled(environ: Mapping[str, str], name: str) -> bool:
    raw = environ.get(name, "").strip().lower()
    return bool(raw and raw not in ("0", "false", "no", "off"))


def load_session_config(environ: Mapping[str, str] = os.environ) -> SessionConfig:
    raw_backend = environ.get("PSM_SESSION_BACKEND", "").strip()
    backend = raw_backend or ("redis" if _env_enabled(environ, "VERCEL") else "memory")
    if backend not in ("memory", "redis"):
        raise SessionStoreError("PSM_SESSION_BACKEND는 memory 또는 redis여야 합니다.")

    raw_ttl = environ.get("PSM_SESSION_TTL_S", "").strip()
    try:
        ttl_s = int(raw_ttl) if raw_ttl else DEFAULT_SESSION_TTL_S
    except ValueError:
        raise SessionStoreError("PSM_SESSION_TTL_S는 초 단위 정수여야 합니다.") from None
    if ttl_s <= 0:
        raise SessionStoreError("PSM_SESSION_TTL_S는 0보다 커야 합니다.")

    url = environ.get("UPSTASH_REDIS_REST_URL", "").strip() or None
    token = environ.get("UPSTASH_REDIS_REST_TOKEN", "").strip() or None
    if backend == "redis" and (not url or not token):
        raise SessionStoreError(
            "Redis 세션 저장소 설정이 없습니다. Vercel의 Upstash Redis 환경변수를 확인하세요."
        )
    return SessionConfig(backend=backend, ttl_s=ttl_s, redis_url=url, redis_token=token)


@dataclass
class WorkState:
    plan: PlanInput = field(default_factory=PlanInput)
    original: PlanInput | None = None
    changed_fields: frozenset[str] = frozenset()
    choices: ChoiceSet = field(default_factory=ChoiceSet)
    llm_model: str | None = None
    opinions: dict[str, OpinionSet] = field(default_factory=dict)
    opinions_for: PlanInput | None = None
    choices_synced: bool = False
    choices_evidence_versions: tuple[str, str | None] | None = None

    @property
    def review_restarted(self) -> bool:
        return bool(self.changed_fields)

    def start_review(self) -> None:
        self.changed_fields = diff_plan(self.original, self.plan)
        self.original = deepcopy(self.plan)
        self.choices_synced = False
        self.opinions = {}
        self.opinions_for = None

    def sync_choices(self, result: ReviewResult, evidence: LoadResult) -> None:
        versions = (
            evidence.file.dataset_version,
            evidence.thresholds.version if evidence.thresholds else None,
        )
        if not self.choices_synced or versions != self.choices_evidence_versions:
            changed_fields = self.changed_fields if not self.choices_synced else frozenset()
            sync_after_review(self.choices, result, changed_fields, *versions)
            self.choices_synced = True
            self.choices_evidence_versions = versions

    def cached_opinions(self, model: str) -> OpinionSet | None:
        if self.opinions_for == self.original:
            return self.opinions.get(model)
        return None

    def remember_opinions(self, model: str, opinions: OpinionSet, plan: PlanInput) -> None:
        if plan != self.original:
            return
        if self.opinions_for != self.original:
            self.opinions = {}
            self.opinions_for = deepcopy(self.original)
        self.opinions[model] = opinions

    def reset(self) -> None:
        """참조를 유지한 채 새 작업 상태로 바꿔 요청 종료 시 그대로 저장되게 한다."""
        fresh = WorkState()
        self.__dict__.clear()
        self.__dict__.update(fresh.__dict__)


@dataclass
class LoadedSession:
    session_id: str
    state: WorkState
    repository: "SessionRepository"
    revision: int
    snapshot: str
    is_new: bool = False


class SessionRepository(Protocol):
    backend: SessionBackend

    def load_or_create(self, session_id: str | None) -> LoadedSession: ...

    def commit(self, loaded: LoadedSession) -> None: ...

    def ping(self) -> None: ...


def _new_session_id() -> str:
    return secrets.token_urlsafe(24)


def _valid_session_id(value: str | None) -> bool:
    return bool(value and SESSION_ID.fullmatch(value))


class SessionStore:
    """로컬용 메모리 저장소. 기존 직접 조회 테스트와도 호환한다."""

    backend: SessionBackend = "memory"

    def __init__(self) -> None:
        self._states: dict[str, WorkState] = {}
        self._lock = Lock()

    def load_or_create(self, session_id: str | None) -> LoadedSession:
        with self._lock:
            if _valid_session_id(session_id) and session_id in self._states:
                state = self._states[session_id]
                return LoadedSession(
                    session_id, state, self, revision=0, snapshot=encode_session(state, 0)
                )
            new_id = _new_session_id()
            state = WorkState()
            self._states[new_id] = state
            return LoadedSession(
                new_id, state, self, revision=0, snapshot=encode_session(state, 0), is_new=True
            )

    def get_or_create(self, session_id: str | None) -> tuple[str, WorkState]:
        loaded = self.load_or_create(session_id)
        return loaded.session_id, loaded.state

    def commit(self, loaded: LoadedSession) -> None:
        return None

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._states[session_id] = WorkState()

    def clear(self) -> None:
        with self._lock:
            self._states.clear()

    def ping(self) -> None:
        return None


CAS_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if ARGV[1] == '-1' then
  if current then return 0 end
else
  if not current then return 0 end
  local ok, decoded = pcall(cjson.decode, current)
  if not ok or tostring(decoded.revision) ~= ARGV[1] then return 0 end
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
return 1
"""


class RedisSessionStore:
    backend: SessionBackend = "redis"

    def __init__(self, client: Any, ttl_s: int = DEFAULT_SESSION_TTL_S) -> None:
        self._client = client
        self._ttl_s = ttl_s

    @staticmethod
    def _key(session_id: str) -> str:
        return f"{SESSION_KEY_PREFIX}{session_id}"

    def _fresh(self) -> LoadedSession:
        session_id = _new_session_id()
        state = WorkState()
        return LoadedSession(
            session_id,
            state,
            self,
            revision=-1,
            snapshot=encode_session(state, -1),
            is_new=True,
        )

    def load_or_create(self, session_id: str | None) -> LoadedSession:
        if not _valid_session_id(session_id):
            return self._fresh()
        try:
            raw = self._client.get(self._key(session_id))
        except Exception:
            log.exception("Redis 세션 읽기 실패")
            raise SessionStoreError("작업 상태 저장소에 연결하지 못했습니다.") from None
        if raw is None:
            return self._fresh()
        if not isinstance(raw, str):
            raise SessionStoreError("작업 상태 저장소가 잘못된 응답을 반환했습니다.")
        try:
            state, revision = decode_session(raw)
        except SessionDataError:
            log.warning("손상되거나 지원하지 않는 Redis 세션을 새로 시작합니다.")
            try:
                self._client.delete(self._key(session_id))
            except Exception:
                log.exception("손상된 Redis 세션 삭제 실패")
            return self._fresh()
        return LoadedSession(
            session_id,
            state,
            self,
            revision=revision,
            snapshot=encode_session(state, revision),
        )

    def commit(self, loaded: LoadedSession) -> None:
        current = encode_session(loaded.state, loaded.revision)
        key = self._key(loaded.session_id)
        if not loaded.is_new and current == loaded.snapshot:
            try:
                refreshed = self._client.expire(key, self._ttl_s)
            except Exception:
                log.exception("Redis 세션 만료 갱신 실패")
                raise SessionStoreError("작업 상태를 저장하지 못했습니다.") from None
            if not refreshed:
                raise SessionConflict("작업 상태가 만료되었습니다. 화면을 다시 불러오세요.")
            return
        try:
            next_revision = loaded.revision + 1
            payload = encode_session(loaded.state, next_revision)
            saved = self._client.eval(
                CAS_SCRIPT,
                keys=[key],
                args=[str(loaded.revision), payload, str(self._ttl_s)],
            )
        except Exception:
            log.exception("Redis 세션 저장 실패")
            raise SessionStoreError("작업 상태를 저장하지 못했습니다.") from None
        if saved != 1:
            raise SessionConflict("다른 요청에서 작업 상태가 변경되었습니다. 화면을 다시 불러오세요.")
        loaded.revision = next_revision
        loaded.snapshot = payload
        loaded.is_new = False

    def ping(self) -> None:
        try:
            self._client.ping()
        except Exception:
            log.exception("Redis 상태 확인 실패")
            raise SessionStoreError("작업 상태 저장소에 연결하지 못했습니다.") from None


store = SessionStore()


@cache
def _redis_store(url: str, token: str, ttl_s: int) -> RedisSessionStore:
    from upstash_redis import Redis

    client = Redis(
        url=url,
        token=token,
        allow_telemetry=False,
        read_your_writes=True,
    )
    return RedisSessionStore(client, ttl_s)


def configured_session_store(environ: Mapping[str, str] = os.environ) -> SessionRepository:
    config = load_session_config(environ)
    if config.backend == "memory":
        return store
    assert config.redis_url is not None and config.redis_token is not None
    return _redis_store(config.redis_url, config.redis_token, config.ttl_s)


def cookie_secure(environ: Mapping[str, str] = os.environ) -> bool:
    raw = environ.get("PSM_COOKIE_SECURE", "").strip().lower()
    if raw:
        return raw not in ("0", "false", "no", "off")
    return _env_enabled(environ, "VERCEL")


def cookie_max_age(environ: Mapping[str, str] = os.environ) -> int:
    try:
        return load_session_config(environ).ttl_s
    except SessionStoreError:
        return DEFAULT_SESSION_TTL_S
