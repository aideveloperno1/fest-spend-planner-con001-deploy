# 콕콕 — 공개 배포용 서비스

> 소비데이터로 기획안 한 번 더 보기

> 최신화: 2026-09-22

## 이 저장소는 무엇인가

이 폴더는 공개 배포 전용 복사본이며, 별도 저장소
`aideveloperno1/fest-spend-planner-con001-deploy`에서 관리합니다.
내부용 데이터와 지역 대응표는 이 프로젝트에 저장하지 않습니다.

지자체·행사 담당자가 **사업 기획안을 입력하면**, 카드 소비데이터 근거로 **확인할 점을 질문**으로 보여 주고, 담당자가 고른 보완 방법을 반영한 **보완 기획안 문서**를 만들어 주는 웹 서비스입니다.
서비스는 예측하거나 판정하지 않습니다. 결정은 담당자가 합니다.

```
1 기획 입력 → 2 근거 확인 → 3 검토 질문 → 4 보완 선택 → 5 보완 기획안
```

- 기준 문서(저장소 밖, 한 단계 위 폴더): [최종기획서](../최종기획서.md) · [개발업무 워크플로우](../개발업무_워크플로우.md)
- 사용법: [docs/usage_guide.md](docs/usage_guide.md)
- 합의·진행 기록: [checks.md](./checks.md)

**화면의 모든 수치는 공개 시연용 합성 수치입니다.** 기본 데이터는
`review_evidence_hierarchy_v1.json`(`demo-hierarchy-002`)이며, 2026년 6월 기준 실제 지명에 대응하는 267개 시군구 선택 항목·17개 시도·전국의 합성 월별 근거를 담습니다. 화성시의 출장소 2곳은 행정구역 선택·집계에서 제외했습니다. 인천의 중구·동구·서구는 2026년 7월 개편 전 구역이며 새 구역으로 재배분한 자료가 아닙니다. 실제 지역명의 실제 소비 관측값이 아닙니다. 기획 입력에서 별도 `공개 시연 지역` A~L을 고르면 `review_evidence_public_v2.1.json`(`demo-2.1-003`)을 사용하며, 이 값은 실제 지명 지역의 합계에 섞이지 않습니다.

## 바로 실행하기

uv + Python 3.12, FastAPI + Jinja2.

```powershell
$env:GEMINI_API_KEY="Google AI Studio에서 발급한 키" # 현재 PowerShell 창에만 설정
.\run_deploy.ps1                                 # 공개 데이터 + Google AI로 실행
.\run_deploy.ps1 -NoLlm                          # AI 의견 없이 실행
uv run pytest                                    # 테스트
uv run python scripts/check_public_bundle.py     # 공개 저장소 검사 (push 전)
uv run python scripts/capture_screenshots.py     # 제출용 화면 캡처 다시 찍기
uv run python scripts/build_regions.py           # 지역 선택 목록 다시 만들기
uv run python scripts/build_hierarchy_evidence.py # 계층 합성 근거 재생성
```

### Vercel 배포

이 저장소는 Vercel FastAPI 진입점과 Upstash Redis 세션 저장소가 준비되어 있습니다.
Vercel에서는 `run_deploy.ps1`을 사용하지 않습니다. GitHub 저장소를 연결하고 Upstash Redis를 설치한 뒤
Google AI와 Redis Secret을 등록합니다. 전체 순서는 [Vercel 배포 안내](docs/vercel_deployment.md)에 있습니다.

### 설정 (환경변수)

설정하지 않으면 **합성 근거 파일, AI 의견 없음**으로 실행됩니다. 바꿀 때는 `.env.example`을 `.env`로 복사해 값을 채우고 `--env-file`로 실행합니다. `.env`는 git에 올라가지 않습니다.

```powershell
uv run --env-file .env policy-signal-map
```

