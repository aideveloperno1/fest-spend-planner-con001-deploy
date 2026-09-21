# `review/` — 검토 규칙을 실행해 질문 만들기

> 최신화: 2026-09-18

## 이 폴더는 무엇인가

3단계 **검토 질문** 화면에 나올 내용을 만드는 곳입니다. 담당자가 입력한 기획안과 데이터 담당의 근거를 보고, 규칙(R01~R07)마다 **담당자에게 물어볼 질문, 그 이유, 고를 수 있는 보완 방법**을 정합니다.
서비스는 판정하거나 점수를 매기지 않습니다. 관측한 내용은 질문으로 전달하고, 결정은 4단계에서 담당자가 합니다.
질문 문장과 보완 방법의 글은 `resources/rules/` 파일에 있고, 이 폴더는 **언제 어떤 문장을 쓸지 판단**만 합니다.

## 파일 목록

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `__init__.py` | 이 폴더를 파이썬 묶음으로 인식시키는 빈 파일 | 고칠 일 없음 |
| `rules.py` | **규칙 문구 파일을 읽고 검사.** 질문 문장, 보완 방법, 문서에 들어갈 문장, AI에게 줄 상황 설명을 꺼내 줌. 판정 단어(문제·오류 등)를 쓰지 않았는지도 확인 | 규칙 문구 파일의 형식을 바꿀 때 |
| `packs.py` | **사업 유형별로 켜지는 질문 목록.** 공통 질문은 항상 켜고, 유형을 고르지 않은 기획은 아무 질문도 숨기지 않음 | 유형에 질문을 더하거나 뺄 때 |
| `industry_checks.py` | **사용처 업종 확인(R02)과 대상·고객 구성(R08).** 고른 업종 자체 또는 그 업종 안의 대상 연령이 전국 운영 기준 이하인지 물음. 기준값은 근거 파일에서 받음 | 업종·대상 연령 확인 조건을 바꿀 때 |
| `season_checks.py` | **사업 시기 확인(R04 시기)과 외국인 대상 기반 확인(R12).** 사업 기간에 든 달 가운데 결제가 평소보다 컸던 달, 외국인 결제 기반이 낮은 편인 경우를 물음 | 시기·외국인 기반 조건을 바꿀 때 |
| `capacity_checks.py` | **규모와 수용 여건 확인(R11).** 목표 방문객/주민등록인구 비율이 근거 파일의 기준 이상일 때 수용 여건 확인 자료를 물음. 두 집단이 다름을 함께 밝힘 | 목표 규모·외부 인구 조건을 바꿀 때 |
| `metric_checks.py` | **성과지표와 자료 범위 확인(R10).** 고른 성과지표 가운데 카드 자료로 산출되지 않는 것(방문객·참여자·고객 수)이 있으면 어떤 자료로 확인할지 물음 | 지표 점검 조건을 바꿀 때 |
| `outcome.py` | **검토 결과의 모양**을 정함: 질문 / 참고 안내 / 추가 확정 필요 / 자료 부족으로 보류, 그리고 "확인했으나 해당 없음"과 "검토하지 않음"의 구분. AI에게 넘길 수치 없는 요약도 만듦 | 결과에 새 정보를 담아야 할 때 |
| `context.py` | 어떤 근거(지금은 전국)를 쓸지 고르고, "전국 참고 — 특정 지역의 진단이 아님" 같은 **범위 안내 문구**를 붙임. 2단계 화면도 함께 씀 | 지역별 근거를 쓰기 시작할 때 |
| `r07_indicator.py` | 핵심 규칙 **R07(금액·비중과 성과지표 확인)** 판단. 근거가 부족하면 보류, 지표를 참고로만 쓰면 안내, 직접 평가에 쓰면 질문 | R07 조건을 바꿀 때 |
| `basic_checks.py` | 입력 내용만으로 판단하는 **기본 규칙 R01·R03·R04·R05** (사용처, 대상과 자료, 기간, 빠진 운영 조건) | 기본 규칙 조건을 바꿀 때 |
| `engine.py` | 규칙을 **정해진 순서로 실행**하고, 같은 정보를 묻는 질문끼리 서로 가리키게 연결. 규칙 파일과 코드가 어긋나면 앱이 켜지지 않게 막음 | 규칙을 추가하거나 실행 순서를 바꿀 때 |

