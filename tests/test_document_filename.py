"""저장 파일 이름 (5보완기획안계획.md 4장). 운영체제가 막는 글자를 남기지 않는다."""

from datetime import date

from policy_signal_map.document.filename import document_filename

TODAY = date(2026, 9, 17)


def test_spaces_become_underscores():
    assert document_filename("하반기 외국인 소비지원 쿠폰", TODAY) == "보완기획안_하반기_외국인_소비지원_쿠폰_20260917.docx"


def test_forbidden_characters_are_removed():
    name = document_filename('a/b\\c:d*e?f"g<h>i|j', TODAY)
    assert not set(name) & set('/\\:*?"<>|')
    assert name == "보완기획안_abcdefghij_20260917.docx"


def test_empty_name_falls_back():
    assert document_filename("   ", TODAY) == "보완기획안_20260917.docx"


def test_long_name_is_trimmed():
    name = document_filename("가" * 200, TODAY)
    assert name == "보완기획안_" + "가" * 60 + "_20260917.docx"


def test_newline_and_trailing_dot_are_removed():
    assert document_filename("사업\n계획.", TODAY) == "보완기획안_사업계획_20260917.docx"
