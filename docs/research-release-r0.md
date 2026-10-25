# R0 research release — scope, state, and operator sequence

## What R0 is

R0 is a **two-instrument, research-only draft corpus** recovered in Phase D.2:

| Official number | Title | Type |
|---|---|---|
| `43/2024/QH15` | Luật sửa đổi, bổ sung một số điều của Luật Đất đai số 31/2024/QH15, Luật Nhà ở số 27/2023/QH15, Luật Kinh doanh bất động sản số 29/2023/QH15 và Luật Các tổ chức tín dụng số 32/2024/QH15 | Amending law |
| `88/2024/NĐ-CP` | Quy định về bồi thường, hỗ trợ, tái định cư khi Nhà nước thu hồi đất | Decree |

R0 exists to exercise the reviewed-corpus pipeline on real, officially acquired text. It
is **not** a general Hanoi legal corpus, not a consolidated Land Law, and not a legal
advice source.

## What R0 is not

- **Not current-law ready.** `legal_validity` is `unknown` for both instruments.
- **Not human reviewed.** All four review categories and the whole-stage review are
  pending; `reviewed=0`.
- **Not complete for general advice.** `43/2024/QH15` only amends four other laws and does
  not restate them. It cannot substitute for `31/2024/QH15` or the amended laws.
- **Not sealed, indexed, or published.** The draft is `state=DRAFT`, `indexed=false`,
  `published=false`, and `current_law_ready=false`.
- **Not a validity or completeness claim.** Publication dates are absent from the acquired
  PDFs and remain unrecorded.
- **Not OCR-derived.** No OCR was run; scanned-only material is refused rather than
  guessed.

## Document identity and artifact binding

| | `43/2024/QH15` | `88/2024/NĐ-CP` |
|---|---|---|
| Issuer | Quốc hội | Chính phủ |
| Jurisdiction | VN | VN |
| Issuance date | 2024-06-29 | 2024-07-15 |
| Publication date | not recorded | not recorded |
| Stage id | `7d6545c477d531ffa0345d5045ac18c0ba2a3b9e3d8b1b875912b7313193fb89` | `2c9ed6d69894410ae68cbb8fa97a76252831b399f1589e26b5d08e7786aa9a02` |
| Original file | `51470-1-2024987-98843-2024-qh15.pdf` | `51007-1-2024873-87488-2024-nd-cp.pdf` |
| Raw SHA-256 | `859d1f08a3a9fd5555ffc4396226cb2c86a4c48c6f577331cdd476071d2e00f4` | `a5721e26bb7079e107c4e1bc2eda9474f4f9bb416219fa0db55e779139ebe94f` |
| Parsed text SHA-256 | `c55af2b904d337329da91d95f6802d9846cf283a7859e18f85ab9d78d7dc84fc` | `d8c51ff3a0ac966540a58f16c2b13a43aade1343b1d71167bddfaa271d3d8fb5` |
| Parser / gate | `local-legal-parser-v3` / `pilot-quality-v2` | same |
| Characters | 3,571 | 78,595 |
| PDF pages | 2 | 38 |
| Articles | 5 | 32 |
| Chapters / sections | 0 / 0 | 3 / 5 |
| Clauses / points | 4 / 2 | 121 / 127 |
| Annexes | 0 | 1 (administrative form) |

Source pages:

- `43/2024/QH15`:
  `https://vanban.chinhphu.vn/?pageid=27160&docid=211201`
  (gazette PDF via `congbaocdn.chinhphu.vn`)
- `88/2024/NĐ-CP`:
  `https://vanban.chinhphu.vn/?pageid=27160&docid=210658`
  (gazette PDF via `congbaocdn.chinhphu.vn`)

Acquisition receipts and HTTP metadata are preserved under
`data/phase-d-corpus-v2/acquisitions/`. All 16 preserved PDFs still hash-match their
`incoming/<sha256>/` originals.

## Extraction state and known limitations

Both R0 stages are `validated_pending_legal_review`, not approved:

| | `43/2024/QH15` | `88/2024/NĐ-CP` |
|---|---|---|
| Required review categories A/B/C/D | pending | pending |
| Whole-stage review | pending | pending |
| `human_reviewed` | false | false |
| `legal_validity` | unknown | unknown |

Known limitations:

- **`43/2024/QH15` is amending only.** It changes `31/2024/QH15`, `27/2023/QH15`,
  `29/2023/QH15`, and `32/2024/QH15`; it does not contain their consolidated text.
- **`88/2024/NĐ-CP` has an attached administrative form.** Template headings are excluded
  from operative provisions, but the annex still needs visual review.
- **PDF reading order, tables, and footnotes** require human visual review. The parser
  reports this and does not claim OCR coverage.
