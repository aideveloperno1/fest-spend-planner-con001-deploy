"""AI 출력 검사 (6LLM참고의견계획.md C-4)."""

from policy_signal_map.llm.guard import MAX_LINES, check

AVAILABLE = {"R07", "R03", "R05"}
NOT_REVIEWED = {"R06", "R02"}


def run(raw: str):
    return check(raw, AVAILABLE, NOT_REVIEWED)


def test_plain_opinion_passes_and_keeps_rule_ids():
    result = run("- 참여자 확인 자료를 어디서 모을지 정해 두면 좋겠습니다 [R07]")
    assert len(result.kept) == 1
    assert result.kept[0].cited_rule_ids == ("R07",)
    assert result.kept[0].text.startswith("참여자 확인 자료")
    assert result.dropped == ()


def test_bullet_marks_are_removed():
    for mark in ("- ", "• ", "* ", "  -  "):
        assert run(f"{mark}확인할 점이 있습니다 [R07]").kept[0].text == "확인할 점이 있습니다 [R07]"


def test_line_without_rule_id_is_dropped():
    result = run("확인할 점이 있습니다")
    assert result.kept == ()
    assert result.drop_reasons == ("근거 규칙 번호가 없음",)


def test_unknown_rule_id_is_dropped():
    result = run("- 지역 자료를 확인하세요 [R09]")
    assert result.kept == ()
    assert "이번 검토에 없는 규칙" in result.drop_reasons[0]


def test_not_reviewed_rule_cannot_be_recommended():
    result = run("- 업종 후보를 함께 보세요 [R02]")
    assert result.kept == ()
    assert "검토하지 않은 규칙" in result.drop_reasons[0]


def test_numbers_are_dropped():
    for line in (
        "- 비중이 3개 구간에서 달랐습니다 [R07]",
        "- 외국인 결제액이 8.2% 늘었습니다 [R07]",
        "- 예산 500만원을 잡으세요 [R05]",
    ):
        assert run(line).kept == (), line


def test_rule_id_digits_are_not_counted_as_numbers():
    assert run("- 확인할 점을 정리하세요 [R07] [R03]").kept[0].cited_rule_ids == ("R03", "R07")


def test_korean_quantity_words_are_dropped():
    for line in (
        "- 절반 정도의 구간에서 방향이 달랐습니다 [R07]",
        "- 세 개 항목을 확인하세요 [R05]",
        "- 대부분의 달에서 비중이 높았습니다 [R07]",
    ):
        assert run(line).kept == (), line
    assert "수량 표현" in run("- 절반은 확인이 필요합니다 [R07]").drop_reasons[0]


def test_profile_rank_population_and_distance_written_as_korean_numbers_are_dropped():
    for line in (
        "- 자료가 있는 이백 곳 가운데 순위를 확인하세요 [R07]",
        "- 주민등록인구 십만 명을 참고하세요 [R03]",
        "- 유사 지역과의 거리가 열두 킬로미터입니다 [R05]",
        "- 아래에서 열한 번째입니다 [R07]",
    ):
        assert run(line).kept == (), line
        assert "수량 표현" in run(line).drop_reasons[0]


def test_judgment_words_are_dropped():
    for line in (
        "- 이 지표는 잘못 골랐습니다 [R07]",
        "- 이대로 하면 사업이 성공합니다 [R07]",
        "- 자료 수집이 반드시 해야 하는 일입니다 [R05]",
        "- 지표 선택이 틀렸습니다 [R07]",
    ):
        assert run(line).kept == (), line


def test_mixed_output_keeps_only_clean_lines():
    result = run(
        "- 참여자 확인 자료를 정해 두세요 [R07]\n"
        "- 3개 구간에서 방향이 달랐습니다 [R07]\n"
        "- 사용처 범위를 적어 두세요 [R03]"
    )
    assert [o.text.split(" [")[0] for o in result.kept] == ["참여자 확인 자료를 정해 두세요", "사용처 범위를 적어 두세요"]
    assert len(result.dropped) == 1


def test_all_dropped_gives_empty_result_with_reasons():
    result = run("- 성공합니다 [R07]\n- 3개입니다 [R07]")
    assert result.kept == ()
    assert len(result.dropped) == 2


def test_empty_output_is_handled():
    result = run("   \n\n")
    assert result.kept == () and result.dropped == ()


def test_extra_lines_beyond_limit_are_ignored():
    raw = "\n".join(f"- 확인할 점 {'가' * i} [R07]" for i in range(MAX_LINES + 3))
    result = run(raw)
    assert len(result.kept) + len(result.dropped) == MAX_LINES


def test_dropped_lines_are_kept_for_logging_not_for_screen():
    result = run("- 3개 구간 [R07]")
    assert result.dropped[0][0] == "3개 구간 [R07]"
    assert result.dropped[0][1] == "수치를 포함함"
