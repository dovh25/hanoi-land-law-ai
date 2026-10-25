"""Synthetic metadata/text, deliberately unrelated to any real legal provisions."""
import json
from datetime import date, datetime, timezone
from pathlib import Path

from backend.db.models.legal import (
    LegalDocument, AcquisitionManifest, SourceArtifact, DocumentVersion, LegalProvision,
    ProvisionVersion, LegalRelationship, TerritorialApplicability, CorpusRelease,
)
from backend.services.legal_service import put_record, sha256, add_release_document, add_release_relationship, publish_release

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def seed_synthetic(session, publish=True):
    fixture = json.loads((Path(__file__).parent / "fixtures/legal_synthetic.json").read_text())
    documents, versions, provisions, pversions, artifacts = {}, {}, {}, {}, {}
    for name in ("national", "hanoi", "amending", "unknown"):
        documents[name] = put_record(session, LegalDocument, **fixture[name], is_synthetic=True)
        parent = None
        # Every legal hierarchy level is represented; roots can omit containers in real records.
        for ordinal, kind in enumerate(("part", "chapter", "section", "subsection", "article", "clause", "point")):
            provision = put_record(session, LegalProvision, document_id=documents[name].id,
                parent_id=parent, kind=kind, locator=f"{kind}:1", ordinal=ordinal)
            provisions[name, kind] = provision
            parent = provision.id
        annex = put_record(session, LegalProvision, document_id=documents[name].id,
            parent_id=None, kind="annex", locator="annex:1", ordinal=8)
        provisions[name, "annex"] = annex
        provisions[name, "table"] = put_record(session, LegalProvision, document_id=documents[name].id,
            parent_id=annex.id, kind="table", locator="annex:1/table:1", ordinal=0)
        provisions[name, "unstructured"] = put_record(session, LegalProvision, document_id=documents[name].id,
            parent_id=None, kind="unstructured", locator="preamble", ordinal=0)
        count = 2 if name == "national" else 1
        previous = None
        for sequence in range(1, count + 1):
            text = f"SYNTHETIC ONLY: {name} version {sequence}; no legal meaning."
            texts = {kind: text + f" SYNTHETIC {kind}." for doc_name, kind in provisions if doc_name == name}
            raw_text = "\n".join(texts.values())
            manifest = put_record(session, AcquisitionManifest,
                source_url=f"https://synthetic.invalid/{name}/{sequence}", discovered_at=NOW,
                policy_revision="synthetic-offline-v1", request_key=f"synthetic:{name}:{sequence}",
                review_status="approved", details={"synthetic": True, "network_requests": 0})
            artifact = put_record(session, SourceArtifact, document_id=documents[name].id,
                manifest_id=manifest.id, source_url=manifest.source_url, sha256=sha256(raw_text),
                media_type="text/plain", storage_uri=f"synthetic/{name}/{sequence}.txt", acquired_at=NOW)
            old = name == "national" and sequence == 1
            status = "expired" if old else "unknown" if name == "unknown" else "partially_expired" if name == "national" else "in_force"
            version = put_record(session, DocumentVersion, document_id=documents[name].id,
                source_artifact_id=artifact.id, sequence=sequence, title=documents[name].title,
                issuance_date=date(2020, 1, 1), publication_date=date(2020, 1, 2),
                effective_date=None if name == "unknown" else date(2020 if old else 2022, 1, 1),
                expiry_date=date(2022, 1, 1) if old else None,
                parser_revision="synthetic-parser-v1", text_sha256=sha256(raw_text),
                validity_status=status, review_status="approved", verified_at=NOW, supersedes_id=previous)
            versions[name, sequence] = version
            artifacts[name, sequence] = artifact
            previous = version.id
            for (doc_name, kind), provision in provisions.items():
                if doc_name != name:
                    continue
                ptext = texts[kind]
                pstatus = status
                if name == "national" and sequence == 2:
                    pstatus = "partially_expired" if kind == "clause" else "expired" if kind == "point" else "in_force"
                pv = put_record(session, ProvisionVersion, document_id=documents[name].id,
                    provision_id=provision.id, document_version_id=version.id, text=ptext,
                    parent_provision_id=provision.parent_id,
                    text_sha256=sha256(ptext), source_start=raw_text.index(ptext),
                    source_end=raw_text.index(ptext) + len(ptext), source_page=1,
                    structured_content={"synthetic": True, "rows": [["SYNTHETIC", "test"]]} if kind == "table" else None,
                    effective_date=version.effective_date,
                    expiry_date=date(2023, 1, 1) if pstatus == "expired" and not old else version.expiry_date,
                    validity_status=pstatus, review_status="approved", verified_at=NOW)
                pversions[name, sequence, kind] = pv
        if name == "hanoi":
            for start, end, label in ((date(2022, 1, 1), date(2025, 1, 1), "SYNTHETIC old area name"),
                                      (date(2025, 1, 1), None, "SYNTHETIC successor area name")):
                put_record(session, TerritorialApplicability, document_version_id=previous,
                    area_identifier="SYNTHETIC-HN-AREA", area_name=label, valid_from=start, valid_until=end,
                    evidence_artifact_id=artifacts[name, 1].id)
    relationship = put_record(session, LegalRelationship,
        from_document_id=documents["amending"].id, to_document_id=documents["national"].id,
        from_provision_id=provisions["amending", "article"].id,
        to_provision_id=provisions["national", "article"].id, kind="amends",
        effective_date=date(2022, 1, 1), evidence_artifact_id=artifacts["amending", 1].id,
        evidence_locator="SYNTHETIC article:1", review_status="approved", verified_at=NOW)
    release = put_record(session, CorpusRelease, name="SYNTHETIC-release-v1", created_at=NOW, is_synthetic=True)
    for name, doc in documents.items():
        add_release_document(session, release.id, versions[name, 2 if name == "national" else 1].id)
    add_release_relationship(session, release.id, relationship.id)
    if publish:
        publish_release(session, release.id)
    return dict(documents=documents, versions=versions, provisions=provisions,
                pversions=pversions, artifacts=artifacts, relationship=relationship, release=release)
