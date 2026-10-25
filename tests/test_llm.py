from unittest.mock import Mock, MagicMock
import pytest
import httpx
from backend.core.config import Config
from backend.services.llm import (
    GeminiProvider, LiveLLMDisabled, LLMBudgetExceeded, LLMUnavailable,
    MockProvider, llm_turn,
)


def live_settings(tmp_path, **kwargs):
    # Dummy credential + fake transport only. Tests never contact Gemini.
    return Config(_env_file=None, APP_MODE="development", ENABLE_LIVE_LLM=True,
                  GEMINI_API_KEY="mock-not-a-real-key", LLM_USAGE_DB=tmp_path / "usage.sqlite3", **kwargs)


def test_disabled_live_rejected_without_transport(settings):
    transport = Mock()
    with llm_turn(settings), pytest.raises(LiveLLMDisabled):
        GeminiProvider(settings, transport).invoke("question")
    transport.assert_not_called()
    assert not settings.LLM_USAGE_DB.exists()


def test_per_turn_budget(tmp_path):
    settings = live_settings(tmp_path, MAX_LLM_CALLS_PER_TURN=1)
    transport = Mock(return_value="answer")
    with llm_turn(settings):
        provider = GeminiProvider(settings, transport)
        assert provider.invoke("q") == "answer"
        with pytest.raises(LLMBudgetExceeded):
            provider.invoke("q")
    assert transport.call_count == 1


def test_daily_budget_survives_new_provider(tmp_path):
    settings = live_settings(tmp_path, MAX_LLM_CALLS_PER_DAY=1)
    with llm_turn(settings):
        assert GeminiProvider(settings, lambda _: "ok").invoke("q") == "ok"
    transport = Mock()
    with llm_turn(settings), pytest.raises(LLMBudgetExceeded):
        GeminiProvider(settings, transport).invoke("q")
    transport.assert_not_called()


def test_retries_consume_budget(tmp_path):
    settings = live_settings(tmp_path, MAX_LLM_CALLS_PER_TURN=1, LLM_MAX_RETRIES=2)
    transport = Mock(side_effect=TimeoutError("private provider detail"))
    with llm_turn(settings), pytest.raises(LLMBudgetExceeded):
        GeminiProvider(settings, transport).invoke("q")
    assert transport.call_count == 1


@pytest.mark.parametrize("error", [TimeoutError("private"), httpx.ReadTimeout("private"), RuntimeError("429 quota private")])
def test_failures_are_safe_and_counted(tmp_path, error):
    settings = live_settings(tmp_path, MAX_LLM_CALLS_PER_DAY=1)
    with llm_turn(settings), pytest.raises(LLMUnavailable) as exc:
        GeminiProvider(settings, Mock(side_effect=error)).invoke("q")
    assert "private" not in str(exc.value)
    with llm_turn(settings), pytest.raises(LLMBudgetExceeded):
        GeminiProvider(settings, lambda _: "should not run").invoke("q")


def test_budget_scope_required(tmp_path):
    with pytest.raises(LLMUnavailable):
        GeminiProvider(live_settings(tmp_path), lambda _: "unused").invoke("q")


def test_deterministic_mock():
    provider = MockProvider()
    assert provider.invoke("one") == provider.invoke("two")
    assert provider.calls == 2


def test_successful_retry_is_counted(tmp_path):
    settings = live_settings(tmp_path, MAX_LLM_CALLS_PER_TURN=2, LLM_MAX_RETRIES=1)
    transport = Mock(side_effect=[TimeoutError(), "answer"])
    with llm_turn(settings) as turn:
        assert GeminiProvider(settings, transport).invoke("q") == "answer"
        assert turn.calls == 2


def test_sdk_limits_and_no_sdk_retries(tmp_path, monkeypatch):
    from google import genai
    from langchain_core.prompts import ChatPromptTemplate
    settings = live_settings(tmp_path, MAX_LLM_OUTPUT_TOKENS=123, LLM_REQUEST_TIMEOUT_SECONDS=7)
    client = MagicMock()
    client.models.generate_content.return_value.text = "mock-sdk-answer"
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    monkeypatch.setattr(genai, "Client", factory)
    prompt = ChatPromptTemplate.from_messages([("system", "rules"), ("human", "{q}")]).invoke({"q": "question"})
    with llm_turn(settings):
        assert GeminiProvider(settings).invoke(prompt) == "mock-sdk-answer"
    options = factory.call_args.kwargs["http_options"]
    assert options.timeout == 7000
    assert options.retry_options.attempts == 1
    assert factory.call_args.kwargs["vertexai"] is False
    assert client.models.generate_content.call_args.kwargs["config"].max_output_tokens == 123


def test_generate_accepts_plain_message_list(tmp_path, monkeypatch):
    """The MVP pipeline passes a list, not a ChatPromptValue (live-run regression)."""
    from google import genai
    from langchain_core.messages import HumanMessage, SystemMessage
    settings = live_settings(tmp_path)
    client = MagicMock()
    client.models.generate_content.return_value.text = "list-answer"
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    monkeypatch.setattr(genai, "Client", factory)
    prompt = [SystemMessage(content="rules"), HumanMessage(content="question")]
    with llm_turn(settings):
        assert GeminiProvider(settings).invoke(prompt) == "list-answer"
    contents = client.models.generate_content.call_args.kwargs["contents"]
    assert [item.role for item in contents] == ["user"]
    assert contents[0].parts[0].text == "question"
    config = client.models.generate_content.call_args.kwargs["config"]
    assert config.system_instruction == "rules"


def test_upstream_status_is_numeric_only(tmp_path):
    class ProviderError(RuntimeError):
        code = 429

    settings = live_settings(tmp_path)
    error = ProviderError("quota private detail")
    with llm_turn(settings), pytest.raises(LLMUnavailable) as exc:
        GeminiProvider(settings, Mock(side_effect=error)).invoke("q")
    assert exc.value.upstream_status == 429
    assert "private" not in str(exc.value)


def test_ledger_enforces_concurrent_daily_budget(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    settings = live_settings(tmp_path, MAX_LLM_CALLS_PER_DAY=3)
    def attempt(_):
        with llm_turn(settings):
            try:
                return GeminiProvider(settings, lambda _: "ok").invoke("q")
            except LLMBudgetExceeded:
                return "blocked"
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(attempt, range(6)))
    assert results.count("ok") == 3
    assert results.count("blocked") == 3


def test_ledger_failure_refuses_transport(tmp_path):
    settings = live_settings(tmp_path)
    settings.LLM_USAGE_DB.mkdir()
    transport = Mock()
    with llm_turn(settings), pytest.raises(LLMUnavailable):
        GeminiProvider(settings, transport).invoke("q")
    transport.assert_not_called()
