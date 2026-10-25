"""Frozen schema for legal revision 0002. Never edit to implement later migrations."""
from sqlalchemy import (
    MetaData, Table, Column as C, String as S, Text, Integer as I, Boolean,
    Date, JSON, ForeignKey as FK, ForeignKeyConstraint as FKC,
    UniqueConstraint as UQ, CheckConstraint as CK, Index,
)
from backend.db.legal_types import (
    ReviewStatus, ValidityStatus, ProvisionKind, RelationshipKind, UTCDateTime, enum_type,
)

metadata = MetaData()


def identity():
    return C("id", S(36), primary_key=True)


def digest(name):
    return C(name, S(64), nullable=False)


def digest_check(name):
    return CK(f"length({name}) = 64 AND {name} NOT GLOB '*[^0-9a-f]*'", name=f"ck_{name}")


def temporal():
    return [
        C("effective_date", Date), C("expiry_date", Date),
        C("validity_status", enum_type(ValidityStatus), nullable=False),
        C("review_status", enum_type(ReviewStatus), nullable=False),
        C("verified_at", UTCDateTime()),
        CK("expiry_date IS NULL OR effective_date IS NULL OR expiry_date > effective_date", name="ck_legal_interval"),
        CK("review_status != 'approved' OR verified_at IS NOT NULL", name="ck_verified_review"),
        CK("validity_status = 'unknown' OR (review_status = 'approved' AND verified_at IS NOT NULL)", name="ck_validity_evidence"),
    ]


