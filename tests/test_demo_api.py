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
        response = client.post(
            "/api/v1/demo/chat", json={"message": "Xin chào"},
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.status_code == 429
        assert response.headers["Retry-After"].isdigit()
        assert "retry-after" in response.headers["access-control-expose-headers"].lower()
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


def test_anonymous_daily_llm_cap_returns_sources_without_second_call(settings, monkeypatch):
    from backend.services import llm
    from backend.services.pipelines import mvp_rag_pipeline

    calls = []
    def transport(_):
        calls.append(1)
        return "Bồi thường về đất ở [E1]."

    monkeypatch.setattr(mvp_rag_pipeline, "GeminiProvider",
                        lambda config: llm.GeminiProvider(config, transport))
    limited = settings.model_copy(update={"ENABLE_LIVE_LLM": True,
        "GEMINI_API_KEY": "mock-only", "MAX_LLM_CALLS_PER_DAY": 1})
    with TestClient(create_app(limited)) as client:
        payload = {"message": "Điều 11 Nghị định 88/2024/NĐ-CP quy định gì?"}
        assert client.post("/api/v1/demo/chat", json=payload).json()["status"] == "answered"
        result = client.post("/api/v1/demo/chat", json=payload).json()
        assert result["status"] == "llm_unavailable"
        assert result["sources"]
        assert result["llm_used"] is False
    assert len(calls) == 1


def test_demo_history_is_request_local(settings):
    prompts = []
    class RecordingProvider:
        def invoke(self, prompt):
            prompts.append(str(prompt))
            return "Bồi thường về đất ở [E1]."

    pipeline = MvpRagPipeline(provider=RecordingProvider(), index=MvpCorpusIndex.load())
    with TestClient(create_app(settings, mvp_pipeline=pipeline)) as client:
        question = "Điều 11 Nghị định 88/2024/NĐ-CP quy định gì?"
        first = client.post("/api/v1/demo/chat", json={"message": question,
            "history": [{"role": "user", "content": "PRIVATE_M4_CANARY"}]})
        second = client.post("/api/v1/demo/chat", json={"message": question})
        assert first.status_code == second.status_code == 200
        assert "PRIVATE_M4_CANARY" in prompts[0]
        assert "PRIVATE_M4_CANARY" not in prompts[1]
        assert "set-cookie" not in first.headers


def test_anonymous_cannot_access_or_mutate_persisted_sessions(settings):
    with TestClient(create_app(settings)) as client:
        session_id = "1e07a9a8-31dc-441d-8641-2e4c735a72b9"
        for method, path, body in [
            ("GET", "/sessions", None),
            ("GET", f"/sessions/{session_id}", None),
            ("PATCH", f"/sessions/{session_id}", {"title": "stolen"}),
            ("DELETE", f"/sessions/{session_id}", None),
        ]:
            assert client.request(method, f"/api/v1{path}", json=body).status_code == 401
        assert client.post("/api/v1/demo/chat", json={
            "message": "Xin chào", "session_id": session_id,
        }).status_code == 422


def test_public_citation_opens_matching_bundled_excerpt(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/demo/chat", json={
            "message": "Điều 11 Nghị định 88/2024/NĐ-CP quy định gì?",
        })
        assert response.status_code == 200
        source = response.json()["sources"][0]
        doc = client.get(f'/api/v1/documents/{source["document_id"]}')
        assert doc.status_code == 200
        assert doc.json()["ref"] == source["document_number"]
        assert source["article_number"] in doc.json()["content"]
        assert "không phải toàn văn" in doc.json()["content"]
        found = client.get('/api/v1/documents/search', params={"q": source["document_number"]})
        assert any(item["id"] == source["document_id"] for item in found.json()["items"])
        articles = client.get(f'/api/v1/documents/{source["document_id"]}/articles')
        assert articles.status_code == 200
        assert any(item["article_number"] == source["article_number"] for item in articles.json())


def test_demo_rejects_blank_and_unbounded_history(settings):
    with TestClient(create_app(settings)) as client:
        for payload in [
            {"message": "   "},
            {"message": "Xin chào", "history": [{"role": "user", "content": "x"}] * 21},
            {"message": "Xin chào", "history": [{"role": "user", "content": "x" * 4001}]},
        ]:
            assert client.post("/api/v1/demo/chat", json=payload).status_code == 422
