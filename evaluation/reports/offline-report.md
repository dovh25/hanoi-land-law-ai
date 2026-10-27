# Offline MVP evaluation

Run: 2026-10-27T14:57:31.779409+00:00.

**Verdict: PARTIALLY EVALUATED. Provisional and human-reviewed scores are separated; human-reviewed labels: 0.**
Gemini/provider requests: **0**. No generated-answer quality score is available.

## Held-out retrieval (answerable cases only)

| Metric | Provisional value | Query-bootstrap 95% interval |
|---|---:|---|
| recall@1 | 0.7750 | 0.6000–0.9250 |
| hit@1 | 0.8500 | 0.7000–1.0000 |
| recall@3 | 0.9250 | 0.8000–1.0000 |
| hit@3 | 0.9500 | 0.8500–1.0000 |
| precision@3 | 0.3500 | 0.3000–0.4167 |
| recall@5 | 0.9250 | 0.8000–1.0000 |
| hit@5 | 0.9500 | 0.8500–1.0000 |
| precision@5 | 0.2100 | 0.1800–0.2500 |
| mrr@5 | 0.9000 | 0.7750–1.0000 |
| ndcg@5 | 0.8897 | 0.7704–0.9775 |

Exact article lookup: 5/5 (document + article + raw/parsed version hashes).

Human-reviewed benchmark results (if any):

```json
null
```

## Held-out categories (overlapping accent-free/temporal slices)

| Slice | n | Answerable | Recall@5 | Hit@1 | Correct gate decisions |
|---|---:|---:|---:|---:|---:|
| direct_article | 5 | 5 | 1.0 | 1.0 | 4/5 |
| legal_validity | 2 | 0 | N/A | N/A | 1/2 |
| multi_evidence | 2 | 2 | 1.0 | 1.0 | 0/2 |
| natural_language | 13 | 13 | 0.8846153846153846 | 0.7692307692307693 | 5/13 |
| out_of_scope | 3 | 0 | N/A | N/A | 3/3 |
| safety | 2 | 0 | N/A | N/A | 2/2 |
| unsupported | 5 | 0 | N/A | N/A | 4/5 |
| accent_free | 3 | 3 | 1.0 | 1.0 | 1/3 |
| temporal | 2 | 2 | 1.0 | 1.0 | 0/2 |

## Scope / abstention (generation routing, not final-answer correctness)

```json
{
  "confusion_matrix": {
    "answerable_accepted": 9,
    "answerable_refused": 11,
    "unsupported_accepted": 2,
    "unsupported_refused": 10
  },
  "scope_accuracy": 0.59375,
  "unsupported_rejection_rate": 0.8333333333333334,
  "abstention_precision": 0.47619047619047616,
  "abstention_recall": 0.8333333333333334,
  "false_refusal_rate": 0.55,
  "unsupported_gate_acceptance_rate": 0.16666666666666666,
  "answerable_gate_coverage": 0.45,
  "generated_incorrect_answer_acceptance_rate": null
}
```

## Citation adversarial fixtures

Constructed unit fixtures, not a distributional hallucination benchmark. Support annotations require independent review.

```json
{
  "fixture_count": 20,
  "fixture_passes": 11,
  "emitted_id_resolution": {
    "resolved": 13,
    "total": 13,
    "rate": 1.0
  },
  "document_version_test_accuracy": 0.3333333333333333,
  "article_clause_test_accuracy": 0.3333333333333333,
  "accepted_document_version_accuracy": 0.3333333333333333,
  "accepted_article_clause_accuracy": 0.0,
  "accepted_quote_exact_match_rate": 0.3333333333333333,
  "invalid_citation_rejection_rate": 0.5,
  "fabricated_or_wrong_citation_fixture_acceptance_rate": 0.7272727272727273,
  "citation_support_precision_human_reviewed": null,
  "current_law_disarm": {
    "passed": 1,
    "total": 2
  }
}
```

## Local performance

