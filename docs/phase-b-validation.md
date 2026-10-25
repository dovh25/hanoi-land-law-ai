# Phase B validation — legal domain + interactive Colab preparation

## Acceptance

- **Phase B legal-domain foundation: PASS (offline scope).**
- **Colab preparation: PASS (contracts/notebook/static checks/synthetic CPU only).**
- **Real Colab GPU/model execution: NOT EXECUTED; no GPU integration claim.**

## Task 0 and environment

- Root `.env` exists and is Git-ignored. `GEMINI_API_KEY configured: true`.
- `ENABLE_LIVE_LLM=false`; offline backend settings load successfully.
- Existing `.env` was not edited, overwritten, copied into a bundle, or rotated.
  No new environment variables were needed; `.env.example` did not need Phase B changes.
- Phase A's **63 tests passed before implementation**. Existing uncommitted Phase A
  changes were preserved; no reset, commit, push, or deployment was performed.
- All new tests override credentials with isolated test values and block network.

## Implemented files / entities

- `backend/db/legal_types.py`, `legal_schema_v1.py`, `models/legal.py`:
  LegalDocument, AcquisitionManifest, SourceArtifact, DocumentVersion,
  LegalProvision, ProvisionVersion, LegalRelationship, TerritorialApplicability,
  CorpusRelease, CorpusReleaseDocument, CorpusReleaseRelationship, and checked
  ReviewStatus/ValidityStatus/ProvisionKind/RelationshipKind enums.
- `backend/services/legal_service.py`: deterministic immutable inserts, explicit
  transactions, release membership/sealing/fingerprints, conservative temporal checks.
- `alembic.ini`, `backend/db/migrate.py`, `backend/db/migrations/`:
  `0001_application` safe legacy adoption and `0002_legal_domain` schema/constraints/
  indexes/immutability guards. Startup uses migrations; existing application data is
  never automatically dropped. Only temporary SQLite databases were upgraded here.
- `batch/`: standalone validated JSONL/NPY contracts, shared lazy encoder,
  checkpoint/resume worker, ZIP/code transfer, local SQLite provenance validation and
  atomic filesystem import receipts, synthetic smoke, CLI, and bounded reranker module.
- `notebooks/embedding_batch.ipynb`, `notebooks/colab-requirements.txt`: guarded
  interactive execution, upload/download and recovery instructions; cleared outputs.
- Existing Vietnamese adapter/pipeline guards/benchmark wrapper now use the same
  pinned dense encoder. Legacy learned-sparse ingestion for that checkpoint refuses
  operation. No checkpoint switch or existing index modification occurred.
- Updated dependency/lock/package files, Docker package inclusion, notebook ignore
  exceptions, README/environment guide; added legal/model/Colab documentation.
- Added synthetic fixtures and legal, batch/artifact, and notebook tests. Fixtures
  explicitly say SYNTHETIC and reference `synthetic.invalid`, not official law.

## Executed checks

| Check | Actual result |
|---|---|
| Baseline Phase A pytest | 63 passed |
| Final offline pytest | **119 passed, 0 failed, 0 skipped** |
| Migration empty DB / unversioned Phase A adoption | Passed; user/session/message rows preserved |
| Alembic schema-vs-ORM check | Passed |
| Legal round trips, hierarchy, historical/partial/unknown validity, amendment links, immutability, idempotence, release seals | Passed |
| Artifact compatibility rejection, transfer, local canonical import, resume/no recompute | Passed |
| Notebook nbformat validation, all-cell Python syntax, cleared outputs | Passed |
| Notebook synthetic CPU cell (not a Colab runtime) | Passed |
| Real CLI synthetic CPU smoke, repeat/resume, pack/unpack, validate and code bundle | Passed |
| Python lock / installed dependency check / compileall | Passed |
| Python source distribution + wheel build | Passed |
| Frontend lint / TypeScript / build | Passed, zero lint warnings |
| Frontend security regression tests | 3 passed, 0 failed |
| Compose configuration validation | Passed; no container started |
| Secret patterns/local-secret exclusion, build/bundle exclusion, diff check/review | Passed |

The final secret scan checked 5,523 source/build/archive entries against configured
local secret values (without displaying them) and high-confidence credential patterns.
The rebuilt wheel and source distribution include migrations and the batch package;
neither they nor the code-only bundle contain the root `.env`.

Only ordinary project dependencies were installed into the local uv environment
(Alembic, notebook format validation and pinned NumPy). No ML weights, system packages,
GPU packages, Gemini requests, legal-site crawling or real Qdrant connections occurred.
Public model metadata and official Colab documentation were read to make compatibility
decisions; they were not acquired as a legal corpus.

## Compatibility decision and remaining limitations

- Checkpoint unchanged: `AITeamVN/Vietnamese_Embedding_v2` at
  `18b44161e041bf1d3a333ab5144b5b7b93f914d2`. Published module/config evidence establishes
  SentenceTransformer, 1024-dimensional CLS + L2 output and no supported sparse-head
  path. Token-length disagreement is handled by an explicit 2048-token reject policy.
- No real weights were loaded. Actual CPU/GPU vector agreement, local query latency,
  numerical inference and GPU memory/throughput remain unverified. Old BGEM3-loaded
  artifacts/indexes require explicit rebuilding; no silent compatibility is promised.
- Real Colab Google-account connection, widget/file transfer, Python/CUDA/package
  compatibility, runtime disconnection and reranker execution were **not tested**.
  Free GPU allocation is variable; users must select and validate a real runtime.
- CLI batches currently export whole provision snapshots and cap input size; Phase C
  must supply tokenizer-bounded chunking/pagination for larger documents/releases.
- Import stores validated artifacts + `indexed=false` receipt, not Qdrant vectors.
  No authoritative corpus, live legal QA integration or ingestion redesign was added.
- Acquisition/review operations, source-file verification, conflict/transitional
  reasoning, review freshness, and real index publication remain later work.
- SQLite backup/upgrade against existing user data and Docker image execution were
  not performed. Automatic destructive downgrades remain disabled.

## Next phase / manual prerequisites

Recommend **Phase C — offline ingestion**, beginning with parser/metadata/chunking
fixtures and local files, not crawling. Before acquisition: approve source policies,
curated source list and legal-review procedure. Before an existing DB upgrade: back
up SQLite and inspect the configured URL. Before real Colab inference: install official
Colab Web (see the superseding `docs/colab-web.md`), select a compatible GPU runtime, approve packages/
weights, verify the code-bundle SHA, then execute a small pilot and compare local CPU
queries to GPU outputs. A reviewed sealed release is required for canonical export/import.
