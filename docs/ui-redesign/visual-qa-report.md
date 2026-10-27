# Visual QA report

Date: 2026-10-27. Local frontend `http://127.0.0.1:5173`; local API `http://127.0.0.1:8000`. Browser testing used Playwright MCP and deterministic intercepted chat responses. Local demo info confirmed `llm_enabled=false`; no Gemini generation/judge requests were made.

## Results

| Validation | Result |
| --- | --- |
| Frontend lint / typecheck / production build | Pass |
| Frontend tests | 8 passed |
| Backend tests | 274 passed |
| Playwright redesign audit | 62 checks passed |
| Unexpected browser console errors / page exceptions | 0 |
| Lock / installed-package validation | Pass |
| Git whitespace check | Pass |
| Common secret patterns in diff / untracked text / built assets | No matches |

Expected HTTP console messages from deliberately mocked 429/503 responses are excluded from the unexpected-error count. No authentication or pytest network protections were weakened.

## Browser coverage

390×844, 768×1024, 1440×900 and 1920×1080: empty chat, long dark-theme answer, citation clearance, library and reader horizontal overflow checks plus screenshots. Additional captures cover desktop active Light/Dark, mobile drawer, mobile active Light, dark library/reader, rate limit, generating, empty results and a 390×500 reduced-height viewport.

Functional checks include Enter/Shift+Enter, bounded textarea growth, disabled send, exact evidence anchors, expanded source excerpts, correct article navigation/highlight, official source resolution, sidebar collapse/expand, history switching/deletion, native drawer Escape/outside dismissal/focus restoration, mobile TOC, search/filter, errors/retry delay/draft recovery, cancellation, system theme changes, refresh persistence boundaries and legacy route redirects.

The reduced-height viewport is a keyboard-layout approximation, not a real iOS/Android software-keyboard test. Chromium was exercised through MCP; Safari/Firefox, assistive-technology certification and full WCAG auditing remain outside this validation.

## Visual review and fixed defects

Actual implementation screenshots were opened and visually reviewed alongside Figma references. Checked neutral surfaces, sidebar sizing, typography/wrapping, source density, reading width, theme consistency and composer separation.

- Replaced dense gold/navy/serif panels with neutral surfaces and a sans-serif reading layout.
- Added working sidebar, mobile drawer and theme controls absent from the old UI.
- Fixed Figma text overflow using wrapped, height-hugging component text; fixed reader title/metadata overlap.
- Corrected law metadata and misleading insufficient-evidence/long-response design examples.
- Fixed the library search button shrinking into two lines.
- Verified that the final source and answer actions can scroll above the composer at every required width.

## Screenshot evidence

Retained representative images under `screenshots/`:

| Image | Review |
| --- | --- |
| `desktop-empty-light.png` | Neutral empty state; 256px sidebar and 768px composer |
| `desktop-active-dark.png` | Unboxed answer, dark source card and bottom composer |
| `mobile-empty-light.png` | Mobile welcome and bottom composer |
| `mobile-long-dark.png` | Last source clears composer |
| `desktop-library-light.png` | Long real titles, metadata and corrected search button |
| `mobile-reader-light.png` | Legal text, unknown validity, source/PDF/TOC controls |
| `figma-reader-light.png` | Editable design reference, verified after height repair |
| `figma-mobile-active-light.png` | Editable mobile design reference after text repair |

Full temporary capture set: `/tmp/opencode/redesign-*.png`; baseline: `/tmp/opencode/redesign-before-*.png`; Figma review captures: `/tmp/opencode/figma-redesign-*.png`. These temporary files are not durable release artifacts. Reproduce using `scripts/browser_redesign_audit.js` through Playwright MCP with both local services running and live LLM disabled.

## Deliberate Figma / implementation differences

- Figma uses Inter; system sans-serif fallback is used when Inter is unavailable. No remote font request is required.
- React uses real API document titles/content, so title lengths, result order, TOC density and article heights differ from illustrative Figma excerpts.
- React highlights the cited article heading and scrolls to it rather than tinting a fixed-height sample excerpt card.
- Source cards include expandable excerpts and separate functional reader/official links; their height follows available data, not a fixed mockup height.
- The implemented mobile drawer is 288px with explicit close control and deletion actions; Figma uses the shared 256px sidebar specimen.
- The implementation adds native focus handling, service-info icon, composer character count and actual stop/send control; Figma state diagrams remain noninteractive editable specimens.
- Earlier document reading-progress/back-to-top decoration is omitted in favor of native scrolling and TOC links; search, pagination, source access and print export remain available.

No critical layout defect remains in the tested Chromium configurations. Legal accuracy/validity and Hanoi corpus QA are **not** established by these UI tests.

## Production verification

Released with user approval on 2026-10-27. Application commit `5917de2`; Cloudflare Pages production deployment `d379ae4c-8920-4541-b423-227d4170fc13`.

- Public UI: `https://hanoi-land-law-ai.pages.dev`.
- Backend health/readiness returned 200; CORS allows the exact frontend origin; public library contains two documents; live Gemini is disabled.
- Playwright production smoke: **21 checks passed**, **0 browser errors**. One real anonymous chat request returned HTTP 200, retrieval citations and `llm_used=false` (request ID `34e55c55d4e1433d829f4801aeed696d`).
- Verified chat/composer geometry at 390×844, 768×1024, 1440×900 and 1920×1080; mobile drawer/theme, exact article reader navigation, route refresh and document-reference search.
- Production screenshots opened for visual review: `/tmp/opencode/deployed-desktop-empty.png`, `/tmp/opencode/deployed-mobile-chat.png`, `/tmp/opencode/deployed-mobile-reader-dark.png`; additional library capture `/tmp/opencode/deployed-desktop-library-dark.png`.
- No Gemini calls, resource creation or plan upgrades were performed. Backend deployment was completed by the user before frontend publication.
