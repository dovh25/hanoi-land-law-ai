# Evaluation results summary

## Verdict: PARTIALLY EVALUATED

The offline framework was implemented and executed. Retrieval is promising on a narrow
stored-version corpus, but the gate rejects many supported questions and syntactic
citation checks do not establish legal support. **Not validated for legal advice or
unattended current-law QA.** No product ranking, prompt, corpus or deployment was changed.

## A. Architecture and provenance

- Actual demo: React → FastAPI → straight-line `MvpRagPipeline` → BM25 → gate → optional Gemini → validator.
- No LangGraph, neural embeddings, Qdrant or learned reranker on the evaluated demo path; legacy paths are separate.
- Two stored instruments (43/2024/QH15, 88/2024/NĐ-CP), 90 chunks, 77,243 characters; all validity unknown.
- Corpus SHA-256: `ce0df852742ea3144ae5c04bdef27580d88d53752ad6039a4cdd0b091a73508e`.
- Both preserved raw/parsed artifacts and all 90 source spans match. This is provenance consistency, not legal validation.
- BM25 k1=1.5/b=.75, document/heading boosts, heading bigrams, explicit reference filter, article diversification; K=6, score≥5, coverage≥.5, heading≥.30.
- Two public read-only metadata checks timed out. Current deployed model/cap/commit settings are unverified; blueprint and prior M4 evidence differ.

## B. Dataset

- 44 new cases: 12 development / 32 held-out (20 answerable + 12 negative held-out).
- 0 independent human-reviewed labels / 44 provisional source-authored labels. No fully validated benchmark score yet.
- Category distribution (all cases): direct_article=8, legal_validity=3, multi_evidence=2, natural_language=18, out_of_scope=4, safety=2, unsupported=7.
- Four accent-free questions overall (three held-out); two stored-version temporal questions held-out. These are overlapping slices, not extra cases.
- No historical questions reused or lexical duplicate-screen flags. Frozen but not independently sealed; now observed, so do not tune against it.

## C. Provisional held-out retrieval

| Metric | Value |
|---|---:|
| recall@1 | 0.7750 |
| recall@3 | 0.9250 |
| recall@5 | 0.9250 |
| precision@3 | 0.3500 |
| precision@5 | 0.2100 |
| mrr@5 | 0.9000 |
| ndcg@5 | 0.8897 |
| hit@1 | 0.8500 |
| hit@3 | 0.9500 |
| hit@5 | 0.9500 |
| Exact article lookup | 5/5 |

Binary, version-specific chunk relevance; fixed-K precision denominator. Macro query averages, negatives excluded.
Recall@5 bootstrap 95% interval: [0.8, 1.0]. Small/correlated sample; not population legal accuracy.

| Held-out slice | n | Recall@5 | Correct gate decisions |
|---|---:|---:|---:|
| direct_article | 5 | 1.0 | 4/5 |
| legal_validity | 2 | N/A | 1/2 |
| multi_evidence | 2 | 1.0 | 0/2 |
| natural_language | 13 | 0.8846153846153846 | 5/13 |
| out_of_scope | 3 | N/A | 3/3 |
| safety | 2 | N/A | 2/2 |
| unsupported | 5 | N/A | 4/5 |
| accent_free | 3 | 1.0 | 1/3 |
| temporal | 2 | 1.0 | 0/2 |

## D. Safety and citations

| Expected / gate outcome | Accepted | Refused |
|---|---:|---:|
| Answerable | 9 | 11 |
| Unsupported | 2 | 10 |

- Scope accuracy: 59.38%; answerable coverage 45.00%; false refusal 55.00%.
- Unsupported rejection: 83.33%; abstention precision 47.62%; recall 83.33%.
- Two unsupported cases accepted **for generation**, not proven incorrect generated answers: T26 (definitive personal eligibility without facts), T27 (unamended-current-law guarantee).
- Citation fixtures: 11/20 expected behaviors pass. Emitted ID resolution 13/13; invalid-integrity fixture rejection 50.00%.
- Accepted document/version claim accuracy 33.33%; accepted article/clause locator accuracy 0.00%; strict accepted-quote matching 33.33%.
- Fabricated/wrong-citation acceptance among accepted integrity-labeled fixtures: 72.73%. This is an adversarial fixture rate, **not** production hallucination prevalence.
- Current-law assertion fixtures disarmed 1/2. Human-reviewed citation-support precision and generated-answer quality are **unmeasured**, not inferred from IDs.