| 환경변수 | 기본값 | 의미 |
|---|---|---|
| `PSM_EVIDENCE_PATH` | 공개 합성 파일 `resources/evidence/review_evidence_hierarchy_v1.json` | 배포 서비스가 읽는 분석 근거 파일 |
| `PSM_REGION_MAPPING_PATH` | 사용하지 않음 | 합성자료는 기존 행정구역 선택 코드와 직접 연결된다 |
| `PSM_SESSION_BACKEND` | 로컬 `memory`, Vercel `redis` | 작업 중인 기획과 선택을 저장할 곳 |
| `PSM_SESSION_TTL_S` | `86400` | Redis 세션의 마지막 이용 후 유지 시간(초) |
| `UPSTASH_REDIS_REST_URL` | 없음 | Vercel Marketplace가 넣는 Redis REST 주소. Secret으로만 관리 |
| `UPSTASH_REDIS_REST_TOKEN` | 없음 | Vercel Marketplace가 넣는 Redis REST 토큰. Secret으로만 관리 |
| `PSM_LLM_PROVIDER` | `none` | AI 참고 의견. `none` 또는 `google_ai` |
| `GEMINI_API_KEY` | 없음 | Google AI Studio API 키. `.env` 또는 배포 서비스의 Secret에만 저장 |
| `PSM_LLM_MODEL` | 목록의 첫 모델 | 기본 모델. 배포 기본값은 `gemini-3.8-flash` |
| `PSM_LLM_MODELS` | Google AI 모델 4개 | 3단계 선택 목록. 순서: Gemini 3.8 Flash, 3.6 Flash, 2.5 Pro, Gemma 4 31B IT |
| `PSM_LLM_TIMEOUT_S` | `45` | Google AI 응답을 기다릴 최대 시간(초) |

- 근거 파일은 서버가 처음 필요할 때 한 번 읽어 보관한다. **파일을 바꾸면 서버를 다시 시작한다** (`--reload`는 코드 변경에만 반응)
- 화면 상단 칩에 불러온 파일의 종류와 버전이 표시된다 (`시연용 합성 수치 · demo-hierarchy-002`). 파일에 문제가 있으면 `근거 파일 오류`로 바뀌고, 2단계부터 안내 화면이 나온다
- 테스트는 `tests/conftest.py`가 `PSM_` 환경변수를 비우고 합성 파일로 고정하므로, 셸 설정과 상관없이 같은 결과가 나온다

## 파일 목록 (저장소 맨 위)

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `README.md` | 이 문서. 저장소 소개, 실행 방법, 폴더 안내 | 실행 방법이나 폴더 구성이 바뀔 때 |
| `작업진행.md` | **서비스 완성까지 할 일 전체 목록**과 완료 기준(0~8장). 무엇이 끝났고 무엇이 남았는지 보는 곳 | 다음에 무엇을 할지 정할 때, 작업을 끝냈을 때 체크 |
| `checks.md` | **결정한 것·연결 확인 결과·시험 결과·진행 기록**을 모은 장부 | 무언가를 정했거나 확인·완료했을 때 한 줄 기록 |
| `1근거계산계층계획.md` | 1번 작업(근거 파일 읽기·비교 계산)을 **만들기 전에 세운 설계와 결정 이유** | 계산 규칙이 왜 이렇게 됐는지 궁금할 때. 본문은 작성 당시 기록이라 코드가 우선 |
| `2근거확인화면계획.md` | 2번 작업(2단계 근거 확인 화면)의 설계와 결정 이유 | 〃 |
| `3검토질문계획.md` | 3번 작업(3단계 검토 질문 규칙)의 설계와 결정 이유 | 〃 |
| `4보완선택계획.md` | 4번 작업(4단계 보완 선택)의 설계와 결정 이유 | 〃 |
| `5보완기획안계획.md` | 5번 작업(5단계 보완 기획안과 저장)의 설계와 결정 이유 | 〃 |
| `6LLM참고의견계획.md` | 배포용 Google AI 참고 의견 기능의 설계와 모델별 호출 설정 | AI 기능을 바꾸거나 모델을 새로 고를 때 |
| `7지역확장계획.md` | 지역 소비 프로필·유사 지역·성과지표 점검·사업 유형별 질문을 **만들기 전에 정한 약속**(근거 파일 2.1 계약, 지역 대응표 서식, 새 질문이 문서 어느 장에 들어가는지) | 고도화 작업을 시작·이어갈 때, 근거 파일 형식을 데이터 담당과 맞출 때 |
| `pyproject.toml` | 프로젝트 이름, **필요한 라이브러리 목록**, 실행 명령(`policy-signal-map`), 테스트 설정 | 라이브러리를 추가·변경할 때 |
| `uv.lock` | 설치할 라이브러리의 **정확한 버전을 고정**한 파일. `uv sync`가 자동으로 만듦 | 직접 고치지 않음 |
| `.python-version` | 사용할 파이썬 버전(3.12) | 파이썬 버전을 바꿀 때 |
| `.env.example` | 설정 파일 **예시**. 복사해서 `.env`를 만들어 씀 | 새 환경변수를 추가할 때 |
| `vercel.json` | Vercel 실행 지역·최대 실행 시간·함수 번들 제외 항목 | Vercel 실행 조건을 바꿀 때 |
| `.gitignore` | git에 올리지 않을 파일 목록. **private 폴더, 이름에 real이 들어간 근거 파일과 비밀 설정 파일을 막음** | 올리면 안 되는 파일 종류가 늘어날 때 |
| `.gitattributes` | 줄바꿈을 LF로 맞추고 이미지를 바이너리로 다루는 규칙 | 거의 고칠 일 없음 |

