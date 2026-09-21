# `web/` — 화면 (주소별 처리·화면 틀·모양)

> 최신화: 2026-09-21

## 이 폴더는 무엇인가

담당자가 브라우저로 보는 **1~5단계 화면**을 만드는 곳입니다. 주소(`/step/1` 같은)로 요청이 오면 아래 폴더의 계산 코드를 불러 결과를 받고, 화면 틀에 채워 돌려줍니다.
사용자마다 작업 중인 기획안과 선택을 **서버 메모리에 잠시 보관**하고, 입력 폼 값을 읽고, 숫자를 보기 좋게 표시하는 일도 여기서 합니다.
**계산이나 규칙 판단은 여기서 하지 않습니다.** 서버를 다시 켜면 보관하던 작업 상태는 사라집니다.

## 파일 목록

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `__init__.py` | 이 폴더를 파이썬 묶음으로 인식시키는 빈 파일 | 고칠 일 없음 |
| `session.py` | **사용자별 작업 상태 보관함.** 입력한 원안, 바뀐 칸, 고른 보완 방법, 고른 AI 모델, 모델별 AI 의견을 브라우저 쿠키 하나로 찾아 보관 | 단계 사이에 기억해야 할 정보가 늘어날 때 |
| `profile_view.py` | 2단계 **지역 소비 프로필 카드**에 넘길 데이터 조립과, 1단계에서 고를 수 있는 **업종·연령 목록**(`option_catalog`). **고른 지역 자료만 쓰고 범위를 넓히지 않음**, 준비됐다고 적히지 않은 묶음은 이유만 표시 | 프로필 카드에 담을 내용을 바꿀 때 |
| `forms.py` | 화면에서 보낸 **입력 폼 값을 읽어** 기획안·선택 데이터로 바꿈. 목록에 없는 값은 버림 | 입력 칸을 추가했을 때 |
| `templating.py` | **모든 화면을 그리는 공통 함수**와 숫자 표시 규칙 등록, 쿠키·페이지 이동 도우미 | 모든 화면에 공통으로 넘길 정보가 늘어날 때 |
| `dependencies.py` | 각 주소 처리 코드가 공통으로 받는 것(작업 상태, 근거 파일 상태)을 꺼내 주는 **연결 파일** | 공통으로 받을 것이 늘어날 때 |
| `evidence_state.py` | 서버가 처음 필요할 때 **근거 파일을 한 번 읽어 보관**. 화면 위쪽 "시연용 합성 수치 · demo-001" 표시와, 막아야 할 설정 조합 확인 | 근거 파일 오류 안내나 상단 표시를 바꿀 때 |
| `evidence_view.py` | 2단계 **근거 확인 화면에 필요한 데이터**를 준비 (월별 표, 이웃 달 비교, 요약 문장, 차트, 자료 부족 사례, 해석 한계 두 묶음) | 2단계 화면 내용을 바꿀 때 |
| `ai_models.py` | 3단계 **AI 모델 선택 칸에 필요한 데이터**: 지금 쓰는 모델, 고를 수 있는 모델, 컴퓨터에 받아 둔 모델인지 | 모델 선택 칸을 바꿀 때 |
| `routes/` | **주소마다 무엇을 할지** 정한 파일들 (단계별 1개씩) | [README](routes/README.md) |
| `templates/` | 화면의 **HTML 틀** | [README](templates/README.md) |
| `static/` | 화면 **모양(CSS)과 즉시 반응(JS)** | [README](static/README.md) |

---

## 자세한 설명 (개발자용)

### 역할 요약

HTTP 요청을 받아 하위 로직(`plan/`·`evidence/`·`review/`·`choices/`·`document/`·`llm/`)을 호출하고 HTML(또는 AI 의견 JSON)을 돌려준다. 작업 상태 보관, 폼 해석, 표시 형식 등록을 담당한다.

### 기준 문서

