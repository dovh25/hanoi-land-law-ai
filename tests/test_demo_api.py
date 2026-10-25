"""Anonymous demo API: public access, no persistence, rate limits, no secret leakage."""
from fastapi.testclient import TestClient

from backend.core.config import Config
from backend.db.models import ChatSession
from backend.main import create_app
from backend.services.mvp_corpus import MvpCorpusIndex
from backend.services.pipelines.mvp_rag_pipeline import MvpRagPipeline


class FakeProvider:
    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def invoke(self, _prompt):
        self.calls += 1
        return self.answer


def test_demo_is_public_stateless_and_does_not_touch_chat_tables(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/demo/readyz").status_code == 200
        response = client.post("/api/v1/demo/chat", json={"message": "Xin chào"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "greeting"
        assert body["llm_used"] is False
        assert body["request_id"]
        assert "session_id" not in body
        assert app.state.chat_service.pipeline is None
        with app.state.session_factory() as session:
            assert session.query(ChatSession).count() == 0


def test_demo_info_has_coverage_limits_and_no_secrets(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get("/api/v1/demo/info")
        assert response.status_code == 200
        body = response.json()
        assert body["corpus"] == "MVP_DEMO_CORPUS"
        assert body["validity_status"] == "unknown"
        assert body["document_count"] == 2
        assert body["chunk_count"] == 90
        assert "31/2024/QH15" in body["limitations"]
        assert body["llm_enabled"] is False
        text = response.text.lower()
        assert "gemini_api_key" not in text
        assert "api_key" not in text


def test_demo_abstains_without_persisting(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/demo/chat",
            json={"message": "Quy hoạch sử dụng đất cấp huyện được lập thế nào?"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "abstained"
        assert response.json()["abstention_reason"] == "outside_corpus_scope"
        assert response.json()["sources"] == []


def test_demo_rate_limit(settings):
    limited = settings.model_copy(update={"MVP_RATE_LIMIT_PER_MINUTE": 1})
    app = create_app(limited)
    with TestClient(app) as client:
        assert client.post("/api/v1/demo/chat", json={"message": "Xin chào"}).status_code == 200
        response = client.post("/api/v1/demo/chat", json={"message": "Xin chào"})
        assert response.status_code == 429
        assert response.headers["Retry-After"].isdigit()
        assert "quá nhiều" in response.json()["detail"]


def test_demo_rejects_overlong_message(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post("/api/v1/demo/chat", json={"message": "đất " * 400})
        assert response.status_code == 422


def test_demo_disabled_returns_503(settings):
    disabled = settings.model_copy(update={"MVP_ENABLED": False})
    app = create_app(disabled)
    with TestClient(app) as client:
        assert client.get("/api/v1/demo/info").status_code == 503
        assert client.post("/api/v1/demo/chat", json={"message": "Xin chào"}).status_code == 503


def test_demo_cors_allowlist(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        headers = {"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"}
        assert client.options("/api/v1/demo/chat", headers=headers).status_code == 400
        headers["Origin"] = "http://localhost:5173"
        response = client.options("/api/v1/demo/chat", headers=headers)
        assert response.headers["access-control-allow-origin"] == headers["Origin"]


def test_demo_uses_injected_pipeline_and_returns_citations(settings):
    index = MvpCorpusIndex.load()
    provider = FakeProvider("Hộ gia đình có đất ở bị thu hồi được xem xét bồi thường [E1].")
    pipeline = MvpRagPipeline(provider=provider, index=index)
    app = create_app(settings, mvp_pipeline=pipeline)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/demo/chat",
            json={
                "message": "Bồi thường khi Nhà nước thu hồi đất ở là gì?",
                "history": [
                    {"role": "user", "content": "Xin chào"},
                    {"role": "assistant", "content": "Chào bạn"},
                ],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "answered"
        assert body["sources"][0]["evidence_id"] == "E1"
        assert body["sources"][0]["source_url"].startswith("https://vanban.chinhphu.vn/")
        assert provider.calls == 1


def test_demo_accepts_full_length_retrieval_answer_in_history(settings):
    """The UI echoes the whole retrieval-only answer (~3.3k chars) as history."""
    index = MvpCorpusIndex.load()
    provider = FakeProvider("Không đủ căn cứ.")
    pipeline = MvpRagPipeline(provider=provider, index=index)
    app = create_app(settings, mvp_pipeline=pipeline)
    long_answer = "Đoạn trích nguồn. " * 200  # ~3,600 chars, under MVP_MAX_HISTORY_CHARS
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/demo/chat",
            json={
                "message": "Thời hạn sử dụng đất ở là bao lâu?",
                "history": [
                    {"role": "user", "content": "Bồi thường khi Nhà nước thu hồi đất ở là gì?"},
                    {"role": "assistant", "content": long_answer},
                ],
            },
        )
    assert response.status_code == 200


def test_demo_readiness_follows_corpus_loading(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        body = client.get("/readyz").json()
        assert body["database"] is True
        assert body["demo_rag"] is True
        assert body["rag"] is False
