# Phase B — canonical legal metadata (SQLite)

This is storage infrastructure, **not an authoritative legal corpus or legal-status
inference engine**. The fixtures under `tests/fixtures/` and `tests/legal_fixtures.py`
are synthetic, labeled as such, and make no claims about Vietnamese law. No legal
portal was crawled. Gemini is never consulted to determine legal validity.

## Entities and boundaries

| Entity | Meaning / key rules |
|---|---|
| `LegalDocument` | Stable instrument identity: identifier, official number, type, title, issuing authority, jurisdiction, synthetic flag. Unique official identifier and jurisdiction/authority/number tuple. |
| `AcquisitionManifest` | Append-only discovery/policy/request record, source URL, timestamp, request key, review status, structured acquisition details; not a crawler. |
| `SourceArtifact` | An immutable source manifestation: document, first acquisition manifest, URL, original-byte SHA-256, media type, relative storage path, acquisition time. Same document/URL/hash deduplicates. |
| `DocumentVersion` | Immutable snapshot: source artifact, sequence, superseded snapshot, parsed-text hash, parser revision, title, issuance/publication dates, effective interval, explicit validity/review status and verification timestamp. |
| `LegalProvision` | Stable logical identity within a document, unique document/locator, kind, initial parent and ordering. Callers use full scoped locators where numbering repeats. |
| `ProvisionVersion` | Exact text/hash, source page/span, optional structured table/annex data, legal interval/status, and parent **in this document version**. Same logical provision can move without rewriting history. |
| `LegalRelationship` | Reviewed amendment/repeal/replacement/implementation/consolidation assertion with document/provision endpoints, effective date, source artifact and evidence locator. |
| `TerritorialApplicability` | Version-bound area identifier/name and half-open applicability interval, with source evidence. Renames/successors are new rows, not overwritten names. |
| `CorpusRelease` | Named synthetic/real release, creation time, one-way publication seal and canonical manifest hash. |
| `CorpusReleaseDocument` | Pins exactly one document version per instrument in a release. |
| `CorpusReleaseRelationship` | Pins reviewed legal relationships to a release instead of silently incorporating future assertions. |
| `ReviewStatus` | Checked enum: `pending`, `needs_review`, `approved`, `rejected`; not an LLM score. |

The source schema is `backend/db/legal_schema_v1.py`; classes in
`backend/db/models/legal.py` use SQLAlchemy's declarative mapping of those frozen
tables. This avoids a second, drifting copy of migration 0002's schema. Do not edit
the frozen v1 schema/types to implement future revisions: introduce a new schema
revision and an explicit migration, then point future mappings at that revision.

## Hierarchy and preservation

Document → Part → Chapter → Section → Subsection → Article → Clause → Point.
Documents may omit container levels; clauses require articles and points require
articles/clauses. Annex, table and unstructured nodes retain material that does not
fit that chain, including preambles. A table can retain structured rows alongside
verbatim source text. No parsing/chunking pipeline is introduced here.

Composite foreign keys prevent cross-document parents, mismatched document/provision
versions, and parent snapshots from a different document version. SQLite triggers
reject invalid hierarchy ordering/self-parenting. Parent rows are inserted first;
historical snapshots are never repointed. Deleted numbering and renumbering require
explicit identity decisions, not inferred text matching.

## Legal time versus observation time

- Effective/expiry dates describe legal applicability; acquisition/verification
  timestamps describe evidence collection and review. They are separate fields.
- Legal intervals are **[effective_date, expiry_date)**. An expiry date is the first
  non-applicable date; acquisition adapters must normalize source wording explicitly.
- Null expiry means **unknown/open end**, not automatically “currently valid”.
- `unknown` remains unknown even with plausible dates. Non-unknown assertions require
  an approved review and verification timestamp; known dates do not create approval.
- `partially_expired` exists on both document and provision snapshots. Child provisions
  can have different intervals/statuses; partial validity never becomes blanket validity.
