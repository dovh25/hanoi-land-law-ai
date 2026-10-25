"""Canonical inserts and release seals. Caller owns the surrounding transaction."""
import hashlib
import json
from datetime import date, datetime, timezone
from enum import Enum
from urllib.parse import urlsplit, parse_qsl
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from backend.db.legal_types import ReviewStatus, ValidityStatus
from backend.db.models.legal import (
    LegalDocument, SourceArtifact, DocumentVersion, LegalProvision, ProvisionVersion,
    CorpusRelease, CorpusReleaseDocument, CorpusReleaseRelationship, LegalRelationship, TerritorialApplicability,
    AcquisitionManifest,
)


def canonical(value):
    def default(item):
        if isinstance(item, datetime):
            return item.astimezone(timezone.utc).isoformat()
        if isinstance(item, date):
            return item.isoformat()
        if isinstance(item, Enum):
            return item.value
        raise TypeError("Unsupported canonical value")
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"), default=default)


def sha256(text):
    return hashlib.sha256(text.encode("utf-8") if isinstance(text, str) else text).hexdigest()


def stable_id(kind, *parts):
    return str(uuid5(NAMESPACE_URL, "hanoi-land-law-ai:" + kind + ":" + canonical(parts)))


def _validate(values):
    import re
    for name, value in values.items():
        if name in {"sha256", "text_sha256"} and not re.fullmatch("[0-9a-f]{64}", value):
            raise ValueError("Invalid SHA-256")
        if name.endswith("_url"):
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Source URL must be a credential-free HTTP(S) URL")
            if any(key.lower() in {"key", "api_key", "apikey", "token", "access_token", "signature"} for key, _ in parse_qsl(parsed.query)):
                raise ValueError("Credential-bearing source URLs are not permitted")
        if name == "storage_uri":
            from pathlib import PurePosixPath
            path = PurePosixPath(value)
            if not value or path.is_absolute() or ".." in path.parts or ":" in value or "\\" in value:
                raise ValueError("Artifact storage must be a relative corpus path")
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValueError("Timestamps require an explicit timezone")
    if "text" in values and sha256(values["text"]) != values.get("text_sha256"):
        raise ValueError("Provision text hash mismatch")


def put_record(session, model, **values):
    """Idempotent immutable insert; conflicting contents never become an UPDATE."""
    _validate(values)
    if model is LegalDocument:
        key = (values["official_identifier"],)
    elif model is SourceArtifact:
        key = (values["document_id"], values["source_url"], values["sha256"])
    elif model is LegalProvision:
        key = (values["document_id"], values["locator"])
    elif model is ProvisionVersion:
        key = (values["document_version_id"], values["provision_id"])
    elif model is CorpusRelease:
        key = (values["name"],)
    else:
        key = (values,)
    identifier = stable_id(model.__table__.name, *key)
    existing = session.get(model, identifier)
    if existing is not None:
        if any(canonical(getattr(existing, k)) != canonical(v) for k, v in values.items()):
            raise ValueError("Immutable identity already exists with different contents")
        return existing
    instance = model(id=identifier, **values)
    session.add(instance)
    session.flush()
    return instance


def add_release_document(session, release_id, document_version_id):
    version = session.get(DocumentVersion, document_version_id)
    if version is None:
        raise ValueError("Document version does not exist")
    existing = session.get(CorpusReleaseDocument, (release_id, version.document_id))
    if existing is not None:
        if existing.document_version_id != document_version_id:
            raise ValueError("Release already pins a different version")
        return existing
    member = CorpusReleaseDocument(release_id=release_id, document_id=version.document_id,
                                   document_version_id=document_version_id)
    session.add(member)
    session.flush()
    return member


def add_release_relationship(session, release_id, relationship_id):
    existing = session.get(CorpusReleaseRelationship, (release_id, relationship_id))
    if existing is not None:
        return existing
    member = CorpusReleaseRelationship(release_id=release_id, relationship_id=relationship_id)
    session.add(member)
    session.flush()
    return member


