# Frontend redesign — Indochine legal-tech

> **Earlier visual-design record.** The active interface is documented by the
> [current UI design system](ui-redesign/design-system.md) and
> [implementation evidence](ui-redesign/implementation-summary.md).

The public anonymous demo page (`frontend/src/pages/DemoChatPage.tsx`, route `/`) was
redesigned in Figma and re-implemented in React + Tailwind v4. Behaviour, data flow,
security controls, rate limiting, and citation/anchor handling are **unchanged** — this
is a visual and structural refactor only.

## Design source

| Item | Value |
| --- | --- |
| Figma file | https://www.figma.com/design/D3qDjCwBMSqAlQ5VqqYiBW |
| Screen node | `1:2` |
| Direction | Indochine legal-tech — ink/navy base, warm gold accent, serif display type, paper-white document cards |
| Tooling | Figma MCP server (`https://mcp.figma.com/mcp`) + `html_to_figma` |

The Figma file contains two artboards: the active conversation (with a cited answer and
source cards) and the empty state. It is a reference artifact for review and iteration;
the shipped code is the source of truth.

## Design tokens

Defined once in `frontend/src/index.css` under `@theme` (Tailwind v4), so every page can
reuse them:

| Token | Value | Use |
| --- | --- | --- |
| `ink-900` / `ink-800` / `ink-950` | `#0B1420` / `#102232` / `#0A121C` | Header, AI seal, corpus chip |
| `navy-700` / `navy-600` | `#153550` / `#1B4363` | User message bubble |
| `gold-500` / `gold-600` / `gold-300` / `gold-100` | `#C9A24B` / `#B08A34` / `#E7CB86` / `#F6EDD6` | Accent, primary button, citations |
| `paper` / `paper-2` | `#F8F3E7` / `#FFFDF7` | Page background, cards |
| `line` / `line-soft` | `#E5DCC5` / `#EFE8D6` | Borders |
| `muted` / `muted-2` | `#6E6455` / `#8C8272` | Secondary text |
| `ok` / `okbg` | `#1E6B4F` / `#E7F2EC` | "Trả lời có trích dẫn" |
| `warn` / `warnbg` | `#8A621C` / `#F7EFDA` | Unverified-validity badge |
| `info` / `infobg` | `#20516E` / `#E6EFF4` | Retrieval / Gemini-state chip |

Display headings use `font-display` (Georgia → system serif). Body text keeps the existing
Inter → system sans stack. No external fonts are fetched, so the build stays offline-safe.

Inline evidence citations (`[E1]`) are styled as gold chips via
`.prose a[href^="#"]`, which reuses the anchors the page already generates.

## Scope

- Redesigned: public demo page (`/`) — info panel, empty-state hero, message thread,
  source cards, composer.
- Not yet redesigned: authenticated pages (`/chat`, `/lookup`, `/login`, `/register`).
  They inherit `body` background but still use the previous slate palette.

## Rebuild and deploy

```bash
VITE_API_BASE_URL=https://hanoi-land-law-ai-demo.onrender.com npm --prefix frontend run build
wrangler pages deploy frontend/dist --project-name hanoi-land-law-ai --branch main
```

No backend change is required by this redesign.
