# `tests/fixtures/evidence/` — 근거 파일 경계 사례 28개

> 최신화: 2026-09-20

## 이 폴더는 무엇인가

근거 파일을 읽고 계산하는 코드가 **까다로운 상황을 모두 올바르게 처리하는지** 확인하려고 만든 가짜(합성) 근거 파일 25개입니다.
정상적으로 읽혀야 하는 파일 15개, 읽히지만 경고가 남는 파일 1개, 일부러 틀리게 만들어 **오류로 거부돼야 하는** 파일 12개가 있습니다. 모든 수치는 가상 규모입니다.
**손으로 고치지 않고** `scripts/build_fixtures.py`로 다시 만듭니다.

## 파일 목록

**정상적으로 읽혀야 하는 파일**

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `profiles_ok.json` | **형식 2.1** — 전국·시도 지역 프로필과 운영 기준이 들어 있는 정상 파일 | 직접 고치지 않음 — 프로필 형식을 바꿨을 때 |
| `profiles_one_broken.json` | **형식 2.1** — 프로필 한 곳이 고장 난 파일. 파일은 읽히고 그 지역만 빠져야 함(경고 남음) | 직접 고치지 않음 — 프로필이 고장 났을 때의 처리를 바꿨을 때 |
| `profiles_version_mismatch.json` | 형식은 2.0인데 프로필이 들어 있는 파일. **조용히 무시하지 않고 거부**해야 함 | 직접 고치지 않음 — 버전 문을 바꿨을 때 |
| `amount_up_share_down.json` | 외국인 결제금액은 늘었는데 비중은 줄어든 경우 | 직접 고치지 않음 — 비교 계산을 바꿨을 때 기대 결과 확인 |
| `amount_down_share_up.json` | 외국인 결제금액은 줄었는데 비중은 늘어난 경우 | 직접 고치지 않음 — 비교 계산을 바꿨을 때 기대 결과 확인 |
| `same_direction.json` | 금액과 비중이 같은 방향으로 움직인 경우 | 직접 고치지 않음 — 비교 계산을 바꿨을 때 기대 결과 확인 |
| `flat_change.json` | 금액이나 비중이 전혀 변하지 않은 달이 있는 경우 | 직접 고치지 않음 — 비교 계산을 바꿨을 때 기대 결과 확인 |
| `prev_foreign_zero.json` | 이전 달 외국인 결제금액이 0이라 증감률을 낼 수 없는 경우 | 직접 고치지 않음 — 비교 계산을 바꿨을 때 기대 결과 확인 |
| `missing_month.json` | 중간 달 자료가 없는 경우 (그 달을 건너뛰어 잇지 않는지) | 직접 고치지 않음 — 비교 계산을 바꿨을 때 기대 결과 확인 |
| `tiny_change.json` | 비중 변화가 아주 작은 경우 (방향은 유지, 표시는 "0.01%p 미만") | 직접 고치지 않음 — 비교 계산을 바꿨을 때 기대 결과 확인 |
| `known_only_differs.json` | 미상을 포함할 때와 뺄 때 비중 방향이 다른 경우 | 직접 고치지 않음 — 비교 계산을 바꿨을 때 기대 결과 확인 |
| `large_amounts.json` | 금액이 매우 커서 소수 계산이 틀어질 수 있는 경우 | 직접 고치지 않음 — 비교 계산을 바꿨을 때 기대 결과 확인 |
| `unknown_equals_total.json` | 미상 금액이 전체와 같아 미상 제외 비중을 낼 수 없는 경우 | 직접 고치지 않음 — 비교 계산을 바꿨을 때 기대 결과 확인 |
| `denominator_zero.json` | 전체 금액이 0이라 계산할 수 없다고 표시된 달이 있는 경우 | 직접 고치지 않음 — 비교 계산을 바꿨을 때 기대 결과 확인 |
| `sido_allowed.json` | 쓸 수 있는 지역(시도) 자료가 두 곳 들어 있는 경우 | 직접 고치지 않음 — 지역 선택 동작을 바꿨을 때 기대 결과 확인 |
| `sido_blocked.json` | 한 지역은 쓸 수 없고, 다른 지역은 더 확인이 필요한 경우 | 직접 고치지 않음 — 되돌림·요약 보류 동작 확인 |
| `sido_sparse.json` | 지역 자료의 계산 가능한 달이 너무 적은 경우 | 직접 고치지 않음 — 표본 부족 화면 확인 |

