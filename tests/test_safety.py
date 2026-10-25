import importlib
import logging
from unittest.mock import Mock
import pytest
from langchain_core.messages import HumanMessage

from backend.core.index_safety import prepare_collection
from backend.core.logging import RedactingFilter
from backend.core.models import select_device
from backend.services.chat_service import ChatService
from backend.core.config import get_settings, settings_context


@pytest.mark.parametrize("requested,available,expected", [
    ("cpu", False, "cpu"), ("cpu", True, "cpu"), ("auto", False, "cpu"),
    ("auto", True, "cuda"), ("cuda", True, "cuda"),
])
def test_cpu_selection(requested, available, expected):
    assert select_device(requested, cuda_available=available) == expected


def test_explicit_unavailable_cuda():
    with pytest.raises(RuntimeError):
        select_device("cuda", cuda_available=False)


def test_bounded_history(settings, pipeline):
    settings = settings.model_copy(update={"MAX_HISTORY_MESSAGES": 2, "MAX_HISTORY_CHARACTERS": 10})
    service = ChatService(settings, pipeline)
    service.respond("q", [HumanMessage(content="old"), HumanMessage(content="123456"), HumanMessage(content="recent")])
    assert [m.content for m in pipeline.history] == ["recent"]


def test_injected_settings_reach_lazy_legacy_services(settings):
    with settings_context(settings):
        assert get_settings() is settings


def test_deepeval_live_judge_cannot_bypass_budget():
    from backend.services.llm import LLMUnavailable
    from benchmarks.deepeval_config import get_eval_model
    with pytest.raises(LLMUnavailable):
        get_eval_model()


def test_model_cache_policy_defaults_to_no_download(settings, monkeypatch):
    import sys
    from types import SimpleNamespace
    from backend.core.models import model_location
    download = Mock(return_value="cached-snapshot")
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=download))
    with settings_context(settings):
        assert model_location("test-model") == "cached-snapshot"
    download.assert_called_once_with("test-model", local_files_only=True)


@pytest.mark.parametrize("recreate,confirmation", [(False, None), (True, None), (True, "DELETE:other"), (False, "DELETE:laws")])
def test_destructive_guard(recreate, confirmation):
    client = Mock()
    client.collection_exists.return_value = True
    with pytest.raises(ValueError):
        prepare_collection(client, "laws", recreate=recreate, confirm_collection=confirmation)
    client.delete_collection.assert_not_called()


def test_destructive_guard_exact_confirmation_mock_only():
    client = Mock()
    client.collection_exists.return_value = True
    prepare_collection(client, "test-only", recreate=True, confirm_collection="DELETE:test-only")
    client.delete_collection.assert_called_once_with(collection_name="test-only")


@pytest.mark.parametrize("module", ["ingest_data", "ingest_data_alibaba", "ingest_data_vietnamese"])
def test_legacy_ingestion_refuses_existing_collection_without_model_loading(module, monkeypatch):
    module = importlib.import_module("preprocess." + module)
    client = Mock()
    client.collection_exists.return_value = True
    monkeypatch.setattr(module, "QdrantClient", lambda **_: client)
    with pytest.raises(ValueError):
        module.ingest_data()
    client.delete_collection.assert_not_called()
    client.create_collection.assert_not_called()
    client.upsert.assert_not_called()


@pytest.mark.parametrize("text", [
    "Authorization: Bearer private-token", "https://example.org/?key=private-token",
    "api_key=private-token", "Bearer private-token",
    "GET /documents?key=private-token HTTP/1.1",
])
def test_log_redaction(text):
    record = logging.LogRecord("test", logging.INFO, "", 1, "%s", (text,), None)
    assert RedactingFilter().filter(record)
    assert "private-token" not in record.getMessage()
