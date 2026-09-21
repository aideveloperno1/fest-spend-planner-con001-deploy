import copy
import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "evidence"

VALID_FIXTURES = [
    "amount_up_share_down",
    "amount_down_share_up",
    "same_direction",
    "flat_change",
    "prev_foreign_zero",
    "missing_month",
    "tiny_change",
    "known_only_differs",
    "large_amounts",
    "unknown_equals_total",
    "denominator_zero",
    # 지역(시도) 사례 — 2단계 지역 선택·되돌림·표본 부족 확인용
    "sido_allowed",
    "sido_blocked",
    "sido_sparse",
    # 2.1 사례 — 지역 프로필 묶음이 더해진 파일
    "profiles_ok",
]

# 읽히기는 하지만 경고가 남는 파일. 프로필 한 곳이 고장 나면 그 지역만 빠지고 파일은 살아 있다
# (7지역확장계획.md 3장). 자세한 확인은 test_evidence_profiles.py
WARNING_FIXTURES = ["profiles_one_broken"]


def fixture_path(name: str) -> Path:
    return FIXTURE_DIR / f"{name}.json"


def fixture_data(name: str) -> dict:
    return json.loads(fixture_path(name).read_text(encoding="utf-8"))


def base_data() -> dict:
    return copy.deepcopy(fixture_data("amount_up_share_down"))
