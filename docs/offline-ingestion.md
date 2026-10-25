# Phase C: offline local-file legal ingestion

This pipeline reads **local files only**. It does not crawl, query Gemini, connect to
Qdrant, read application credentials, or migrate the configured application database.
It preserves ViLeXa's legacy APIs and adds deterministic canonical chunking through
`VietLegalChunker.chunk_canonical`. The old random-ID JSON chunker is not used for
Phase C canonical exports.

## Quick synthetic end-to-end run

```bash
uv sync --frozen
uv run --frozen python -m preprocess.offline_cli --workspace data/phase-c-smoke smoke
uv run --frozen python -m batch.cli pack-colab --input data/phase-c-smoke/embedding-input
```

This creates **four explicitly synthetic sources** (TXT/HTML/DOCX/text PDF), stages
and reviews them as unknown-validity fixtures, seals a synthetic release, exports
bounded chunks, and computes **synthetic CPU hash vectors**. No model weights are
needed. Repeating the command resumes/validates the completed smoke run. The local
`data/phase-c-smoke/embedding-output.zip` is a simulated result for offline testing,
**not a download or real Colab execution**.

To exercise the receiver without Colab, optionally copy that simulated ZIP to
`colab-exchange/download-from-colab/embedding-output.zip` (preserve any previous
download first), then run `verify-colab` and `receive-colab --workspace data/phase-c-smoke`.
Do not confuse those CPU reports with GPU evidence.

## Workspace isolation and stages

```text
data/offline-ingestion/
  workspace.json          # safety marker; existing directories are not adopted
  canonical.sqlite3       # NEW, isolated Phase B schema, never the application DB
  raw/<sha256>/<original-filename>
  stages/<stage-sha256>.json
  reviews/<stage-sha256>/00000.json ...
  releases/<release-manifest-sha256>.json
  reports/last-ingest.json
```

Initialization only migrates a **new empty** isolated database with existing Alembic
revisions `0001_application` / `0002_legal_domain`. Later commands require that schema
already be at head and never upgrade it implicitly. No Phase C DB schema change is
needed: staging/review/chunk manifests are immutable files; approved snapshots reuse
Phase B canonical tables. Serial operator writes use a workspace lock. Files and
database commits are not a distributed transaction: a crash after writing a sealed
manifest but before SQLite commit can leave an orphan manifest. Export always checks
canonical DB membership; retry sealing the same reviewed inputs, or preserve the
orphan and use a new release name. Never manually stamp the database.

## 1. File acquisition (manual, no crawling)

Put a permitted local source alongside its JSON acquisition manifest. Retain originals;
the pipeline copies bytes and verifies SHA-256 before parsing. Required metadata:

```json
{
  "file": "reviewed-local-document.html",
  "official_identifier": "OPERATOR_VERIFIED_IDENTIFIER",
  "official_number": "OPERATOR_VERIFIED_NUMBER",
  "document_type": "OPERATOR_VERIFIED_TYPE",
  "title": "Title verified against source",
  "issuing_authority": "Authority verified against source",
  "jurisdiction": "VN-HN",
  "source_url": "https://vbpl.vn/OPERATOR_VERIFIED_SOURCE_PATH",
  "acquired_at": "2026-10-25T09:00:00+07:00",
  "issuance_date": null,
  "publication_date": null,
  "is_synthetic": false
}
```

This is a **template, not an acquired or authoritative document**. Do not guess fields.
Missing/extra/invalid metadata is rejected. Unknown issuance/publication dates are null.
Effective/expiry/validity are supplied separately through explicit review, never inferred.

Source URL gate: HTTPS, no credentials/token parameters/fragment, standard port, host
`vbpl.vn`, `vanban.chinhphu.vn`, `congbao.chinhphu.vn`, `hanoi.gov.vn` or their subdomains.
This is a syntactic reviewed-host allowlist, **not a network verification, legal
authentication, or permission to crawl**. Extend it only after source/terms review.

