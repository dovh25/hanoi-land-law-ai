import json
from pathlib import Path
import unicodedata
from types import SimpleNamespace

import pytest
from sqlalchemy import select, func

from batch.contracts import SYNTHETIC_SPEC, VIETNAMESE_SPEC, canonical, digest
from batch.files import file_hash, validate_input
from backend.db.models.legal import LegalDocument, SourceArtifact, DocumentVersion, ProvisionVersion
from preprocess.legal_parser import normalize, extract, hierarchy, Block, ExtractionError
from preprocess.legal_chunking import ByteBudget, chunk_provision
from preprocess.offline_ingestion import initialize, ingest, review, seal, export, database, load_stage, review_history
from preprocess.synthetic_ingestion import sources, TEXT, smoke

DECISION = dict(decision="approved", reviewer="SYNTHETIC operator", reason="Reviewed synthetic extraction only",
    evidence_locator="SYNTHETIC entire document", reviewed_at="2026-01-02T00:00:00+00:00", validity="unknown")


@pytest.fixture
def prepared(tmp_path):
    root = initialize(tmp_path / "workspace")
    manifests = sources(tmp_path / "sources")
    return root, manifests


@pytest.mark.parametrize("suffix", ["txt", "html", "docx", "pdf"])
def test_local_format_extracts_ordered_text(prepared, suffix):
    root, manifests = prepared
    manifest = next(p for p in manifests if p.name.startswith(suffix + "."))
    result = ingest(root, manifest)
    assert result["status"] == "pending"
    stage = load_stage(root, result["stage_id"])
    assert file_hash(root / stage["raw_path"]) == stage["raw_sha256"]
    assert Path(stage["raw_path"]).name == f"synthetic.{suffix}"
    text = stage["parsed"]["text"]
    assert "SYNTHETIC" in text
    assert "không" in text if suffix != "pdf" else "NOT OFFICIAL" in text
    nodes = stage["parsed"]["nodes"]
    assert ''.join(text[n['start']:n['end']] for n in nodes) == text
    if suffix in {"html", "docx"}:
        assert any(n["kind"] == "table" and n["rows"] for n in nodes)


def test_vietnamese_nfc_and_full_hierarchy():
    assert normalize(unicodedata.normalize("NFD", "Điều khoản đất đai\r\n")) == "Điều khoản đất đai\n"
    parsed = hierarchy([Block(TEXT)])
    nodes = parsed["nodes"]
    kinds = [n["kind"] for n in nodes]
    for kind in ("part", "chapter", "section", "subsection", "article", "clause", "point", "annex", "unstructured"):
        assert kind in kinds
    point = next(n for n in nodes if n["locator"].endswith("point:đ"))
    assert nodes[point["parent"]]["kind"] == "clause"
    assert "article:1/clause:1/point:đ" in point["locator"]
    assert "chú thích" in parsed["text"]


def test_html_inline_text_and_notes_preserved(tmp_path):
    path = tmp_path / "fixture.html"
    path.write_text('<p>Điều <b>1.</b> Giả lập</p><p>1. Nội dung</p><table><tr><td>A</td><td>B</td></tr></table><p>Chú thích cuối</p><script>discard executable</script>')
    blocks, _ = extract(path)
    parsed = hierarchy(blocks)
    assert any(n["kind"] == "article" for n in parsed["nodes"])
    assert "Chú thích cuối" in parsed["text"]
    assert "discard executable" not in parsed["text"]


@pytest.mark.parametrize("text", ["1. Orphan clause", "a) Orphan point", "Điều 1. A\nĐiều 1. Repeated"])
def test_ambiguous_hierarchy_quarantines(text):
    with pytest.raises(ExtractionError): hierarchy([Block(text)])