**오류로 거부돼야 하는 파일**

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `invalid_status_value.json` | 달 상태에 약속에 없는 값이 들어간 파일 | 직접 고치지 않음 — 파일 검사 규칙을 바꿨을 때 기대 오류 확인 |
| `invalid_applicability.json` | 규칙 적용 상태에 약속에 없는 값이 들어간 파일 | 직접 고치지 않음 — 파일 검사 규칙을 바꿨을 때 기대 오류 확인 |
| `missing_reason.json` | 적용 상태의 사유가 비어 있는 파일 | 직접 고치지 않음 — 파일 검사 규칙을 바꿨을 때 기대 오류 확인 |
| `relation_broken.json` | 외국인+미상 금액이 전체보다 큰 파일 | 직접 고치지 않음 — 파일 검사 규칙을 바꿨을 때 기대 오류 확인 |
| `negative_amount.json` | 금액이 음수인 파일 | 직접 고치지 않음 — 파일 검사 규칙을 바꿨을 때 기대 오류 확인 |
| `decimal_amount.json` | 원 단위 금액에 소수가 들어간 파일 | 직접 고치지 않음 — 파일 검사 규칙을 바꿨을 때 기대 오류 확인 |
| `no_data_with_zero.json` | 자료 없는 달의 금액을 null 대신 0으로 적은 파일 | 직접 고치지 않음 — 파일 검사 규칙을 바꿨을 때 기대 오류 확인 |
| `month_omitted.json` | 기간 안의 달 하나를 통째로 빠뜨린 파일 | 직접 고치지 않음 — 파일 검사 규칙을 바꿨을 때 기대 오류 확인 |
| `schema_version_unsupported.json` | 지원하지 않는 형식 버전의 파일 | 직접 고치지 않음 — 파일 검사 규칙을 바꿨을 때 기대 오류 확인 |
| `mixed_data_kind.json` | 합성 자료와 실제 자료 표시가 섞인 파일 (수치는 모두 가짜) | 직접 고치지 않음 — 파일 검사 규칙을 바꿨을 때 기대 오류 확인 |
| `national_region_key_wrong.json` | 전국 자료인데 지역 키가 잘못된 파일 | 직접 고치지 않음 — 파일 검사 규칙을 바꿨을 때 기대 오류 확인 |
| `README.md` | 이 문서. 사례별 기대 결과 | 사례를 추가할 때 |

---

## 자세한 설명 (개발자용)

### 역할 요약

`evidence/` 로더·비교 계산과 2단계 지역 선택이 기획 문서의 모든 예외를 올바르게 처리하는지 확인하는 합성 JSON 25개.
각 파일은 워크플로우 9-3장 형식을 따르고, 확인할 상황만 담도록 2~3개월(지역 사례는 6개월)로 작게 만든다.

### 만드는 방법

**손으로 고치지 않는다.** `scripts/build_fixtures.py`로 생성해 커밋한다.

```powershell
uv run python scripts/build_fixtures.py
```