documents = Table("legal_documents", metadata, identity(),
    C("official_identifier", S(255), nullable=False, unique=True),
    C("official_number", S(120), nullable=False), C("document_type", S(80), nullable=False),
    C("title", Text, nullable=False), C("issuing_authority", S(255), nullable=False),
    C("jurisdiction", S(80), nullable=False, index=True),
    C("is_synthetic", Boolean, nullable=False, server_default="0"),
    UQ("jurisdiction", "issuing_authority", "official_number", name="uq_instrument_identity"),
)
manifests = Table("acquisition_manifests", metadata, identity(),
    C("source_url", Text, nullable=False), C("discovered_at", UTCDateTime(), nullable=False),
    C("policy_revision", S(120), nullable=False), C("request_key", S(255), nullable=False, unique=True),
    C("review_status", enum_type(ReviewStatus), nullable=False),
    C("details", JSON, nullable=False),
)
artifacts = Table("source_artifacts", metadata, identity(),
    C("document_id", S(36), FK("legal_documents.id", ondelete="RESTRICT"), nullable=False),
    C("manifest_id", S(36), FK("acquisition_manifests.id", ondelete="RESTRICT"), nullable=False, index=True),
    C("source_url", Text, nullable=False), digest("sha256"),
    C("media_type", S(120), nullable=False), C("storage_uri", Text, nullable=False),
    C("acquired_at", UTCDateTime(), nullable=False),
    UQ("document_id", "source_url", "sha256", name="uq_artifact_manifestation"),
    UQ("id", "document_id"), digest_check("sha256"),
)
versions = Table("document_versions", metadata, identity(),
    C("document_id", S(36), FK("legal_documents.id", ondelete="RESTRICT"), nullable=False),
    C("source_artifact_id", S(36), nullable=False),
    C("sequence", I, nullable=False), C("title", Text, nullable=False),
    C("issuance_date", Date), C("publication_date", Date),
    C("parser_revision", S(120), nullable=False), digest("text_sha256"),
    C("supersedes_id", S(36)),
    *temporal(),
    FKC(["source_artifact_id", "document_id"], ["source_artifacts.id", "source_artifacts.document_id"], ondelete="RESTRICT"),
    FKC(["supersedes_id", "document_id"], ["document_versions.id", "document_versions.document_id"], ondelete="RESTRICT"),
    UQ("id", "document_id"), UQ("document_id", "sequence"),
    CK("sequence > 0"), CK("supersedes_id IS NULL OR supersedes_id != id"), digest_check("text_sha256"),
)
provisions = Table("legal_provisions", metadata, identity(),
    C("document_id", S(36), FK("legal_documents.id", ondelete="RESTRICT"), nullable=False),
    C("parent_id", S(36)), C("kind", enum_type(ProvisionKind), nullable=False),
    C("locator", S(255), nullable=False), C("ordinal", I, nullable=False),
    UQ("id", "document_id"), UQ("document_id", "locator"),
    FKC(["parent_id", "document_id"], ["legal_provisions.id", "legal_provisions.document_id"], ondelete="RESTRICT"),
    CK("parent_id IS NULL OR parent_id != id"), CK("ordinal >= 0"),
)
provision_versions = Table("provision_versions", metadata, identity(),
    C("document_id", S(36), nullable=False), C("provision_id", S(36), nullable=False),
    C("document_version_id", S(36), nullable=False),
    C("parent_provision_id", S(36)),
    C("text", Text, nullable=False), digest("text_sha256"),
    C("source_start", I), C("source_end", I), C("source_page", I),
    C("structured_content", JSON),
    *temporal(),
    FKC(["provision_id", "document_id"], ["legal_provisions.id", "legal_provisions.document_id"], ondelete="RESTRICT"),
    FKC(["document_version_id", "document_id"], ["document_versions.id", "document_versions.document_id"], ondelete="RESTRICT"),
    FKC(["document_version_id", "parent_provision_id"], ["provision_versions.document_version_id", "provision_versions.provision_id"], ondelete="RESTRICT"),
    UQ("id", "document_id"), UQ("document_version_id", "provision_id"),
    CK("source_start IS NULL OR source_start >= 0"),
    CK("(source_start IS NULL AND source_end IS NULL) OR (source_start IS NOT NULL AND source_end > source_start)"),
    CK("source_page IS NULL OR source_page > 0"), digest_check("text_sha256"),
)
relationships = Table("legal_relationships", metadata, identity(),
    C("from_document_id", S(36), FK("legal_documents.id", ondelete="RESTRICT"), nullable=False, index=True),
    C("to_document_id", S(36), FK("legal_documents.id", ondelete="RESTRICT"), nullable=False),
    C("from_provision_id", S(36)), C("to_provision_id", S(36)),
    C("kind", enum_type(RelationshipKind), nullable=False),
    C("effective_date", Date),
    C("evidence_artifact_id", S(36), FK("source_artifacts.id", ondelete="RESTRICT"), nullable=False),
    C("evidence_locator", Text, nullable=False),
    C("review_status", enum_type(ReviewStatus), nullable=False), C("verified_at", UTCDateTime()),
    FKC(["from_provision_id", "from_document_id"], ["legal_provisions.id", "legal_provisions.document_id"], ondelete="RESTRICT"),
    FKC(["to_provision_id", "to_document_id"], ["legal_provisions.id", "legal_provisions.document_id"], ondelete="RESTRICT"),
    CK("review_status != 'approved' OR verified_at IS NOT NULL"),
)
territories = Table("territorial_applicability", metadata, identity(),
    C("document_version_id", S(36), FK("document_versions.id", ondelete="RESTRICT"), nullable=False),
    C("area_identifier", S(120), nullable=False), C("area_name", S(255), nullable=False),
    C("valid_from", Date, nullable=False), C("valid_until", Date),
    C("evidence_artifact_id", S(36), FK("source_artifacts.id", ondelete="RESTRICT"), nullable=False),
    CK("valid_until IS NULL OR valid_until > valid_from"),
    UQ("document_version_id", "area_identifier", "valid_from"),
)
releases = Table("corpus_releases", metadata, identity(),
    C("name", S(120), nullable=False, unique=True), C("created_at", UTCDateTime(), nullable=False),
    C("published_at", UTCDateTime()), C("manifest_sha256", S(64)),
    C("is_synthetic", Boolean, nullable=False, server_default="0"),
    CK("(published_at IS NULL AND manifest_sha256 IS NULL) OR (published_at IS NOT NULL AND length(manifest_sha256) = 64)", name="ck_release_seal"),
)
members = Table("corpus_release_documents", metadata,
    C("release_id", S(36), FK("corpus_releases.id", ondelete="RESTRICT"), primary_key=True),
    C("document_id", S(36), FK("legal_documents.id", ondelete="RESTRICT"), primary_key=True),
    C("document_version_id", S(36), nullable=False, index=True),
    FKC(["document_version_id", "document_id"], ["document_versions.id", "document_versions.document_id"], ondelete="RESTRICT"),
)
release_relationships = Table("corpus_release_relationships", metadata,
    C("release_id", S(36), FK("corpus_releases.id", ondelete="RESTRICT"), primary_key=True),
    C("relationship_id", S(36), FK("legal_relationships.id", ondelete="RESTRICT"), primary_key=True),
)

Index("ix_version_effectivity", versions.c.document_id, versions.c.effective_date, versions.c.expiry_date)
Index("ix_provision_parent", provisions.c.document_id, provisions.c.parent_id, provisions.c.ordinal)
Index("ix_provision_effectivity", provision_versions.c.provision_id, provision_versions.c.effective_date, provision_versions.c.expiry_date)
Index("ix_relationship_target", relationships.c.to_document_id, relationships.c.kind)
Index("ix_area_time", territories.c.area_identifier, territories.c.valid_from, territories.c.valid_until)
Index("ix_release_document_version", members.c.document_version_id)


