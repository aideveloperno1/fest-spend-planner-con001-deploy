# `src/policy_signal_map/` — 서비스 코드 전체

> 최신화: 2026-09-17

## 이 폴더는 무엇인가

서비스의 **모든 코드**가 들어 있는 곳입니다. 기능별로 하위 폴더(기획 입력, 근거 계산, 검토 질문, 보완 선택, 문서 만들기, AI 의견, 화면)가 나뉘어 있고,
이 폴더 바로 아래에는 **여러 기능이 함께 쓰는 파일**(앱 시작, 설정 읽기, 숫자 표시 형식, 한글 이름표, 폴더 위치)만 둡니다.

## 파일 목록

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `__init__.py` | **`uv run policy-signal-map` 명령의 시작점.** 근거 파일에 문제가 없는지 먼저 보고 서버를 켬 | 실행 주소·포트를 바꿀 때 |
| `app.py` | 웹 앱을 만들고 화면 주소들을 등록하는 **조립 파일**. 계산 코드는 두지 않음 | 새 화면 주소 묶음을 추가할 때 |
| `config.py` | **설정 읽기.** 어떤 근거 파일을 쓸지, AI를 켤지, 어떤 모델을 고를 수 있는지, 몇 초 기다릴지. 실제 자료와 외부(클라우드) AI를 함께 켜지 못하게 막음 | 설정 항목을 추가하거나 AI 응답 대기 시간 기본값을 바꿀 때 |
| `formatting.py` | 숫자를 **화면·문서에 보이는 모양**으로 바꿈 (억원, %, %p, 증가·감소, 기간 표기) | 숫자 표시 방식을 바꿀 때 |
| `labels.py` | 선택지의 **한글 이름표** 모음 (사업 목표, 성과지표, 자료 확보 상태, 단계 이름, 담당자 결정). 화면과 문서가 같은 이름을 씀 | 선택지 이름을 바꿀 때 |
| `paths.py` | 자료 폴더·화면 폴더의 **위치**를 한곳에 적어 둔 파일 | 폴더 구조를 바꿀 때 |
| `plan/` | 담당자가 입력하는 **기획안**: 입력 칸, 빠진 칸 확인, 지역 목록, 바뀐 칸 찾기 | [README](plan/README.md) |
| `evidence/` | 데이터 담당이 준 **근거 파일을 읽고 검사**하고, 이웃한 두 달을 비교 계산 | [README](evidence/README.md) |
| `review/` | **검토 규칙을 실행**해 담당자에게 물을 질문과 고를 수 있는 보완 방법을 만듦 | [README](review/README.md) |
| `choices/` | 담당자가 고른 **보완 방법을 저장·취소**하고, 원안이 바뀌면 다시 확인하게 함 | [README](choices/README.md) |
| `document/` | 원안과 선택을 합쳐 **보완 기획안 문서**를 만듦 | [README](document/README.md) |
| `llm/` | **AI 참고 의견**: 컴퓨터에 설치한 AI 모델에 묻고, 답을 검사하고, 모델 이름표를 관리 | [README](llm/README.md) |
| `web/` | **화면**: 주소별 처리, 화면 틀, 모양, 즉시 반응, 사용자별 작업 상태 | [README](web/README.md) |
| `resources/` | 코드가 읽는 **자료 파일**: 규칙 문구, 가짜(합성) 근거, 문서 양식, AI 요청 문장, 모델 이름표, 지역 목록 | [README](resources/README.md) |

---

## 자세한 설명 (개발자용)

### 기획 단계와 폴더

`plan/` S01 · `review/` S02·11장 · `choices/` S03 · `document/` S04·S05 · `evidence/` 워크플로우 8~9장 · `llm/` `6LLM참고의견계획.md` · `web/` 화면 전체

### 의존 방향

```
web → document → choices → review → evidence, plan
llm → review 결과·plan·labels·config만 사용
```

