from datetime import date
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from backend.core.database import create_database, create_engine_only
from backend.db.migrate import upgrade_database
from backend.db.models.legal import (
    LegalDocument, SourceArtifact, DocumentVersion, LegalProvision, ProvisionVersion,
    LegalRelationship, TerritorialApplicability, CorpusReleaseDocument,
)
from backend.services.legal_service import (
    put_record, stable_id, sha256, validity_on, add_release_document, release_fingerprint,
)
from legal_fixtures import seed_synthetic, NOW


def test_persistence_hierarchy_and_synthetic_labels(seeded):
    factory, fixture = seeded
    with factory() as session:
        documents = session.scalars(select(LegalDocument)).all()
        assert len(documents) == 4
        assert all(doc.is_synthetic and doc.title.startswith("SYNTHETIC") for doc in documents)
        assert {doc.jurisdiction for doc in documents} == {"VN", "VN-HN"}
        point = session.get(LegalProvision, fixture["provisions"]["national", "point"].id)
        kinds = []
        while point:
            kinds.append(point.kind.value)
            point = session.get(LegalProvision, point.parent_id) if point.parent_id else None
        assert kinds == ["point", "clause", "article", "subsection", "section", "chapter", "part"]
        table = session.get(ProvisionVersion, fixture["pversions"]["hanoi", 1, "table"].id)
        assert table.structured_content["synthetic"] is True
        assert table.source_end > table.source_start
        artifact = session.get(SourceArtifact, fixture["artifacts"]["hanoi", 1].id)
        assert artifact.acquired_at == NOW
        assert artifact.acquired_at.date() != fixture["versions"]["hanoi", 1].effective_date


def test_temporal_unknown_partial_and_history(seeded):
    _, f = seeded
    old = f["versions"]["national", 1]
    assert validity_on(old, date(2021, 1, 1)) == "in_force"
    assert validity_on(old, date(2022, 1, 1)) == "expired"
    assert validity_on(old, date(2019, 1, 1)) == "not_yet_effective"
    current = f["versions"]["national", 2]
    assert current.supersedes_id == old.id
    assert validity_on(current, date(2026, 1, 1)) == "partially_expired"
    assert validity_on(f["pversions"]["national", 2, "clause"], date(2026, 1, 1)) == "partially_expired"
    assert validity_on(f["pversions"]["national", 2, "point"], date(2026, 1, 1)) == "expired"
    unknown = f["versions"]["unknown", 1]
    assert unknown.expiry_date is None
    assert validity_on(unknown, date(2026, 1, 1)) == "unknown"


def test_amendment_relationship_and_area_history(seeded):
    factory, f = seeded
    with factory() as session:
        link = session.get(LegalRelationship, f["relationship"].id)
        assert link.kind == "amends"
        assert link.to_document_id == f["documents"]["national"].id
        assert link.to_provision_id == f["provisions"]["national", "article"].id
        assert link.evidence_artifact_id == f["artifacts"]["amending", 1].id
        areas = session.scalars(select(TerritorialApplicability).order_by(TerritorialApplicability.valid_from)).all()
        assert areas[0].valid_until == areas[1].valid_from
        assert areas[0].area_name != areas[1].area_name


def test_idempotent_inserts(seeded):
    factory, first = seeded
    with factory.begin() as session:
        second = seed_synthetic(session)
        assert second["documents"]["national"].id == first["documents"]["national"].id
        assert len(session.scalars(select(LegalDocument)).all()) == 4
        assert len(session.scalars(select(DocumentVersion)).all()) == 5


def test_identity_conflict_refuses_update(seeded):
    factory, f = seeded
    doc = f["documents"]["national"]
    with factory.begin() as session, pytest.raises(ValueError):
        put_record(session, LegalDocument, official_identifier=doc.official_identifier, title="changed")


@pytest.mark.parametrize("operation", [
    "UPDATE source_artifacts SET source_url='https://synthetic.invalid/tampered'",
    "UPDATE provision_versions SET text='tampered'",
    "DELETE FROM document_versions",
    "DELETE FROM legal_relationships",
    "UPDATE acquisition_manifests SET policy_revision='tampered'",
])
def test_provenance_is_append_only_even_raw_sql(seeded, operation):
    factory, _ = seeded
    with factory.begin() as session, pytest.raises(IntegrityError):
        session.execute(text(operation))


