"""Solo-operator, local-file ingestion. Isolated SQLite, immutable filesystem journal."""
from contextlib import contextmanager
from datetime import date, datetime, timezone
import fcntl
import json
from pathlib import Path
import re
import shutil
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select

from backend.core.database import create_database
from backend.db.models.legal import (
    AcquisitionManifest, LegalDocument, SourceArtifact, DocumentVersion, LegalProvision,
    ProvisionVersion, CorpusRelease,
)
from backend.services.legal_service import put_record, add_release_document, publish_release, validity_on, stable_id
from batch.contracts import canonical, digest, VIETNAMESE_SPEC, SYNTHETIC_SPEC
from batch.files import atomic_bytes, file_hash, export_input
from preprocess.legal_parser import extract, hierarchy, normalize, PARSER_VERSION, ExtractionError
from preprocess.legal_chunking import CHUNKER_VERSION, ByteBudget, provision_context

OFFICIAL_HOSTS = {"vbpl.vn", "vanban.chinhphu.vn", "congbao.chinhphu.vn", "hanoi.gov.vn", "datafiles.chinhphu.vn"}
MARKER = {"schema": 1, "purpose": "isolated-offline-ingestion"}


class InputMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    file: str = Field(min_length=1)
    official_identifier: str = Field(min_length=1, max_length=255)
    official_number: str = Field(min_length=1, max_length=120)
    document_type: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=500)
    issuing_authority: str = Field(min_length=1, max_length=255)
    jurisdiction: str = Field(min_length=1, max_length=80)
    source_url: str
    acquired_at: datetime
    issuance_date: date | None = None
    publication_date: date | None = None
    is_synthetic: bool = False

    @field_validator("official_identifier", "official_number", "document_type", "title", "issuing_authority", "jurisdiction", mode="before")
    @classmethod
    def unicode_identity(cls, value):
        return normalize(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def safe(self):
        from backend.services.legal_service import _validate
        _validate({"source_url": self.source_url, "acquired_at": self.acquired_at})
        parsed = urlsplit(self.source_url)
        host = parsed.hostname or ""
        allowed = host == "synthetic.invalid" if self.is_synthetic else any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)
        if parsed.scheme != "https" or parsed.port not in {None, 443} or not allowed or parsed.fragment:
            raise ValueError("Use an HTTPS official-source URL on the reviewed host list (synthetic.invalid for fixtures)")
        if self.is_synthetic and not self.title.startswith("SYNTHETIC"):
            raise ValueError("Synthetic titles must begin SYNTHETIC")
        if self.acquired_at.tzinfo is None:
            raise ValueError("Supply an explicit acquisition timezone")
        return self


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validity: Literal["unknown", "in_force", "partially_expired", "expired", "repealed", "suspended", "not_yet_effective"] = "unknown"
    effective_date: date | None = None
    expiry_date: date | None = None

    @model_validator(mode="after")
    def interval(self):
        if self.validity != "unknown" and self.effective_date is None:
            raise ValueError("Reviewed non-unknown validity requires an explicit effective date")
        if self.expiry_date and self.effective_date and self.expiry_date <= self.effective_date:
            raise ValueError("Expiry is an exclusive end and must follow the effective date")
        return self