def install_guards(connection):
    """Database-level append-only guarantees also cover Core/raw-SQL writes."""
    for table in metadata.tables:
        if table == "corpus_releases":
            continue
        for operation in ("UPDATE", "DELETE"):
            connection.exec_driver_sql(f"""CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation}
                BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'legal records are append-only'); END""")
    connection.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS immutable_release_delete
        BEFORE DELETE ON corpus_releases BEGIN SELECT RAISE(ABORT, 'releases are append-only'); END""")
    connection.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS seal_release
        BEFORE UPDATE ON corpus_releases WHEN OLD.published_at IS NOT NULL
        OR NEW.published_at IS NULL OR OLD.id != NEW.id OR OLD.name != NEW.name
        OR OLD.created_at != NEW.created_at OR OLD.is_synthetic != NEW.is_synthetic
        BEGIN SELECT RAISE(ABORT, 'release permits only one seal transition'); END""")
    connection.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS sealed_release_members
        BEFORE INSERT ON corpus_release_documents
        WHEN (SELECT published_at FROM corpus_releases WHERE id = NEW.release_id) IS NOT NULL
        BEGIN SELECT RAISE(ABORT, 'published membership is immutable'); END""")
    connection.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS sealed_release_relationships
        BEFORE INSERT ON corpus_release_relationships
        WHEN (SELECT published_at FROM corpus_releases WHERE id = NEW.release_id) IS NOT NULL
        BEGIN SELECT RAISE(ABORT, 'published relationships are immutable'); END""")
    for table in ("provision_versions", "territorial_applicability"):
        connection.exec_driver_sql(f"""CREATE TRIGGER IF NOT EXISTS sealed_{table}
            BEFORE INSERT ON {table} WHEN EXISTS (
                SELECT 1 FROM corpus_release_documents m JOIN corpus_releases r ON r.id=m.release_id
                WHERE m.document_version_id=NEW.document_version_id AND r.published_at IS NOT NULL)
            BEGIN SELECT RAISE(ABORT, 'released version content is sealed'); END""")
    connection.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS document_version_sequence
        BEFORE INSERT ON document_versions WHEN NEW.supersedes_id IS NOT NULL
        AND (SELECT sequence FROM document_versions WHERE id=NEW.supersedes_id) >= NEW.sequence
        BEGIN SELECT RAISE(ABORT, 'version predecessor must have a lower sequence'); END""")
    ranks = "CASE kind WHEN 'annex' THEN 0 WHEN 'part' THEN 1 WHEN 'chapter' THEN 2 WHEN 'section' THEN 3 WHEN 'subsection' THEN 4 WHEN 'article' THEN 5 WHEN 'clause' THEN 6 WHEN 'point' THEN 7 ELSE 8 END"
    new_rank = ranks.replace("kind", "NEW.kind")
    connection.exec_driver_sql(f"""CREATE TRIGGER IF NOT EXISTS legal_hierarchy
        BEFORE INSERT ON legal_provisions WHEN
        (NEW.kind IN ('clause', 'point') AND NEW.parent_id IS NULL)
        OR (NEW.kind IN ('part','chapter','section','subsection','article','clause','point')
            AND ({new_rank}) <= (SELECT {ranks} FROM legal_provisions WHERE id=NEW.parent_id))
        OR (NEW.kind='clause' AND (SELECT kind FROM legal_provisions WHERE id=NEW.parent_id) != 'article')
        OR (NEW.kind='point' AND (SELECT kind FROM legal_provisions WHERE id=NEW.parent_id) NOT IN ('article','clause'))
        BEGIN SELECT RAISE(ABORT, 'invalid provision hierarchy'); END""")
    parent_rank = ranks.replace("kind", "p.kind")
    child_rank = ranks.replace("kind", "c.kind")
    connection.exec_driver_sql(f"""CREATE TRIGGER IF NOT EXISTS version_hierarchy
        BEFORE INSERT ON provision_versions WHEN
        NEW.parent_provision_id = NEW.provision_id
        OR ((SELECT kind FROM legal_provisions WHERE id=NEW.provision_id) IN ('clause','point') AND NEW.parent_provision_id IS NULL)
        OR EXISTS (SELECT 1 FROM legal_provisions c JOIN legal_provisions p ON p.id=NEW.parent_provision_id
            WHERE c.id=NEW.provision_id AND c.kind NOT IN ('annex','table','unstructured') AND ({child_rank}) <= ({parent_rank}))
        OR ((SELECT kind FROM legal_provisions WHERE id=NEW.provision_id) = 'clause'
            AND (SELECT kind FROM legal_provisions WHERE id=NEW.parent_provision_id) != 'article')
        OR ((SELECT kind FROM legal_provisions WHERE id=NEW.provision_id) = 'point'
            AND (SELECT kind FROM legal_provisions WHERE id=NEW.parent_provision_id) NOT IN ('article','clause'))
        BEGIN SELECT RAISE(ABORT, 'invalid version hierarchy'); END""")