- 화살표 반대 방향 import 금지. 예: `evidence/`가 `web/`이나 `review/`를 import하면 안 된다.
- `plan/`·`evidence/`·`review/`·`choices/`·`document/`는 FastAPI·Jinja2 화면 코드를 import하지 않는다 (단, `document/`는 Markdown 양식 렌더링에 Jinja2 라이브러리 자체는 사용 가능).
- `llm/`은 `evidence/`를 import하지 않는다. 카드 수치가 LLM으로 넘어가지 않게 하는 구조적 장치다.
- `tests/test_boundaries.py`가 검사하는 것은 세 가지다: ① 로직 패키지(`plan·evidence·review·choices·document·llm`)의 `web`·`app`·FastAPI·Starlette import ② `evidence`의 위층 import ③ `llm`의 `evidence` import. 그 밖의 역방향(예: `review` → `choices`)은 검사하지 않으므로 직접 지킨다.

### 루트 파일 상세

| 파일 | 내용 |
|---|---|
| `__init__.py` | `main()`: `web/evidence_state.get_evidence_state()`로 근거 상태를 확인해 blocked면 오류 문구로 종료, 아니면 uvicorn 실행 (127.0.0.1:8000, reload) |
| `app.py` | FastAPI 생성, `/static` 마운트, `web/routes/`의 라우터 등록만 한다 |
| `paths.py` | `PACKAGE_DIR`, `RESOURCES_DIR`, `WEB_DIR` |
| `formatting.py` | 숫자·상태 표시 형식 (억원·%·%p·증감률·방향·상태·기간). 웹 의존 없음. 화면 필터(`FILTERS`)와 문서 생성이 함께 사용 |
| `labels.py` | 목표·지표·지표 용도·자료 상태·단계·결정의 한글 라벨 (`document/`가 `web/`을 부를 수 없어 루트에 둠) |
| `config.py` | `load_settings()`, `check_llm_data_combination()`. 아래 표 참고 |
| `.env.example` (저장소 루트) | `config.py` 항목 예시. 실제 `.env`는 git 제외, `uv run --env-file .env`로 사용 |

### `config.py` 항목

| 환경변수 | 기본값 | 의미 |
|---|---|---|
| `PSM_EVIDENCE_PATH` | `resources/evidence/review_evidence_demo_v1.json` | 읽을 분석 근거 파일. 실제 파일은 `private/`에 두고 이 값으로 지정. 바꾸면 서버 재시작 |
| `PSM_REGION_MAPPING_PATH` | `private/region_mapping.json` | 분석 전달본 지역명과 서비스의 10자리 행정표준코드를 잇는 대응표. 바꾸면 서버 재시작 |
| `PSM_LLM_PROVIDER` | `none` | `none` / `google_ai` |
| `GEMINI_API_KEY` | 없음 | Google AI Studio API 키. 설정 객체의 문자열 표현에서도 제외 |
| `PSM_LLM_MODEL` | Google 목록의 첫 모델 | 기본 모델 이름 |
| `PSM_LLM_MODELS` | Google AI 모델 4개 | 3단계 선택 목록. 쉼표 순서를 화면에서 유지 |
| `PSM_LLM_TIMEOUT_S` | `45` (`DEFAULT_LLM_TIMEOUT_S`) | Google AI 응답을 기다릴 초. 0보다 커야 함 |

- 설정은 앱 시작 시 한 번 읽어 불변 객체(dataclass frozen)로 둔다. 빈 문자열은 설정하지 않은 것으로 본다.
- `google_ai`는 API 키가 없으면 `SettingsError`다. API 키는 URL이나 브라우저 응답에 넣지 않는다.
- 배포 프로젝트에는 공개 합성 근거만 두며 `scripts/check_public_bundle.py`가 이를 검사한다.
- 실제 자료 여부는 `evidence/loader.py`의 `is_real_evidence`로 판단한다 (`private/` 경로, `_real_` 이름, `synthetic`이 아닌 `data_kind`). `uv run policy-signal-map`은 막힌 조합이면 서버를 켜지 않고, `uvicorn`을 직접 실행하면 `web/evidence_state.py`가 blocked 상태로 두어 2~5단계가 오류 화면이 된다.

### 지켜야 할 원칙

- 새 파일을 만들면 해당 폴더 README의 "파일 목록"에 쉬운 말로 추가한다.
- 선택지 라벨은 루트 `labels.py`, 규칙 문구·대안·문서 문장은 `resources/rules/`, 보완 기획안 양식은 `resources/documents/`, AI 요청 문장은 `resources/prompts/`, 모델 표시 이름은 `resources/llm/`에 둔다. 코드 여러 곳에 같은 문구를 적지 않는다.
