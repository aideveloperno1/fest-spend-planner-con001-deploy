"""한 규칙이 질문을 둘 이상 낼 때 (7지역확장계획.md 5장).

지금 규칙은 모두 "규칙 하나 = 질문 하나"라 화면 동작은 달라지지 않는다.
여기서는 나눌 준비가 됐는지, 즉 ① 이름표가 섞이지 않는지 ② 한쪽만 바뀌었을 때
그 선택만 재확인 대상이 되는지를 고정한다.
"""

import pytest

from policy_signal_map.choices.models import Choice, ChoiceSet, Decision
from policy_signal_map.choices.recheck import mark_recheck
from policy_signal_map.choices.selection import apply_choice
from policy_signal_map.review.outcome import ReviewOutcome, question_key_of
from policy_signal_map.review.rules import QuestionSpec, RuleInfo


def rule(**values) -> RuleInfo:
    base = dict(
        id="R04",
        title="기간 확인",
        scope="basic",
        summary="",
        messages={},
        options=(),
        related_fields=("period", "indicator_use"),
        document_targets=(),
        merge_group=None,
    )
    return RuleInfo(**{**base, **values})


def outcome(question: str | None, related: tuple[str, ...]) -> ReviewOutcome:
    return ReviewOutcome(
        rule_id="R04",
        question_key=question_key_of("R04", question),
        merge_group=None,
        kind="question",
        title="기간 확인",
        message="확인할 점이 있습니다.",
        related_fields=related,
    )


def saved(choice_set: ChoiceSet, item: ReviewOutcome) -> None:
    errors = apply_choice(choice_set, item, {"decision": Decision.KEEP_ORIGINAL.value})
    assert not errors


# ---------------------------------------------------------------- 이름표


def test_질문이_하나면_이름표는_규칙_번호_그대로():
    assert question_key_of("R07") == "R07"


def test_질문이_둘이면_이름표가_서로_다르다():
    assert question_key_of("R04", "period") == "R04-period"
    assert question_key_of("R04", "season") == "R04-season"
    assert question_key_of("R04", "period") != question_key_of("R04", "season")


# ---------------------------------------------------------------- 관련 입력 항목


def test_질문_이름을_주지_않으면_규칙_값을_쓴다():
    assert rule().related_fields_for() == ("period", "indicator_use")


def test_질문마다_관련_항목을_따로_가진다():
    info = rule(
        questions={
            "period": QuestionSpec("period", ("period", "indicator_use")),
            "season": QuestionSpec("season", ("period", "region")),
        }
    )
    assert info.related_fields_for("period") == ("period", "indicator_use")
    assert info.related_fields_for("season") == ("period", "region")


def test_규칙에_없는_질문_이름은_바로_알린다():
    with pytest.raises(KeyError, match="R04"):
        rule().related_fields_for("없는질문")


# ---------------------------------------------------------------- 선택 저장


def test_같은_규칙의_두_질문_선택이_서로_덮어쓰지_않는다():
    choice_set = ChoiceSet()
    saved(choice_set, outcome("period", ("period",)))
    saved(choice_set, outcome("season", ("period", "region")))

    assert sorted(choice_set.choices) == ["R04-period", "R04-season"]
    assert {c.rule_id for c in choice_set.choices.values()} == {"R04"}


def test_선택은_질문의_관련_항목을_기억한다():
    choice_set = ChoiceSet()
    saved(choice_set, outcome("season", ("period", "region")))
    assert choice_set.choices["R04-season"].related_fields == ("period", "region")


# ---------------------------------------------------------------- 재확인


def test_한쪽_질문의_항목만_바뀌면_그_선택만_재확인된다():
    choice_set = ChoiceSet()
    saved(choice_set, outcome("period", ("period", "indicator_use")))
    saved(choice_set, outcome("season", ("region",)))

    marked = mark_recheck(choice_set, frozenset({"region"}))

    assert marked == ("R04-season",)
    assert choice_set.choices["R04-season"].needs_recheck is True
    assert choice_set.choices["R04-period"].needs_recheck is False


def test_두_질문에_함께_걸린_항목이_바뀌면_둘_다_재확인된다():
    choice_set = ChoiceSet()
    saved(choice_set, outcome("period", ("period", "indicator_use")))
    saved(choice_set, outcome("season", ("period", "region")))

    marked = mark_recheck(choice_set, frozenset({"period"}))

    assert sorted(marked) == ["R04-period", "R04-season"]


def test_관련_항목을_모르는_선택은_규칙_값으로_판단한다():
    """옛 방식으로 만든 선택도 그대로 동작해야 한다."""
    choice_set = ChoiceSet()
    choice_set.put(Choice(question_key="R07", rule_id="R07", decision=Decision.KEEP_ORIGINAL))

    assert mark_recheck(choice_set, frozenset({"metrics"})) == ("R07",)
    assert mark_recheck(choice_set, frozenset({"budget"})) == ()
