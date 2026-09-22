"""랜딩 화면에 쓰는 글자. 화면과 어긋나지 않게 한곳에 모은다.

지키는 것 (tests/test_landing.py가 검사한다):
- 규칙 관리 번호(R01~R07)를 쓰지 않는다. 규칙 제목만 쓴다 (사용자 결정 2026-09-18)
- 행정표준코드 10자리를 쓰지 않는다. 지역 이름으로만 적는다
- 실제 자료 버전(real-…)이나 실제 수치를 쓰지 않는다. 공개 계층 합성 자료 기준이다
지역 예시는 기본 합성 자료의 범위와 일치시킨다.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    num: str
    title: str
    note: str


@dataclass(frozen=True)
class Card:
    title: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class LadderCase:
    """지역 사다리 시연 한 칸. used는 실제로 쓰는 범위(sigungu·sido·national)."""

    key: str
    chip: str
    used: str
    scope_label: str
    note: str


@dataclass(frozen=True)
class Rule:
    stage: str
    title: str
    note: str


@dataclass(frozen=True)
class LandingContent:
    hero_eyebrow: str
    hero_title_1: str
    hero_title_strong: str
    hero_title_2: str
    hero_lead: str
    hero_note: str
    steps: tuple[Step, ...]
    steps_note: str
    before: Card
    after: Card
    outputs: Card
    evidence_summary: str
    method_lines: tuple[str, ...]
    limitation_line: str
    ladder_intro: str
    ladder_cases: tuple[LadderCase, ...]
    ladder_foot: str
    trust_cards: tuple[Card, ...]
    hold_months: tuple[tuple[str, str], ...]
    rules: tuple[Rule, ...]
    closing_title: str
    closing_lead: str
    foot: str
    nav: tuple[tuple[str, str], ...] = field(default=())


LANDING = LandingContent(
    hero_eyebrow="소비데이터 기반 기획서 보완 서비스",
    hero_title_1="차트를 보여주는 대신,",
    hero_title_strong="기획안의 한 줄",
    hero_title_2="을 고칩니다",
    hero_lead=(
        "소비데이터에서 찾은 근거를 질문으로 바꾸고, 담당자의 선택을 보완 기획안 문장에 그대로 반영합니다. "
        "모든 변경에는 근거와 선택 기록이 남습니다."
    ),
    hero_note="화면의 모든 수치는 시연용 합성 수치입니다 · 자료 버전 demo-hierarchy-002",
    steps=(
        Step("1", "기획 입력", "지표의 용도까지 확인"),
        Step("2", "근거 확인", "금액·비중 방향 비교"),
        Step("3", "검토 질문", "결론이 아니라 물음"),
        Step("4", "보완 선택", "결정은 담당자"),
        Step("5", "보완 기획안", "변경마다 근거 기록"),
    ),
    steps_note="근거가 부족하면 결론을 내지 않고 보류합니다.",
    before=Card("기존 방식", (
        "차트를 확인하고 끝난다",
        "해석과 문서 수정은 담당자 몫",
        "변경의 근거가 어디에도 남지 않는다",
    )),
    after=Card("콕콕", (
        "근거 → 질문 → 선택 → 문서 수정까지 연결",
        "변경 문장마다 근거 표시가 붙는다",
        "근거가 부족하면 보류로 남긴다",
    )),
    outputs=Card("산출물", (
        "편집 가능한 보완 기획안 Word 문서",
        "추가 확정 필요 목록",
        "정밀 분석 요청서 초안",
    )),
    evidence_summary=(
        "2026년 1~6월 시연용 합성 자료에서 지역을 바꾸면 그 지역의 월별 결제금액과 비중 흐름을 확인할 수 있습니다. "
        "상위 지역의 금액과 건수는 겹치지 않는 하위 지역의 합입니다."
    ),
    method_lines=(
        "전체 분모 외국인 비중 = 외국인 결제금액 ÷ 전체 결제금액 × 100",
        "미상 제외 외국인 비중 = 외국인 결제금액 ÷ (전체 결제금액 − 미상 금액) × 100",
        "변화 방향은 반올림한 비중이 아니라 원래 금액의 교차곱으로 판정합니다",
    ),
    limitation_line=(
        "외국인 전체 기준이며 관광객을 따로 보지 않습니다 · 미상 제외 비중을 정답으로 해석하지 않습니다"
    ),
    ladder_intro="선택한 시군구·시도·전국의 합성 자료를 각각 보여 줍니다. 이 범위들은 실제 소비 진단이 아닙니다.",
    ladder_cases=(
        LadderCase(
            "gangneung", "강원 강릉시", "sigungu",
            "강원특별자치도 강릉시 범위 참고 — 선택 지역의 진단이 아님",
            "고른 지역의 자료를 그대로 씁니다. 넓히지 않았습니다.",
        ),
        LadderCase(
            "taebaek", "강원 태백시", "sigungu",
            "강원특별자치도 태백시 범위 참고 — 선택 지역의 진단이 아님",
            "태백시 고유의 합성 월별 자료를 보여 줍니다. 강원특별자치도 자료로 대신하지 않습니다.",
        ),
        LadderCase(
            "jongno", "서울 종로구", "sigungu",
            "서울특별시 종로구 범위 참고 — 선택 지역의 진단이 아님",
            "종로구 고유의 합성 월별 자료를 보여 줍니다. 표본 부족 시연은 별도 시험 자료에서 확인합니다.",
        ),
        LadderCase(
            "jejusi", "제주 제주시", "sigungu",
            "제주특별자치도 제주시 범위 참고 — 선택 지역의 진단이 아님",
            "제주시 고유의 합성 월별 자료를 보여 줍니다. 제주특별자치도 값에는 서귀포시도 함께 합산됩니다.",
        ),
        LadderCase(
            "sejong", "세종특별자치시", "sido",
            "세종특별자치시 범위 참고 — 선택 지역의 진단이 아님",
            "시군구 선택지가 없는 세종은 시도 자체의 합성 자료를 보여 줍니다.",
        ),
    ),
    ladder_foot=(
        "시연 자료에는 시군구 자료를 모두 넣어 두었습니다. 실제로는 시군구 단위 표본이 작아 "
        "전면 적용이 어렵고, 자료가 갖춰지는 지역부터 코드 수정 없이 좁은 범위로 내려갑니다."
    ),
    trust_cards=(
        Card("보류", (
            "자료가 없으면 0으로 채우지 않습니다.",
            "계산할 수 없는 달은 빈칸으로 남고, 그 이유를 적습니다.",
        )),
        Card("추적", (
            "문장 → 근거 → 질문 → 선택",
            "보완 기획안의 모든 변경은 근거와 담당자 선택으로 거슬러 확인할 수 있습니다. 자료 버전도 함께 남습니다.",
        )),
        Card("범위", (
            "검토하지 않은 항목을 밝힙니다.",
            "‘문제없음’과 ‘검토하지 않음’을 구분합니다. 점수·신호등·적합 판정은 쓰지 않습니다.",
        )),
    ),
    hold_months=(
        ("3월", "계산됨"),
        ("4월", "자료 없음"),
        ("5월", "분모 0 · 계산 불가"),
    ),
    rules=(
        Rule("구현 완료", "금액·비중과 성과지표 확인", "금액과 비중의 방향 차이를 근거로 성과지표 문장을 보완합니다"),
        Rule("구현 완료", "빠진 운영 조건 확인", "예산·사용처·자료 확보 상태가 비면 추가 확정 필요로 남깁니다"),
        Rule("분석 예시", "고급 소비 근거 확인", "업종 비중이 곧 고급 수요를 뜻하지 않음을 검토합니다"),
        Rule("향후 기능", "업종 후보 검토", "지역 기준과 운영 자료가 확인된 뒤에 적용합니다"),
    ),
    closing_title="예시 기획 하나로 보완 기획안까지",
    closing_lead=(
        "강원특별자치도 강릉시의 외국인 소비지원 쿠폰 사업을 예시로, "
        "근거 확인부터 Word 문서 저장까지 직접 따라가 보세요."
    ),
    foot="콕콕 · 소비데이터로 기획안 한 번 더 보기 · BC카드 소비데이터 활용 공모전 제안 · 화면의 모든 수치는 시연용 합성 수치입니다",
    nav=(("#flow", "서비스 흐름"), ("#evidence", "근거 설계"), ("#region", "지역 범위"), ("#trust", "신뢰 원칙")),
)
