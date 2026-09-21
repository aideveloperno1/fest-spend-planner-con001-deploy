"""랜딩 화면 (`/`). 시안에 들어 있던 금지 표기가 따라 들어오지 않게 못 박는다.

랜딩은 소개 화면이라 세션을 만들지 않고, 동적 효과는 향상일 뿐이라 JS 없이도 내용이 다 보여야 한다.
"""

import re

from fastapi.testclient import TestClient

from policy_signal_map.app import app
from policy_signal_map.web.landing_content import LANDING
from policy_signal_map.web.session import COOKIE_NAME


def client() -> TestClient:
    return TestClient(app)


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def landing_text() -> str:
    return text_of(client().get("/").text)


def test_root_shows_landing_without_session():
    response = client().get("/")
    assert response.status_code == 200
    assert "차트를 보여주는 대신" in text_of(response.text)


def test_step_one_still_works():
    assert client().get("/step/1").status_code == 200


def test_try_buttons_point_to_step_one():
    html = client().get("/").text
    assert html.count('href="/step/1"') >= 2  # 위쪽 막대 + 머리말 + 맺음


def test_landing_has_no_rule_management_codes():
    """규칙 관리 번호(R01~R07)는 화면에 쓰지 않는다 (사용자 결정 2026-09-18). 시안에는 있었다."""
    assert not re.findall(r"\bR0[1-7]\b", landing_text())


def test_landing_has_no_administrative_codes():
    """행정표준코드 10자리는 화면에 쓰지 않는다. 지역은 이름으로만 적는다."""
    assert not re.findall(r"\b\d{10}\b", landing_text())


def test_landing_has_no_real_dataset_version():
    """실제 자료 버전(real-…)을 쓰지 않는다. 시연용 합성(demo-) 기준이다."""
    assert not re.findall(r"real-[\w-]+", landing_text())
    assert "demo-001" in landing_text()


def test_landing_states_synthetic_and_not_official():
    text = landing_text()
    assert "시연용 합성 수치" in text
    assert "BC카드 소비데이터 활용 공모전 제안" in text


def test_landing_does_not_create_a_session():
    """소개 화면을 보기만 해도 작업 상태가 생기면 안 된다."""
    assert COOKIE_NAME not in client().get("/").cookies


def test_every_section_is_readable_without_javascript():
    """동적 효과는 향상일 뿐이다. 서버가 그린 HTML에 모든 구역 글자가 들어 있어야 한다."""
    text = landing_text()
    for step in LANDING.steps:
        assert step.title in text
    for case in LANDING.ladder_cases:
        assert case.chip in text
        assert case.note in text  # 고르지 않은 칸의 안내도 HTML에 있다
    for rule in LANDING.rules:
        assert rule.title in text
    assert LANDING.evidence_summary in text


def test_landing_serves_its_own_styles_and_script():
    c = client()
    assert c.get("/static/css/landing.css").status_code == 200
    assert c.get("/static/js/landing.js").status_code == 200


def test_screenshots_are_served_for_the_landing():
    """랜딩용 합성 캡처는 설치 패키지의 정적 파일에서도 제공한다."""
    assert client().get("/static/images/screenshot-evidence-region.png").status_code == 200


def test_brand_on_every_step_goes_to_the_landing():
    """작업 화면에서 서비스 이름을 누르면 랜딩으로 돌아간다 (전에는 1단계로 갔다)."""
    c = client()
    c.post("/step/1", data={"action": "sample"}, follow_redirects=True)
    for step in (1, 2, 3):
        html = c.get(f"/step/{step}").text
        assert re.search(r'<a\b[^>]*class="brand"[^>]*href="/"(?:\s[^>]*)?>', html), step


def test_landing_and_service_share_the_same_pencil_palette():
    c = client()
    landing = c.get("/").text
    service = c.get("/step/1").text
    for class_name in (
        "brand-pen-fill",
        "brand-pen-outline",
        "brand-pen-detail",
        "brand-pen-underline",
    ):
        assert f'class="{class_name}"' in landing
        assert f'class="{class_name}"' in service
