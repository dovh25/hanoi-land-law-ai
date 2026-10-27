# Phase D — corpus quality report

> **Phase D quality snapshot.** Results describe this phase's inputs and gates.
> See [current runtime corpus](corpus.md) and [evaluation](evaluation.md) for the
> demo; technical extraction checks do not establish legal validity.

## Bottom line

**No real corpus-quality percentage can be reported.** Phase D acquired zero full-text
instruments. Reporting article/clause/point extraction accuracy, duplicate rates,
hierarchy completeness, or amendment coverage for an empty real corpus would be
invented. The figures below distinguish implemented checks, synthetic test evidence,
and real-corpus facts.

| Layer | Result |
|---|---|
| Real documents acquired | 0 |
| Real documents parsed | 0 |
| Real documents quarantined | 0 |
| Real provisions extracted | 0 |
| Real chunks generated | 0 |
| Real legal reviews completed | 0 |
| Synthetic parser/quality tests | 24 Phase D pilot tests (in the 197-test suite) |
| Real quality percentage | **Not computable / not claimed** |

## Implemented quality gates

`law_crawler/quality.py::assess` runs on every stage created through the existing
ingestion path. Critical findings quarantine the stage and block review/sealing until a
new stage is supplied.

Critical checks:

- empty extraction;
- extracted-text SHA-256 mismatch against the stage record;
- replacement character (`U+FFFD`), NUL, or `(cid:)` glyph-loss indicators;
- duplicate locators;
- broken or uncovered source-span coverage;
- invalid parent ordering;
- missing article numbers inside an article sequence (for example 1, 3);
- no usable article structure where the document should have it.

Warnings that require human inspection but do not silently pass as reviewed:

- article sequence starts after Article 1 (possible multi-part source);
- no article headings (possible annex/unstructured material);
- extraction warnings from the parser.

The gate is deliberately conservative. It does **not** prove legal correctness, current
validity, amendment status, table completeness, or OCR quality. It only prevents clearly
broken extraction from entering a release candidate.

The existing Phase C parser still provides:

- UTF-8/NFC normalization without accent stripping;
- TXT/HTML/text-PDF/DOCX extraction;
- ordered Part → Chapter → Section → Subsection → Article → Clause → Point hierarchy;
- tables/annexes as ordered non-overlapping spans;
- exact normalized-text character spans;
- explicit quarantine for empty/non-text PDFs, unsupported automatic DOCX numbering,
  tracked changes, text boxes, nested tables, and other unsafe structures;
- no OCR and no LLM text reconstruction.

## Synthetic evidence

The tests exercise the quality gates and parser contracts with explicitly SYNTHETIC
fixtures. They are parser/self-test evidence, not legal-corpus evidence.

Examples of covered cases:

- missing article number (`Điều 1`, `Điều 3`) is quarantined;
- altered extracted-text hash is quarantined;
- an incomplete synthetic document cannot be approved through the review API;
- duplicate locators, broken spans, and invalid parent order are rejected;
- hierarchy extraction preserves article/clause/point structure;
- acquisition provenance, content-addressed raw bytes, idempotent re-ingestion, and
  pending review status are preserved;
- a 41st instrument is refused before any request;
- robots denial, 401/403/429 stop, redirect rejection, retry cap, `Retry-After`, and
  access-challenge detection are enforced without network access in tests.

Real PDF layout, Vietnamese font encoding, scanned pages, tables, annexes, and
amendment-heavy documents remain untested because no real attachment was acquired.

## Provenance quality

Provenance is stronger for discovery than for acquisition:

| Provenance item | Coverage |
|---|---:|
| Candidate discovery timestamp | 18/18 |
| Candidate discovery evidence SHA-256 | 18/18 |
| Official source URL | 18/18 |
| Declared attachment URL | 18/18 |
| Source policy record | 8/8 inspected hosts |
| Acquisition timestamp | 0/18 |
| Original raw bytes + SHA-256 | 0/18 |
| HTTP response metadata | 0/18 for documents; discovery requests journaled |
| Review event | 0/18 |
| Release membership | 0/18 |

The network journal preserves policy/discovery evidence. It is not a substitute for
preserving the legal attachment bytes, which were not downloaded.

## Relationship and legal-status quality

- **14** relationship claims are recorded from titles and official related-document rows.
  They are unreviewed.
- **0** relationships have been verified against operative text.
- **18/18** legal validity values are `unknown`.
- **0/18** publication dates are verified; the inspected pages did not expose them.
- **1/18** has no effective-date claim (`71/2024/NĐ-CP`).
- **0/18** expiry/replacement statuses are verified.
- No consolidated/amended text was reconstructed.

The registry therefore cannot support a current-law release. A research release with
unknown validity is also not ready because no text has been acquired or reviewed.

## Quality risks for the next acquisition attempt

1. **PDF extraction risk.** Real Vietnamese legal PDFs may be scanned, use embedded
   fonts, multi-column layouts, tables, or annexes. Text extraction must be checked
   visually; OCR is unsupported.
2. **Hierarchy risk.** Consolidated documents, appendices, and amendment instructions
   can contain multiple article sequences or cross-references that a generic parser may
   misclassify.
3. **Amendment/repeal risk.** A title or related-document row is not proof of scope.
   Multiple versions and transitional provisions require human legal review.
4. **Territorial risk.** National instruments, Hanoi People's Committee decisions, and
   district land-use plans have different applicability. The registry records a pending
   claim, not a verified scope.
5. **Duplicate risk.** The same instrument may appear on multiple portals with different
   file renditions. Real-byte deduplication and semantic reconciliation are not yet
   demonstrated.
6. **Freshness risk.** The metadata was discovered in October 2026. Portals can change
   or remove documents; the registry evidence hash is a snapshot, not a guarantee of
   current status.

## Acceptance gates before any future release

A real release must not be sealed until all of the following are true:

- every included instrument has an official source page, preserved raw bytes, SHA-256,
  retrieval timestamp, HTTP metadata, and original filename;
- extraction is reviewed against the source, including tables/annexes;
- article/clause/point hierarchy is complete and no critical quality gate is open;
- legal validity, effective/expiry dates, amendments/repeals, territorial scope, and
  transitional provisions are reviewed by a qualified human;
- every included document has an explicit approval decision;
- the pinned cached XLM-R tokenizer is provisioned for canonical chunking;
- the release is sealed with explicit publication approval and remains
  `indexed=false` / `published=false`.

## Reproduce the checks

```bash
uv run --frozen pytest -q
uv run --frozen pytest tests/test_pilot.py tests/test_offline_ingestion.py tests/test_legal_domain.py -q
```

After manual acquisition:

```bash
uv run --frozen python -m preprocess.offline_cli \
  --workspace data/phase-d-corpus-v2 ingest \
  --manifest <acquisition.json>
```

Inspect the stage JSON and run the review workflow in `docs/corpus-review.md`. A
`validated_pending_legal_review` state is not legal approval.
