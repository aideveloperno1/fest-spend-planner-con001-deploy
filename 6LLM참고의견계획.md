# 6. AI 참고 의견 — Google AI 배포 계획

> 적용일: 2026-09-21
> 대상: 공개 합성 데이터 전용 배포 서비스

## 목적

3단계 규칙 검토 결과를 바탕으로 Google AI가 담당자가 추가로 확인할 점을 최대 3줄 제시합니다. AI 응답은 참고용이며 규칙 결과, 보완 선택, 보완 기획안을 변경하지 않습니다.

## 제공자와 모델

배포 서비스의 제공자는 `none`과 `google_ai`만 허용합니다. 기본 모델과 화면 순서는 다음과 같습니다.

1. `gemini-3.8-flash` — 기본
2. `gemini-3.6-flash`
3. `gemini-2.5-pro`
4. `gemma-4-31b-it`

`gemini-3.5-flash-lite`는 선택 목록에서 제외합니다.

## API 요청

- 엔드포인트: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- 인증: 서버 환경변수 `GEMINI_API_KEY`를 `x-goog-api-key` 헤더로 전달
- 요청 내용: 시스템 지시문과 규칙 결과·기획 요약
- `maxOutputTokens`: 2,048. 사고 토큰이 이 한도에 포함되므로 기존 400에서 올림
- 타임아웃: 45초
- 자동 재시도 없음
- API 키, 요청 본문, 응답 본문을 로그에 기록하지 않음

모델별 사고 설정:

| 모델 | 설정 |
|---|---|
| Gemini 3.8 Flash | `thinkingLevel=low` |
| Gemini 3.6 Flash | `thinkingLevel=low` |
| Gemini 2.5 Pro | `thinkingBudget=128` |
| Gemma 4 31B IT | `thinkingLevel=minimal` |

Gemini 3 계열에는 `temperature`, `topP`, `topK`를 보내지 않습니다.

## 화면 흐름

화면 진입만으로 콘텐츠 생성 API를 호출하지 않습니다. 모델 사용 가능 여부는 프로세스에서 한 번 조회해 보관하고, 담당자가 **AI 의견 생성**을 누르면 `POST /step/3/opinions`가 호출됩니다.

- 같은 원안·같은 모델의 결과는 세션에 보관해 다시 사용
- 원안이 바뀌면 모든 모델의 AI 의견 캐시 삭제
- Google Models API에서 현재 키로 사용할 수 없는 것이 확실한 모델만 선택 비활성화
- 모델 확인 API가 실패하면 선택은 허용하고 실제 생성 요청 결과로 안내
- 인증, 할당량, 안전 필터, 시간 초과, 응답 형태 오류는 모두 일반 실패 안내로 처리
- AI 실패와 관계없이 1~5단계 규칙 기반 흐름은 계속 동작

## 데이터와 출력 검사

Google 전환 때문에 별도의 입력 마스킹을 추가하지 않습니다. 기존 의견 기능과 같이 규칙 결과의 상황 설명과 담당자 입력 요약을 사용하며 근거 JSON 원문을 직접 전달하지 않습니다.

응답은 다음 조건을 통과한 줄만 표시합니다.

- 이번 검토에 있는 규칙 번호 인용
- 검토하지 않은 규칙을 제안하지 않음
- 숫자·비율·한글 수량 표현 없음
- 성공·실패 등 판정 표현 없음
- 최대 3줄

## 설정 예시

```text
PSM_LLM_PROVIDER=google_ai
GEMINI_API_KEY=<배포 서비스 Secret>
PSM_LLM_MODELS=gemini-3.8-flash,gemini-3.6-flash,gemini-2.5-pro,gemma-4-31b-it
PSM_LLM_MODEL=gemini-3.8-flash
PSM_LLM_TIMEOUT_S=45
```

API 키는 저장소에 저장하지 않습니다. 로컬 `.env`와 배포 플랫폼의 Secret만 사용합니다.

## 검증 기준

- 모델 순서와 기본 모델이 설정·화면·실행 스크립트에서 같음
- 모델별 사고 설정이 정확함
- API 키가 URL·본문·오류·로그에 나타나지 않음
- `GET /step/3/opinions`는 생성하지 않고, `POST`만 생성함
- 같은 원안·모델은 한 번만 호출함
- 외부 API를 실제로 부르지 않는 자동 테스트 통과
- 공개 저장소 검사에서 비공개 자료와 비밀 설정 위반이 없음
