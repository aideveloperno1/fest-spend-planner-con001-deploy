# `plan/` — 담당자가 입력하는 기획안

> 최신화: 2026-09-17

## 이 폴더는 무엇인가

1단계 **기획 입력** 화면에서 담당자가 적는 기획안(원안)을 다루는 곳입니다.
기획안에 어떤 칸이 있는지, 빠뜨린 칸이 없는지, 지역을 어디서 고르는지, 다시 제출했을 때 무엇이 바뀌었는지를 여기서 정합니다.
화면(웹)과는 따로 떨어진 계산 코드라서, 화면을 바꿔도 이 폴더는 그대로 쓸 수 있습니다.

## 파일 목록

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `__init__.py` | 이 폴더를 파이썬 묶음으로 인식시키는 빈 파일 | 고칠 일 없음 |
| `models.py` | **기획안에 어떤 칸이 있는지** 정해 둔 파일. 사업 목표·성과지표 같은 선택지 목록과, [예시 기획 채우기]를 누르면 들어가는 예시 기획도 여기 있음 | 입력 칸을 늘리거나, 선택지·예시 기획을 바꿀 때 |
| `validation.py` | 제출한 기획안에 **꼭 필요한 칸이 비었는지, 날짜·예산이 올바른지** 확인하는 파일. 비워도 되는 칸은 보완 기획안에 "추가 확정 필요"로 넘길 목록을 만듦 | 필수 칸이나 확인 규칙을 바꿀 때 |
| `regions.py` | 시도·시군구 **선택 목록**을 읽고, 고른 지역을 "강원특별자치도 강릉시"처럼 읽기 좋은 이름으로 바꾸는 파일 | 지역 목록을 새로 만들었거나 지역 표시 방식을 바꿀 때 |
| `changes.py` | 담당자가 기획안을 **고쳐 다시 제출했을 때 어떤 칸이 바뀌었는지** 찾는 파일. 바뀐 칸과 관련된 선택만 4단계에서 "다시 확인"으로 표시하는 데 씀 | 비교할 입력 칸이 늘어날 때 |

---

## 자세한 설명 (개발자용)

### 기준 문서

- 워크플로우 3장 "입력폼 최소 항목", S01(입력과 원안 보관)
- 최종기획서 3장 (첫 버전은 항목별 입력폼), 7장 (자료가 없으면 0으로 대체하지 않음)
- checks.md 입력폼 결정 (필수 7개, 목표·지표 복수 선택, 전국/시도/시군구, 예산 미정·0원 구분)

### `models.py`

- 선택지 열거형: `Goal`(금액 확대·비중 확대·참여 상점 이용 확대·기타), `BusinessType`(쿠폰·지역화폐 / 외국인·관광 / 축제·행사 / 연령 대상 사업 — 고르지 않으면 `None`), `Metric`(결제금액·결제건수·건당 결제금액·외국인 결제금액·외국인 결제 비중 / 방문객 수·참여자 수·고객 수 / 쿠폰 사용·정산 실적·기타), `IndicatorUse`(직접 평가·참고 현황·아직 모름), `DataStatus`(확보됨·협의 중·미정), `RegionLevel`(전국·시도·시군구), `BudgetStatus`(미입력·미정·금액)
- `CARD_DERIVABLE_METRICS`·`NON_CARD_METRICS`: 카드 자료로 산출할 수 있는 지표와 없는 지표. 3단계 지표 점검(R10)이 쓴다. 쿠폰 사용 실적과 기타는 데이터 담당 검수 전이라 어느 쪽에도 넣지 않았다
- `usage_industries`·`target_ages`: 사용처 업종과 대상 연령. **근거 파일이 알려 주는 코드**이며 서비스가 목록을 지어내지 않는다. 화면에 보여 줄 이름도 근거 파일에서 온다(`web/profile_view.py`의 `option_catalog`). 목록에 없는 코드는 `web/forms.py`가 버린다
- `visitor_goal`: 목표 방문객 수. `None`은 적지 않은 것이고 `0`은 0명이라고 적은 것이다. 숫자로 읽지 못한 입력은 `visitor_goal_raw`에 원문을 남긴다. 축제·행사에서는 외부 인구가 연결됐을 때 R11이 수용 여건 확인에 쓴다
- `Region`: 범위와 시도·시군구 코드
- `Budget`: 상태, 원 단위 정수 금액, 숫자로 읽지 못한 원문(`raw`)
- `PlanInput`: 입력 전체
- `sample_plan()`: 최종기획서 4-1장 첫 시험 기획. 지역은 공개 시연용 예시(강원 강릉시)
- 필드를 늘리면 `web/forms.py`, `web/templates/steps/input.html`, `validation.py`, `changes.py`, 테스트를 함께 고친다

