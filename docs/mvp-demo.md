# MVP demo — corpus, retrieval, Gemini, and free-cloud runbook

> **Implementation-stage snapshot, retained as evidence.** Status, budgets and
> deployment statements below describe that stage, not the current checkout.
> Use [current setup](environment-setup.md), [deployment](deployment.md),
> [pipeline semantics](rag-pipeline.md) and [evaluation](evaluation.md) instead.
> In particular, citation checks are partial rather than per-claim proof; unknown
> markers alone do not necessarily reject an answer. Later recorded releases
> deployed the UI and verified generation disabled. Health routes `/demo/readyz`
> and `/readyz` are root routes, not under `/api/v1`.

## Status

This document describes the **public MVP demo** that is implemented and tested offline but
has **not** been deployed, and whose live Gemini path has **not** been run. It is not a
legal release and does not change the strict Phase D review/sealing gates.

| Item | State |
|---|---|
| Anonymous demo UI and API | Implemented |
| Bundled demo corpus | 2 documents, 90 chunks, 77,243 characters |
| Retrieval | Deterministic Vietnamese BM25, no embeddings/Qdrant |
| Live Gemini | Implemented but **disabled**; M2 approval required |
| Offline backend tests | 263 passed |
| Frontend lint/typecheck/build/tests | Passing (3 Node security tests) |
| Public deployment | **Not created**; M3 approval + Git remote/push required |
| Legal validity | `unknown` for every demo chunk |
| Legal review / seal / publication | None |

The historical ViLeXa benchmarks and the Phase D.2 research draft are unrelated to this
demo and must not be presented as validation of it.

## Architecture

```text
Browser (Cloudflare Pages, React)
   │  POST /api/v1/demo/chat   (no auth, no cookies, no persistence)
   ▼
FastAPI (Render Free, Python 3.12)
   ├─ in-memory per-client minute/day limiter
   ├─ MvpRagPipeline
   │    ├─ greeting / deterministic shortcut ──► no LLM call
   │    ├─ BM25 over bundled JSONL ──► sufficiency/scope gate
   │    │      └─ insufficient ──► abstain, no LLM call
   │    ├─ one Gemini call (only for sufficient evidence)
   │    └─ citation/date/article/quote validation
   │           ├─ valid ──► answer + evidence cards
   │           └─ invalid ──► reject answer, return verbatim excerpts
   └─ Gemini usage ledger (ephemeral SQLite on free hosting)
```

The demo path is intentionally separate from the authenticated `/chat`, `/lookup`, and
Agentic RAG paths, which remain available and unchanged for local/legacy use.

### Bounded turn

One standard successful turn performs at most **one** generation call:

1. Retrieve top-6 chunks.
2. Apply a domain gate, corpus-scope gate, explicit-citation check, and score/coverage
   thresholds.
3. If evidence is insufficient, return a deterministic Vietnamese abstention (zero calls).
4. Otherwise send the question plus bounded evidence excerpts to `gemini-2.5-flash-lite`.
5. Validate that every citation ID exists, every quoted span occurs in a cited excerpt,
   every `Điều N` occurs in the cited excerpts, and every date occurs in them.
6. Replace claims of current effect with neutral wording.
7. On any validation failure, discard the generated text and return the source excerpts.

There are no query-rewrite loops, judge calls, or retries in the demo path. The per-turn
call cap is forced to `1`; `LLM_MAX_RETRIES=0`.

## Demo corpus (`MVP_DEMO_CORPUS`)

Built by `scripts/build_mvp_demo_corpus.py` from the preserved Phase D workspace. The
builder only reads preserved artifacts and does not modify the canonical SQLite database.

| Document | Role in demo | Chunks |
|---|---|---:|
| `43/2024/QH15` | Amending instrument for several laws, including the Land Law | 7 |
| `88/2024/NĐ-CP` | Decree on compensation, support, and resettlement | 83 |

- **90 chunks / 77,243 characters**, exact parsed-text spans, official source page URL,
  stage/raw/parsed SHA-256 values in `backend/resources/mvp_demo_corpus.manifest.json`.
- Artifact hash: `ce0df852742ea3144ae5c04bdef27580d88d53752ad6039a4cdd0b091a73508e`.
- Every chunk is `validity_status=unknown`, `review_status=technical_validation_only`.
- `43/2024/QH15` is an **amending instrument**, not the complete Land Law
  `31/2024/QH15`.
