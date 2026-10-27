# Phase D.2 validation — parser recovery, review packets, R0 research draft

> **Phase D.2 validation snapshot.** Stage-specific counts and draft publication
> status are distinct from the [isolated demo corpus](corpus.md). Technical
> extraction success does not certify legal validity.

## Outcome

Phase D.2 recovered technically usable extractions for the two R0 instruments
(`43/2024/QH15` and `88/2024/NĐ-CP`), created an explicit per-document human-review
packet/workflow, provisioned the pinned tokenizer only, and produced a **RESEARCH_ONLY**
R0 draft. No legal review, sealing, embedding export, Qdrant indexing, publication,
commit, or deployment was performed.

**R0 is not asserted to be in force, complete, or sufficient for general Hanoi advice.**
Both documents remain `legal_validity=unknown`, `human_reviewed=false`, and every review
category is still `pending`.

| Measure | Result |
|---|---:|
| Official identifiers acquired in D.1 | 8 |
| Preserved official PDFs | 16 |
| Active stage records (superseding lineage applied) | 16 |
| Superseded v2 stage records (immutable evidence) | 16 |
| Active parsed stages | 10 |
| Active quarantined stages | 6 |
| Multipart components (not standalone instruments) | 13 |
| Annex-only fragments | 1 |
| **R0 release candidates** | **2** (`43/2024/QH15`, `88/2024/NĐ-CP`) |
| Human-reviewed stages | **0** |
| Sealed / indexed / published real releases | **0 / 0 / 0** |

## D.1 audit correction

The D.1 report's "8 instruments / 7 parsed stages" figures were stage counts, not
instrument counts. Audit of the workspace found **16 acquired PDFs across 8
identifiers**: several instruments were published by the gazette as multiple continuation
PDFs, and the earlier inventory counted some parts as if they were separate parsed
instruments.

Phase D.2 therefore classifies every active stage as one of:

- **release candidate** — a single acquired artifact with operative articles and no
  duplicate bytes (`43/2024/QH15`, `88/2024/NĐ-CP`);
- **multipart component** — any identifier represented by more than one active artifact;
  no part is a release candidate until a reviewer verifies a complete standalone
  rendition;
- **annex-only fragment** — real extracted annex material with no standalone articles
  (`102/2024/NĐ-CP` part 3), never promotable to a document/release on its own;
- **quarantined** — extraction/QA refusal; never reviewable or sealable.

Because `31/2024/QH15`, `101/2024/NĐ-CP`, `102/2024/NĐ-CP`, `103/2024/NĐ-CP`, and
`133/VBHN-VPQH` are multipart, their parts remain excluded from release candidacy even
when a part parses cleanly.

## Parser defects fixed (within the existing architecture)

Parser version: `local-legal-parser-v3`; quality gate: `pilot-quality-v2`.
No OCR, crawl, model inference, or alternate corpus was used.

1. **PDF text extraction** now uses `pdfminer.six` per page, with the existing `pypdf`
   path only as a per-page fallback. The extraction report records the format, page count,
   fallback pages, blank pages, and stripped-line count.
2. **Horizontal padding** is collapsed while preserving line structure. Single-space
   syllable splits are *not* guessed at, because repairing them would reconstruct text.
3. **Gazette mastheads/page numbers** are stripped only near page edges. The stripped
   count is reported (`43`: 4 lines; `88`: 76 lines) and must still be spot-checked.
4. **Trailing blank PDF pages** are skipped and reported; blank pages inside the body
   remain warnings rather than silent deletions.
5. **Administrative form annexes** (`MẪU`, `Mẫu số`, `Kèm theo`, `ban hành kèm theo`) are
   detected and their template `Điều`/clause/point headings are not promoted into
   operative provisions. The underlying text spans are preserved.
6. **Article numbering QA** is global to the instrument rather than reset by chapter, so
   a valid continuation is no longer reported as an article-sequence defect.
7. **Reparse is append-only.** A reparse writes a new stage with
   `supersedes=<old_stage_id>` and never overwrites the old artifact. Superseded stages
   are excluded from inventory and refused by `review`, `decide_category`, and `seal`.
8. **Multipart classification** was added to inventory so continuation PDFs cannot be
   silently treated as complete instruments.

Old v2 stage files remain byte-for-byte unchanged and are retained as evidence.

## R0 extraction results

