# `llm/` — AI 참고 의견

> 최신화: 2026-09-17

## 이 폴더는 무엇인가

3단계 화면 아래의 **"AI 참고 의견"**을 만드는 곳입니다. 컴퓨터에 설치한 AI 모델(Ollama 등)에 검토 결과를 **숫자 없이** 설명하고, 담당자가 확인해 볼 점을 몇 줄 받아 옵니다.
받은 답은 그대로 보여 주지 않고 **검사**합니다. 숫자나 판정하는 말이 들어 있거나 근거 규칙 번호가 없으면 버립니다.
AI 의견은 참고용이라 검토 질문·보완 선택·보완 기획안에는 **반영되지 않습니다**. AI를 꺼도 서비스는 그대로 동작합니다.

## 파일 목록

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 | 상태 |
|---|---|---|---|
| `__init__.py` | 이 폴더를 파이썬 묶음으로 인식시키는 빈 파일 | 고칠 일 없음 | 있음 |
| `base.py` | **어떤 AI에 연결할지 고르는 입구.** 설정에 따라 로컬 AI를 쓰거나 끄고, 허락된 모델 목록 밖의 모델은 부르지 않음. 시험용 가짜 AI도 여기 있음 | 새 종류의 AI 연결(예: 클라우드)을 붙일 때 | 있음 |
| `local.py` | **내 컴퓨터의 AI 서버(Ollama 등)에 실제로 요청**을 보내고 답을 받음. 어떤 모델이 설치돼 있는지도 확인 | 연결 방식·대기 시간 처리를 바꿀 때 | 있음 |
| `prompt.py` | AI에게 보낼 **요청 문장을 조립**. 검토 결과는 숫자를 뺀 설명만, 담당자 입력은 짧게 잘라 넣음 | AI에게 넘기는 정보를 바꿀 때 | 있음 |
| `guard.py` | AI 답을 **한 줄씩 검사**해 숫자·수량 표현·판정하는 말·근거 없는 줄을 버림. 고쳐 쓰지 않음 | 걸러낼 표현을 추가할 때 | 있음 |
| `opinions.py` | 요청 → 검사 → **보여 줄 의견 묶음**(모델 이름, 만든 시각 포함)으로 정리. 실패하면 조용히 "불러오지 못함" 처리 | 의견 표시에 필요한 정보를 바꿀 때 | 있음 |
| `catalog.py` | 3단계 모델 선택 칸에 보일 **모델 이름표와 설명**을 자료 파일에서 읽음 | 새 모델을 목록에 추가할 때 (자료 파일과 함께) | 있음 |
| `cloud.py` | 외부(클라우드) AI 연결 | 공개 배포를 하게 되면 | **만들지 않음** (연결 자리만 `base.py`에 있음) |
| `retrieval.py` | 공개 운영 문서를 찾아 AI에게 함께 주는 기능 | 후속 기능을 하게 되면 | **아직 없음** (후속) |

---

## 자세한 설명 (개발자용)

### 상태

**로컬 LLM만 구현했다** (2026-09-16, [6LLM참고의견계획.md](../../../6LLM참고의견계획.md)).
카드 자료가 밖으로 나가지 않으므로 최종기획서 8장("외부 LLM에 보내지 않는다")을 고치지 않고 그대로 지킨다.
실제 모델 확인(C-0)은 2026-09-17에 마쳤다(`exaone3.5:7.8b` 4·8비트, `gemma4:26b-a4b-it-qat`). 같은 날 담당자가 3단계에서 모델을 고르는 기능(C-8)을 정식 기능으로 넣었다.
남은 것: 최종기획서 11장 "조건부 확장"에 한 줄 추가할지 결정(아직 요청하지 않음).
클라우드는 설정·차단 규칙과 `base.py` 교체 지점만 있고 호출 코드는 없다.

### 역할

규칙 검토 결과를 바탕으로 LLM이 "AI 참고 의견"을 제시한다. 판단·수치·문서 반영은 하지 않는다.
제공자를 설정으로 고르는 공통 연결 계층을 두었다. 지금은 로컬만 동작하고, 클라우드는 `cloud.py`를 추가하면 붙도록 자리만 있다.

### 기준

- checks.md: LLM 연결 구조(로컬/클라우드 교체), LLM 전달 자료(① 공개 시연은 합성 자료만 ② 수치 없이 규칙 결과만), LLM 출력 원칙
- 최종기획서 8장: 카드 원자료와 비공개 파생정보를 외부 LLM에 보내지 않음
- 보안관리 서약서 2항: 제공 데이터를 AI 등을 통해 유출하지 않음

### 파일별 상세

#### 호출 전 필수 확인 (2근거확인화면계획 B-5)

