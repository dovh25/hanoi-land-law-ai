"""Offline, evidence-bound inventory/draft generation; never approves or seals law."""
from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import select
from backend.db.models.legal import CorpusRelease
from backend.services.legal_service import put_record
from batch.contracts import canonical, digest
from batch.files import file_hash
from law_crawler.catalog import validate_catalog
from law_crawler.quality import inventory
from preprocess.offline_ingestion import initialize, database, write_once


def _guide_rows(registry_paths, workspace_root, receipts):
    """Priority / number / title / source page / file link / folder / format / status rows."""
    rows, seen = [], set()
    acquired = {}
    for receipt in receipts:
        for artifact in receipt.get("artifacts", []):
            if artifact.get("sha256"):
                acquired.setdefault(receipt["official_identifier"], artifact)
    for registry_path in registry_paths:
        data = json.loads(Path(registry_path).read_text())
        for candidate in data["candidates"]:
            if candidate["official_identifier"] in seen:
                continue
            seen.add(candidate["official_identifier"])
            folder = workspace_root / "manual-inbox" / digest(candidate["official_identifier"])
            artifact = acquired.get(candidate["official_identifier"])
            if artifact:
                link = artifact.get("url", "")
                status = "AUTO-ACQUIRED (pending human legal review)"
                target = (workspace_root / "incoming" / artifact["sha256"]).as_posix()
            else:
                link = candidate["download_urls"][0] if candidate["download_urls"] else "(none verified; use source page)"
                status = "MANUAL download required"
                target = folder.as_posix()
            rows.append(dict(number=candidate["official_number"], title=candidate["title"],
                source_page=candidate["source_url"], file_link=link, target=target,
                fmt="PDF", status=status, jurisdiction=candidate["jurisdiction"]))
    return rows