Record `source_url` as the official **metadata/document page**, not a transient
attachment-storage URL. Phase D found `datafiles.chinhphu.vn`, `datafiles.hanoi.gov.vn`,
and `storage-vnportal.vnpt.vn` returning robots HTTP 403 and `vbpl.vn` document access
gated/ambiguous; the allowlist does not grant access and does not override those stops.
See [corpus-acquisition.md](corpus-acquisition.md) for the manual procedure.
Synthetic sources use `synthetic.invalid` and titles beginning `SYNTHETIC`.
Relative local paths only; symlinks/traversal are refused. Files are bounded to 20 MiB.
The manifest `source_url` must be the official **metadata/document page**, never the
transient file-CDN URL; the exact download URL, HTTP metadata and SHA-256 live in the
acquisition receipt under `<workspace>/acquisitions/`.

A human-populated inbox can be scanned instead of hand-editing manifests. Drop a downloaded
official file into `<workspace>/manual-inbox/<digest>/` and run:

```bash
uv run --frozen python -m law_crawler.pilot_cli scan-manual-inbox --workspace data/phase-d-corpus-v2 --ingest
```

The scanner matches the file to its approved candidate, verifies the document identity
against the extracted text, writes `acquisition.json`, detects byte duplicates, rejects
ambiguous or unmatched files without guessing, preserves originals, and ingests a pending
stage. See [phase-d1-validation.md](phase-d1-validation.md).

```bash
uv run --frozen python -m preprocess.offline_cli --workspace data/offline-ingestion init
uv run --frozen python -m preprocess.offline_cli --workspace data/offline-ingestion ingest --manifest path/to/acquisition.json
```

Copy the returned `stage_id`. Inspect the preserved raw file, stage JSON, normalized
text, nodes, spans, warnings, and `reports/last-ingest.json` before approving.

## 2. Parsing and legal structure

- UTF-8 TXT/HTML; NFC Vietnamese Unicode, normalized newlines/NBSP, no accent stripping.
  Source bytes remain unchanged. Scripts/styles/HTML head are non-content; visible
  body paragraphs, inline text, notes and tables remain ordered. No website chrome
  classifier silently removes text; supply a reviewed document-body rendition if needed.
- Text PDF via pypdf; page numbers retained. Blank/non-text pages quarantine the
  extraction. **OCR is unsupported**. Reading order, columns, tables and footnotes need
  visual review. No general-purpose parser can certify arbitrary legal PDFs automatically.
- DOCX via python-docx; paragraphs/tables in body order, notes/header/footer text appended
  in named-part order. Explicit/inherited automatic list numbering, tracked changes,
  text boxes, embedded content and nested tables are refused where detected; supply a
  reviewed explicit-number HTML/TXT rendition. Notes' original placement is not reconstructed.
- Hierarchy: Part → Chapter → Section → Subsection → Article → Clause → Point;
  annexes may have their own hierarchy. `đ)` is supported. Scoped locators avoid repeated
  clause numbers under different articles. Duplicate locators/orphan clause/point
  numbering quarantine rather than guessing. TOCs and combined instruments need cleanup.
- Preamble, headings, attachments, tables and trailing notes remain in non-overlapping
  provision spans. Normalized-text character offsets are exact; they are **not PDF
  byte coordinates**. Raw hash + parser revision + extracted-text hash bridge provenance.

Limits: at most 500 PDF pages, 4 million extracted characters; DOCX expands to at most
64 MiB/2,000 entries. Use trusted local sources; these libraries are not a sandbox for
arbitrarily hostile documents. Extraction quality always requires human review.

## 3. Metadata and legal review

See [`corpus-review.md`](corpus-review.md). Pending/quarantined extraction never enters
canonical ordinary current-law retrieval. Review is distinct from legal validity.
Acquisition time never becomes an effective date. Unknown end date never proves currency.

## 4. Deterministic legal-aware chunks