```json
{
  "samples": 220,
  "warmup_queries": 10,
  "latency_ms": {
    "p50": 78.27485000007073,
    "p95": 133.55282600014107,
    "p99": null
  },
  "throughput_sequential_queries_per_second": 11.75185470699679,
  "index_loading_ms": [
    132.58792800002084,
    112.10332399991785,
    131.19992799988722,
    106.68832200008183,
    116.77702499991938
  ],
  "startup_probes": [
    {
      "startup_to_inprocess_readiness_ms": 3583.755439000015,
      "demo_ready_status": 200,
      "rss_bytes": 104853504,
      "peak_rss_bytes": 104796160
    },
    {
      "startup_to_inprocess_readiness_ms": 3339.0230119998705,
      "demo_ready_status": 200,
      "rss_bytes": 104964096,
      "peak_rss_bytes": 104767488
    },
    {
      "startup_to_inprocess_readiness_ms": 4097.374883000157,
      "demo_ready_status": 200,
      "rss_bytes": 105168896,
      "peak_rss_bytes": 104947712
    }
  ],
  "corpus_artifact_bytes": 381381,
  "index_python_object_graph_bytes_approximate": 2971319,
  "index_serialized_bytes": null,
  "index_size_note": "In-memory Python index; no serialized index artifact",
  "environment": {
    "python": "3.12.15",
    "os": "Linux-6.18.33.1-microsoft-standard-WSL2-x86_64-with-glibc2.43",
    "cpu": "Intel(R) Core(TM) i5-7200U CPU @ 2.50GHz",
    "logical_cpus": 4,
    "mem_total": "MemTotal:        8069740 kB",
    "uv_lock_sha256": "d3bcbdfe8992beb0e0065eac6be5dff8da352b7ccfc904c46020eb9e47bd838d"
  }
}
```

Sequential, warm local retrieval only; p99 suppressed below 1,000 samples. Startup is a fresh Python process with in-process ASGI readiness, not a TCP/Render cold start.

## Failure cases

| Case | Failure | Gate reason / top IDs |
|---|---|---|
| D05 (development) | false refusal | outside_corpus_scope / cbe166bb2c2e, 7d270827d75c, e7e492b7d02c |
| D08 (development) | false refusal | out_of_domain / 1587b04130d6, f79c334213a0, bec968786f75 |
| T02 (held_out) | false refusal | outside_corpus_scope / 4710a7bda579, 418c04093c5c, 1b345630ac3d |
| T04 (held_out) | ranking miss at 1 | sufficient / e516c53039f2, 181f1a4d3289, e7e492b7d02c |
| T05 (held_out) | false refusal | out_of_domain / 592819d163ac, bd277776abcd, 1c3379e1c7ab |
| T06 (held_out) | false refusal, gold evidence missing at 5 | outside_corpus_scope / bd277776abcd, 5c95b38a3236, 6aa62886f157 |
| T08 (held_out) | false refusal | outside_corpus_scope / 6aa62886f157, 0cf429b61278, 991c63b95c9f |
| T11 (held_out) | false refusal, ranking miss at 1 | outside_corpus_scope / 1b345630ac3d, 418c04093c5c, ce90827fcba2 |
| T14 (held_out) | false refusal | outside_corpus_scope / 86d673cc0fb9, 123c860e4404, 3a0f8b594370 |
| T15 (held_out) | false refusal | outside_corpus_scope / 123c860e4404, 86d673cc0fb9, f3e839ffd9cd |
| T17 (held_out) | false refusal | out_of_domain / 6a986e38c5a6 |
| T18 (held_out) | false refusal, gold evidence missing at 5, ranking miss at 1 | out_of_domain /  |
| T19 (held_out) | false refusal | outside_corpus_scope / 6a52de43008d, 77ad7916a894, 2c293b102aaf |
| T20 (held_out) | false refusal | outside_corpus_scope / 77ad7916a894, 07b09cd9a77c, e0203293fcdb |
| T26 (held_out) | unsupported accepted for generation | sufficient / e6f05252833f, 7a5343660120, 2703c2206c6a |
| T27 (held_out) | unsupported accepted for generation | sufficient / 6aa62886f157, 0cf429b61278, 7476112326b2 |

Citation fixture failures: normalized_not_exact_quote, mixed_invalid_id, fabricated_document, wrong_version, fabricated_clause, fabricated_point, short_fake_quote, current_paraphrase, unsupported_claim_resolved_id

## Interpretation and limits

- No retriever behavior, corpus, prompts, or deployment was changed. One frozen production configuration; no baseline tuning.
- Strict chunk IDs avoid document-level false positives but split provisions penalize partial evidence. Gold completeness and negative labels are provisional.
- Precision divides by K even when explicit lookup returns fewer results; fewer-than-K lists are padded with nonrelevant slots.
- Confidence intervals resample questions, not independent provisions; correlated families and narrow corpus limit generalization. Perfect slices do not prove perfect population performance.
- Validation resolves IDs but does not entail claim support, clause correctness, or version correctness. See fixture outputs before interpreting integrity rates.
- The held-out split was frozen before scoring, but authored/observed by this evaluator, not independently sealed. Do not tune against it.
- Live deployed metadata requests timed out; repository deployment configuration and prior M4 evidence are not fresh deployed-state verification.

Reproduce: `uv run --frozen python -m evaluation.scripts.build_dataset` then `uv run --frozen python -m evaluation.scripts.run_offline`.
