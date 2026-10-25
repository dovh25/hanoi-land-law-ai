"""One-ZIP Colab Web exchange, wrapping the unchanged Phase B vector contracts."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

from batch.archive import extract_zip, safe_root, write_member
from batch.contracts import canonical, digest
from batch.files import (checked_file, file_hash, validate_input, validate_output,
                         record_batches, validate_shard, atomic_bytes)
from batch.worker import package_versions

CODE_FILES = ("__init__.py", "contracts.py", "files.py", "embedding.py", "worker.py",
              "archive.py", "colab.py", "smoke.py", "transfer.py", "rerank.py")
INPUT_NAMES = {"input.json", "records.jsonl", "bundle.json", "colab-requirements.txt", "LICENSE",
               *("batch/" + name for name in CODE_FILES)}
REPORTS = {"execution-report.json", "processing-summary.json", "failed-records.json"}


def output_name(name):
    return name in {"exchange.json", "output.json", *REPORTS} or bool(re.fullmatch(r"(?:shard-\d{5}\.json|vectors-\d{5}\.npy)", name))


def json_file(root, name):
    path = checked_file(root, name)
    if path.stat().st_size > 4 * 1024 * 1024: raise ValueError("Metadata too large; regenerate bounded package")
    return json.loads(path.read_text())


def checksum_set(root, envelope, envelope_name):
    if not isinstance(envelope.get("files"), dict): raise ValueError("Checksum manifest missing; regenerate package")
    allowed_directories = {str(Path(name).parent) for name in envelope["files"] if str(Path(name).parent) != "."}
    if any(p.is_symlink() or (p.is_dir() and p.relative_to(root).as_posix() not in allowed_directories) for p in root.rglob('*')):
        raise ValueError("Unexpected directory/symlink in extracted package; restore the original ZIP")
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != set(envelope["files"]) | {envelope_name}:
        raise ValueError("Unexpected/missing package files; do not add files to exchange archives")
    for name, expected in envelope["files"].items():
        path = root / name
        if path.is_symlink() or file_hash(path) != expected:
            raise ValueError("Package checksum mismatch; recopy the original ZIP and retry")


def pack_colab(input_directory, exchange="colab-exchange"):
    manifest = validate_input(input_directory)
    root = safe_root(exchange)
    for name in ("upload-to-colab", "download-from-colab", "extracted", "reports"):
        safe_root(root / name).mkdir(parents=True, exist_ok=True)
    archive = safe_root(root / "upload-to-colab/embedding-input.zip")
    retained = safe_root(root / "extracted" / ("input-" + manifest.batch_id))
    if retained.exists():
        if validate_input(retained) != manifest: raise ValueError("Retained input conflicts; restore local export")
        if file_hash(retained / "input.json") != file_hash(Path(input_directory) / "input.json"):
            raise ValueError("Input encoding changed; retain the exact original manifest")
    else:
        retained.mkdir()
        for name in ("input.json", "records.jsonl"):
            shutil.copyfile(checked_file(input_directory, name), retained / name)
    if archive.exists():
        # Never replace a previous upload silently.
        with tempfile.TemporaryDirectory(dir=root / "extracted") as tmp:
            extracted = unpack_input(archive, Path(tmp) / "input")
            if file_hash(extracted / "input.json") != file_hash(retained / "input.json"):
                raise ValueError("Previous embedding-input.zip exists; archive it outside upload-to-colab before preparing a new batch")
            repository = Path(__file__).resolve().parents[1]
            if any(file_hash(extracted / "batch" / name) != file_hash(repository / "batch" / name) for name in CODE_FILES):
                raise ValueError("Previous input ZIP contains older compute code; preserve it and repack into the standard filename")
    else:
        repository = Path(__file__).resolve().parents[1]
        files = {name: checked_file(retained, name) for name in ("input.json", "records.jsonl")}
        files.update({"batch/" + name: repository / "batch" / name for name in CODE_FILES})
        files.update({"colab-requirements.txt": repository / "notebooks/colab-requirements.txt", "LICENSE": repository / "LICENSE"})
        bundle = dict(schema_version=1, batch_id=manifest.batch_id, files={name: file_hash(path) for name, path in files.items()})
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
            for name, path in files.items():
                safe_root(path); write_member(output, name, path=path)
            write_member(output, "bundle.json", data=(canonical(bundle) + "\n").encode())
    atomic_bytes(root / "extracted/active-input.json", (canonical({"batch_id": manifest.batch_id}) + "\n").encode())
    result = dict(status="ready", batch_id=manifest.batch_id, archive=str(archive), sha256=file_hash(archive),
                  record_count=manifest.record_count, model=manifest.model.model_dump())
    atomic_bytes(root / "reports/pack-colab.json", (canonical(result) + "\n").encode())
    return result


def unpack_input(archive, destination):
    root = extract_zip(archive, destination, lambda name: name in INPUT_NAMES)
    bundle = json_file(root, "bundle.json")
    if bundle.get("schema_version") != 1: raise ValueError("Unsupported bundle; update notebook and regenerate package")
    checksum_set(root, bundle, "bundle.json")
    if set(bundle["files"]) != INPUT_NAMES - {"bundle.json"}: raise ValueError("Input code/data allowlist differs; regenerate package")
    manifest = validate_input(root)
    if manifest.batch_id != bundle.get("batch_id"): raise ValueError("Bundle belongs to another batch")
    return root


def checkpoint_status(input_directory, output_directory, shard_size):
    manifest = validate_input(input_directory)
    if not isinstance(shard_size, int) or not 1 <= shard_size <= 128: raise ValueError("Invalid checkpoint layout; restore original shard size")
    output_directory = Path(output_directory)
    input_sha = file_hash(checked_file(input_directory, "input.json"))
    files, completed, missing = [], [], []
    for index, rows in enumerate(record_batches(input_directory, manifest, shard_size)):
        name = f"shard-{index:05d}.json"
        if (output_directory / name).exists():
            validate_shard(output_directory, name, manifest, input_sha, rows, index)
            files.extend([name, f"vectors-{index:05d}.npy"])
            completed.extend(row.chunk_id for row in rows)
        else:
            missing.extend(row.chunk_id for row in rows)
    expected_sidecars = {f"shard-{i:05d}.json" for i, _ in enumerate(record_batches(input_directory, manifest, shard_size))}
    if any(p.name not in expected_sidecars for p in output_directory.glob("shard-*.json")):
        raise ValueError("Extra checkpoints detected; restore output from the matching source batch")
    if (output_directory / "output.json").exists():
        output = validate_output(input_directory, output_directory)
        if output.shard_size != shard_size: raise ValueError("Shard size changed; restore original checkpoint layout")
        files.append("output.json")
    complete = not missing and "output.json" in files
    return manifest, files, completed, missing, complete


def package_output(input_directory, output_directory, archive, *, shard_size=32, execution=None, failure_code=None):
    """Called even after OOM/interruption; only verified finished shards are packaged."""
    manifest, names, completed, missing, complete = checkpoint_status(input_directory, output_directory, shard_size)
    execution = execution or {"device": "cpu", "gpu_name": None, "vram_bytes": None, "real_model_inference": False}
    # Explicit allowlist: never serialize arbitrary exception text, environment, or corpus text.
    allowed_execution = {"device", "gpu_name", "vram_bytes", "free_vram_bytes", "real_model_inference", "elapsed_seconds"}
    if set(execution) - allowed_execution: raise ValueError("Execution report has unexpected fields")
    report = dict(**execution, model=manifest.model.model_dump(), package_versions=package_versions(),
                  finished_at=datetime.now(timezone.utc).isoformat())
    summary = dict(status="complete" if complete else "partial", expected_records=manifest.record_count,
                   processed_records=len(completed), missing_records=len(missing), indexed=False)
    failures = [dict(chunk_id=value, code=failure_code or "not_processed", action="Restore checkpoints and resume the same batch") for value in missing]
    with tempfile.TemporaryDirectory(prefix="colab-output-") as temporary:
        stage = Path(temporary)
        for name in names: shutil.copyfile(checked_file(output_directory, name), stage / name)
        for name, value in (("execution-report.json", report), ("processing-summary.json", summary), ("failed-records.json", failures)):
            atomic_bytes(stage / name, (canonical(value) + "\n").encode())
        envelope = dict(schema_version=1, batch_id=manifest.batch_id, input_manifest_sha256=file_hash(Path(input_directory) / "input.json"),
            model=manifest.model.model_dump(), corpus_release_id=manifest.corpus_release_id,
            corpus_release_sha256=manifest.corpus_release_sha256, shard_size=shard_size, **summary,
            files={p.name: file_hash(p) for p in stage.iterdir()})
        atomic_bytes(stage / "exchange.json", (canonical(envelope) + "\n").encode())
        validate_package(input_directory, stage)
        safe_root(archive)
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
            for path in sorted(stage.iterdir()): write_member(output, path.name, path=path)
    return envelope


def validate_package(input_directory, directory):
    directory = Path(directory)
    envelope = json_file(directory, "exchange.json")
    if envelope.get("schema_version") != 1: raise ValueError("Unknown output schema; use the current notebook")
    if set(envelope) != {"schema_version", "batch_id", "input_manifest_sha256", "model", "corpus_release_id",
        "corpus_release_sha256", "shard_size", "status", "expected_records", "processed_records", "missing_records", "indexed", "files"}:
        raise ValueError("Unexpected output manifest fields; regenerate with the current notebook")
    if not all(output_name(p.name) for p in directory.iterdir()): raise ValueError("Unexpected output file; recopy the generated ZIP")
    checksum_set(directory, envelope, "exchange.json")
    manifest, names, completed, missing, complete = checkpoint_status(input_directory, directory, envelope.get("shard_size"))
    expected = dict(batch_id=manifest.batch_id, input_manifest_sha256=file_hash(Path(input_directory) / "input.json"),
        model=manifest.model.model_dump(), corpus_release_id=manifest.corpus_release_id,
        corpus_release_sha256=manifest.corpus_release_sha256, status="complete" if complete else "partial",
        expected_records=manifest.record_count, processed_records=len(completed), missing_records=len(missing), indexed=False)
    if any(envelope.get(key) != value for key, value in expected.items()):
        raise ValueError("Output provenance/model/count mismatch; use the original matching batch")
    if set(envelope["files"]) != set(names) | REPORTS:
        raise ValueError("Output has missing or extra vectors/reports; regenerate the result archive")
    summary = json_file(directory, "processing-summary.json")
    if summary != {key: expected[key] for key in ("status", "expected_records", "processed_records", "missing_records", "indexed")}:
        raise ValueError("Processing summary disagrees with verified vectors")
    failures = json_file(directory, "failed-records.json")
    if not isinstance(failures, list) or any(not isinstance(item, dict) or set(item) != {"chunk_id", "code", "action"}
        or not isinstance(item["code"], str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,63}", item["code"])
        or item["action"] != "Restore checkpoints and resume the same batch" for item in failures):
        raise ValueError("Invalid failed-record report schema; regenerate package")
    if [item.get("chunk_id") for item in failures] != missing: raise ValueError("Failed-record report does not match missing IDs")
    execution = json_file(directory, "execution-report.json")
    if (set(execution) - {"device", "gpu_name", "vram_bytes", "free_vram_bytes", "real_model_inference", "elapsed_seconds", "model", "package_versions", "finished_at"}
            or execution.get("device") not in {"cpu", "cuda"}
            or not isinstance(execution.get("real_model_inference"), bool)):
        raise ValueError("Invalid execution report schema; regenerate package")
    if manifest.model.model_id.startswith("SYNTHETIC/") and execution["real_model_inference"]:
        raise ValueError("Synthetic output cannot claim real-model inference")
    if execution.get("model") != manifest.model.model_dump(): raise ValueError("Execution model report differs from input")
    return envelope


def receive_colab(exchange="colab-exchange", *, workspace=None, verify_only=False):
    root = safe_root(exchange)
    archive = safe_root(root / "download-from-colab/embedding-output.zip")
    result = {}
    try:
        active = json_file(root / "extracted", "active-input.json")
        if not re.fullmatch(r"[0-9a-f]{64}", active.get("batch_id", "")): raise ValueError("Active input missing; run pack-colab first")
        source = safe_root(root / "extracted" / ("input-" + active["batch_id"]))
        archive_sha = file_hash(archive)
        target = safe_root(root / "extracted" / ("output-" + archive_sha))
        if not target.exists(): extract_zip(archive, target, output_name)
        envelope = validate_package(source, target)
        result = dict(status=envelope["status"], batch_id=envelope["batch_id"], archive_sha256=archive_sha,
            processed_records=envelope["processed_records"], missing_records=envelope["missing_records"], indexed=False,
            action="Resume the same input/checkpoints; partial output is never imported" if envelope["status"] == "partial" else "Validated; receive-colab --workspace imports against canonical SQLite")
        if not verify_only and envelope["status"] == "complete":
            if workspace is None: raise ValueError("Pass --workspace pointing to the isolated canonical ingestion workspace; verify-colab does not need it")
            from preprocess.offline_ingestion import database, validate_workspace_export
            from batch.local import import_output
            validate_workspace_export(workspace, source)
            with database(workspace) as factory, factory.begin() as session:
                result["receipt_directory"] = str(import_output(session, source, target, root / "extracted/verified-imports"))
            result["action"] = "Imported verified artifacts; indexed=false, no retrieval publication"
        return result
    except Exception as exc:
        result = dict(status="rejected", error=type(exc).__name__, indexed=False,
                      action=str(exc) if isinstance(exc, ValueError) else "Check the input/output ZIP paths and regenerate the matching package")
        raise ValueError(result["action"]) from None
    finally:
        reports = safe_root(root / "reports"); reports.mkdir(parents=True, exist_ok=True)
        atomic_bytes(reports / ("verify-colab.json" if verify_only else "receive-colab.json"), (canonical(result) + "\n").encode())