def test_ocr_and_docx_auto_numbering_fail_closed(tmp_path):
    from pypdf import PdfWriter
    writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
    writer.write(tmp_path / "scan.pdf")
    with pytest.raises(ExtractionError, match="OCR"): extract(tmp_path / "scan.pdf")
    from docx import Document
    from docx.oxml import OxmlElement
    doc = Document(); paragraph = doc.add_paragraph("SYNTHETIC automatic list")
    paragraph._p.get_or_add_pPr().append(OxmlElement("w:numPr"))
    doc.save(tmp_path / "auto.docx")
    with pytest.raises(ExtractionError, match="numbering"): extract(tmp_path / "auto.docx")


def test_ingestion_idempotent_incremental_and_quarantine(prepared):
    root, manifests = prepared
    first = ingest(root, manifests[0]); second = ingest(root, manifests[0])
    assert first == second
    assert len(list((root / "stages").glob("*.json"))) == 1
    source = manifests[0].parent / "synthetic.txt"
    source.write_text(TEXT + "\nGhi chú bổ sung mới.\n")
    third = ingest(root, manifests[0])
    assert third["stage_id"] != first["stage_id"]
    assert len(list((root / "raw").iterdir())) == 2
    source.write_text("a) invalid orphan")
    failed = ingest(root, manifests[0])
    assert failed["status"] == "quarantined"
    with pytest.raises(ValueError, match="Quarantined"): review(root, failed["stage_id"], DECISION)


def test_unchanged_source_skips_parser(prepared, monkeypatch):
    root, manifests = prepared
    first = ingest(root, manifests[0])
    monkeypatch.setattr('preprocess.offline_ingestion.extract', lambda *_: pytest.fail('Unchanged source must resume without parsing'))
    assert ingest(root, manifests[0]) == first


@pytest.mark.parametrize("mutation", ["missing", "host", "credentials", "path", "timezone", "synthetic_title"])
def test_bad_metadata_is_rejected_and_reported(prepared, mutation):
    root, manifests = prepared
    path = manifests[0]; metadata = json.loads(path.read_text())
    if mutation == "missing": metadata.pop("official_number")
    elif mutation == "host": metadata["source_url"] = "https://unreviewed.invalid/"
    elif mutation == "credentials": metadata["source_url"] = "https://synthetic.invalid/?api_key=NEVER_ECHO_THIS_VALUE"
    elif mutation == "path": metadata["file"] = "../outside.txt"
    elif mutation == "timezone": metadata["acquired_at"] = "2026-01-01T00:00:00"
    elif mutation == "synthetic_title": metadata["title"] = "Looks official but synthetic"
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError): ingest(root, path)
    assert "NEVER_ECHO_THIS_VALUE" not in (root / "reports/last-ingest.json").read_text()
    assert json.loads((root / "reports/last-ingest.json").read_text())["status"] == "failed"


def test_workspace_never_adopts_existing_database(tmp_path):
    root = tmp_path / "existing"; root.mkdir(); (root / "canonical.sqlite3").write_bytes(b"user data")
    with pytest.raises(ValueError): initialize(root)
    assert (root / "canonical.sqlite3").read_bytes() == b"user data"


def test_review_chain_and_explicit_seal(prepared, tmp_path):
    root, manifests = prepared
    stage = ingest(root, manifests[0])["stage_id"]
    with pytest.raises(ValueError, match="explicitly"): seal(root, "SYNTHETIC", [stage])
    with pytest.raises(ValueError, match="approved"): seal(root, "SYNTHETIC", [stage], approve_publication=True, purpose="synthetic")
    review(root, stage, dict(DECISION, decision="rejected"))
    with pytest.raises(ValueError): seal(root, "SYNTHETIC", [stage], approve_publication=True, purpose="synthetic")
    event = review(root, stage, DECISION)
    assert review(root, stage, DECISION) == event
    assert len(review_history(root, stage)) == 2
    result = seal(root, "SYNTHETIC", [stage], approve_publication=True, purpose="synthetic")
    assert result == seal(root, "SYNTHETIC", [stage], approve_publication=True, purpose="synthetic")
    assert result["indexed"] is False and result["published"] is False
    export(root, result["release_hash"], tmp_path / "export")
    rows = [json.loads(line) for line in (tmp_path / "export/records.jsonl").read_text().splitlines()]
    assert rows and all(row["source_text_sha256"] and row["chunker_version"] for row in rows)
    review(root, stage, dict(DECISION, decision="rejected", reason="SYNTHETIC correction"))
    with pytest.raises(ValueError, match="changed"): export(root, result["release_hash"], tmp_path / "blocked")


