"""작업 상태를 Redis에 저장할 수 있는 버전 있는 JSON으로 바꾼다."""

from __future__ import annotations

import json
from typing import Any

from ..choices.models import (
    ArchivedChoice,
    Availability,
    Choice,
    ChoiceSet,
    Decision,
    ExecutionInput,
)
from ..llm.guard import Opinion
from ..llm.opinions import OpinionSet
from ..plan.models import (
    Budget,
    BudgetStatus,
    BusinessType,
    DataStatus,
    Goal,
    IndicatorUse,
    Metric,
    PlanInput,
    Region,
    RegionLevel,
)

SCHEMA_VERSION = 1


class SessionDataError(ValueError):
    """저장된 세션이 현재 코드에서 안전하게 읽을 수 없는 경우."""


def _plan_data(plan: PlanInput | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    return {
        "name": plan.name,
        "business_type": plan.business_type.value if plan.business_type else None,
        "goals": [value.value for value in plan.goals],
        "goal_other": plan.goal_other,
        "target": plan.target,
        "region": (
            {
                "level": plan.region.level.value,
                "sido_code": plan.region.sido_code,
                "sigungu_code": plan.region.sigungu_code,
            }
            if plan.region
            else None
        ),
        "period_start": plan.period_start,
        "period_end": plan.period_end,
        "budget": {
            "status": plan.budget.status.value,
            "krw": plan.budget.krw,
            "raw": plan.budget.raw,
        },
        "usage_place": plan.usage_place,
        "usage_industries": list(plan.usage_industries),
        "target_ages": list(plan.target_ages),
        "metrics": [value.value for value in plan.metrics],
        "metric_others": list(plan.metric_others),
        "indicator_use": plan.indicator_use.value if plan.indicator_use else None,
        "data_status": plan.data_status.value if plan.data_status else None,
        "fixed_conditions": plan.fixed_conditions,
        "visitor_goal": plan.visitor_goal,
        "visitor_goal_raw": plan.visitor_goal_raw,
    }


def _plan_from(data: Any) -> PlanInput | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise SessionDataError("기획안 형식이 올바르지 않습니다.")
    region_data = data.get("region")
    if region_data is not None and not isinstance(region_data, dict):
        raise SessionDataError("지역 형식이 올바르지 않습니다.")
    budget_data = data.get("budget") or {}
    if not isinstance(budget_data, dict):
        raise SessionDataError("예산 형식이 올바르지 않습니다.")
    try:
        region = (
            Region(
                level=RegionLevel(region_data["level"]),
                sido_code=str(region_data.get("sido_code", "")),
                sigungu_code=str(region_data.get("sigungu_code", "")),
            )
            if region_data is not None
            else None
        )
        business_type = BusinessType(data["business_type"]) if data.get("business_type") else None
        indicator_use = IndicatorUse(data["indicator_use"]) if data.get("indicator_use") else None
        data_status = DataStatus(data["data_status"]) if data.get("data_status") else None
        visitor_goal = data.get("visitor_goal")
        if visitor_goal is not None and (not isinstance(visitor_goal, int) or isinstance(visitor_goal, bool)):
            raise SessionDataError("방문객 목표 형식이 올바르지 않습니다.")
        budget_krw = budget_data.get("krw")
        if budget_krw is not None and (not isinstance(budget_krw, int) or isinstance(budget_krw, bool)):
            raise SessionDataError("예산 금액 형식이 올바르지 않습니다.")
        metrics = [Metric(value) for value in data.get("metrics", [])]
        metrics = [metric for metric in metrics if metric is not Metric.OTHER]
        raw_metric_others = data.get("metric_others")
        if raw_metric_others is not None and not isinstance(raw_metric_others, list):
            raise SessionDataError("직접 입력 성과지표 형식이 올바르지 않습니다.")
        metric_others = (
            [str(value).strip() for value in raw_metric_others if str(value).strip()]
            if raw_metric_others is not None
            else []
        )
        legacy_metric_other = str(data.get("metric_other", "")).strip()
        if legacy_metric_other and legacy_metric_other not in metric_others:
            metric_others.append(legacy_metric_other)
        metric_others = list(dict.fromkeys(metric_others))
        return PlanInput(
            name=str(data.get("name", "")),
            business_type=business_type,
            goals=[Goal(value) for value in data.get("goals", [])],
            goal_other=str(data.get("goal_other", "")),
            target=str(data.get("target", "")),
            region=region,
            period_start=str(data.get("period_start", "")),
            period_end=str(data.get("period_end", "")),
            budget=Budget(
                status=BudgetStatus(budget_data.get("status", BudgetStatus.UNSET.value)),
                krw=budget_krw,
                raw=str(budget_data.get("raw", "")),
            ),
            usage_place=str(data.get("usage_place", "")),
            usage_industries=[str(value) for value in data.get("usage_industries", [])],
            target_ages=[str(value) for value in data.get("target_ages", [])],
            metrics=metrics,
            metric_others=metric_others,
            indicator_use=indicator_use,
            data_status=data_status,
            fixed_conditions=str(data.get("fixed_conditions", "")),
            visitor_goal=visitor_goal,
            visitor_goal_raw=str(data.get("visitor_goal_raw", "")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, SessionDataError):
            raise
        raise SessionDataError("기획안 값을 읽을 수 없습니다.") from exc


def _choice_data(choice: Choice) -> dict[str, Any]:
    return {
        "question_key": choice.question_key,
        "rule_id": choice.rule_id,
        "decision": choice.decision.value,
        "merge_group": choice.merge_group,
        "option_id": choice.option_id,
        "modified_text": choice.modified_text,
        "reason": choice.reason,
        "evidence_ids": list(choice.evidence_ids),
        "needs_recheck": choice.needs_recheck,
        "related_fields": list(choice.related_fields),
        "evidence_dataset_version": choice.evidence_dataset_version,
        "evidence_thresholds_version": choice.evidence_thresholds_version,
    }


def _choice_from(data: Any) -> Choice:
    if not isinstance(data, dict):
        raise SessionDataError("보완 선택 형식이 올바르지 않습니다.")
    try:
        return Choice(
            question_key=str(data["question_key"]),
            rule_id=str(data["rule_id"]),
            decision=Decision(data["decision"]),
            merge_group=data.get("merge_group"),
            option_id=data.get("option_id"),
            modified_text=data.get("modified_text"),
            reason=str(data.get("reason", "")),
            evidence_ids=tuple(str(value) for value in data.get("evidence_ids", [])),
            needs_recheck=bool(data.get("needs_recheck", False)),
            related_fields=tuple(str(value) for value in data.get("related_fields", [])),
            evidence_dataset_version=data.get("evidence_dataset_version"),
            evidence_thresholds_version=data.get("evidence_thresholds_version"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SessionDataError("보완 선택 값을 읽을 수 없습니다.") from exc


def _execution_data(execution: ExecutionInput) -> dict[str, Any]:
    return {
        "collect_items": list(execution.collect_items),
        "availability": execution.availability.value if execution.availability else None,
        "owner": execution.owner,
        "cycle": execution.cycle,
    }


def _execution_from(data: Any) -> ExecutionInput:
    if not isinstance(data, dict):
        raise SessionDataError("실행 조건 형식이 올바르지 않습니다.")
    try:
        availability = Availability(data["availability"]) if data.get("availability") else None
        return ExecutionInput(
            collect_items=tuple(str(value) for value in data.get("collect_items", [])),
            availability=availability,
            owner=str(data.get("owner", "")),
            cycle=str(data.get("cycle", "")),
        )
    except (TypeError, ValueError) as exc:
        raise SessionDataError("실행 조건 값을 읽을 수 없습니다.") from exc


def _choice_set_data(choice_set: ChoiceSet) -> dict[str, Any]:
    return {
        "choices": {key: _choice_data(value) for key, value in choice_set.choices.items()},
        "executions": {key: _execution_data(value) for key, value in choice_set.executions.items()},
        "archived": [
            {"choice": _choice_data(value.choice), "reason": value.reason}
            for value in choice_set.archived
        ],
        "last_archived": [
            {"choice": _choice_data(value.choice), "reason": value.reason}
            for value in choice_set.last_archived
        ],
    }


def _archived_from(data: Any) -> ArchivedChoice:
    if not isinstance(data, dict):
        raise SessionDataError("보관 선택 형식이 올바르지 않습니다.")
    return ArchivedChoice(
        choice=_choice_from(data.get("choice")),
        reason=str(data.get("reason", "기획 또는 근거 변경으로 더 이상 해당하지 않음")),
    )


def _choice_set_from(data: Any) -> ChoiceSet:
    if not isinstance(data, dict):
        raise SessionDataError("보완 선택 모음 형식이 올바르지 않습니다.")
    choices = data.get("choices", {})
    executions = data.get("executions", {})
    if not isinstance(choices, dict) or not isinstance(executions, dict):
        raise SessionDataError("보완 선택 모음 값을 읽을 수 없습니다.")
    return ChoiceSet(
        choices={str(key): _choice_from(value) for key, value in choices.items()},
        executions={str(key): _execution_from(value) for key, value in executions.items()},
        archived=[_archived_from(value) for value in data.get("archived", [])],
        last_archived=[_archived_from(value) for value in data.get("last_archived", [])],
    )


def _opinion_set_data(value: OpinionSet) -> dict[str, Any]:
    return {
        "opinions": [
            {"text": opinion.text, "cited_rule_ids": list(opinion.cited_rule_ids)}
            for opinion in value.opinions
        ],
        "provider_name": value.provider_name,
        "model": value.model,
        "created_at": value.created_at,
        "dropped_count": value.dropped_count,
    }


def _opinion_set_from(data: Any) -> OpinionSet:
    if not isinstance(data, dict):
        raise SessionDataError("AI 의견 형식이 올바르지 않습니다.")
    rows = data.get("opinions", [])
    if not isinstance(rows, list):
        raise SessionDataError("AI 의견 목록 형식이 올바르지 않습니다.")
    opinions = []
    for row in rows:
        if not isinstance(row, dict):
            raise SessionDataError("AI 의견 값을 읽을 수 없습니다.")
        opinions.append(
            Opinion(
                text=str(row.get("text", "")),
                cited_rule_ids=tuple(str(value) for value in row.get("cited_rule_ids", [])),
            )
        )
    try:
        return OpinionSet(
            opinions=tuple(opinions),
            provider_name=str(data["provider_name"]),
            model=str(data["model"]),
            created_at=str(data["created_at"]),
            dropped_count=int(data.get("dropped_count", 0)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SessionDataError("AI 의견 값을 읽을 수 없습니다.") from exc


def work_state_data(state: Any) -> dict[str, Any]:
    """순환 import를 피하려고 WorkState 타입은 실행 시점에만 다룬다."""
    return {
        "plan": _plan_data(state.plan),
        "original": _plan_data(state.original),
        "changed_fields": sorted(state.changed_fields),
        "choices": _choice_set_data(state.choices),
        "llm_model": state.llm_model,
        "opinions": {key: _opinion_set_data(value) for key, value in state.opinions.items()},
        "opinions_for": _plan_data(state.opinions_for),
        "choices_synced": state.choices_synced,
        "choices_evidence_versions": (
            list(state.choices_evidence_versions) if state.choices_evidence_versions else None
        ),
    }


def encode_session(state: Any, revision: int) -> str:
    return json.dumps(
        {"schema_version": SCHEMA_VERSION, "revision": revision, "state": work_state_data(state)},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def decode_session(raw: str) -> tuple[Any, int]:
    from .session import WorkState

    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
            raise SessionDataError("지원하지 않는 세션 버전입니다.")
        revision = payload["revision"]
        data = payload["state"]
        if not isinstance(revision, int) or revision < 0 or not isinstance(data, dict):
            raise SessionDataError("세션 머리말 형식이 올바르지 않습니다.")
        versions = data.get("choices_evidence_versions")
        if versions is not None and (not isinstance(versions, list) or len(versions) != 2):
            raise SessionDataError("근거 버전 형식이 올바르지 않습니다.")
        opinions = data.get("opinions", {})
        if not isinstance(opinions, dict):
            raise SessionDataError("AI 의견 모음 형식이 올바르지 않습니다.")
        return (
            WorkState(
                plan=_plan_from(data.get("plan")) or PlanInput(),
                original=_plan_from(data.get("original")),
                changed_fields=frozenset(str(value) for value in data.get("changed_fields", [])),
                choices=_choice_set_from(data.get("choices", {})),
                llm_model=data.get("llm_model"),
                opinions={str(key): _opinion_set_from(value) for key, value in opinions.items()},
                opinions_for=_plan_from(data.get("opinions_for")),
                choices_synced=bool(data.get("choices_synced", False)),
                choices_evidence_versions=tuple(versions) if versions is not None else None,
            ),
            revision,
        )
    except SessionDataError:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SessionDataError("저장된 세션 JSON을 읽을 수 없습니다.") from exc
