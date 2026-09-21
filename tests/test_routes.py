from fastapi.testclient import TestClient
from helpers import VALID_FORM

from policy_signal_map.app import app


def client() -> TestClient:
    return TestClient(app)


def test_later_steps_locked_until_review_starts():
    response = client().get("/step/2", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/step/1"


def test_input_page_lists_rules_from_catalog():
    response = client().get("/step/1")
    assert response.status_code == 200
    # 1단계 예정 목록은 범위 라벨과 설명만 보여 준다 (관리 번호는 화면에 쓰지 않음, 9/18)
    assert "검토 구현" in response.text and "기본 검토" in response.text and "분석 예시" in response.text
    assert "R07" not in response.text and "R02" not in response.text


def test_static_files_are_served():
    c = client()
    assert c.get("/static/css/style.css").status_code == 200
    assert c.get("/static/js/input.js").status_code == 200


def test_empty_submit_shows_errors():
    response = client().post("/step/1", data={"action": "submit"})
    assert response.status_code == 422
    assert "필수 항목 8개를 확인해 주세요." in response.text
    assert "사업명을 입력해 주세요." in response.text


def test_valid_submit_keeps_original_and_opens_step_two():
    c = client()
    response = c.post("/step/1", data=VALID_FORM)
    assert response.status_code == 200
    assert str(response.url).endswith("/step/2")
    assert "" in response.text

    # 보관한 원안은 다시 입력 화면을 열어도 그대로 남는다
    again = c.get("/step/1").text
    assert 'value="하반기 외국인 소비지원 쿠폰"' in again
    assert "51150" in again


def test_resubmitting_changed_plan_shows_recheck_notice():
    c = client()
    c.post("/step/1", data=VALID_FORM)
    c.post("/step/1", data={**VALID_FORM, "indicator_use": "reference"})
    assert "원안이 바뀌어 검토를 다시 실행했습니다" in c.get("/step/3").text


def test_recheck_notice_disappears_after_unchanged_resubmit():
    c = client()
    c.post("/step/1", data=VALID_FORM)
    c.post("/step/1", data={**VALID_FORM, "indicator_use": "reference"})
    c.post("/step/1", data={**VALID_FORM, "indicator_use": "reference"})  # 바뀐 것 없이 다시 제출
    assert "원안이 바뀌어 검토를 다시 실행했습니다" not in c.get("/step/3").text


def test_sample_button_fills_form():
    response = client().post("/step/1", data={"action": "sample"})
    assert 'value="하반기 외국인 소비지원 쿠폰"' in response.text


def test_reset_clears_work():
    c = client()
    c.post("/step/1", data=VALID_FORM)
    c.post("/reset")
    assert c.get("/step/2", follow_redirects=False).status_code == 303


def test_user_input_is_escaped():
    response = client().post("/step/1", data={**VALID_FORM, "name": "<script>alert(1)</script>", "target": ""})
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;" in response.text


def test_pages_declare_an_icon_so_browsers_do_not_request_favicon():
    # 파비콘 파일이 없어 /favicon.ico 요청이 404 콘솔 기록을 남기던 것을 막는다 (6-4a)
    html = TestClient(app).get("/step/1").text
    assert '<link rel="icon" href="data:," />' in html


def test_static_files_are_revalidated():
    """브라우저가 옛 CSS·JS를 계속 쓰지 않도록 매번 확인하게 한다 (2026-09-18)."""
    response = TestClient(app).get("/static/js/input.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_static_urls_carry_a_version():
    """파일이 바뀌면 주소가 바뀌어야 브라우저가 옛 CSS·JS를 쓰지 않는다 (2026-09-18)."""
    import re

    html = TestClient(app).get("/step/1").text
    assert re.search(r'/static/js/input\.js\?v=\d+', html)
    assert re.search(r'/static/css/style\.css\?v=\d+', html)
