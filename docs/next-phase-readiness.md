# Phase E readiness — real neural embedding preparation

> **Optional neural-workflow planning snapshot.** This is not the public MVP
> execution path or a prerequisite for [current setup](environment-setup.md).

## Status

Phase D.2 recovered technically usable R0 extractions for `43/2024/QH15` and
`88/2024/NĐ-CP`, generated human-review packets, provisioned the pinned tokenizer only,
and produced a **RESEARCH_ONLY** R0 draft. **No document has passed human legal review and
no real release is sealed**, so Phase E (real neural embedding of a released corpus)
**must not start yet**. See [phase-d2-validation.md](phase-d2-validation.md) and
[research-release-r0.md](research-release-r0.md).

| Prerequisite | State |
|---|---|
| 1024-dim model contract defined and pinned | Ready (`docs/model-compatibility-vietnamese-v2.json`) |
| Shared encoder with offline/version guards | Ready (`batch/embedding.py`) |
| Batch contracts, JSONL/JSON, float32 NPY | Ready (`batch/contracts.py`) |
| One-ZIP Colab Web exchange + receiver | Ready (`docs/colab-web.md`) |
| Acquired official PDFs | **16 PDFs / 8 identifiers** |
| Active stage records | 16 (plus 16 immutable superseded v2 stages) |
| Parsed active stages | 10 |
| R0 standalone release candidates | **2** (`43/2024/QH15`, `88/2024/NĐ-CP`) |
| Multipart components / annex-only fragments | 13 / 1 |
| Quarantined active stages | 6 (unresolved) |
| Reviewed stages | **0** |
| Sealed/indexed/published real releases | **0 / 0 / 0** |
| Pinned cached tokenizer (chunking/sealing) | **Ready on this host — tokenizer files only, no weights** |
| R0 research draft | `DRAFT`, `research_only=true`, not sealed |
| Explicit approval for model download / GPU inference | **Not granted** |
| Runtime numerical validation of the checkpoint | **Not performed** |
| Qdrant index / retrieval publication | **Out of scope; not performed** |

## Model contract (do not substitute)

- Model: `AITeamVN/Vietnamese_Embedding_v2`
- Revision: `18b44161e041bf1d3a333ab5144b5b7b93f914d2` (immutable pin)
- Architecture: `XLMRobertaModel`; loader `sentence_transformers.SentenceTransformer`
- Dimension: **1024**
- Pooling: **CLS only**
- Normalization: declared `Normalize` module, and `normalize_embeddings=True`
- Tokenizer: `XLMRobertaTokenizer` (SentencePiece); pinned `transformers==4.57.3`
- Max tokens: **2048 including special tokens**; oversized input is rejected, never
  silently truncated
- dtype: `float32`
- Learned sparse / ColBERT heads: **not supported** by this checkpoint
- Custom remote code: not required and explicitly disabled (`trust_remote_code=False`)
- Declared license: Apache-2.0 by the publisher (model card metadata only)
- Weights: **not downloaded**; parameters ~567,754,752 (metadata claim)

The encoder enforces the contract at load time: pinned ML package versions, exact
dimension, CLS-only pooling, XLM-R architecture, and a `Normalize` module chain. A
mismatch raises instead of producing silently incompatible vectors.

The card/licence/metadata were inspected publicly. **No runtime numerical validation,
embedding-quality benchmark, or Vietnamese semantic evaluation has been performed.**

## Colab compatibility

The existing exchange supports the 1024-dim contract unchanged:

- `preprocess/offline_cli seal` writes a sealed release only with the exact cached
  tokenizer identity (`MODEL_ID@MODEL_REVISION`); a real release cannot be sealed with the
  byte-budget fallback.
- `python -m batch.cli pack-colab` packages bounded chunks plus the pinned model metadata.
- `notebooks/embedding_batch.ipynb` validates the independently supplied input SHA,
  package allowlist, checksums, release/model binding, and expected 1024 dimensions.
