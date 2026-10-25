# Phase C validation — offline ingestion and Colab Web

## Acceptance

- **Offline Phase C: PASS.** Synthetic local-file acquisition, extraction, review,
  canonical persistence, deterministic chunk export, ZIP exchange and verified
  `indexed=false` imports work end-to-end.
- **Colab Web preparation: PASS (offline/static/synthetic scope).**
- **Real Colab browser connectivity, model downloads, neural/GPU inference: NOT EXECUTED.**
  No GPU performance, numerical correctness or real legal QA readiness is claimed.

## Preflight and boundaries

The pre-change suite passed **119 Python tests**. Existing uncommitted Phase A/B work
was preserved. Reviewed the canonical models/schema, both migrations, legal service,
batch contracts/worker/transfers/local import, notebook and ViLeXa chunker.
The root `.env` exists, is Git-ignored, key configured **true**, live Gemini **disabled**.
No secret values were displayed or modified. No live application database was opened
or migrated. No crawl, Gemini request, weight download, existing Qdrant connection,
push, deployment or Git commit occurred. Only ordinary local Python dependencies
(BeautifulSoup, pypdf, python-docx and their dependencies) were installed through uv.

## Implementation inventory

Created:
- `preprocess/legal_parser.py`: bounded local TXT/HTML/PDF/DOCX extraction, NFC
  normalization, full ordered spans, Vietnamese hierarchy, tables/annex preservation,
  and quarantine diagnostics.
- `preprocess/legal_chunking.py`: deterministic source-span IDs, parent context,
  paragraph-aware bounded splits, synthetic byte counter and exact cached tokenizer mode.
- `preprocess/offline_ingestion.py`: isolated workspace, raw checksums/original filenames,
  restart/idempotence, append-only review journal, explicit sealing/export to Phase B tables.
- `preprocess/offline_cli.py`, `preprocess/synthetic_ingestion.py`: operator CLI and four
  synthetic local source formats, end-to-end smoke.
- `preprocess/migration_safety.py`: read-only backup, staging-only migration rehearsal,
  integrity/foreign-key/legacy-content checks, downgrade-refusal validation.
- `batch/archive.py`, `batch/colab.py`: strict ZIP gate, one-input/one-result Web exchange,
  complete/partial validation, safe reports and canonical import receipts.
- `tests/test_offline_ingestion.py`, `tests/test_colab_web.py` and updated encoder mocks.
- `colab-exchange/README.md` and four directory placeholders; generated artifacts ignored.
- `docs/offline-ingestion.md`, `docs/colab-web.md`, `docs/corpus-review.md`, this report.

Modified:
- `notebooks/embedding_batch.ipynb`: Colab Web upload/download, pinned install/runtime/GPU
  checks, verified one-ZIP bootstrap, optional checkpoint restore and execution reports.
- `preprocess/chunker.py`: canonical deterministic extension; legacy interface retained;
  optional splitter import stays lazy.
- `batch/contracts.py`, `local.py`, `worker.py`, `embedding.py`, `transfer.py`, `cli.py`:
  backward-compatible optional span provenance, canonical revalidation, OOM backoff,
  stronger loader checks, shared secure extraction and exchange commands. Legacy batch
  export/import no longer runs database migrations automatically.
- `pyproject.toml`, `uv.lock`, `.gitignore`, README, legacy Colab guide/link and Phase B
  handoff note. No new environment variables or frozen schema edits were needed.

Reused Phase B JSONL/JSON/float32-NPY contracts, validators, checkpoints, canonical models,
immutable insert/release helpers, migrations and synthetic encoder. No duplicate neural
encoder, new database server, Colab API server or Qdrant indexing implementation was added.

## Executed validation

