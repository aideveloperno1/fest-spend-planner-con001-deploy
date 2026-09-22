"""화면 시연용 합성 근거 파일을 만든다.

실행: uv run python scripts/build_demo_evidence.py
수치와 구간 설계 의도: 1근거계산계층계획.md 9장. 실제 카드 분석 수치를 쓰지 않는다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _evidence_builder import evidence_file, ok_month, record, status_month, write_json  # noqa: E402

from policy_signal_map.evidence.compare import compare_record  # noqa: E402
from policy_signal_map.evidence.loader import load_evidence  # noqa: E402
from policy_signal_map.evidence.schema import PROFILE_VERSION  # noqa: E402
from policy_signal_map.evidence.summary import summarize_pairs  # noqa: E402
from policy_signal_map.paths import RESOURCES_DIR  # noqa: E402
from policy_signal_map.plan.regions import sido_list  # noqa: E402

OUT_PATH = RESOURCES_DIR / "evidence" / "review_evidence_demo_v1.json"
DATASET_VERSION = "demo-001"
# 순위 표시의 분모. 시연 파일 안에서 프로필이 있는 지역 수를 그대로 쓴다
DEMO_RANK_REGIONS = 283

# 시도 레코드 공통값. 지역 자료가 생겨도 업종 후보 검토(R02)는 켜지 않는다 (워크플로우 8-4)
SIDO_APPLICABILITY = {
    "R07": {"status": "allowed", "reason": "합성 시도 금액·비중 예시로만 사용"},
    "R06": {"status": "blocked", "reason": "업종·월 보정 자료 없음"},
    "R02": {"status": "blocked", "reason": "업종 후보 자료 미확인"},
}
SIDO_LIMITATIONS = [
    "합성 자료",
    "시도 범위 참고 예시이며 선택 시군구 진단이 아님",
    "미상 제외 비중을 정답으로 해석하지 않음",
]


def sido(code: str, name: str, months: list[dict], *, applicability: dict | None = None) -> dict:
    """시도 레코드 하나.

    region_key는 행정표준코드 10자리다 (연결 키 C-1). 화면에는 지역 이름으로 나온다.
    evidence_id에는 읽을 수 있는 이름을 쓴다 — 근거 칩에 그대로 보이기 때문이다.
    """
    return record(
        f"DEMO-R07-SIDO-{name}",
        months,
        geographic_scope="sido",
        region_key=code,
        region_basis="merchant_location",
        applicability=applicability or SIDO_APPLICABILITY,
        limitations=list(SIDO_LIMITATIONS),
    )


def sigungu(code: str, name: str, months: list[dict], *, applicability: dict | None = None) -> dict:
    """시군구 레코드 하나. 시도와 같은 형식이며 geographic_scope만 다르다."""
    return record(
        f"DEMO-R07-SIGUNGU-{name}",
        months,
        geographic_scope="sigungu",
        region_key=code,
        region_basis="merchant_location",
        applicability=applicability or SIDO_APPLICABILITY,
        limitations=[
            "합성 자료",
            "시군구 범위 참고 예시이며 판정 결과가 아님",
            "미상 제외 비중을 정답으로 해석하지 않음",
        ],
    )


# 시군구 레코드를 만들지 않는 곳. 사다리(시군구 → 시도 → 전국)를 화면에서 보이려고 일부러 비운다
SIGUNGU_SKIP = {
    "5119000000": "태백시 — 자료 없음 → 강원 시도 자료로 넓히는 화면",
}
# 아래 세 곳은 손으로 만든다 (표본 부족·사용 불가 예시). 자동 생성에서 뺀다
SIGUNGU_HANDMADE = {"5115000000", "5111000000", "1111000000", "5011000000"}


def _numbers(code: str, index: int) -> tuple[int, int, int]:
    """시군구 코드에서 그 달의 (외국인, 전체, 미상) 금액을 만든다.

    같은 코드면 항상 같은 값이 나온다(난수를 쓰지 않는다). 모든 값은 가상 규모이며
    실제 카드 분석 수치와 아무 관계가 없다. 전체 금액은 1만 원을 넘지 않게 둔다
    (합성 파일은 수만 원 이하만 쓴다 — tests/test_demo_evidence.py).
    """
    seed = int(code)
    base = 300 + (seed // 10_000) % 3_200          # 300 ~ 3,499
    slope = ((seed // 1_000) % 9) - 4               # -4 ~ +4 (달마다 늘거나 줄거나)
    total = base + slope * index * (base // 60 + 1)
    total = max(120, total)
    share = 60 + (seed // 100_000) % 60             # 6.0% ~ 11.9%
    wobble = ((seed // 10) % 7) - 3                 # 달마다 비중이 조금씩 흔들린다
    foreign = max(1, total * (share + wobble * index) // 1000)
    unknown = max(1, total * (40 + (seed % 50)) // 1000)
    if foreign + unknown > total:                   # 외국인 + 미상 ≤ 전체 (형식 검사 규칙)
        unknown = max(1, total - foreign - 1)
    return foreign, total, unknown


# evidence_id는 근거 칩으로 화면에 그대로 보인다. 행정표준코드를 쓰지 않으려고 짧은 이름을 붙인다
SIDO_SHORT = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기", "강원특별자치도": "강원", "충청북도": "충북", "충청남도": "충남",
    "전북특별자치도": "전북", "전라남도": "전남", "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주",
}


def auto_sigungus() -> list[dict]:
    """입력 화면의 시군구 전체에 합성 레코드를 만든다 (손으로 만든 곳과 일부러 비운 곳은 뺀다).

    "중구"처럼 여러 시도에 같은 이름이 있으므로 시도 이름을 앞에 붙여 구분한다.
    """
    records = []
    for sido in sido_list():
        if not sido["code"].isdigit():
            continue
        short = SIDO_SHORT[sido["name"]]
        for gu in sido["sigungu"]:
            code = gu["code"]
            if code in SIGUNGU_SKIP or code in SIGUNGU_HANDMADE:
                continue
            months = [ok_month(f"2026-0{i + 1}", *_numbers(code, i)) for i in range(6)]
            records.append(sigungu(code, f"{short}-{gu['name']}", months))
    return records


def held(status: str, reason: str) -> dict:
    return {**SIDO_APPLICABILITY, "R07": {"status": status, "reason": reason}}


def build() -> dict:
    national = record(
        "DEMO-R07-NATIONAL",
        [
            ok_month("2026-01", 820, 10000, 450),  # 01→02 금액 감소·비중 증가 (반대)
            ok_month("2026-02", 790, 9400, 520),  # 02→03 금액 증가·비중 감소 (반대)
            ok_month("2026-03", 860, 10300, 560),  # 03→04 같은 방향
            ok_month("2026-04", 905, 10600, 540),  # 04→05 같은 방향, 비중 변화 0.01%p 미만
            ok_month("2026-05", 930, 10890, 900),  # 05→06 같은 방향
            ok_month("2026-06", 880, 10700, 760),
        ],
    )
    sido_hold = record(
        "DEMO-R07-SIDO-HOLD",
        [
            ok_month("2026-01", 120, 1500, 90),
            ok_month("2026-02", 135, 1580, 100),
            status_month("2026-03", "no_data", warnings=("해당 월 관측 행 없음",)),
            ok_month("2026-04", 128, 1540, 95),
            status_month("2026-05", "invalid_denominator", F=0, T=0, U=0, C=0, warnings=("전체 금액 0으로 비중 계산 불가",)),
            ok_month("2026-06", 131, 1560, 98),
        ],
        geographic_scope="sido",
        region_key="DEMO-SIDO-A",
        applicability={
            "R07": {"status": "needs_review", "reason": "합성 보류 예시: 시도 자료의 누락 월이 많아 비교 결론 보류"},
            "R06": {"status": "blocked", "reason": "업종·월 보정 자료 없음"},
            "R02": {"status": "blocked", "reason": "지역 기준 미확인"},
        },
        limitations=["합성 자료", "가상 시도 예시이며 실제 지역이 아님", "누락 월을 0으로 해석하지 않음"],
    )
    # ------------------------------------------------------------ 시도 16곳
    # 입력 화면의 시도 17곳 중 16곳에 레코드를 둔다. 세종특별자치시는 **일부러 비워**
    # "선택한 지역의 자료가 없어 전국으로 되돌립니다" 화면을 시연할 수 있게 한다.
    # 지역마다 다른 상황을 담아, 지역을 바꿔 고르는 것만으로 근거 화면의 모든 경우를 볼 수 있다.
    # 어느 지역에 어느 상황을 둘지는 시연 편의로 정한 것이며, 사유 문장은 지역이 아니라
    # **자료의 상태**만 말한다 ("○○ 지역이 문제"로 읽히지 않게).
    sidos = [
        # 서울: 정상. 금액과 비중의 방향이 반대인 구간 2개 (핵심 질문이 나오는 화면)
        sido("1100000000", "SEOUL", [
            ok_month("2026-01", 320, 4000, 250),  # 01→02 금액 감소·비중 증가 (반대)
            ok_month("2026-02", 305, 3800, 260),  # 02→03 금액 증가·비중 감소 (반대)
            ok_month("2026-03", 345, 4300, 270),
            ok_month("2026-04", 360, 4400, 265),
            ok_month("2026-05", 380, 4600, 300),
            ok_month("2026-06", 365, 4500, 290),
        ]),
        # 부산: 정상이되 반대 구간이 하나도 없음 ("반대만 모아 둔 자료가 아니다")
        sido("2600000000", "BUSAN", [
            ok_month("2026-01", 200, 2500, 150),
            ok_month("2026-02", 220, 2650, 160),
            ok_month("2026-03", 240, 2800, 170),
            ok_month("2026-04", 255, 2900, 175),
            ok_month("2026-05", 270, 3000, 180),
            ok_month("2026-06", 260, 2950, 175),
        ]),
        # 대구: 한 달이 "입력 확인 필요" (자료에 약속과 다른 값이 있던 달)
        sido("2700000000", "DAEGU", [
            ok_month("2026-01", 180, 2200, 140),
            ok_month("2026-02", 190, 2300, 145),
            status_month("2026-03", "invalid_input", warnings=("성별 코드가 약속과 다른 값이어서 이 달은 계산하지 않음",)),
            ok_month("2026-04", 200, 2400, 150),
            ok_month("2026-05", 210, 2500, 155),
            ok_month("2026-06", 205, 2450, 150),
        ]),
        # 인천: 한 달이 "자료 없음" → 앞뒤 구간을 잇지 않고 둘 다 보류
        sido("2800000000", "INCHEON", [
            ok_month("2026-01", 160, 2000, 120),
            ok_month("2026-02", 170, 2100, 125),
            status_month("2026-03", "no_data", warnings=("해당 월 관측 행 없음",)),
            ok_month("2026-04", 180, 2200, 130),
            ok_month("2026-05", 190, 2300, 135),
            ok_month("2026-06", 185, 2250, 132),
        ]),
        # 광주: 한 달의 전체 금액이 0 → 분모 0으로 비중 계산 불가
        sido("2900000000", "GWANGJU", [
            ok_month("2026-01", 120, 1500, 90),
            ok_month("2026-02", 125, 1550, 92),
            ok_month("2026-03", 130, 1600, 95),
            status_month("2026-04", "invalid_denominator", F=0, T=0, U=0, C=0, warnings=("전체 금액 0으로 비중 계산 불가",)),
            ok_month("2026-05", 135, 1650, 98),
            ok_month("2026-06", 132, 1620, 96),
        ]),
        # 대전: 첫 달 외국인 금액이 0 → 증감률은 계산 불가, 금액 차이는 유효
        sido("3000000000", "DAEJEON", [
            ok_month("2026-01", 0, 1800, 130, warnings=("외국인 집단 관측 행 없음 (실제 소비 0으로 단정하지 않음)",)),
            ok_month("2026-02", 110, 1850, 135),
            ok_month("2026-03", 120, 1900, 140),
            ok_month("2026-04", 125, 1950, 142),
            ok_month("2026-05", 130, 2000, 145),
            ok_month("2026-06", 128, 1980, 143),
        ]),
        # 울산: 두 달 값이 완전히 같음 → "변화 없음"
        sido("3100000000", "ULSAN", [
            ok_month("2026-01", 100, 1300, 80),
            ok_month("2026-02", 100, 1300, 80),
            ok_month("2026-03", 110, 1400, 85),
            ok_month("2026-04", 115, 1450, 88),
            ok_month("2026-05", 120, 1500, 90),
            ok_month("2026-06", 118, 1480, 89),
        ]),
        # 경기: 비중 변화가 0.01%p 미만인 구간 (아주 작은 수 표시 규칙)
        sido("4100000000", "GYEONGGI", [
            ok_month("2026-01", 800, 10000, 1000),  # 01→02 비중 변화 −0.0004%p
            ok_month("2026-02", 801, 10013, 1000),
            ok_month("2026-03", 850, 10500, 1050),
            ok_month("2026-04", 880, 10800, 1080),
            ok_month("2026-05", 900, 11000, 1100),
            ok_month("2026-06", 890, 10900, 1090),
        ]),
        # 강원: 예시 기획(강릉시)이 쓰는 레코드. 지금 캡처가 이 화면이다
        sido("5100000000", "GANGWON", [
            ok_month("2026-01", 110, 1400, 70),  # 01→02 금액 감소·비중 증가 (반대)
            ok_month("2026-02", 104, 1280, 75),  # 02→03 금액 증가·비중 감소 (반대)
            ok_month("2026-03", 118, 1500, 80),
            ok_month("2026-04", 125, 1560, 78),
            ok_month("2026-05", 132, 1620, 95),
            ok_month("2026-06", 128, 1600, 90),
        ]),
        # 충북: 전체 분모 비중과 미상 제외 비중의 방향이 서로 다름 (비교 B만 반대)
        sido("4300000000", "CHUNGBUK", [
            ok_month("2026-01", 400, 5000, 500),
            ok_month("2026-02", 395, 5250, 1000),
            ok_month("2026-03", 410, 5300, 900),
            ok_month("2026-04", 420, 5400, 850),
            ok_month("2026-05", 430, 5500, 800),
            ok_month("2026-06", 425, 5450, 820),
        ]),
        # 충남: 한 달의 미상 금액이 전체와 같음 → 미상 제외 비중을 낼 수 없음
        sido("4400000000", "CHUNGNAM", [
            ok_month("2026-01", 300, 3800, 280),
            ok_month("2026-02", 0, 2000, 2000),
            ok_month("2026-03", 310, 3900, 290),
            ok_month("2026-04", 320, 4000, 295),
            ok_month("2026-05", 330, 4100, 300),
            ok_month("2026-06", 325, 4050, 298),
        ]),
        # 전북: 적용 상태가 "확인 필요" → 수치는 보이고 요약 문장만 보류
        sido("5200000000", "JEONBUK", [
            ok_month("2026-01", 140, 1800, 110),
            ok_month("2026-02", 145, 1850, 112),
            ok_month("2026-03", 150, 1900, 115),
            ok_month("2026-04", 155, 1950, 118),
            ok_month("2026-05", 160, 2000, 120),
            ok_month("2026-06", 158, 1980, 119),
        ], applicability=held("needs_review", "지역 분류 기준(가맹점 소재지 여부)을 확인하는 중인 자료")),
        # 전남: 적용 상태가 "사용 불가" → 지역 수치를 쓰지 않고 전국으로 되돌린다
        sido("4600000000", "JEONNAM", [
            ok_month("2026-01", 130, 1700, 100),
            ok_month("2026-02", 135, 1750, 105),
            ok_month("2026-03", 140, 1800, 108),
            ok_month("2026-04", 145, 1850, 110),
            ok_month("2026-05", 150, 1900, 112),
            ok_month("2026-06", 148, 1880, 111),
        ], applicability=held("blocked", "가맹점 소재지 기준이 확인되지 않아 지역 비교에 사용할 수 없는 자료")),
        # 경북: 6개월 중 계산 가능한 달이 3개월 → 표본 부족 화면
        sido("4700000000", "GYEONGBUK", [
            ok_month("2026-01", 150, 1900, 115),
            status_month("2026-02", "no_data", warnings=("해당 월 관측 행 없음",)),
            status_month("2026-03", "no_data", warnings=("해당 월 관측 행 없음",)),
            ok_month("2026-04", 160, 2000, 120),
            status_month("2026-05", "invalid_denominator", F=0, T=0, U=0, C=0, warnings=("전체 금액 0으로 비중 계산 불가",)),
            ok_month("2026-06", 165, 2050, 122),
        ]),
        # 경남: 평범한 정상 자료
        sido("4800000000", "GYEONGNAM", [
            ok_month("2026-01", 170, 2100, 130),
            ok_month("2026-02", 175, 2150, 133),
            ok_month("2026-03", 180, 2200, 136),
            ok_month("2026-04", 185, 2250, 138),
            ok_month("2026-05", 190, 2300, 140),
            ok_month("2026-06", 188, 2280, 139),
        ]),
        # 제주: 평범한 정상 자료 (외국인 비중이 높은 편)
        sido("5000000000", "JEJU", [
            ok_month("2026-01", 250, 2000, 150),
            ok_month("2026-02", 260, 2050, 155),
            ok_month("2026-03", 270, 2100, 158),
            ok_month("2026-04", 280, 2150, 160),
            ok_month("2026-05", 290, 2200, 165),
            ok_month("2026-06", 285, 2180, 163),
        ]),
        # 세종특별자치시(3600000000)는 일부러 넣지 않는다 — "자료 없음 → 전국으로 되돌림" 시연용
    ]

    # ------------------------------------------------------------ 시군구 3곳
    # 시군구 자료는 표본이 작아 전면 적용이 어렵다. **확장이 가능하다는 것**과
    # **왜 아직 전면 적용을 안 하는지**를 같은 화면으로 보이려고 세 가지 경우만 둔다.
    # 나머지 시군구(예: 강릉시)는 레코드가 없어 자동으로 시도 자료로 넓혀진다.
    sigungus = [
        # 강릉시: 예시 기획이 고르는 지역. 캡처에 쓰이므로 손으로 설계한다 —
        # 반대 2구간·같음 3구간으로 "반대인 경우만 모아 둔 자료가 아니다"를 보이게 한다
        sigungu("5115000000", "강원-강릉시", [
            ok_month("2026-01", 130, 1600, 95),   # 01→02 금액 감소·비중 증가 (반대)
            ok_month("2026-02", 123, 1470, 100),  # 02→03 금액 증가·비중 감소 (반대)
            ok_month("2026-03", 140, 1720, 105),
            ok_month("2026-04", 148, 1790, 103),
            ok_month("2026-05", 156, 1860, 118),
            ok_month("2026-06", 152, 1840, 115),
        ]),
        # 춘천시: 시군구 자료가 있고 쓸 수 있음 → 고른 그 지역 자료가 그대로 나온다
        sigungu("5111000000", "강원-춘천시", [
            ok_month("2026-01", 60, 800, 45),
            ok_month("2026-02", 58, 760, 46),
            ok_month("2026-03", 64, 850, 48),
            ok_month("2026-04", 68, 880, 47),
            ok_month("2026-05", 72, 920, 55),
            ok_month("2026-06", 70, 900, 53),
        ]),
        # 서울 종로구: 표본 부족 → 같은 지역의 더 넓은 범위(서울특별시) 자료로 넓힌다
        sigungu("1111000000", "서울-종로구", [
            ok_month("2026-01", 40, 500, 30),
            status_month("2026-02", "no_data", warnings=("해당 월 관측 행 없음",)),
            status_month("2026-03", "no_data", warnings=("해당 월 관측 행 없음",)),
            ok_month("2026-04", 44, 540, 32),
            status_month("2026-05", "no_data", warnings=("해당 월 관측 행 없음",)),
            ok_month("2026-06", 46, 560, 33),
        ]),
        # 제주시: 사용 불가 → 제주특별자치도 자료로 넓히고 사유를 밝힌다
        sigungu("5011000000", "제주-제주시", [
            ok_month("2026-01", 90, 700, 50),
            ok_month("2026-02", 94, 720, 52),
            ok_month("2026-03", 98, 750, 54),
            ok_month("2026-04", 102, 780, 55),
            ok_month("2026-05", 106, 800, 57),
            ok_month("2026-06", 104, 790, 56),
        ], applicability=held("blocked", "가맹점 소재지 기준이 확인되지 않아 시군구 비교에 사용할 수 없는 자료")),
    ]

    # 보류 사례 예시(sido_hold)를 전국 바로 뒤에 둔다. 화면은 예시를 한 건만 보여 준다
    records = [national, sido_hold, *sidos, *sigungus, *auto_sigungus()]
    data = evidence_file(records, dataset_version=DATASET_VERSION, schema_version=PROFILE_VERSION)
    data["profiles"] = demo_profiles(records)
    data["thresholds"] = DEMO_THRESHOLDS
    return data


# ---------------------------------------------------------------- 2.1 지역 프로필 (시연용)

# 업종 이름은 **시연용 이름**이다. 실제 업종 11개의 이름과 코드는 데이터 담당이 2.1 파일에 넣는다
# (7지역확장계획.md 8장). 여기서 실제 이름을 지어 쓰면 공개물이 제공 자료의 구성을 암시하게 된다.
DEMO_INDUSTRIES = [(f"IND{i:02d}", f"시연 업종 {chr(ord('A') + i - 1)}") for i in range(1, 12)]
# 연령 구간 이름은 제공 자료의 칸 정의를 그대로 쓴다 (수치는 합성이다).
# 코드 1의 경계는 확인 전이라 화면에서 주민등록 연령대와 맞대어 놓지 않는다
DEMO_AGES = [
    ("AGE1", "20대 이하"),
    ("AGE2", "20대"),
    ("AGE3", "30대"),
    ("AGE4", "40대"),
    ("AGE5", "50대"),
    ("AGE6", "60대 이상"),
]
DEMO_MONTHS = [f"2026-0{i}" for i in range(1, 7)]

PROFILE_LIMITATIONS = [
    "시연용 합성 수치이며 실제 지역 소비를 나타내지 않음",
    "지역 구분의 기준(가맹점 자리인지 이용자 기준인지)은 확인 전",
]

DEMO_THRESHOLDS = {
    "version": "demo-th-1",
    "R02": {"low_share_percentile": 20.0},
    "R08": {"low_share_percentile": 20.0},
    "R04": {"season_index": 1.10, "season_index_small_region": 1.25},
    "R12": {"low_foreign_percentile": 20.0},
    "R11": {"visitor_to_resident_ratio": 1.0},
}


def _spread(text: str) -> int:
    """글자에서 0~9999 사이 값을 만든다. 같은 글자면 항상 같은 값이다(난수를 쓰지 않는다).

    지역 코드는 끝자리에 0이 많아 그대로 나누면 값이 한쪽으로 몰린다. 자리마다 소수를 곱해 흩는다.
    """
    value = 2166136261
    for ch in text:
        value = (value ^ ord(ch)) * 16777619 % 2**32
    return value % 10_000


def _weights(seed: int, count: int, spread: int) -> list[float]:
    """합이 100이 되는 구성비. 같은 코드면 항상 같은 값이 나온다(난수를 쓰지 않는다)."""
    raw = [10 + (seed // (7**i) + i * spread) % 40 for i in range(count)]
    total = sum(raw)
    shares = [round(value * 100 / total, 2) for value in raw]
    # 반올림 오차를 마지막 항목으로 맞춘다 (합이 100이어야 경고가 나지 않는다)
    shares[-1] = round(shares[-1] + (100 - sum(shares)), 2)
    return shares


def _share_items(codes: list[tuple[str, str]], shares: list[float], scale: int, key: str) -> list[dict]:
    """구성비 항목. 전국에서의 자리(percentile)도 함께 넣는다.

    percentile은 같은 지표를 가진 지역들 사이의 자리이며, 몇 곳 중인지(regions)와 항상 함께 둔다.
    값은 코드에서 만들어 낸 가상 수치다.
    """
    items = []
    for index, ((code, label), share) in enumerate(zip(codes, shares, strict=True)):
        percentile = round(_spread(f"{key}-{code}") % 1000 / 10, 1)
        items.append(
            {
                "code": code,
                "label": label,
                "amount": int(round(share * scale)),
                "share_pct": share,
                "status": "ok",
                "percentile": percentile,
                "regions": DEMO_RANK_REGIONS,
            }
        )
    return items


def demo_profile(region_key: str, scope: str) -> dict:
    """지역 한 곳의 시연용 프로필. 모든 값은 코드에서 만들어 낸 가상 수치다."""
    seed = int(region_key) if region_key.isdigit() else 7_000_000_000
    industry = _share_items(DEMO_INDUSTRIES, _weights(seed, len(DEMO_INDUSTRIES), 3), scale=90, key=region_key)
    age = _share_items(DEMO_AGES, _weights(seed // 3 + 11, len(DEMO_AGES), 5), scale=160, key=f"age-{region_key}")

    # 업종 안의 연령 구성. 각 업종마다 합이 100이며, 순위는 같은 업종×연령 항목을 가진
    # 시연 지역들 사이의 자리다. 실제 이름·수치·분포는 사용하지 않는다.
    industry_age = []
    for industry_index, (industry_code, _label) in enumerate(DEMO_INDUSTRIES):
        ages = _share_items(
            DEMO_AGES,
            _weights(seed // (industry_index + 2) + industry_index * 17, len(DEMO_AGES), 7),
            scale=40,
            key=f"industry-age-{region_key}-{industry_code}",
        )
        industry_age.append(
            {
                "industry_code": industry_code,
                "age_denominator": "known_only",
                "ages": ages,
            }
        )

    # 지역 한 곳(강릉시)의 첫 업종은 결제가 0인 사례로 둔다 — "결제 없음"과 "자료 없음"이
    # 화면에서 어떻게 다른지 보이려는 것이다. 상점이 없다는 뜻이 아니다
    if region_key == "5115000000":
        zero = dict(industry[0])
        moved = zero["share_pct"]
        zero.update(amount=0, share_pct=0.0, percentile=0.0)
        industry[0] = zero
        industry[1] = {**industry[1], "share_pct": round(industry[1]["share_pct"] + moved, 2)}
        # R08 화면 확인용 합성 사례. 두 번째 업종 안에서 첫 연령 구간의 전국 자리를
        # 운영 기준 아래로 둔다. 구성비 자체는 위의 가상 분포를 그대로 쓴다.
        industry_age[1]["ages"][0] = {**industry_age[1]["ages"][0], "percentile": 10.0}

    months = []
    for index, month in enumerate(DEMO_MONTHS):
        # 지역마다 한 달을 "자료 없음"으로 둬서 빈 달 표시를 확인할 수 있게 한다
        if index == (seed // 1_000) % 12 and scope == "sigungu":
            months.append({"month": month, "status": "no_data", "season_index": None})
            continue
        wave = _spread(f"season-{region_key}-{month}") % 60 / 100  # 0.00 ~ 0.59
        months.append({"month": month, "status": "ok", "season_index": round(0.82 + wave, 2)})

    size_percentile = round(2 + (seed // 7) % 960 / 10, 1)
    foreign = round(2.0 + (seed // 100_000) % 100 / 10, 1)   # 2.0 ~ 11.9
    unknown = round(0.5 + (seed // 10_000) % 200 / 10, 1)    # 0.5 ~ 20.4
    # 외부 인구도 시연용 합성값이다. 카드 자료와 관측 시점이 다를 수 있음을 보이기 위해
    # 날짜와 출처 이름을 값에 붙인다. 카드 결제값을 이 수로 나누지는 않는다.
    population = 40_000 + _spread(f"population-{region_key}") * 25
    registered_foreigners = _spread(f"registered-foreigners-{region_key}") * 2
    return {
        "region_key": region_key,
        "geographic_scope": scope,
        # 주최 측 확인 전이라 가맹점 자리 기준이라고 단정하지 않는다 (7지역확장계획.md 8장 1번)
        "region_basis": "unconfirmed",
        "period_start": DEMO_MONTHS[0],
        "period_end": DEMO_MONTHS[-1],
        "industry": industry,
        "age": age,
        "industry_age": industry_age,
        "external": {
            "population": {
                "status": "ok",
                "count": population,
                "observed_at": "2026-06-30",
                "source_name": "시연용 합성 주민등록인구",
            },
            "registered_foreigners": {
                "status": "ok",
                "count": registered_foreigners,
                "observed_at": "2026-06-30",
                "source_name": "시연용 합성 등록외국인",
            },
        },
        "age_denominator": "known_only",
        "months": months,
        "foreign_share_pct": foreign,
        "unknown_share_pct": unknown,
        "ranks": {
            # 0.0%나 100.0% 지점이 나오지 않게 안쪽으로 둔다 — 시연 화면이 "전국 꼴찌"처럼 읽히지 않게
            "foreign_share": {"percentile": round(2 + seed % 960 / 10, 1), "regions": DEMO_RANK_REGIONS},
            "payment_amount": {"percentile": size_percentile, "regions": DEMO_RANK_REGIONS},
        },
        # 결제 규모가 작은 지역(시연 기준: 규모 자리가 아래쪽인 곳)은 달마다 크게 흔들린다
        "small_region": size_percentile <= 20.0,
        "readiness": {
            "profile": "ok",
            "industry": "ok",
            "age": "ok",
            "industry_age": "ok",
            "season": "ok",
            "foreign": "ok",
            # 유사 지역은 쓸 업종 목록이 확정되지 않아 아직 만들지 않았다
            "peers": "unlinked",
            "external": "ok",
        },
        "limitations": list(PROFILE_LIMITATIONS),
    }


def demo_profiles(records: list[dict]) -> list[dict]:
    """레코드가 있는 지역마다 프로필 하나. 레코드가 없는 지역은 프로필도 없다.

    한 곳(춘천시)은 일부러 "자료가 부족해 보여 주지 않음" 상태로 둔다 — 화면이 그 사정을
    올바로 알리는지 확인하려는 것이다.
    """
    profiles = []
    for rec in records:
        scope = rec["scope"]["geographic_scope"]
        key = rec["scope"]["region_key"]
        if not key.isdigit() and key != "ALL":
            continue  # 시험용 합성 키(DEMO-SIDO-A)는 프로필을 만들지 않는다
        profile = demo_profile(key, scope)
        if key == "5111000000":
            profile["readiness"] = {
                **profile["readiness"],
                "profile": "insufficient",
                "industry": "insufficient",
                "industry_age": "insufficient",
            }
        profiles.append(profile)
    return profiles


def main() -> int:
    write_json(OUT_PATH, build())
    result = load_evidence(OUT_PATH)
    if result.warnings:
        print("경고가 있습니다:", *result.warnings, sep="\n  ")
        return 1
    for rec in result.file.records:
        s = summarize_pairs(compare_record(rec))
        print(
            f"{rec.evidence_id}: 구간 {s.pair_count}, 비교 가능 {s.comparable_count}, "
            f"비교 A 반대 {s.opposite_a_count}, 같음 {s.same_a_count}, 보류 {s.skipped_count}"
        )
    print(f"-> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
