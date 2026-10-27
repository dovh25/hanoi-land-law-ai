# Environment setup and offline development

## One environment file

Use **repository-root `.env` only**. The tracked `.env.example` is the settings
template and contains no credentials. Never create `backend/.env` or
`frontend/.env`, and never expose backend secrets through `VITE_*` values.

```bash
python3 scripts/setup_env.py
```

This creates `.env` with mode `0600` and a cryptographically random JWT secret.
An existing file is left byte-for-byte unchanged: no rotation, merge or overwrite.
Reconcile incomplete existing files manually using `.env.example`. Its JWT
placeholder is deliberately rejected at runtime. The template leaves Gemini off
and its key empty; no provider key is needed for retrieval-only operation.

## Reproducible installation

Use Python **3.12**, uv and Node **22.21+ or 24**. `pyproject.toml` is the Python
dependency declaration; `uv.lock` pins the resolution. Requirements files are
documentation pointers, not independent installers. From repository root:

```bash
uv sync --frozen
uv lock --check
uv pip check
npm --prefix frontend ci --ignore-scripts --no-audit --no-fund
```

The base environment includes API/database, parsing and test dependencies, but
not torch/transformers/model weights. Extras `tokenizer`, `ml`, `crawl` and `eval`
are optional. Installing them does not authorize crawling, weights or live judges.
Optional torch uses the official CPU wheel index; remote model code remains off.
Ordinary installation may need package-network access; validation can use
`UV_OFFLINE=true` with an already provisioned environment. No new package install
or external documentation request is required to run the local checks.

## Offline startup

Run these commands from root in separate terminals:

```bash
uv run --frozen uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```bash
npm --prefix frontend run dev
```

Open `http://127.0.0.1:5173`; API documentation is at `http://127.0.0.1:8000/docs`.
Use installed `backend.*` imports, not `PYTHONPATH=backend` or old `main:app`
targets. Application startup validates settings, applies local Alembic migrations
and loads the bundled demo BM25 index. It does not initialize the separate neural
RAG pipeline, instantiate a live Gemini client or download weights.

- `/healthz`: process liveness.
- `/demo/readyz`: database and demo index readiness; expected 200 after startup
  with the bundled artifact and `MVP_ENABLED=true`.
- `/readyz`: separate authenticated RAG readiness; expected 503 until initialized.
- Public `/api/v1/demo/chat`: greetings, retrieval excerpts and scope refusals
  work offline. With generation disabled, source-grounded queries return
  `llm_disabled`, not a synthesized legal answer.
- Authenticated `/api/v1/chat`: separate path; returns 503 when live use is off.

