# Vercel 배포 안내

> 기준: 2026-09-22

이 저장소는 Vercel의 Python 3.12 FastAPI 런타임과 Upstash Redis 세션을 사용한다.
`run_deploy.ps1`은 로컬 실행용이며 Vercel에서는 실행하지 않는다.

## 1. 프로젝트 연결

Vercel에서 `aideveloperno1/fest-spend-planner-con001-deploy` 저장소를 가져온다.
Root Directory는 저장소 루트(`.`), Framework Preset은 FastAPI 자동 감지를 사용한다.
`pyproject.toml`의 `[tool.vercel]`이 저장소 루트의 `main.py`에 있는 FastAPI 객체(`main:app`)를 진입점으로 지정한다.

## 2. Redis 연결

Vercel Marketplace에서 **Upstash Redis**를 이 프로젝트에 연결한다. 연결 뒤 Preview와 Production에
다음 Secret이 들어왔는지 확인한다.

```text
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
```

브라우저 쿠키에는 무작위 세션 ID만 저장한다. 기획안·보완 선택·AI 의견은 Redis에 JSON으로 저장하며
마지막 이용 뒤 기본 24시간이 지나면 만료된다.

## 3. 환경변수

Preview와 Production에 다음 값을 등록한다.

```text
PSM_SESSION_BACKEND=redis
PSM_SESSION_TTL_S=86400
PSM_LLM_PROVIDER=google_ai
GEMINI_API_KEY=<Google AI Studio에서 발급한 키>
PSM_LLM_TIMEOUT_S=45
```

모델 목록과 기본 모델은 코드의 고정 기본값을 사용한다. 직접 지정하려면 다음 값을 그대로 쓴다.

```text
PSM_LLM_MODELS=gemini-3.8-flash,gemini-3.6-flash,gemini-2.5-pro,gemma-4-31b-it
PSM_LLM_MODEL=gemini-3.8-flash
```

`PSM_EVIDENCE_PATH`는 설정하지 않아도 저장소의 계층 합성 파일(`review_evidence_hierarchy_v1.json`)을 사용한다. 기존 배포에 이 환경변수가 옛 파일로 설정돼 있다면 새 경로로 변경하거나 변수를 제거해야 한다.
`PSM_REGION_MAPPING_PATH`는 공개 배포에 등록하지 않는다.

## 4. 배포 확인

Preview 배포가 끝나면 다음을 확인한다.

1. `GET /health`가 HTTP 200과 `status: ok`, `session_backend: redis`를 반환한다.
2. 랜딩 화면의 CSS·JS·이미지가 표시된다.
3. 상단 배지가 `demo-hierarchy-002`인지 확인한다. 안양시 전체·만안구·동안구를 각각 고를 때 2단계 차트 값이 달라지고, 안양시의 월별 원금액은 두 구의 합과 같다. 화성시 출장소 2곳은 선택지에 없어야 한다. `공개 시연 지역` A를 선택하면 2~5단계 배지가 `demo-2.1-003`으로 바뀌고, 실제 지명을 다시 고르면 `demo-hierarchy-002`로 돌아와야 한다.
4. 1단계 예시 기획부터 5단계 문서 다운로드까지 이어진다.
5. 새로고침하거나 다음 요청이 다른 인스턴스로 전달돼도 입력과 선택이 유지된다.
6. 3단계에서 모델을 고르고 **AI 의견 생성**을 눌렀을 때 Google AI 응답이 표시된다.
7. Vercel 로그에 API 키·Redis 토큰·전체 세션 JSON이 출력되지 않는다.

코드 검증 명령은 다음과 같다.

```powershell
uv run pytest -q
uv run python scripts/check_public_bundle.py
vercel build
```

Preview 검증이 끝난 배포만 Production으로 승격한다.
