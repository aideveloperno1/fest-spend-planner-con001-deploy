from dataclasses import dataclass, field
from datetime import date

from ..labels import DATA_STATUS_LABELS
from .models import BudgetStatus, BusinessType, DataStatus, Goal, Metric, PlanInput, RegionLevel
from .regions import is_known_region


@dataclass
class ValidationResult:
    errors: dict[str, str] = field(default_factory=dict)
    # 선택 항목 중 비어 있어 기획안에 "추가 확정 필요"로 남을 항목
    pending: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def validate_plan(plan: PlanInput) -> ValidationResult:
    errors: dict[str, str] = {}

    if not plan.name:
        errors["name"] = "사업명을 입력해 주세요."

    if plan.business_type is None:
        # 고르지 않은 기획을 서비스가 한 유형으로 분류하지 않는다 (7지역확장계획.md D9)
        errors["business_type"] = "사업 유형을 골라 주세요."

    if not plan.goals:
        errors["goals"] = "사업 목표를 하나 이상 골라 주세요."
    elif Goal.OTHER in plan.goals and not plan.goal_other:
        errors["goal_other"] = "기타 목표의 내용을 적어 주세요."

    if not plan.target:
        errors["target"] = "사업 대상을 입력해 주세요."

    region = plan.region
    if region is None:
        errors["region"] = "지역 범위를 골라 주세요."
    elif region.level is not RegionLevel.NATIONAL and not region.sido_code:
        errors["region"] = "시도를 골라 주세요."
    elif region.level is RegionLevel.SIGUNGU and not region.sigungu_code:
        errors["region"] = "시군구를 골라 주세요."
    elif not is_known_region(region):
        errors["region"] = "목록에 없는 지역입니다. 다시 골라 주세요."

    start, end = _parse_date(plan.period_start), _parse_date(plan.period_end)
    if not plan.period_start or not plan.period_end:
        errors["period"] = "시작일과 종료일을 모두 입력해 주세요."
    elif start is None or end is None:
        errors["period"] = "날짜 형식이 올바르지 않습니다."
    elif end < start:
        errors["period"] = "종료일이 시작일보다 빠릅니다."

    if plan.budget.status is BudgetStatus.AMOUNT and plan.budget.krw is None:
        errors["budget"] = "예산은 0 이상의 원 단위 정수로 입력해 주세요."
    elif plan.budget.status is BudgetStatus.UNDECIDED and plan.budget.raw.strip():
        # 금액과 [미정]이 함께 오면 금액을 조용히 버리지 않고 물어본다 (9/18)
        errors["budget"] = "금액과 [미정] 중 하나만 남겨 주세요. 금액을 쓰려면 [미정] 체크를 풀어 주세요."

    selected_metrics = [metric for metric in plan.metrics if metric is not Metric.OTHER]
    if not selected_metrics and not plan.metric_others:
        errors["metrics"] = "현재 성과지표를 고르거나 직접 입력해 주세요."

    if plan.indicator_use is None:
        errors["indicator_use"] = "지표를 어떻게 쓰는지 골라 주세요."

    if plan.visitor_goal is None and plan.visitor_goal_raw.strip():
        # 빈칸은 "적지 않음"이라 넘어가고, 숫자로 읽지 못한 값만 물어본다
        errors["visitor_goal"] = "목표 방문객 수는 0 이상의 정수로 입력해 주세요."

    pending: list[str] = []
    if plan.budget.status is BudgetStatus.UNSET:
        pending.append("예산 (미입력)")
    elif plan.budget.status is BudgetStatus.UNDECIDED:
        pending.append("예산 (미정)")
    if plan.business_type is BusinessType.COUPON and not plan.usage_place:
        pending.append("쿠폰 사용처")
    if plan.business_type is BusinessType.FESTIVAL and plan.visitor_goal is None:
        # 축제·행사에서만 묻는다. 다른 유형에서는 없어도 빠진 항목이 아니다
        pending.append("목표 방문객 수 (미입력)")
    if plan.data_status is None:
        pending.append("자료 확보 상태 (선택 안 함)")
    elif plan.data_status is not DataStatus.SECURED:
        # 고른 값을 함께 보여 준다. 고르기 전과 고른 뒤가 구분되지 않으면
        # "선택했는데 왜 그대로지?"로 읽힌다 (사용자 확인 9/18)
        pending.append(f"성과 자료 확보 ({DATA_STATUS_LABELS[plan.data_status]})")

    return ValidationResult(errors=errors, pending=pending)