- The `88/2024/NĐ-CP` annex/form template is excluded from operative retrieval.
- No embeddings, Qdrant collection, PDFs, or secrets are in the artifact.
- The following are deliberately excluded as multipart, quarantined, ambiguous, or
  annex-only: `31/2024/QH15`, `101/2024/NĐ-CP`, `102/2024/NĐ-CP`, `103/2024/NĐ-CP`,
  `133/VBHN-VPQH`.

### Validity caveats shown to users

The demo never asserts that a document is currently in force. Public sources indicate:

- `vbpl.vn` indexes `43/2024/QH15` as “Hết hiệu lực một phần” (updated 08/05/2026), but
  direct access returned HTTP 403 and was not verified here.
- Search results indicate `88/2024/NĐ-CP` was amended by `226/2025/NĐ-CP` and
  `49/2026/NĐ-CP`; this was not officially verified here.

Because validity, amendment status, and completeness are unresolved, the UI and API label
all evidence as “Hiệu lực: chưa xác minh” and the answer carries a research-demo disclaimer.

## Retrieval

`backend/services/mvp_corpus.py`

- Accent-folded Vietnamese tokenization; both accented and unaccented forms are indexed.
- BM25 (`k1=1.5`, `b=0.75`) with heading term boost, heading bigram boost, and an
  article-diversity cap (max 2 chunks per article).
- Explicit lookup: `Điều 30 Nghị định 88` and `43/2024` are honoured; an explicit article
  absent from the corpus abstains instead of falling back to unrelated text.
- Abstention reasons: `out_of_domain`, `outside_corpus_scope`,
  `explicit_citation_not_in_corpus`, `insufficient_evidence`, `weak_query_match`.
- Generic document overviews (`Nghị định 88 quy định gì?`) answer from `Điều 1`
  (`document_overview`).
- Defaults: `MVP_TOP_K=6`, `MVP_MIN_SCORE=5.0`, `MVP_MIN_COVERAGE=0.5`.

### Offline benchmark

```bash
uv run --frozen python scripts/evaluate_mvp_retrieval.py
```

Latest local run (20 fixed questions, not a legal-accuracy evaluation):

| Measure | Result |
|---|---:|
| Decision accuracy (answer vs abstain) | 1.00 |
| Abstention accuracy | 1.00 |
| Answerable hit@1 | 1.00 |
| Answerable hit@3 | 1.00 |
| Median latency | 63.49 ms |
| p95 latency | 116.37 ms |

Latency depends on hardware; the decision, hit, and abstention metrics are deterministic.
The script writes `data/mvp-retrieval-benchmark.json` (local, gitignored). Re-run it after
any corpus, tokenizer, or threshold change; do not carry these numbers over automatically.

## API

Base path: `/api/v1`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/demo/info` | Corpus counts, documents, exclusions, model/LLM flag, limits |
| `POST` | `/demo/chat` | Stateless question; optional bounded `history` |
| `GET` | `/demo/readyz` | Demo readiness (corpus + DB); use as Render health check |
| `GET` | `/readyz` | Legacy readiness; may stay 503 because the authenticated RAG is not initialized |

`POST /demo/chat` body:

```json
{
  "message": "Bồi thường khi Nhà nước thu hồi đất ở là gì?",
  "history": [
    {"role": "user", "content": "Xin chào"},
    {"role": "assistant", "content": "Chào bạn"}
  ]
}
```

History is bounded to 6 messages / 4,000 characters and is used only as prompt context;
nothing is stored server-side. The response includes `status`, `sources`, `warnings`,
`rejected_citations`, `llm_used`, `request_id`, and optional `abstention_reason`.

Statuses:

| Status | LLM calls | Meaning |
|---|---:|---|
| `answered` | 1 | Validated answer with evidence IDs |
| `greeting` | 0 | Greeting/thanks/capability reply |
| `abstained` | 0 | Domain/scope/evidence gate refused |
| `llm_disabled` | 0 | Retrieval-only mode (`ENABLE_LIVE_LLM=false`) |
| `llm_unavailable` | 0 | Provider timeout/quota/error; excerpts returned |
| `citation_rejected` | 1 | Generated text failed validation; excerpts returned |

Every chunk retains `validity_status=unknown`; the API never manufactures effective dates
or current-law claims. `request_id` is random and is not linked to the question.

## Privacy, rate, and cost controls

- Anonymous and stateless: no login, no session cookie, no database row, no message log.
- Per-client sliding-window limits: 6 questions/minute and 60/day by default.
- `429` includes `Retry-After`; the UI explains the wait.
- Message length ≤ 1,000 characters; history ≤ 6 messages / 4,000 characters.
- Gemini daily ledger hard cap: 8 application calls/day; one call per successful turn.
- Provider timeout 20 s; SDK and application retries disabled.
- Limits are process-local and reset on restart. On Render Free, the SQLite ledger and
  all counters are also lost on spin-down/redeploy, so the application cap is **not** a
  global provider-quota guarantee. Monitor Google AI Studio usage during any live test.
- The rate limiter keys on the client IP observed by Uvicorn. `render.yaml` enables
  `--proxy-headers` so Render's `X-Forwarded-For` is used; treat this as a cost guard,
  not an authorization boundary.

## Local run

```bash
# Once, from repo root; never overwrites an existing .env
python3 scripts/setup_env.py

