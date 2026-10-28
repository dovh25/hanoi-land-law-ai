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

The canonical production frontend is `https://hanoi-land-law-ai.pages.dev`, backed by
the [preserved release evidence](ui-redesign/implementation-summary.md#deployment-readiness).
The legacy URL `https://hanoi-land-law.pages.dev` redirects to this application;
it is not an independent application deployment. Redirect and read-only backend
checks were performed on 2026-10-28, as recorded below.

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

### Legacy domain consolidation (verified 2026-10-28)

Both existing Pages projects belong to account `6dea4b2aa0a3efc4bdb326f1164b541f`.
Both use **Direct Upload**, production branch `main`, no connected Git repository,
no configured Pages build command/output directory, and no custom domains.
The build settings above describe the local canonical frontend build, not a
Cloudflare Git build pipeline.

| Project | Project ID | Production deployment after consolidation |
|---|---|---|
| `hanoi-land-law` (redirect only) | `a9d6b5a9-511f-4aca-93e1-7da0019eac57` | `14269eae-1ca4-41f7-8b87-e09c3727b9ed` |
| `hanoi-land-law-ai` (canonical, unchanged) | `865c0da9-77bc-4966-99ed-86ef4976fa41` | `b35fae5d-8397-4a72-838d-1eb0ee86f6af` |

The old production deployment was `9a00398a-eb3f-4283-987a-e2fe6d34d090`.
Its root served the legacy application (HTTP 200), and production settings included
`BACKEND_ORIGIN=https://land-law-chatbot.onrender.com` and an encrypted
`INGRESS_SECRET`. The obsolete `BACKEND_ORIGIN` was removed from the old project's
production configuration. The encrypted secret was left untouched; the new static
deployment has no Functions, JavaScript, API client or backend dependency.
Both projects have empty preview environment settings; the canonical project also
has empty production environment settings because its API URL is compiled locally
into the frontend assets, rather than supplied by a Pages build.

The minimal source is [`deploy/legacy-pages`](../deploy/legacy-pages). Its native
Pages `_redirects` rules issue **301** redirects over HTTPS:

- `/` → canonical `/`.
- `/lookup` and `/lookup/` → canonical `/lookup`.
- Legacy `/chat`, `/chat/:sessionId`, `/login`, and all other paths → canonical `/`.
  Only `/` and `/lookup` are distinct supported canonical pages.
- Incoming query strings are preserved, including encoded values.

Rules were first deployed and verified with 302, including browser navigation,
then redeployed with 301. The final deployment status is `success`. To maintain
this redirect, upload **only** that directory to the **old** project:

```bash
wrangler pages deploy deploy/legacy-pages --project-name hanoi-land-law --branch main
```

Do not upload the application build to `hanoi-land-law`, delete that project, or
replace the canonical frontend's SPA `_redirects` file with these external rules.
There is no Git integration that could automatically restore the old application.
The redirect source is in this repository, but deployment is managed by Direct
Upload, not automated Git builds. Committing or pushing these files does not
trigger a deployment of either Pages project.

Actual verification results:

- Ten fresh HTTP route/query/API-path checks each returned one 301 followed by
  canonical HTTP 200, without loops or third-party redirect destinations.
- Playwright in a fresh browser context verified redirected root, library query,
  legacy chat, and direct canonical access: current UI, no password/login form,
  no JavaScript or console errors.
- Mobile viewport 390×844: redirected UI rendered, chat input visible, document
  width 390px (no horizontal overflow).
- Browser requests reached only the two Pages hostnames and
  `https://hanoi-land-law-ai-demo.onrender.com`. Demo info, document types and
  document listing returned 200; no requests targeted the old backend.
- Current backend `/healthz`, `/demo/readyz`, `/api/v1/demo/info`: 200. Readiness
  reported `demo_rag=true`, `live_llm_enabled=true`; info reported anonymous MVP
  corpus metadata and model `gemini-3.5-flash-lite`. No chat/generation request was
  made. Canonical CORS preflight: 200 with exact canonical origin; legacy origin:
  400 with no CORS allowance. Backend settings/keys/quotas were not changed.
- Cloudflare API snapshots confirmed the entire canonical project configuration
  and production deployment were unchanged before/after the operation.

The old Render backend `https://land-law-chatbot.onrender.com` remains running
(`/healthz` returned 200). It is absent from the active canonical frontend assets
and browser traffic. No Render service or historical Pages deployment was deleted;
historical deployment-specific URLs were not retired. Other consumers of the old
backend have not been ruled out. Decommissioning it requires a dependency review
and explicit approval. No new project, Worker, backend, database or paid resource
was created, and no Gemini generation was invoked.

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