---

## 자세한 설명 (개발자용)

### 기준 문서

- 워크플로우 11장 검토 규칙과 문서 반영, S02 조회와 질문
- 최종기획서 4-3 서비스가 묻는 질문, 4-4 선택할 보완 방법, 5장 추가 사례, 11장 구현 범위
- checks.md: R07 검토 구현, R01·R02·R03·R04·R05·R08·R10·R11·R12 기본 검토, R06 분석 예시

### 파일별 상세

#### `rules.py`

- `load_rule_catalog()` → `RuleInfo(id, title, scope, summary, messages, options, related_fields, document_targets, merge_group, llm_context, questions)`, `rules_by_id()`, `get_rule(id)`
- `questions`: 한 규칙이 질문을 둘 이상 낼 때만 채운다. `QuestionSpec(name, related_fields)`이며 `rule.related_fields_for(질문이름)`으로 꺼낸다. 규칙에 없는 이름을 주면 바로 알린다 (7지역확장계획.md 5장)
- `OptionSpec(id, title, where, need, load, execution_fields, document)`, `OptionDocument(section, mode, lines, replace_key, appendix)`
- `RuleInfo.message(key, **values)`: 문구에 값 채움. `RuleInfo.context(key)`: 수치 없는 상황 설명
- `merge_group_label(key)`: 묶음 키의 한글 이름 (`merge_groups`)
- 불러올 때 검사 항목은 `resources/rules/README.md` 표 참고
- `FORBIDDEN_WORDS`: 문구에 쓰지 않는 판정 단어 (테스트가 `messages`·`llm_context` 전체를 검사)
- **문구·대안·문서 반영 위치는 JSON이 원본**, **조건 판단은 코드**(규칙 ID별 함수)가 맡는다
- 시작 시 검사: `engine.py`를 불러올 때 `check_rule_functions()`가 한 번 실행된다. `scope`가 implement/basic인데 실행 함수가 없으면 **앱이 시작하지 않는다** (화면을 여는 순간 500이 나지 않게). 요청 처리 중에는 다시 검사하지 않는다

#### `outcome.py`

```
ReviewOutcome
  rule_id: str
  question_key: str               4단계 선택이 참조. 규칙 하나가 질문 하나면 규칙 ID,
                                  질문을 둘 이상 내면 `규칙ID-이름` (question_key_of)
  merge_group: str | None         같은 값끼리 4단계에서 추가 입력을 공유
  kind: "question" | "notice" | "pending" | "held"
      question      담당자 선택이 필요한 질문 (4단계에서 필수)
      notice        오류 없이 해석 조건만 안내 (예: 참고용 지표). 선택은 가능하지만 필수 아님
      pending       추가 확정 필요 항목 (R05). 선택 없이 문서 8장에 기록
      held          근거 부족으로 결론 보류 (레코드 없음, blocked, needs_review, 비교 구간 없음). 선택 없이 문서 8장에 기록
  title: str
  message: str                    화면에 나갈 문장 (JSON 문구 + 값 채움)
  why: str | None                 "왜 묻나요?" 설명
  evidence_ids: list[str]
  scope_label: str | None         "전국 참고 — 특정 지역의 진단이 아님" 등
  region_note: str | None         시도·시군구 기획에 붙는 "전국 참고" 안내
  observations: dict              비교 요약 (구간 수 등). 문장 조립용, LLM에는 넘기지 않음
  options: tuple[OptionSpec]      choices/가 사용
  related_fields: tuple[str]      재확인 트리거 필드 (plan/changes.py 항목 이름과 같음)
  related_rule_ids: tuple[str]    같은 merge_group의 다른 질문 (카드는 합치지 않고 서로 가리킴)
  context_keys: tuple[str]        결과를 만들 때 고른 문구 키 → llm_context를 찾는 데 사용

ReviewResult(outcomes, no_finding, not_reviewed, evidence_id)
  no_finding     조건을 확인했으나 물을 것이 없는 규칙 ("문제없음")
  not_reviewed   NotReviewed(rule_id, title, scope_label, reason) — 이번 범위에서 검토하지 않음 (R06 분석 예시)
```

