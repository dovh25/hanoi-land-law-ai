"""Canonical mapped legal entities; versioned schema is shared with migration 0002."""
from backend.db.base import Base
from backend.db.legal_schema_v1 import metadata


def table(name):
    return metadata.tables[name].to_metadata(Base.metadata)


class LegalDocument(Base):
    __table__ = table("legal_documents")


class AcquisitionManifest(Base):
    __table__ = table("acquisition_manifests")


class SourceArtifact(Base):
    __table__ = table("source_artifacts")


class DocumentVersion(Base):
    __table__ = table("document_versions")


class LegalProvision(Base):
    __table__ = table("legal_provisions")


class ProvisionVersion(Base):
    __table__ = table("provision_versions")


class LegalRelationship(Base):
    __table__ = table("legal_relationships")


class TerritorialApplicability(Base):
    __table__ = table("territorial_applicability")


class CorpusRelease(Base):
    __table__ = table("corpus_releases")


class CorpusReleaseDocument(Base):
    __table__ = table("corpus_release_documents")


class CorpusReleaseRelationship(Base):
    __table__ = table("corpus_release_relationships")
