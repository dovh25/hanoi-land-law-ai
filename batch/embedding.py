"""One shared Vietnamese encoder for local CPU queries and interactive Colab batches."""
import numpy as np
from batch.contracts import VIETNAMESE_SPEC, SYNTHETIC_SPEC, digest


class VietnameseEncoder:
    spec = VIETNAMESE_SPEC

    def __init__(self, device="cpu", *, allow_downloads=False, model_factory=None):
        if device not in {"cpu", "cuda"}:
            raise ValueError("Select cpu or cuda explicitly")
        self.device = device
        self.allow_downloads = allow_downloads
        self.model_factory = model_factory
        self._model = None

    @property
    def model(self):
        if self._model is None:
            factory = self.model_factory
            if factory is None:
                from importlib.metadata import version
                for package, expected in {"sentence-transformers": "5.2.0", "transformers": "4.57.3",
                                          "torch": "2.9.1", "numpy": "2.4.1", "huggingface-hub": "0.36.0"}.items():
                    if version(package).split("+")[0] != expected:
                        raise ValueError("ML package version differs from the pinned encoder contract")
                from sentence_transformers import SentenceTransformer
                factory = SentenceTransformer
            model = factory(self.spec.model_id, revision=self.spec.model_revision,
                            device=self.device, trust_remote_code=False,
                            local_files_only=not self.allow_downloads, token=False)
            model.max_seq_length = self.spec.max_tokens
            if model.get_sentence_embedding_dimension() != self.spec.dimension:
                raise ValueError("Checkpoint dimension differs from pinned contract")
            pooling = model[1].get_config_dict()
            if not pooling.get("pooling_mode_cls_token") or any(
                value for key, value in pooling.items() if key.startswith("pooling_mode_") and key != "pooling_mode_cls_token"
            ):
                raise ValueError("Checkpoint pooling differs from verified CLS contract")
            architecture = model[0].auto_model.config
            if (architecture.model_type != "xlm-roberta" or architecture.hidden_size != self.spec.dimension
                    or type(model[2]).__name__ != "Normalize"):
                raise ValueError("Checkpoint architecture/module chain differs from reviewed XLM-R/CLS/Normalize configuration")
            self._model = model
        return self._model

    @property
    def tokenizer(self):
        return self.model.tokenizer

    def encode(self, texts, *, batch_size=16):
        if not texts:
            return np.empty((0, self.spec.dimension), dtype=np.float32)
        tokens = self.tokenizer(texts, truncation=False, add_special_tokens=True)["input_ids"]
        if any(len(row) > self.spec.max_tokens for row in tokens):
            raise ValueError("Input exceeds the verified token policy; chunk locally, do not silently truncate")
        return np.asarray(self.model.encode(
            texts, batch_size=batch_size, normalize_embeddings=True, precision="float32",
            convert_to_numpy=True, show_progress_bar=False,
        ), dtype=np.float32)


class SyntheticEncoder:
    """Deterministic CPU smoke data, NOT a retrieval model or approximation of the checkpoint."""
    spec = SYNTHETIC_SPEC

    def encode(self, texts, *, batch_size=16):
        rows = []
        for text in texts:
            values = np.frombuffer(bytes.fromhex(digest(text)), dtype=np.uint8)[:self.spec.dimension].astype(np.float32) + 1
            rows.append(values / np.linalg.norm(values))
        return np.asarray(rows, dtype=np.float32)