Each provision's exact source span is chunked separately; short clauses/points are not
split unnecessarily. Parent headings and document title are included. Oversized spans
prefer paragraph/sentence boundaries, then split at character boundaries that fit the
token budget. No whitespace or tail content is discarded; long context headings fail
with an action instead of being silently truncated.

Chunk metadata includes provision/document version IDs, source text hash, relative
character start/end within the provision, context, chunker/tokenizer/preprocessing IDs
and exact input hash. Stable IDs bind those facts. Canonical provision source offsets
map relative chunk spans back to the normalized full-document text.

Synthetic tests use a conservative `utf8-byte-budget-v1` counter, explicitly **not the
checkpoint tokenizer**. Real releases require `CachedTokenizerBudget`: the exact pinned
XLM-R tokenizer, cached locally, `local_files_only=True`, no remote code, no weights.
If tokenizer dependencies/cache are absent, sealing real releases fails clearly.
Provision text is verified locally again during vector import; Colab must also reject
anything over the shared 2,048-token policy. Default chunk target is 512 tokens.

## 5. Seal and export

```bash
uv run --frozen python -m preprocess.offline_cli --workspace data/offline-ingestion seal --name reviewed-research-v1 --stages STAGE_ID --purpose research --cached-tokenizer --approve-publication
uv run --frozen python -m preprocess.offline_cli --workspace data/offline-ingestion export --release RELEASE_MANIFEST_HASH --destination data/batches/reviewed-v1
uv run --frozen python -m batch.cli pack-colab --input data/batches/reviewed-v1
```

`--cached-tokenizer` requires the optional local tokenizer runtime/cache, provisioned
explicitly by the operator; **none is downloaded during ordinary setup/tests**. If no
cache is available yet, continue the complete synthetic workflow and report the blocker.
Research releases can contain reviewed text with unknown legal validity; current-law
purpose refuses unknown/partial/non-current/superseded/amended review assertions.
Synthetic and real metadata cannot mix. No mode indexes or publishes retrieval.

Release manifests bind source filenames/hashes/URLs, extraction/review events,
document/provision versions, canonical fingerprint, exact chunks/hashes, parser and
chunker versions, token policy, creation time and explicit approval. Publication flags
remain `indexed=false`, `published=false`. Phase B's `published_at` column is the
legacy **seal timestamp**, not live retrieval publication.

Duplicate raw bytes share content-addressed storage. Same stage/decision is idempotent;
changed bytes/parser/review create new immutable facts. Same canonical official number
under a different identity is refused. Correcting review after sealing blocks new exports
of the stale release; create a new release. Cross-stage semantic duplicate detection
and automatic amendment reconciliation are not inferred by this implementation.

## 6. Migration safety (not needed for this phase's live database)

No existing application database is opened/migrated by the offline commands above.
Before a future approved migration, identify the configured SQLite path privately,
stop writers, and run an explicit backup/rehearsal **only when approved**:

```bash
uv run --frozen python -m preprocess.offline_cli rehearse-migration --database /explicit/local/app.sqlite3 --destination data/migration-rehearsal-new
```

This uses SQLite's read-only connection + backup API, verifies backup integrity and
legacy row hashes, upgrades a separate staging copy, checks foreign keys/data, and
tests that destructive downgrade is refused. The original is never upgraded.
Rollback means restoring a verified backup to a new file, not destructive downgrade.
Reports contain hashes/count outcomes, not user message contents or database credentials.
Only synthetic temporary databases were rehearsed during Phase C validation.

## Failure handling

Metadata failure: correct manifest and retry. Quarantine: inspect raw/stage warnings,
provide a reviewed supported rendition, and ingest a new stage. Review rejection:
append a corrected decision, never rewrite the journal. Duplicate identity: reconcile
canonical identifiers manually. Sealing failure rolls back SQLite facts. Batch exceeds
10,000 records/64 MiB: split into smaller reviewed releases; automatic pagination is
not implemented. Vector/index publication is a separate future phase.