- `evidence_ids`는 소비데이터를 쓰는 R07 결과에만 붙는다. R01·R03·R04·R05는 입력 항목만으로 판단하므로 비어 있다
- `llm/`에 넘길 때는 `to_llm_summary()`로 수치 없는 요약만 만든다: 규칙 ID, kind, 제목, 근거 유무, 적용 범위 라벨, 관련 규칙, `context`(`context_keys`로 찾은 `llm_context` 문장)

#### `r07_indicator.py`

최종기획서 4장 첫 사례의 핵심 규칙.

실행 판단 순서
1. 성과지표에 외국인 결제 비중 또는 금액이 없음 → R07 대상 아님 (`not_reviewed` 아님, 결과 없음)
2. 근거 레코드 없음 → `held` (`held_no_record`). 레코드는 `context.select_main(file, plan)`이 **사다리**로 고른다: **시군구 → 시도 → 전국** 순으로 쓸 수 있는 가장 좁은 범위를 쓰고, 못 쓰면(없음·`blocked`·표본 부족) 한 칸 넓힌 뒤 **넓힌 이유를 `region_note`로 밝힌다** (워크플로우 8-4). 연결 키는 행정표준코드 10자리(C-1)
3. `applicability.R07.status`
   - `blocked` → `held`, 사유 표시 (2단계 화면은 수치를 모두 숨김)
   - `needs_review` → `held`, 확인할 내용 표시
4. 비교 가능한 구간이 하나도 없음 → `held`
5. 반대 방향 구간이 1개 이상이면 "왜 묻나요?"에 `why_opposite`, 없으면 `why_same`
6. 지표 용도
   - `reference`(참고 현황) → `notice`: 직접 평가 오류로 표시하지 않고 해석 조건(분모·미상 처리·전국 참고)만 안내 (워크플로우 S02, 11장). 고를 수 있는 대안은 B(해석 조건 명시)뿐
   - `direct`(직접 평가) → `question`: 목표가 금액 확대인지 비중 확대인지, 참여 실적을 별도로 수집할 수 있는지 질문
   - `unknown`(아직 모름) → `question`: 결론 없이 선택지만 제시
7. 목표와 지표 불일치 (금액 확대 목표 + 비중 지표, 또는 반대) → 질문일 때 문구 앞에 `goal_mismatch_prefix`

문구 원칙
- 반대 방향 구간이 0개여도 검토 불필요라고 하지 않고, 반대 방향이 있어도 비중을 삭제하라고 하지 않는다 (8-3장)
- 방향이 같은 기간에 "방향이 달랐다" 예시 문구를 재사용하지 않는다 (12장)
- 작은 차이에 빨간 경고·"오류" 단어를 쓰지 않는다
- 지역 기획 + 전국 근거 → 반드시 "전국 참고" 표시. 시도 근거 + 시군구 기획 → "넓은 범위의 참고자료" (8-4장)
- 비교 B(미상 포함·제외)는 보조 근거로만 쓰고 비교 A와 합치지 않는다

대안 (JSON 원본, 최종기획서 4-4장)
- A 참여 실적 추가: 추가 입력 = 수집자료, 확보 여부, 담당자, 주기
- B 해석 조건 명시
- C 자료 확보 전 (추가 확정 필요로 기록)
- D 정밀 BC 분석 요청서 초안 (계약·제공 확정처럼 표시 금지)
- 공통: 원안 유지, 보류

#### `basic_checks.py`

조건은 초안이며 `docs/review_rules.md`에서 데이터 담당과 확정한다.