| Check | Result |
|---|---|
| Baseline Python suite | 119 passed |
| Final Python suite | **173 passed; 0 failed; 0 skipped** |
| HTML/TXT/PDF/DOCX, Unicode, hierarchy, clause/point/table/annex, lossless spans | Passed synthetic fixtures |
| Long provision chunks, stable IDs, source hashes/context, incremental no-reparse | Passed |
| Duplicate identity/raw detection, review/quarantine gates, sealed history | Passed |
| Canonical export → vector generation → ZIP receive/import receipt | Passed with synthetic CPU vectors |
| Traversal/symlink/duplicate/unexpected entries and expansion/count limits | Rejected as expected |
| Checksum/revision/release/ID/count/dtype/dimension/NaN/Infinity incompatibility | Rejected as expected |
| Interrupted/zero-progress batches, checkpoint resume and mocked CUDA OOM | Passed; partial packages never imported |
| Full notebook execution | Passed with synthetic CPU and **mocked browser transport** |
| Notebook nbformat, all-cell syntax, cleared outputs, safe defaults | Passed |
| Migration backup/rehearsal | Temporary synthetic DB only; original bytes unchanged, legacy rows preserved, FK/integrity checks passed, destructive downgrade refused |
| Phase A/B regression coverage | Passed |
| Frontend lint / typecheck / build | Passed |
| Frontend security tests | **3 passed** |
| uv lock / dependency check / compileall / wheel+sdist build | Passed |
| Compose configuration / git diff whitespace check | Passed; no container started |
| Credential-pattern and sensitive-file exclusion scan | Passed across 5,581 source/build/archive entries; no secret values read for matching |
| Wheel/sdist contents and final input ZIP checks | Passed; new ingestion/exchange modules and existing migrations included, `.env`/databases/weights excluded |
| Exchange Git ignore rules | Generated ZIPs/reports ignored; README/placeholders versionable |

The real local CLI smoke created **4 synthetic documents, 43 chunks, 0 real documents**.
The generated input is at `colab-exchange/upload-to-colab/embedding-input.zip`, with
its SHA in `reports/pack-colab.json`. The download folder remains reserved for the
operator's browser result; local simulated output stays in `data/phase-c-smoke/`.
Local CLI `pack-colab`, `verify-colab` and `receive-colab` were also executed against
a temporary exchange with synthetic output; the default download directory was left empty.

## Model validation levels

Static review: unchanged checkpoint/revision, recorded pinned XLM-R/CLS/Normalize
configuration, 1,024-dimensional normalized dense output and 2,048-token reject policy.
Loader now verifies architecture, dimension, CLS-only pooling and Normalize module on
load. Learned-sparse use remains unsupported. Old indexes are not assumed compatible.
Synthetic tests mock those configuration checks; **no real weights were loaded**.

Real CPU/GPU vector agreement, GPU allocation, available RAM/VRAM, download/install
compatibility in an actual Colab runtime and real reranker quality remain unexecuted.
The optional exact local tokenizer is not installed/cached by ordinary tests; real
release sealing fails explicitly until the operator provisions it.

## Known limitations and next phase

Parsing is conservative, not universal legal-format understanding. Scanned PDFs/OCR,
DOCX automatic numbering/tracked changes/embedded content and ambiguous TOCs require
reviewed renditions; PDF layout and DOCX note placement need visual review. Numbering
patterns are Vietnamese single-letter points/numeric clauses; unusual formats require
explicit parser review. Raw/normalized provenance is retained, not PDF byte coordinates.
Large batches require smaller releases; pagination is not automated. Review journals
are local append-only/hash-linked, not cryptographic signatures or a multi-user audit system.
Filesystem/SQLite sealing has a documented crash-recovery boundary. No automatic live
index publication/revocation, legal-status reconciliation or transitional reasoning exists.

Recommend **Phase D — controlled pilot crawl**, only after explicit approval of a small
source list (candidate official portals require terms/robots/access-policy review),
document scope, rate limits, retention/license policy and a stop/retry plan. A human
must verify source identity, effective/repeal/amendment evidence, Hanoi territorial
applicability and extraction/chunk citations. Real tokenizer provisioning, a small manual
Colab run, local CPU compatibility checks and retrieval evaluation block any live index
switch. No crawler or pilot crawl was started here.