uv sync --frozen
npm --prefix frontend ci --ignore-scripts --no-audit --no-fund

# Terminal 1 — API
uv run --frozen uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — UI
npm --prefix frontend run dev
```

Open <http://localhost:5173>. With the default `ENABLE_LIVE_LLM=false`, answerable
questions return `llm_disabled` plus retrieved excerpts; greetings and out-of-scope
questions are handled deterministically. Set `VITE_API_BASE_URL` only in the root `.env`
(never put secrets in it).

Useful checks:

```bash
curl -s http://127.0.0.1:8000/healthz
curl -s http://127.0.0.1:8000/demo/readyz
curl -s http://127.0.0.1:8000/api/v1/demo/info
curl -s -X POST http://127.0.0.1:8000/api/v1/demo/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Xin chào"}'
```

## Tests

```bash
uv run --frozen pytest -q
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend run test
```

Focused demo tests:

```bash
uv run --frozen pytest -q \
  tests/test_mvp_corpus.py tests/test_mvp_pipeline.py tests/test_demo_api.py
```

They assert corpus isolation/hashes, retrieval decisions, citation/date/quote rejection,
one-call behaviour, no persisted chat rows, no secrets in `/demo/info`, 429 handling,
disabled mode, and CORS allowlisting. Tests block network access; no test requires a
Gemini key, Qdrant, or model weights.

## M2 — bounded live Gemini test (approval required)

**Preflight is complete as of 2026-10-25; no live request has been made.** `ENABLE_LIVE_LLM=false`
stays set until the test is explicitly approved.

### Preflight findings (official docs, checked 2026-10-25)

| Check | Result | Source |
|---|---|---|
| `gemini-2.5-flash-lite` exists and is stable | Yes; not deprecated; output limit 65,536 tokens | <https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite> |
| Model access | **Restricted**: 2.5 models are limited to users who actively used them in the past; new projects are directed to `gemini-3.5-flash-lite` or `gemini-3.8-flash` | same model page |
| Free Tier pricing | Input/output "Free of charge"; free-tier content may be used to improve Google products | <https://ai.google.dev/gemini-api/docs/pricing> |
| Billing | New accounts start on Free Tier; API keys inherit the project's tier; Free Tier needs no billing setup | <https://ai.google.dev/gemini-api/docs/billing> |
| Rate limits | Applied per project, not per API key; RPD resets at midnight Pacific; published values are not guaranteed; exact RPM/TPM/RPD appear only in AI Studio | <https://ai.google.dev/gemini-api/docs/rate-limits> |
| Structured output | Supported by `gemini-2.5-flash-lite`; not used here (plain text plus `[E#]` markers) | model page |

What **cannot** be verified from the repo or docs: whether this key's project is on Free Tier,
whether that project still has 2.5 access, its actual RPM/TPM/RPD, and which project owns
`GEMINI_API_KEY`. Those require the manual checks below.

### Manual Google AI Studio checklist (no generation)

Sign in with the account that owns the key. Do not paste the key into a terminal, screenshot,
issue, or `VITE_*` value.

1. <https://aistudio.google.com/projects> — find the project linked to the key. Its **Billing
   Tier** must read **Free** (no "Set up billing", no Tier 1+). Note the project name.
2. <https://aistudio.google.com/api-keys> — confirm the key in `.env` belongs to that project.
3. <https://aistudio.google.com/rate-limit?timeRange=last-28-days> — select
   `gemini-2.5-flash-lite`. If it is absent, **stop**: the project has no 2.5 access.
   Otherwise record RPM, TPM, and RPD.
4. <https://aistudio.google.com/billing> — confirm no billing account or prepay credits are
   attached. Do not enable billing.
5. In the AI Studio model picker, confirm `gemini-2.5-flash-lite` is selectable. Do not send a
   prompt there; the live test goes through this API so the application ledger counts it.
6. Record UTC date/time, project, model ID, and the three limits in the test log.

### Test setup

The repository enforces the test budget in configuration (`.env`, `.env.example`,
`render.yaml`):

```dotenv
MAX_LLM_CALLS_PER_TURN=1   # the pipeline also forces 1
MAX_LLM_CALLS_PER_DAY=8    # hard cap; expected usage is 3
LLM_MAX_RETRIES=0
LLM_REQUEST_TIMEOUT_SECONDS=20
MAX_LLM_OUTPUT_TOKENS=1024
ENABLE_LIVE_LLM=false      # flip only for the approved run
```

The ledger is keyed by **UTC** day while Google resets RPD at midnight **Pacific**; keep the
whole test inside one UTC day and check AI Studio usage afterwards.

### Budget — five fixed prompts

Run in this order, one request each, no retries, no judges, no DeepEval, no grounding/search
tools, no paid fallback model.

| # | Prompt | Expected status | Expected calls |
|---|---|---|---:|
| 1 | `Xin chào` | `greeting` | 0 |
| 2 | `Bồi thường khi Nhà nước thu hồi đất ở là gì?` | `answered` | 1 |
| 3 | `Điều 30 Nghị định 88/2024/NĐ-CP quy định gì?` | `answered` | 1 |
| 4 | `Thời hạn sử dụng đất ở là bao lâu?` | `abstained` (`outside_corpus_scope`) | 0 |
| 5 | `Hỗ trợ ổn định đời sống cho hộ gia đình bị thu hồi đất?` | `answered` | 1 |
| | **Expected total** | | **3** |
| | **Hard cap** | | **8** |

These five prompts were replayed offline on 2026-10-25 with an injected mock provider: exactly
3 provider calls, and 0 calls for prompts 1 and 4. Prompt 4 is land-related but outside the
bundled two-document corpus, so the scope/evidence gate abstains deterministically.

### Acceptance

- Statuses are `answered` ×3, `greeting` ×1, `abstained` ×1; `llm_used=true` only for the
  three answered turns; `request_id` present on all five.
- Each source card has an official URL, an exact span, an `E1`-style ID, and
  "Hiệu lực: chưa xác minh".
- No invented article number, date, quotation, document number, or URL survives.
- If any response is `citation_rejected` or `llm_unavailable`, stop, record it, and do not
  increase the budget or add retries. A 429 means stop for the day.
- Compare observed calls/latency with the 3/8 budget and with AI Studio usage.
- Afterwards set `ENABLE_LIVE_LLM=false` and restart.

### Approved live-test command

Only run after explicit approval. Start the API with the live flag scoped to that process
(OS environment overrides `.env`, so `.env` itself stays `false`):

```bash
ENABLE_LIVE_LLM=true MAX_LLM_CALLS_PER_TURN=1 MAX_LLM_CALLS_PER_DAY=8 \
LLM_MAX_RETRIES=0 LLM_REQUEST_TIMEOUT_SECONDS=20 \
uv run --frozen uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Then send the five prompts in order from a second shell:

```bash
for m in "Xin chào" \
  "Bồi thường khi Nhà nước thu hồi đất ở là gì?" \
  "Điều 30 Nghị định 88/2024/NĐ-CP quy định gì?" \
  "Thời hạn sử dụng đất ở là bao lâu?" \
  "Hỗ trợ ổn định đời sống cho hộ gia đình bị thu hồi đất?"; do
  curl -s -X POST http://127.0.0.1:8000/api/v1/demo/chat \
    -H 'Content-Type: application/json' \
    --data "$(python3 -c 'import json,sys; print(json.dumps({"message": sys.argv[1]}))' "$m")" |
    python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("status"), d.get("llm_used"), d.get("request_id"))'
