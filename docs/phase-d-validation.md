# Phase D validation — authoritative corpus acquisition preparation

> **Phase D validation snapshot.** Acquisition/test counts are stage-specific.
> See [current bundled corpus](corpus.md) and later D.1/D.2 records.

> **Historical Phase D record.** Phase D.1 later resolved the acquisition blocker by using
> an alternate official representation (the gazette file CDN `congbaocdn.chinhphu.vn`) and
> acquired 8 instruments / 16 originals. See [phase-d1-validation.md](phase-d1-validation.md).
> The counts below describe Phase D itself and are preserved unchanged.

## Acceptance

- **Phase D source discovery and policy verification: PASS (offline/local scope).**
- **Phase D controlled full-text acquisition: 0 acquired by design; blocked hosts
  respected.** This is a policy outcome, not a passing acquisition.
- **Phase D parsing / legal review / sealing of real law: NOT EXECUTED** because no
  real attachment was acquired.
- **Real neural embedding / GPU / Colab execution: NOT EXECUTED.**
- **Human legal review: NOT PERFORMED.** No validity, amendment, repeal, territorial
  scope, or transitional-provision determination is claimed.

The deliverable is an evidence-bound **18-candidate registry** (12 national, 6 Hanoi),
an 8-host policy registry, a conservative quality-gate implementation, an empty and
unsealed isolated draft release, and an 18-entry manual download/review queue. It is not
a corpus release.

## Scope and preserved state

Phase D was limited to the current repository. It did not inspect other local projects
or corpora, did not reuse a foreign corpus, and did not migrate, overwrite, or delete
the configured application database. The prior 14-candidate draft in
`data/phase-d-corpus/` is preserved untouched.

No prohibited action occurred:

- no Google Colab execution, no Gemini request, no real neural model load or weight
  download, no GPU job, no paid API;
- no Qdrant or production index connection, no bulk crawl beyond the 40-instrument cap
  (18 were discovered, 0 downloaded), no access-control bypass, no CAPTCHA/login/403
  circumvention, no proxy/stealth rotation;
- no public deployment, no GitHub push, no commit, no staging;
- no destructive database operation, and no reuse of the Phase C synthetic 8-dimensional
  vectors as production retrieval data.

Root `.env` remains unchanged, Git-ignored, and untracked; `ENABLE_LIVE_LLM=false`.
`data/` (including all Phase D evidence, workspaces, and SQLite) remains Git-ignored.

## Sources and policy outcome

Eight hosts were inspected. No host was approved for automated document download.

| Host | robots.txt | Decision | Document request |
|---|---|---|---|
| `congbao.hanoi.gov.vn` | 200, `Crawl-delay: 5`, `Allow: /` | discovery only | not made; approval required |
| `hanoi.gov.vn` | 200, `Crawl-delay: 5`, `Allow: /` | discovery only | not made; approval required |
| `vanban.chinhphu.vn` | 200, `Allow: /` | discovery only | not made; approval required |
| `vanban.hanoi.gov.vn` | 200, `Crawl-delay: 5`, `Allow: /` | discovery only | not made; approval required |
| `vbpl.vn` | 200; disallows `/api/`, `/Pages/`; reCAPTCHA-gated documents | blocked / ambiguous | not made |
| `datafiles.chinhphu.vn` | **403** | blocked | not made |
| `datafiles.hanoi.gov.vn` | **403** | blocked | not made |
| `storage-vnportal.vnpt.vn` | **403** | blocked | not made |

All 21 declared attachment URLs across the 18 candidates resolve to one of the three
robots-403 attachment hosts (15 to `datafiles.chinhphu.vn`, 3 to
`datafiles.hanoi.gov.vn`, 3 to `storage-vnportal.vnpt.vn`). `vbpl.vn` was independently
rejected for document access because its documents are reCAPTCHA-gated and robots
disallows `/api/` and `/Pages/`. The pilot therefore acquired **0 full-text
instruments**. The metadata pages do not contain the legal text; they are not treated as
acquisition.

Exact URLs, evidence hashes, retrieval timestamps, policy text, and per-candidate
attachment links are in `docs/corpus-sources.md`, `corpus/source-approvals.json`, and
`data/phase-d-network/`.

## Counts (authoritative)

| Stage | Count |
|---|---:|
| Candidate metadata pages discovered | 18 |
| National / Hanoi candidates | 12 / 6 |
| Hosts inspected | 8 |
| Automated downloads | 0 |
| Raw artifacts preserved | 0 |
| Parsed instruments | 0 |
| Quarantined real instruments | 0 |
| Human-reviewed documents | 0 |
| Verified relationships | 0 of 14 claims |
| Sealed releases | 0 |
| Stored document / version / provision / provision-version / artifact rows | 0 / 0 / 0 / 0 / 0 |
| Chunks | 0 |
| Embeddings | 0 |
| Indexed / published | 0 |

Invalidity is explicit: all 18 candidates have `legal_validity=unknown`,
`review_status=pending`, and `full_text_acquired=false`. Publication dates are unknown
for 18/18; `71/2024/NĐ-CP` also has no effective-date claim. Six Hanoi issuers come
from the official masthead plus the `QĐ-UBND` number suffix and remain pending human
confirmation.

