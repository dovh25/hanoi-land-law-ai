"""Local SQLite export and validated filesystem import; never indexes Qdrant."""
from pathlib import Path
from datetime import datetime, timezone
import os
import shutil
import tempfile

from sqlalchemy import select
from backend.db.models.legal import CorpusRelease, CorpusReleaseDocument, ProvisionVersion
from backend.services.legal_service import release_fingerprint
from batch.contracts import VIETNAMESE_SPEC, SourceRecord, digest, canonical
from batch.files import export_input, iter_records, validate_input, validate_output, file_hash, atomic_bytes


def checked_release(session, identifier):
    release = session.get(CorpusRelease, identifier)
    if (release is None or release.published_at is None
            or release.manifest_sha256 != release_fingerprint(session, identifier)):
        raise ValueError("Expected a sealed, intact local corpus release")
    return release


def export_release(session, release_id, destination, *, model=VIETNAMESE_SPEC):
    release = checked_release(session, release_id)
    rows = session.scalars(select(ProvisionVersion).join(
        CorpusReleaseDocument, CorpusReleaseDocument.document_version_id == ProvisionVersion.document_version_id
    ).where(CorpusReleaseDocument.release_id == release_id).order_by(ProvisionVersion.id)).yield_per(128)
    def records():
        for row in rows:
            yield SourceRecord(chunk_id=digest(canonical([row.id, row.text_sha256, model.preprocessing_version])),
                document_version_id=row.document_version_id, provision_version_id=row.id,
                text=row.text, text_sha256=row.text_sha256)
    return export_input(destination, records(), release_id=release_id,
                        release_sha256=release.manifest_sha256,
                        is_synthetic=release.is_synthetic, model=model)


def validate_local_provenance(session, input_directory):
    manifest = validate_input(input_directory)
    release = checked_release(session, manifest.corpus_release_id)
    if manifest.corpus_release_sha256 != release.manifest_sha256 or manifest.is_synthetic != release.is_synthetic:
        raise ValueError("Batch does not match the local corpus release")
    for row in iter_records(input_directory, manifest):
        pv = session.get(ProvisionVersion, row.provision_version_id)
        if pv is None or pv.document_version_id != row.document_version_id:
            raise ValueError("Chunk provenance/text differs from local canonical metadata")
        member = session.get(CorpusReleaseDocument, (release.id, pv.document_id))
        if row.chunker_version is None:
            if any(value is not None for value in (row.source_start, row.source_end, row.context, row.source_text_sha256, row.tokenizer_id)):
                raise ValueError("Incomplete chunk provenance; re-export a complete Phase C span")
            if row.text_sha256 != pv.text_sha256 or row.text != pv.text:
                raise ValueError("Whole-provision text differs from canonical metadata")
            expected_id = digest(canonical([pv.id, pv.text_sha256, manifest.model.preprocessing_version]))
        else:
            from preprocess.legal_chunking import CHUNKER_VERSION, ByteBudget, chunk_id, provision_context
            if (row.chunker_version != CHUNKER_VERSION or row.source_start is None or row.source_end is None
                    or not row.source_start < row.source_end <= len(pv.text)
                    or row.source_text_sha256 != pv.text_sha256 or row.context != provision_context(session, pv)):
                raise ValueError("Chunk span/heading/source hash is incompatible; restore the local export")
            from batch.contracts import MODEL_ID, MODEL_REVISION
            if row.tokenizer_id not in {ByteBudget.identity, f"{MODEL_ID}@{MODEL_REVISION}"}:
                raise ValueError("Unknown tokenizer policy; re-export with the reviewed chunker")
            if not manifest.is_synthetic and row.tokenizer_id == ByteBudget.identity:
                raise ValueError("Real chunks require the pinned tokenizer policy")
            if row.text != row.context + "\n" + pv.text[row.source_start:row.source_end]:
                raise ValueError("Chunk contents differ from canonical source span")
            expected_id = chunk_id(pv.id, pv.text_sha256, row.source_start, row.source_end,
                row.context, row.tokenizer_id, manifest.model.preprocessing_version)
        if member is None or member.document_version_id != pv.document_version_id or row.chunk_id != expected_id:
            raise ValueError("Chunk is outside the pinned release or has an incompatible ID")
    return manifest


def import_output(session, input_directory, output_directory, destination):
    """Validate against local source-of-truth, copy only artifacts, atomically publish receipt."""
    manifest = validate_local_provenance(session, input_directory)
    output = validate_output(input_directory, output_directory)
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError("Refusing symlink import directory")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / manifest.batch_id
    if target.exists():
        if target.is_symlink():
            raise ValueError("Refusing symlink import")
        validate_local_provenance(session, target / "input")
        validate_output(target / "input", target / "output")
        if file_hash(target / "output/output.json") != file_hash(Path(output_directory) / "output.json"):
            raise ValueError("Import already exists with different output; never overwrite")
        return target
    with tempfile.TemporaryDirectory(prefix=".import-", dir=destination) as temporary:
        stage = Path(temporary) / "artifact"
        (stage / "input").mkdir(parents=True)
        (stage / "output").mkdir()
        for name in ("input.json", "records.jsonl"):
            shutil.copyfile(Path(input_directory) / name, stage / "input" / name)
        for index, name in enumerate(output.shards):
            shutil.copyfile(Path(output_directory) / name, stage / "output" / name)
            vector_name = f"vectors-{index:05d}.npy"
            shutil.copyfile(Path(output_directory) / vector_name, stage / "output" / vector_name)
        shutil.copyfile(Path(output_directory) / "output.json", stage / "output/output.json")
        validate_local_provenance(session, stage / "input")
        validate_output(stage / "input", stage / "output")
        receipt = dict(batch_id=manifest.batch_id, corpus_release_id=manifest.corpus_release_id,
            model=manifest.model.model_dump(), output_sha256=file_hash(stage / "output/output.json"),
            imported_at=datetime.now(timezone.utc).isoformat(), indexed=False)
        atomic_bytes(stage / "receipt.json", (canonical(receipt) + "\n").encode())
        os.rename(stage, target)
    return target
