# `evidence/` — 데이터 담당이 준 근거 파일 읽기·검사·비교 계산

> 최신화: 2026-09-21

## 이 폴더는 무엇인가

데이터 분석 담당이 카드 소비데이터로 만든 **근거 파일**을 읽어, 형식이 약속대로인지·숫자끼리 맞는지 검사하는 곳입니다.
그다음 **이웃한 두 달을 비교**해 "외국인 결제금액은 늘었는데 비중은 줄었는가" 같은 방향 차이를 계산합니다.
숫자를 고치거나 새로 만들지 않고, 화면·규칙·AI와 상관없이 계산만 합니다. 실제 수치가 오류 문구로 새지 않도록 값 대신 형식만 알려 줍니다.

## 파일 목록

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `__init__.py` | 이 폴더를 파이썬 묶음으로 인식시키는 빈 파일 | 고칠 일 없음 |
| `schema.py` | **근거 파일의 약속된 모양**(어떤 칸이 있고 어떤 값이 허용되는지)을 적어 두고, 받은 파일이 그 약속을 지켰는지 하나하나 검사 | 데이터 담당과 파일 형식을 바꾸기로 했을 때 |
| `delivery_v21.py` | **분석팀 전달본 2.1 변환.** 전달본의 레코드 안 프로필·평면 기준값·지역명을 서비스 내부 2.1과 10자리 행정코드로 바꿈. 값은 다시 계산하지 않음 | 분석팀 전달본 구조나 지역 대응 계약이 바뀔 때 |
| `profile_schema.py` | **근거 파일 2.1에 더해진 지역 프로필·업종별 연령 구성·외부 인구·운영 기준**의 모양과 검사. 부분 묶음이 고장 나면 그 기능만 끔 | 지역 프로필 형식을 바꾸기로 했을 때 |
| `loader.py` | 파일을 열어 읽고 검사를 부름. **실제 자료인지 가짜(합성) 자료인지 판단**하고, 원하는 지역 범위의 자료를 찾음 | 실제 자료 판단 기준이나 파일 읽는 방식을 바꿀 때 |
| `compare.py` | **이웃한 두 달 비교 계산.** 금액 방향과 비중 방향이 서로 다른지(비교 A), 미상 포함·제외 비중 방향이 다른지(비교 B) | 비교 방법을 바꿀 때 (워크플로우 8장과 함께) |
| `summary.py` | 여러 달을 **합산한 기간 비중**과 "비교할 수 있는 구간 몇 개 중 방향이 다른 구간 몇 개" 같은 **개수 요약** | 요약 항목을 늘릴 때 |

---

## 자세한 설명 (개발자용)

### 역할 요약

`review_evidence.json`을 읽어 형식·상태값·수치 관계를 검증하고, 인접 월의 **비교 A(외국인 금액 vs 전체 분모 비중)**와 **비교 B(전체 분모 비중 vs 미상 제외 비중)**를 계산한다. 화면·규칙·LLM과 무관한 순수 계산 계층이다.

### 기준 문서

- 워크플로우 8-1 F·T·U 정의, 8-2 두 종류의 비교, 8-3 작은 차이 표시, 8-4 전국 우선·시도 조건부, 8-5 검증 예시
- 워크플로우 9-1 `calculation_status`, 9-2 `applicability`, 9-3 파일 형식
- 워크플로우 12장 시험 항목 중 서비스 담당분

### 파일별 상세

#### `schema.py`

워크플로우 9-3장 형식을 그대로 옮긴 dataclass. 필드명은 JSON과 같게 둔다 (데이터 담당과 대조하기 쉽게).

```
EvidenceFile
  schema_version: "2.0"          지원 버전 목록에 없으면 오류
  dataset_version: str           합성은 "demo-"로 시작
  records: list[EvidenceRecord]

EvidenceRecord
  evidence_id: str               파일 안에서 중복 금지
  data_kind: "synthetic" | "real"   다른 값은 오류. 서비스는 synthetic이 아니면 실제 자료로 취급
  scope: Scope
    geographic_scope: "national" | "sido"
    region_key: "ALL" | 시도 고정 키     national이면 반드시 ALL
    population: "foreign_code_3"
    industry_scope: "all_provided"
    age_scope: "all"
    period_start / period_end: "YYYY-MM"
  region_basis: str              예: "unknown"
  applicability: {"R07" | "R06" | "R02": Applicability}
    status: "allowed" | "needs_review" | "blocked"
    reason: str                  빈 문자열 금지
  amount_unit: "KRW"
  months: list[MonthValue]
  limitations: list[str]

MonthValue
  month: "YYYY-MM"
  calculation_status: "ok" | "no_data" | "invalid_input" | "invalid_denominator"
  foreign_amount / total_amount / unknown_amount: int | None     원 단위 정수
  transaction_count: int | None  고객 수가 아니라 거래 건수
  foreign_share_pct / known_only_share_pct / unknown_share_pct: float | None   8% → 8.0
  warnings: list[str]
```

