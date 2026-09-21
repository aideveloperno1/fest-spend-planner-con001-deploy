# AI 모델 표시 자료

`models.json`은 3단계 선택 칸에 보일 Google AI 모델의 ID, 이름과 설명을 관리합니다.

현재 화면 순서는 다음과 같습니다.

1. `gemini-3.8-flash` — Gemini 3.8 Flash, 기본 모델
2. `gemini-3.6-flash` — Gemini 3.6 Flash
3. `gemini-2.5-pro` — Gemini 2.5 Pro
4. `gemma-4-31b-it` — Gemma 4 31B IT

`gemini-3.5-flash-lite`는 선택 목록에 넣지 않습니다. 실제 선택 가능 목록은 `PSM_LLM_MODELS`가 정하며, `models.json`에 없는 ID는 ID 자체를 화면 이름으로 사용합니다.

파일은 다음 형태입니다.

```json
{
  "version": "2.0",
  "models": [
    {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash", "description": "한 줄 설명"}
  ]
}
```

ID 중복, 빈 이름·설명, 판정 표현은 `llm/catalog.py`가 거부합니다. 배열 순서와 배포 실행 설정의 모델 순서를 함께 맞추고 `tests/test_llm_catalog.py`와 `tests/test_config.py`로 확인합니다.
