"""사업 유형별로 켜지는 검토 질문 (7지역확장계획.md 6-2장).

담당자가 고른 사업 유형에 맞는 질문만 켠다. 공통 질문은 유형과 상관없이 항상 켠다.

**유형을 고르지 않은 기획은 아무 질문도 숨기지 않는다.** 서비스가 마음대로 한 유형으로
분류해 질문을 골라내면, 담당자는 왜 그 질문이 안 나왔는지 알 수 없다 (D9).

파일은 규칙 **번호 목록**만 담는다. 실행 함수는 `engine.RUNNERS`에 등록된 것만 부른다.
"""

from __future__ import annotations

import json
from functools import cache

from ..paths import RESOURCES_DIR
from ..plan.models import BusinessType

PACKS_FILE = RESOURCES_DIR / "rules" / "business_packs.json"
SUPPORTED_VERSIONS = frozenset({"1.0"})

# 유형이 달라 이번 기획에서는 실행하지 않았다고 화면에 적는 문장
NOT_IN_PACK_REASON = "이 사업 유형에서는 확인하지 않는 항목입니다."


@cache
def _packs_file() -> dict:
    data = json.loads(PACKS_FILE.read_text(encoding="utf-8"))
    if data.get("version") not in SUPPORTED_VERSIONS:
        raise ValueError(f"지원하지 않는 사업 유형 파일 버전: {data.get('version')}")
    unknown = set(data.get("packs", {})) - {t.value for t in BusinessType}
    if unknown:
        # 입력에 없는 유형 이름이 파일에 있으면 아무 기획에도 걸리지 않는다. 조용히 두지 않는다
        raise ValueError(f"입력 목록에 없는 사업 유형: {', '.join(sorted(unknown))} (business_packs.json)")
    return data


@cache
def common_rules() -> tuple[str, ...]:
    """유형과 상관없이 항상 켜는 질문."""
    return tuple(_packs_file().get("common", ()))


@cache
def pack_rules(business_type: BusinessType) -> tuple[str, ...]:
    """그 유형에서만 켜는 질문."""
    pack = _packs_file().get("packs", {}).get(business_type.value, {})
    return tuple(pack.get("rules", ()))


def active_rules(business_type: BusinessType | None, run_order: tuple[str, ...]) -> tuple[str, ...]:
    """이번 기획에서 실행할 질문 목록. 순서는 화면 순서(run_order)를 따르고 중복은 한 번만 실행한다.

    유형을 고르지 않았으면 실행할 수 있는 질문을 모두 켠다.
    """
    if business_type is None:
        return run_order
    allowed = {*common_rules(), *pack_rules(business_type)}
    return tuple(rule_id for rule_id in run_order if rule_id in allowed)


def check_pack_rules(known_rule_ids: frozenset[str]) -> None:
    """규칙 파일에 없는 번호가 사업 유형 파일에 있으면 알린다.

    이 모듈을 불러올 때가 아니라 규칙 목록을 아는 쪽(engine)이 부른다.
    """
    listed = {*common_rules(), *(rule for t in BusinessType for rule in pack_rules(t))}
    missing = sorted(listed - known_rule_ids)
    if missing:
        raise ValueError(f"규칙 파일에 없는 번호가 사업 유형에 적혀 있습니다: {', '.join(missing)} (business_packs.json)")
