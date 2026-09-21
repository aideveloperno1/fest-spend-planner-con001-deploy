# `scripts/` — 사람이 필요할 때 실행하는 도구

> 최신화: 2026-09-17

## 이 폴더는 무엇인가

서비스가 돌아가는 동안에는 쓰지 않고, **개발자가 필요할 때 직접 실행하는 도구**를 모아 둔 곳입니다.
지역 목록·시연용 가짜 근거·시험용 근거 파일을 만들고, 공개 저장소에 실제 자료가 섞이지 않았는지 검사하고, 제출용 화면을 찍습니다.
모두 `uv run python scripts/<파일>.py`로 실행합니다.

## 파일 목록

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `check_public_bundle.py` | **공개 저장소 검사.** git에 올라가는 파일 중 실제 자료·비밀 설정·원본 데이터 파일이 섞였는지 찾아냄 | **push 전에 매번 실행** |
| `capture_screenshots.py` | 서비스를 가짜 자료로 띄워 1~5단계를 자동으로 누르고 **제출용 화면 캡처 6장**을 찍음 | 화면이 바뀌어 캡처를 다시 찍을 때 |
| `build_regions.py` | 공개 인구 통계 파일에서 **1단계 지역 선택 목록**(시도·시군구)을 만듦 | 지역 목록을 새로 만들어야 할 때 |
| `build_region_mapping.py` | 분석 쪽 지역표를 **서비스 지역 코드(10자리)에 잇는 대응표**를 만듦. 결과는 `private/`에 저장 | 분석 쪽에서 새 지역표를 받았을 때 |
| `build_demo_evidence.py` | 화면 시연에 쓰는 **가짜(합성) 근거 파일**을 만듦. 지역 프로필·업종별 연령 구성·외부 인구도 실제 값을 쓰지 않고 코드에서 만듦 | 시연 화면에 보일 가짜 자료를 바꿀 때 |
| `build_fixtures.py` | 자동 시험에 쓰는 **경계 사례 근거 파일 28개**를 만듦 (정상 파일, 일부러 틀린 파일) | 시험 사례를 추가·변경할 때 |
| `_evidence_builder.py` | 위 두 도구가 함께 쓰는 **근거 파일 조립 도우미**. 직접 실행하지 않음 | 근거 파일 형식이 바뀔 때 |
| `README.md` | 이 문서 | 도구를 추가·변경할 때 |

---

## 자세한 설명 (개발자용)

### 지켜야 할 원칙

- 스크립트는 `src/policy_signal_map`의 함수를 가져다 쓸 수 있지만, 서비스 코드가 스크립트를 가져다 쓰지는 않는다.
- 스크립트가 만든 결과 파일도 커밋 전에 `check_public_bundle.py`를 통과해야 한다.

### `build_regions.py`

- 입력: 저장소 한 단계 바깥의 `데이터/2/202601_202606_주민등록인구및세대현황_월간.csv` (코드의 `SRC`, 행정안전부 공개 자료, cp949). **9/17 기준 현재 작업 폴더에는 이 경로가 없다.** 결과 파일은 이미 커밋돼 있으므로 다시 만들 때만 원본을 해당 위치에 둔다
- 출력: `src/policy_signal_map/resources/regions.json`
- 규칙: 10자리 행정코드 끝 8자리가 0이면 시도, 6월 총인구 0인 코드 제외, 세종처럼 시군구 없는 시도는 하위 목록 비움
- 카드 CSV는 사용하지 않는다

### `build_region_mapping.py`

- 입력: 저장소 한 단계 바깥의 분석 쪽 지역표 CSV(`--자료`로 바꿀 수 있음)와 `resources/regions.json`
- 출력: `private/region_mapping.json` (`--결과`로 바꿀 수 있음). **공개 저장소에 올리지 않는다** — 어느 지역이 제공 자료에 들어 있는지가 드러난다
- 연결 상태: `linked`(그대로 붙음) · `composed`(여러 코드를 합치거나 나눠 붙음) · `unlinked`(서비스 지역인데 자료에 줄이 없음) · `source_only`(자료에만 있음)
- 화면에는 **개수와 상태만** 찍는다. 지역 이름은 파일에만 쓴다
- 구를 둔 시와 그 구가 둘 다 연결되면 전국 합계가 두 번 더해지므로 `double_count_risk`로 표시한다
- 형식과 결정 이유: `7지역확장계획.md` 4장

### `_evidence_builder.py`

`ok_month`, `status_month`, `record`, `evidence_file`, `write_json`. 비중을 정수 금액에서 계산해 소수 10자리로 넣고, 미상 제외 분모가 0이면 null과 경고를 넣는다. JSON은 UTF-8·LF로 쓴다.

### `build_fixtures.py`

