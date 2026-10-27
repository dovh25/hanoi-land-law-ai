# M4 — public deployment validation

Date: 2026-10-27. Scope: supervised public MVP demonstration, not a comprehensive
legal QA benchmark or an unattended production service. No paid resources, plan
changes, new databases, corpus downloads or live Gemini calls were made.

## Targets and versions

- Frontend: https://hanoi-land-law-ai.pages.dev
- Backend: https://hanoi-land-law-ai-demo.onrender.com
- URLs resolved from the deployment runbook and confirmed in the served JS bundle
  and Render API, not inferred from build status.
- Initial backend: `8c8ee0c6b1a5dbf3f82d9aa4e1ecee5ff8ee4eaa`, Render deploy
  `dep-dbf8jf5g1s2s73esfr9g`.
- Initial frontend: asset `index-CVO1tFVH.js`, matching the redesign build associated
  with `9cd16ca5d1b53c8b3b1cfbb7aec590770daffc85`. This is asset evidence, not a
  claim that the old direct-upload deployment had commit metadata.
- M4 fixes: `3ab7c8edb4f83f037af1f6522d324d3629a071db`; Render deploy
  `dep-dbg0gcivcj2c73apk380`; Pages deploy `64b8273e`, asset `index-Bwa-Rd1N.js`.
- Post-deploy: Render API confirms **live** on that SHA; real browser rechecked
  readiness (2/90, Gemini enabled), six greeting successes then 429, readable
  `Retry-After: 60`, and UI displaying “Vui lòng thử lại sau 60 giây.”
  Served JS SHA-256 matches the local tested build:
  `1a315f8024094d194cb7ff62b467ca21b845bef3e27309f56b0dac7564fccb58`.

## Executed checks

| Check | Result / evidence |
| --- | --- |
| Public frontend | Chromium loaded real URL, HTTP 200. Bare Python urllib got 403; browser access works. |
| Demo readiness | Real `/demo/readyz` HTTP 200, `ready`, `demo_rag=true`. |
| Intended corpus | Real info: 2 instruments, 90 chunks; 43/2024/QH15=7, 88/2024/NĐ-CP=83. |
| Browser/API connectivity | Cross-origin fetch from Pages to real Render info and chat succeeds. |
| HTTPS/CORS | Both real HTTPS URLs load; preflight exact Pages origin=200 with matching allow-origin; untrusted origin=400 with no allow-origin. |
| Frontend secrets | Served JS contains intended Render URL; credential-name/key-pattern scan found zero hits. Pattern scanning is not proof of absence of all possible secrets. |
| Mobile | 390×844, document width=390 (no horizontal overflow); desktop 1280×900 screenshot. |
| Vietnamese input | Filled and submitted “Xin chào” through real UI; readable Vietnamese response. |
| Deterministic greeting | Repeated public greetings produce identical answer, distinct request IDs, `llm_used=false`. |
| In-scope retrieval | Five guide prompts executed locally with generation disabled; all return corpus excerpts. No in-scope public generation request was sent. |
| Exact article | Local actual BM25: Điều 30 → 1 source; public UI rendered offline API response via interception, anchor resolves to its card. |
| Abstention | Three guide out-of-scope prompts sent to real API; all `abstained`, zero sources, `llm_used=false`. |
| Citation links | Both government source URLs returned HTTP 200; browser source link has `noopener noreferrer`; gold E# anchor target exists. |
| Unknown validity | Real info has `unknown` / `technical_validation_only`; rendered source card and info badge say “Hiệu lực: chưa xác minh”. |
| Cold start | Initial readiness took 52.62 s; next info request 0.22 s. Consistent with free-tier wake-up, not a controlled repeated sleep experiment. Delayed 503 simulation shows spinner, disabled Send, then Vietnamese error. |
| Rate limit | Real browser sequence of safe non-generating requests: six 200s then 429. Pre-fix browser could not read Retry-After; fixed and regression-tested. |
| Privacy/isolation | Browser local/session storage and cookies empty; reload clears thread; independent browser context has no source cards. Mock canary history appears only in the first request prompt. Existing suite covers authenticated ownership/isolation. Public unauthenticated GET sessions and POST chat return 401. |
| Anonymous LLM cap | Production configuration inspected: 1/turn, 50/day, retries=0, timeout=20s, output=1024. Mocked API test with cap=1 allows first generation, blocks second transport call and returns sources. Existing tests cover concurrent daily reservations, retries counted, fail-closed ledger. Not a permanent cross-restart global cap. |

Generation-heavy checks are explicitly **offline/mocked**, not a claim of fresh
public Gemini availability. M4's exact approved live-generation budget was zero.

## Tests and fixes

- Baseline backend: **266 passed**.
- Final backend: **268 passed**, network-blocked pytest. New tests cover anonymous
  daily model cap and request-local history; extended CORS rate-limit regression.
- Frontend: lint and typecheck pass, **5/5 tests pass**, production build passes.
  Two new tests cover Retry-After parsing.
- `uv lock --check` and `uv pip check` pass.
- Fixed: expose `Retry-After` through CORS; parse missing/invalid headers as null
  so UI uses 60-second fallback instead of displaying zero seconds.
- Fixed: demo endpoint now enters its application's settings context before
  invoking the pipeline. Previously injected settings could disagree with the
  generation path (the new test initially failed for this reason).
- Browser had no observed application JavaScript exceptions in initial page
  validation. Deliberately induced 429 and mocked 503 emit expected HTTP error
  console entries; these are not application exceptions or silent successes.

## Remaining limitations and recommendation

- **GO for a supervised MVP demo**, with generation fallback and startup warning.
  **NO-GO for an unlimited/unattended production launch**: SQLite usage ledger and
  process-local IP counters reset on Render restart/deploy. No provider-side spend
  ceiling was verified or altered. Keep billing disabled and monitor the demo.
- Gemini enabled does not prove provider availability; M4 intentionally did not
  exercise a live generation. A separate exact request budget is needed for that.
- Broad Law 43 suggestion currently conservatively abstains in the offline smoke
  check. Prefer the five tested guide prompts. No coverage claims beyond two docs.
- A bare HTTP client can receive Cloudflare 403 even when Chromium succeeds.
  Do not promise unrestricted automated fetch access to the Pages site.
- No forced restart or disruption was used to test cold start. Wake once before
  presenting. No paid persistence was added.
- No dashboard changes required for the code fixes. A durable global cap would
  require a separately approved design; ephemeral limits must not be advertised
  as permanent guarantees.
- Anonymous chat is not persisted as an application chat session, but in-scope
  prompts/context go to Google when generation is enabled. Provider operational
  logs/retention were not audited. Do not enter confidential personal/case data.

## Evidence

Local ignored browser artifacts (not committed):

- `.playwright-mcp/m4-desktop.png`
- `.playwright-mcp/m4-mobile.png`
- `.playwright-mcp/m4-offline-article-mobile.png` (offline response interception)
- `.playwright-mcp/m4-simulated-cold-start.png` (simulated delayed 503)

Temporary initial public timing/metadata and offline retrieval responses are in
`/tmp/opencode/m4/`. These are local evidence, not deployment inputs.

Presenter material: [M4 demo guide](m4-demo-guide.md).

**Verdict: MVP DEMO READY for a supervised demonstration.** Fresh live Gemini
generation remains explicitly untested in M4, and unattended launch is not approved.