| | `43/2024/QH15` | `88/2024/NĐ-CP` |
|---|---|---|
| Stage id | `7d6545c477d531ffa0345d5045ac18c0ba2a3b9e3d8b1b875912b7313193fb89` | `2c9ed6d69894410ae68cbb8fa97a76252831b399f1589e26b5d08e7786aa9a02` |
| Raw SHA-256 | `859d1f08a3a9fd5555ffc4396226cb2c86a4c48c6f577331cdd476071d2e00f4` | `a5721e26bb7079e107c4e1bc2eda9474f4f9bb416219fa0db55e779139ebe94f` |
| Parsed text SHA-256 | `c55af2b904d337329da91d95f6802d9846cf283a7859e18f85ab9d78d7dc84fc` | `d8c51ff3a0ac966540a58f16c2b13a43aade1343b1d71167bddfaa271d3d8fb5` |
| Extracted characters | 3,571 | 78,595 |
| PDF pages | 2 | 38 |
| Chapters / sections | 0 / 0 | 3 / 5 |
| Articles | 5 | 32 |
| Clauses | 4 | 121 |
| Points | 2 | 127 |
| Annexes | 0 | 1 (administrative form) |
| Structured articles | 5 | 32 |
| Extraction state | `validated_pending_legal_review` | `validated_pending_legal_review` |

`43/2024/QH15` is an amending instrument: its five articles amend four other laws and do
not restate those laws. It cannot be used as a consolidated Land Law. `88/2024/NĐ-CP`
contains an attached administrative form template; the template is excluded from operative
provisions but still requires visual review.

## Remaining quarantined stages

Six active stages still fail the parser's QA and remain quarantined. They were not
repaired, OCR'd, or guessed at.

| Identifier | Preserved file | Reason |
|---|---|---|
| `71/2024/NĐ-CP` | `50667-1-2024783-78471-2024-nd-cp.pdf` | Repeated legal locator |
| `102/2024/NĐ-CP` | `51276-1-2024933-934102-2024-nd-cp.pdf` | Repeated legal locator |
| `103/2024/NĐ-CP` | `51304-1-2024945-946103-2024-nd-cp.pdf` | Repeated legal locator |
| `133/VBHN-VPQH` | `58840-1-20251337-1338133-vbhn-vpqh.pdf` | Numbered clause outside an article |
| `133/VBHN-VPQH` | `58846-1-20251341-1342133-vbhn-vpqh.pdf` | Repeated legal locator |
| `31/2024/QH15` | `49032-1-2024367-36831-2024-qh15.pdf` | Repeated legal locator |

A repeated locator usually indicates a table of contents, a combined/consolidated
rendition, or an amending instrument quoting the text it amends. Resolving it requires a
human decision and possibly a different official rendition, not automatic text repair.
The multipart `31/2024/QH15` parts also leave the instrument without a verified complete
body.

## Human-review packets

Generated under `data/phase-d-corpus-v2/review-packets/`:

- `43-2024-qh15-859d1f08a3a9/`
- `88-2024-nd-cp-a5721e26bb70/`

Each packet contains:

- `report.md` — human briefing with provenance, page checks, provision samples,
  limitations, and exact commands;
- `checklist.json` — machine-readable checklist bound to `stage_id`, `raw_sha256`,
  `text_sha256`;
- `decisions/*.template.json` — four separate templates (A/B/C/D) containing `FILL:`
  markers that are rejected verbatim.

Checklist categories (25 items total):

| Category | Meaning | Items |
|---|---|---:|
| A. Source identity | identifier, title, issuer, official host, raw hash, completeness | 6 |
| B. Extraction quality | pages, hierarchy, diacritics, annex handling, stripped lines, counts, spans | 7 |
| C. Legal metadata | dates, publication, effective/transitional clauses, relations, annexes, type | 6 |
| D. Applicability/validity | validity, dates, territory, later amendments, provision status, current-law claim | 6 |

**Approvals are separate.** A/B/C approval is a parsing/source decision and does not
certify legal validity. D cannot be approved while validity is `unknown` or the effective
date is absent. Evidence-only records do not change any approval status. Every decision is
append-only and bound to the exact raw/text hashes; an artifact change invalidates prior
approvals.

## Tokenizer provisioning (authorized scope only)

Pinned target:
`AITeamVN/Vietnamese_Embedding_v2@18b44161e041bf1d3a333ab5144b5b7b93f914d2`.

Only four official tokenizer files were downloaded:

| File | Bytes | SHA-256 |
|---|---:|---|
| `tokenizer_config.json` | 1,203 | `b87c8703482b0300d3da30e201519aa641f6a450f5eb5bf1e624afbf70c74d80` |
| `tokenizer.json` | 17,098,251 | `b74659c780d49afad7a7b9799868f75cbd3014fb6c34956e85a793028d38094a` |
| `sentencepiece.bpe.model` | 5,069,051 | `cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865` |
| `special_tokens_map.json` | 964 | `8c785abebea9ae3257b61681b4e6fd8365ceafde980c21970d001e834cf10835` |

No weights, ONNX files, model config, remote code, or authentication were used. The
provisioning manifest at
`data/model-cache/hub/models--AITeamVN--Vietnamese_Embedding_v2/provision.json` records
`scope=tokenizer-only`, `weights_downloaded=false`, `remote_code=false`.

Offline verification:

- class `XLMRobertaTokenizerFast`;
- vocabulary size `250002`;
- `model_max_length=8192`;
- deterministic sample tokenization: 23 tokens;
- round-trip decode matches the Vietnamese input.

