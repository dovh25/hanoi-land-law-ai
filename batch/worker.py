"""Interactive bounded execution with verified per-shard checkpoints. No servers."""
from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
from io import BytesIO

import numpy as np
from batch.contracts import OutputManifest, Shard
from batch.files import (
    atomic_bytes, checked_file, file_hash, record_batches, validate_input,
    validate_output, validate_shard, validate_vectors, write_contract,
)


def package_versions():
    result = {}
    for name in ("numpy", "sentence-transformers", "transformers", "torch", "huggingface-hub", "tokenizers"):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = "not-installed"
    return result


def run_batch(input_directory, output_directory, encoder, *, shard_size=32, inference_batch_size=4):
    if not 1 <= shard_size <= 128:
        raise ValueError("Shard size must be between 1 and 128")
    if not 1 <= inference_batch_size <= 32:
        raise ValueError("Inference batch size must be between 1 and 32")
    manifest = validate_input(input_directory)
    if encoder.spec != manifest.model:
        raise ValueError("Encoder does not match source batch model contract")
    output_directory = Path(output_directory)
    if output_directory.is_symlink():
        raise ValueError("Refusing symlink output directory")
    output_directory.mkdir(parents=True, exist_ok=True)
    if (output_directory / "output.json").exists():
        return validate_output(input_directory, output_directory)
    input_sha = file_hash(checked_file(input_directory, "input.json"))
    shards = {}
    processed = 0
    for index, rows in enumerate(record_batches(input_directory, manifest, shard_size)):
        name = f"shard-{index:05d}.json"
        sidecar = output_directory / name
        if sidecar.exists():
            validate_shard(output_directory, name, manifest, input_sha, rows, index)
        else:
            while True:
                try:
                    vectors = np.asarray(encoder.encode([r.text for r in rows], batch_size=inference_batch_size))
                    break
                except RuntimeError as exc:
                    if type(exc).__name__ != "OutOfMemoryError" and "CUDA out of memory" not in str(exc):
                        raise
                    if inference_batch_size == 1:
                        raise RuntimeError("CUDA out of memory at batch size 1; save checkpoints, restart runtime, use a larger GPU or reviewed shorter chunks") from None
                    inference_batch_size = max(1, inference_batch_size // 2)
                    import gc
                    gc.collect()
                    # torch is imported only on the actual CUDA failure path.
                    try:
                        import torch
                        torch.cuda.empty_cache()
                    except ImportError:
                        pass
            validate_vectors(vectors, len(rows), manifest.model)
            buffer = BytesIO()
            np.save(buffer, vectors, allow_pickle=False)
            vector_name = f"vectors-{index:05d}.npy"
            atomic_bytes(output_directory / vector_name, buffer.getvalue())
            shard = Shard(batch_id=manifest.batch_id, input_manifest_sha256=input_sha,
                model=manifest.model, index=index, chunk_ids=[r.chunk_id for r in rows],
                text_hashes=[r.text_sha256 for r in rows], vectors_file=vector_name,
                vectors_sha256=file_hash(output_directory / vector_name), processed_records=len(rows),
                inferred_at=datetime.now(timezone.utc).isoformat(), package_versions=package_versions(),
                device=getattr(encoder, "device", "cpu"))
            write_contract(sidecar, shard)
        shards[name] = file_hash(sidecar)
        processed += len(rows)
    output = OutputManifest(batch_id=manifest.batch_id, input_manifest_sha256=input_sha,
                            processed_records=processed, shard_size=shard_size, shards=shards)
    write_contract(output_directory / "output.json", output)
    return validate_output(input_directory, output_directory)