def test_long_clause_chunks_are_bounded_stable_and_lossless():
    text = "1. " + "Nội dung giả lập. " * 500
    pv = SimpleNamespace(id="SYNTHETIC-pv", document_version_id="SYNTHETIC-v", text=text, text_sha256=digest(text))
    rows = chunk_provision(pv, "SYNTHETIC | Điều 1", SYNTHETIC_SPEC, ByteBudget(), max_tokens=256)
    assert len(rows) > 10
    assert all(ByteBudget().count(row.text) <= 256 for row in rows)
    assert ''.join(text[row.source_start:row.source_end] for row in rows) == text
    assert rows == chunk_provision(pv, "SYNTHETIC | Điều 1", SYNTHETIC_SPEC, ByteBudget(), max_tokens=256)
    assert len({row.chunk_id for row in rows}) == len(rows)


def test_synthetic_full_ingestion_round_trip(tmp_path):
    root = tmp_path / "smoke"
    result = smoke(root)
    assert result["documents"] == 4 and result["chunks"] > 20 and result["real_documents"] == 0
    assert smoke(root) == result
    with database(root) as factory, factory() as session:
        assert session.scalar(select(func.count()).select_from(LegalDocument)) == 4
        assert session.scalar(select(func.count()).select_from(SourceArtifact)) == 4
        assert all(v.validity_status == "unknown" for v in session.scalars(select(DocumentVersion)))


def test_canonical_duplicate_number_rejected(prepared):
    root, manifests = prepared
    stage = ingest(root, manifests[0])["stage_id"]; review(root, stage, DECISION)
    seal(root, "SYNTHETIC-first", [stage], approve_publication=True, purpose="synthetic")
    metadata = json.loads(manifests[0].read_text()); metadata["official_identifier"] = "SYNTHETIC:conflicting-identifier"
    manifests[0].write_text(json.dumps(metadata))
    other = ingest(root, manifests[0])["stage_id"]; review(root, other, DECISION)
    with pytest.raises(ValueError, match="Duplicate canonical"):
        seal(root, "SYNTHETIC-conflict", [other], approve_publication=True, purpose="synthetic")


def test_incremental_versions_preserve_sealed_history(prepared):
    root, manifests = prepared
    first = ingest(root, manifests[0])["stage_id"]; review(root, first, DECISION)
    old_release = seal(root, "SYNTHETIC-history-v1", [first], approve_publication=True, purpose="synthetic")
    path = manifests[0].parent / "synthetic.txt"
    path.write_text(TEXT + "\nGhi chú sửa đổi giả lập.\n")
    second = ingest(root, manifests[0])["stage_id"]
    review(root, second, dict(DECISION, legal_change="amended"))
    new_release = seal(root, "SYNTHETIC-history-v2", [second], approve_publication=True, purpose="synthetic")
    with database(root) as factory, factory() as session:
        versions = session.scalars(select(DocumentVersion).order_by(DocumentVersion.sequence)).all()
        assert len(versions) == 2 and versions[1].supersedes_id == versions[0].id
        assert session.scalar(select(func.count()).select_from(LegalDocument)) == 1
        assert session.scalar(select(func.count()).select_from(SourceArtifact)) == 2
    assert old_release["release_hash"] != new_release["release_hash"]


def test_source_and_review_tampering_block_export(prepared, tmp_path):
    root, manifests = prepared
    stage_id = ingest(root, manifests[0])["stage_id"]; review(root, stage_id, DECISION)
    result = seal(root, "SYNTHETIC-tamper", [stage_id], approve_publication=True, purpose="synthetic")
    stage = load_stage(root, stage_id)
    (root / stage["raw_path"]).write_text("SYNTHETIC tampered original")
    with pytest.raises(ValueError, match="checksum"): export(root, result["release_hash"], tmp_path / "blocked")


