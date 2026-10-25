import json
import shutil
import stat
import sys
import types
import zipfile
from pathlib import Path
from unittest.mock import Mock

import nbformat
import numpy as np
import pytest

from batch.archive import extract_zip
from batch.colab import pack_colab, unpack_input, package_output, validate_package, receive_colab, output_name
from batch.contracts import canonical
from batch.embedding import SyntheticEncoder
from batch.files import file_hash, validate_input
from batch.smoke import smoke
from batch.worker import run_batch


@pytest.fixture
def exchange(tmp_path):
    source = tmp_path / "smoke"
    smoke(source)
    root = tmp_path / "exchange"
    report = pack_colab(source / "input", root)
    return source, root, report


def test_one_input_zip_complete_and_idempotent(exchange, tmp_path):
    source, root, report = exchange
    archive = root / "upload-to-colab/embedding-input.zip"
    assert report["sha256"] == file_hash(archive)
    assert pack_colab(source / "input", root) == report
    extracted = unpack_input(archive, tmp_path / "remote-input")
    assert validate_input(extracted) == validate_input(source / "input")
    with zipfile.ZipFile(archive) as z:
        assert "batch/embedding.py" in z.namelist()
        assert not any('.env' in n or 'backend/' in n or '.sqlite' in n for n in z.namelist())
    other = pack_colab(source / 'input', tmp_path / 'other-exchange')
    assert other['sha256'] == report['sha256']


def test_complete_output_validation_and_verify_cli_contract(exchange):
    source, root, _ = exchange
    archive = root / "download-from-colab/embedding-output.zip"
    summary = package_output(source / "input", source / "output", archive, shard_size=2)
    assert summary["status"] == "complete" and summary["processed_records"] == 5
    result = receive_colab(root, verify_only=True)
    assert result["status"] == "complete" and not result["indexed"]
    with zipfile.ZipFile(archive) as z:
        names = set(z.namelist())
        assert {"exchange.json", "output.json", "execution-report.json", "processing-summary.json", "failed-records.json"} <= names
        assert "records.jsonl" not in names
    assert json.loads((root / "reports/verify-colab.json").read_text())["status"] == "complete"


def test_partial_output_verified_never_imported_and_resumes(exchange, tmp_path):
    source, root, _ = exchange
    output = tmp_path / "interrupted"
    encoder = SyntheticEncoder(); original = encoder.encode
    encoder.encode = Mock(side_effect=[original(["SYNTHETIC smoke record 0; not legal text.", "SYNTHETIC smoke record 1; not legal text."]), RuntimeError('SYNTHETIC interrupted')])
    with pytest.raises(RuntimeError): run_batch(source / "input", output, encoder, shard_size=2)
    archive = root / "download-from-colab/embedding-output.zip"
    result = package_output(source / "input", output, archive, shard_size=2, failure_code="RuntimeError")
    assert result["status"] == "partial" and result["processed_records"] == 2
    received = receive_colab(root)
    assert received["status"] == "partial"
    assert not (root / "extracted/verified-imports").exists()
    restored = extract_zip(archive, tmp_path / "restored", output_name)
    assert validate_package(source / "input", restored)["missing_records"] == 3
    run_batch(source / "input", restored, SyntheticEncoder(), shard_size=2)
    done = package_output(source / "input", restored, tmp_path / "complete.zip", shard_size=2)
    assert done["status"] == "complete"


def test_zero_progress_package_is_explicit_partial(exchange, tmp_path):
    source, _, _ = exchange
    result = package_output(source / "input", tmp_path / "missing-output", tmp_path / "zero.zip", shard_size=2)
    assert result["processed_records"] == 0 and result["missing_records"] == 5 and result["status"] == "partial"


@pytest.mark.parametrize("name", ["../records.jsonl", "/records.jsonl", "nested/records.jsonl", "..\\records.jsonl", ".env", "credentials.json"])
def test_web_zip_traversal_and_unexpected_entries_rejected(tmp_path, name):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as z: z.writestr(name, 'SYNTHETIC')
    with pytest.raises(ValueError): unpack_input(archive, tmp_path / "extracted")
    assert not (tmp_path / "extracted").exists()


def test_symlink_and_duplicate_zip_rejected(tmp_path):
    archive = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo('output.json'); info.create_system = 3; info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as z: z.writestr(info, '../outside')
    with pytest.raises(ValueError): extract_zip(archive, tmp_path / "symlink", output_name)
    archive = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr('output.json', '{}')
        with pytest.warns(UserWarning): z.writestr('output.json', '{}')
    with pytest.raises(ValueError): extract_zip(archive, tmp_path / "duplicate", output_name)


def test_input_bundle_checksum_mismatch(exchange, tmp_path):
    _, root, _ = exchange
    source = root / 'upload-to-colab/embedding-input.zip'
    target = tmp_path / 'bad-input.zip'
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(target, 'w') as new:
        for name in old.namelist():
            new.writestr(name, b'SYNTHETIC changed bytes' if name == 'records.jsonl' else old.read(name))
    with pytest.raises(ValueError, match='checksum'): unpack_input(target, tmp_path / 'bad-input')


