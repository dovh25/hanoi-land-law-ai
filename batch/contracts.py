"""Versioned, non-pickle interchange contracts. No credentials or application imports."""
import hashlib
import json
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

MODEL_ID = "AITeamVN/Vietnamese_Embedding_v2"
MODEL_REVISION = "18b44161e041bf1d3a333ab5144b5b7b93f914d2"
SHA = r"^[0-9a-f]{64}$"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ModelSpec(Contract):
    model_id: str = Field(min_length=1, max_length=255)
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    dimension: int = Field(ge=1, le=4096)
    dtype: Literal["float32"]
    normalized: bool
    pooling: Literal["cls", "synthetic_hash"]
    max_tokens: int = Field(ge=1, le=2048)
    preprocessing_version: str = Field(min_length=1, max_length=120)
    encoder_version: str = Field(min_length=1, max_length=120)


VIETNAMESE_SPEC = ModelSpec(
    model_id=MODEL_ID, model_revision=MODEL_REVISION, dimension=1024, dtype="float32",
    normalized=True, pooling="cls", max_tokens=2048,
    preprocessing_version="exact-utf8-no-truncation-v1", encoder_version="sentence-transformers-cls-l2-v1",
)
SYNTHETIC_SPEC = ModelSpec(
    model_id="SYNTHETIC/hash-embedding-not-for-retrieval", model_revision="0" * 40,
    dimension=8, dtype="float32", normalized=True, pooling="synthetic_hash", max_tokens=2048,
    preprocessing_version="SYNTHETIC-exact-utf8-v1", encoder_version="SYNTHETIC-cpu-v1",
)


class SourceRecord(Contract):
    chunk_id: str = Field(min_length=1, max_length=255)
    document_version_id: str = Field(min_length=1, max_length=64)
    provision_version_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=16000)
    text_sha256: str = Field(pattern=SHA)
    # Optional Phase C exact-span provenance; absent fields retain Phase B whole-provision semantics.
    source_start: int | None = Field(default=None, ge=0)
    source_end: int | None = Field(default=None, gt=0)
    source_text_sha256: str | None = Field(default=None, pattern=SHA)
    context: str | None = None
    chunker_version: str | None = None
    tokenizer_id: str | None = None


class InputManifest(Contract):
    schema_version: Literal[1] = 1
    batch_id: str = Field(pattern=SHA)
    corpus_release_id: str = Field(min_length=1, max_length=64)
    corpus_release_sha256: str = Field(pattern=SHA)
    is_synthetic: bool
    model: ModelSpec
    records_file: Literal["records.jsonl"] = "records.jsonl"
    records_sha256: str = Field(pattern=SHA)
    record_count: int = Field(ge=1, le=10000)


class Shard(Contract):
    schema_version: Literal[1] = 1
    batch_id: str = Field(pattern=SHA)
    input_manifest_sha256: str = Field(pattern=SHA)
    model: ModelSpec
    index: int = Field(ge=0)
    chunk_ids: list[str]
    text_hashes: list[str]
    vectors_file: str
    vectors_sha256: str = Field(pattern=SHA)
    processed_records: int = Field(ge=1, le=128)
    inferred_at: str
    package_versions: dict[str, str]
    device: Literal["cpu", "cuda", "unknown"] = "unknown"

    @field_validator("inferred_at")
    @classmethod
    def timestamp(cls, value):
        if datetime.fromisoformat(value).tzinfo is None:
            raise ValueError("Inference timestamp requires a timezone")
        return value


class OutputManifest(Contract):
    schema_version: Literal[1] = 1
    batch_id: str = Field(pattern=SHA)
    input_manifest_sha256: str = Field(pattern=SHA)
    processed_records: int = Field(ge=1, le=10000)
    shard_size: int = Field(ge=1, le=128)
    # Filename -> checksum; only deterministic sidecar names are accepted by validation.
    shards: dict[str, str]


def validate_policy(manifest):
    expected = SYNTHETIC_SPEC if manifest.model.model_id == SYNTHETIC_SPEC.model_id else VIETNAMESE_SPEC
    if manifest.model != expected:
        raise ValueError("Unsupported model contract; explicit checkpoint/encoder migration required")
    if expected == SYNTHETIC_SPEC and not manifest.is_synthetic:
        raise ValueError("Synthetic embeddings cannot be associated with real corpus data")