- `parse_evidence(data) -> ParseResult(file, errors, warnings)`: 오류가 하나라도 있으면 `file`은 None
- 허용 값은 파일 위쪽 상수(`SUPPORTED_SCHEMA_VERSIONS`, `CALCULATION_STATUSES` 등) 한곳에서 관리한다
- 계산에 쓰는 값은 정수 F·T·U·C뿐이며, 파일의 `*_share_pct`는 대조·표시 참고용이다

검증 규칙 전체(파일 9·레코드 15·월 15개)와 선행 조건은 [1근거계산계층계획.md 7장](../../../1근거계산계층계획.md#7-1-3b-검증과-로더)을 따른다. 핵심:

1. 목록에 없는 상태값·범위값 → 오류 (9-2장). 상태값이 틀린 월은 상태별 규칙을 적용하지 않는다
2. `reason` 누락·빈 값 → 오류
3. `ok` 월: F·T·U·C는 0 이상 정수(참/거짓·소수 불가), T > 0, `F + U ≤ T` (8-1장). 형식이 틀린 월은 관계 검사를 하지 않는다
4. `ok` 월: 미상 제외 분모(T−U)가 0이면 `known_only_share_pct`는 null
5. `ok` 월: 파일 비중과 재계산 비중의 차이가 1e-6%p를 넘으면 **경고**. 숫자를 고치지 않는다
6. months는 기간의 모든 월을 순서대로 한 번씩 포함. **누락 월을 생략하지 않고 상태·null로 둔다** (9-3장)
7. `no_data` 월의 금액·비중은 null. 0이면 오류 ("관측 0"과 "자료 없음" 구분, 8-1장)
8. 한 파일에 합성·실제 레코드 혼합, `evidence_id` 중복 → 오류
9. 모르는 필드 → 경고 후 계속 읽기. `_`로 시작하는 최상위 필드는 무시

오류 문구 형식: `[레코드 ID / 월 / 필드] 내용`. **금액·건수·비중 필드는 값을 출력하지 않고 형식(정수·소수·글자 등)만** 적는다. 실제 파일 오류가 화면·로그로 옮겨질 때 카드 수치가 새지 않게 하기 위해서다.

#### `loader.py`

- `load_evidence(path, region_mapping_path=None) -> LoadResult(file, warnings, source_path)`: 파일 읽기(UTF-8, BOM 허용, NaN·Infinity 거부) → 전달본이면 `delivery_v21` 변환 → `parse_evidence`. 실패 시 `EvidenceError(messages, path)`
- 전달본 실자료는 `region_mapping_path`의 `linked`·`composed` 행만 사용한다. 대응표가 없으면 지역명을 추정하지 않고 전국 레코드만 읽는다
- `find_record(file, geographic_scope, region_key)`: 요청한 범위가 없으면 None. **전국 자료로 자동 대체하지 않는다** (9-3장). 입력 화면 행정코드와 `region_key`는 **행정표준코드 10자리**로 잇는다 (연결 키 C-1). 어느 레코드를 쓸지는 `review/context.select_main()`이 정한다 (시군구 → 시도 → 전국 사다리)
- `has_real_records(file)`, `is_real_evidence(path, file)`: **경로에 `private` 폴더·이름에 `_real_`이 있거나**, 레코드의 `data_kind`가 `synthetic`이 아니면 실제 자료로 본다. 파일이 검증에 실패했으면 `raw_marks_real(path)`가 원문의 `data_kind`를 찾아 같은 기준으로 본다(예: `actual_internal` — 2026-09-17 임시본 점검에서 알아보지 못하던 경우). `config.check_llm_data_combination`에 넘긴다
- 파일 경로는 `config.py`에서 받는다. 이 모듈은 캐시하지 않으며, 앱 시작 시 한 번 읽어 보관하는 것은 web 계층(2-1)의 몫이다

#### `compare.py`

인접 월 0 → 1 쌍마다 계산한다. **정수 연산과 `fractions.Fraction`만 사용**하고 float는 표시 직전에만 쓴다.

```
MonthPair
  month_0, month_1
  status: "ok" | "skipped"
  skip_reason: str | None            예: "2026-02 자료 없음(no_data)", 두 달 모두면 쉼표로 함께

  foreign_amount_diff: int | None               F1 - F0
  foreign_amount_growth_pct: Fraction | None    (F1-F0)/F0 × 100, F0 == 0 이면 None
  total_amount_growth_pct: Fraction | None      (T1-T0)/T0 × 100
  share_change_pp: Fraction | None          (F1/T1 - F0/T0) × 100
  known_only_share_change_pp: Fraction | None   (F1/(T1-U1) - F0/(T0-U0)) × 100

  comparison_a: DirectionComparison   외국인 금액 방향 vs 전체 분모 비중 방향
  comparison_b: DirectionComparison   전체 분모 비중 방향 vs 미상 제외 비중 방향

DirectionComparison
  left: "up" | "down" | "flat" | None
  right: "up" | "down" | "flat" | None
  opposite: bool | None
```

계산 규칙

| 규칙 | 근거 |
|---|---|
| 두 달 중 하나라도 `calculation_status != "ok"` → 파생 비중 비교 안 함, `skipped`와 사유 | 8-2 예외, 9-2 |
| 월이 연속되지 않으면 비교 안 함 (누락 월 건너뛰어 연결 금지) | 8-2 예외 |
| 금액 방향: `F1 - F0`의 부호 | 8-2 |
| 전체 분모 비중 방향: `F1×T0 - F0×T1`의 부호 (T0, T1 > 0일 때만) | 8-2 |
| 미상 제외 비중 방향: `F1×(T0-U0) - F0×(T1-U1)`의 부호 (두 분모 > 0일 때만) | 8-2 |
| 분모 ≤ 0 → 해당 방향 None | 8-1 |
| `opposite`: 양쪽 모두 up/down이고 서로 다를 때만 True, flat 포함 시 False, None 포함 시 None | 8-2 |
| 이전 F = 0 → 증감률 None, 금액 차이 방향은 유효 | 8-2 예외 |
| 비교 A와 B를 합쳐 점수를 만들지 않는다 | 8-2 |
| 반올림한 퍼센트로 방향을 판단하지 않는다 | 8-2 |
| 자료 범위·버전이 다른 레코드끼리 비교하지 않는다 | 8-2 |

#### `summary.py`

- `period_totals(record) -> PeriodTotals` : `ok` 월의 F·T·U를 **각각 합산한 뒤** 기간 비중 계산 (8-1장). 제외한 월 목록 포함
- `summarize_pairs(pairs) -> PairSummary` : 전체 구간 수, 비교 가능 구간 수, 비교 A 반대 방향 구간 수, 같은 방향 구간 수, 보류 구간 수
- 규칙·화면·문서가 "5개 구간 중 N개" 같은 문장을 만들 때 이 결과만 사용한다. 문장을 만들지는 않는다 (문장은 `review/`·`web/`)
- 반대 방향 구간만 골라 반환하는 함수는 만들지 않는다 (8-3장: 반대 방향 구간만 골라 보여주지 않음)

### 의존 관계

- 가져다 쓰는 곳: 표준 라이브러리만 (`json`, `dataclasses`, `fractions`)
- 이 폴더를 쓰는 곳: `review/`, `document/`, `web/`, `scripts/build_demo_evidence.py`
- 쓰면 안 되는 곳: `llm/` (카드 수치 차단), `web/`·FastAPI import 금지

### 테스트

| 테스트 파일 | 확인 내용 | 워크플로우 |
|---|---|---|
| `tests/test_evidence_loader.py` | 상태값 오류, reason 누락, F+U>T, 금액 소수·음수, no_data에 0, 월 누락 생략, schema_version 불일치, synthetic/real 혼합, 전국 자동 대체 없음 | 9-1, 9-2, 12장 "숫자·코드 오류", "미상 0 또는 관측 행 없음" |
| `tests/test_evidence_compare.py` | `tests/fixtures/evidence/` 시나리오 전부, 큰 금액 교차곱 정확성, 0.01%p 미만 변화의 방향 유지 | 8-5 전체, 12장 "분모 0·자료 없음", "비교 A/B", "이전 F=0·변화 없음·월 누락", "아주 작은 방향 차이" |
| `tests/test_evidence_summary.py` | 기간 합산 비중이 월 비중 평균이 아님, 보류 구간 수 | 8-1 |

12장의 "GENDER_CD=x와 AGE_CD=x가 섞임"은 원본 CSV 집계 단계 시험이라 데이터 담당(`../Analysis/`) 소관이다.