done
```

Stop immediately if a call fails; do not rerun completed prompts.


## M3 — free-cloud deployment (approval required)

Deployment requires a Git remote, a commit, and a push, none of which have been done.
It also creates public cloud resources and is therefore blocked pending explicit approval.
No paid service, custom domain purchase, or database add-on is needed.

### 1. Backend on Render Free

1. Push the approved commit to a Git remote.
2. Render Dashboard → **New → Blueprint** → select the repository. Render reads
   `render.yaml`.
3. Provide `CORS_ORIGINS` as an exact JSON list. Before the Pages URL exists, a temporary
   placeholder such as `["https://pending.pages.dev"]` is acceptable; update it after
   step 2.
4. Leave `ENABLE_LIVE_LLM=false`. Do not add `GEMINI_API_KEY` yet.
5. Deploy. The free instance has 512 MB, an ephemeral disk, and sleeps when idle.
6. Confirm:
   - `https://<service>.onrender.com/healthz` → 200
   - `https://<service>.onrender.com/demo/readyz` → 200 with `demo_rag=true`
   - `GET /api/v1/demo/info` → 2 documents, 90 chunks, `llm_enabled=false`
   - `POST /api/v1/demo/chat` with `Xin chào` → `status=greeting`
   - An answerable question → `status=llm_disabled` with excerpts
