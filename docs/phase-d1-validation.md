# Phase D.1 validation — recovering authoritative corpus acquisition

> **Phase D.1 validation snapshot.** This preserves the acquisition/extraction
> results of that stage. See [current runtime corpus](corpus.md) for included
> artifacts and [D.2](phase-d2-validation.md) for subsequent extraction evidence.

> **Phase D.2 audit note:** the parsed-stage counts below are historical. D.2 found
> **16 preserved PDFs across 8 identifiers**, several of which are multipart
> continuations, and applied append-only parser v3 re-stages. See
> [phase-d2-validation.md](phase-d2-validation.md) for the current inventory
> (`16` active stages, `10` parsed, `6` quarantined, `2` R0 release candidates,
> `0` reviewed).

## Outcome

Phase D.1 resolves the acquisition blocker that Phase D hit. The previous strategy depended
on attachment hosts whose `robots.txt` returned HTTP 403. Phase D.1 found an **alternate
official representation** of the same instruments on the official Government Gazette file
CDN and acquired **8 instruments / 16 PDF originals** under an explicit, narrow source
policy. No access control was bypassed.

| Stage | Phase D | Phase D.1 |
|---|---:|---:|
| Candidate instruments discovered | 18 | 18 (+1 consolidated manifestation) |
| Official source URLs resolved to a downloadable file | 0 | 8 |
| Automatically acquired documents | 0 | **8** |
| Preserved original artifacts | 0 | **16** |
| Parsed stages (pending legal review) | 0 | **7** |
| Instruments with a parsed main body | 0 | **6** |
| Quarantined stages | 0 | 9 |
| Human-reviewed documents | 0 | 0 |
| Sealed / indexed / published | 0 | 0 |

Parsing is **not** legal review: all 7 parsed stages are `status=pending`,
`legal_validity=unknown`, `human_reviewed=false`. No release is sealed. The research-only
draft `phase-d1-authoritative-pilot-draft` remains `sealed=false`, `indexed=false`,
`published=false`, with no canonical document rows.

## What was acquired

All files come from `congbaocdn.chinhphu.vn` (official gazette file CDN), linked directly
from `congbao.chinhphu.vn` document pages. Each is an immutable original preserved under
`data/phase-d-corpus-v2/incoming/<sha256>/`, with an acquisition receipt in
`data/phase-d-corpus-v2/acquisitions/`, HTTP metadata and content-addressed evidence in
`data/phase-d-network/`.

| # | Instrument | Parts | Gazette issues | Parse result |
|---|---|---:|---|---|
| 1 | 31/2024/QH15 — Luật Đất đai | 3 | 363+364, 365+366, 367+368 | 2 parsed / 1 quarantined |
| 2 | 43/2024/QH15 — sửa đổi Luật Đất đai | 1 | 987+988 | parsed |
| 3 | 88/2024/NĐ-CP — bồi thường, hỗ trợ, tái định cư | 1 | 873+874 | parsed |
| 4 | 71/2024/NĐ-CP — giá đất | 1 | 783+784 | quarantined |
| 5 | 101/2024/NĐ-CP — điều tra cơ bản, đăng ký đất đai | 2 | 913+914, 915+916 | 1 parsed / 1 quarantined |
| 6 | 102/2024/NĐ-CP — chi tiết thi hành Luật Đất đai | 3 | 931+932, 933+934, 935+936 | 1 parsed / 2 quarantined |
| 7 | 103/2024/NĐ-CP — tiền sử dụng đất, tiền thuê đất | 2 | 945+946, 947+948 | 2 quarantined |
| 8 | 133/VBHN-VPQH — hợp nhất Luật Đất đai | 3 | 1337+1338, 1339+1340, 1341+1342 | 1 parsed / 2 quarantined |

Note: the `congbao.chinhphu.vn` page for the Land Law is **mislabeled** as
"Nghị quyết số 31/2024/QH15" (a different instrument that shares the number). The served
PDF text was verified to be *Luật Đất đai số 31/2024/QH15*, and the canonical identity was
taken from the correctly titled `vanban.chinhphu.vn` page. This discrepancy is recorded in
the manifestation registry and flagged for human review; it is not silently resolved.

## Source policy for the new host

| Host | robots.txt | Decision | Basis |
|---|---|---|---|
| `congbaocdn.chinhphu.vn` | **HTTP 404** (absent) | `approved_public_download` (limited) | Official gazette file CDN; files linked from `congbao.chinhphu.vn` pages whose robots is `Allow: /`; TLS chain verifies; HTTPS only |
| `congbao.chinhphu.vn` | HTTP 200, `Allow: /` | discovery only | metadata/document pages |
| `datafiles.chinhphu.vn` / `datafiles.hanoi.gov.vn` / `storage-vnportal.vnpt.vn` | HTTP 403 | blocked | unchanged from Phase D |
| `vbpl.vn` | disallows `/api/`, `/Pages/`; reCAPTCHA documents | blocked/ambiguous | unchanged from Phase D |
| `g7.cdnchinhphu.vn` | TLS chain fails to verify | not used | certificate verification is never disabled |

An absent `robots.txt` (HTTP 404) is treated as *unrestricted* per RFC 9309 §2.3.1.3, but
never as a blanket approval: the policy approves **only the exact 16 official PDF URLs**,
caps the phase at 10 instruments, requires ≥5 s between requests, and uses one request at a
time. A robots 403 or an unavailable/erroring robots remains a hard stop. The policy record
is `corpus/phase-d1-source-approvals.json`.

