# Local and hosted deployment

## Local development

Follow [environment setup](environment-setup.md) from the repository root:

```bash
python3 scripts/setup_env.py
uv sync --frozen
npm --prefix frontend ci --ignore-scripts --no-audit --no-fund
```

Run the API and Vite in separate terminals:

```bash
uv run --frozen uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```bash
npm --prefix frontend run dev
```

The UI is at `http://127.0.0.1:5173`; API documentation is at
`http://127.0.0.1:8000/docs`. Use root `.env` only. Existing databases are migrated
at startup; back them up before schema upgrades. Setup never overwrites secrets.

## Production frontend: Cloudflare Pages

The recorded production origin is `https://hanoi-land-law-ai.pages.dev`, backed by
the [preserved release evidence](ui-redesign/implementation-summary.md#deployment-readiness).
This guide records configuration, not a new public availability check.

With repository root as the build working directory:

| Setting | Value |
|---|---|
| Install | `npm --prefix frontend ci --ignore-scripts --no-audit --no-fund` |
| Build | `npm --prefix frontend run build` |
| Output directory | `frontend/dist` |
| Build environment | Node 22.21+ or 24; `VITE_API_BASE_URL=https://hanoi-land-law-ai-demo.onrender.com` |

Vite loads root settings, and only `VITE_*` values are exposed. The API origin is
public and compiled into assets; changing it requires a rebuild. Never configure
Gemini/JWT secrets as frontend build variables. `frontend/public/_redirects`
contains `/* /index.html 200` so `/lookup` refreshes correctly.

For a local production preview after building, run
`npm --prefix frontend run preview -- --host 127.0.0.1 --port 5173`; using port
5173 keeps the default development CORS allowlist applicable. Preview is not a
production application server.

## Production backend: Render

[`render.yaml`](../render.yaml) defines a Python 3.12.8 free web service in
Singapore, branch `main`, with automatic deployment disabled. Creating/updating
the service and pushing code are separate authorized operations.

Build:

```bash
pip install --upgrade uv && uv sync --frozen --no-dev
```

Start (Render supplies `PORT`):

```bash
uv run --frozen --no-dev uvicorn backend.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
```

Health-check path: **`/demo/readyz`**. The bundled artifact is included in the
repository; no Qdrant or embedding service is required. Startup still applies
application migrations and needs writable SQLite storage.

Required configuration:

- `APP_MODE=production`; strong `JWT_SECRET_KEY` (Blueprint generates it).
- `CORS_ORIGINS=["https://hanoi-land-law-ai.pages.dev"]`, or the exact authorized
  frontend origins. No wildcard, trailing path or credentials.
- `MVP_ENABLED=true`; default bundled corpus path.
- `ENABLE_LIVE_LLM=true` in the Blueprint following explicit production activation
  approval on 2026-10-27. A valid backend-only `GEMINI_API_KEY` secret is required.
  Set `ENABLE_LIVE_LLM=false` for retrieval-only hosting; local setup remains off.
- `ALLOW_MODEL_DOWNLOADS=false`, `ALLOW_REMOTE_MODEL_CODE=false` in both modes.
- Blueprint generation settings: `MODEL=gemini-3.5-flash-lite`, one attempt/turn,
  eight/day, 1,024 output tokens, 20-second attempt timeout, zero retries. The
  provider/account model must be verified before separately approved live use;
  this document does not certify availability.
- Enter `GEMINI_API_KEY` as a backend secret only and retain all budget controls.
  Confirm provider model access and account billing/quota settings before live
  traffic. Production activation is separate from ordinary local setup.

Code-only `Config.MODEL` falls back to `gemini-2.5-flash-lite`; the template and
Blueprint explicitly override it. Earlier service settings can differ from the
Blueprint; inspect deployed metadata rather than inferring current settings from
an old report. The earlier recorded UI release verified `llm_enabled=false`;
changing the Blueprint alone does not establish that the running service is enabled.

### Storage, proxy and scale prerequisites

Free-host filesystem data can disappear on restart/redeploy. SQLite usage ledgers,
accounts and sessions are not durable there; per-IP counters are process-local.
Do not describe these controls as a persistent global provider quota. Use shared,
durable accounting and an appropriate storage plan before multi-instance or
unattended use; this repository does not implement distributed limiting.

The start command trusts forwarded headers from any peer. It is appropriate only
behind controlled Render ingress that sanitizes those headers; do not copy that
trust setting to an exposed standalone server. IP limits are cost guards, not
authentication. Keep backend credentials out of logs and build artifacts.

## Containers

The backend Dockerfile installs frozen runtime dependencies without ML extras;
the frontend Dockerfile/Compose service runs development Vite, not Pages-style
static production serving. Root `.env` is excluded from image contexts and passed
only to the backend at runtime. Compose binds host ports to loopback, persists new
backend data in a named volume, and keeps Qdrant behind the optional `retrieval`
profile without a published host port. Existing host data is not auto-migrated.

```bash
docker compose config --quiet
docker compose up --build backend frontend
```

Building/pulling containers may need network access and is separate from offline
tests. Do not publish `docker compose config` output: resolved settings can contain
secrets. Container execution was not performed during repository cleanup.

## Deployment verification

After an explicitly authorized release, verify without invoking Gemini:

1. `/healthz` returns 200; `/demo/readyz` reports the initialized corpus/database.
2. `/api/v1/demo/info` reports two documents, 90 chunks, unknown validity and the
   expected `llm_enabled` value. These endpoints do not call the provider.
3. Confirm exact frontend CORS origin and exposed `Retry-After` header.
4. In the browser, open chat/library, refresh `/lookup`, inspect article/source
   navigation and test mobile/light/dark layout. A greeting uses no model call.
5. Only while generation is confirmed disabled, submit an in-scope retrieval
   question and inspect evidence/fallback rendering. Do not use a legal prompt as
   a free health check when generation is on.

Render cold starts can delay first requests. `/readyz` reports the separate
authenticated RAG state and is not the public MVP health target. No CI/CD workflow
is committed under `.github/`; local checks and recorded manual release evidence
must not be presented as an automated CI badge.
