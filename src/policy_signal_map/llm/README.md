# AI 참고 의견

3단계 검토 질문 아래에서 담당자가 요청한 경우에만 Google AI Studio API로 참고 의견을 만듭니다. AI 의견은 질문·선택·보완 기획안을 바꾸지 않습니다.

| 파일 | 역할 |
|---|---|
| `base.py` | 제공자 공통 형식, 테스트용 가짜 제공자, 설정에 따른 제공자 생성 |
| `google_ai.py` | `generateContent` 호출, 모델 목록 확인, 모델별 사고 설정, 오류 정리 |
| `prompt.py` | 규칙 검토 결과와 담당자 입력을 요청 문장으로 조립 |
| `guard.py` | 규칙 번호·수치·판정 표현을 검사하고 맞지 않는 줄을 제외 |
| `opinions.py` | 요청, 검사, 모델·시각과 함께 결과 묶음 생성 |
| `catalog.py` | `resources/llm/models.json`의 화면 표시 이름을 읽음 |

## 연결 방식

- 제공자: `PSM_LLM_PROVIDER=google_ai`
- 비밀키: `GEMINI_API_KEY`. 서버 환경변수에서만 읽으며 URL, 요청 본문, 브라우저 응답에 넣지 않습니다.
- 주소: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- 인증: `x-goog-api-key` 요청 헤더
- 타임아웃: 기본 45초, 자동 재시도 없음
- 출력 상한: 사고 토큰을 포함해 2,048토큰. 화면에는 검사 통과 문장 중 최대 3줄만 표시

모델별 설정은 다음과 같습니다.

| 모델 | 사고 설정 |
|---|---|
| `gemini-3.8-flash` | `thinkingLevel=low` |
| `gemini-3.6-flash` | `thinkingLevel=low` |
| `gemini-2.5-pro` | `thinkingBudget=128` |
| `gemma-4-31b-it` | `thinkingLevel=minimal` |

Gemini 3 계열에는 `temperature`, `topP`, `topK`를 보내지 않습니다. API 실패는 `LLMError`로 바꾸고, 화면은 규칙 기반 결과를 그대로 유지합니다.

## 화면 호출

`POST /step/3/opinions`는 사용자가 **AI 의견 생성**을 눌렀을 때만 호출합니다. 같은 세션에서 원안과 모델이 같으면 저장해 둔 결과를 사용합니다. 모델을 바꾸면 모델별로 한 번 생성하고, 원안이 바뀌면 모든 모델 캐시를 비웁니다.

선택 목록은 `PSM_LLM_MODELS` 순서입니다. Google Models API 확인에 성공해 사용할 수 없는 것이 확실한 모델만 비활성화하고, 확인 자체가 실패하면 선택을 막지 않습니다.

## 데이터와 출력

현재 기능은 근거 JSON 원문 대신 규칙 결과의 수치 없는 상황 설명과 담당자가 입력한 목표·대상·지표를 전달합니다. 이는 모델 전환 전부터 사용하던 의견 생성 구조입니다. 공개 배포 프로젝트에는 합성 근거 파일만 포함합니다.

답변은 `guard.py`에서 다음을 확인합니다.

- 이번 검토 결과에 있는 규칙 번호를 인용했는지
- 검토하지 않은 규칙을 제안하지 않았는지
- 숫자·비율·수량 표현·판정 표현이 없는지
- 최대 3줄인지

요청·응답 본문과 API 키는 로그에 남기지 않습니다. 제외된 줄은 본문 대신 제외 사유와 글자 수만 기록합니다.
