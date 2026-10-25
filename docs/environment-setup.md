# Phase A: local environment and offline development

## One environment file

Use **repository-root `.env` only**. `.env.example` is tracked and contains no credentials;
`.env` is ignored. Do not create `backend/.env` or `frontend/.env`.

From the repository root:

```bash
python3 scripts/setup_env.py
```

This creates `.env` with mode `0600` and a cryptographically random JWT secret.
If `.env` already exists, it is left byte-for-byte unchanged: no secret rotation,
automatic merging, or overwriting. Existing incomplete files must be edited manually
using `.env.example` as a reference. Do not copy its JWT placeholder into runtime use.

Edit the root `.env` in your editor. `GEMINI_API_KEY` is intentionally empty;
`ENABLE_LIVE_LLM=false`. No Gemini key is needed for offline startup or tests.
Never paste keys into terminal commands, screenshots, commits, or `VITE_*` variables.

## Reproducible installation

Supported Python: **3.12** (the existing local 3.12 interpreter is sufficient).
`pyproject.toml` is the sole dependency declaration; `uv.lock` pins the resolution.
The former requirements files are documentation pointers, not independent installers.
Do not use the old README's `pip install -e .` from `backend/`.

```bash
uv sync --frozen
uv pip check
npm --prefix frontend ci --ignore-scripts --no-audit --no-fund
```

Use Node 22.21+ or Node 24 for the built-in TypeScript-stripping security tests.
The default Python environment contains API/auth/database, LangGraph, provider SDK,
and test dependencies, but **not torch/transformers/embedding weights**.
`ml`, `crawl`, and `eval` are opt-in extras, not required for Phase A.
The optional torch resolution uses the official PyTorch CPU index; other packages
use PyPI. Installing an extra is not permission to run crawling or live evaluations.
Changing dependency declarations requires `uv lock`; ordinary setup uses `--frozen`.

## Offline startup

From the repository root, in separate terminals:

```bash
uv run --frozen uvicorn backend.main:app --host 127.0.0.1 --port 8000
npm --prefix frontend run dev
```

The installed `backend` package also imports from other working directories;
do not add `backend/` to `PYTHONPATH` or launch the old `main:app` target.
Startup validates settings and applies local Alembic migrations only. It does not
initialize RAG, contact Qdrant, instantiate Gemini clients, or download model weights.
Authentication, sessions, document lookup, and liveness work offline; legal chat
returns **503** when live LLM use is disabled. No synthetic legal answers are served.

- `/healthz`: process liveness; never probes models, Gemini, or Qdrant.
- `/readyz`: database + initialized RAG readiness; **503 is expected in offline mode**.
  It is a local state report, not a live provider/quota probe.
- SQLite defaults to `data/law.db`, resolved relative to repository root, not cwd.
  Back up existing data before schema changes; Phase B introduces guarded Alembic
  adoption of Phase A tables. See `docs/legal-data-model.md`. No existing database is reset.

## How settings reach each process

- FastAPI and legacy ingestion settings use Pydantic Settings with an absolute root
  `.env` path. OS environment overrides `.env`; explicit injected settings override both.
- Relative `DOCS_ROOT`, `LLM_USAGE_DB`, and the default relative SQLite URL resolve
  against repository root. Prefer absolute paths for custom database URLs.
- Benchmark/crawler commands explicitly read root `.env`, never a cwd-relative file.
  Invoke scripts as modules from root, e.g. `uv run --frozen python -m preprocess.ingest_data --help`.
  This is a help command only, not authorization to index.
- Vite uses root `envDir` and exposes only `VITE_*`; keep all backend secrets unprefixed.
- Compose explicitly injects root `.env` into **backend only** via `env_file`.
  It overrides container database/document/ledger paths and `QDRANT_HOST=qdrant`.
  Frontend receives only `VITE_API_BASE_URL`; `.env` is excluded from build contexts.
- A root `.env` used for Compose substitution does not implicitly populate containers.

Compose is CPU-first, has no GPU reservation, and binds host ports to loopback only.
The optional `retrieval` profile starts Qdrant without exposing a host port. Named
volumes persist new container data; old `qdrant_data/` is untouched and not migrated.
The default backend image intentionally has no ML extra; it is an offline foundation
image, not yet a complete legal QA deployment. Docker build/start was not required
to run the offline test suite.

## Configuration and consent controls