## 폴더 목록

주요 폴더의 `README.md`에는 폴더 역할과 파일 목록이 있습니다.

| 폴더 | 하는 일 (쉬운 말) | README |
|---|---|---|
| `src/policy_signal_map/` | 서비스 코드 전체. 앱 시작·설정·표시 형식처럼 모두가 함께 쓰는 파일 | [README](src/policy_signal_map/README.md) |
| `  plan/` | 담당자가 입력하는 기획안의 칸, 빠진 칸 확인, 지역 목록, 바뀐 칸 찾기 | [README](src/policy_signal_map/plan/README.md) |
| `  evidence/` | 데이터 담당이 준 근거 파일을 읽고 검사하고, 이웃 달끼리 비교 계산 | [README](src/policy_signal_map/evidence/README.md) |
| `  review/` | 검토 규칙(R07 등)을 실행해 담당자에게 던질 질문을 만듦 | [README](src/policy_signal_map/review/README.md) |
| `  choices/` | 담당자가 고른 보완 방법을 저장·취소하고, 원안이 바뀌면 다시 확인하게 함 | [README](src/policy_signal_map/choices/README.md) |
| `  document/` | 원안과 선택을 합쳐 보완 기획안 문서(Markdown)를 만듦 | [README](src/policy_signal_map/document/README.md) |
| `  llm/` | AI 참고 의견: Google AI에 요청하고, 답을 검사하고, 모델 표시 이름을 관리 | [README](src/policy_signal_map/llm/README.md) |
| `  web/` | 화면: 주소별 처리, 세션, 폼 읽기, 화면용 데이터, AI 모델 선택 | [README](src/policy_signal_map/web/README.md) |
| `    routes/` | 주소(`/`, `/step/1` 등)마다 무엇을 보여 줄지 정함 | [README](src/policy_signal_map/web/routes/README.md) |
| `    templates/` (`steps/`, `partials/`) | 화면의 HTML 틀 | [README](src/policy_signal_map/web/templates/README.md) |
| `    static/` (`css/`, `js/`) | 화면 모양(CSS)과 즉시 반응(JS) | [README](src/policy_signal_map/web/static/README.md) |
| `  resources/` (`rules/`, `evidence/`, `documents/`, `prompts/`, `llm/`) | 코드가 읽는 자료: 규칙 문구, 합성 근거, 문서 양식, AI 요청 문장, 모델 표시 이름, 지역 목록 | [README](src/policy_signal_map/resources/README.md) |
| `tests/` (`fixtures/evidence/`) | 자동 시험(pytest)과 시험용 근거 파일 | [README](tests/README.md) |
| `scripts/` | 사람이 필요할 때 실행하는 도구: 지역 목록·합성 근거 만들기, 공개 저장소 검사, 화면 캡처 | [README](scripts/README.md) |
| `docs/` (`screenshots/`) | 사람이 읽는 문서: 규칙 설명, 사용법, 제출용 캡처 | [README](docs/README.md) |

---

## 자세한 설명 (개발자용)

### 구조와 의존 방향

순수 로직(plan·evidence·review·choices·document)과 웹 계층(web)을 나눈다. 의존 방향은 한쪽으로만 간다.

```
web → document → choices → review → evidence, plan
llm → review 결과·plan·labels·config만 사용 (evidence·web 직접 사용 금지)
```

`tests/test_boundaries.py`가 일부 방향을 자동으로 검사한다. 자세한 내용은 [src/policy_signal_map/README.md](src/policy_signal_map/README.md).

### 공개 데이터 경계

서비스에는 공개 합성 JSON과 공개 설명 문서만 포함합니다. `scripts/check_public_bundle.py`가 추적 파일을 검사해
`private/`, 실제 자료 표시, 원자료 형식과 비밀 설정 파일의 커밋을 차단합니다.

## 권리 고지

이 저장소는 「제1회 AI금융빅데이터플랫폼 소비데이터 활용 아이디어 공모전」 제출을 위한 작업물이며, 오픈소스 라이선스를 부여하지 않는다.
코드와 문서의 모든 권리는 작성자에게 있고, 사전 허락 없이 사용·복제·수정·배포할 수 없다.
공모전 수상 시 산출물의 권리는 공모전 규정에 따른다.

사용한 외부 라이브러리와 글꼴은 각자의 라이선스를 따른다 (FastAPI·Chart.js·Upstash Redis Python SDK: MIT, Jinja2·uvicorn: BSD, Pretendard: SIL OFL).
