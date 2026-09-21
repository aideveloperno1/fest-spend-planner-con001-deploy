# 근거 파일 스키마 2.1 안내 (개발자용)

## 1. 파일 구성

| 파일 | 공개 여부 | 설명 |
| --- | --- | --- |
| `review_evidence_demo_v2.1.json` | 공개 가능 | 합성 근거. 가상 시군구 12곳 + 전국(ALL). 공개 시연·테스트용 |
| `review_evidence_real_v2.1.json` | **비공개** | 실제 근거. 255개 시군구 + 전국. `private/`에만 두고 저장소에 올리지 않는다 |
| `region_code_map.csv` | 공개 가능 | BC 시도·시군구명 → 행정구역 코드 (255개 전부 대조) |
| `ext_population.csv` | 공개 가능 | 시군구별 주민등록 인구(2026-08-31), 연령 6구간 |
| `ext_registered_foreign.csv` | 공개 가능 | 시군구별 등록외국인(2026-01~06) |
| `09_make_evidence.py` | 공개 가능 | 두 근거 파일을 만드는 생성기(같은 함수로 만들어 구조가 동일) |
| `06b_region_map_csv.py`, `07_process_external.py` | 공개 가능 | 코드 매핑표·외부 데이터 가공 |

실제 근거 파일에는 BC카드 제공 데이터에서 나온 시군구별 값이 들어 있다. 공모전 규정상 재배포가 안 되므로 공개 저장소, 공개 배포, 외부 AI 도구에 올리지 않는다.

## 2. 2.0에서 바뀐 점 (추가만 했다)

기존 키(`records`, `evidence_id`, `data_kind`, `scope`, `region_basis`, `applicability`, `amount_unit`, `months`, `limitations`)의 뜻은 그대로다. 새 키를 더했으니 모르는 키를 무시하는 코드는 그대로 동작한다. 확인이 필요한 변경은 세 가지다.

1. `region_basis` 값이 `merchant_location_assumed`(가맹점 소재지로 간주)로 들어간다. 2.0의 `unknown`일 때 R02를 막는 로직이 있다면 이 값은 막지 않도록 바꿔야 한다.
2. `applicability`에 R08, R09, R11, R12가 더해졌다. 시군구 기록은 R02·R03·R04·R07·R08·R09·R11·R12는 `allowed`, R06은 `blocked`이다. R11은 외부 인구 자료가 없으면 `blocked`이다.
3. `months[]`에 `season_index`, `season_flag`가 더해졌다. 월별 필드 이름(`foreign_amount`, `total_amount`, `unknown_amount`, `transaction_count`, `foreign_share_pct`, `known_only_share_pct`, `unknown_share_pct`, `calculation_status`, `warnings`)은 2.0과 같다.

## 3. 파일 구조

```
schema_version, dataset_version, data_kind, amount_unit, period
age_note, display_policy   연령 코드 1 해석 메모, 규칙별 표시 수준(R08 = reference)
external_sources   외부 자료 출처·기준일, 인구감소지역 재지정 상태
industry_codes      업종코드 → 업종명 (11개)
age_labels          연령 코드 1~6 → 표기
thresholds          운영 임계값 + derived_cutoffs(이 자료에서 계산된 컷오프 값)
national_distribution  지표별 255개 시군구 분포(p10, p20, p30, p50, p70, p80, p90)
records[]           시군구별 기록 + 마지막에 전국(ALL) 기록
```

시군구 기록 한 건:

| 키 | 내용 |
| --- | --- |
| `evidence_id`, `data_kind`, `scope`, `region_basis`, `amount_unit` | 2.0과 같음 |
| `region_codes` | `admin_2026_08`(2026-08 행정기관코드), `pre_2026`(BC 기간 코드), `match_type` |
| `applicability` | 규칙별 `status`와 `reason` |
| `months[]` | 월별 F·T·U·C, 비중 3종, `season_index`, `season_flag` |
| `profile` | 총 결제금액, 거래건수, 업종 비중 11개, 연령 비중 6개(미상 제외), 미상 비중, 업종별 연령 구성비 |
| `foreign_profile` | 외국인 결제 합, 생활유통 비중, 일반한식 비중, 업종 구성, 연령 구성, 월 변동계수, `type`, `type_status` |
| `season_summary` | 적용한 임계값과 발동 월 목록 |
| `national_rank` | 지표별 값·백분위·순위(255개 시군구 기준) |
| `size_flag` | 소액 지역 여부, 미상 비중과 그 백분위 |
| `derived_flags` | 결제 없음 업종, 하위 20% 업종, 하위 20% 업종×연령 쌍, 외국인 비중 낮음, R03 유형, 발동 월 |
| `peers` | 유사 지자체 5곳(`region_key`, `distance`) |
| `external` | 주민등록 인구(연령 6구간), 등록외국인 월별, 인구감소지역 여부, 인구 대비 결제액. 없으면 `null` |
| `limitations` | 화면에 함께 보여 줄 한계 문구 |

