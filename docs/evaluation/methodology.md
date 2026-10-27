# Evaluation methodology

## Scope and status

EVAL-A runs the bundled MVP demo path offline, not the legacy neural/agentic path.
The new dataset contains **44 cases: 12 development, 32 held-out**. There are **28
answerable and 16 negative** cases; the held-out set has **20 answerable, 12 negative**.
All 44 annotations are **provisional source-authored labels**, with **zero independent
human-reviewed gold labels** at initial execution. No source-authored key fact is a
legal opinion or a verified model answer.

The corpus is `backend/resources/mvp_demo_corpus.jsonl`, SHA-256
`ce0df852742ea3144ae5c04bdef27580d88d53752ad6039a4cdd0b091a73508e`.
It contains 43/2024/QH15 (7 chunks) and 88/2024/NĐ-CP (83 chunks), **77,243
characters**. All records have unknown legal validity and technical-only review.
The available evidence is the preserved rendition, not consolidated current law.
No crawling, rebuilding, legal release, indexing, publication, or deployment occurs.

## Independent label construction

Questions and locators were authored after direct inspection of stored source text,
before the first new retrieval run. `source-authored.tsv` chooses source record
ordinals explicitly; the builder does not import or call retrieval. It materializes
the complete reference text, source offsets, document number, stage/version hashes,
stable chunk IDs, key facts, and annotation/review status. The fixed corpus hash
guards ordinal mappings. The runner compares every materialized field to the
artifact and checks all 90 spans and raw/parsed hashes against preserved local
stages when available. Missing preserved stages are disclosed rather than inferred.

**This is not independent human annotation.** AI source inspection can select wrong
or incomplete evidence. Source identity checks prove provenance, not relevance.
Human review must establish evidence completeness, exceptions, meaning, and scope.
No previous retrieval result, answer, or the old 20 questions was used as a label.
The old benchmark is imported only for duplicate screening, never executed or scored.

## Splits and contamination

Development and held-out questions are fixed in the seed TSV before scoring.
Provision/topic families are separated across splits (including multi-evidence
families). Lexical screening reports cross-split content-token Jaccard ≥0.70 and
old-question character similarity ≥0.80; exact historical reuse is forbidden.
The initial run has no such flags. Manual source-based authoring seeks distinct
facts, not accent/no-accent copies to inflate N. The linguistic slices use different
questions rather than paired duplicates. These heuristics do not prove semantic
independence, and the split is not independently sealed. Historical topic overlap
is unavoidable with only two documents; no broad generalization is justified.

No product behavior was tuned before or after scoring. The evaluated configuration
matches the versioned Render retrieval settings (K=6, minimum score 5, coverage .5).
The local environment contains no retrieval overrides for these fields. Runtime
credentials/live flags are deliberately replaced by keyless test settings; this is
a safety isolation step, not a retrieval change. No optional baseline was added:
the immediate value is measuring the actual MVP, not a reengineered retriever.

## Execution and uncertainty

- `run_offline` blocks Internet sockets and fails on provider invocation; no `.env`
  credentials are loaded into evaluation settings. No generated-answer scores.
- Search metrics use the actual `MvpCorpusIndex.search` before the gate. Every case
  is also run through `MvpRagPipeline.respond` in disabled mode; gate/output agreement
  is asserted and exact responses are saved. A retrieved but refused case remains a
  retrieval success and a coverage failure, not an end-to-end successful answer.
- Classification compares source-supported bounded research answerability with
  routing to generation. For ambiguous/current-law requests, gate acceptance is a
  risk signal, **not proof that a live answer would be unsafe**: the prompt or model
  may still refuse. No such answer has been generated here.
- Binary nDCG is used; there is no defensible graded legal relevance scale yet.
- Macro means weight questions equally. Development and held-out results are
  separate; negatives never enter ordinary recall/MRR/nDCG.
- Seeded 2,000-resample percentile bootstrap intervals are reported only for
  answerable retrieval slices with ≥10 cases. Smaller slices show counts. Families
  are correlated, so query bootstrap intervals may be optimistic; no population
  legal-accuracy inference or model-significance claim is made.
- No composite readiness score hides false refusals or unsupported acceptance.

## Performance and reliability

Ten warm-up queries, then five sequential passes over all 44 cases: **220 local
search timing samples**. Nearest-rank p50/p95; p99 withheld below 1,000 observations.
Five independent in-process index constructions measure warm-filesystem loading.
Three fresh Python subprocesses measure application import/factory/database lifespan/
index loading through in-process ASGI readiness. They do **not** include a TCP server,
network, deployment, or deliberately cold disk cache. RSS comes from `/proc`; the
Python object graph estimate is approximate and is not process RSS. The corpus
artifact is not a serialized search index. No concurrent/public load test is run.

Pinned network-blocked pytest covers API schemas, disabled/unsupported routing,
readiness, isolation, 401/422/429/503 behavior, citation fallbacks, rate limiting,
and mocked provider budgets/failures. Passing contract tests do not establish
public uptime or Gemini availability. Hardware, lock hash, timing samples, startup
samples, source hashes, and code hashes are retained in the result JSON.

## Deferred work

EVAL-B is intentionally skipped: Ragas ID metrics duplicate exact-ID arithmetic;
fuzzy text similarity provides no additional legal evidence. EVAL-C is prepared
but not executed; EVAL-D needs separate approval. Independent gold review and
human answer/citation-support review remain blockers to validated answer-quality
claims. See `gemini-budget.md` and `results-summary.md`.