### `validation.py`

- `validate_plan(plan) -> ValidationResult(errors, pending)`
- errors 키: `name, business_type, goals, goal_other, target, region, period, budget, metrics, indicator_use, visitor_goal`
- `business_type`은 필수다. 고르지 않은 기획을 서비스가 한 유형으로 분류하지 않는다
- `visitor_goal`은 선택이다. 빈칸은 넘어가고 숫자로 읽지 못한 값만 묻는다. 축제·행사에서 적지 않으면 '추가 확정 필요'로 남는다
- pending: 비어 있는 선택 항목 → 보완 기획안 "추가 확정 필요"로 넘어갈 이름 (`예산 (미입력)`, `예산 (미정)`, 쿠폰·지역화폐 유형의 `쿠폰 사용처`, `자료 확보 상태 (선택 안 함)`, `성과 자료 확보 (협의 중)`, `성과 자료 확보 (미정)`). 고른 값을 이름에 함께 넣는다 — 고르기 전과 고른 뒤가 같아 보이면 "선택했는데 왜 남지?"가 된다 (9/18). 변경 불가 조건은 비어도 pending에 넣지 않는다 (없을 수 있는 항목)
- 검증: 목록에 없는 지역 코드, 날짜 형식, 종료일 < 시작일, 예산 비정수, **금액과 [미정] 동시 입력**(금액을 조용히 버리지 않는다)
- 추정·보정하지 않는다. 예: 잘못된 예산 글자를 0으로 바꾸지 않는다

### `regions.py`

- `load_regions()`, `sido_list()`, `find_sido(code)`, `is_known_region(region)`, `region_label(region)`
- 자료: `resources/regions.json` (`scripts/build_regions.py`로 생성)
- 이 목록은 **입력 선택용**이다. 카드 근거의 지역 범위(`region_key`)와 같은 뜻이 아니다. 근거의 지역 적용 여부는 `evidence/`·`review/`가 판단한다

### `changes.py`

원안을 바꿔 다시 제출했을 때 이후 단계 선택 중 무엇을 다시 확인해야 하는지 계산한다 (워크플로우 S05, 11장).

- `diff_plan(before, after) -> frozenset[str]`: 바뀐 항목 이름. 첫 검토(원안 없음)면 빈 집합
- 비교 항목(`COMPARERS`): `name`, `business_type`, `goals`, `metrics`, `indicator_use`, `target`, `region`, `period`, `budget`, `usage_place`, `data_status`, `fixed_conditions`, `visitor_goal`
- 이름은 규칙 JSON의 `related_fields`와 같다. `choices/recheck.py`가 **바뀐 항목과 `related_fields`가 겹치는 규칙의 선택만** "재확인 필요"로 바꾼다. 겹치지 않는 변경(예: 사업명 수정)은 선택을 유지한다
- 재확인 표시는 원안을 제출할 때마다 **한 번만** 붙는다(`web/session.py`의 `sync_choices`, 6-5a). 다시 저장하면 풀린다
- `web/session.py`의 `review_restarted`는 바뀐 항목이 하나라도 있는지(`changed_fields`)로 판단한다

### 의존 관계

- 가져다 쓰는 곳: `paths.py`
- 이 폴더를 쓰는 곳: `review/`, `choices/`, `document/`, `web/`
- 쓰면 안 되는 것: `web/`, `evidence/`, FastAPI

### 테스트

- `tests/test_plan_validation.py`: 필수 7개, 예산 3상태 구분, 잘못된 예산, pending, 기타 설명, 목록 밖 선택값·지역, 기간 역전
- `tests/test_plan_changes.py`: 바뀐 항목만 반환, 첫 검토는 빈 집합