- `validity_on` evaluates stored reviewed assertions and interval boundaries. It is not
  a conflict-of-laws, transitional-case, or present-day legal reasoning system. A stored
  future-effective assertion is not promoted to current law merely because time passed.
- UTC timestamps reject naive inputs and round-trip with timezone information. Review
  freshness and source-policy thresholds belong to Phase C and later QA gates.

## Immutability, identifiers, and transactions

All legal records are append-only at the SQLite trigger level, including raw SQL
updates/deletes. Reviews/corrections create new document/provision snapshots referencing
their predecessor and source, not updates to old evidence. An artifact records its
first acquisition; later acquisition observations must retain that artifact identity
and be represented explicitly in manifests/future observation records, not overwrite it.
Physical file content must be checked against the stored SHA by Phase C acquisition.

`put_record` creates deterministic UUID5 identities, validates hashes and credential-free
source URLs, and compares repeated identities rather than issuing updates. IDs use
canonical JSON/UTC values, not Python's randomized hash. Logical provision identity
is document+locator; provision snapshots are document-version+provision. A changed
payload under either identity is a conflict, not an idempotent insert.

Database constraints cover required fields, checked enums, hashes, date intervals,
uniqueness, and foreign keys. Application helpers additionally verify text hashes,
URL credentials, relative storage paths, and timezone-aware timestamps. The service
entrypoint must be used for imports; a privileged SQLite administrator can of course
remove triggers or bypass application validation and is outside this trust boundary.

Caller owns the transaction:

```python
with session_factory.begin() as session:
    # put_record(...), add_release_document(...), add_release_relationship(...)
    # publish_release(...) only after all snapshots and reviews are complete
    pass
```

Helpers flush for FK validation but never commit. Exceptions roll back the entire unit
of work. No bulk UPDATE-based upsert is permitted. Keep transactions short; batch
inference runs outside SQLite and imports only after artifact validation.

## Corpus publication

Populate a new draft release, pin document versions/relationships, then publish once.
Publication requires reviewed document/provision snapshots and reviewed relationships
between included documents. Synthetic and real instruments cannot mix in a release.
The fingerprint binds document membership and complete version/provision snapshots,
territorial and relationship facts, source artifacts and acquisition manifests.
After publication no membership, content,
applicability or seal changes are allowed. A new release is required for corrections.
Reviewed text with unknown legal status may be stored/released, but remains unknown
for legal applicability; publication alone never certifies current law.

## Migrations and existing application data

- `0001_application`: creates the existing users/sessions/messages/sources tables only
  when absent. Compatible unversioned Phase A tables are adopted without rewriting
  rows; incompatible columns/types/nullability/PKs fail for manual review.
- `0002_legal_domain`: creates new legal tables, indexes, constraints and append-only
  triggers. It refuses arbitrary unversioned legal tables instead of stamping them.
- Startup now runs Alembic instead of `create_all`. Connection-level foreign keys
  and explicit SQLite BEGIN make migration DDL transactional in the supported runtime.
- Automatic destructive downgrades are disabled. No existing user/session/message
  table is dropped. Tests exercise empty and unversioned legacy SQLite databases only;
  no existing local database has been migrated during this implementation session.

Before a real local upgrade: stop writers, back up SQLite using its backup API (or a
consistent offline copy), inspect `DATABASE_URL`, then from repository root run:

```bash
uv sync --frozen
uv run --frozen alembic upgrade head
uv run --frozen alembic current
uv run --frozen alembic check
```

These commands operate on your configured local database; they are instructions,
not operations performed against existing data in this phase. Never stamp an
incompatible database to bypass the adoption guard.

## Deferred to Phase C

Official-source acquisition, robots/terms compliance, file persistence/verification,
parsing, legal review operations, clause-aware chunking, incremental updates, and
Qdrant index publication. Lookup/chat are not yet backed by the canonical legal tables.