| Setting | Default / meaning |
|---|---|
| `APP_MODE` | `development`; `production` and `test` also supported |
| `JWT_SECRET_KEY` | Generated locally; missing, known-placeholder, short, or low-diversity values rejected |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | 60 |
| `CORS_ORIGINS` | JSON array of exact localhost/loopback frontend origins; no wildcard or credentialed CORS |
| `LOG_LEVEL` | `INFO`; Authorization/API-key/password logs and URLs redacted |
| `GEMINI_API_KEY` | Empty; manual input only when separately enabling approved live use |
| `MODEL` | `gemini-2.5-flash-lite`; availability/account entitlement not verified |
| `ENABLE_LIVE_LLM` | `false`; checked before lazy RAG startup and each live provider invocation |
| `MAX_LLM_CALLS_PER_TURN` | 1; entire graph, not just final answer |
| `MAX_LLM_OUTPUT_TOKENS` | 1024 per attempt |
| `MAX_LLM_CALLS_PER_DAY` | 8 application attempts per UTC day; persistent SQLite ledger; M2 live-test budget |
| `LLM_REQUEST_TIMEOUT_SECONDS` | 20 per attempt, not a whole-turn deadline |
| `LLM_MAX_RETRIES` | 0; optional bounded retries consume the same call budgets |
| `LLM_USAGE_DB` | `data/llm-usage.sqlite3`; failures count, ledger failure refuses requests |
| `EMBEDDING_DEVICE` | `cpu`; `auto` falls back to CPU; explicit unavailable `cuda` fails clearly |
| `ALLOW_MODEL_DOWNLOADS` | `false`; loaders resolve local paths/cached snapshots only |
| `ALLOW_REMOTE_MODEL_CODE` | `false`; no model-specific need has been approved or validated |
| `QDRANT_HOST`, `QDRANT_PORT` | `localhost`, 6333 for future host-side retrieval |
| `COLLECTION_NAME`, `VIETNAMESE_COLLECTION_NAME` | `laws`; legacy indexes can be incompatible—verify schema first |
| `RETRIEVAL_MODE`, `RETRIEVAL_K`, `TOP_K` | `dense`, 10, 3; `TOP_K <= RETRIEVAL_K` required |
| `MAX_HISTORY_MESSAGES`, `MAX_HISTORY_CHARACTERS` | 20 / 20000 for model context; no process-local history cache |
| `VITE_API_BASE_URL` | Public browser URL `http://127.0.0.1:8000` |

These are conservative application safeguards, **not Google's free-tier quotas or
a guarantee of zero billing**. Do not enable live use without separate authorization.
Provider/account quotas can be lower. The SDK's internal retries are disabled;
application retries reserve another attempt before transmission. Rate/quota failures
fail closed with a generic 503 and no paid fallback. A default five-call turn can
exhaust its budget if the inherited graph rewrites; this is intentional.
All workers must share the same ledger file; separate machines/volumes do not share
a global quota. Preserve the ledger across restarts; it must not be casually reset.
LLM tracing is disabled at the request boundary. Legacy live DeepEval judges are
blocked until their internal calls can be budgeted; installing `eval` does not enable them.

Persisted conversations have no automatic age-based deletion in Phase A. Owners
can delete sessions; bounded model context is not a data-retention purge. Agree a
retention policy before shared use. Existing JWT default/CORS/header-log defects
are fixed, but public hosting, rate limiting, cookie-based auth, and TLS are not
implemented deployment features.

## Offline checks

```bash
uv lock --check
uv pip check
uv run --frozen pytest -q
uv run --frozen pytest tests/test_main.py::test_healthcheck -q
uv run --frozen python -m compileall -q backend preprocess law_crawler benchmarks scripts tests
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend test
npm --prefix frontend run lint
git diff --check
```

pytest blocks network sockets, disables model download/tracing, uses explicit test
secrets and temporary SQLite databases, and injects deterministic providers. Destructive
indexing tests use mocks only. Legacy indexing now refuses existing collections unless
both `--recreate` and `--confirm-collection DELETE:<exact-name>` are supplied. Never
exercise that path against real data during Phase A.

## Remaining boundaries

No corpus, index, model weights, or Gemini account configuration is supplied by Phase A.
Real ML inference compatibility and Docker image builds need separate validation; do not
claim successful legal QA merely because liveness/tests pass. Phase B now provides
legal models/explicit validity metadata and migrations; authoritative acquisition,
applicability reasoning and verified citations remain later work.