## Extraction and quarantine

The Phase D parser was line-based and too strict for real gazette PDFs. Three principled,
conservative fixes were applied (parser bumped to `local-legal-parser-v2`):

1. **Article headings require the numbering period** (`Điều N.` / `Điều N:`). A wrapped
   cross-reference such as `Điều 86 của Luật này` is no longer read as a new article.
2. **Container headings must be standalone lines** (`Chương III`, `Mục 1`). A wrapped
   cross-reference such as `Mục 5 Chương III của Nghị định này` or `Phụ lục ban hành kèm
   theo Nghị định này` is no longer read as a new chapter/section/annex.
3. **A trailing non-text PDF page** (the gazette signature/seal page) is skipped with a
   warning. A non-text page *before* the last text page still quarantines, and a fully
   text-free PDF still fails closed. OCR is not performed.

Quarantine is retained for genuinely ambiguous material — amending instruments that quote
article text (71, part of 102), multipart segment continuations (part of 31/101/133), and
annex form templates with repeated numbering (102/103). Nothing is discarded silently:
each quarantine records a precise reason in its stage JSON.

Provision nodes extracted from the 7 pending stages: 31 chapters, 55 sections, **415
articles**, 1,959 clauses, 2,260 points. These are extractions pending review, not verified
provisions.

## Manual handoff

Instruments still only reachable through blocked or ambiguous hosts (for example
`56/2024/QĐ-UBND` and the other Hanoi decisions) are listed with a per-document target
folder in `data/phase-d-corpus-v2/reports/manual-download-guide.md`. The operator drops an
official file into `data/phase-d-corpus-v2/manual-inbox/<digest>/` and runs:

```bash
uv run --frozen python -m law_crawler.pilot_cli scan-manual-inbox \
  --workspace data/phase-d-corpus-v2 --ingest
```

The scanner matches the file to the approved candidate, verifies the document identity
against the extracted text, writes the acquisition manifest, detects byte duplicates,
rejects ambiguous/unmatched files without guessing, preserves originals, and ingests a
**pending** (never valid) stage.

## Tokenizer readiness

The pinned contract is unchanged: `AITeamVN/Vietnamese_Embedding_v2` at revision
`18b44161e041bf1d3a333ab5144b5b7b93f914d2`, `XLMRobertaTokenizer` (SentencePiece), pinned
`transformers==4.57.3`, `local_files_only=True`, `trust_remote_code=False`, declared license
Apache-2.0. Only the tokenizer files (not weights) are required to make
`CachedTokenizerBudget` succeed. **No tokenizer or weights were downloaded in this phase.**
See `docs/model-compatibility-vietnamese-v2.json` and `docs/next-phase-readiness.md`.

## Executed validation

| Check | Result |
|---|---|
| Phase D policy/parser/quality/release tests | 29 passed |
| Full Python suite | **202 passed; 0 failed; 0 skipped** |
| `uv lock --check` | Passed (`Resolved 173 packages`) |
| `uv pip check` | Passed (`Checked 89 packages`; all compatible) |
| Isolated DB inspection | 2 metadata-only releases, all unsealed; 0 rows in all legal-corpus tables |
| Sealed release manifests | 0 |
| Credential scan | no configured secret values present in tracked source |

## Preserved state and prohibited actions

- `corpus/phase-d-candidates.json` (SHA-256 `44fd41d4…befa`) and
  `corpus/source-approvals.json` (SHA-256 `8964c6d3…7a5a`) are **unchanged**.
- The earlier Phase D draft and evidence are preserved; D.1 writes only new files.
- No commit, staging, push, deployment, Gemini request, model-weight download, GPU job,
  Qdrant connection, or OCR run occurred. `data/` remains Git-ignored.

## Evidence paths

- `corpus/phase-d1-instruments.json` — D.1 manifestations (SHA-256 `32a70e9a…f395`).
- `corpus/phase-d1-source-approvals.json` — CDN policy (SHA-256 `eb887e23…9b2e`).
- `data/phase-d-corpus-v2/acquisitions/` — 8 acquisition receipts (16 artifacts).
- `data/phase-d-corpus-v2/incoming/<sha256>/` — 16 preserved originals + manifests.
- `data/phase-d-corpus-v2/reports/phase-d1-quality.json` — counts and release summary.
- `data/phase-d-corpus-v2/reports/phase-d1-review-worksheet.md` — human-review checklist.
- `data/phase-d-corpus-v2/reports/manual-download-guide.md` — manual handoff.
- `data/phase-d-network/http-journal.jsonl` — policy/discovery/download journal
  (SHA-256 `3e1d1ee3…03e2`).

## Remaining decisions

1. **Human legal review** of the 7 pending stages (identity, validity, effective/expiry,
   amendments/repeals, territorial scope, transitional provisions, annex completeness).
2. **Annex/amendment/multipart segments** remain quarantined; provide a reviewed rendition
   or approve targeted parser work before they can enter review.
3. **Hanoi instruments** (including `56/2024/QĐ-UBND`) remain manual-only.
4. **Tokenizer provisioning** before any real seal; **inference approval** before embedding.