The isolated draft release `phase-d-authoritative-pilot-draft-v2` has
`published_at=NULL`, `manifest_sha256=NULL`, `sealed=false`, `indexed=false`,
`published=false`, `approved_publication=false`, and no members.

## Implemented controls

New Phase D code (all kept separate from the inherited bulk crawler):

- `law_crawler/pilot.py`: HTTPS-only exact-host client, robots longest-match handling,
  persistent per-host stop on 401/403/429, redirect destination validation before
  connecting, bounded retries, `Retry-After` handling, access-challenge detection,
  content-addressed evidence journal, per-host pacing, a persistent 40-instrument
  reservation ledger, and acquisition that requires explicit per-source, per-URL
  approval.
- `law_crawler/catalog.py`: deterministic official-metadata parsing, identity checks
  (page number must equal the discovered number), relationship claims, attachment-link
  extraction, and registry validation.
- `law_crawler/quality.py`: extraction quarantine gate for empty text, hash mismatch,
  encoding/glyph loss, duplicate locators, broken spans, invalid parent ordering,
  missing article numbers, and unstructured documents.
- `law_crawler/reporting.py`: isolated draft release, quality report, and manual review
  queue generation. It refuses to touch a sealed release.
- `law_crawler/pilot_cli.py`, `corpus/pilot-seeds.json`,
  `corpus/phase-d-candidates.json`, `corpus/source-approvals.json`.
- `tests/test_pilot.py`: 24 offline policy/parser/quality/release tests.

Each control was exercised with mocks; no test performs a network request. The suite's
network-socket block remains in force.

## Executed validation

| Check | Result |
|---|---|
| Phase D tests | **24 passed** |
| Full Python suite | **197 passed; 0 failed; 0 skipped** |
| `uv lock --check` | Passed (`Resolved 173 packages`) |
| `uv pip check` | Passed (`Checked 89 packages`) |
| `docker compose config --quiet` | Passed; no container started |
| `compileall` (backend, batch, preprocess, law_crawler, tests) | Passed |
| Frontend lint | Passed |
| Frontend typecheck | Passed |
| Frontend build | Passed |
| Frontend security tests | **3 passed** |
| Isolated DB inspection | Draft unsealed; 0 rows in all legal-corpus tables |
| Credential scan | 388 files; 0 configured sensitive-value leaks outside `.env` |
| `.env` state | exists, ignored, untracked; live Gemini disabled |

The credential scan found one `AIza`-shaped substring inside a captured Base64 portal
evidence blob in `data/phase-d-network/evidence/`. It is not the configured
`GEMINI_API_KEY` (the value comparison fails) and is embedded inside encoded third-party
page data. It is recorded as an ambiguous third-party false positive. Because `data/` is
Git-ignored and uncommitted, no credential-bearing artifact is proposed for commit. The
raw evidence was not rewritten, since Phase D preserves original artifacts.

## Known gaps and blockers

1. **No full text.** Every attachment host returned robots HTTP 403, or document access
   is ambiguous/reCAPTCHA. No request was made to an attachment.
2. **No real parsing.** PDF layout, Vietnamese font encoding, scans, tables, annexes,
   consolidated text, and amendment-heavy structure are untested on real documents.
3. **No legal review.** Validity, effective/expiry dates, amendments/repeals,
   territorial scope, transitional provisions, and annex completeness are unreviewed.
4. **No sealing prerequisites met.** Sealing a real release requires the pinned cached
   XLM-R tokenizer plus explicit publication approval; neither is present.
5. **Thin planning coverage.** Only one district-level land-use plan lead and one
   official news lead (not a legal instrument).

## Exact evidence paths

- `docs/corpus-sources.md` — sources, policy table, 18 candidates, issuer evidence note.
- `docs/corpus-acquisition.md` — acquisition outcome, controls, manual procedure.
- `docs/corpus-inventory.md` — counts, inventory, metadata completeness.
- `docs/corpus-quality-report.md` — quality gates, synthetic evidence, acceptance gates.
- `corpus/phase-d-candidates.json` — registry
  (SHA-256 `44fd41d45642067452c6547571cb22e0506ff6bb9c1d509038c277798a17befa`).
- `corpus/source-approvals.json` — policy registry
  (SHA-256 `8964c6d31b654a6d1706b845374bf54797089d5d20fdfd05aafdf4d29ded7a5a`).
- `corpus/discovery-history/` — preserved earlier registry revision.
- `data/phase-d-network/http-journal.jsonl` — discovery/policy request journal.
- `data/phase-d-corpus-v2/reports/corpus-quality.json` — counts and release summary.
- `data/phase-d-corpus-v2/reports/draft-release.json` — empty unsealed draft.
- `data/phase-d-corpus-v2/reports/manual-review-queue.json` — 18 manual entries.

## Required decisions before progress

1. Approve or decline automated access to the robots-403 attachment hosts and to
   `vbpl.vn`; or perform manual browser downloads.
2. Provide qualified human legal review for identity, validity, amendments/repeals,
   territorial scope, transitional provisions, and annex completeness.
3. Provision the exact cached tokenizer before any real seal.
4. Authorize real neural embedding only in a later, separately approved phase.

Until then the correct state is: **18 discovered, 0 acquired, 0 parsed, 0 reviewed,
0 chunks, 0 embeddings, 0 indexed, 0 published.**
