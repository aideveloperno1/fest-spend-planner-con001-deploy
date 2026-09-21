"""근거 레코드 선택과 지역 표시. 2단계 화면과 3단계 검토가 같은 기준을 쓰도록 한곳에 둔다.

입력 화면의 행정코드와 근거 파일 region_key는 **행정표준코드 10자리**로 잇는다
(연결 키 C-1, 사용자 결정 2026-09-18. 근거: checks.md 1장).

**사다리 원칙** (워크플로우 8-4):
쓸 수 있는 **가장 좁은 범위**부터 쓴다. 못 쓰면 한 칸씩 넓히고, **넓힌 사실을 문구로 밝힌다.**

    시군구 자료  →  시도 자료  →  전국 자료

- 지역 자료를 써도 "선택 지역의 진단"이라고 말하지 않는다.
- 화면 글자에는 행정표준코드를 쓰지 않는다. 항상 지역 이름으로 바꿔 보여 준다.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..evidence.loader import find_record
from ..evidence.schema import EvidenceFile, EvidenceRecord
from ..plan.models import PlanInput, RegionLevel
from ..plan.regions import find_sido, region_label, sigungu_name

NATIONAL_SCOPE_LABEL = "전국 참고 — 특정 지역의 진단이 아님"
UNKNOWN_REGION_LABEL = "확인되지 않은 지역"
NOT_A_DIAGNOSIS = "선택한 지역의 소비를 진단한 결과가 아닙니다."

# 지역 자료는 표본이 작아 계산 불가 월이 쉽게 생긴다. 계산 가능한 달이 이 수보다 적으면
# 표본 부족으로 본다 (C-4, 시나리오 23·28). 전국 자료에는 적용하지 않는다:
# 전국은 2개월짜리 경계 시험 파일도 정상 동작해야 하고, 표본 문제가 지역만큼 크지 않다.
MIN_OK_MONTHS_REGION = 4


def sparse_reason(record: EvidenceRecord) -> str | None:
    """지역 자료의 표본이 부족한지. 부족하면 화면·안내에 적을 사유를 돌려준다."""
    if record.scope.geographic_scope == "national":
        return None
    ok = sum(1 for m in record.months if m.calculation_status == "ok")
    if ok >= MIN_OK_MONTHS_REGION:
        return None
    return f"{len(record.months)}개월 중 계산 가능한 달이 {ok}개월로 기준 {MIN_OK_MONTHS_REGION}개월에 못 미침"


def exact_region_key(plan: PlanInput) -> str | None:
    """고른 지역의 근거 키. **넓히지 않는다.**

    금액·비중 비교(R07)는 자료가 없으면 사다리를 타고 올라가지만, 지역 프로필과 그 값을 쓰는
    질문(업종·연령·시기)은 고른 지역 자료만 쓴다. 다른 지역 값을 그 지역 것처럼 쓰게 되기 때문이다.
    """
    region = plan.region
    if region is None:
        return None
    if region.level is RegionLevel.NATIONAL:
        return "ALL"
    if region.level is RegionLevel.SIDO:
        return region.sido_code or None
    return region.sigungu_code or None


def region_display(geographic_scope: str, region_key: str) -> str:
    """근거 레코드의 범위를 사람이 읽는 이름으로. 행정표준코드가 화면에 나가지 않게 한다.

    목록에 없는 코드(10자리 숫자)는 이름을 만들 수 없으므로 코드 대신 '확인되지 않은 지역'으로 적는다.
    시험용 합성 키(예: DEMO-SIDO-A)는 코드가 아니므로 그대로 보여 준다.
    """
    if geographic_scope == "national":
        return "전국"
    if geographic_scope == "sigungu":
        name = sigungu_name(region_key)
    else:
        sido = find_sido(region_key)
        name = sido["name"] if sido else ""
    if name:
        return name
    return UNKNOWN_REGION_LABEL if region_key.isdigit() else region_key


def sido_display(region_key: str) -> str:
    """시도 region_key를 이름으로 (기존 호출부 호환)."""
    return region_display("sido", region_key)


def source_label(record: EvidenceRecord) -> str:
    """문장 안에서 쓰는 자료 출처 이름 ("전국" / "강원특별자치도" / "강원특별자치도 강릉시")."""
    return region_display(record.scope.geographic_scope, record.scope.region_key)


def scope_label(record: EvidenceRecord | None) -> str | None:
    if record is None:
        return None
    if record.scope.geographic_scope == "national":
        return NATIONAL_SCOPE_LABEL
    return f"{source_label(record)} 범위 참고 — 선택 지역의 진단이 아님"


@dataclass(frozen=True)
class RecordSelection:
    """어떤 레코드를 왜 골랐는지. 2단계 화면과 3단계 검토가 이 하나를 나눠 쓴다."""

    record: EvidenceRecord | None
    scope_label: str | None = None
    region_note: str | None = None


# ---------------------------------------------------------------- 안내 문장


def _plan_label(plan: PlanInput) -> str:
    return region_label(plan.region) or "선택한 지역"


def _national_only_note(plan: PlanInput) -> str | None:
    """지역 자료가 아예 없는 파일(전국 전용)에서 쓰던 안내. 넓혔다고 말하지 않는다."""
    label = region_label(plan.region)
    if not label:
        return None
    return f"전국 참고 자료입니다. 선택한 {label}의 소비를 진단한 결과가 아닙니다."


def _wider_note(plan: PlanInput) -> str:
    """시군구 기획에 시도 자료를 쓰는데, 파일에 시군구 레코드 자체가 없을 때 (C-2)."""
    return f"넓은 범위의 참고자료입니다. 선택한 {_plan_label(plan)}의 소비를 진단한 결과가 아닙니다."


def _widened_note(plan: PlanInput, used_name: str, skipped: tuple[str, str | None], *, wider: bool) -> str:
    """한 칸 넓힌 사실과 그 이유를 밝힌다 (없음 / 사용 불가 / 표본 부족)."""
    label = _plan_label(plan)
    kind, reason = skipped
    if kind == "missing":
        head = f"선택한 {label}의 근거 자료가 없어 {used_name} 자료를 보여 줍니다."
    elif kind == "sparse":
        head = f"선택한 {label}의 자료는 표본이 부족해({reason}) {used_name} 자료를 보여 줍니다."
    else:
        head = f"선택한 {label}의 자료는 사용할 수 없어(사유: {reason}) {used_name} 자료를 보여 줍니다."
    tail = f"넓은 범위의 참고자료이며 {NOT_A_DIAGNOSIS}" if wider else NOT_A_DIAGNOSIS
    return f"{head} {tail}"


# ---------------------------------------------------------------- 레코드 고르기


def _has_scope(file: EvidenceFile, geographic_scope: str) -> bool:
    return any(r.scope.geographic_scope == geographic_scope for r in file.records)


def _ladder(plan: PlanInput) -> list[tuple[str, str]]:
    """좁은 범위부터 넓은 범위 순서. (geographic_scope, region_key)"""
    region = plan.region
    steps: list[tuple[str, str]] = []
    if region is not None and region.level is RegionLevel.SIGUNGU:
        steps.append(("sigungu", region.sigungu_code))
    if region is not None and region.level in (RegionLevel.SIGUNGU, RegionLevel.SIDO):
        steps.append(("sido", region.sido_code))
    return steps


def select_main(file: EvidenceFile | None, plan: PlanInput) -> RecordSelection:
    """화면·검토가 기준으로 삼을 레코드 하나를 고른다 (사다리 원칙)."""
    if file is None:
        return RecordSelection(None, None, _national_only_note(plan))

    national = find_record(file, "national", "ALL")
    steps = _ladder(plan)
    if not steps:
        return RecordSelection(national, scope_label(national))

    is_sigungu_plan = steps[0][0] == "sigungu"
    # 바로 아래 칸에서 왜 못 썼는지 (missing / blocked / sparse). 파일에 그 범위 레코드가
    # 하나도 없으면 "없어서 넓혔다"고 말하지 않는다 — 자료 성격을 잘못 알리게 된다
    skipped: tuple[str, str | None] | None = None

    for index, (geographic_scope, key) in enumerate(steps):
        last_region_step = index == len(steps) - 1
        record = find_record(file, geographic_scope, key)
        if record is None:
            if _has_scope(file, geographic_scope):
                skipped = ("missing", None)
            continue
        applicability = record.applicability["R07"]
        if applicability.status == "blocked":
            # 쓸 수 없는 지역 수치를 지역 진단처럼 보여 주지 않는다 (C-4)
            skipped = ("blocked", applicability.reason)
            continue
        sparse = sparse_reason(record)
        if sparse and not last_region_step:
            # 표본이 부족하면 **같은 지역의 더 넓은 범위**가 남아 있을 때만 한 칸 넓힌다.
            # 마지막 지역 칸에서는 넓히지 않고 그 자료를 쓴다 — 화면이 수치를 접고
            # "이 지역은 자료가 부족하다"를 보여 주는 편이 지역을 포기하는 것보다 정직하다
            skipped = ("sparse", sparse)
            continue

        if index == 0:
            note = None  # 고른 지역의 자료를 그대로 씀
        elif skipped is not None:
            note = _widened_note(plan, source_label(record), skipped, wider=True)
        else:
            note = _wider_note(plan)  # 파일에 시군구 레코드 자체가 없음
        return RecordSelection(record, scope_label(record), note)

    # 끝까지 못 썼다 → 전국
    if skipped is None:
        return RecordSelection(national, scope_label(national), _national_only_note(plan))
    note = _widened_note(plan, "전국 참고", skipped, wider=is_sigungu_plan)
    return RecordSelection(national, scope_label(national), note)
