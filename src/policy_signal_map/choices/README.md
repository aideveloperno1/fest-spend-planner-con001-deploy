# `choices/` — 담당자가 고른 보완 방법 보관

> 최신화: 2026-09-21

## 이 폴더는 무엇인가

4단계 **보완 선택** 화면에서 담당자가 질문마다 고른 결정(원안 유지·채택·수정·보류)과 실행 조건(무슨 자료를, 누가, 얼마나 자주 모을지)을 **보관하고 확인**하는 곳입니다.
담당자가 원안을 고쳐 다시 제출하면, 바뀐 칸과 관련된 선택만 "다시 확인 필요"로 돌려놓고 더 이상 해당하지 않는 질문의 선택은 따로 보관합니다.
서비스가 대신 고르지 않습니다.

## 파일 목록

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `__init__.py` | 이 폴더를 파이썬 묶음으로 인식시키는 빈 파일 | 고칠 일 없음 |
| `models.py` | **선택 한 건의 모양**(결정, 고른 대안, 고친 문장, 이유)과 실행 조건, 전체 선택 보관함을 정함 | 선택에 새 정보를 담아야 할 때 |
| `selection.py` | 선택을 **저장·취소하고 올바른지 확인**. 비어 있는 담당자·주기 같은 "추가 확정 필요" 목록과, 5단계로 넘어가지 못하는 이유를 만듦 | 선택 확인 규칙이나 5단계 진입 조건을 바꿀 때 |
| `recheck.py` | 원안이 바뀌었을 때 **관련된 선택만 다시 확인 필요로 표시**하고, 사라진 질문의 선택은 보관함으로 옮김 | 다시 확인 조건을 바꿀 때 |

---

## 자세한 설명 (개발자용)

### 기준 문서

- 워크플로우 S03 보완 선택, S05 수정·출력, 11장 (재확인), 12장 (목표 유지·대안 취소, 목표·지역 변경)
- 최종기획서 3장 3~4단계, 4-4 선택할 보완 방법, 9장 (BC 제휴를 선택하지 않아도 기본 검토 제공)
- checks.md: 시안의 A~D 대안 + 원안 유지·보류 + 수정, "실행 조건"은 보완 선택 화면의 추가 입력 칸

### 파일별 상세

#### `models.py`

```
Decision = "keep_original" | "adopt" | "modify" | "hold"      (화면 라벨: 원안 유지·채택·수정·보류)
Availability = "available" | "negotiating" | "unavailable"   (확보 가능·협의 중·확보 어려움)

Choice (frozen)
  question_key: str                규칙 하나가 질문 하나면 규칙 ID, 둘 이상이면 `규칙ID-이름`
  rule_id: str
  decision: Decision
  merge_group: str | None
  option_id: str | None            adopt/modify일 때. R07은 A~D, R01·R03·R04는 A·B
  modified_text: str | None        modify일 때 담당자가 고친 문장 → 문서에서 대안 문장을 대체
  reason: str                      선택 이유 (선택 입력)
  evidence_ids: tuple[str]         review 결과에서 그대로 복사
  needs_recheck: bool
  related_fields: tuple[str]        질문 단위 원안 재확인 기준
  evidence_dataset_version: str | None
  evidence_thresholds_version: str | None
  changes_document (속성)          adopt·modify일 때 True

ExecutionInput (frozen)            실행 조건이 있는 대안(R07·R03·R04의 A) 기준
  collect_items: tuple[str]        필수 1개 이상
  availability: Availability | None
  owner: str                       빈 값 허용 → 추가 확정 필요
  cycle: str                       빈 값 허용 → 추가 확정 필요
  pending_labels()                 비었거나 확보 가능이 아닌 항목 이름

ChoiceSet
  choices: dict[question_key, Choice]
  executions: dict[merge_group, ExecutionInput]    같은 묶음 질문이 공유. 마지막 저장값으로 덮어씀
  archived: list[ArchivedChoice]                   기획·근거 변경으로 사라진 질문의 선택 (전체 기록)
  last_archived: list[ArchivedChoice]              가장 최근 변경으로 보관한 선택. 4단계 안내는 이것만 보여 줌
  needs_recheck_keys (속성)
```

#### `selection.py`

