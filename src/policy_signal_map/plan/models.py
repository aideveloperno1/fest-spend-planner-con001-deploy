"""사용자가 입력하는 기획 원안의 형태. 워크플로우 3장 입력폼 최소 항목 기준."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Goal(StrEnum):
    FOREIGN_AMOUNT = "foreign_amount"
    FOREIGN_SHARE = "foreign_share"
    STORE_USAGE = "store_usage"
    OTHER = "other"


class BusinessType(StrEnum):
    """사업 유형. 3단계에서 켜질 질문 묶음을 고르는 값 (7지역확장계획.md 6장).

    고르지 않은 상태는 `None`으로 둔다. 서비스가 마음대로 한 유형으로 분류하지 않는다.
    """

    COUPON = "coupon"
    FOREIGN_TOURISM = "foreign_tourism"
    FESTIVAL = "festival"
    AGE_TARGET = "age_target"


class Metric(StrEnum):
    FOREIGN_SHARE = "foreign_share"
    FOREIGN_AMOUNT = "foreign_amount"
    PAYMENT_AMOUNT = "payment_amount"
    PAYMENT_COUNT = "payment_count"
    PAYMENT_PER_CASE = "payment_per_case"
    VISITORS = "visitors"
    PARTICIPANTS = "participants"
    CUSTOMERS = "customers"
    COUPON_USAGE = "coupon_usage"
    OTHER = "other"


# 카드 자료로 산출할 수 있는 지표와 산출할 수 없는 지표.
# 3단계 지표 점검(R10)이 쓴다. 쿠폰 사용 실적과 기타는 어느 쪽인지 데이터 담당 검수 전이라 넣지 않았다.
CARD_DERIVABLE_METRICS = frozenset(
    {Metric.FOREIGN_SHARE, Metric.FOREIGN_AMOUNT, Metric.PAYMENT_AMOUNT, Metric.PAYMENT_COUNT, Metric.PAYMENT_PER_CASE}
)
# 사람 수는 카드 자료에 없다. 결제 건수는 사람 수가 아니다
NON_CARD_METRICS = frozenset({Metric.VISITORS, Metric.PARTICIPANTS, Metric.CUSTOMERS})


class IndicatorUse(StrEnum):
    DIRECT = "direct"
    REFERENCE = "reference"
    UNKNOWN = "unknown"


class DataStatus(StrEnum):
    SECURED = "secured"
    NEGOTIATING = "negotiating"
    UNDECIDED = "undecided"


class RegionLevel(StrEnum):
    NATIONAL = "national"
    SIDO = "sido"
    SIGUNGU = "sigungu"


class BudgetStatus(StrEnum):
    UNSET = "unset"  # 입력하지 않음
    UNDECIDED = "undecided"  # 미정으로 표시함
    AMOUNT = "amount"  # 금액 입력 (0원 포함)


@dataclass
class Region:
    level: RegionLevel
    sido_code: str = ""
    sigungu_code: str = ""


@dataclass
class Budget:
    status: BudgetStatus = BudgetStatus.UNSET
    krw: int | None = None
    # 숫자로 읽지 못한 입력을 사용자가 고칠 수 있도록 원문을 남긴다
    raw: str = ""


@dataclass
class PlanInput:
    name: str = ""
    business_type: BusinessType | None = None
    goals: list[Goal] = field(default_factory=list)
    goal_other: str = ""
    target: str = ""
    region: Region | None = None
    period_start: str = ""  # YYYY-MM-DD
    period_end: str = ""
    budget: Budget = field(default_factory=Budget)
    usage_place: str = ""
    # 사용처 업종·대상 연령은 근거 파일이 알려 주는 코드다. 서비스가 목록을 지어내지 않는다
    usage_industries: list[str] = field(default_factory=list)
    target_ages: list[str] = field(default_factory=list)
    metrics: list[Metric] = field(default_factory=list)
    # 선택지에 없는 성과지표. 입력 행을 추가할 수 있으므로 순서를 지킨 목록으로 보관한다.
    metric_others: list[str] = field(default_factory=list)
    indicator_use: IndicatorUse | None = None
    data_status: DataStatus | None = None
    fixed_conditions: str = ""
    # 목표 방문객 수. None은 적지 않은 것이고 0은 0명이라고 적은 것이다 (둘을 구분한다)
    visitor_goal: int | None = None
    # 숫자로 읽지 못한 입력을 사용자가 고칠 수 있도록 원문을 남긴다 (예산과 같은 방식)
    visitor_goal_raw: str = ""


def sample_plan() -> PlanInput:
    """공개 시연용 예시 기획. 최종기획서 4-1장의 첫 시험 기획."""
    return PlanInput(
        name="하반기 외국인 소비지원 쿠폰",
        business_type=BusinessType.FOREIGN_TOURISM,
        goals=[Goal.FOREIGN_SHARE],
        target="외국인 전체",
        region=Region(RegionLevel.SIGUNGU, sido_code="5100000000", sigungu_code="5115000000"),
        period_start="2026-10-01",
        period_end="2026-12-31",
        budget=Budget(BudgetStatus.UNDECIDED),
        usage_place="관내 참여 점포",
        metrics=[Metric.FOREIGN_SHARE],
        indicator_use=IndicatorUse.DIRECT,
    )