비중은 퍼센트 값 그대로(0~100)이고 금액은 원 단위 정수이다. 연령 코드는 `"1"`~`"6"` 문자열이다.

## 4. 규칙이 근거 파일을 읽는 방법

| 규칙 | 읽는 곳 | 켜지는 조건 |
| --- | --- | --- |
| R02 | `derived_flags.no_payment_industries`, `low_share_industries` | 담당자가 고른 사용처 업종이 둘 중 하나에 있을 때 |
| R03 | `foreign_profile.type`, `type_status` | 입력 조건(방문객 대상 + 외국인 카드 지표)일 때 질문. 유형 이름은 근거 카드에 표시 |
| R04 시기 | `months[].season_flag` | 사업 시기 월 중 하나라도 `true`일 때. 2026-01~06 밖이면 적용하지 않음 |
| R07 | `months[]`의 F·T·U | 입력 조건(성과지표가 외국인 결제비중·금액)일 때 |
| R08 | `derived_flags.low_industry_age_pairs`(`"업종\|연령코드"`) | 담당자가 고른 업종과 대상 연령 쌍이 있을 때. `applicability.R08.display_level`이 `reference`이므로 확정 판정이 아니라 **참고용**으로 표시한다 |
| R09 | `profile`, `peers`, `size_flag`, `external` | 시군구를 고르면 항상 |
| R11 | `external.population_total` | 입력한 목표 방문객 ÷ 인구 ≥ `thresholds.R11_visitor_to_resident_ratio` |
| R12 | `derived_flags.foreign_share_low`, `foreign_profile.type_status` | 대상에 외국인 관광객이 있고, 낮음이 `true`이거나 `type_status`가 `not_shown_small_foreign_amount`일 때 |
| R01, R04 기간, R05, R10 | 근거 파일 안 씀 | 입력 표현·항목만 본다 |

R02는 업종별 컷오프(`thresholds.derived_cutoffs.R02_low_industry_share_pct_max`)로 이미 계산해 두었다. 화면에서 다시 계산하려면 `value <= cutoff`(같은 값 포함)로 맞춘다.

## 5. 임계값

`thresholds` 안의 값은 통계적 임계값이 아니라 질문을 띄울 지점을 정한 운영 기준이다. 값은 데이터 분포와 재현성으로 점검해 정했고, 근거는 `임계값_결정표_v2.1.md`에 있다.

| 키 | 값 | 뜻 |
| --- | --- | --- |
| `R02_R08_low_percentile` | 20 | 업종(업종×연령) 비중이 255개 시군구 분포의 하위 20% 이하 |
| `small_size_percentile` | 20 | 6개월 총결제 하위 20% = 소액 지역(화면 문구용) |
| `R03_min_foreign_amount_percentile` | 50 | 외국인 결제 규모 상위 50%만 R03 유형 표시 |
| `R03_type_top_percentile` | 30 | 생활유통·일반한식 비중 상위 30% |
| `R04_season_index_min` | 1.10 | 결제 규모 하위 30% 초과 지역의 시기 지수 기준 |
| `R04_season_index_min_small` | 1.15 | 하위 10% 초과~30% 이하 지역 |
| `R04_season_index_min_very_small` | 1.30 | 하위 10% 이하 지역 |
| `R12_low_foreign_share_percentile` | 20 | 외국인 결제 비중 하위 20% 이하 |
| `R11_visitor_to_resident_ratio` | 1.0 | 목표 방문객 ÷ 주민등록 인구 |

R04는 지역마다 기준이 다르다. 화면에서 다시 계산하지 말고 각 시군구의 `season_summary.threshold`와 `months[].season_flag`를 그대로 쓴다. 값을 바꾸면 근거 파일을 다시 만들어야 한다(`derived_flags`, `season_flag`가 값에 따라 다시 계산된다).

## 5-1. 파일 버전

