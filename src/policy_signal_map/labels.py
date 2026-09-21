"""선택지 한글 문구. 화면과 보완 기획안 문서가 함께 쓴다 (document/는 web/을 import할 수 없다)."""

from .plan.models import BusinessType, DataStatus, Goal, IndicatorUse, Metric

BUSINESS_TYPE_LABELS: dict[BusinessType, str] = {
    BusinessType.COUPON: "쿠폰·지역화폐",
    BusinessType.FOREIGN_TOURISM: "외국인·관광",
    BusinessType.FESTIVAL: "축제·행사",
    BusinessType.AGE_TARGET: "연령 대상 사업",
}

BUSINESS_TYPE_NOTES: dict[BusinessType, str] = {
    BusinessType.COUPON: "소비 쿠폰, 지역화폐, 할인 행사처럼 사용처를 정하는 사업입니다.",
    BusinessType.FOREIGN_TOURISM: "외국인 관광객 유치나 외국인 소비 지원 사업입니다.",
    BusinessType.FESTIVAL: "지역 축제와 상권 행사입니다.",
    BusinessType.AGE_TARGET: "청년·어르신처럼 대상 연령을 정한 소비 지원 사업입니다.",
}

BUSINESS_TYPE_UNSET_LABEL = "고르지 않음"

GOAL_LABELS: dict[Goal, str] = {
    Goal.FOREIGN_AMOUNT: "외국인 결제금액 확대",
    Goal.FOREIGN_SHARE: "외국인 결제 비중 확대",
    Goal.STORE_USAGE: "참여 상점 이용 확대",
    Goal.OTHER: "기타",
}

METRIC_LABELS: dict[Metric, str] = {
    Metric.FOREIGN_SHARE: "외국인 결제 비중",
    Metric.FOREIGN_AMOUNT: "외국인 결제금액",
    Metric.PAYMENT_AMOUNT: "결제금액",
    Metric.PAYMENT_COUNT: "결제건수",
    Metric.PAYMENT_PER_CASE: "건당 결제금액",
    Metric.VISITORS: "방문객 수",
    Metric.PARTICIPANTS: "참여자 수",
    Metric.CUSTOMERS: "고객 수",
    Metric.COUPON_USAGE: "쿠폰 사용·정산 실적",
    Metric.OTHER: "기타",
}

# 입력 화면에서 지표를 묶어 보여 주는 순서. 자료로 잴 수 있는지를 고르기 전에 알 수 있게 한다.
# 묶음 이름은 안내일 뿐이며, 고른 지표를 서비스가 판정하지는 않는다
METRIC_GROUPS: list[tuple[str, list[Metric]]] = [
    (
        "카드 자료로 산출할 수 있는 지표",
        [
            Metric.PAYMENT_AMOUNT,
            Metric.PAYMENT_COUNT,
            Metric.PAYMENT_PER_CASE,
            Metric.FOREIGN_AMOUNT,
            Metric.FOREIGN_SHARE,
        ],
    ),
    ("카드 자료에 없어 별도 자료가 필요한 지표", [Metric.VISITORS, Metric.PARTICIPANTS, Metric.CUSTOMERS]),
    ("그 밖", [Metric.COUPON_USAGE, Metric.OTHER]),
]

INDICATOR_USE_LABELS: dict[IndicatorUse, str] = {
    IndicatorUse.DIRECT: "사업 성과로 직접 평가",
    IndicatorUse.REFERENCE: "참고 현황",
    IndicatorUse.UNKNOWN: "아직 모름",
}

INDICATOR_USE_NOTES: dict[IndicatorUse, str] = {
    IndicatorUse.DIRECT: "직접 평가에 쓰면 지표가 사업 목표를 대표하는지 먼저 확인합니다.",
    IndicatorUse.REFERENCE: "참고 현황으로 쓰면 오류로 표시하지 않고, 해석 조건만 문서에 적도록 제안합니다.",
    IndicatorUse.UNKNOWN: "용도가 정해지지 않았다면 결론을 내지 않고 선택지만 함께 보여줍니다.",
}

DATA_STATUS_LABELS: dict[DataStatus, str] = {
    DataStatus.SECURED: "확보됨",
    DataStatus.NEGOTIATING: "협의 중",
    DataStatus.UNDECIDED: "미정",
}

STEP_LABELS = ["기획 입력", "근거 확인", "검토 질문", "보완 선택", "보완 기획안"]

# 보완 기획안 별첨에 적는 결정 표기
DECISION_LABELS_FOR_DOCUMENT = {
    "keep_original": "원안 유지",
    "adopt": "채택",
    "modify": "대안을 고쳐서 적용",
    "hold": "보류",
}