def test_hierarchy_cross_document_and_order_rejected(seeded):
    factory, f = seeded
    for parent, doc, kind in [
        (f["provisions"]["national", "article"].id, f["documents"]["hanoi"].id, "clause"),
        (f["provisions"]["national", "point"].id, f["documents"]["national"].id, "chapter"),
        (None, f["documents"]["national"].id, "point"),
    ]:
        with factory.begin() as session, pytest.raises(IntegrityError):
            put_record(session, LegalProvision, document_id=doc, parent_id=parent, kind=kind, locator=f"invalid-{kind}", ordinal=9)


def test_orphans_and_invalid_intervals_rejected(seeded):
    factory, f = seeded
    with factory.begin() as session, pytest.raises(IntegrityError):
        put_record(session, LegalProvision, document_id=stable_id("absent"), parent_id=None, kind="article", locator="orphan", ordinal=0)
    with factory.begin() as session, pytest.raises(IntegrityError):
        put_record(session, TerritorialApplicability, document_version_id=f["versions"]["hanoi", 1].id,
            area_identifier="invalid", area_name="SYNTHETIC", valid_from=date(2022, 1, 1), valid_until=date(2021, 1, 1),
            evidence_artifact_id=f["artifacts"]["hanoi", 1].id)


def test_release_seal_and_membership_are_immutable(seeded):
    factory, f = seeded
    with factory.begin() as session:
        assert release_fingerprint(session, f["release"].id) == f["release"].manifest_sha256
        with pytest.raises(ValueError):
            add_release_document(session, f["release"].id, f["versions"]["national", 1].id)
    with factory.begin() as session, pytest.raises(IntegrityError):
        session.execute(text("UPDATE corpus_releases SET name='tampered'"))
    with factory.begin() as session, pytest.raises(IntegrityError):
        session.execute(text("DELETE FROM corpus_release_documents"))


def test_released_version_cannot_gain_content(seeded):
    factory, f = seeded
    with factory.begin() as session, pytest.raises(IntegrityError):
        put_record(session, TerritorialApplicability, document_version_id=f["versions"]["hanoi", 1].id,
            area_identifier="new", area_name="SYNTHETIC", valid_from=date(2022, 1, 1), valid_until=None,
            evidence_artifact_id=f["artifacts"]["hanoi", 1].id)


def test_schema_validation_hashes_and_urls():
    with pytest.raises(ValueError):
        put_record(None, SourceArtifact, source_url="https://user:password@synthetic.invalid", sha256="0" * 64)
    with pytest.raises(ValueError):
        put_record(None, ProvisionVersion, text="SYNTHETIC", text_sha256=sha256("different"))
    with pytest.raises(ValueError):
        put_record(None, SourceArtifact, source_url="https://synthetic.invalid/?api_key=not-a-real-key")
    with pytest.raises(ValueError):
        put_record(None, SourceArtifact, storage_uri="../outside")


def test_unknown_expiry_never_infers_validity():
    from types import SimpleNamespace
    row = SimpleNamespace(validity_status="unknown", review_status="approved", verified_at=NOW,
                          effective_date=date(2020, 1, 1), expiry_date=None)
    assert validity_on(row, date(2026, 1, 1)) == "unknown"
    row.validity_status = "not_yet_effective"
    assert validity_on(row, date(2026, 1, 1)) == "unknown"


def test_synthetic_real_release_mix_is_rejected(seeded):
    from backend.db.models.legal import CorpusRelease
    from backend.services.legal_service import publish_release
    factory, f = seeded
    with factory.begin() as session:
        release = put_record(session, CorpusRelease, name="SYNTHETIC-invalid-real-release",
                             created_at=NOW, is_synthetic=False)
        add_release_document(session, release.id, f["versions"]["hanoi", 1].id)
        with pytest.raises(ValueError):
            publish_release(session, release.id)


