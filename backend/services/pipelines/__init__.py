"""Load optional ML implementations only when selected."""
from importlib import import_module
from .base import RAGPipeline

_MODULES = {
    "AgenticRAGPipeline": "agentic_rag_pipeline",
    "GTEPipeline": "gte_pipeline",
    "VietnameseEmbeddingPipeline": "vietnamese_embedding_pipeline",
    "BGEM3Pipeline": "bge_m3_pipeline",
}
__all__ = ["RAGPipeline", *_MODULES]


def __getattr__(name):
    if name not in _MODULES:
        raise AttributeError(name)
    return getattr(import_module(f"{__name__}.{_MODULES[name]}"), name)