7. First request after idle is slow (cold start); this is expected.

`render.yaml` uses `uv sync --frozen --no-dev`, so no ML extra, Qdrant service,
model download, or crawl dependency is required.

### 2. Frontend on Cloudflare Pages Free

1. Cloudflare Dashboard → **Workers & Pages → Create → Pages → Connect to Git**.
2. Root directory: `frontend`.
3. Build command:
   `npm ci --ignore-scripts --no-audit --no-fund && npm run build`
4. Build output directory: `dist`.
5. Environment variable (public, not a secret):
   `VITE_API_BASE_URL=https://<service>.onrender.com`
6. Set `NODE_VERSION=22.21.0` (the security tests require Node 22.21+/24; the build uses
   the same toolchain).
7. Deploy `frontend/public/_redirects` is already included; it rewrites SPA routes to
   `index.html` with status 200.
8. Copy the resulting `https://<project>.pages.dev` origin into Render's
   `CORS_ORIGINS` as `["https://<project>.pages.dev"]` (add a custom domain later if
   approved, no wildcard) and redeploy the backend.

### 3. End-to-end verification

- Desktop and mobile: ask Vietnamese questions, confirm source cards and official links.
- Confirm a greeting and an out-of-scope question make no Gemini call.
- Confirm 429 + `Retry-After` by exceeding 6 questions/minute.
- Confirm the built JS contains only the public API URL, no key/secret.
- Confirm no conversation appears after reload and no session cookie is set.
- Confirm the UI displays corpus limits, excluded documents, and validity caveats.
- Only after M2 approval: enable live Gemini, repeat the five-prompt budget, then disable.

## Known limitations and risks

- **Not law:** 2 documents, technical validation only, no legal review, no seal, no
  current-effect determination. Scope is compensation/support/resettlement plus the
  `43/2024/QH15` amendments; almost all other land-law questions abstain.
- **Validity unknown:** partial expiry and later amendments are not modelled.
- **BM25 only:** lexical matching can miss paraphrase; the benchmark is small and
  self-authored, not an independent evaluation.
- **Ephemeral free hosting:** database, usage ledger, and rate counters reset on
  spin-down/redeploy; the 20/day cap is per instance lifetime, not global.
- **Rate limiting:** in-memory, per process, best-effort; not an authorization boundary.
- **Cold starts:** Render Free sleeps; first response can be slow.
- **No persistence:** deliberate; there is no account, history, admin, upload, analytics,
  subscription, or multi-agent UI in the demo.
- **No crawling or external corpora:** the artifact is built only from preserved stages.

## Rollback

1. Set `ENABLE_LIVE_LLM=false` and redeploy/restart immediately if generation misbehaves.
2. Render: **Manual Deploy → previous commit**, or suspend the service.
3. Cloudflare Pages: **Deployments → Rollback** to the previous successful deployment.
4. Remove or rotate the Gemini key externally if exposure is suspected; then update the
   Render secret. Never rotate the local `.env` automatically.
5. Since the demo has no persistent data, no data migration rollback is needed. Do not
   delete `data/phase-d-corpus-v2/` or any Phase D artifacts.

## Smallest next action

1. Review and approve this runbook and the `render.yaml` values.
2. Approve M2 preflight (model availability + Free Tier quota + 3-call expected budget).
3. Approve a Git remote/commit/push so M3 can create Render and Cloudflare Pages.
4. Otherwise, keep the demo local with `ENABLE_LIVE_LLM=false`.
