# Public demo UI and integration validation

Validated locally on 2026-10-27; base commit `a4f60f1`, with uncommitted changes.
Verdict: **UI READY — LOCAL ONLY** (retrieval-only demo, not legal-production certification).

## Authentication and session design

- `/` is anonymous chat. `/lookup` is public. `/login`, `/register`, `/chat`,
  `/chat/:sessionId`, `/demo`, and unknown routes safely redirect to `/`.
- Removed the unused account frontend dependency graph: account pages/forms,
  AuthContext, ProtectedRoute, account sidebar, authenticated chat, session hook,
  token storage/client, and account/session types/services. No frontend account API
  calls, login prompts, authentication headers, or stored access tokens remain.
- Preserved legacy backend account/session endpoints and ownership enforcement.
  Knowing a session UUID does not authorize reading, renaming, or deleting it.
- Public chat uses the existing `/api/v1/demo/chat` stateless contract. No anonymous
  conversation is stored server-side. No ownership token or persistent session ID is
  needed or accepted; arbitrary `session_id` fields are rejected. Each response has
  a server-generated random request ID, which grants no access to conversations.
- Messages and draft exist only in React memory for the current browser tab.
  Chat → lookup → chat preserves them. Refresh/closing the tab clears them.
  Persistent conversation switching, renaming, and deletion are deliberately absent.
- Maximum question length defaults to 1,000 characters; request schema caps history
  at 20 entries × 4,000 characters, and model context is further bounded by configured
  limits (default six messages / 4,000 characters). Blank questions are rejected.
- Existing minute/day IP limits, explicit CORS allowlist, and shared LLM wrapper and
  ledger remain. Limiter expiry cleanup is fixed; saturation fails closed at 8,192
  active keys per window instead of allocating indefinitely or resetting active limits.

## Screens and defects fixed

Inspected the route tree, every frontend component file, chat/lookup API contracts,
legacy ownership dependencies, CORS, limiter, and Render/Cloudflare configuration.
Browser coverage includes every remaining reachable screen: empty chat, greeting,
retrieval/citations, abstention, loading/error states, lookup list, filters, empty
search, reader, table of contents, print window, invalid document/article parameters,
and compatibility redirects.

| Reproduced defect or integration gap | Fix |
| --- | --- |
| Homepage links into login; lookup requires authentication | Public routing/navigation; removed account frontend |
| Reader has fixed 384px list plus 256px TOC; unusable mobile width | Mobile list/reader navigation, responsive widths, collapsible TOC |
| Fixed composer with guessed bottom padding can obscure content | Bounded viewport flex layout: separately scrolling transcript and compact in-flow composer |
| Chat requests survive navigation/new chat | AbortController, request identity guard, duplicate submission lock, timeout |
| Lookup requests race and overwrite newer selections/search | Separate cancellable document/list requests and unmount cleanup |
| API success bodies trusted without validation | Runtime checks and recoverable errors for malformed chat/info/document/list data |
| Chat sources have no internal reader destination; reader's legacy dataset is absent | Stable public document IDs; bundled immutable excerpts exposed through lookup |
| Search cannot find a document by its displayed number | Search includes reference metadata |
| Concurrent first lookup requests duplicate document rows | Locked, idempotent lookup initialization with regression test |
| Article 1 matches Article 12; cross-references create false TOC entries | Validated article parameters, heading-boundary matching, stricter TOC parsing |
| Reopening the same mobile document can leave reader hidden | Explicit mobile reader selection state |
| Lookup selection is not represented in URL | Selection updates query parameters; direct navigation/refresh works |
| Untrusted source hrefs and misleading generic validation note | HTTPS-only source links; actual warnings with Vietnamese labels |
| Low-contrast secondary text, missing labels/statuses/focus, hidden focus target | Darker muted token, labeled controls, live statuses/errors, focus styling, reduced motion, hidden back-to-top removed from tab order |
| Small mobile form text and source interactions | 16px mobile inputs, larger primary/source touch targets, keyboard-scrollable excerpts |
| Default Vite branding | Project favicon |

Bundled reader content is explicitly **a collection of demo excerpts, not full
instruments**; validity remains unknown. No corpus files, BM25 ranking, legal scope
gates, or citation validation rules were changed. Source serialization only adds
the public reader identifier. Legacy local document reading remains available.

## Browser validation

Playwright MCP ran `scripts/browser_public_audit.js`: **60 assertions passed**.
The script obtains real deterministic offline greeting/retrieval/abstention responses
and reuses them as browser fixtures; errors, delayed responses, XSS probes, and
multi-page pagination use explicit mocks. Earlier manual browser sends also exercised
the actual local anonymous chat endpoint. No live Gemini calls occurred.

