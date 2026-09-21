"""Vercel이 앱을 찾는 설정과 공개 상태 확인 경로."""

import json
import runpy
import tomllib

from fastapi.testclient import TestClient

from policy_signal_map.app import app
from policy_signal_map.paths import PROJECT_ROOT
from policy_signal_map.web.session import COOKIE_NAME


def test_vercel_entrypoint_and_function_settings_are_declared():
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    entrypoint = pyproject["tool"]["vercel"]["entrypoint"]
    assert entrypoint == "main:app"

    module_name, object_name = entrypoint.split(":", maxsplit=1)
    module_path = (PROJECT_ROOT / f"{module_name.replace('.', '/')}").with_suffix(".py")
    assert module_path.is_file()
    assert runpy.run_path(module_path)[object_name] is app

    config = json.loads((PROJECT_ROOT / "vercel.json").read_text(encoding="utf-8"))
    function = config["functions"]["main.py"]
    assert function["maxDuration"] >= 45
    assert config["regions"] == ["icn1"]


def test_health_reports_public_evidence_without_starting_a_session():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["session_backend"] == "memory"
    assert payload["evidence"]
    assert COOKIE_NAME not in response.cookies
    assert "key" not in response.text.lower()


def test_cookie_is_secure_in_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("PSM_SESSION_BACKEND", "memory")
    response = TestClient(app).get("/step/1")
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" in cookie
    assert "Max-Age=86400" in cookie


def test_vercel_does_not_silently_fall_back_to_memory_without_redis(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("PSM_SESSION_BACKEND", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)

    client = TestClient(app)
    assert client.get("/step/1").status_code == 503
    health = client.get("/health")
    assert health.status_code == 503
    assert health.json()["session_backend"] == "unavailable"
    assert "UPSTASH" not in health.text
