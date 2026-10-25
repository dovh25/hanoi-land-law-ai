"""Benchmark the same pinned dense encoder as local CPU queries and Colab."""
from batch.contracts import MODEL_ID
from batch.embedding import VietnameseEncoder
from backend.core.config import config
from backend.core.models import select_device
from .base import EmbeddingOutput, EmbeddingProvider


class VietnameseProvider(EmbeddingProvider):
    def __init__(self, model_name=MODEL_ID, device=None):
        if model_name != MODEL_ID:
            raise ValueError("Checkpoint changes require a model-contract migration")
        self.encoder = VietnameseEncoder(select_device(device or config.EMBEDDING_DEVICE),
                                         allow_downloads=config.ALLOW_MODEL_DOWNLOADS)

    @property
    def name(self):
        return "vietnamese"

    @property
    def model_name(self):
        return MODEL_ID

    @property
    def dense_dim(self):
        return self.encoder.spec.dimension

    @property
    def supports_sparse(self):
        return False

    def encode(self, texts, return_dense=True, return_sparse=False, batch_size=32, show_progress=True):
        if return_sparse:
            raise ValueError("Learned-sparse output is not supported by this checkpoint")
        return EmbeddingOutput(dense=self.encoder.encode(texts, batch_size=batch_size).tolist() if return_dense else None)
