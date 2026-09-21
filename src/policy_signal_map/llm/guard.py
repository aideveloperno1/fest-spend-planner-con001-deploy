"""AI 출력 검사 (6LLM참고의견계획.md C-4).

검사에 걸린 의견은 화면에 보내지 않고 버린다. 고쳐 쓰지 않는다.
고쳐 쓰면 서비스가 AI 문장을 손본 셈이 되어 출처가 흐려진다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..review.rules import FORBIDDEN_WORDS

RULE_ID = re.compile(r"R\d{2}")
# 문장 끝·중간에 붙는 번호 표기: [R07], (R07, R05), [R07·R05]
RULE_CITATION = re.compile(r"[\[(]\s*R\d{2}(?:\s*[,·/]\s*R\d{2})*\s*[\])]")
# 규칙 번호를 뺀 뒤 남는 숫자·비율·금액 표기
NUMBER = re.compile(r"\d|[%％]")
# 수량을 나타내는 한글 표현. 수치를 글자로 바꿔 쓰는 것도 막는다
KOREAN_QUANTITY = (
    "한 개", "두 개", "세 개", "네 개", "다섯", "여섯", "일곱", "여덟", "아홉", "열 개",
    "절반", "대부분", "과반", "다수의", "몇 개", "여러 배", "두 배", "세 배",
)
# 새 지역 프로필의 순위·인구·거리값을 한글 숫자로 바꿔 쓰는 경우도 막는다.
# 한 글자 수사는 일반 문장과 겹치므로 단위를 함께 쓴 경우만 잡는다.
KOREAN_NUMBER_WITH_UNIT = re.compile(
    r"(?:한|두|세|네|다섯|여섯|일곱|여덟|아홉|열(?:한|두|세|네)?|수십|수백|수천|"
    r"[일이삼사오육칠팔구십백천만억]+)\s*(?:명|곳|개|원|건|배|번째|퍼센트|킬로미터)"
)
# 단정·판정 표현 (규칙 문구 금지어 + AI가 쓰기 쉬운 말)
JUDGMENT_WORDS = (*FORBIDDEN_WORDS, "틀렸", "옳습니다", "확실합니다", "보장", "반드시 해야")

MAX_LINES = 3


@dataclass(frozen=True)
class Opinion:
    text: str
    cited_rule_ids: tuple[str, ...]

    @property
    def display_text(self) -> str:
        """화면용 문장. 모델이 붙인 [R07] 같은 관리 번호 표기를 뺀다.

        번호는 카드 아래 근거 배지로 따로 보여 주므로 문장에 두 번 나올 필요가 없다.
        검사(check)는 원문 text로 하므로 규칙 번호 확인은 그대로 동작한다.
        """
        cleaned = RULE_CITATION.sub("", self.text)
        return re.sub(r"\s{2,}", " ", cleaned).strip(" ·,")


@dataclass(frozen=True)
class GuardResult:
    kept: tuple[Opinion, ...]
    dropped: tuple[tuple[str, str], ...]  # (버린 줄, 사유)

    @property
    def drop_reasons(self) -> tuple[str, ...]:
        return tuple(reason for _, reason in self.dropped)


def _lines(raw: str) -> list[str]:
    lines = []
    for line in raw.splitlines():
        text = line.strip().lstrip("-•*").strip()
        if text:
            lines.append(text)
    return lines


def _reason(line: str, available: set[str], not_reviewed: set[str]) -> str | None:
    cited = set(RULE_ID.findall(line))
    if not cited:
        return "근거 규칙 번호가 없음"
    # 검토하지 않은 규칙을 먼저 본다. 그 규칙은 결과에 없으므로 "없는 규칙"으로 잘못 알려지기 쉽다
    blocked = cited & not_reviewed
    if blocked:
        return f"검토하지 않은 규칙을 제안함: {', '.join(sorted(blocked))}"
    unknown = cited - available
    if unknown:
        return f"이번 검토에 없는 규칙을 인용함: {', '.join(sorted(unknown))}"
    if NUMBER.search(RULE_ID.sub("", line)):
        return "수치를 포함함"
    for word in KOREAN_QUANTITY:
        if word in line:
            return f"수량 표현을 포함함: {word}"
    if match := KOREAN_NUMBER_WITH_UNIT.search(line):
        return f"수량 표현을 포함함: {match.group(0)}"
    for word in JUDGMENT_WORDS:
        if word in line:
            return f"단정 표현을 포함함: {word}"
    return None


def check(raw: str, available_rule_ids: set[str], not_reviewed_rule_ids: set[str]) -> GuardResult:
    kept: list[Opinion] = []
    dropped: list[tuple[str, str]] = []
    for line in _lines(raw)[:MAX_LINES]:
        reason = _reason(line, available_rule_ids, not_reviewed_rule_ids)
        if reason:
            dropped.append((line, reason))
        else:
            kept.append(Opinion(text=line, cited_rule_ids=tuple(sorted(set(RULE_ID.findall(line))))))
    return GuardResult(kept=tuple(kept), dropped=tuple(dropped))