- 최종기획서 3장 사용자 흐름, 6장 제공할 화면
- checks.md: 시안 5단계, 시안 디자인, 서버 메모리 세션, [결과 저장] 저장 위치 선택
- 참고 시안: `../../../../프론트_예시/정책맵 워크스페이스.dc.html`

### 파일별 상세

옮긴 파일: `labels.py`, `formatters.py` → 패키지 루트 `labels.py`, `formatting.py` (보완 기획안 문서도 쓰도록 웹 의존 없는 위치로)

#### `session.py`

- `WorkState`: `plan`, `original`, `changed_fields`(`plan/changes.py` 결과), `choices`(`ChoiceSet`), `choices_evidence_versions`(마지막 선택 정리 때의 자료·운영 기준 버전), `llm_model`, 모델별 AI 의견 상태
- `start_review()`: 원안 보관, 바뀐 항목 계산, AI 의견 캐시 비움, 선택 정리 표시(`choices_synced`) 초기화
- `sync_choices(result, evidence)`: 원안 제출 때 또는 자료·운영 기준 버전이 달라졌을 때 재확인 표시·사라진 질문 보관(`choices/recheck.sync_after_review`). 원안 변경 필드는 제출 직후 한 번만 적용하고, 자료 버전만 달라진 호출에는 예전 원안 변경을 다시 적용하지 않는다
- `cached_opinions(model)`·`remember_opinions(model, opinions, plan)`: 원안이 같을 때만 그 모델의 캐시 사용, 원안이 바뀌면 모든 모델 캐시를 비움. `plan`(요청을 시작한 원안)이 지금 원안과 다르면 보관하지 않음(6-5c). 모델 선택은 원안이 바뀌어도 유지
- 쿠키 `psm_session` (httponly, samesite=lax). 여러 프로세스로 띄우면 세션이 공유되지 않는다
- 검토 결과는 저장하지 않고 요청마다 다시 계산한다 (같은 입력이면 같은 결과)
- `SessionStore`: 메모리 dict + 락. 서버 재시작 시 초기화
- 공개 배포 호스팅 결정(checks.md 미정)에 따라 이 파일만 교체할 수 있게 `get_or_create`·`reset` 인터페이스를 유지한다
- 오래된 세션 정리: **아직 구현하지 않았다.** 공개 배포를 하게 되면 필요하다 (`작업진행.md` 7-2)

#### `forms.py`

- `parse_plan_form(single, multi) -> PlanInput`
- `parse_choice_form(form) -> (단일 값 dict, 수집 자료 목록)` — 수집 자료는 줄바꿈·쉼표로 나눈다. 검증은 `choices/selection.py`
- 원칙: 목록에 없는 값은 버리고, 숫자로 읽지 못한 값은 원문을 남겨 오류로 보여준다

#### 라벨 (`../labels.py`)

입력 선택지 문구·단계 이름·문서용 결정 표기. 규칙 질문·대안 문구는 여기 두지 않는다 (`resources/rules/`).

#### 표시 형식 필터 (`../formatting.py`)

