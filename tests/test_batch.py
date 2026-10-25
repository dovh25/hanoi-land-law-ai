import json
from pathlib import Path
from unittest.mock import Mock
import zipfile

import numpy as np
import pytest

from batch.contracts import SYNTHETIC_SPEC, VIETNAMESE_SPEC, SourceRecord, digest
from batch.embedding import SyntheticEncoder, VietnameseEncoder
from batch.files import export_input, validate_input, validate_output, file_hash
from batch.local import export_release, import_output
from batch.smoke import smoke
from batch.transfer import bundle_code, pack_transfer, unpack_transfer
from batch.worker import run_batch


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "smoke"
    smoke(root)
    return root


def test_synthetic_cpu_smoke_and_resume(workspace):
    result = smoke(workspace)
    assert result.processed_records == 5
    assert len(result.shards) == 3
    encoder = SyntheticEncoder()
    encoder.encode = Mock(side_effect=AssertionError("Completed work must not recompute"))
    run_batch(workspace / "input", workspace / "output", encoder, shard_size=2)
    encoder.encode.assert_not_called()


def test_checkpoint_resume_after_disconnection(workspace, tmp_path):
    output = tmp_path / "interrupted"
    encoder = SyntheticEncoder()
    original = encoder.encode
    calls = 0
    def disconnected(texts, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("SYNTHETIC disconnection")
        return original(texts, **kwargs)
    encoder.encode = disconnected
    with pytest.raises(RuntimeError):
        run_batch(workspace / "input", output, encoder, shard_size=2)
    assert (output / "shard-00000.json").exists()
    assert not (output / "output.json").exists()
    resumed = SyntheticEncoder()
    resumed.encode = Mock(wraps=resumed.encode)
    assert run_batch(workspace / "input", output, resumed, shard_size=2, inference_batch_size=1).processed_records == 5
    assert resumed.encode.call_count == 2


def rewrite_sidecar(root, change):
    path = root / "output/shard-00000.json"
    shard = json.loads(path.read_text())
    change(shard)
    path.write_text(json.dumps(shard))
    output_path = root / "output/output.json"
    output = json.loads(output_path.read_text())
    output["shards"][path.name] = file_hash(path)
    output_path.write_text(json.dumps(output))


@pytest.mark.parametrize("mutation", ["nan", "inf", "dimension", "dtype", "normalization", "count"])
def test_bad_vectors_rejected_even_with_updated_checksums(workspace, mutation):
    path = workspace / "output/vectors-00000.npy"
    vectors = np.load(path, allow_pickle=False)
    if mutation == "nan": vectors[0, 0] = np.nan
    elif mutation == "inf": vectors[0, 0] = np.inf
    elif mutation == "dimension": vectors = np.zeros((2, 9), dtype=np.float32)
    elif mutation == "dtype": vectors = vectors.astype(np.float64)
    elif mutation == "normalization": vectors *= 2
    elif mutation == "count": vectors = vectors[:1]
    np.save(path, vectors, allow_pickle=False)
    rewrite_sidecar(workspace, lambda shard: shard.update(vectors_sha256=file_hash(path)))
    with pytest.raises(ValueError):
        validate_output(workspace / "input", workspace / "output")


@pytest.mark.parametrize("mutation", ["duplicate_ids", "missing_ids", "text_hash", "revision", "count", "path"])
def test_incompatible_sidecars_rejected(workspace, mutation):
    def change(shard):
        if mutation == "duplicate_ids": shard["chunk_ids"][1] = shard["chunk_ids"][0]
        elif mutation == "missing_ids": shard["chunk_ids"].pop()
        elif mutation == "text_hash": shard["text_hashes"][0] = "f" * 64
        elif mutation == "revision": shard["model"]["model_revision"] = "f" * 40
        elif mutation == "count": shard["processed_records"] = 1
        elif mutation == "path": shard["vectors_file"] = "../private.npy"
    rewrite_sidecar(workspace, change)
    with pytest.raises(ValueError):
        validate_output(workspace / "input", workspace / "output")


def test_changed_release_rejected(workspace):
    path = workspace / "input/input.json"
    manifest = json.loads(path.read_text())
    manifest["corpus_release_id"] = "different-release"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        validate_output(workspace / "input", workspace / "output")


def test_duplicate_input_ids_and_bad_text_hashes(tmp_path):
    row = SourceRecord(chunk_id="SYNTHETIC", document_version_id="SYNTHETIC",
        provision_version_id="SYNTHETIC", text="SYNTHETIC", text_sha256=digest("SYNTHETIC"))
    for index, rows in enumerate(([row, row], [row.model_copy(update={"text_sha256": "f" * 64})])):
        with pytest.raises(ValueError):
            export_input(tmp_path / str(index), rows, release_id="SYNTHETIC", release_sha256="0" * 64,
                         is_synthetic=True, model=SYNTHETIC_SPEC)


def test_export_import_round_trip_with_local_release(seeded, tmp_path):
    factory, fixture = seeded
    with factory.begin() as session:
        manifest = export_release(session, fixture["release"].id, tmp_path / "input", model=SYNTHETIC_SPEC)
        assert manifest.record_count == 40
        output = run_batch(tmp_path / "input", tmp_path / "output", SyntheticEncoder(), shard_size=8)
        assert output.processed_records == manifest.record_count
        imported = import_output(session, tmp_path / "input", tmp_path / "output", tmp_path / "imports")
        assert (imported / "receipt.json").is_file()
        assert json.loads((imported / "receipt.json").read_text())["indexed"] is False
        assert import_output(session, tmp_path / "input", tmp_path / "output", tmp_path / "imports") == imported


def test_import_rejects_nonexistent_local_release(legal_db, workspace, tmp_path):
    _, factory = legal_db
    with factory.begin() as session, pytest.raises(ValueError):
        import_output(session, workspace / "input", workspace / "output", tmp_path / "imports")
    assert not (tmp_path / "imports").exists()


def test_data_transfer_round_trip(workspace, tmp_path):
    for kind in ("input", "output"):
        archive = pack_transfer(workspace / kind, tmp_path / (kind + ".zip"), kind)
        unpack_transfer(archive, tmp_path / kind, kind)
    validate_output(tmp_path / "input", tmp_path / "output")


@pytest.mark.parametrize("name", ["../private", "/absolute", "nested/input.json", ".env"])
def test_zip_path_and_secret_file_rejection(tmp_path, name):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(name, "not a real secret")
    with pytest.raises(ValueError):
        unpack_transfer(archive, tmp_path / "unpacked", "input")
    assert not (tmp_path / "unpacked").exists()


def test_compute_bundle_excludes_settings_and_application(tmp_path):
    archive = bundle_code(tmp_path / "code.zip")
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        assert "batch/embedding.py" in names
        assert "colab-requirements.txt" in names
        assert all("backend" not in name and ".env" not in name for name in names)
        assert not any(b"load_dotenv" in source.read(name) for name in names)


def fake_model():
    # MagicMock supports the standard SentenceTransformer module-index interface.
    from unittest.mock import MagicMock
    model = MagicMock()
    model.get_sentence_embedding_dimension.return_value = 1024
    model.__getitem__.return_value.get_config_dict.return_value = {"pooling_mode_cls_token": True, "pooling_mode_mean_tokens": False}
    from types import SimpleNamespace
    pooling = model.__getitem__.return_value
    modules = {0: SimpleNamespace(auto_model=SimpleNamespace(config=SimpleNamespace(model_type="xlm-roberta", hidden_size=1024))),
               1: pooling, 2: type("Normalize", (), {})()}
    model.__getitem__.side_effect = modules.__getitem__
    model.tokenizer.return_value = {"input_ids": [[0, 1, 2]]}
    model.encode.return_value = np.ones((1, 1024), dtype=np.float32) / 32
    return model


def test_shared_encoder_is_lazy_pinned_dense_normalized_and_local_only():
    model = fake_model()
    factory = Mock(return_value=model)
    encoder = VietnameseEncoder("cpu", model_factory=factory)
    factory.assert_not_called()
    output = encoder.encode(["SYNTHETIC"])
    assert output.shape == (1, 1024)
    assert np.allclose(np.linalg.norm(output, axis=1), 1)
    assert factory.call_args.kwargs["revision"] == VIETNAMESE_SPEC.model_revision
    assert factory.call_args.kwargs["trust_remote_code"] is False
    assert factory.call_args.kwargs["local_files_only"] is True
    assert model.encode.call_args.kwargs["normalize_embeddings"] is True


def test_shared_encoder_rejects_silent_truncation():
    model = fake_model()
    model.tokenizer.return_value = {"input_ids": [[0] * 2049]}
    encoder = VietnameseEncoder(model_factory=Mock(return_value=model))
    with pytest.raises(ValueError):
        encoder.encode(["SYNTHETIC oversized tokens"])
    model.encode.assert_not_called()


def test_checkpoint_shape_is_verified_before_caching():
    model = fake_model()
    model.get_sentence_embedding_dimension.return_value = 768
    encoder = VietnameseEncoder(model_factory=Mock(return_value=model))
    for _ in range(2):
        with pytest.raises(ValueError):
            encoder.encode(["SYNTHETIC"])
    assert encoder._model is None


def test_checkpoint_pooling_is_verified_before_encoding():
    model = fake_model()
    model.__getitem__.return_value.get_config_dict.return_value = {"pooling_mode_cls_token": False, "pooling_mode_mean_tokens": True}
    encoder = VietnameseEncoder(model_factory=Mock(return_value=model))
    with pytest.raises(ValueError):
        encoder.encode(["SYNTHETIC"])
    model.encode.assert_not_called()


def test_checkpoint_architecture_is_verified_before_encoding():
    model = fake_model()
    model[0].auto_model.config.model_type = "unreviewed-architecture"
    encoder = VietnameseEncoder(model_factory=Mock(return_value=model))
    with pytest.raises(ValueError, match="architecture"):
        encoder.encode(["SYNTHETIC"])
    model.encode.assert_not_called()


def test_output_manifest_count_and_missing_vector_rejected(workspace):
    path = workspace / "output/output.json"
    original = json.loads(path.read_text())
    changed = dict(original, processed_records=4)
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError):
        validate_output(workspace / "input", workspace / "output")
    path.write_text(json.dumps(original))
    (workspace / "output/vectors-00000.npy").unlink()
    with pytest.raises(ValueError):
        validate_output(workspace / "input", workspace / "output")


def test_reranker_experiment_is_bounded_and_offline():
    from batch.rerank import evaluate_pairs
    predictor = Mock()
    predictor.predict.side_effect = [[0.1, 0.8], [0.3]]
    result = evaluate_pairs(predictor, [["SYNTHETIC query", "SYNTHETIC passage"]] * 3, batch_size=2)
    assert result["ranked_indices"] == [1, 2, 0]
    with pytest.raises(ValueError):
        evaluate_pairs(predictor, [["SYNTHETIC", "SYNTHETIC"]] * 129)