- **Gazette mastheads/page numbers were stripped** (4 lines for `43`, 76 for `88`). A
  reviewer must confirm no legal text was removed.
- **Publication dates are unrecorded**, so they must not be inferred.
- **Validity, amendments, repeals, and transitional status are unresolved.** No later
  instrument was checked automatically.

## Human review required before sealing

Each document needs explicit, separate decisions:

1. **A. Source identity** — identifier, title, issuer, official host, raw hash,
   completeness.
2. **B. Extraction quality** — page coverage, hierarchy, diacritics, annex handling,
   stripped lines, counts, spans.
3. **C. Legal metadata** — dates, publication, effective/transitional clauses, relations,
   annexes, document type.
4. **D. Applicability / validity** — validity, dates, territory, later amendments,
   provision status, current-law claim.
5. **Whole-stage review** — the legacy gate required by `seal`.

A/B/C approval is a parsing/source decision and **does not** certify legal validity.
D cannot be approved while validity is `unknown`; a `pending` D with evidence is the
honest R0 state. See `docs/corpus-review-runbook.md` for the exact procedure.

Current blockers (10):

- `43/2024/QH15`: A, B, C, D, and whole-stage review.
- `88/2024/NĐ-CP`: A, B, C, D, and whole-stage review.

No embedding blocker remains.

## Review packets and draft artifacts

Packets:

- `data/phase-d-corpus-v2/review-packets/43-2024-qh15-859d1f08a3a9/`
- `data/phase-d-corpus-v2/review-packets/88-2024-nd-cp-a5721e26bb70/`

Draft:

- `data/phase-d-corpus-v2/reports/r0-research-draft.json`
- `data/phase-d-corpus-v2/reports/r0-research-draft.md`

Draft state:

```text
state=DRAFT
research_only=true
purpose=research
human_reviewed=false
approved_publication=false
indexed=false
published=false
legal_validity=unknown
current_law_ready=false
embedding_export=ready_after_seal
```

Canonical persistence remains empty: legal-document, version, provision, artifact,
manifest, relationship, territorial, and release-document tables all have 0 rows. The two
existing releases are metadata-only drafts with `published=false`.

## Embedding-export readiness

The pinned tokenizer is provisioned only, at:

`AITeamVN/Vietnamese_Embedding_v2@18b44161e041bf1d3a333ab5144b5b7b93f914d2`

Verified offline:

- `XLMRobertaTokenizerFast`, vocabulary `250002`, `model_max_length=8192`;
- four official tokenizer files only; no weights, model config, ONNX, or remote code;
- deterministic sample tokenization and round-trip decode.

Chunking at `max_tokens=512` is deterministic, lossless, and unique-ID-stable; the longest
smoke chunk used 504 tokens. The dense contract is 1024-dimensional, `float32`, CLS-only,
L2-normalized, with a 2048-token shared limit. A temporary batch-manifest round-trip
passed.

No neural embedding was generated. The synthetic 8-dimensional vectors are test fixtures
only and must never be used for R0. An isolated copy rehearsal sealed a test-only research
release and exported 303 chunk records deterministically; that copy is not the real
workspace, which remains unsealed and undecided.

## Exact sequence after all decisions exist

Check readiness first:

```bash
uv run --frozen python -m preprocess.offline_cli --workspace data/phase-d-corpus-v2 \
  review-eligibility --stages \
  7d6545c477d531ffa0345d5045ac18c0ba2a3b9e3d8b1b875912b7313193fb89 \
  2c9ed6d69894410ae68cbb8fa97a76252831b399f1589e26b5d08e7786aa9a02
```

Seal only when both rows show `research_seal_ready=true`:

```bash
HF_HOME=data/model-cache uv run --frozen python -m preprocess.offline_cli \
  --workspace data/phase-d-corpus-v2 seal \
  --name phase-d2-r0-research-v1 \
  --stages \
  7d6545c477d531ffa0345d5045ac18c0ba2a3b9e3d8b1b875912b7313193fb89 \
  2c9ed6d69894410ae68cbb8fa97a76252831b399f1589e26b5d08e7786aa9a02 \
  --purpose research \
  --cached-tokenizer --max-tokens 512 \
  --approve-publication
```

Then export to a fresh directory (still not indexing):

```bash
HF_HOME=data/model-cache uv run --frozen python -m preprocess.offline_cli \
  --workspace data/phase-d-corpus-v2 export \
  --release <sealed-release-hash> \
  --destination <fresh-directory>
```

## Prohibitions

- Do not describe R0 as current, complete, verified, or sufficient for Hanoi advice.
- Do not seal while any A/B/C/D/whole-stage gate is missing.
- Do not use `--purpose current-law` while validity is unknown.
- Do not generate or publish embeddings, index Qdrant, or deploy without separate
  approval.
- Do not reconstruct missing legal text or mark ambiguous content verified.
