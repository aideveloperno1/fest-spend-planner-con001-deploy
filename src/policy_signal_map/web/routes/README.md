# `web/routes/` — 주소마다 무엇을 할지

> 최신화: 2026-09-21

## 이 폴더는 무엇인가

브라우저가 `/step/1`, `/step/2` 같은 **주소로 요청을 보낼 때 무엇을 할지** 정한 파일들입니다. 화면 단계마다 파일이 하나씩 있습니다.
각 파일은 요청을 읽고 → 계산 코드를 부르고 → 작업 상태를 갱신하고 → 화면 틀에 채워 돌려주는 일만 합니다.
아직 들어갈 수 없는 단계(예: 기획안을 입력하지 않고 2단계)로 가면 알맞은 단계로 돌려보냅니다.

## 파일 목록

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `__init__.py` | 이 폴더를 파이썬 묶음으로 인식시키는 빈 파일 | 고칠 일 없음 |
| `input.py` | **1단계 기획 입력**: 처음 화면, 예시 채우기·모두 지우기·검토 시작, 처음부터 다시 | 1단계 버튼 동작을 바꿀 때 |
| `evidence.py` | **2단계 근거 확인** 화면 | 2단계로 넘기는 데이터를 바꿀 때 |
| `questions.py` | **3단계 검토 질문** 화면과 **AI 모델 고르기** 저장 | 3단계 화면이나 모델 선택 규칙을 바꿀 때 |
| `opinions.py` | 3단계 화면이 뜬 뒤 따로 부르는 **AI 참고 의견 받기** (화면이 AI를 기다리지 않게 분리) | AI 의견 응답 내용을 바꿀 때 |
| `choices.py` | **4단계 보완 선택**: 선택 저장·취소, 입력 오류 표시 | 4단계 저장 흐름을 바꿀 때 |
| `draft.py` | **5단계 보완 기획안**: 화면, 전체 문서 보기, 요청서 초안 보기, 파일 내려받기 | 5단계 화면이나 저장 파일을 바꿀 때 |

---

## 자세한 설명 (개발자용)

### 주소 한눈에 보기

| 파일 | 주소 | 화면 틀 |
|---|---|---|
| `__init__.py` | — | — |
| `landing.py` | `GET /` (랜딩. **세션을 만들지 않는다**) | `landing.html` |
| `input.py` | `GET·POST /step/1`, `POST /reset` | `steps/input.html` |
| `evidence.py` | `GET /step/2` (원안 없으면 `/step/1`, 근거 오류면 `error.html` 503) | `steps/evidence.html` |
| `questions.py` | `GET /step/3` (원안 없으면 `/step/1`, 근거 오류면 503), `POST /step/3/ai-model` (AI 모델 선택: 목록 밖·받아 두지 않은 모델 422, 저장 후 303) | `steps/questions.html` |
| `opinions.py` | `GET /step/3/opinions` (JSON, AI 참고 의견. 고른 모델로 호출, `model_label` 포함) | — (`static/js/opinions.js`가 채움) |
| `choices.py` | `GET·POST /step/4`, `POST /step/4/cancel` (저장 후 303, 검증 실패는 422) | `steps/choices.html` |
| `draft.py` | `GET /step/5`, `GET /step/5/document`, `GET /step/5/download`, `GET /step/5/request` | `steps/draft.html`, `steps/document.html`, `steps/request.html` |

임시 화면(`steps.py`·`placeholder.html`)은 5단계 구현과 함께 삭제했다. 단계 주소는 모두 전용 라우터가 받으므로 `/step/{step}` 같은 포괄 규칙을 다시 만들지 않는다 (만들면 `/step/2` 등 전용 주소를 가로챈다).

모든 화면은 `templating.render()`로 그린다 (문맥에 `evidence`가 빠지면 템플릿 오류).

### 파일별 상세

#### `input.py` — 1단계 기획 입력

- `POST /step/1`의 `action`: `sample`(예시 채우기) / `clear`(모두 지우기) / `submit`(검토 시작)
- 검증 실패: 422와 오류 표시. 성공: 원안 보관 → `/step/2`
- 원안 보관(`state.start_review()`) 시 `plan/changes.py`로 바뀐 항목을 계산한다. 재확인 표시·사라진 질문 보관은 `state.sync_choices(result)`가 원안 제출마다 **한 번만** 한다 (4단계 화면·저장·취소, 5단계 화면·전체 문서·요청서·내려받기 중 먼저 열린 곳에서, 6-5a). 검토 결과는 세션에 저장하지 않고 요청마다 다시 계산한다

#### `evidence.py` — 2단계 근거 확인

- 근거 레코드는 `review/context.select_main(file, plan)`이 **시군구 → 시도 → 전국** 사다리로 고른다. 어느 범위를 쓰든 **"선택 지역의 진단이 아님"** 안내를 붙이고, 넓혔으면 그 이유(없음·사용 불가·표본 부족)도 함께 적는다
- 템플릿에 넘길 것
  - 상단 표시: 전국 참고/시도 범위, 기간, `dataset_version`, 합성/실제
  - 월별 표 6행: 금액, 전체 분모 비중, 미상 비중, 미상 제외 비중, 상태
  - 인접 구간 5개: 비교 A 결과, 비교 B 결과(보조), 보류 사유
  - 요약 문장용 숫자: `evidence/summary.py`의 구간 수
  - 차트 데이터 JSON (금액 막대, 비중 선 — 전체/미상 제외 전환)
  - 계산 방법·해석 한계 (`limitations`)
  - 보류 사례 보기: `no_data`·`invalid_denominator`가 있는 레코드