`templating.py`가 `formatting.FILTERS`를 Jinja2 필터로 등록한다. 규칙은 워크플로우 8-3장, 상세는 [2근거확인화면계획.md 5-1](../../../2근거확인화면계획.md#5-1-policy_signal_mapformattingpy-b-3).

| 필터 | 출력 예 |
|---|---|
| `amount(value, unit)` | `1,234.56억원`, `800원`, `0.01억원 미만`, None → `자료 없음` |
| `pct` | `12.34%`, `0.01% 미만`, None → `계산 불가` |
| `growth` | `+1.23%`, `0.01% 미만 (증가)`, None → `계산 불가` |
| `pp_change` | `+0.12%p`, `0.01%p 미만 (증가)`, `0.00%p` |
| `direction`, `comparison`, `calc_status` | `증가`, `방향 다름`, `분모 0 · 계산 불가` |
| `month_label`, `pair_label`, `period_label` | `4월`, `1→2월`, `2026년 1~6월` |

- 반올림은 Fraction → Decimal 사사오입. None은 절대 0으로 표시하지 않는다
- 방향 차이에 빨간색·경고 아이콘 클래스를 붙이지 않는다

#### `evidence_state.py`

- `load_evidence_state(environ)`: 설정 → 근거 파일 로드 → 실제 자료 판단 → 클라우드 조합 차단. 예외를 던지지 않고 `EvidenceState(errors, blocked, …)`로 담는다
- `get_evidence_state()`: 프로세스에서 한 번만 읽는다. 근거 파일을 바꾸면 서버 재시작
- 화면용 오류 문구에는 서버 전체 경로 대신 파일 이름만 넣고, 원래 문구는 서버 로그에 남긴다
- `badge`: `시연용 합성 수치 · demo-001` / `실제 분석 자료 · {버전} · 내부 검증용` / `근거 파일 오류`

#### `templating.render()`

모든 화면은 `render(request, template, context, step=, session_id=, state=, evidence=)`로 그린다. `base.html`이 쓰는 `step`·`state`·`evidence`를 빠뜨리면 페이지 전체가 템플릿 오류(500)가 나기 때문이다.

#### `ai_models.py`

- `current_model(settings, state)`: 담당자가 고른 모델(`state.llm_model`)이 목록에 있으면 그것, 아니면 기본 모델
- `installed_models(settings)`: local일 때 `llm/local.list_models()`로 받아 둔 모델 이름. 확인 실패면 None("모름")
- `model_options(settings, installed) -> list[ModelOption(id, label, description, installed)]`: `PSM_LLM_MODELS` 순서대로 이름표·설명(`llm/catalog`)과 설치 여부
- 모델 선택 칸은 모델이 2개 이상일 때만 보이고, 그때만 Ollama에 받아 둔 모델을 묻는다. 받아 두지 않은 것이 확실한 모델은 "(받아 두지 않음)"으로 비활성 표시하고 저장 요청도 422. 확인하지 못했으면(None) 고를 수 있게 둔다
- 설정이 바뀌어 고른 모델이 목록에서 빠지면 기본 모델로 돌아간다

#### `evidence_view.py`

- `build_evidence_view(plan, result) -> EvidenceView`: 레코드 선택(`review/context.select_main`이 지역·전국을 정함), 금액 단위, 적용 상태별 표시 여부(`show_numbers`·`show_summary`), 요약 문장, 차트 데이터(JSON 형식만), 보류 사례(합성 파일만), 표본 부족·기간 안 겹침 안내
- 해석 한계는 `data_limitations`(근거 파일, 분석 담당 작성)와 `service_notes`(서비스 고정 원칙)로 나눠 전달 → 2단계 화면에서 두 묶음으로 표시

#### `dependencies.py`

- `session_dep` : 쿠키 → `(session_id, WorkState)`
- `evidence_state_dep` : `get_evidence_state()`. 테스트는 `app.dependency_overrides`로 교체 (`tests/conftest.py`)
- 단계 잠금은 각 라우트에서 명시적으로 확인한다
  - 2~5단계: `original` 있음 (없으면 `/step/1`), 근거 파일 정상 (아니면 `error.html` 503)
  - 5단계: 고르지 않은 질문·재확인 필요가 없음 → 아니면 `/step/4`로 (이유는 4단계 화면에 표시)

### 의존 관계

- 가져다 쓰는 곳: 모든 로직 폴더, `llm/` (`routes/opinions.py`, `routes/questions.py`, `ai_models.py`, `session.py`)
- 이 폴더를 쓰는 곳: `app.py`만
- 원칙: 템플릿에 넘기기 전 계산은 로직 폴더 함수로 끝내고, 템플릿은 표시만 한다

### 테스트

- 화면: `test_routes.py`(1단계), `test_evidence_routes.py`, `test_question_routes.py`, `test_opinion_routes.py`, `test_choice_routes.py`, `test_draft_routes.py`
- 표시·상태: `test_formatters.py`(0.01 미만, None 표시, 억원 변환), `test_evidence_view.py`, `test_evidence_state.py`, `test_top_badge.py`