SQLite defaults to `data/law.db` relative to repository root. Back up existing
databases before schema changes; follow [migration guidance](legal-data-model.md#migrations-and-existing-application-data).
No database is reset by this guide. Lookup includes bundled excerpts and can
also read local JSON under `DOCS_ROOT`; it is independent of Qdrant.

## How settings reach each process

- Pydantic Settings reads an absolute root `.env` path. OS environment overrides
  that file; injected application settings propagate through `settings_context`.
- Relative `DOCS_ROOT`, `LLM_USAGE_DB`, `MVP_DEMO_CORPUS_PATH` and the default
  relative SQLite URL resolve against repository root. Prefer absolute paths for
  custom database URLs.
- Vite's `envDir` points to root and exposes only `VITE_*`. Backend and frontend
  should agree on API origin/port; changing production frontend settings requires
  rebuilding assets.
- Compose injects `.env` into **backend only**, overrides container data/document
  paths and Qdrant host, and sends only the public API origin to frontend.
  Build contexts exclude `.env`. Loopback host ports and optional internal-only
  Qdrant are documented in [deployment](deployment.md).

## Configuration and consent controls

Values below are from **`.env.example`**, not necessarily Python fallbacks or
existing local/remote settings. In particular `Config.MODEL` falls back to
`gemini-2.5-flash-lite`, `MAX_LLM_CALLS_PER_TURN` to 5 and daily attempts to 20;
the template explicitly overrides these. Do not silently rotate existing values.

| Setting | Template value / purpose |
|---|---|
| `APP_MODE`, `LOG_LEVEL` | `development`, `INFO` |
| `JWT_SECRET_KEY` | Generated locally; missing/placeholder/short/low-diversity values rejected |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | 60 |
| `CORS_ORIGINS` | JSON array of localhost/loopback frontend origins; no wildcard |
| `ENABLE_LIVE_LLM`, `GEMINI_API_KEY` | `false`, empty; explicit approval and key required for live use |
| `MODEL` | `gemini-3.5-flash-lite`; verify exact account access before live use |
| `MAX_LLM_CALLS_PER_TURN`, `MAX_LLM_CALLS_PER_DAY` | 1 / 8 attempts; MVP forces a one-attempt turn |
| `MAX_LLM_OUTPUT_TOKENS` | 1024 per attempt |
| `LLM_REQUEST_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` | 20 / 0; timeout is per attempt, not whole-turn |
| `LLM_USAGE_DB` | `data/llm-usage.sqlite3`; failed attempts count; accounting failure refuses calls |
| `MVP_ENABLED`, `MVP_DEMO_CORPUS_PATH` | `true`, `backend/resources/mvp_demo_corpus.jsonl` |
| `MVP_TOP_K`, `MVP_MIN_SCORE`, `MVP_MIN_COVERAGE` | 6 / 5.0 / 0.5 |
| `MVP_RATE_LIMIT_PER_MINUTE`, `MVP_RATE_LIMIT_PER_DAY` | 6 / 60 per observed client IP; process-local |
| `MVP_MAX_MESSAGE_CHARS` | 1000 |
| `MVP_MAX_HISTORY_MESSAGES`, `MVP_MAX_HISTORY_CHARS` | 6 / 4000; generation has an additional smaller prompt bound |
| `DATABASE_URL` | `sqlite:///./data/law.db` |
| `MAX_HISTORY_MESSAGES`, `MAX_HISTORY_CHARACTERS` | 20 / 20000 for the separate authenticated path |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000`; public browser/build setting, never a credential |
| `DOCS_ROOT` | `law_crawler/vbpl_documents`; optional local JSON lookup |
| `EMBEDDING_DEVICE`, `ALLOW_MODEL_DOWNLOADS`, `ALLOW_REMOTE_MODEL_CODE` | `cpu`, `false`, `false`; optional neural workflows |
| `QDRANT_HOST`, `QDRANT_PORT` | `localhost`, 6333; optional neural retrieval only |
| `COLLECTION_NAME`, `VIETNAMESE_COLLECTION_NAME` | `laws`; verify historical schemas before any indexing |
| `VIETNAMESE_EMBEDDING_MODEL` | `AITeamVN/Vietnamese_Embedding_v2`; optional workflow, not MVP search |
| `RETRIEVAL_MODE`, `RETRIEVAL_K`, `TOP_K` | `dense`, 10, 3 for separate neural paths; `TOP_K <= RETRIEVAL_K` |

These are application safeguards, **not provider quotas or a zero-billing
guarantee**. SDK retries are disabled; application retries reserve extra attempts.
The shared SQLite ledger must persist across restarts and be shared by workers;
separate machines/filesystems do not automatically share budgets. Ephemeral free
hosting loses the ledger; process-local rate counters reset too. Live DeepEval
judges remain blocked. Do not enable external tracing or bypass the shared LLM
provider. Never paste credentials into commands, screenshots or documentation.

Demo chats are not saved server-side and reload clears browser conversations;
enabled generation still sends question/context/history to Google. Retained
authenticated chats persist until owner deletion; context limits are not retention
purges. See [architecture/privacy](architecture.md) before shared use.

## Offline checks

```bash
uv lock --check
uv pip check
uv run --frozen pytest -q
uv run --frozen pytest tests/test_main.py::test_healthcheck -q
uv run --frozen python -m compileall -q backend batch preprocess law_crawler benchmarks scripts tests evaluation
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend test
git diff --check
```

pytest blocks network sockets, disables downloads/tracing, injects deterministic
providers and uses temporary databases. Mocked indexing tests are not permission
to recreate a real collection; existing indexes require explicit destructive
confirmation. No ML inference, container build, public availability or generated
answer correctness is established by successful offline checks.
