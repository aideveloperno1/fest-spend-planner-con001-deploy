"""쿠폰 시나리오를 입력부터 저장용 Word 문서까지 한 번에 통과시킨다."""

import re

from fastapi.testclient import TestClient
from helpers import VALID_FORM, docx_text

from policy_signal_map.app import app

COUPON_FORM = {
    **VALID_FORM,
    "name": "지역 상점 이용 쿠폰",
    "business_type": "coupon",
    "goals": ["store_usage"],
    "target": "지역 주민",
    "usage_place": "관내 참여 점포",
    # 첫 업종은 결제 0 사례, 둘째 업종×첫 연령은 대상 구성 질문 사례다.
    "usage_industries": ["IND01", "IND02"],
    "target_ages": ["AGE1"],
    "metrics": ["coupon_usage"],
    "indicator_use": "reference",
}


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_coupon_flow_reaches_document_with_both_value_based_choices():
    client = TestClient(app)
    assert client.post("/step/1", data=COUPON_FORM).status_code == 200

    questions = text_of(client.get("/step/3").text)
    assert "사용처 업종 확인" in questions
    assert "대상과 고객 구성" in questions

    client.post(
        "/step/4",
        data={"question_key": "R02", "decision": "adopt", "option_id": "A"},
    )
    client.post(
        "/step/4",
        data={
            "question_key": "R08",
            "decision": "adopt",
            "option_id": "C",
            "collect_items": "쿠폰 참여자 연령 확인 자료",
            "availability": "negotiating",
            "owner": "지역경제과",
            "cycle": "사업 종료 후 확인",
        },
    )

    response = client.get("/step/5")
    assert response.status_code == 200
    text = text_of(response.text)
    assert "쿠폰 참여자 연령 확인 자료" in text
    assert "지역 소비 프로필" in text

    document = docx_text(client.get("/step/5/download").content)
    assert "변경 001" in document and "변경 002" in document
    assert "R02-A" not in document and "R08-C" not in document
    assert "지역 소비 프로필" in document