- `apply_choice(choice_set, outcome, single, collect_items, evidence_dataset_version=, evidence_thresholds_version=) -> ChoiceErrors` : 오류가 없으면(빈 dict) 선택과 선택 당시 자료 문맥을 저장한다
- `cancel_choice(choice_set, question_key)` : 선택 삭제 → 문서에서도 해당 변경이 사라짐 (12장). 같은 묶음에 **실행 조건을 쓰는 대안**을 채택·수정한 선택이 더 없으면 실행 입력도 지움 (`drop_unused_execution`, 6-5b). 실행 조건을 쓰는 대안 = 입력칸이 있는 대안(R07·R03·R04 A) + 문서 문장에서 `{collect_items}{owner}{cycle}{availability}`를 쓰는 대안(R04 B). 저장(원안 유지·보류·다른 대안으로 변경)과 질문 보관에서도 같은 정리를 한다
- `pending_from_choices(choice_set, result) -> list[str]` : 보류한 질문, 실행 입력의 빈 담당자·주기·확보 여부·확보 협의 → 추가 확정 필요. 묶음 이름은 `merge_groups` 한글 이름으로 표시
- `blocking_reasons(result, choice_set) -> list[str]` : 질문(`question`)을 고르지 않았거나 재확인 필요가 남은 경우. 안내(`notice`)는 필수가 아니다
- 검증
  - `option_id`는 해당 규칙 JSON에 정의된 대안만 허용
  - `modify`는 수정 문장 필수
  - 옵션 A 선택 시 `collect_items` 1개 이상 필수, 담당자·주기는 비워도 됨 (비우면 "추가 확정 필요", 시안)
  - 아직 없는 자료는 "계획"으로 남긴다 (S03). 확보된 것처럼 바꾸지 않는다
  - 옵션 D는 "요청서 초안" 상태로만 저장. 계약·제공 확정 필드를 두지 않는다 (S03)
- 선택하지 않은 질문은 `keep_original`로 간주하지 않는다. "미선택"으로 남겨 기획안 생성 전에 확인받는다

#### `recheck.py`

- `mark_recheck(choice_set, changed_fields)`, `mark_evidence_recheck(choice_set, dataset_version, thresholds_version)`, `archive_missing(choice_set, result)`, 이를 묶은 `sync_after_review(...)`. `web/session.py`의 `WorkState.sync_choices()`가 4단계·5단계·내려받기 어디서든 문서를 만들기 전에 부른다
- `plan/changes.py`의 변경 필드와 **그 선택이 기억해 둔 `related_fields`**가 겹치는 선택만 `needs_recheck`. 선택은 저장할 때 질문에서 그 값을 받아 둔다(`Choice.related_fields`). 값이 없으면 규칙 JSON의 `related_fields`를 쓴다 — 한 규칙이 질문을 둘 이상 낼 때 한쪽만 바뀌었는데 양쪽에 재확인이 붙지 않게 하려는 것이다 (7지역확장계획.md 5장)
- 자료 버전 변경은 값 기반 질문(R07·R02·R08·R04 시기·R11·R12), 운영 기준 버전 변경은 기준값을 쓰는 질문(R02·R08·R04 시기·R12)만 다시 확인한다. R04 기간처럼 원안 입력만 보는 질문은 자료 버전으로 표시하지 않는다
- 기획·근거 변경 후 규칙을 다시 실행해 **질문 자체가 사라진 경우**: 선택을 보관함으로 옮기고 화면에 "기획 또는 근거 변경으로 더 이상 해당하지 않음" 표시, 문서에는 반영하지 않음
- `needs_recheck`가 하나라도 있으면 보완 기획안 생성을 막고 확인받는다 (11장: 최종 문서 생성 전에 확인)

### 의존 관계

- 가져다 쓰는 곳: `plan/`, `review/`
- 이 폴더를 쓰는 곳: `document/`, `web/`
- 쓰면 안 되는 것: `web/`, FastAPI, `evidence/` 직접 계산 (근거는 review 결과로만 받음)

### 테스트

`tests/test_choices.py`, `tests/test_choice_routes.py`

| 확인 | 워크플로우 12장 |
|---|---|
| 대안 취소 시 ChoiceSet에서 제거 | 목표 유지·대안 취소 |
| 원안 유지 선택 시 변경 없음 | 목표 유지·대안 취소 |
| 목표 변경 → 관련 선택만 needs_recheck, 사업명 변경은 유지 | 목표·지역 변경 |
| 자료·운영 기준 버전 변경 → 관련 값 기반 선택만 needs_recheck | 근거 갱신 |
| 옵션 A 담당자 빈 값 → pending 항목 | 자료 수집 미정 |
| JSON에 없는 option_id 거부 | — |
| needs_recheck 존재 시 문서 생성 차단 신호 | — |