- `python -m batch.cli verify-colab` / `receive-colab` validate dtype, dimension,
  NaN/Infinity, duplicate/missing IDs, and sealed-release membership. Imports are
  `indexed=false`; nothing is published to retrieval.

Colab remains an optional batch compute surface, not a dependency of the local app. The
notebook requires Python 3.12 and pinned package versions, and fails rather than resolving
a different environment. Real inference requires `SMOKE_ONLY=False` and an explicit
`ALLOW_MODEL_DOWNLOADS=True` in the Colab session.

The synthetic 8-dimensional `SYNTHETIC/hash-embedding-not-for-retrieval` vectors are test
fixtures only. They must never be mixed with, compared to, or substituted for the
1024-dimensional checkpoint vectors, and must never enter a real index.

## Ordered Phase E prerequisites

1. **Acquire real documents.** *(R0 acquisition is complete: `43/2024/QH15` and
   `88/2024/NĐ-CP` each have one preserved official PDF. The wider D.1 set is 16 PDFs
   across 8 identifiers.)* Remaining manual-only items (for example Hanoi
   `56/2024/QĐ-UBND`) are downloaded with a normal browser into
   `data/phase-d-corpus-v2/manual-inbox/<digest>/` per
   `data/phase-d-corpus-v2/reports/manual-download-guide.md`, then scanned with
   `python -m law_crawler.pilot_cli scan-manual-inbox`. Preserve original bytes, filename,
   SHA-256, retrieval timestamp, and HTTP metadata. Do not bypass access controls.
2. **Ingest and pass quality gates.** *(R0 extraction is complete under
   `local-legal-parser-v3` / `pilot-quality-v2`; both R0 stages are
   `validated_pending_legal_review`.)* Six other active stages remain quarantined
   (repeated legal locators or a numbered clause outside an article). Investigate them
   against the source; do not repair legal text with an LLM. Multipart identifiers are not
   standalone release candidates until completeness is verified.
3. **Complete human legal review.** **Still missing.** Complete the four separate
   category decisions plus the explicit whole-stage review for each R0 document. Confirm
   identity, validity, effective/expiry dates, amendments/repeals, territorial scope,
   transitional provisions, and annex completeness. A/B/C approval never certifies legal
   validity; D cannot be approved while validity is unknown. See
   `docs/corpus-review-runbook.md`.
4. **Provision the exact tokenizer.** *(Done for the tokenizer-only scope.)* The four
   pinned tokenizer files are cached at
   `data/model-cache/hub/models--AITeamVN--Vietnamese_Embedding_v2/snapshots/18b44161e041bf1d3a333ab5144b5b7b93f914d2/`
   and verified offline. No weights, model config, ONNX, or remote code were downloaded.
   Do not loosen the pin to make it work.
5. **Seal a release.** **Blocked on step 3.** Seal with `--approve-publication` for the
   intended purpose (`research` for unknown-validity corpora; `current-law` only with
   reviewed in-force status). Sealing is exportability, not retrieval publication. See
   `docs/research-release-r0.md` for the exact command.
6. **Approve inference separately.** Only then authorize the pinned checkpoint download
   and GPU/CPU inference in the approved environment. Prefer a reviewed cached snapshot.
7. **Verify results and import.** Run `verify-colab` then `receive-colab`. Keep the
   `indexed=false` receipt. Do not index Qdrant or publish retrieval without a further
   explicit decision.

## Explicitly still prohibited

- Downloading model weights, running GPU jobs, or calling paid APIs without approval.
- Using the synthetic embedding test or its 8-dimensional vectors for production.
- Building or querying a Qdrant/production index.
- Migrating or overwriting the configured application database.
- Self-certifying human legal review or sealing a release without real approvals.
- Describing R0 as current, complete, or sufficient for general Hanoi advice.
- Deploying or pushing.

## Bottom line

The embedding and Colab exchange layers are contract-ready and offline-tested. The pinned
tokenizer and R0 parser recovery are now in place, but **Phase E is still blocked on human
review, not code**: 0 reviewed documents, 0 sealed real releases, and no approved
inference. R0 remains a `DRAFT` research artifact.