def test_rejected_output_writes_actionable_report(exchange):
    _, root, _ = exchange
    archive = root / 'download-from-colab/embedding-output.zip'
    with zipfile.ZipFile(archive, 'w') as z: z.writestr('.env', 'SYNTHETIC not a real secret')
    with pytest.raises(ValueError): receive_colab(root, verify_only=True)
    result = json.loads((root / 'reports/verify-colab.json').read_text())
    assert result['status'] == 'rejected' and result['action'] and not result['indexed']


def test_archive_size_and_count_limits(tmp_path, monkeypatch):
    import batch.archive as gate
    archive = tmp_path / "large.zip"
    with zipfile.ZipFile(archive, "w") as z: z.writestr('output.json', '12345')
    monkeypatch.setattr(gate, 'MAX_BYTES', 4)
    with pytest.raises(ValueError): extract_zip(archive, tmp_path / "large", output_name)
    monkeypatch.setattr(gate, 'MAX_BYTES', 100)
    monkeypatch.setattr(gate, 'MAX_FILES', 0)
    with pytest.raises(ValueError): extract_zip(archive, tmp_path / "many", output_name)


@pytest.mark.parametrize("mutation", ["checksum", "revision", "release", "missing", "duplicate", "nan", "inf", "dimension", "dtype"])
def test_result_rejection_even_with_self_consistent_envelope(exchange, tmp_path, mutation):
    source, _, _ = exchange
    archive = tmp_path / "output.zip"
    package_output(source / "input", source / "output", archive, shard_size=2)
    extracted = extract_zip(archive, tmp_path / "result", output_name)
    envelope = json.loads((extracted / "exchange.json").read_text())
    shard_path = extracted / "shard-00000.json"
    shard = json.loads(shard_path.read_text())
    if mutation == "checksum":
        (extracted / "vectors-00000.npy").write_bytes(b'invalid')
    elif mutation == "revision": envelope["model"]["model_revision"] = "f" * 40
    elif mutation == "release": envelope["corpus_release_id"] = "wrong"
    elif mutation in {"duplicate", "missing"}:
        shard["chunk_ids"] = [shard["chunk_ids"][0]] * 2 if mutation == "duplicate" else shard["chunk_ids"][:1]
    else:
        path = extracted / "vectors-00000.npy"
        vectors = np.load(path, allow_pickle=False)
        if mutation == "nan": vectors[0, 0] = np.nan
        elif mutation == "inf": vectors[0, 0] = np.inf
        elif mutation == "dimension": vectors = vectors[:, :4]
        elif mutation == "dtype": vectors = vectors.astype(np.float64)
        np.save(path, vectors, allow_pickle=False)
        shard["vectors_sha256"] = file_hash(path)
        envelope["files"][path.name] = file_hash(path)
    shard_path.write_text(json.dumps(shard))
    envelope["files"][shard_path.name] = file_hash(shard_path)
    (extracted / "exchange.json").write_text(json.dumps(envelope))
    with pytest.raises(ValueError): validate_package(source / "input", extracted)


def test_gpu_oom_retries_only_inference_batch_size(exchange, tmp_path, monkeypatch):
    source, _, _ = exchange
    encoder = SyntheticEncoder(); original = encoder.encode
    calls = []
    def oom(texts, *, batch_size):
        calls.append(batch_size)
        if batch_size > 1: raise RuntimeError("CUDA out of memory")
        return original(texts)
    encoder.encode = oom
    monkeypatch.setitem(sys.modules, 'torch', types.SimpleNamespace(cuda=types.SimpleNamespace(empty_cache=lambda: None)))
    run_batch(source / "input", tmp_path / "output", encoder, shard_size=2, inference_batch_size=4)
    assert calls[:3] == [4, 2, 1]


def test_notebook_full_synthetic_browser_transport_mock(exchange, tmp_path, monkeypatch):
    """Execute notebook code; browser transport is mocked, never claimed as real Colab."""
    source, root, report = exchange
    payload = (root / "upload-to-colab/embedding-input.zip").read_bytes()
    downloaded = []
    def upload():
        Path('embedding-input.zip').write_bytes(payload)
        return {'embedding-input.zip': payload}
    def download(path): downloaded.append(Path(path).read_bytes())
    colab = types.ModuleType('google.colab'); colab.files = types.SimpleNamespace(upload=upload, download=download)
    monkeypatch.setitem(sys.modules, 'google.colab', colab)
    monkeypatch.chdir(tmp_path)
    notebook = nbformat.read(Path(__file__).resolve().parents[1] / 'notebooks/embedding_batch.ipynb', as_version=4)
    scope = {}
    before = sys.path[:]
    try:
        for cell in notebook.cells:
            if cell.cell_type != 'code': continue
            exec(compile(cell.source, cell.id, 'exec'), scope)
            if cell.id == 'controls': scope['EXPECTED_INPUT_SHA256'] = report['sha256']
    finally:
        sys.path[:] = before
    assert len(downloaded) == 1
    (root / 'download-from-colab/embedding-output.zip').write_bytes(downloaded[0])
    assert receive_colab(root, verify_only=True)['status'] == 'complete'