def test_partial_review_and_unknown_real_current_law_gates(prepared):
    from preprocess.offline_ingestion import Review
    with pytest.raises(ValueError): Review.model_validate(dict(DECISION, validity="in_force"))
    root, manifests = prepared
    stage = ingest(root, manifests[0])["stage_id"]
    with pytest.raises(ValueError, match="Partial"):
        review(root, stage, dict(DECISION, validity="partially_expired", effective_date="2020-01-01"))
    metadata = json.loads(manifests[0].read_text())
    metadata.update(is_synthetic=False, source_url="https://vbpl.vn/SYNTHETIC-test-only")
    manifests[0].write_text(json.dumps(metadata))
    real_labeled = ingest(root, manifests[0])["stage_id"]
    review(root, real_labeled, DECISION)
    from batch.contracts import MODEL_ID, MODEL_REVISION
    # Mock tokenizer identity/count, not an inference claim or acquisition of real documents.
    class FakePinnedBudget(ByteBudget): identity = f"{MODEL_ID}@{MODEL_REVISION}"
    with pytest.raises(ValueError, match="Current-law"):
        seal(root, "SYNTHETIC-gate-test", [real_labeled], purpose="current-law", approve_publication=True, budget=FakePinnedBudget())
    with database(root) as factory, factory() as session:
        assert session.scalar(select(func.count()).select_from(LegalDocument)) == 0


def test_canonical_receive_receipt_and_span_tamper_rejection(tmp_path):
    from batch.colab import pack_colab, receive_colab
    from batch.local import validate_local_provenance
    root = tmp_path / "workspace"
    smoke(root)
    exchange = tmp_path / "exchange"
    pack_colab(root / "embedding-input", exchange)
    import shutil
    shutil.copyfile(root / "embedding-output.zip", exchange / "download-from-colab/embedding-output.zip")
    received = receive_colab(exchange, workspace=root)
    receipt = json.loads((Path(received["receipt_directory"]) / "receipt.json").read_text())
    assert receipt["indexed"] is False
    assert receive_colab(exchange, workspace=root) == received
    from batch.files import export_input
    from batch.contracts import SourceRecord
    manifest = validate_input(root / "embedding-input")
    rows = [SourceRecord.model_validate_json(line) for line in (root / "embedding-input/records.jsonl").read_text().splitlines()]
    rows[0] = rows[0].model_copy(update={"source_start": rows[0].source_start + 1})
    export_input(tmp_path / "tampered", rows, release_id=manifest.corpus_release_id, release_sha256=manifest.corpus_release_sha256,
        is_synthetic=True, model=SYNTHETIC_SPEC)
    with database(root) as factory, factory() as session, pytest.raises(ValueError):
        validate_local_provenance(session, tmp_path / "tampered")


def test_staged_migration_backup_and_legacy_preservation(tmp_path):
    from backend.core.database import create_engine_only
    from backend.db.migrate import upgrade_database
    from preprocess.migration_safety import rehearsal
    original = tmp_path / "synthetic-app.sqlite3"
    engine = create_engine_only(f"sqlite:///{original}")
    upgrade_database(engine, "0001_application")
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO users VALUES(1, 'synthetic-user', 'synthetic-hash', '2020-01-01')")
        conn.exec_driver_sql("INSERT INTO chat_sessions VALUES('synthetic-session', 1, 'SYNTHETIC', '2020-01-01', '2020-01-01')")
        conn.exec_driver_sql("INSERT INTO messages VALUES(1, 'synthetic-session', 'user', 'SYNTHETIC message', '2020-01-01')")
    engine.dispose()
    before = file_hash(original)
    report = rehearsal(original, tmp_path / "backup-and-rehearsal")
    assert report["status"] == "pass" and report["legacy_preserved"]
    assert report["foreign_keys_ok"] and not report["original_migrated"]
    assert "refused" in report["rollback"]
    assert file_hash(original) == before