- `real-002` / `demo-2.1-002`: R04 시기 기준을 규모별 3단계(1.10·1.15·1.30)로 바꿨다. `real-001`에서는 하위 20%가 1.25, 나머지가 1.10이었다. 이 변화로 `season_flag`와 `season_summary.threshold`가 바뀌었고 `thresholds`에 키 3개(`R04_season_index_min_very_small`, `R04_small_percentile`, `R04_very_small_percentile`)와 `derived_cutoffs`에 키 2개(`R04_small_total_amount_max`, `R04_very_small_total_amount_max`)가 늘었다. 나머지 구조는 같다.
- `real-003` / `demo-2.1-003`: (1) R08을 참고용으로 표시하도록 `applicability.R08.display_level = "reference"`와 최상위 `display_policy`를 추가했다. 이유는 업종×연령 기준의 반기 재현성이 0.75로 R02(0.81)보다 낮기 때문이다. 화면에서는 R08 질문을 "확정"이 아니라 "참고"로 보여 준다. (2) 최상위 `external_sources`를 추가해 외부 자료 출처와 기준일, 인구감소지역 재지정 상태(`pending_redesignation`)를 적었다. (3) `age_note`에 데이터 담당 확인(2026-09-20)을 적었다. (4) `region_code_map.csv`의 인천 중구·동구·서구 `note`에 옛 구 인구 대조 결과를 적었다. 시군구 값과 R04 기준은 `real-002`와 같다.
- 이전 버전을 받았다면 `real-003`으로 교체한다.

## 5-2. 인구감소지역 표시

`external.depopulation_area_2021`은 2021년 지정 89곳 기준이다. 2026-06-30 보도에 따르면 행정안전부가 지표를 개편해 2026년 10월부터 새로 지정할 계획이고 결과는 아직 나오지 않았다. 화면에서는 "2021년 지정 기준"이라고 쓴다. 발표 후 `region_code_map.csv`의 `depop_2021` 열을 고치고 `09_make_evidence.py`를 다시 실행하면 갱신된다.

## 6. 개발 쪽 검증 방법 (자세한 단계는 `검증_절차_가이드.md`)

1. **구조:** 합성 파일과 실제 파일의 시군구 기록이 같은 키를 가진다. 합성 파일로 스키마 검증 테스트를 만든다.
2. **규칙 테스트(합성 파일):** 아래 시나리오가 기대대로 켜지고 꺼지는지 본다.

| 합성 시군구 | 확인할 것 |
| --- | --- |
| DEMO-SGG-A | 기본 구성(대도시 구). 프로필·유사 지자체 표시 |
| DEMO-SGG-B | 소액 지역 문구, 대형할인점 결제 없음(R02), 3월 `no_data` 표시 |
| DEMO-SGG-C, D, E | R03 유형 이름이 생활유통형, 한식외식형, 복합형 순으로 표시 |
| DEMO-SGG-F | R12 켜짐(외국인 결제 비중 낮음) |
| DEMO-SGG-G | 2월이 사업 시기이면 R04 시기 켜짐, 다른 달이면 꺼짐 |
| DEMO-SGG-H | 미상 비중이 큰 지역의 두 비중(전체·미상 제외) 함께 표시(R07) |
| DEMO-SGG-I | 외국인 결제 규모가 작아 R03 유형 미표시, R12 켜짐 |
| DEMO-SGG-J | 인구감소지역 라벨, 한식 비중 상위 |
| DEMO-SGG-K | 대상 연령 60대 이상 + 사용처 업종이면 R08 검토(참고용 표시) |
| DEMO-SGG-L | 외부 자료 없음 → R11 꺼짐, `external`이 `null`일 때 화면이 깨지지 않음 |

3. **화면 수치 대조(실제 파일):** 시군구 3곳 이상(규모가 크게 다른 두 곳과 미상 비중이 큰 한 곳)을 골라 화면에 표시된 값이 근거 파일의 값과 같은지 본다. 이 대조는 개발 쪽이 하고, 근거 파일이 원본과 맞는지는 데이터 담당이 따로 검증한다.
4. **보안:** 실제 파일이 저장소 변경분에 포함되지 않는지(`.gitignore`, `private/`) 매번 확인한다.

## 7. 다시 만드는 방법

```
python 09_make_evidence.py synthetic   # 합성 근거(공개 가능)
python 09_make_evidence.py real        # 실제 근거(BC 원본 필요, 비공개)
```
