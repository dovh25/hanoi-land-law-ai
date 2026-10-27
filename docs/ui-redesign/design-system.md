# Design system

[Editable Figma file](https://www.figma.com/design/XNJdMYnFQwEbCPKCAN7ouo) · workspace: **codex**.

## Direction

Neutral, content-first Vietnamese legal research assistant, inspired by modern conversational interfaces. Own document icon and product name; no OpenAI branding or affiliation. Assistant answers are unboxed; sources use restrained outlined containers. Unknown legal validity is always explicitly disclosed.

## Semantic colors

Figma `color/<name>` maps directly to CSS `--<name>` in `frontend/src/index.css`.

| Name | Light | Dark |
| --- | --- | --- |
| app-bg | #FFFFFF | #212121 |
| sidebar-bg | #F9F9F9 | #171717 |
| text-primary | #171717 | #F4F4F4 |
| text-secondary | #6B6B6B | #B4B4B4 |
| surface-hover | #F1F1F1 | #2F2F2F |
| border | #E5E5E5 | #424242 |
| composer-bg | #F4F4F4 | #303030 |
| user-bg | #F4F4F4 | #2F2F2F |
| button-bg | #171717 | #F4F4F4 |
| button-text | #FFFFFF | #171717 |
| accent | #176B51 | #81D7B1 |
| error | #B42318 | #FFB4AB |
| warning | #805514 | #E9C985 |
| highlight | #FAF5E8 | #383020 |

Figma has raw primitive colors, aliased Light/Dark semantic modes, and a separate Layout collection. Muted borders are decorative, not the sole indication of interactive state. Keyboard focus uses the accent color plus an outline; selection also uses surface and accessible state attributes.

## Typography and layout

- Figma: Inter; implementation: `Inter, system-ui, -apple-system, "Segoe UI", sans-serif`. Inter is not bundled or fetched remotely; system font rendering differs slightly.
- App 16/24 medium; page 32/40 semibold; section 20/28 medium; answer 16/28 regular; supporting 14/22; metadata 13/20; caption 12/18; button 14/20 medium.
- Figma spacing tokens: 4, 8, 12, 16, 24, 32, 48, 64px. CSS uses these values in semantic component rules.
- Radii: 8, 12, 16, composer 24px; circular send control.
- Sidebar: `--sidebar-width: 256px`, collapsed 64px; drawer below 768px. Drawer is 288px in React to accommodate close control and history actions.
- Chat: `--reading-width: 768px`; 24px desktop / 16px mobile gutters. Minimum control height 44px; textarea expands to 160px.
- Reader: independent scroll column and 240px TOC on wide screens. Below 1101px, TOC is a disclosure. Library content is capped at 960px inside padded wrapper.

## Components and interaction

Reusable React primitives: `Button`, `IconButton`, `Input`, `Badge`, `Dialog`, `Loading`, `ErrorState`, `Icon`. Product components: `AppShell`, `Composer`, `AssistantMessage`, `CitationCard`.

- Themes: system default; manual Light/Dark/System select; only `hll-theme` persists. Head script applies theme before React paints.
- Native dialogs supply modal focus containment, Escape handling and focus restoration; mobile drawer closes outside its bounds.
- Enter submits; Shift+Enter inserts a newline; IME composition does not submit. Empty submit is disabled; pending requests expose Stop.
- Transcript scrolls separately from the in-flow composer. `visualViewport` resize updates app height; browser viewport metadata requests keyboard-driven resizing where supported.
- History: at most 20 conversations, React tab memory only. Refresh clears it. No conversation search, login UI, or server session creation.
- Citation links resolve message-local evidence anchors, document ID/article routes and validated HTTPS source URLs. Legal validity is not inferred from retrieval metadata.