- 근거 파일 로드 오류면 오류 내용과 "데이터 담당에게 확인" 안내

#### `questions.py` — 3단계 검토 질문

- `review_result.outcomes`를 kind별로 표시: 질문 / 안내 / 추가 확정 필요 / 보류
- 오른쪽 패널: 검토하지 않은 항목 (R06 분석 예시, R02 향후 기능)
- 각 질문의 근거 ID 칩 → 5단계 근거 추적 또는 2단계로 이동
- `PSM_LLM_PROVIDER`가 `none`이 아니면 "AI 참고 의견" 영역(모델이 2개 이상이면 모델 선택 칸 포함)을 두고, 화면이 뜬 뒤 `static/js/opinions.js`가 `/step/3/opinions`에서 받아 채운다 (아래 `opinions.py`)

#### `opinions.py` — 3단계 AI 참고 의견 (JSON)

- `GET /step/3/opinions` → `{"state": "off", "opinions": []}`(원안 없음·근거 오류·blocked·설정 none) / `{"state": "ok", "opinions": [{text, rule_ids}], "model", "model_label", "created_at", "dropped_count"}` / `{"state": "failed", "message": "AI 의견을 불러오지 못했습니다"}`
- 호출 전 `blocked`·`ok`를 여기서 확인한다 (`llm/`은 `web/`을 부르지 않음)
- 고른 모델은 `web/ai_models.current_model()`. **모델별로** 세션 캐시를 두어 같은 원안·같은 모델이면 다시 부르지 않는다. 응답을 기다리는 동안 원안이 다시 제출되면(요청 시작 원안 `asked_for`와 다르면) 결과를 보관하지 않는다 (6-5c)
- 응답 `ok`에는 `model_label`(모델 이름표)도 담는다
- 실패 문구에 서버 주소·예외 내용을 넣지 않는다

#### `choices.py` — 4단계 보완 선택

- 질문마다 원안 유지 / 채택 / 수정 / 보류 + 대안(규칙 JSON 정의. R07은 A~D, R01·R03·R04는 A·B). 안내(notice)는 고를 수 있지만 필수가 아니다
- 대안 카드: 바뀌는 곳, 필요 자료, 운영 부담
- R07·R03·R04의 대안 A 선택 시 실행 조건 입력칸: 수집자료(필수), 확보 여부, 담당자, 주기 (빈 값 → "추가 확정 필요"). 같은 묶음 질문끼리 입력을 공유하며 화면이 기존 값을 채워 보낸다
- `POST /step/4`: `web/forms.py` → `choices/selection.py` 검증 → 세션 저장
- `POST /step/4/cancel`: 해당 질문 선택 취소
- `needs_recheck` 선택은 상단에 모아 "기획 또는 근거 자료 변경으로 재확인 필요" 표시. 가장 최근 변경으로 더 이상 해당하지 않게 된 질문의 선택(`choice_set.last_archived`)만 안내한다
- 실행 조건 입력칸의 "같은 자료를 묻는 질문(…)과 함께 쓰는 입력입니다" 안내는 같은 묶음의 다른 질문이 있을 때만(`related_rule_ids`) 붙인다
- [보완 기획안 만들기]: 미선택·재확인 필요가 남아 있으면 막고 목록 표시

#### `draft.py` — 5단계 보완 기획안

- `GET /step/5`: 보완 기획안 화면 (문서 순번 `변경 001`로 본문과 변경표 연결, 별첨 2 고른 지역 프로필 요약, 근거 추적 패널 포함)
- `GET /step/5/document`: 전체 문서 보기 (저장될 Markdown 원문을 `<pre>`로)
- `GET /step/5/download`: `document/render.py` 결과를 `text/markdown; charset=utf-8`로 응답, `Content-Disposition`에 `document/filename.py` 파일명 (RFC 5987 `filename*=UTF-8''` 인코딩으로 한글 파일명)
  - 화면의 [결과 저장]은 `static/js/save.js`가 이 주소를 받아 저장 위치 선택 창을 연다
- `GET /step/5/request`: 옵션 D 선택 시 정밀 분석 요청서 초안. 선택하지 않았으면 `/step/5`로 되돌린다
- `GET /step/5/download?kind=request`: 요청서 초안 파일 (`정밀분석요청서_...md`)
- 문서 생성 차단 상태면 4단계로 리다이렉트 (다운로드는 409와 사유 목록)

### 공통 원칙

- 세션·근거 파일은 `web/dependencies.py`로 받는다
- 쿠키: `httponly`, `samesite=lax` (배포 시 `secure` 추가)
- 상태를 바꾸는 요청은 POST만 사용하고 처리 후 303 리다이렉트 (새로고침 시 재제출 방지)

### 테스트

단계별 파일로 나눴다: `test_routes.py`(1단계·잠금), `test_evidence_routes.py`, `test_question_routes.py`, `test_opinion_routes.py`, `test_choice_routes.py`, `test_draft_routes.py`
- 단계 잠금 (원안 없이 2~5단계 → 1단계로)
- 2단계에 "전국 참고"와 "시연용 합성" 표시
- 4단계 미선택 상태에서 5단계 차단
- `/step/5/download` 응답 헤더의 한글 파일명과 본문 일치
