"""Scan a human-populated inbox of manually downloaded official files.

The operator drops a downloaded original into ``manual-inbox/<digest>/`` (the folder is
created for each candidate). This command matches the file to the approved candidate
metadata, verifies the document identity where feasible, writes a normal acquisition
manifest, detects duplicates, and (optionally) runs the existing offline ingestion.

It never guesses an identity, never overwrites an original, and never asserts legal
validity: a successful scan yields a *pending* stage, exactly like an automated download.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from batch.contracts import digest
from batch.files import atomic_bytes, file_hash
from preprocess.legal_parser import extract, normalize, ExtractionError

SUPPORTED = {".pdf", ".docx", ".htm", ".html", ".txt"}
RESERVED = {"acquisition.json", "acquisition.template.json", "scan.json"}
MANIFEST_FIELDS = ("official_identifier", "official_number", "document_type", "title",
                   "issuing_authority", "jurisdiction", "source_url", "issuance_date", "publication_date")


def _load_candidates(registries):
    by_digest, by_identity = {}, {}
    for registry in registries:
        data = json.loads(Path(registry).read_text())
        for candidate in data["candidates"]:
            identity = candidate["official_identifier"]
            folder = digest(identity)
            if folder in by_digest and by_digest[folder]["official_identifier"] != identity:
                raise ValueError("Two candidates collide on one inbox folder; resolve before scanning")
            by_digest[folder] = candidate
            by_identity[identity] = candidate
    return by_digest


def _number_tokens(number):
    import re
    return [t for t in re.split(r"[^0-9A-Za-zÀ-ỹĐđ]+", number) if t]


def _identity_evidence(path, candidate):
    """Return (confirmed, detail). Content-based where feasible; never a guess."""
    number = candidate["official_number"]
    try:
        blocks, _ = extract(path)
        text = normalize("".join(block.text for block in blocks)) if blocks else ""
    except (ExtractionError, OSError, ValueError) as exc:
        return False, f"extraction_unavailable:{type(exc).__name__}"
    flat = " ".join(text.split())
    if number in flat or number.replace("/", " ") in flat:
        return True, "official number present in extracted text"
    tokens = _number_tokens(number)
    if tokens and all(token in flat for token in tokens) and candidate["issuing_authority"] in flat:
        return True, "number tokens and issuing authority present in extracted text"
    return False, "official number not found in extracted text"


def scan(registries, workspace, *, ingest_files=False):
    from preprocess.offline_ingestion import require_workspace, ingest

    root = require_workspace(workspace)
    candidates = _load_candidates(registries)
    inbox = root / "manual-inbox"
    if not inbox.exists():
        raise ValueError("Manual inbox does not exist; run the prepare command first")

    acquired_hashes = set()
    for receipt_path in (root / "acquisitions").glob("*.json") if (root / "acquisitions").exists() else []:
        receipt = json.loads(receipt_path.read_text())
        acquired_hashes.update(a.get("sha256") for a in receipt.get("artifacts", []) if a.get("sha256"))

    report = dict(schema_version=1, notice=("Manual inbox scan. Matching/identity only; a scanned stage is still "
        "pending human legal review and is never asserted legally valid."),
        matched=[], ingested=[], quarantined=[], duplicates=[], ambiguous=[], unmatched=[], unconfirmed=[])
    seen_hashes = {h: "existing acquisition" for h in acquired_hashes}

    for folder in sorted(p for p in inbox.iterdir() if p.is_dir()):
        files = sorted(f for f in folder.iterdir() if f.is_file() and f.name not in RESERVED and not f.name.startswith("."))
        if not files:
            continue
        candidate = candidates.get(folder.name)
        if candidate is None:
            report["unmatched"].append(dict(folder=folder.name, files=[f.name for f in files],
                reason="no approved candidate owns this inbox folder"))
            continue
        if len(files) > 1:
            report["ambiguous"].append(dict(folder=folder.name, files=[f.name for f in files],
                reason="more than one candidate file; resolve manually rather than guessing"))
            continue
        source = files[0]
        suffix = source.suffix.lower()
        if suffix not in SUPPORTED:
            report["unmatched"].append(dict(folder=folder.name, files=[source.name],
                reason=f"unsupported format {suffix!r}"))
            continue
        sha = file_hash(source)
        if sha in seen_hashes:
            report["duplicates"].append(dict(folder=folder.name, file=source.name, sha256=sha,
                reason=f"identical bytes already present ({seen_hashes[sha]})"))
            continue
        seen_hashes[sha] = "manual inbox"
        confirmed, detail = _identity_evidence(source, candidate)
        entry = dict(official_number=candidate["official_number"], official_identifier=candidate["official_identifier"],
                     file=source.name, sha256=sha, identity_confirmed=confirmed, identity_detail=detail)
        if not confirmed:
            report["unconfirmed"].append(entry)
            continue
        mtime = datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc)
        manifest = {key: candidate.get(key) for key in MANIFEST_FIELDS}
        manifest.update(file=source.name, acquired_at=mtime.isoformat(), is_synthetic=False)
        manifest_path = folder / "acquisition.json"
        from preprocess.offline_ingestion import write_once
        write_once(manifest_path, manifest)
        entry["manifest"] = manifest_path.relative_to(root).as_posix()
        report["matched"].append(entry)
        if ingest_files:
            result = ingest(root, manifest_path)
            entry["stage"] = result
            if result["status"] == "pending":
                report["ingested"].append(entry)
            else:
                report["quarantined"].append(entry)

    atomic_bytes(root / "reports/manual-inbox-scan.json", (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())
    return report