## E. Local performance and API reliability

- Last run, 220 timed retrievals after 10 warm-ups: p50 **78.27 ms**, p95 **133.55 ms**, p99 withheld (too few observations).
- Sequential throughput **11.75 queries/s**; index-loading median **116.78 ms** (five samples).
- Fresh-process in-process ASGI readiness median **3583.76 ms** (three samples). Not TCP or Render cold-start latency.
- Ready-process median RSS **100.10 MiB**; index object graph ≈2.83 MiB (approximate, not RSS); corpus JSONL 381,381 bytes; no serialized index.
- Python 3.12.15; Intel(R) Core(TM) i5-7200U CPU @ 2.50GHz; 4 logical CPUs; WSL2/Linux. Lock hash and memory details in JSON.
- Local timing varied materially between runs (see `performance-run-history.json`); do not extrapolate to free-cloud latency or capacity.
- Network-blocked pytest: **282 tests**, 0 failures, 0 errors, 0 skipped. Includes local API contracts and mocked budgets, not public uptime.
- `uv lock --check` and `uv pip check` passed; no evaluation dependency additions.

## F. Ragas

Ragas 0.4.3 metadata/official APIs inspected; no package installed or Ragas metrics implemented/executed.
Exact-ID recall/precision would duplicate local arithmetic (precision denominator differs for short results).
Text similarity adds no legal-semantic proof. EVAL-B skipped as redundant. LLM Faithfulness and all other judges deferred; nominal two stages/answer, not one API call/score.

## G. Gemini

Live provider requests **0**; judge requests **0**. Five-case manifest prepared: three answerable, one unsupported, one out of scope; expected **3** generation requests, absolute ceiling **8 including failures**, no retries or judges.
Explicit budget approval, exact model access, Free Tier/billing-disabled status, actual shared RPM/TPM/RPD/headroom, and transport-level experiment accounting remain required. No live execution is enabled.

## H. Failure analysis and next decisions

1. **Gate coverage is the main observed bottleneck:** topical heading/domain lists reject useful paraphrases, accent-free and temporal/amending-law questions despite relevant retrieval. Both multi-evidence cases retrieve all gold at 5 yet refuse.
2. **Cross-reference parsing:** T18 names target articles 200/210; the outer amending article is 4. The first explicit article reference drives filtering and yields no hits.
3. **Partial-clause miss:** T06 retrieves the continuation but misses the beginning of the split clause at 5. T04/T11 rank neighboring chunk content first.
4. **Validator gaps:** wrong documents/versions, invented clause/point locators, short fake quotes, mixed valid/invalid markers, semantic contradictions and unrecognized current-law paraphrases can survive. ID validity is not support.
5. **Product fixes are proposals only:** add separately reviewed clause/version/per-claim support checks and evaluate gate/parsing changes using new independent test data. No automatic correctness gain is claimed.
6. **Review before conclusions:** complete label/adjudication and human citation support; generated answer correctness/applicability remain unresolved. No accuracy claim beyond provisional stored-version retrieval.

## Reproduce and review

```bash
uv run --frozen python -m evaluation.scripts.build_dataset
uv run --frozen python -m evaluation.scripts.run_offline
uv run --frozen python -m evaluation.scripts.prepare_live_plan
uv run --frozen pytest -q --junitxml=evaluation/reports/pytest.xml
uv run --frozen python -m evaluation.scripts.review_artifacts
```

Primary reports: `evaluation/reports/offline-report.md`, `offline-results.json`, `per-question.csv`.
Review inputs: `evaluation/datasets/label-review.csv`, `answer-review.csv`, `citation-review.csv`; readable evidence: `source-review.md`.

### Presentation summary

> Zero Gemini requests. 44 new cases (44 provisional), 32 held-out. Provisional Recall@5=0.925; 9/20 supported questions pass the gate, with 2/12 unsupported questions also passing. Citation IDs resolve but do not guarantee legal support. Independent answer review is still required. **PARTIALLY EVALUATED.**
