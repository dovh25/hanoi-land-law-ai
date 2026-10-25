"""Small checked metadata + JSONL input + bounded float32 NPY shards."""
from pathlib import Path
import hashlib
import json
import os
import tempfile

import numpy as np
from batch.contracts import (
    InputManifest, OutputManifest, SourceRecord, Shard, canonical, digest, validate_policy,
)


def checked_file(root, name):
    root = Path(root)
    if not name or Path(name).name != name or name in {".", ".."}:
        raise ValueError("Artifact filenames must be simple basenames")
    path = root / name
    if path.is_symlink() or not path.is_file() or path.resolve().parent != root.resolve():
        raise ValueError("Artifact file is missing, nonregular, or outside the artifact directory")
    return path


def file_hash(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def read_contract(root, name, kind):
    path = checked_file(root, name)
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Metadata exceeds the supported size")
    return kind.model_validate_json(path.read_bytes())


def atomic_bytes(path, content):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Refusing symlink output")
    fd, temporary = tempfile.mkstemp(prefix=".partial-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def write_contract(path, value):
    atomic_bytes(path, (canonical(value.model_dump(mode="json")) + "\n").encode())


def export_input(destination, records, *, release_id, release_sha256, is_synthetic, model):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    seen = set()
    hasher = hashlib.sha256()
    total_bytes = 0
    with (destination / "records.jsonl").open("xb") as handle:
        for record in records:
            record = SourceRecord.model_validate(record)
            if record.chunk_id in seen or digest(record.text) != record.text_sha256:
                raise ValueError("Duplicate chunk ID or input text hash mismatch")
            seen.add(record.chunk_id)
            data = (canonical(record.model_dump(mode="json")) + "\n").encode()
            total_bytes += len(data)
            if len(seen) > 10000 or total_bytes > 64 * 1024 * 1024:
                raise ValueError("Export a smaller source batch (maximum 10000 records / 64 MiB)")
            handle.write(data)
            hasher.update(data)
        handle.flush()
        os.fsync(handle.fileno())
    values = dict(schema_version=1, corpus_release_id=release_id, corpus_release_sha256=release_sha256,
                  is_synthetic=is_synthetic, model=model.model_dump(), records_file="records.jsonl",
                  records_sha256=hasher.hexdigest(), record_count=len(seen))
    manifest = InputManifest(batch_id=digest(canonical(values)), **values)
    validate_policy(manifest)
    write_contract(destination / "input.json", manifest)
    return manifest


def iter_records(directory, manifest):
    path = checked_file(directory, manifest.records_file)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(line) > 128 * 1024 or not line.strip():
                raise ValueError("Invalid or oversized JSONL record")
            yield SourceRecord.model_validate_json(line)


def validate_input(directory):
    manifest = read_contract(directory, "input.json", InputManifest)
    validate_policy(manifest)
    values = manifest.model_dump(mode="json")
    values.pop("batch_id")
    if digest(canonical(values)) != manifest.batch_id:
        raise ValueError("Source batch identity mismatch")
    path = checked_file(directory, manifest.records_file)
    if path.stat().st_size > 64 * 1024 * 1024 or file_hash(path) != manifest.records_sha256:
        raise ValueError("Input checksum or size mismatch")
    seen = set()
    for row in iter_records(directory, manifest):
        if row.chunk_id in seen or digest(row.text) != row.text_sha256:
            raise ValueError("Duplicate chunk ID or text hash mismatch")
        seen.add(row.chunk_id)
        if len(seen) > manifest.record_count:
            raise ValueError("Input record count mismatch")
    if len(seen) != manifest.record_count:
        raise ValueError("Input record count mismatch")
    return manifest


def record_batches(directory, manifest, size):
    batch = []
    for row in iter_records(directory, manifest):
        batch.append(row)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def validate_shard(directory, name, manifest, input_sha, rows, index):
    shard = read_contract(directory, name, Shard)
    expected_vectors = f"vectors-{index:05d}.npy"
    if (shard.batch_id != manifest.batch_id or shard.input_manifest_sha256 != input_sha
            or shard.model != manifest.model or shard.index != index
            or shard.chunk_ids != [r.chunk_id for r in rows]
            or shard.text_hashes != [r.text_sha256 for r in rows]
            or shard.processed_records != len(rows) or shard.vectors_file != expected_vectors):
        raise ValueError("Incompatible shard provenance, IDs, count, or model")
    path = checked_file(directory, expected_vectors)
    if path.stat().st_size > len(rows) * manifest.model.dimension * 4 + 8192:
        raise ValueError("Unexpected vector file size")
    if file_hash(path) != shard.vectors_sha256:
        raise ValueError("Vector checksum mismatch")
    vectors = np.load(path, allow_pickle=False, mmap_mode="r", max_header_size=1024)
    validate_vectors(vectors, len(rows), manifest.model)
    return shard


def validate_vectors(vectors, count, model):
    if not isinstance(vectors, np.ndarray) or vectors.dtype != np.dtype("float32") or vectors.shape != (count, model.dimension):
        raise ValueError("Vector dimension, count, or dtype mismatch")
    if not np.isfinite(vectors).all():
        raise ValueError("Nonfinite embedding values")
    if model.normalized and not np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-4):
        raise ValueError("Embedding normalization mismatch")


def validate_output(input_directory, output_directory):
    manifest = validate_input(input_directory)
    output = read_contract(output_directory, "output.json", OutputManifest)
    input_sha = file_hash(checked_file(input_directory, "input.json"))
    if output.batch_id != manifest.batch_id or output.input_manifest_sha256 != input_sha:
        raise ValueError("Output belongs to a different source batch/release")
    names = []
    count = 0
    for index, rows in enumerate(record_batches(input_directory, manifest, output.shard_size)):
        name = f"shard-{index:05d}.json"
        path = checked_file(output_directory, name)
        if output.shards.get(name) != file_hash(path):
            raise ValueError("Shard metadata checksum mismatch")
        validate_shard(output_directory, name, manifest, input_sha, rows, index)
        names.append(name)
        count += len(rows)
    if set(names) != set(output.shards) or count != manifest.record_count or output.processed_records != count:
        raise ValueError("Missing, duplicate, or extra output records/shards")
    return output