class Review(Claim):
    decision: Literal["approved", "rejected", "pending"]
    reviewer: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=2000)
    evidence_locator: str = Field(min_length=1, max_length=500)
    reviewed_at: datetime
    legal_change: Literal["none", "amended", "superseded"] = "none"
    provisions: dict[str, Claim] = Field(default_factory=dict)

    @field_validator("reviewed_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None: raise ValueError("Review timestamp requires timezone")
        return value


CATEGORIES = ("A_source_identity", "B_extraction_quality", "C_legal_metadata", "D_applicability_validity")
CATEGORY_TITLES = {
    "A_source_identity": "A. Source identity",
    "B_extraction_quality": "B. Extraction quality",
    "C_legal_metadata": "C. Legal metadata",
    "D_applicability_validity": "D. Applicability / validity",
}
# Parsing/source approval is not a legal-validity determination, and never becomes one implicitly.
REQUIRED_FOR_RESEARCH = ("A_source_identity", "B_extraction_quality", "C_legal_metadata")


class CategoryDecision(Claim):
    """One append-only checklist decision, bound to the exact stage artifact it reviewed."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    category: Literal["A_source_identity", "B_extraction_quality", "C_legal_metadata", "D_applicability_validity"]
    decision: Literal["approved", "rejected", "pending"]
    reviewer: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(min_length=1, max_length=2000)
    scope: str = Field(min_length=1, max_length=500)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    reviewed_at: datetime
    stage_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("reviewed_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None: raise ValueError("Review timestamp requires timezone")
        return value

    @model_validator(mode="after")
    def validity_only_when_reviewed(self):
        for field in ("reviewer", "reason", "evidence", "scope"):
            if getattr(self, field).startswith("FILL:"):
                raise ValueError("Replace template FILL: text with a real review statement")
        if any(value.startswith("FILL:") for value in self.limitations):
            raise ValueError("Replace template FILL: text with real limitations")
        if self.category == "D_applicability_validity" and self.decision == "approved":
            if self.validity == "unknown":
                raise ValueError("Category D cannot be approved while validity stays unknown; record pending/rejected with evidence")
            if self.effective_date is None:
                raise ValueError("Approved applicability/validity requires an explicit effective date")
        return self


def write_once(path, value):
    data = (canonical(value) + "\n").encode()
    if path.exists():
        if path.is_symlink() or path.read_bytes() != data:
            raise ValueError("Immutable workspace artifact conflicts; preserve it and use a new revision")
        return
    with path.open("xb") as handle:
        handle.write(data)


def initialize(workspace):
    from batch.archive import safe_root
    root = safe_root(workspace)
    root.mkdir(parents=True, exist_ok=True)
    marker = root / "workspace.json"
    if marker.exists():
        require_workspace(root)
        return root
    if any(root.iterdir()):
        raise ValueError("Initialize a new empty workspace; existing databases are never adopted automatically")
    for name in ("raw", "stages", "reviews", "releases", "reports"):
        (root / name).mkdir()
    engine, _ = create_database(f"sqlite:///{(root / 'canonical.sqlite3').resolve()}")
    engine.dispose()
    write_once(marker, MARKER)
    return root


def require_workspace(workspace):
    root = Path(workspace)
    if root.is_symlink() or not (root / "workspace.json").is_file() or json.loads((root / "workspace.json").read_text()) != MARKER:
        raise ValueError("Initialize an isolated workspace first; do not use the live application directory")
    for path in (root, *root.parents):
        if path.is_symlink(): raise ValueError("Workspace ancestor symlinks are refused")
    if any((root / name).is_symlink() for name in ("raw", "stages", "reviews", "releases", "reports", "canonical.sqlite3")):
        raise ValueError("Workspace symlinks are refused")
    return root


@contextmanager
def locked(workspace):
    root = require_workspace(workspace)
    lock_path = root / ".operator.lock"
    if lock_path.is_symlink(): raise ValueError("Workspace lock symlink refused")
    with lock_path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield root


@contextmanager
def database(workspace):
    # Already initialized at head; no automatic migration of *any existing* DB here.
    from backend.core.database import create_engine_only
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    root = require_workspace(workspace)
    if not (root / "canonical.sqlite3").is_file(): raise ValueError("Workspace database missing; restore backup")
    engine = create_engine_only(f"sqlite:///{(root / 'canonical.sqlite3').resolve()}")
    try:
        with engine.connect() as conn:
            if conn.scalar(text("SELECT version_num FROM alembic_version")) != "0002_legal_domain":
                raise ValueError("Staging schema differs; test a backup upgrade explicitly before continuing")
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        engine.dispose()


def identifier(value):
    if not re.fullmatch(r"[0-9a-f]{64}", value): raise ValueError("Use the exact stage/release hash from the previous report")
    return value


def load_stage(root, stage_id):
    path = root / "stages" / (identifier(stage_id) + ".json")
    if path.is_symlink(): raise ValueError("Stage symlink refused")
    stage = json.loads(path.read_text())
    if digest(canonical(stage)) != stage_id: raise ValueError("Stage checksum failed; restore the original stage")
    from batch.archive import safe_root
    raw_relative = Path(stage["raw_path"])
    if raw_relative.is_absolute() or ".." in raw_relative.parts or len(raw_relative.parts) != 3 or raw_relative.parts[:2] != ("raw", stage["raw_sha256"]):
        raise ValueError("Invalid source provenance path; restore the original stage")
    raw = safe_root(root / raw_relative)
    if file_hash(raw) != stage["raw_sha256"]:
        raise ValueError("Raw source checksum failed; restore source before review/export")
    return stage


def stage_lineage(root):
    """Return (stages by id, ids superseded by a newer parser revision).

    Reparsing is append-only: a new stage points at the stage it replaces, and the
    original stage file stays immutable for audit and historical sealed releases.
    """
    stages, superseded = {}, set()
    for path in sorted((root / "stages").glob("*.json")):
        stages[path.stem] = load_stage(root, path.stem)
    for stage_id, stage in stages.items():
        prior = stage.get("supersedes")
        if prior is not None:
            if prior not in stages:
                raise ValueError("Stage supersedes an absent artifact; restore the lineage")
            superseded.add(prior)
    for stage_id in superseded:
        seen, cursor = set(), stage_id
        while cursor is not None:
            if cursor in seen: raise ValueError("Stage supersedes cycle; restore the lineage")
            seen.add(cursor)
            cursor = stages.get(cursor, {}).get("supersedes")
    return stages, superseded


def reparse(workspace, stage_ids=None):
    """Re-extract preserved originals with the current parser; never overwrite a stage."""
    with locked(workspace) as root:
        stages, superseded = stage_lineage(root)
        selected = sorted(stage_ids or [sid for sid in stages if sid not in superseded])
        results = []
        for stage_id in selected:
            identifier(stage_id)
            if stage_id not in stages: raise ValueError("Unknown stage; select a preserved stage id")
            stage = stages[stage_id]
            if stage["parser_version"] == PARSER_VERSION and stage.get("quality_gate_version") == "pilot-quality-v2":
                results.append(dict(stage_id=stage_id, supersedes=stage.get("supersedes"), status=stage["status"],
                                    nodes=len(stage.get("parsed", {}).get("nodes", [])), reused=True))
                continue
            for existing_id, existing in stages.items():
                if (existing.get("supersedes") == stage_id
                        and existing.get("parser_version") == PARSER_VERSION
                        and existing.get("quality_gate_version") == "pilot-quality-v2"):
                    results.append(dict(stage_id=existing_id, supersedes=stage_id, status=existing["status"],
                                        nodes=len(existing.get("parsed", {}).get("nodes", [])), reused=True))
                    break
            else:
                from batch.archive import safe_root
                raw = safe_root(root / Path(stage["raw_path"]))
                if file_hash(raw) != stage["raw_sha256"]:
                    raise ValueError("Raw source checksum failed; restore source before reparsing")
                extraction, warnings = {}, []
                try:
                    blocks, warnings = extract(raw, report=extraction)
                    parsed = hierarchy(blocks)
                    parsed["extraction"] = extraction
                except Exception as exc:
                    parsed = None
                    warnings.append(f"Parser failed: {type(exc).__name__}; inspect the preserved source")
                revised = dict(metadata=stage["metadata"], raw_path=stage["raw_path"],
                    raw_sha256=stage["raw_sha256"], parser_version=PARSER_VERSION,
                    quality_gate_version="pilot-quality-v2", status="pending", warnings=warnings,
                    supersedes=stage_id)
                if parsed is not None:
                    from law_crawler.quality import assess
                    revised["parsed"] = parsed
                    revised["quality"] = assess(parsed)
                    if revised["quality"]["critical"]:
                        revised.update(status="quarantined", action="Critical extraction QA: "
                            + ", ".join(revised["quality"]["critical"])
                            + "; obtain complete/reviewed source and ingest a new stage")
                else:
                    revised.update(status="quarantined", action=warnings[-1])
                    revised["quality"] = dict(state="quarantined", critical=["parser_failed"], counts={},
                        legal_validity="unknown", human_reviewed=False)
                new_id = digest(canonical(revised))
                write_once(root / "stages" / (new_id + ".json"), revised)
                results.append(dict(stage_id=new_id, supersedes=stage_id, status=revised["status"],
                    nodes=len(revised.get("parsed", {}).get("nodes", [])),
                    counts=revised["quality"].get("counts", {}), warnings=warnings))
        atomic_bytes(root / "reports/last-reparse.json",
            (canonical(dict(stages=len(selected), results=results)) + "\n").encode())
        return results


def ingest(workspace, manifest_path):
    root = require_workspace(workspace)
    try:
        manifest_path = Path(manifest_path)
        metadata = InputMetadata.model_validate_json(manifest_path.read_bytes())
        relative = Path(metadata.file)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Manifest file must be relative to the manifest directory, without traversal")
        source = manifest_path.parent / relative
        if source.suffix.lower() not in {".html", ".htm", ".txt", ".pdf", ".docx"} or "\\" in str(relative):
            raise ValueError("Use a supported source filename without backslash path separators")
        for part in [source, *source.parents]:
            if part.is_symlink(): raise ValueError("Source symlinks are refused; copy a regular local file")
        if not source.is_file() or source.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("Source missing or exceeds 20 MiB; verify the manifest file")
        raw_hash = file_hash(source)
        with locked(root):
            raw_dir = root / "raw" / raw_hash
            if raw_dir.is_symlink(): raise ValueError("Raw artifact directory symlink refused")
            raw_dir.mkdir(exist_ok=True)
            raw = raw_dir / source.name
            if raw.is_symlink(): raise ValueError("Raw artifact symlink refused")
            if not raw.exists():
                with source.open("rb") as src, raw.open("xb") as dst: shutil.copyfileobj(src, dst)
            if file_hash(raw) != raw_hash: raise ValueError("Preserved source mismatch; restore the raw artifact")
            meta = metadata.model_dump(mode="json")
            meta["file"] = source.name
            stage = dict(metadata=meta, raw_path=raw.relative_to(root).as_posix(), raw_sha256=raw_hash,
                         parser_version=PARSER_VERSION, quality_gate_version="pilot-quality-v1", status="pending", warnings=[])
            for candidate in (root / "stages").glob("*.json"):
                prior = load_stage(root, candidate.stem)
                if all(prior.get(key) == stage[key] for key in ("metadata", "raw_path", "raw_sha256", "parser_version", "quality_gate_version")):
                    result = dict(stage_id=candidate.stem, status=prior["status"], raw_sha256=raw_hash,
                        nodes=len(prior.get("parsed", {}).get("nodes", [])), warnings=prior["warnings"])
                    atomic_bytes(root / "reports/last-ingest.json", (canonical(result) + "\n").encode())
                    return result
            try:
                extraction = {}
                blocks, warnings = extract(raw, report=extraction)
                parsed = hierarchy(blocks)
                parsed["extraction"] = extraction
                stage.update(parsed=parsed, warnings=warnings)
                from law_crawler.quality import assess
                stage['quality']=assess(stage['parsed'])
                if stage['quality']['critical']:
                    stage.update(status='quarantined',action='Critical extraction QA: '+', '.join(stage['quality']['critical'])+'; obtain complete/reviewed source and ingest a new stage')
            except Exception as exc:
                stage.update(status="quarantined", error=type(exc).__name__,
                    action=str(exc) if isinstance(exc, ExtractionError) else "Parser failed; inspect the preserved source and supply a supported rendition")
            stage_id = digest(canonical(stage))
            write_once(root / "stages" / (stage_id + ".json"), stage)
            result = dict(stage_id=stage_id, status=stage["status"], raw_sha256=raw_hash,
                          nodes=len(stage.get("parsed", {}).get("nodes", [])), warnings=stage["warnings"])
            atomic_bytes(root / "reports/last-ingest.json", (canonical(result) + "\n").encode())
            return result
    except Exception as exc:
        # Never echo manifest contents, URLs, parser payloads or credentials into reports.
        report = dict(status="failed", error=type(exc).__name__, action="Check required metadata, official HTTPS host, file path/encoding and source size; retry with corrected manifest")
        atomic_bytes(root / "reports/last-ingest.json", (canonical(report) + "\n").encode())
        raise ValueError(report["action"]) from None


def review_history(root, stage_id):
    directory = root / "reviews" / identifier(stage_id)
    if directory.is_symlink(): raise ValueError("Review journal symlink refused")
    if not directory.exists(): return []
    history, previous = [], None
    for index, path in enumerate(sorted(directory.glob("*.json"))):
        event = json.loads(path.read_text())
        if path.is_symlink() or path.name != f"{index:05d}.json" or event["previous"] != previous or event["stage_id"] != stage_id:
            raise ValueError("Review chain damaged; restore journal before continuing")
        previous = digest(canonical(event))
        history.append(event)
    return history


def category_history(root, stage_id):
    """Append-only checklist decisions. A separate chain from the whole-stage legal review."""
    directory = root / "reviews" / identifier(stage_id) / "categories"
    if directory.is_symlink(): raise ValueError("Category review journal symlink refused")
    if not directory.exists(): return []
    history, previous = [], None
    for index, path in enumerate(sorted(directory.glob("*.json"))):
        event = json.loads(path.read_text())
        if path.is_symlink() or path.name != f"{index:05d}.json" or event["previous"] != previous or event["stage_id"] != stage_id:
            raise ValueError("Category review chain damaged; restore journal before continuing")
        previous = digest(canonical(event))
        history.append(event)
    return history


def category_status(root, stage_id):
    status = {name: None for name in CATEGORIES}
    for event in category_history(root, stage_id):
        # Evidence-only records never change an approval status.
        if event.get("kind", "decision") == "decision":
            status[event["review"]["category"]] = event["review"]
    return status


def _stage_text_hash(stage):
    return (stage.get("parsed") or {}).get("text_sha256")


def decide_category(workspace, stage_id, payload, *, kind="decision"):
    """Record one explicit checklist decision; never implied by another approval."""
    if kind not in {"decision", "evidence"}: raise ValueError("Choose decision or evidence record kind")
    decision = CategoryDecision.model_validate(payload)
    with locked(workspace) as root:
        stages, superseded = stage_lineage(root)
        if stage_id not in stages: raise ValueError("Unknown stage; use the exact stage id from the inventory")
        if stage_id in superseded:
            raise ValueError("Superseded stage cannot be reviewed; reparse/review the active stage")
        stage = stages[stage_id]
        if decision.stage_id != stage_id:
            raise ValueError("Decision stage_id does not match the selected stage")
        if decision.raw_sha256 != stage["raw_sha256"] or decision.text_sha256 != _stage_text_hash(stage):
            raise ValueError("Decision is bound to a different artifact; regenerate it from the current packet")
        if stage["status"] == "quarantined" and decision.category == "B_extraction_quality" and decision.decision == "approved":
            raise ValueError("Quarantined extraction cannot be approved; correct the source and ingest/reparse a new stage")
        events = category_history(root, stage_id)
        values = decision.model_dump(mode="json")
        if events and events[-1].get("kind", "decision") == kind and events[-1]["review"] == values: return events[-1]
        event = dict(stage_id=stage_id, kind=kind, previous=digest(canonical(events[-1])) if events else None, review=values)
        directory = root / "reviews" / stage_id / "categories"
        directory.mkdir(parents=True, exist_ok=True)
        write_once(directory / f"{len(events):05d}.json", event)
        return event


def _latest_legacy_review(root, stage_id):
    history = review_history(root, stage_id)
    return Review.model_validate(history[-1]["review"]) if history else None


def eligibility(workspace, stage_ids=None):
    """Report review gates honestly; absence of a decision is never treated as approval."""
    root = require_workspace(workspace)
    stages, superseded = stage_lineage(root)
    selected = sorted(stage_ids or [sid for sid in stages if sid not in superseded])
    rows = []
    for stage_id in selected:
        if stage_id not in stages: raise ValueError("Unknown stage; use the exact stage id from the inventory")
        stage = stages[stage_id]
        categories = category_status(root, stage_id)
        legacy = _latest_legacy_review(root, stage_id)
        binding_current = all(
            item is None or (item["raw_sha256"] == stage["raw_sha256"] and item["text_sha256"] == _stage_text_hash(stage))
            for item in categories.values())
        approved = {name: bool(value and value["decision"] == "approved") for name, value in categories.items()}
        validity_value = (categories["D_applicability_validity"] or {}).get("validity", "unknown")
        validity_recorded = categories["D_applicability_validity"] is not None
        validity_rejected = validity_recorded and categories["D_applicability_validity"]["decision"] == "rejected"
        gates = dict(
            not_superseded=stage_id not in superseded,
            not_quarantined=stage.get("status") == "pending",
            artifact_binding_current=binding_current,
            source_identity_approved=approved["A_source_identity"],
            extraction_approved=approved["B_extraction_quality"],
            legal_metadata_approved=approved["C_legal_metadata"],
            validity_recorded=validity_recorded,
            validity_not_rejected=not validity_rejected,
            legacy_review_approved=bool(legacy and legacy.decision == "approved"),
            legacy_validity_in_force=bool(legacy and legacy.validity == "in_force"),
            validity_in_force=validity_value == "in_force",
        )
        research = all(gates[key] for key in ("not_superseded", "not_quarantined", "artifact_binding_current",
            "source_identity_approved", "extraction_approved", "legal_metadata_approved", "validity_recorded",
            "validity_not_rejected", "legacy_review_approved"))
        current_law = research and gates["validity_in_force"] and gates["legacy_validity_in_force"]
        blocking = sorted(key for key, passed in gates.items() if not passed)
        rows.append(dict(stage_id=stage_id, official_identifier=stage["metadata"]["official_identifier"],
            official_number=stage["metadata"]["official_number"], status=stage.get("status"), superseded=stage_id in superseded,
            raw_sha256=stage["raw_sha256"], text_sha256=_stage_text_hash(stage), categories=categories,
            legacy_review=legacy.model_dump(mode="json") if legacy else None,
            gates=gates, research_seal_ready=research, current_law_seal_ready=current_law, blocking=blocking,
            parsing_approval_confers_legal_validity=False))
    return dict(stages=len(rows), research_ready=sum(row["research_seal_ready"] for row in rows),
        current_law_ready=sum(row["current_law_seal_ready"] for row in rows), rows=rows)


def review(workspace, stage_id, decision):
    decision = Review.model_validate(decision)
    with locked(workspace) as root:
        stages, superseded = stage_lineage(root)
        if stage_id not in stages: raise ValueError("Unknown stage; use the exact stage id from the inventory")
        if stage_id in superseded:
            raise ValueError("Superseded stage cannot be reviewed; reparse/review the active stage")
        stage = stages[stage_id]
        if stage["status"] == "quarantined" and decision.decision == "approved":
            raise ValueError("Quarantined extraction cannot be approved; correct the source and ingest a new stage")
        locators = {n["locator"] for n in stage.get("parsed", {}).get("nodes", [])}
        if set(decision.provisions) - locators: raise ValueError("Unknown provision locator in review; inspect the stage")
        if decision.validity == "partially_expired" and not decision.provisions:
            raise ValueError("Partial validity needs explicit provision-level assertions")
        events = review_history(root, stage_id)
        payload = decision.model_dump(mode="json")
        if events and events[-1]["review"] == payload: return events[-1]
        event = dict(stage_id=stage_id, previous=digest(canonical(events[-1])) if events else None, review=payload)
        directory = root / "reviews" / stage_id
        directory.mkdir(exist_ok=True)
        write_once(directory / f"{len(events):05d}.json", event)
        return event


def materialize(session, stage, decision):
    """Create approved immutable snapshots only; caller owns SQLite transaction."""
    m = stage["metadata"]
    doc_values = {k: m[k] for k in ("official_identifier", "official_number", "document_type", "title", "issuing_authority", "jurisdiction", "is_synthetic")}
    # A canonical number under another ID is a conflict, not a new document.
    other = session.scalar(select(LegalDocument).where(LegalDocument.jurisdiction == m["jurisdiction"],
        LegalDocument.issuing_authority == m["issuing_authority"], LegalDocument.official_number == m["official_number"]))
    if other and other.official_identifier != m["official_identifier"]:
        raise ValueError("Duplicate canonical number under another identifier; resolve identity before sealing")
    doc = session.scalar(select(LegalDocument).where(LegalDocument.official_identifier == m["official_identifier"]))
    if doc is None:
        doc = put_record(session, LegalDocument, **doc_values)
    elif any(getattr(doc, key) != value for key, value in doc_values.items() if key != "title"):
        raise ValueError("Canonical document identity changed; reconcile metadata without overwriting the instrument")
    request_key = digest(canonical([doc.id, stage["raw_sha256"], m["source_url"]]))
    manifest = session.scalar(select(AcquisitionManifest).where(AcquisitionManifest.request_key == request_key))
    if manifest is None:
        manifest = put_record(session, AcquisitionManifest, source_url=m["source_url"],
        discovered_at=datetime.fromisoformat(m["acquired_at"]), policy_revision="local-files-v1",
        request_key=request_key,
        review_status="approved", details={"original_filename": m["file"], "offline": True, "raw_sha256": stage["raw_sha256"]})
    artifact_id = stable_id(
        SourceArtifact.__table__.name, doc.id, m["source_url"], stage["raw_sha256"])
    artifact = session.get(SourceArtifact, artifact_id)
    if artifact is None:
        artifact = put_record(session, SourceArtifact, document_id=doc.id, manifest_id=manifest.id,
            source_url=m["source_url"], sha256=stage["raw_sha256"], media_type={".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".html": "text/html", ".htm": "text/html", ".txt": "text/plain"}[Path(m["file"]).suffix.lower()],
            storage_uri=stage["raw_path"], acquired_at=datetime.fromisoformat(m["acquired_at"]))
    review_hash = digest(canonical([doc_values, stage["parsed"]["text_sha256"], decision.model_dump(mode="json")]))
    parser_revision = PARSER_VERSION + ":" + review_hash
    existing = session.scalar(select(DocumentVersion).where(DocumentVersion.document_id == doc.id,
        DocumentVersion.source_artifact_id == artifact.id, DocumentVersion.parser_revision == parser_revision))
    if existing: return existing
    prior = session.scalar(select(DocumentVersion).where(DocumentVersion.document_id == doc.id).order_by(DocumentVersion.sequence.desc()))
    parsed = stage["parsed"]
    temporal = dict(effective_date=decision.effective_date, expiry_date=decision.expiry_date,
        validity_status=decision.validity, review_status="approved", verified_at=decision.reviewed_at)
    version = put_record(session, DocumentVersion, document_id=doc.id, source_artifact_id=artifact.id,
        sequence=prior.sequence + 1 if prior else 1, title=m["title"],
        issuance_date=date.fromisoformat(m["issuance_date"]) if m["issuance_date"] else None,
        publication_date=date.fromisoformat(m["publication_date"]) if m["publication_date"] else None,
        parser_revision=parser_revision, text_sha256=parsed["text_sha256"], supersedes_id=prior.id if prior else None, **temporal)
    provisions = []
    for ordinal, node in enumerate(parsed["nodes"]):
        parent = provisions[node["parent"]].id if node["parent"] is not None else None
        provision = session.scalar(select(LegalProvision).where(LegalProvision.document_id == doc.id, LegalProvision.locator == node["locator"]))
        if provision is None:
            provision = put_record(session, LegalProvision, document_id=doc.id, parent_id=parent,
                kind=node["kind"], locator=node["locator"], ordinal=ordinal)
        provisions.append(provision)
        text = parsed["text"][node["start"]:node["end"]]
        if not text: raise ValueError("Empty extraction span; quarantine and review parser output")
        claim = decision.provisions.get(node["locator"], decision)
        put_record(session, ProvisionVersion, document_id=doc.id, provision_id=provision.id,
            document_version_id=version.id, parent_provision_id=parent, text=text, text_sha256=digest(text),
            source_start=node["start"], source_end=node["end"], source_page=node["page"],
            structured_content={"heading": node["heading"], "rows": node["rows"], "parser": PARSER_VERSION},
            effective_date=claim.effective_date, expiry_date=claim.expiry_date, validity_status=claim.validity,
            review_status="approved", verified_at=decision.reviewed_at)
    return version


def _require_packet_approvals(root, stage_ids, purpose):
    """Real releases need the four checklist decisions; none is implied by another."""
    for stage_id in stage_ids:
        categories = category_status(root, stage_id)
        for name in REQUIRED_FOR_RESEARCH:
            item = categories[name]
            if not item or item["decision"] != "approved":
                raise ValueError(f"Missing explicit {CATEGORY_TITLES[name]} approval; review the packet first")
        validity = categories["D_applicability_validity"]
        if validity is None:
            raise ValueError("Missing explicit D. Applicability / validity decision; review the packet first")
        if validity["decision"] == "rejected":
            raise ValueError("Applicability/validity was rejected; do not seal this stage")
        if purpose == "current-law" and (validity["decision"] != "approved" or validity["validity"] != "in_force"):
            raise ValueError("Current-law release needs approved in-force applicability/validity")


def seal(workspace, name, stage_ids, *, approve_publication=False, purpose="research", budget=None, max_tokens=512):
    """Sealed means exportable, NOT indexed/published to retrieval. Unknown law is research-only."""
    if not approve_publication: raise ValueError("Review all stages and explicitly pass --approve-publication")
    if purpose not in {"research", "current-law", "synthetic"}: raise ValueError("Choose research, current-law or synthetic release")
    from preprocess.chunker import VietLegalChunker
    with locked(workspace) as root, database(root) as factory:
        stages, decisions, events = [], [], []
        _, superseded = stage_lineage(root)
        for stage_id in sorted(set(stage_ids)):
            if stage_id in superseded:
                raise ValueError("Superseded stage cannot be sealed; reparse/review the active stage")
            stage = load_stage(root, stage_id)
            history = review_history(root, stage_id)
            if stage["status"] != "pending" or not history or history[-1]["review"]["decision"] != "approved":
                raise ValueError("Only non-quarantined, explicitly approved stages can be sealed")
            stages.append(stage); decisions.append(Review.model_validate(history[-1]["review"])); events.append(history[-1])
        if not stages: raise ValueError("Select at least one reviewed stage")
        if len({s["metadata"]["official_identifier"] for s in stages}) != len(stages):
            raise ValueError("Select only one staged version per canonical document")
        synthetic = all(s["metadata"]["is_synthetic"] for s in stages)
        if synthetic != (purpose == "synthetic") or any(s["metadata"]["is_synthetic"] for s in stages) != synthetic:
            raise ValueError("Keep synthetic releases separate; use purpose=synthetic for fixtures")
        if not synthetic:
            if purpose == "current-law" and any(d.legal_change != "none" or d.validity != "in_force" for d in decisions):
                raise ValueError("Current-law release refuses unknown/partial/superseded status; resolve legal review first")
            _require_packet_approvals(root, sorted(set(stage_ids)), purpose)
        budget = budget or ByteBudget()
        if not synthetic and budget.identity == ByteBudget.identity:
            raise ValueError("Real releases require the pinned cached tokenizer; install ML extras/cache tokenizer explicitly, without weights")
        model = SYNTHETIC_SPEC if synthetic else VIETNAMESE_SPEC
        chunks, ids = [], []
        with factory.begin() as session:
            previous_release = session.scalar(select(CorpusRelease).where(CorpusRelease.name == name))
            created = previous_release.created_at if previous_release else datetime.now(timezone.utc)
            release = put_record(session, CorpusRelease, name=name, created_at=created, is_synthetic=synthetic)
            for stage, decision in zip(stages, decisions):
                version = materialize(session, stage, decision)
                if purpose == "current-law" and (decision.legal_change != "none" or validity_on(version, created.date()) != "in_force"):
                    raise ValueError("Current-law release refuses unknown/partial/superseded status; resolve legal review first")
                add_release_document(session, release.id, version.id); ids.append(version.id)
                pvs = session.scalars(select(ProvisionVersion).where(ProvisionVersion.document_version_id == version.id).order_by(ProvisionVersion.source_start)).all()
                for pv in pvs:
                    if purpose == "current-law" and validity_on(pv, created.date()) != "in_force":
                        raise ValueError("Current-law release has non-current provisions; use research purpose or reviewed current snapshots")
                    chunks.extend(VietLegalChunker.chunk_canonical(pv, provision_context(session, pv), model, budget, max_tokens=max_tokens))
            publish_release(session, release.id)
            result = dict(schema_version=1, release_id=release.id, name=name, state="sealed", indexed=False,
                published=False, approved_publication=True, purpose=purpose, created_at=created.isoformat(),
                corpus_release_sha256=release.manifest_sha256, document_versions=ids, stages=sorted(set(stage_ids)),
                review_events=events, parser_version=PARSER_VERSION, chunker_version=CHUNKER_VERSION,
                tokenizer=budget.identity, max_tokens=max_tokens, model=model.model_dump(),
                provenance=[dict(raw_path=s["raw_path"], raw_sha256=s["raw_sha256"], source_url=s["metadata"]["source_url"],
                    original_filename=s["metadata"]["file"], parsed_text_sha256=s["parsed"]["text_sha256"]) for s in stages],
                chunks=[c.model_dump(mode="json") for c in chunks])
            release_hash = digest(canonical(result))
            # Write before DB commit: a crash can leave an uncommitted file; retry checks identical facts.
            write_once(root / "releases" / (release_hash + ".json"), result)
        return dict(release_hash=release_hash, release_id=release.id, state="sealed", documents=len(ids), chunks=len(chunks), indexed=False, published=False)


def release_details(root, release_hash):
    from batch.archive import safe_root
    path = safe_root(root / "releases" / (identifier(release_hash) + ".json"))
    release = json.loads(path.read_text())
    if digest(canonical(release)) != release_hash: raise ValueError("Release manifest checksum failed; restore sealed release")
    # A later rejection invalidates new exports, not historical immutable release facts.
    for stage_id in release["stages"]:
        load_stage(root, stage_id)
        history = review_history(root, stage_id)
        if not history or history[-1] not in release["review_events"]:
            raise ValueError("Review changed since sealing; create a new reviewed release before export")
    return release


def validate_workspace_export(workspace, input_directory):
    from batch.files import validate_input
    root = require_workspace(workspace)
    manifest = validate_input(input_directory)
    for path in (root / "releases").glob("*.json"):
        # A sealed filesystem manifest must pin the entire exact export, not merely plausible spans.
        candidate = json.loads(path.read_text())
        if candidate.get("release_id") != manifest.corpus_release_id: continue
        release = release_details(root, path.stem)
        expected_hash = digest("".join(canonical(row) + "\n" for row in release["chunks"]))
        if (manifest.records_sha256 == expected_hash and manifest.model.model_dump() == release["model"]
                and manifest.corpus_release_sha256 == release["corpus_release_sha256"]):
            return release
    raise ValueError("Input is not the exact sealed workspace chunk export; re-export the reviewed release")


def export(workspace, release_hash, destination):
    from batch.local import validate_local_provenance
    root = require_workspace(workspace)
    release = release_details(root, release_hash)
    from batch.contracts import ModelSpec
    manifest = export_input(destination, release["chunks"], release_id=release["release_id"],
        release_sha256=release["corpus_release_sha256"], is_synthetic=release["purpose"] == "synthetic",
        model=ModelSpec.model_validate(release["model"]))
    with database(root) as factory, factory() as session:
        validate_local_provenance(session, destination)
    return manifest
