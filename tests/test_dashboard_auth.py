"""Tests for dashboard HTTP Basic Auth."""

import base64

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER", "admin")
    monkeypatch.setenv("DASHBOARD_PASS", "superpowers")
    # Reset cached settings so env vars are picked up
    import dashboard.deps as deps

    deps._settings = None
    from dashboard.app import app

    yield TestClient(app)
    deps._settings = None


def _basic_header(user: str, password: str) -> dict:
    creds = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}


# --- Unauthenticated /api/* returns 401 ---


def test_api_status_unauthenticated(client):
    resp = client.get("/api/status")
    assert resp.status_code == 401


def test_api_cron_unauthenticated(client):
    resp = client.get("/api/cron/jobs")
    assert resp.status_code == 401


# --- Correct credentials return 200 ---


def test_api_status_authenticated(client):
    resp = client.get("/api/status", headers=_basic_header("admin", "superpowers"))
    assert resp.status_code == 200


def test_api_cron_authenticated(client):
    resp = client.get("/api/cron/jobs", headers=_basic_header("admin", "superpowers"))
    assert resp.status_code == 200


# --- Wrong credentials return 401 ---


def test_api_wrong_password(client):
    resp = client.get("/api/status", headers=_basic_header("admin", "wrong"))
    assert resp.status_code == 401


def test_api_wrong_user(client):
    resp = client.get("/api/status", headers=_basic_header("hacker", "superpowers"))
    assert resp.status_code == 401


# --- /health is public ---


def test_health_no_auth(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- Static files are public ---


def test_static_index_no_auth(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_static_appjs_no_auth(client):
    resp = client.get("/app.js")
    assert resp.status_code == 200


def test_static_appcss_no_auth(client):
    resp = client.get("/app.css")
    assert resp.status_code == 200