def test_cross_document_provision_snapshot_rejected(legal_db):
    _, factory = legal_db
    with factory.begin() as session:
        f = seed_synthetic(session, publish=False)
    original = f["pversions"]["hanoi", 1, "article"]
    values = {column.name: getattr(original, column.name) for column in ProvisionVersion.__table__.columns if column.name != "id"}
    values.update(document_id=f["documents"]["national"].id,
                  document_version_id=f["versions"]["national", 2].id, parent_provision_id=None)
    with factory.begin() as session, pytest.raises(IntegrityError):
        put_record(session, ProvisionVersion, **values)


def test_annex_can_preserve_its_own_structured_articles(legal_db):
    _, factory = legal_db
    with factory.begin() as session:
        f = seed_synthetic(session, publish=False)
        article = put_record(session, LegalProvision, document_id=f["documents"]["hanoi"].id,
            parent_id=f["provisions"]["hanoi", "annex"].id, kind="article", locator="annex:1/article:1", ordinal=1)
        assert article.parent_id == f["provisions"]["hanoi", "annex"].id


def test_versioned_hierarchy_preserves_old_location(seeded):
    factory, f = seeded
    previous = f["versions"]["national", 2]
    with factory.begin() as session:
        values = {column.name: getattr(previous, column.name) for column in DocumentVersion.__table__.columns if column.name != "id"}
        values.update(sequence=3, supersedes_id=previous.id, parser_revision="SYNTHETIC-relocated-tree")
        new_version = put_record(session, DocumentVersion, **values)
        chapter = put_record(session, LegalProvision, document_id=previous.document_id,
            parent_id=None, kind="chapter", locator="SYNTHETIC-chapter:2", ordinal=2)
        original_chapter = f["pversions"]["national", 2, "chapter"]
        values = {column.name: getattr(original_chapter, column.name) for column in ProvisionVersion.__table__.columns if column.name != "id"}
        values.update(document_version_id=new_version.id, provision_id=chapter.id, parent_provision_id=None)
        put_record(session, ProvisionVersion, **values)
        original_article = f["pversions"]["national", 2, "article"]
        values = {column.name: getattr(original_article, column.name) for column in ProvisionVersion.__table__.columns if column.name != "id"}
        values.update(document_version_id=new_version.id, parent_provision_id=chapter.id)
        new_article = put_record(session, ProvisionVersion, **values)
        assert new_article.parent_provision_id != original_article.parent_provision_id
        assert session.get(ProvisionVersion, original_article.id).parent_provision_id == original_article.parent_provision_id


def test_migration_metadata_matches_orm(legal_db):
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    engine, _ = legal_db
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "backend/db/migrations"))
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.check(cfg)


def test_migration_preserves_legacy_rows_and_is_repeatable(tmp_path):
    engine = create_engine_only(f"sqlite:///{tmp_path / 'legacy.db'}")
    try:
        upgrade_database(engine, "0001_application")
        with engine.begin() as connection:
            connection.exec_driver_sql("INSERT INTO users VALUES (1, 'legacy', 'not-a-real-password-hash', '2020-01-01')")
            connection.exec_driver_sql("INSERT INTO chat_sessions VALUES ('legacy-session', 1, 'preserved', '2020-01-01', '2020-01-01')")
            connection.exec_driver_sql("INSERT INTO messages VALUES (1, 'legacy-session', 'user', 'preserved message', '2020-01-01')")
            connection.exec_driver_sql("DROP TABLE alembic_version")
        upgrade_database(engine)
        upgrade_database(engine)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT username FROM users")) == "legacy"
            assert connection.scalar(text("SELECT content FROM messages")) == "preserved message"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002_legal_domain"
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    finally:
        engine.dispose()


def test_migration_refuses_incompatible_schema_atomically(tmp_path):
    engine = create_engine_only(f"sqlite:///{tmp_path / 'bad.db'}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        with pytest.raises(RuntimeError):
            upgrade_database(engine)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM sqlite_master WHERE name='legal_documents'")) == 0
    finally:
        engine.dispose()
