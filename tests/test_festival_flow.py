"""축제 시나리오를 입력부터 보완 기획안까지 한 번에 통과시킨다 (묶음 2 마무리 확인).

3일짜리 지역 축제 + 방문객 수 지표라는 기획으로, 새로 만든 입력·프로필·지표 점검이
5단계 문서까지 이어지는지 본다. 수치는 모두 시연용 합성 자료다.
"""

import re

from fastapi.testclient import TestClient
from helpers import VALID_FORM

from policy_signal_map.app import app

FESTIVAL_FORM = {
    **VALID_FORM,
    "name": "가을 지역 축제",
    "business_type": "festival",
    "target": "국내 방문객",
    # 자료 기간(2026-01~06) 안의 사흘짜리 행사
    "period_start": "2026-05-08",
    "period_end": "2026-05-10",
    "metrics": ["visitors", "payment_amount"],
    "visitor_goal": "30000",
    "usage_industries": ["IND01"],
    "target_ages": ["AGE2"],
}

ANSWER_R02 = {"question_key": "R02", "decision": "keep_original"}
# 5월은 이 지역에서 결제가 평소보다 컸던 달이라 시기 질문도 뜬다
ANSWER_SEASON = {"question_key": "R04-season", "decision": "keep_original"}

ANSWER_R10 = {
    "question_key": "R10",
    "decision": "adopt",
    "option_id": "A",
    "collect_items": "축제 입장 집계",
    "availability": "negotiating",
    "owner": "문화관광과",
    "cycle": "행사 종료 후 1회",
}


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def festival_client() -> TestClient:
    c = TestClient(app)
    response = c.post("/step/1", data=FESTIVAL_FORM)
    assert response.status_code == 200, "축제 기획 입력이 검증을 통과해야 한다"
    return c


def test_입력이_그대로_남는다():
    c = festival_client()
    text = c.get("/step/1").text
    assert 'value="IND01"\n                     checked' in text or 'value="IND01" checked' in text.replace("\n", " ")


def test_2단계에_고른_지역_프로필이_뜬다():
    text = text_of(festival_client().get("/step/2").text)
    assert "지역 소비 프로필" in text
    assert "업종 구성" in text and "연령 구성" in text


def test_3단계에_못_재는_지표_질문이_뜬다():
    text = text_of(festival_client().get("/step/3").text)
    assert "성과지표와 자료 범위 확인" in text
    assert "방문객 수" in text


def test_4단계에서_고르고_5단계_문서에_남는다():
    c = festival_client()
    assert c.post("/step/4", data=ANSWER_R10).status_code in (200, 303)
    # 축제 팩은 사용처 업종도 확인한다. 고른 업종이 질문에 걸리면 함께 답해야 문서로 넘어간다
    c.post("/step/4", data=ANSWER_R02)
    c.post("/step/4", data=ANSWER_SEASON)
    text = text_of(c.get("/step/5").text)
    assert "축제 입장 집계" in text
    assert "문화관광과" in text


def test_문서_본문에_해석_조건이_적힌다():
    c = festival_client()
    c.post("/step/4", data=ANSWER_R10)
    c.post("/step/4", data=ANSWER_R02)
    c.post("/step/4", data=ANSWER_SEASON)
    text = text_of(c.get("/step/5/document").text)
    assert "사람 수" in text
    assert "협의 중" in text  # 자료 확보 여부를 확정으로 바꾸지 않는다


def test_화면에는_규칙_번호가_나오지_않는다():
    """3~5단계 화면과 저장할 Markdown에 규칙 관리 번호를 쓰지 않는다."""
    c = festival_client()
    c.post("/step/4", data=ANSWER_R10)
    c.post("/step/4", data=ANSWER_R02)
    c.post("/step/4", data=ANSWER_SEASON)
    for path in ("/step/3", "/step/4", "/step/5", "/step/5/document"):
        text = text_of(c.get(path).text)
        assert "R10" not in text, path
    markdown = c.get("/step/5/download").text
    assert "변경 001" in markdown
    assert "R10-A" not in markdown
