"""The only live LLM boundary: lazy SDK, explicit consent, persistent budgets."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
import sqlite3
import httpx

from backend.core.config import Config, get_settings, settings_context


class LLMUnavailable(RuntimeError):
    """Safe public error; never carries provider response/credentials."""

    # Numeric upstream status only (e.g. 429); never provider text or the key.
    upstream_status: int | None = None


class LiveLLMDisabled(LLMUnavailable):
    pass


class LLMBudgetExceeded(LLMUnavailable):
    pass


@dataclass
class Turn:
    settings: Config
    calls: int = 0


_turn: ContextVar[Turn | None] = ContextVar("llm_turn", default=None)


@contextmanager
def llm_turn(settings: Config):
    from langsmith import tracing_context
    if _turn.get() is not None:
        yield _turn.get()
        return
    token = _turn.set(Turn(settings))
    try:
        with settings_context(settings), tracing_context(enabled=False):
            yield _turn.get()
    finally:
        _turn.reset(token)


def budgeted_turn(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        settings = _turn.get().settings if _turn.get() else get_settings()
        require_live(settings)
        with llm_turn(settings):
            return function(*args, **kwargs)
    return wrapped


def require_live(settings: Config):
    if not settings.ENABLE_LIVE_LLM:
        raise LiveLLMDisabled("Live LLM use is disabled")


def reserve_call(turn: Turn):
    """Count every attempt, including failures; shared SQLite transaction across workers."""
    settings = turn.settings
    require_live(settings)
    if turn.calls >= settings.MAX_LLM_CALLS_PER_TURN:
        raise LLMBudgetExceeded("Per-turn LLM call limit reached")
    path = Path(settings.LLM_USAGE_DB)
    day = datetime.now(timezone.utc).date().isoformat()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path, timeout=5) as db:
            db.execute("CREATE TABLE IF NOT EXISTS usage (day TEXT PRIMARY KEY, calls INTEGER NOT NULL)")
            db.execute("BEGIN IMMEDIATE")
            calls = db.execute("SELECT calls FROM usage WHERE day = ?", (day,)).fetchone()
            if calls and calls[0] >= settings.MAX_LLM_CALLS_PER_DAY:
                raise LLMBudgetExceeded("Daily LLM call limit reached")
            db.execute("INSERT INTO usage VALUES (?, 1) ON CONFLICT(day) DO UPDATE SET calls = calls + 1", (day,))
    except (sqlite3.Error, OSError):
        raise LLMUnavailable("LLM usage ledger unavailable") from None
    turn.calls += 1


class GeminiProvider:
    """No SDK/client construction until an approved, budgeted invocation."""
    def __init__(self, settings: Config, transport=None):
        self.settings = settings
        self.transport = transport

    def invoke(self, prompt):
        turn = _turn.get()
        if turn is None:
            raise LLMUnavailable("LLM requests require a turn budget")
        require_live(self.settings)
        # A provider cannot substitute different settings to bypass the turn budget.
        if turn.settings != self.settings:
            raise LLMUnavailable("LLM settings do not match turn budget")
        for attempt in range(self.settings.LLM_MAX_RETRIES + 1):
            reserve_call(turn)
            try:
                return (self.transport or self._generate)(prompt)
            except (TimeoutError, ConnectionError, httpx.TimeoutException, httpx.NetworkError):
                if attempt < self.settings.LLM_MAX_RETRIES:
                    continue
                raise LLMUnavailable("LLM request timed out or is unavailable") from None
            except LLMUnavailable:
                raise
            except Exception as exc:
                # Includes rate limits/quota errors: do not retry or expose provider text.
                error = LLMUnavailable("LLM provider unavailable; retry later")
                code = getattr(exc, "code", None)
                error.upstream_status = code if isinstance(code, int) else None
                raise error from None

    def _generate(self, prompt):
        from google import genai
        from google.genai import types
        # Pipelines may pass a ChatPromptValue or a plain list of messages.
        messages = prompt.to_messages() if hasattr(prompt, "to_messages") else list(prompt)
        system = "\n".join(str(m.content) for m in messages if m.type == "system")
        contents = [types.Content(
            role="model" if m.type == "ai" else "user",
            parts=[types.Part(text=str(m.content))],
        ) for m in messages if m.type != "system"]
        with genai.Client(
            vertexai=False,
            api_key=self.settings.GEMINI_API_KEY.get_secret_value(),
            http_options=types.HttpOptions(
                base_url="https://generativelanguage.googleapis.com",
                timeout=int(self.settings.LLM_REQUEST_TIMEOUT_SECONDS * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        ) as client:
            result = client.models.generate_content(
                model=self.settings.MODEL, contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=self.settings.MAX_LLM_OUTPUT_TOKENS,
                ),
            )
        if not result.text:
            raise LLMUnavailable("LLM returned no answer")
        return result.text


def build_llm():
    from langchain_core.runnables import RunnableLambda
    # Capture settings from the request context, never a second environment file.
    def invoke(prompt):
        settings = _turn.get().settings if _turn.get() else get_settings()
        return GeminiProvider(settings).invoke(prompt)
    return RunnableLambda(invoke)


class MockProvider:
    """Deterministic offline provider for injected test pipelines."""
    def __init__(self, answer="Offline test answer"):
        self.answer = answer
        self.calls = 0

    def invoke(self, _prompt):
        self.calls += 1
        return self.answer
