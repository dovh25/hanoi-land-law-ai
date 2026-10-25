"""Credential-free, weight-free CPU exercise for notebooks and local CLI."""
from pathlib import Path
from batch.contracts import SYNTHETIC_SPEC, SourceRecord, digest
from batch.files import export_input, validate_input
from batch.embedding import SyntheticEncoder
from batch.worker import run_batch


def smoke(workspace):
    workspace = Path(workspace)
    if not workspace.exists():
        workspace.mkdir(parents=True, exist_ok=False)
        rows = [SourceRecord(chunk_id=f"SYNTHETIC-{i}", document_version_id="SYNTHETIC-version",
            provision_version_id=f"SYNTHETIC-provision-{i}", text=f"SYNTHETIC smoke record {i}; not legal text.",
            text_sha256=digest(f"SYNTHETIC smoke record {i}; not legal text.")) for i in range(5)]
        export_input(workspace / "input", rows, release_id="SYNTHETIC-smoke-release",
            release_sha256=digest("SYNTHETIC smoke release"), is_synthetic=True, model=SYNTHETIC_SPEC)
    manifest = validate_input(workspace / "input")
    if manifest.model != SYNTHETIC_SPEC or manifest.record_count != 5:
        raise ValueError("Not the expected synthetic smoke workspace")
    return run_batch(workspace / "input", workspace / "output", SyntheticEncoder(), shard_size=2)
