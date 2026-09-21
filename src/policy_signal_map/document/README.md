# `document/` — 보완 기획안 문서 만들기

> 최신화: 2026-09-21

## 이 폴더는 무엇인가

5단계 **보완 기획안**을 만드는 곳입니다. 담당자가 입력한 원안, 3단계 검토 결과, 4단계에서 고른 보완 방법을 합쳐 **1~8장 + 별첨으로 된 문서**를 만들고, 저장용 Markdown 글로 바꿉니다.
AI를 쓰지 않고 정해 둔 양식에 **확인된 값만** 채웁니다. 입력에 없는 값은 지어내지 않고 "추가 확정 필요"로 남깁니다.

## 파일 목록

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `models.py` | **문서의 모양**을 정함: 장 제목 8개, 줄마다 원안·변경·추가 표시, 변경 전후 기록, 근거 설명, 요청서 초안 | 장을 늘리거나 문서에 담을 정보를 바꿀 때 |
| `describe.py` | 입력한 원안을 **사람이 읽는 문장**으로 옮김. 5단계 화면의 원안 요약과 문서가 같은 문장을 씀 | 원안 문장 표현을 바꿀 때 |
| `builder.py` | 원안 문장에 **담당자가 고른 보완 문장을 끼워 넣어** 문서를 조립. 아직 고르지 않았거나 다시 확인할 질문이 있으면 만들지 않음 | 선택이 문서에 반영되는 방식을 바꿀 때 |
| `render.py` | 조립한 문서를 양식에 넣어 **저장용 Markdown 글**로 바꿈. 표가 깨지지 않게 특수문자를 처리 | 문서 겉모양(양식)을 쓰는 방식을 바꿀 때 |
| `filename.py` | 저장 파일 이름 만들기 (`보완기획안_사업명_날짜.md`, 요청서 파일 이름). 파일 이름에 못 쓰는 글자를 뺌 | 파일 이름 규칙을 바꿀 때 |

이 폴더에는 다른 폴더와 달리 `__init__.py`가 없습니다. 없어도 파이썬 3.12에서 그대로 불러올 수 있습니다.

---

## 자세한 설명 (개발자용)

### 기준 문서

- 워크플로우 S04 전체 기획안 생성, S05 수정·출력, 12장 (목표 유지·대안 취소, Markdown 내보내기)
- 최종기획서 4-5 최종 기획안에서 바뀌는 부분, 6장 제공할 화면과 문서, 8장 (문서 생성에 AI 필수 아님)
- `5보완기획안계획.md` 2장 문서 구조
- checks.md: 파일명 `보완기획안_{사업명}_{날짜}.md`, [전체 문서 보기]·[정밀 분석 요청서 초안]

### `models.py`

```
SECTION_TITLES = {1 사업 개요, 2 목적·대상, 3 일정, 4 혜택·사용처, 5 모집·정산, 6 예산 상태, 7 성과 측정계획, 8 추가 확인사항}
PENDING_MARK = "[추가 확정 필요]"      NOT_IN_PLAN = "원안에 기재 없음 [추가 확정 필요]"

PlanDocument (frozen)
  title, created_on, data_notice        data_notice: "시연용 합성 수치" / "실제 분석 자료"
  sections: tuple[Section]
  changes: tuple[Change]                별첨 1 변경 전후
  profile_summary: ProfileSummary       별첨 2 고른 지역 소비 프로필 요약
  evidence_refs: tuple[EvidenceRef]     별첨 2 근거 (변경·결과에 쓴 근거 ID만)
  pending: tuple[str]                   추가 확정 필요
  request_draft: RequestDraft | None    대안 문서 설정의 appendix가 "request"인 선택이 있을 때만 (R07 D)
  unchanged_sections (속성)

Section: number, lines: list[Line], title·changed (속성), find(key)
Line (frozen): text, key, state("original"|"changed"|"added"|"pending"), change_id, evidence_ids
Change (frozen): change_id, section, before, after, rule_id, option_id, decision_label, evidence_ids, modified
EvidenceRef (frozen): evidence_id, data_kind, dataset_version, scope_label, period_label, limitations
ProfileSummary (frozen): region_label, 자료 종류·버전, 사용 가능 여부, 기간·지역 기준, 요약 문장, 한계
RequestDraft (frozen): purpose, targets, period, metrics, to_confirm
DocumentBlocked (frozen): reasons         미선택·재확인 필요 때문에 만들 수 없는 상태
```

### `describe.py`

- `describe_plan(plan) -> list[Section]`: 입력 필드를 1~8장 줄 문장으로. 줄마다 `key`를 붙여 대안의 `replace_key`가 바꿀 줄을 찾게 한다
- `goal_labels`, `metric_labels`, `budget_text`, `period_text`: 대안 문장의 `{…}` 자리에 넣을 값
- 입력에 없는 값은 `NOT_IN_PLAN`. 예산 미정/미입력은 "추가 확정 필요", 금액은 원 단위 그대로

### `builder.py`

