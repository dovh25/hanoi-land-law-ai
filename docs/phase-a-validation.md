# Phase A implementation and validation

> **Phase A validation snapshot.** Test counts and runtime scope below are
> phase-specific. Use [current setup](environment-setup.md) and
> [architecture](architecture.md) for the bundled MVP.

## Delivered

- Created local ignored `.env` (0600) and versionable `.env.example`; bootstrap never
  overwrites existing values. `GEMINI_API_KEY configured: false`; live LLM disabled.
- Added `scripts/setup_env.py`, typed root-relative settings, and
  `docs/environment-setup.md`; removed stale setup/environment instructions from README.
- Canonical Python 3.12 project/lock, installed editable package, optional ML/crawl/eval
  extras, normalized requirements pointers. Backend imports no longer depend on cwd.
- Added `backend/services/llm.py`: lazy Gemini SDK, no SDK retries, per-turn and shared
  persistent UTC daily attempt budgets, output/time caps, safe failures, deterministic mock.
  Legacy live DeepEval judge calls are blocked rather than left unbudgeted.
- Refactored application factory/lifespan, injectable services, lazy pipeline imports,
  explicit liveness/readiness, request-local bounded history, atomic message-pair writes.
- Fixed JWT defaults, header logging/redaction, CORS, frontend literal article matching,
  print escaping, and frontend lint errors. Authentication/ownership are preserved.
- Added shared exact-name destructive-indexing guard; all verification uses mocks.
- Added CPU/device and cached-model helpers, disabled remote model code by default.
- Updated backend/frontend Dockerfiles, Compose, and build-context exclusions. Backend
  container runs non-root; host ports are loopback-only; Qdrant is private and opt-in.
- Created `tests/test_config.py`, `tests/test_llm.py`, `tests/test_safety.py`, replaced
  stale API tests/fixtures, and added built-in Node tests plus document-safety helpers.
  Updated local ignored `AGENTS.md` to remove obsolete audit guidance.

## Executed results

Tooling used: Python 3.12.15, uv 0.13.0, Node 24.21.0, npm 11.19.0.

| Check | Result |
|---|---|
| `uv sync --frozen` | Lightweight environment installed; no torch or model weights |
| `uv lock --check` | Pass |
| `uv pip check` | Pass; installed dependency set compatible |
| `uv run --frozen pytest -q` | **63 passed, 0 failed, 0 skipped** |
| Python `compileall` over application/scripts/tests | Pass |
| `uv build` | Source distribution and wheel built |
| Built archive contents / secret exclusion | Pass; backend namespace modules included; no `.env`/local secret contents |
| Frontend `npm ci --ignore-scripts --no-audit --no-fund` | Pass; dependency lockfile unchanged |
| Frontend lint / TypeScript / production build | All pass; zero lint warnings |
| Frontend `npm test` | **3 passed, 0 failed, 0 skipped** |
| `docker compose config --quiet` | Pass; no container started |
| Changed-file + frontend-output secret-pattern scan | Pass; locations-only reporting |
| `.env` ignore / permissions / template exception | Verified |
| `git diff --check` and source diff review | Pass |

The tests exercise authentication, unauthorized session access, rollback, offline
lifespan, disabled live use, retry/daily/concurrent budgets, mocked SDK limits,
CPU fallback, lazy imports/cache policy, indexing guards, and frontend injection fixes.
They use temporary SQLite and network-blocked pytest; no real Gemini, Qdrant, or
Hugging Face request was made. Package sources were PyPI, official PyTorch CPU index,
and npm registry only.

## Not executed / remaining limitations

- Docker image build/run: configuration validated only; no images pulled/containers started.
- Real ML inference, GPU operation, or model-specific remote-code compatibility:
  optional ML stack/weights were intentionally not installed or downloaded.
- Live Gemini/account/model availability and live DeepEval: forbidden in this phase.
- Browser/Playwright E2E: no existing suite; targeted frontend security tests use Node.
- No legal corpus, new index, legal schema, migrations, citation verification, or
  workflow redesign was implemented. Database table creation remains `create_all`.
- No automatic chat-retention purge or production deployment hardening was added.
  The default Docker image is offline-only; legal QA readiness is not claimed.
- No commit, push, deployment, real collection mutation, or existing-data deletion.

Next recommended phase: **Phase B — legal document domain model**, with offline
fixtures first and separate approval before any acquisition or live model work.
