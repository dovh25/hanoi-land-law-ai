"""Every test is offline, with explicit isolated settings and databases."""
import os

# Set before importing application modules; never read real credentials in tests.
os.environ.update({
    "APP_MODE": "test", "ENABLE_LIVE_LLM": "false", "GEMINI_API_KEY": "",
    "JWT_SECRET_KEY": "test-only-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ALLOW_MODEL_DOWNLOADS": "false", "ALLOW_REMOTE_MODEL_CODE": "false",
    "LANGSMITH_TRACING": "false", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
})

import pytest
from fastapi.testclient import TestClient
from backend.core.config import Config
from backend.main import create_app
from backend.services.llm import MockProvider


@pytest.fixture
def settings(tmp_path):
    return Config(
        _env_file=None, DATABASE_URL=f"sqlite:///{tmp_path / 'test.db'}",
        LLM_USAGE_DB=tmp_path / "usage.sqlite3", DOCS_ROOT=tmp_path / "documents",
    )


class MockPipeline:
    is_initialized = True

    def __init__(self):
        self.provider = MockProvider()
        self.history = []

    def respond(self, query, history=None):
        self.history = history or []
        return {"answer": self.provider.invoke(query), "sources": []}


@pytest.fixture
def pipeline():
    return MockPipeline()


@pytest.fixture
def client(settings, pipeline):
    with TestClient(create_app(settings, pipeline=pipeline)) as client:
        yield client


def login(client, username="alice"):
    assert client.post("/api/v1/auth/register", json={
        "username": username, "password": "offline-test-password",
    }).status_code == 201
    response = client.post("/api/v1/auth/login", json={
        "username": username, "password": "offline-test-password",
    })
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def auth(client):
    return login(client)


@pytest.fixture
def legal_db(tmp_path):
    from backend.core.database import create_database
    engine, factory = create_database(f"sqlite:///{tmp_path / 'legal.db'}")
    try:
        yield engine, factory
    finally:
        engine.dispose()


@pytest.fixture
def seeded(legal_db):
    from legal_fixtures import seed_synthetic
    _, factory = legal_db
    with factory.begin() as session:
        fixture = seed_synthetic(session)
    return factory, fixture