Coverage includes anonymous landing; all compatibility redirects; Enter/Shift+Enter;
greeting; BM25 sources; evidence anchors; official portal hrefs; matching reader
provision; tab-local return to chat; long documents; filters/search; TOC/toggle;
print/export popup; missing documents; invalid article parameters; malformed API
responses and retry; pagination; abstention; Markdown/code; unsafe HTML/links;
rate-limit delay; cancellation on new chat; refresh; back/forward; independent visitor.

Viewport matrix for chat and reader:

- 375 × 812
- 390 × 844
- 768 × 1024
- 1366 × 768
- 1920 × 1080

No page-level horizontal overflow was measured in this matrix. Geometry assertions
verify the transcript and final source card remain above the composer. No uncaught
JavaScript exceptions were observed; clean-page console inspection had no warnings
or errors. Deliberate 404/429 tests can produce expected HTTP console entries.

Screenshots saved and visually reviewed locally:

- `/tmp/opencode/hanoi-desktop-empty.png`
- `/tmp/opencode/hanoi-desktop-chat.png`
- `/tmp/opencode/hanoi-citations.png`
- `/tmp/opencode/hanoi-mobile-chat.png`
- `/tmp/opencode/hanoi-desktop-lookup.png`
- `/tmp/opencode/hanoi-mobile-lookup.png`
- `/tmp/opencode/hanoi-error.png`

To repeat, start the API **explicitly offline**, then Vite:

```bash
ENABLE_LIVE_LLM=false ALLOW_MODEL_DOWNLOADS=false DATABASE_URL=sqlite:////tmp/opencode/hanoi-ui-audit.sqlite3 uv run --frozen uvicorn backend.main:app --host 127.0.0.1 --port 8000
npm --prefix frontend run dev -- --host 127.0.0.1
```

Use Playwright MCP `browser_run_code_unsafe` with `filename` set to the absolute path
of `scripts/browser_public_audit.js`. This is an MCP-run browser test, not an npm
Playwright package installation. The script refuses fixtures if live LLM is enabled;
normal local rate limits remain active (avoid rapid repeated runs).

## Regression and security results

- `uv run --frozen pytest -q`: **274 passed**. Includes account ownership, anonymous
  request-local isolation, protected-session denial, citation/lookup integration,
  input bounds, limiter capacity/expiry, and concurrent lookup initialization.
- Frontend ESLint, TypeScript, production build: **pass**.
- Frontend Node security/unit tests: **6 passed**.
- `uv lock --check`, `uv pip check`, `git diff --check`: **pass**.
- Changed/new application files and production assets checked for configured backend
  secret values and common API-token/private-key patterns: **zero findings**. This
  is a local targeted scan, not a third-party security certification.
- Existing CORS allowlist and rejected-origin regression tests pass. Unsafe Markdown
  HTML, executable source schemes, and escaped print interpolations are tested.

## Deployment status and limitations

Local: frontend `http://127.0.0.1:5173`, backend `http://127.0.0.1:8000`.

Existing services were smoke-tested without generation requests:

- `https://hanoi-land-law-ai.pages.dev`: **200**; browser loaded the existing UI,
  which still displays its old login link (these fixes have not been deployed).
- `https://hanoi-land-law-ai-demo.onrender.com/healthz`: **200**.
- `https://hanoi-land-law-ai-demo.onrender.com/demo/readyz`: **200**.

Cloudflare SPA fallback `frontend/public/_redirects` is retained. Intended frontend
build: `VITE_API_BASE_URL=https://hanoi-land-law-ai-demo.onrender.com npm --prefix frontend run build`;
publish **frontend/dist**, not the unrelated root dist directory. Only the public
backend URL belongs in VITE settings. CORS must allow exactly
`https://hanoi-land-law-ai.pages.dev`. Existing Render blueprint binds `$PORT` on
`0.0.0.0`, remains Free with auto-deploy off, and keeps Gemini/model downloads disabled.

No commit, push, cloud configuration update, plan change, or deployment was performed.
Approval and confirmation of the existing target services/Free plans are required
before updating them; no duplicate services are needed.

Operational limits, not hidden acceptance claims:

- Chromium viewport tests are not real iOS/Android keyboard, Safari, or Firefox tests;
  native mobile keyboard and full assistive-technology certification remain unverified.
- The free demo intentionally has no durable anonymous history. The per-IP limiter
  is process-local and resets on restart; visitors sharing an IP share its limits.
- Live Gemini remains disabled. Its SQLite spend ledger is not durable on Render's
  ephemeral filesystem. Do not enable live generation without separately approved
  durable/shared budgeting; multiple workers/machines cannot be assumed to share it.
- Legal validity/applicability is not established by UI QA. The demo has two documents
  and 90 evidence chunks, not a comprehensive verified Hanoi legal corpus.