- 비중은 정수 금액에서 계산해 넣는다 (`scripts/_evidence_builder.py`)
- 스크립트는 월 수치로 직접 만드는 10개, 지역 사례 3개, 정상 사례 `amount_up_share_down`을 만든 뒤 **한 곳만 바꾸는** 12개로 나뉜다. 한 곳만 바꾼 12개 중 `denominator_zero`만 로드에 성공하고 나머지 11개는 오류 문구 정확히 1개를 확인한다. 아래 표는 **로드 결과** 기준으로 나눴다
- `tests/test_evidence_loader.py::test_fixtures_match_generator`가 스크립트 결과와 커밋된 파일이 같은지 검사한다. 스크립트만 고치고 재생성을 잊으면 테스트가 실패한다
- 레코드 ID는 `FX-01`, 지역 사례의 시도 레코드만 `FX-SIDO-…`. `dataset_version: fixture-{파일이름}`
- 지역 사례의 `region_key`는 **행정표준코드 10자리**다 (서울 `1100000000`, 강원 `5100000000`). 화면에는 지역 이름으로 나온다
- 사례별 월 수치와 기대 결과(방향·비교 A/B·증감률)는 [1근거계산계층계획.md 6장](../../../1근거계산계층계획.md#6-1-2-경계-사례-22개)

### 정상 파일 14개 — 로드 성공

| 파일 | 상황 | 기대 결과 |
|---|---|---|
| `amount_up_share_down.json` | 외국인 금액 증가, 전체 금액이 더 빠르게 증가 | 비교 A 반대 (금액 up, 비중 down) |
| `amount_down_share_up.json` | 외국인 금액 감소, 전체 금액이 더 빠르게 감소 | 비교 A 반대 (금액 down, 비중 up) |
| `same_direction.json` | 외국인 금액·비중 모두 증가 | 반대 아님 |
| `flat_change.json` | 01→02 금액 변화 0, 02→03 비중 변화 0 | flat이 있으면 반대 아님 |
| `prev_foreign_zero.json` | 이전 달 외국인 금액 0 (관측 행 없음 경고) | 증감률 None, 금액 차이 +500 |
| `missing_month.json` | 02월 `no_data` (금액 null) | 01→02, 02→03 보류, 01→03을 잇지 않음 |
| `tiny_change.json` | 비중 변화 −0.0004%p | 방향 유지(비교 A 반대), 표시는 "0.01%p 미만" |
| `known_only_differs.json` | 전체 분모 비중 down, 미상 제외 비중 up | 비교 B만 반대 |
| `large_amounts.json` | 1,000조 원 규모 | 소수점 계산은 flat, 정수 교차곱은 up |
| `unknown_equals_total.json` | 02월 U = T (미상 제외 분모 0) | 미상 제외 비중 null, 비교 B 계산 불가 |
| `denominator_zero.json` | 02월 `invalid_denominator`, T = 0 | 로드 성공, 01→02 보류 |
| `sido_allowed.json` | 전국 + 서울·강원 시도 레코드(둘 다 `allowed`, 6개월) | 시도 선택 시 그 레코드 사용, 시군구는 "넓은 범위" 안내 |
| `sido_blocked.json` | 전국 + 서울 `blocked` + 강원 `needs_review` | 서울은 전국으로 되돌리고 사유 표시, 강원은 요약만 보류 |
| `sido_sparse.json` | 전국 + 강원 시도(6개월 중 계산 가능 3개월) | 차트·요약 없이 계산하지 못한 달만 표시 |

### 오류 파일 11개 — 로드 실패 (오류 문구 1개)

| 파일 | 바꾼 곳 | 기대 오류 |
|---|---|---|
| `invalid_status_value.json` | 02월 `calculation_status: "okay"` | 허용되지 않는 값 |
| `invalid_applicability.json` | R07 status `"maybe"` | 허용되지 않는 값 |
| `missing_reason.json` | R06 `reason: ""` | 사유(reason)가 비어 있습니다 |
| `relation_broken.json` | 02월 `unknown_amount` → F + U > T | 외국인+미상 금액이 전체 금액보다 큽니다 |
| `negative_amount.json` | 01월 외국인 금액 음수 | 0 이상이어야 합니다 (값 출력 안 함) |
| `decimal_amount.json` | 01월 외국인 금액 소수 | 원 단위 정수여야 합니다 (받은 형식: 소수) |
| `no_data_with_zero.json` | 02월 `no_data`, 비중·건수 null, **F·T·U만 0** | 자료 없음 월의 금액은 null이어야 합니다 |
| `month_omitted.json` | 기간 끝 03월, 03월 항목 없음 | 2026-03 월이 없습니다 |
| `schema_version_unsupported.json` | `schema_version: "1.0"` | 지원하지 않는 형식 버전, 데이터 담당 확인 안내 |
| `mixed_data_kind.json` | 두 번째 레코드 `data_kind: "real"` (수치는 가짜) | 합성 자료와 실제 자료가 섞여 있습니다 |
| `national_region_key_wrong.json` | 전국인데 `region_key: "11"` | 전국 범위의 region_key는 "ALL" |

### 원칙

- 모든 수치는 가상 규모다. 실제 카드 분석 수치를 쓰지 않는다
- `mixed_data_kind.json`의 `real` 레코드도 수치는 가짜이며 이름표만 real이다 → `scripts/check_public_bundle.py`는 이 파일 경로를 예외 목록에 명시해 허용한다
- JSON의 `_case` 필드에 사례 설명을 한 줄 남긴다 (로더는 `_`로 시작하는 최상위 필드를 무시)
- 새 사례를 추가하면 `build_fixtures.py`, `tests/evidence_helpers.py`의 목록, 이 README를 함께 고친다 (`test_every_fixture_file_is_covered_by_a_test`가 누락을 잡는다)