`tests/fixtures/evidence/`의 경계 사례 28개를 만든다. 월 수치로 직접 만드는 10개, 정상 ①에서 한 곳만 바꾸는 12개, 지역(시도) 사례 3개, 2.1 프로필 사례 3개로 나뉜다(12개 중 `denominator_zero`는 로드 성공, 나머지 11개는 로드 실패). 사례 수치와 기대 결과는 `1근거계산계층계획.md` 6장. `build_all()`은 테스트가 커밋된 파일과 비교할 때도 쓴다. 생성 목록에 없는 JSON이 폴더에 남아 있으면 종료 코드 1.

### `build_demo_evidence.py`

화면 시연용 합성 근거 파일을 만든다. 손으로 JSON을 쓰면 비중(%)과 금액이 서로 안 맞기 쉬워서, 정수 금액만 정하고 비중은 계산해서 넣는다.

- 출력: `src/policy_signal_map/resources/evidence/review_evidence_demo_v1.json`
- 내용
  - 레코드 A: 전국, 2026-01~06, 6개월 모두 `ok`. 금액·비중 반대 방향 구간과 같은 방향 구간이 섞이도록 구성 (반대 방향만 고르지 않음, 워크플로우 8-3장)
  - 레코드 B: 가상 시도 1곳, `no_data` 월과 `invalid_denominator` 월 포함 → 보류 사례 화면용
- 모든 레코드에 `data_kind: "synthetic"`, `dataset_version: "demo-001"`, limitations에 "합성 자료" 포함
- 금액은 누가 봐도 가상 규모로 정한다. 최종기획서 4-2장 등 **실제 분석 수치를 쓰지 않는다**
- 비중 계산은 `_evidence_builder.py`를 쓰고, 만든 파일을 `evidence/loader.py`로 다시 읽어 오류·경고가 없는지 확인한다
- 테스트용 경계 사례는 이 스크립트가 아니라 `build_fixtures.py`가 만든다

### `check_public_bundle.py`

공개 저장소·공개 배포에 실제 자료가 섞이지 않았는지 검사한다. 파일 이름이 아니라 내용으로 검사해 이름을 바꿔 둔 실수도 잡는다.

- 대상: `git -c core.quotepath=false ls-files -z`로 얻은 추적 파일 전체 (한글 경로가 이스케이프되면 파일을 열지 못해 검사가 빠지므로), 열 수 없는 추적 파일은 위반
- 실패 조건
  - `.json` 파일 안에 `"data_kind"`가 `"synthetic"`이 아닌 값이 있음 (`"real"`, `"actual_internal"` 등. 9/17부터 서비스의 실제 자료 기준과 같음)
  - 경로에 `private/`가 있음
  - `.env` 파일이 추적됨
  - `dataset_version`이 `demo-`·`fixture-`로 시작하지 않는 근거 파일
  - 경로에 `_real_`이 있는 파일
  - 원자료 형식(`.csv`, `.xlsx`, `.xls`, `.parquet`) 파일 — 원본 카드 자료가 CSV라서 내용 검사 대상(JSON) 밖의 유출을 막는다
- 허용 예외: `tests/fixtures/evidence/mixed_data_kind.json` (이름표만 real인 가짜 수치)
- 결과: 문제 파일 목록을 출력하고 종료 코드 1
- `tests/test_public_bundle.py`에서도 같은 함수를 호출해 `uv run pytest`로 함께 검사한다

### `capture_screenshots.py`

`docs/screenshots/` 이름 규칙대로 제출·사용법용 캡처 6장을 만든다(2026-09-17).

- 실행: `uv run python scripts/capture_screenshots.py` (AI 참고 의견 포함) · `--no-ai` · `--chrome <경로>` · `--models <목록>` · `--ollama <주소>` · `--out <폴더>`
- **합성 자료만:** 셸의 `PSM_` 환경변수를 모두 비우고 서버를 따로 띄운다. 캡처 전마다 상단 표시가 "시연용 합성 수치"인지 확인하고 아니면 종료한다
- 창 없는 Chrome(임시 프로필, 끝나면 삭제)을 Chrome DevTools Protocol로 조작한다. 예시 기획 채우기 → 검토 시작 → 4단계 R07 대안 A 입력·저장 → 5단계 순서로 실제 화면을 거친다
- 전체 페이지는 화면 높이를 페이지 높이로 키우고 3초 기다린 뒤 찍는다. 화면 밖까지 한 번에 찍는 옵션을 쓰면 차트가 다시 그려지는 중에 찍혀 막대·선이 왼쪽에 뭉쳤다
- 페이지 콘솔 오류가 있으면 파일은 남기고 종료 코드 1
- `websockets`는 `uvicorn[standard]`와 함께 설치된 패키지를 쓴다(실행 의존성을 따로 늘리지 않음). 없으면 `uv sync` 안내 후 종료
- 테스트는 없다. 캡처를 바꾸면 이미지를 직접 열어 확인한다