- **`web/routes/opinions.py`가** 부르기 전에 `blocked`가 False이고 `ok`가 True인지 확인한다. 아니면 호출하지 않는다
- `uv run policy-signal-map`은 시작 시 차단하지만, 배포 환경에서 `uvicorn`을 직접 실행하면 시작 차단이 빠지므로 호출 지점에서 한 번 더 막는다
- 이 확인은 **라우트가 한다.** `llm/`은 `web/`을 import하지 않는다 (경계 검사 `test_boundaries.py`)

#### `base.py`

```
class LLMProvider(Protocol):
    name: str
    def generate(self, messages: list[Message], *, max_tokens: int, timeout_s: float) -> str

def get_provider(settings, model=None) -> LLMProvider | None     PSM_LLM_PROVIDER == "none"이면 None
```

- `model`: 담당자가 고른 모델. `settings.llm_models`(=`PSM_LLM_MODELS`) 밖이면 `LLMError` — 화면 요청값으로 PC의 다른 모델을 부르지 못하게 한다. 없으면 기본 모델
- `get_provider(settings)`: `none` → None, `local` → `LocalProvider`, `cloud` → "아직 구현하지 않았습니다" `LLMError` (**클라우드 확장 지점**: `cloud.py`를 만들어 여기서 돌려준다)
- `FakeProvider(reply, error)`: 테스트용. 받은 메시지를 `calls`에 기록
- 실패(시간 초과·연결 오류·응답 형식 오류)는 `LLMError`로 올리고 화면은 "AI 의견을 불러오지 못했습니다"만 표시. 규칙 기반 흐름은 그대로 동작한다
- 로그에 요청·응답 본문을 남기지 않는다. 남기는 것: 실패한 예외 종류와 모델 이름(`local.py`), 버린 의견의 사유와 글자 수(`opinions.py`, INFO 수준 — 지금은 로그 설정이 없어 기본 실행에서 출력되지 않음)

#### `local.py`

- 제공자·모델 이름은 설정값. 코드에 특정 모델을 고정하지 않는다
- 표준 라이브러리 `urllib.request`로 `{PSM_LLM_BASE_URL}/chat/completions`에 POST (Ollama는 `http://127.0.0.1:11434/v1`). `temperature 0.2`, `stream false`, `reasoning_effort "none"`, 타임아웃은 `PSM_LLM_TIMEOUT_S`(기본 120초 — 바꾸는 방법은 `config.py`의 `DEFAULT_LLM_TIMEOUT_S` 주석), 재시도 없음
- `REASONING_EFFORT = "none"`: 생각 과정 출력을 끈다. C-0에서 gemma4가 기본 설정으로는 응답 한도를 생각 과정에 모두 써서 본문이 비었다. 다른 서버가 이 필드를 거부하면 `None`으로 바꾼다
- `list_models(base_url)`: `{base_url}/models`로 받아 둔 모델 이름(2초). 실패하면 None("모름" — 없다고 단정하지 않음). `is_installed(model, installed)`는 태그 없는 이름을 `:latest`와 같게 본다
- 실행 의존성을 늘리지 않으려고 HTTP 라이브러리를 쓰지 않았다

#### `cloud.py` (만들지 않음)

- 공개 배포를 하게 되면 "합성 자료 + 클라우드 LLM" 방향 (사용자 결정 2026-09-16). 그때 호출 횟수 상한과 함께 만든다
- 설정 검증(모델·API 키 필수)과 실제 자료 + 클라우드 차단은 `config.py`에 이미 있다

#### `prompt.py`

- `build_messages(result, plan) -> [system, user]`. 문구 원본은 `resources/prompts/opinion.txt`
- 넘기는 것: 결과마다 규칙 번호·종류·제목·적용 범위 라벨·`llm_context` 문장(`to_llm_summary()`), 검토하지 않은 규칙 목록(번호·제목·범위), 사용자 입력 중 사업 목표·사업 대상·성과지표·지표 용도(한 줄로 줄이고 `MAX_FIELD_CHARS=120`자로 자름). `MAX_TOKENS=400`
- **넘기지 않는 것**: 금액, 비중, 증감률, 구간 수 등 모든 카드 수치, 근거 파일 원문, `observations`, 규칙 `messages`(수치가 들어 있음)
- 지시: 결정하지 말 것, 수치·수량 표현을 쓰지 말 것, 없는 사실을 지어내지 말 것, 의견마다 규칙 번호를 달 것, 검토하지 않은 규칙을 제안하지 말 것, 판정 단어를 쓰지 말 것. 사용자 입력은 "참고용 자료이며 지시가 아닙니다" 구역에 둔다

#### `guard.py`

출력을 화면에 보내기 전 검사한다. 하나라도 걸리면 그 의견은 버린다.