| 규칙 | 실행 조건 (초안) | 결과 |
|---|---|---|
| R01 목표와 사용처 | 목표에 참여 상점 이용 확대 포함 + 쿠폰 사용처가 **비어 있음** | `question`: 사용처 범위 확인 |
| R03 대상과 자료 | 대상 문구에 "관광객·방문객·여행객" 중 하나 포함 + 성과지표가 외국인 카드 지표(비중·금액) | `question`: 외국인 전체 자료로 관광객 성과를 볼 수 있는지 (최종기획서 5-2: 외국인 전체와 관광객 구분) |
| R04 기간 | 사업 기간(시작일~종료일 포함)이 **31일 미만** + 지표 용도가 직접 평가 + 성과지표가 외국인 카드 지표 | `question`: 별도 실적·집계 주기 |
| | ↳ `SHORT_PERIOD_DAYS = 31`은 월 단위 집계와 짧은 사업을 가르려고 **서비스가 정한 운영 기준**이며 카드 자료 분석에서 나온 통계 기준이 아니다 (데이터 담당 검수 2026-09-17). 화면 문구는 "한 달이 되지 않습니다"만 쓴다 | |
| R05 운영 조건 누락 | `plan.validation`의 pending 항목 존재 | `pending`: 추가 확정 필요 목록 |

- R06 → `not_reviewed` "분석 예시로 제시" (최종기획서 5-1)
- R02·R08 → 고른 지역의 프로필 값과 근거 파일의 운영 기준을 쓴다. 자료가 없으면 더 넓은 범위로 바꾸지 않고 `held`로 둔다
- 사용자가 입력하지 않은 사실을 추정해 지적하지 않는다

#### `engine.py`

- `run_review(plan, evidence) -> ReviewResult(outcomes, no_finding, not_reviewed, evidence_id)`
- 실행 순서: `RUN_ORDER = ("R07", "R10", "R02", "R08", "R03", "R12", "R11", "R04", "R01", "R05")` → R06은 `not_reviewed`로 표시
- 모듈을 불러올 때 `check_rule_functions()` 실행 (JSON의 implement·basic 규칙마다 실행 함수가 있는지)
- 중복 질문 묶기: 같은 `merge_group` 질문끼리 **카드는 합치지 않고** `related_rule_ids`로 서로 가리킨다. 실제 묶기는 4단계 실행 조건 입력 공유 (`3검토질문계획.md` 결정 ③·④)
- 결과에 "검토한 규칙 / 검토하지 않은 규칙"을 모두 담는다 (시안: '문제없음'과 '검토하지 않음' 구분)
- 같은 입력·같은 근거 파일이면 항상 같은 결과 (난수·시간 의존 금지)

### 의존 관계

- 가져다 쓰는 곳: `plan/`, `evidence/`, `resources/rules/`
- 이 폴더를 쓰는 곳: `choices/`, `document/`, `web/`, `llm/`(요약만)
- 쓰면 안 되는 것: `web/`, FastAPI

### 테스트

`tests/test_review_rules.py`

| 확인 | 워크플로우 12장 |
|---|---|
| 참고용 지표 → `notice`, 오류 문구 없음 | 참고용 지표 |
| 직접 평가 + 반대 방향 구간 존재 → `question` | — |
| 방향이 같은 기간만 있을 때 반대 방향 문구 없음 | 방향이 같은 두 기간 |
| 전국 근거 + 시군구 기획 → 전국 참고 표시 | 전국 자료 + 특정 지역 기획 |
| 시도 근거 + 시군구 기획 → 넓은 범위 표시, R02 비활성 | 검증 시도 자료 + 시군구 기획 |
| applicability blocked/needs_review → 실행 안 함/보류 | — |
| 자료 확보 미정 → R05 pending | 자료 수집 미정 |
| R03·R04·R07 같은 묶음 → 카드는 따로, 서로 `related_rule_ids`로 가리킴, 질문 키는 규칙 ID로 서로 다름 | — |
| JSON 규칙 ID와 코드 함수 일치 | — |
