"""앱이 사용할 분석 근거 파일 상태. 처음 필요할 때 한 번 읽어 프로세스에 보관한다.

근거 파일을 바꾸면 서버를 다시 시작해야 한다. 예외를 밖으로 던지지 않고 오류 상태로 담아
입력 화면은 계속 쓸 수 있게 한다. 화면용 문구에는 서버의 전체 경로를 넣지 않는다.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from ..config import (
    DEFAULT_EVIDENCE_PATH,
    PUBLIC_SCENARIO_EVIDENCE_PATH,
    Settings,
    SettingsError,
    load_settings,
)
from ..evidence.loader import EvidenceError, LoadResult, is_real_evidence, load_evidence
from ..plan.models import Region

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvidenceState:
    settings: Settings | None
    result: LoadResult | None
    errors: tuple[str, ...]
    is_real: bool
    # 이전 내부용 서비스와 같은 화면 상태 형태를 유지한다. 공개 배포본에서는 항상 False다.
    blocked: bool

    @property
    def ok(self) -> bool:
        return not self.errors and self.result is not None

    @property
    def badge(self) -> str:
        if not self.ok or self.result is None:
            return "근거 파일 오류"
        version = self.result.file.dataset_version
        if self.is_real:
            return f"실제 분석 자료 · {version} · 내부 검증용"
        return f"시연용 합성 수치 · {version}"


def _for_screen(message: str, path: Path) -> str:
    # 로더 문구의 전체 경로를 파일 이름으로 바꾼다 (공개 배포에서 서버 폴더 구조가 드러나지 않게)
    for full in {str(path.resolve()), str(path)}:
        message = message.replace(full, path.name)
    return message


def load_evidence_state(environ: Mapping[str, str] | None = None) -> EvidenceState:
    environ = os.environ if environ is None else environ
    try:
        settings = load_settings(environ)
    except SettingsError as exc:
        log.error("설정 오류: %s", exc)
        return EvidenceState(None, None, (str(exc),), is_real=False, blocked=False)

    path = settings.evidence_path
    errors: list[str] = []
    result: LoadResult | None = None
    try:
        result = load_evidence(path, settings.region_mapping_path)
    except EvidenceError as exc:
        for message in exc.messages:
            log.error("근거 파일 오류: %s", message)
        errors.extend(_for_screen(message, path) for message in exc.messages)
    else:
        for warning in result.warnings:
            log.warning("근거 파일 경고: %s", warning)

    is_real = is_real_evidence(path, result.file if result else None)
    return EvidenceState(settings, result, tuple(errors), is_real=is_real, blocked=False)


@cache
def get_evidence_state() -> EvidenceState:
    return load_evidence_state()


@cache
def get_scenario_evidence_state() -> EvidenceState:
    """The separate A–L scenario file is never mixed into geographic totals."""
    environ = dict(os.environ)
    environ["PSM_EVIDENCE_PATH"] = str(PUBLIC_SCENARIO_EVIDENCE_PATH)
    environ.pop("PSM_REGION_MAPPING_PATH", None)
    return load_evidence_state(environ)


def dual_source_enabled(primary: EvidenceState) -> bool:
    """Only the bundled public hierarchy may offer the second demo source."""
    return bool(
        primary.settings
        and primary.settings.evidence_path.resolve() == DEFAULT_EVIDENCE_PATH.resolve()
        and primary.result
        and primary.result.file.dataset_version == "demo-hierarchy-002"
        and not primary.is_real
    )


def primary_evidence_for(current: EvidenceState) -> EvidenceState:
    """Recover the geographic source while editing an A–L plan."""
    if (
        current.settings
        and current.settings.evidence_path.resolve() == PUBLIC_SCENARIO_EVIDENCE_PATH.resolve()
    ):
        primary = get_evidence_state()
        if dual_source_enabled(primary):
            return primary
    return current


def evidence_for_region(region: Region | None, primary: EvidenceState | None = None) -> EvidenceState:
    primary = primary or get_evidence_state()
    if dual_source_enabled(primary) and region is not None and region.sido_code == "DEMO":
        return get_scenario_evidence_state()
    return primary
