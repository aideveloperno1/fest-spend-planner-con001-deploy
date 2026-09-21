"""모든 화면 상단의 자료 종류·버전 표시 (2근거확인화면계획.md 8장, A-3)."""

import json
import re
from pathlib import Path

from evidence_helpers import base_data, fixture_path
from fastapi.testclient import TestClient
from helpers import VALID_FORM

from policy_signal_map.app import app

BADGE_RE = re.compile(r'<span class="tag[^"]*" data-evidence-badge>([^<]+)</span>')


def badge(html: str) -> str:
    match = BADGE_RE.search(html)
    assert match, "상단 칩이 없습니다"
    return match.group(1)


def test_every_page_renders_top_badge():
    c = TestClient(app)
    assert badge(c.get("/step/1").text) == "시연용 합성 수치 · demo-001"
    assert badge(c.post("/step/1", data={"action": "submit"}).text) == "시연용 합성 수치 · demo-001"  # 422
    c.post("/step/1", data=VALID_FORM)
    assert badge(c.get("/step/2").text) == "시연용 합성 수치 · demo-001"
    assert badge(c.get("/step/3").text) == "시연용 합성 수치 · demo-001"


def test_error_page_badge(use_evidence):
    c = TestClient(app)
    c.post("/step/1", data=VALID_FORM)
    use_evidence(fixture_path("relation_broken"))
    response = c.get("/step/2")
    assert response.status_code == 503
    assert badge(response.text) == "근거 파일 오류"
    assert 'class="tag tag-error"' in response.text
    assert badge(c.get("/step/1").text) == "근거 파일 오류"


def test_real_file_badge_and_footer(use_evidence, tmp_path: Path):
    data = base_data()
    data["records"][0]["data_kind"] = "real"
    path = tmp_path / "labelled.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    use_evidence(path)

    html = TestClient(app).get("/step/1").text
    assert badge(html) == "실제 분석 자료 · fixture-amount_up_share_down · 내부 검증용"
    assert "실제 분석 자료 · 내부 검증용 · BC카드 공식 서비스가 아닙니다" in html
    assert "시연용 합성 수치입니다" not in html


def test_demo_footer():
    html = TestClient(app).get("/step/1").text
    assert "화면의 수치는 시연용 합성 수치입니다 · BC카드 공식 서비스가 아닙니다 · 공모전 제안용" in re.sub(r"\s+", " ", html)
