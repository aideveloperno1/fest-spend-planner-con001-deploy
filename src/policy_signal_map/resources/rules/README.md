# `resources/rules/` — 검토 규칙의 문장 원본

> 최신화: 2026-09-17

## 이 폴더는 무엇인가

검토 규칙의 **이름, 담당자에게 보이는 질문 문장, 고를 수 있는 보완 방법, 보완 방법을 고르면 기획안에 들어갈 문장**을 한 파일에 모아 둔 곳입니다.
"언제 이 질문을 할지" 판단은 `review/` 코드가 하고, "무슨 말로 물을지"는 이 파일이 정합니다. 그래서 문장만 바꿀 때는 코드를 고치지 않습니다.
사람이 읽기 쉽게 풀어 쓴 설명서는 `docs/review_rules.md`이며, 두 파일은 항상 같은 내용이어야 합니다.

## 파일 목록

| 파일 | 하는 일 (쉬운 말) | 언제 보거나 고치나 |
|---|---|---|
| `business_packs.json` | **사업 유형별로 켜지는 질문 번호 목록.** 문구가 아니라 번호만 적는다. 여기 적은 번호는 `review_rules.json`에 있어야 하며, 없으면 서버가 시작할 때 멈춘다 | 유형에 질문을 더하거나 뺄 때 |
| `review_rules.json` | **규칙 문장 원본.** 질문, 왜 묻는지, 보완 방법, 기획안에 들어갈 문장, 원안의 어느 칸이 바뀌면 다시 확인할지, AI에게 줄 숫자 없는 상황 설명 | 질문·보완 방법 문장을 바꿀 때 (고친 뒤 `docs/review_rules.md`도 함께, 서버 재시작) |
| `README.md` | 이 문서. 파일 구조와 고칠 때 지킬 것 | 파일 구조가 바뀔 때 |

---

## 자세한 설명 (개발자용)

### `review_rules.json` 구조

```
{
  "version": "1.0",
  "description": "...",
  "merge_groups": { "participation_data": "참여 실적 자료" },
  "rules": [
    {
      "id": "R07",
      "title": "금액·비중과 성과지표 확인",
      "scope": "implement" | "basic" | "example" | "future",
      "summary": "입력 화면 오른쪽 패널 한 줄 설명",
      "messages": {
        "question_direct": "...", "question_unknown": "...", "notice_reference": "...",
        "goal_mismatch_prefix": "... {goal_label} ... {metric_label} ...",
        "why_opposite": "... {period} ... {comparable_count} ... {opposite_count} ...",
        "why_same": "...", "held_no_record": "...", "held_blocked": "... {reason}",
        "held_needs_review": "... {reason}", "held_no_pairs": "..."
      },
      "options": [
        {
          "id": "A", "title": "참여 실적 추가", "where": "7. 성과 측정계획",
          "need": "쿠폰 발급·사용·정산 자료", "load": "중",
          "execution_fields": ["collect_items", "availability", "owner", "cycle"],
          "document": {
            "section": 7, "mode": "append",
            "lines": ["주요 지표: {collect_items}", "...", "수집 담당: {owner}", "확인 주기: {cycle}", "자료 확보 여부: {availability}"]
          }
        },
        { "id": "D", "...": "...", "document": { "section": 8, "mode": "append", "lines": ["..."], "appendix": "request" } }
      ],
      "related_fields": ["goals", "metrics", "indicator_use", "region"],
      "document_targets": ["..."],
      "merge_group": "participation_data",
      "llm_context": { "question_direct": "수치 없는 상황 설명", "why_opposite": "...", "...": "..." }
    }
  ]
}
```

| 필드 | 뜻 | 불러올 때 검사 (`review/rules.py`) |
|---|---|---|
| `version` | `"1.0"`만 허용 | 다르면 오류 |
| `merge_groups` | 묶음 키 → 화면·문서에 쓸 한글 이름 | 규칙의 `merge_group`에 이름이 없으면 오류 (내부 키가 문서에 실리지 않게) |
| `scope` | implement(검토 구현)·basic(기본 검토)·example(분석 예시)·future(향후 기능) | 목록 밖이면 오류. implement·basic인데 `engine.RUN_ORDER`에 실행 함수가 없으면 **앱 시작 실패** |
| `messages` | 화면 문장. `{이름}` 자리에 값을 채움. example·future는 `not_reviewed` 키 | 없는 키를 쓰면 실행 중 오류 |
| `options[].execution_fields` | 대안 A를 고르면 받는 입력(수집 자료는 필수) | — |
| `options[].document` | 대안을 채택했을 때 보완 기획안에 들어갈 문장. `section` 1~8, `mode` append(장 끝에 덧붙임)·replace(`replace_key` 줄을 바꿈), `appendix: "request"`면 요청서 초안 첨부 | 없거나 장 번호·방식이 틀리거나 replace인데 `replace_key`가 없으면 오류 |
| `lines` 자리표시자 | `{collect_items}{owner}{cycle}{availability}{usage_place}{target}{goals}{goals_without_store_usage}{metrics}` — 빈 값은 `[추가 확정 필요]` | — |
| `related_fields` | 이 입력이 바뀌면 선택을 "재확인 필요"로 (`plan/changes.py`의 항목 이름과 같아야 함) | — |
| `merge_group` | 같은 값의 질문끼리 **4단계 실행 조건 입력을 공유**. 3단계 카드는 합치지 않고 서로 가리킨다 | — |
| `llm_context` | `messages`와 같은 키로, AI 참고 의견에 넘길 **수치 없는 상황 설명** 한 줄. R06(`not_reviewed`)의 것은 정의만 있고 지금은 넘기지 않음 | 테스트가 숫자·`%`·`원`·`{`·판정 단어를 막음 |

- 실행 규칙은 `review/engine.py`의 `RUN_ORDER`와 같아야 한다. R06은 분석 예시로 남아 실행하지 않는다
- `why_opposite` 같은 문장에는 수치가 들어간다. **LLM에는 `messages`가 아니라 `llm_context`만 넘긴다** (`ReviewOutcome.context_keys` → `to_llm_summary`)

### 대안 문구 출처

- R07 대안 A~D: 최종기획서 4-4장, 시안 `OPTS`
- R07 문서 반영: 최종기획서 4-5장, 워크플로우 11장 "지표 정의·자료 수집·담당자·주기"
- R01·R03·R04·R05: 워크플로우 11장 표 (조건은 `docs/review_rules.md`에서 데이터 담당과 확정)

### 원칙

- 질문 문구에 "오류", "잘못", "실패" 같은 판정 단어를 쓰지 않는다
- 대안에 성공 확률·점수·추천 순위를 두지 않는다
- 옵션 D 문구에 계약·제공이 확정된 것처럼 읽히는 표현을 쓰지 않는다
- 한 번 읽어 보관하므로 고친 뒤 서버를 다시 시작한다
- 파일 수정 후 `uv run pytest`를 통과해야 한다 (규칙 ID·코드 일치, 판정 단어, `llm_context` 수치, 실행 중 나온 문구 키가 모두 상황 설명을 찾는지)
- 한글이 들어 있으므로 스크립트로 고칠 때는 Python(`ensure_ascii=False, indent=2`)을 쓴다. PowerShell `ConvertTo-Json`은 한글을 깨뜨렸다
- 고치면 `docs/review_rules.md`도 함께 고친다
