import subprocess
import sys

from fastapi.testclient import TestClient
from backend.main import create_app
from conftest import login


def test_healthcheck(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_import_from_other_directory_without_ml(tmp_path):
    code = """
import sys
from backend.main import app
assert 'torch' not in sys.modules
assert 'transformers' not in sys.modules
assert 'google.genai' not in sys.modules
assert app.state.chat_service.pipeline is None
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_offline_lifespan_and_readiness(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["database"] is True
        assert app.state.chat_service.pipeline is None
        headers = login(client)
        response = client.post("/api/v1/chat", json={"message": "test"}, headers=headers)
        assert response.status_code == 503
        assert "disabled" in response.json()["detail"]
        assert app.state.chat_service.pipeline is None


def test_chat_requires_authentication(client):
    assert client.post("/api/v1/chat", json={"message": "hello"}).status_code == 401


def test_authentication(client, auth):
    assert client.get("/api/v1/auth/me", headers=auth).json()["username"] == "alice"
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/register", json={"username": "alice", "password": "another-password"}).status_code == 400


def test_session_ownership(client, auth):
    session = client.post("/api/v1/sessions", headers=auth, json={}).json()["id"]
    other = login(client, "bob")
    for method, path, body in [
        ("GET", f"/api/v1/sessions/{session}", None),
        ("PATCH", f"/api/v1/sessions/{session}", {"title": "stolen"}),
        ("DELETE", f"/api/v1/sessions/{session}", None),
        ("POST", "/api/v1/chat", {"message": "steal", "session_id": session}),
    ]:
        assert client.request(method, path, headers=other, json=body).status_code == 404
    assert client.get("/api/v1/sessions", headers=other).json()["sessions"] == []
    assert client.get(f"/api/v1/sessions/{session}", headers=auth).status_code == 200


def test_chat_persists_and_bounds_history(client, auth, pipeline):
    response = client.post("/api/v1/chat", json={"message": "first"}, headers=auth)
    assert response.status_code == 200
    session = response.json()["session_id"]
    response = client.post("/api/v1/chat", json={"message": "follow-up", "session_id": session}, headers=auth)
    assert response.status_code == 200
    assert [m.content for m in pipeline.history] == ["first", "Offline test answer"]
    saved = client.get(f"/api/v1/sessions/{session}", headers=auth).json()
    assert len(saved["messages"]) == 4
    assert client.delete(f"/api/v1/sessions/{session}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/sessions/{session}", headers=auth).status_code == 404


def test_cors_allowlist(client):
    headers = {"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"}
    response = client.options("/api/v1/chat", headers=headers)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
    headers["Origin"] = "http://localhost:5173"
    response = client.options("/api/v1/chat", headers=headers)
    assert response.headers["access-control-allow-origin"] == headers["Origin"]


def test_no_authorization_logging(client, auth, caplog):
    client.get("/api/v1/auth/me", headers=auth)
    assert auth["Authorization"] not in caplog.text
    assert auth["Authorization"][7:40] not in caplog.text


def test_message_length_validation(client, auth):
    assert client.post("/api/v1/chat", headers=auth, json={"message": ""}).status_code == 422


def test_failed_turn_does_not_commit_half_exchange(client, auth, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    from backend.services.session_service import session_service
    session = client.post("/api/v1/sessions", headers=auth, json={}).json()["id"]
    original = session_service.add_message
    def fail_second(**kwargs):
        if kwargs["role"] == "ai":
            raise SQLAlchemyError("simulated failure")
        return original(**kwargs)
    monkeypatch.setattr(session_service, "add_message", fail_second)
    response = client.post("/api/v1/chat", headers=auth, json={"message": "q", "session_id": session})
    assert response.status_code == 500
    assert client.get(f"/api/v1/sessions/{session}", headers=auth).json()["messages"] == []