`CachedTokenizerBudget` loads `XLMRobertaTokenizerFast` directly from the pinned snapshot
instead of `AutoTokenizer`, because `AutoTokenizer` would require the model `config.json`,
which is outside the authorized tokenizer-only scope.

## Chunking and embedding-export readiness

Using the pinned tokenizer at `max_tokens=512`:

- chunk IDs and boundaries are deterministic across repeated runs;
- concatenated source spans reproduce the input exactly (lossless);
- chunk IDs are unique;
- the longest generated chunk used 504 tokens (within the 512 budget);
- chunker version: `legal-spans-v1`.

Dense-contract checks all pass:

| Check | Result |
|---|---|
| Model id/revision pinned | pass |
| Dimension = 1024 | pass |
| dtype = float32 | pass |
| Pooling = CLS | pass |
| Normalization = true | pass |
| Contract max tokens = 2048 | pass |
| Compatibility document agrees | pass |
| Synthetic 8-d contract kept separate | pass |

A temporary batch-manifest round-trip validated JSONL records, checksums, batch id, and
the 1024-d model contract. **No corpus chunk, neural vector, or batch was written to
production storage.** The synthetic 8-dimensional vectors remain test fixtures only.

## R0 draft

Artifacts:

- `data/phase-d-corpus-v2/reports/r0-research-draft.json`
- `data/phase-d-corpus-v2/reports/r0-research-draft.md`

Key state:

| Field | Value |
|---|---|
| `state` | `DRAFT` |
| `research_only` | `true` |
| `purpose` | `research` |
| `human_reviewed` | `false` |
| `approved_publication` | `false` |
| `indexed` / `published` | `false` / `false` |
| `legal_validity` | `unknown` |
| `current_law_ready` | `false` |
| Embedding export | `ready_after_seal` |

Blockers (10 total): for each document, A/B/C/D decisions and the explicit whole-stage
review. No embedding blocker remains. Canonical persistence remains empty: every legal
corpus table has 0 rows, and the two existing metadata-only draft releases remain
unsealed (`published=false`).

## Tests and integrity checks

- Full suite: **216 passed** (202-test baseline preserved + 14 D.2 regression tests).
- An **isolated copy rehearsal** (never the real workspace) recorded test-only category
  decisions, sealed a research release, and exported **303 chunk records** twice with
  byte-identical `records.jsonl`/`input.json`. No neural vectors were generated. The real
  `data/phase-d-corpus-v2` workspace still has **0 decisions, 0 seals, and 0 canonical
  legal rows**.
- D.2 regression coverage includes: packet read-only generation, separate/bound
  decisions, D-validity rule, `FILL:` rejection, evidence-only records, quarantine
  refusal, append-only reparse/superseded rejection, category-gated seal, multipart
  classification, synthetic refusal in R0, parser whitespace behavior, gazette edge
  stripping, form-annex suppression, global article numbering, and trailing blank PDF.
- `uv lock --check` and `uv pip check` pass.
- All 16 preserved PDFs still hash-match both their `raw/<sha256>/` directory names and
  their `incoming/<sha256>/` originals.
- No raw artifact was overwritten, no real application database row changed, no review
  decision exists, and no secret is written to reports or committed files.

## Exact commands used or available

Inspect inventory and readiness:

```bash
uv run --frozen python -m preprocess.offline_cli --workspace data/phase-d-corpus-v2 review-list
uv run --frozen python -m preprocess.offline_cli --workspace data/phase-d-corpus-v2 \
  review-eligibility --stages \
  7d6545c477d531ffa0345d5045ac18c0ba2a3b9e3d8b1b875912b7313193fb89 \
  2c9ed6d69894410ae68cbb8fa97a76252831b399f1589e26b5d08e7786aa9a02
```

Regenerate packets and draft (safe, does not approve):

```bash
uv run --frozen python -m preprocess.offline_cli --workspace data/phase-d-corpus-v2 \
  packets --stages \
  7d6545c477d531ffa0345d5045ac18c0ba2a3b9e3d8b1b875912b7313193fb89 \
  2c9ed6d69894410ae68cbb8fa97a76252831b399f1589e26b5d08e7786aa9a02
uv run --frozen python -m preprocess.offline_cli --workspace data/phase-d-corpus-v2 r0-draft
```

Provision and verify the tokenizer (authorized tokenizer-only scope):

```bash
uv sync --frozen --extra tokenizer
uv run --frozen python scripts/provision_tokenizer.py \
  --cache-dir data/model-cache/hub --verify
```

## Not performed

No human approval, no seal, no embedding generation, no Qdrant indexing, no corpus
publication, no crawl, no OCR, no Gemini/judge call, no GPU job, no deployment, and no
commit/stage/push. See `docs/corpus-review-runbook.md` for the only permitted next
actions.
