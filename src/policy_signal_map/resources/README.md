# `resources/` — 코드가 읽는 자료 파일

> 최신화: 2026-09-17

## 이 폴더는 무엇인가

화면에 나오는 **문장, 규칙, 문서 양식, 시연용 가짜 자료**처럼 코드와 따로 관리하는 자료 파일을 모아 둔 곳입니다.
문구를 바꿀 때 파이썬 코드를 고치지 않고 이 폴더의 파일만 고치면 되도록 나눠 두었습니다.
이 폴더는 공개 저장소에 그대로 올라가므로 **실제 카드 분석 결과를 두지 않습니다.**

## 파일 목록

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `regions.json` | 1단계 **지역 선택 목록** (시도·시군구 이름과 코드). 공개 인구 통계에서 도구로 만든 파일 | 직접 고치지 않음 — 다시 만들 때는 `scripts/build_regions.py` |
| `rules/` | **검토 규칙의 문장 원본**: 질문, 고를 수 있는 보완 방법, 기획안에 들어갈 문장 | [README](rules/README.md) |
| `evidence/` | 서비스가 기본으로 읽는 **시연용 가짜(합성) 근거 파일** | [README](evidence/README.md) |
| `documents/` | 보완 기획안·요청서의 **문서 양식** | [README](documents/README.md) |
| `prompts/` | **AI에게 보내는 요청 문장** | [README](prompts/README.md) |
| `llm/` | 3단계 AI 모델 선택 칸에 보이는 **모델 이름표와 설명** | [README](llm/README.md) |
| `README.md` | 이 문서 | 폴더가 늘어날 때 |

---

## 자세한 설명 (개발자용)

### `regions.json`

- 시도 17개·시군구 269개. 최상위 키 `source`(원본 파일 안내), `sido`(시도 목록과 하위 시군구)
- `scripts/build_regions.py`로 생성, 손으로 고치지 않음. 읽는 코드는 `plan/regions.py`

### 폴더별 읽는 코드

| 폴더 | 읽는 코드 | 파일을 고친 뒤 반영 |
|---|---|---|
| `rules/` | `review/rules.py` | 서버 재시작 |
| `evidence/` | `evidence/loader.py` (`config.DEFAULT_EVIDENCE_PATH`) | 서버 재시작 |
| `documents/` | `document/render.py` | 다음 문서 생성부터 |
| `prompts/` | `llm/prompt.py` | 다음 AI 요청부터 |
| `llm/` | `llm/catalog.py` | 서버 재시작 (한 번 읽어 보관) |

### 원칙

- 모든 파일은 UTF-8
- 규칙·모델 목록 JSON은 `version`, 근거 파일은 `schema_version`을 두고 구조를 바꾸면 올린다 (`regions.json`은 도구가 만드는 파일이라 버전 없음)
- 읽는 코드는 형식을 검사하고, 틀리면 조용히 넘어가지 않고 오류로 멈춘다
- `scripts/check_public_bundle.py`가 저장소 전체에 실제 자료가 없는지 검사한다