def _write_guide(path, rows):
    lines = ["# Manual download guide (Phase D.1)", "",
        "Some official instruments are only reachable through sources whose access policy does",
        "not clearly permit automated download (for example a `robots.txt` that returns HTTP 403,",
        "or a reCAPTCHA-gated viewer). For those, download the file yourself with a normal browser",
        "and copy it into the folder shown below. Do **not** bypass a 403, CAPTCHA, login, or rate",
        "limit. You do not need to compute any hash or edit any JSON: drop the original file into",
        "the folder and run the scanner.", "",
        "```bash",
        "uv run --frozen python -m law_crawler.pilot_cli scan-manual-inbox \\",
        "  --workspace data/phase-d-corpus-v2 --ingest",
        "```", "",
        "The scanner matches the file to the approved candidate, checks the document identity,",
        "writes the acquisition manifest, detects duplicates, and ingests it as a **pending**",
        "(never valid) stage.", "",
        "| Priority | Document number | Title | Official source page | Direct file link | Local target folder | Format | Status |",
        "|---|---|---|---|---|---|---|---|"]
    for index, row in enumerate(rows, 1):
        title = row["title"].replace("|", "\\|")
        lines.append(f"| {index} | {row['number']} | {title} | {row['source_page']} | {row['file_link']} | "
                     f"`{row['target']}` | {row['fmt']} | {row['status']} |")
    lines += ["", "## Notes", "",
        "- Rows marked AUTO-ACQUIRED were fetched from the official Government Gazette file CDN",
        "  (`congbaocdn.chinhphu.vn`), which publishes no `robots.txt` (HTTP 404) and is linked",
        "  directly from official `congbao.chinhphu.vn` document pages. Their originals are preserved",
        "  under `data/phase-d-corpus-v2/incoming/<sha256>/`.",
        "- Rows marked MANUAL download required resolve to hosts whose document access is blocked or",
        "  ambiguous (for example `datafiles.chinhphu.vn` robots 403, or `vbpl.vn` reCAPTCHA).",
        "- Every downloaded/parsed document remains `legal_validity=unknown` and `review_status=pending`.",
        "  Downloading and parsing is not legal review.", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def _write_review_worksheet(path, quality):
    checks = ["Document identity", "Official title", "Issuing authority", "Territorial scope",
              "Effective date", "Expiry or repeal status", "Amending/superseded relationships",
              "Transitional provisions", "Annex completeness", "Extraction completeness"]
    lines = ["# Human legal review worksheet (Phase D.1)", "",
        "Every item below is **pending**. Acquisition and parsing are not legal review. A human reviewer",
        "must confirm each field against the official source and record an explicit decision via",
        "`preprocess.offline_cli review`. Unknown validity must stay `unknown`; the pre-filled metadata is",
        "the *official page's claim*, not a verified current-law determination.", ""]
    for row in quality["rows"]:
        state = row["quality"]["state"]
        counts = row["quality"]["counts"]
        lines += [f"## {row['official_identifier']}", "",
            f"- Stage: `{row['stage_id']}` ({state})",
            f"- Source page: {row['source_url']}",
            f"- Raw SHA-256: `{row['raw_sha256']}`",
            f"- Duplicate raw bytes: {row['duplicate_raw']}",
            f"- Extracted provision nodes: {counts or 'none'}",
            f"- Human reviewed: {row['human_reviewed']}",
            "- Checklist:"]
        lines += [f"  - [ ] {item}" for item in checks]
        if row["quality"].get("critical"):
            lines.append(f"  - Quarantine reason: {', '.join(row['quality']['critical'])}")
        if row["quality"].get("warnings"):
            lines.append(f"  - Extraction warnings: {', '.join(row['quality']['warnings'])}")
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def prepare_d1(registry_path="corpus/phase-d1-instruments.json", policies_path="corpus/phase-d1-source-approvals.json",
               workspace="data/phase-d-corpus-v2", release_name="phase-d1-authoritative-pilot-draft",
               base_registry="corpus/phase-d-candidates.json"):
    registry_path, policies_path = Path(registry_path), Path(policies_path)
    registry = json.loads(registry_path.read_text())
    candidates = registry["candidates"]
    facts = validate_catalog(candidates)
    root = initialize(workspace)
    quality = inventory(root)
    receipts = [json.loads(path.read_text()) for path in (root / "acquisitions").glob("*.json")] if (root / "acquisitions").exists() else []
    acquired = [r for r in receipts if any(a.get("sha256") for a in r["artifacts"])]
    acquired_ids = {r["official_identifier"] for r in acquired}
    parsed_ids = {row["official_identifier"] for row in quality["rows"] if row["quality"]["counts"]}
    queue = []
    for candidate in candidates:
        folder = root / "manual-inbox" / digest(candidate["official_identifier"])
        folder.mkdir(parents=True, exist_ok=True)
        template = {k: candidate[k] for k in ("official_identifier", "official_number", "title", "document_type",
                    "issuing_authority", "jurisdiction", "issuance_date", "publication_date")}
        template.update(file="REPLACE_WITH_ORIGINAL_FILENAME.pdf", source_url=candidate["source_url"],
                        acquired_at=None, is_synthetic=False)
        write_once(folder / "acquisition.template.json", template)
        queue.append(dict(official_number=candidate["official_number"], official_identifier=candidate["official_identifier"],
            source_page=candidate["source_url"], download_urls=candidate["download_urls"], destination=folder.as_posix(),
            state=("auto_acquired_pending_legal_review" if candidate["official_identifier"] in acquired_ids else "pending_manual_download_and_legal_review"),
            human_reviewed=False, legal_validity="unknown"))
    with database(root) as factory, factory.begin() as session:
        release = session.scalar(select(CorpusRelease).where(CorpusRelease.name == release_name))
        if release is None:
            release = put_record(session, CorpusRelease, name=release_name, created_at=datetime.now(timezone.utc), is_synthetic=False)
        if release.published_at is not None:
            raise ValueError("Existing draft is sealed; preserve it and create a separately reviewed release")
        release_id, created = release.id, release.created_at.isoformat()
    rows = _guide_rows([registry_path, base_registry], root, receipts)
    guide = root / "reports/manual-download-guide.md"
    _write_guide(guide, rows)
    worksheet = root / "reports/phase-d1-review-worksheet.md"
    _write_review_worksheet(worksheet, quality)
    draft = dict(schema_version=2, name=release_name, release_id=release_id, state="draft", created_at=created,
        is_synthetic=False, approved_publication=False, sealed=False, indexed=False, published=False,
        candidate_registry_sha256=file_hash(registry_path), policy_registry_sha256=file_hash(policies_path),
        candidate_identifiers=[c["official_identifier"] for c in candidates], document_versions=[], provision_versions=[],
        chunks=[], automated_downloads=len(acquired), manual_queue_count=len(queue), legal_review_approvals=0,
        blockers=["human legal review absent for every instrument", "some annex/amendment/multipart segments quarantined",
                  "exact cached tokenizer not provisioned; no inference"],
        notice="Research-only draft. Acquisition and parsing are not legal review; unknown-validity text is not 'current law'.")
    write_once(root / "reports/phase-d1-manual-queue.json", queue)
    write_once(root / "reports/phase-d1-draft-release.json", draft)
    report = dict(**facts, acquired_instruments=len(acquired),
        acquired_artifacts=sum(bool(a.get("sha256")) for r in receipts for a in r["artifacts"]),
        official_source_urls_resolved=sum(bool(c["download_urls"]) for c in candidates),
        manual_required=len(candidates) - len(acquired_ids),
        parsed_instruments=len(parsed_ids), parsed_stages=quality["parsed"],
        valid_provisions=quality["provision_counts"], quarantined_artifacts=quality["quarantined"],
        duplicate_documents=quality["duplicates"], missing_attachments=sum(not c["download_urls"] for c in candidates),
        reviewed=quality["reviewed"], sealed=0, indexed=False, chunks=0,
        current_law_applicability_confidence="unknown", draft_release_ready=False,
        draft_release_id=release_id, release_state="draft_unsealed", guide=guide.relative_to(root).as_posix(),
        quality=quality, notice="No success metric is asserted beyond what the preserved artifacts/evidence and pending stages show.")
    write_once(root / "reports/phase-d1-quality.json", report)
    return report


def prepare(registry_path="corpus/phase-d-candidates.json", policies_path="corpus/source-approvals.json",
            workspace="data/phase-d-corpus-v2", release_name="phase-d-authoritative-pilot-draft-v2"):
    registry_path, policies_path = Path(registry_path), Path(policies_path)
    registry=json.loads(registry_path.read_text())
    candidates=registry["candidates"]
    facts=validate_catalog(candidates)
    root=initialize(workspace)  # only a new isolated DB; existing app DB is never adopted
    quality=inventory(root)
    receipts=[json.loads(path.read_text()) for path in (root/"acquisitions").glob('*.json')] if (root/"acquisitions").exists() else []
    downloaded=sum(any(a.get('sha256') for a in r['artifacts']) for r in receipts)
    queue=[]
    for c in candidates:
        folder=root/"manual-inbox"/digest(c["official_identifier"])
        folder.mkdir(parents=True,exist_ok=True)
        # A deliberately incomplete template must not be accepted as an actual acquisition.
        template={k:c[k] for k in ("official_identifier","official_number","title","document_type","issuing_authority","jurisdiction","issuance_date","publication_date")}
        template.update(file="REPLACE_WITH_ORIGINAL_FILENAME.pdf",source_url=c["source_url"],acquired_at=None,is_synthetic=False)
        write_once(folder/"acquisition.template.json",template)
        queue.append(dict(official_number=c["official_number"],official_identifier=c["official_identifier"],
            source_page=c["source_url"],download_urls=c["download_urls"],destination=folder.as_posix(),
            state="pending_manual_download_and_legal_review",requirements=["all source attachments and annexes","original filename and retrieval timestamp","identity/scope/effective/amendment checks"],
            human_reviewed=False,legal_validity="unknown"))
    with database(root) as factory, factory.begin() as session:
        release=session.scalar(select(CorpusRelease).where(CorpusRelease.name==release_name))
        if release is None:
            release=put_record(session,CorpusRelease,name=release_name,created_at=datetime.now(timezone.utc),is_synthetic=False)
        if release.published_at is not None: raise ValueError("Existing draft is sealed; preserve it and create a separately reviewed release")
        release_id=release.id;created=release.created_at.isoformat()
    draft=dict(schema_version=2,name=release_name,release_id=release_id,
        state="draft",created_at=created,is_synthetic=False,approved_publication=False,sealed=False,indexed=False,published=False,
        candidate_registry_sha256=file_hash(registry_path),policy_registry_sha256=file_hash(policies_path),
        candidate_identifiers=[c["official_identifier"] for c in candidates],document_versions=[],provision_versions=[],chunks=[],
        automated_downloads=0,manual_queue_count=len(queue),legal_review_approvals=0,
        blockers=["official full text/annex acquisition blocked or awaits source approval","human legal review absent","exact tokenizer provisioning deferred; no inference"],
        notice="Candidate plan is not corpus membership. No discovered metadata page is represented as acquired legal full text.")
    write_once(root/"reports/manual-review-queue.json",queue)
    write_once(root/"reports/draft-release.json",draft)
    report=dict(**facts,downloaded_instruments=downloaded,downloaded_artifacts=sum(bool(a.get('sha256')) for r in receipts for a in r['artifacts']),
        parsed_instruments=len({r['official_identifier'] for r in quality['rows'] if r['quality']['counts']}),
        quarantined_artifacts=quality['quarantined'],duplicate_artifacts=quality['duplicates'],
        provision_counts=quality['provision_counts'],chunks=0,reviewed=quality['reviewed'],sealed=0,indexed=False,
        full_text_topic_coverage={},claimed_relationships=facts['title_reference_claims'],reviewed_relationships=0,
        missing_effective_date_claim=sum(c['effective_date_claim']['date'] is None for c in candidates),
        acquisition_provenance_completeness=None,discovery_provenance_complete=all(c['discovery_evidence_sha256'] for c in candidates),
        draft_release_id=release_id,release_name=release_name,release_state="draft_unsealed",
        review_queue=str(root/"reports/manual-review-queue.json"),manual_queue_count=len(queue),
        automated_downloads=0,legal_review_approvals=0,
        quality=quality,notice="No percentage computed for zero acquired artifacts; topic counts describe candidates, not validated text coverage.")
    write_once(root/"reports/corpus-quality.json",report)
    return report
