# `resources/llm/` — AI 모델 이름표와 설명

> 최신화: 2026-09-17

## 이 폴더는 무엇인가

3단계 **AI 모델 선택 칸**에 보이는 모델의 **읽기 쉬운 이름과 한 줄 설명**을 두는 곳입니다.
여기에 적는다고 모델을 고를 수 있게 되는 것은 아닙니다. **실제로 고를 수 있는 모델은 설정 파일(`.env`)의 모델 목록이 정합니다.** 여기에 없는 모델은 모델 이름이 그대로 보입니다.

## 파일 목록

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `models.json` | 모델마다 **화면에 보일 이름과 설명** (지금 3개: EXAONE 3.5 두 가지, Gemma 4) | 새 모델을 설치해 목록에 추가할 때, 설명을 바꿀 때 |
| `README.md` | 이 문서 | 파일이 늘어날 때 |

---

## 자세한 설명 (개발자용)

### `models.json` 구조

```
{
  "version": "1.0",
  "description": "...",
  "models": [
    { "id": "gemma4:26b-a4b-it-qat", "label": "화면 표시 이름", "description": "한 줄 설명" }
  ]
}
```

- `id`는 Ollama 모델 이름과 똑같이 적는다 (`PSM_LLM_MODELS`의 값과 비교)
- 읽는 코드: `llm/catalog.py`(`load_catalog`, `model_info`). 형식 검사: `version` 문자열, `models` 목록, `id`·`label`·`description` 빈 값 금지, `id` 중복 금지, 규칙 금지어(판정 표현) 금지 → 틀리면 `CatalogError`
- 한 번 읽어 보관하므로 **고친 뒤 서버를 다시 시작**한다
- 화면 조립은 `web/ai_models.py`: 목록의 모델마다 이름표·설명과 받아 둔 모델인지(`llm/local.list_models`)를 붙인다

### 새 모델을 추가하는 순서

1. `ollama pull <모델 이름>`으로 받는다
2. `.env`의 `PSM_LLM_MODELS`에 쉼표로 추가하고 서버를 다시 시작한다
3. (선택) 이 파일에 이름표·설명을 추가한다. 순위·점수·추천 표현은 쓰지 않는다
4. `uv run pytest` (`tests/test_llm_catalog.py`가 이 파일을 검사)