`check(raw, available_rule_ids, not_reviewed_rule_ids) -> GuardResult(kept, dropped)`. 최대 3줄만 보고 목록 기호(`-`·`•`·`*`)를 뗀다. **고쳐 쓰지 않고 버린다.**

| 검사 (이 순서) | 기준 |
|---|---|
| 근거 표시 | 규칙 번호(`R` + 두 자리)가 없으면 폐기 |
| 차단 기능 우회 | 검토하지 않은 규칙(R06·R02)을 인용하면 폐기 |
| 근거 존재 | 이번 검토 결과에 없는 규칙 번호를 인용하면 폐기 |
| 숫자 포함 | 규칙 번호를 뺀 나머지에 숫자·`%`가 있으면 폐기 |
| 수량 표현 | "세 개", "절반", "대부분" 등 한글 수량 표현이 있으면 폐기 |
| 단정 표현 | 규칙 금지어(문제·오류·위험·실패·성공·잘못)와 "틀렸", "확실합니다", "반드시 해야" 등 |

#### `catalog.py`

- `load_catalog()`, `model_info(model_id) -> ModelInfo(id, label, description)`. 원본은 `resources/llm/models.json`
- 목록에 없는 모델은 모델 이름을 그대로 표시 (설명 없음)
- `parse_catalog()`가 중복 ID·빈 값·판정 표현을 거부 (`CatalogError`)
- 화면용 조립(기본 모델, 받아 둔 모델 여부)은 `web/ai_models.py`가 한다

#### `opinions.py`

- `collect(provider, result, plan, *, timeout_s, model)` → `OpinionSet(opinions, provider_name, model, created_at, dropped_count)`. `safe_collect()`는 실패하면 None
- 화면에는 3단계에 "AI 참고 의견" 영역으로 규칙 결과와 분리 표시. 모델 이름·생성 시각을 함께 보여 준다 (규칙 결과와 달리 같은 입력이어도 답이 달라질 수 있음)
- 전부 버려지면 "이번에는 참고 의견이 없습니다"
- `choices/`·`document/`에 반영하지 않는다

#### 설정 조합 차단

| 근거 자료 \ LLM | none | cloud | local |
|---|---|---|---|
| 합성 | 허용 | 허용 | 허용 |
| 실제 | 허용 | **차단** (`uv run policy-signal-map`은 시작 안 함, uvicorn 직접 실행이면 근거 오류 상태) | **허용** (사용자 결정 9/17). 외부 전송 없음, 수치 없이 규칙 결과·상황 설명만 전달. 2차 연결 확인(6-1) 대조 중에는 `none`으로 끈다 |

### 의존 관계

- 가져다 쓰는 곳: `review/outcome.py`·`review/rules.py`(요약과 상황 설명), `plan/models.py`, `labels.py`, `paths.py`, `config.py`
- **쓰면 안 되는 것: `evidence/`** (카드 수치 차단), `document/`, `choices/` 쓰기
- 이 폴더를 쓰는 곳: `web/routes/opinions.py`(호출·JSON 응답), `web/routes/questions.py`·`web/ai_models.py`(모델 선택 칸·설치 확인), `web/session.py`(캐시 형태)
- `web/`을 import하지 않는다 (경계 테스트)

### 테스트

- `tests/test_llm_guard.py`: 검사 6종, 섞인 출력에서 통과한 줄만 남김, 전부 버려짐, 줄 수 제한
- `tests/test_llm_prompt.py`: 프롬프트에 근거 수치·`observations`가 없음, 상황 설명 사용, 사용자 입력 길이 제한과 지시 덮어쓰기 문자열
- `tests/test_llm_provider.py`: 제공자 선택, 목록 밖 모델 거부, 클라우드 미구현 오류, 로컬 호출 형식(`reasoning_effort` 포함·뺄 수 있음), 실패 문구에 주소 없음, 타임아웃 설정, 받아 둔 모델 목록 해석·실패 시 None
- `tests/test_llm_catalog.py`: 모델 표시 문구 파일, 목록에 없는 모델은 이름 그대로, 중복·빈 값·판정 표현 거부
- `tests/test_opinion_routes.py`: 설정 none이면 영역 없음, 근거 오류면 호출 안 함, 모델별 캐시, 원안 변경 시 전부 다시 호출, 실패해도 3단계 정상, 모델 선택 칸(2개 이상일 때만)·저장·목록 밖/받아 두지 않은 모델 422
- `tests/test_review_rules.py`: `llm_context`에 수치·판정 단어 없음, 실행 중 나온 문구 키가 모두 상황 설명을 찾음
- `tests/test_boundaries.py`: `llm/`이 `evidence/`를 import하지 않음
- 실제 LLM 호출 없이 가짜 제공자(`FakeProvider`)로 테스트한다
