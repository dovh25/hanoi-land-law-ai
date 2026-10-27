# Figma handoff

**File:** [Hanoi Land Law AI — UI/UX Redesign](https://www.figma.com/design/XNJdMYnFQwEbCPKCAN7ouo)

Created in the selected **codex** workspace. No public-sharing action, paid generation, or external community asset import was performed. Editable frames, text, vector icon and component instances were verified through Figma MCP; screen construction returned zero image-filled nodes.

## Pages

| Page | Node |
| --- | --- |
| 01 — Design Foundations | `0:1` |
| 02 — Components | `2:2` |
| 03 — Desktop Screens | `2:3` |
| 04 — Mobile Screens | `2:4` |
| 05 — Interaction States | `2:5` |
| 06 — Developer Handoff | `2:6` |

Append `?node-id=5-2` (for example) to the file URL to open a node.

## Screen references

| Screen | Light | Dark |
| --- | --- | --- |
| Desktop empty, 1440×900 | `5:2` | `5:158` |
| Desktop conversation | `5:38` | `5:194` |
| Desktop library | `5:79` | `5:235` |
| Desktop reader | `5:117` | `5:273` |
| Mobile empty, 390×844 | `6:2` | `6:92` |
| Mobile conversation | `6:19` | `6:109` |
| Mobile library | `6:41` | `6:131` |
| Mobile reader | `6:60` | `6:150` |
| Mobile drawer | `6:73` | `6:163` |

Interaction-state frames: loading `7:2`, generating `7:6`, empty search `7:10`, API error `7:15`, rate limit `7:20`, insufficient evidence `7:25`, long answer `7:32`, disabled send `7:39`, corpus dialog `7:44`, feedback `7:49`. Dark equivalents: `7:53`, `7:57`, `7:61`, `7:66`, `7:71`, `7:76`, `7:83`, `7:90`, `7:95`, `7:100`.

Handoff frame: `7:104`. Foundation review: `2:68`, `2:117`. Component review sheet: `4:14`.

## Components

19 families / 47 variants, with editable label properties and variable-bound surfaces:

| Family | Set or standalone node | React mapping |
| --- | --- | --- |
| PrimaryButton / SecondaryButton / IconButton | `4:2` / `4:3` / `4:4` | `components/ui.tsx` |
| NavigationItem / ConversationItem / SidebarSection | `4:5` / `4:6` / `3:48` | `AppShell.tsx` |
| Composer / UserMessage / AssistantAnswer | `4:7` / `3:59` / `3:61` | `Composer.tsx`, `DemoChatPage.tsx`, `AssistantMessage.tsx` |
| CitationCard / DocumentResult / SearchInput | `4:8` / `4:9` / `4:10` | `CitationCard.tsx`, `LookupPage.tsx` |
| Tooltip / Dialog / Toast | `3:89` / `3:91` / `4:11` | Native title, Dialog, inline status feedback |
| LoadingIndicator / EmptyState / ErrorState | `3:98` / `3:100` / `4:12` | Shared loading/error and page states |
| ThemeToggle | `4:13` | Theme select in AppShell |

These are design variants, not a fully wired Figma interaction prototype. Loading/disabled composer states use editable text representations; React implements actual send/stop controls. No Code Connect publishing was performed.

## Verification

Used supported file creation/session, design-system search, library discovery, Plugin API composition, screenshots, asset export and design-context tools. Desktop/mobile design contexts informed implementation. Screenshot review repaired instance text reflow and reader heading/metadata overlap. Insufficient-evidence and long-answer examples were corrected and re-reviewed. Document metadata for the second result was corrected to `43/2024/QH15 · Luật · 2024`.

Token and interaction mappings: [design-system.md](design-system.md). Implementation differences and screenshot evidence: [visual-qa-report.md](visual-qa-report.md).