- `build_document(plan, result, choice_set, evidence, today) -> PlanDocument | DocumentBlocked`
- 규칙
  - `choices.selection.blocking_reasons()`가 있으면 `DocumentBlocked` (질문 미선택, `needs_recheck`)
  - **선택하지 않은 항목은 원안 문장을 그대로 유지** (S04)
  - 채택·수정한 선택만 대안의 `document`(장·`append`/`replace`·문장)를 적용해 `changed`/`added`로 표시하고 `Change` 기록. 수정이면 담당자 문장으로 대체
  - 취소한 선택은 문서에 흔적을 남기지 않는다 (12장)
  - 원안에 없는 값(예산 금액, 점포 수, 협약 기관)은 채우지 않고 pending으로 (최종기획서 3장)
  - 보류(`held`) 결과는 선택 없이 8장에 기록 (`_auto_records`, 4보완선택계획 결정 ⑤). pending은 원안 검증 + `pending_from_choices`
  - 근거 표시의 범위 라벨은 `review.context.scope_label` (전국이면 "전국 참고")
  - 별첨 2의 지역 소비 프로필은 **고른 지역만** 요약한다. 자료가 없으면 넓히지 않고 미연결 사유를 남긴다. 업종·연령 구성, 월별 지수, 외국인·미상 비중, 순위 분모, 외부 인구의 관측일·출처를 담되 1인당 값은 만들지 않는다
  - 요청서는 **초안**만. "계약·자료 제공이 확정된 것이 아님" 문구는 양식에 고정

### `render.py`

- `render_markdown(doc) -> str`: `resources/documents/plan.md.j2`
- `render_request(doc) -> str`: `resources/documents/request.md.j2`. 요청서 초안이 없으면 `ValueError`. 요청서만 따로 보내는 일이 있어 **별도 파일**로도 저장한다 (본문 별첨 3에도 같은 내용이 들어감)
- Jinja2 `Environment(autoescape=False, undefined=StrictUndefined)`
- `md_escape`: 표 칸과 코드 표기를 깨뜨리는 `|`, 백틱만 이스케이프. 대괄호는 `[추가 확정 필요]` 표기에 쓰므로 그대로 둔다
- `mark_pending`: 문서에서 `[추가 확정 필요]`를 굵게 (화면에는 기호를 넣지 않음)
- 변경 줄 표시: 줄 끝에 `〔변경 · 변경 001〕`, `〔추가 · 변경 001〕`. `change_id`는 문서 안에서 순서대로 붙인 공개 이름표이며 내부 규칙 번호를 포함하지 않는다. 별첨 1의 같은 이름표로 연결한다
- 출력 순서: 머리 줄(생성일·자료 종류·초안 안내) → 요약 → 본문 1~8장 → 별첨 1 변경 전후 → 별첨 2 근거와 해석 한계 → 별첨 3 요청서 초안(있을 때)

### `filename.py`

- `document_filename(plan_name, today) -> "보완기획안_{사업명}_{YYYYMMDD}.md"`, `request_filename(plan_name, today)`
- 파일명에 쓸 수 없는 문자(`\ / : * ? " < > |`, 줄바꿈·탭)와 앞뒤 공백 제거, 공백은 `_`, 최대 60자
- 사업명이 비면 `보완기획안_{YYYYMMDD}.md`

### 의존 관계

- 가져다 쓰는 곳: `plan/`, `review/`, `choices/`, `evidence/loader.LoadResult`(근거 파일 버전·한계 표시), `formatting.py`, `labels.py`, `resources/documents/`, Jinja2 라이브러리
- 이 폴더를 쓰는 곳: `web/routes/draft.py`
- 쓰면 안 되는 것: `web/`, FastAPI, LLM (문서 생성에 AI 사용 안 함)

### 테스트

`tests/test_document_describe.py`, `test_document_builder.py`, `test_document_render.py`, `test_document_filename.py` (공용 준비는 `tests/document_helpers.py`)

| 확인 | 워크플로우 12장 |
|---|---|
| 선택 없음 → 원안과 같은 내용, 변경 0건 | 목표 유지·대안 취소 |
| 옵션 A 채택 → 7장에 수집계획·담당자·주기, 별첨 1에 변경 기록 | — |
| 옵션 A 채택 후 취소 → 변경 흔적 없음 | 목표 유지·대안 취소 |
| 예산 미정 → "추가 확정 필요", 금액 지어내지 않음 | 자료 수집 미정 |
| 담당자 빈 값 → pending | 자료 수집 미정 |
| 전국 근거 → 별첨 2에 전국 참고·한계 | 전국 자료 + 특정 지역 기획 |
| 고른 지역 프로필 → 별첨 2 요약, 미연결이면 다른 지역으로 넓히지 않음 | 지역 프로필 |
| 합성 근거 → 문서에 "시연용 합성 수치" 표시 | 공개 배포 |
| needs_recheck 존재 → 생성 차단 | 목표·지역 변경 |
| 사용자 입력의 `|` 이스케이프, 대괄호 유지 | — |
| 파일명 금지 문자 제거 | Markdown 내보내기 |
