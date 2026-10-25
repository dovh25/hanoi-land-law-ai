"""Request-local history and lazy pipeline loading; no process-local session cache."""
from threading import Lock

from backend.core.config import Config, settings_context
from backend.services.llm import llm_turn, require_live


class ChatService:
    def __init__(self, settings: Config, pipeline=None):
        self.settings = settings
        self.pipeline = pipeline
        self._startup_lock = Lock()

    @property
    def is_ready(self):
        return bool(self.pipeline and self.pipeline.is_initialized)

    def startup(self):
        require_live(self.settings)
        with self._startup_lock, settings_context(self.settings):
            if self.pipeline is None:
                from backend.services.pipelines import AgenticRAGPipeline
                self.pipeline = AgenticRAGPipeline()
            if not self.pipeline.is_initialized:
                self.pipeline.startup()

    def respond(self, query, history=None):
        # Check consent before even attempting imports, model loading, or Qdrant access.
        if self.pipeline is None or not self.pipeline.is_initialized:
            self.startup()
        bounded = []
        remaining = self.settings.MAX_HISTORY_CHARACTERS
        for message in reversed((history or [])[-self.settings.MAX_HISTORY_MESSAGES:]):
            text = str(message.content)
            if len(text) > remaining:
                break
            bounded.append(message)
            remaining -= len(text)
        with llm_turn(self.settings):
            return self.pipeline.respond(query, history=list(reversed(bounded)))