def release_fingerprint(session, release_id):
    members = session.scalars(select(CorpusReleaseDocument).where(
        CorpusReleaseDocument.release_id == release_id).order_by(CorpusReleaseDocument.document_id)).all()
    version_ids = [member.document_version_id for member in members]
    provisions = session.scalars(select(ProvisionVersion).where(
        ProvisionVersion.document_version_id.in_(version_ids)).order_by(ProvisionVersion.id)).all()
    territories = session.scalars(select(TerritorialApplicability).where(
        TerritorialApplicability.document_version_id.in_(version_ids)).order_by(TerritorialApplicability.id)).all()
    relationships = session.scalars(select(LegalRelationship).join(CorpusReleaseRelationship,
        CorpusReleaseRelationship.relationship_id == LegalRelationship.id).where(
        CorpusReleaseRelationship.release_id == release_id).order_by(LegalRelationship.id)).all()
    versions = session.scalars(select(DocumentVersion).where(DocumentVersion.id.in_(version_ids)).order_by(DocumentVersion.id)).all()
    documents = session.scalars(select(LegalDocument).where(
        LegalDocument.id.in_([m.document_id for m in members])).order_by(LegalDocument.id)).all()
    artifact_ids = {v.source_artifact_id for v in versions}
    artifact_ids.update(row.evidence_artifact_id for row in [*territories, *relationships])
    artifacts = session.scalars(select(SourceArtifact).where(SourceArtifact.id.in_(artifact_ids)).order_by(SourceArtifact.id)).all()
    manifests = session.scalars(select(AcquisitionManifest).where(AcquisitionManifest.id.in_(
        {artifact.manifest_id for artifact in artifacts})).order_by(AcquisitionManifest.id)).all()
    def snapshots(rows):
        return [{column.name: getattr(row, column.name) for column in row.__table__.columns} for row in rows]
    # Bind complete facts, not just IDs: review/parent/provenance changes must change the release hash.
    return sha256(canonical(dict(membership=[(m.document_id, m.document_version_id) for m in members],
        documents=snapshots(documents), versions=snapshots(versions), provisions=snapshots(provisions),
        territories=snapshots(territories), relationships=snapshots(relationships),
        artifacts=snapshots(artifacts), acquisitions=snapshots(manifests))))


def publish_release(session, release_id):
    release = session.get(CorpusRelease, release_id)
    if release is None:
        raise ValueError("Release does not exist")
    if release.published_at is not None:
        return release
    versions = session.scalars(select(DocumentVersion).join(
        CorpusReleaseDocument, CorpusReleaseDocument.document_version_id == DocumentVersion.id
    ).where(CorpusReleaseDocument.release_id == release_id)).all()
    if not versions or any(v.review_status != ReviewStatus.APPROVED for v in versions):
        raise ValueError("Release requires reviewed document versions")
    provision_rows = session.scalars(select(ProvisionVersion).where(
        ProvisionVersion.document_version_id.in_([version.id for version in versions]))).all()
    if ({row.document_version_id for row in provision_rows} != {version.id for version in versions}
            or any(row.review_status != ReviewStatus.APPROVED for row in provision_rows)):
        raise ValueError("Every release document needs reviewed provision snapshots")
    if any(session.get(LegalDocument, v.document_id).is_synthetic != release.is_synthetic for v in versions):
        raise ValueError("Synthetic and real documents must not be mixed")
    document_ids = {version.document_id for version in versions}
    links = session.scalars(select(LegalRelationship).join(CorpusReleaseRelationship,
        CorpusReleaseRelationship.relationship_id == LegalRelationship.id
    ).where(CorpusReleaseRelationship.release_id == release_id)).all()
    if any(link.review_status != ReviewStatus.APPROVED or link.from_document_id not in document_ids
           or link.to_document_id not in document_ids for link in links):
        raise ValueError("Release relationships must be reviewed and reference included documents")
    release.manifest_sha256 = release_fingerprint(session, release_id)
    release.published_at = datetime.now(timezone.utc)
    session.flush()
    return release


def validity_on(version, as_of: date):
    """Evaluate an explicitly reviewed assertion, not a prediction of legal status."""
    if (version.validity_status == ValidityStatus.UNKNOWN
            or version.review_status != ReviewStatus.APPROVED or version.verified_at is None):
        return ValidityStatus.UNKNOWN
    if version.effective_date is None:
        return ValidityStatus.UNKNOWN
    if as_of < version.effective_date:
        return ValidityStatus.NOT_YET_EFFECTIVE
    if version.expiry_date is not None and as_of >= version.expiry_date:
        return ValidityStatus.EXPIRED
    if version.validity_status in {ValidityStatus.EXPIRED, ValidityStatus.REPEALED}:
        return ValidityStatus.IN_FORCE if version.expiry_date is not None else ValidityStatus.UNKNOWN
    if version.validity_status == ValidityStatus.NOT_YET_EFFECTIVE:
        return ValidityStatus.UNKNOWN
    return version.validity_status
