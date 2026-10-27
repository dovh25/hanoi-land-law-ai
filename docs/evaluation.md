# Evaluation methodology and verified retrieval highlights

## Scope

The offline framework evaluates stored-version retrieval, evidence-gate decisions,
constructed citation-integrity fixtures and local API/performance behavior.
It does **not** measure generated legal-answer accuracy or independently validate
applicability/current law. It invokes neither Gemini nor an LLM judge.

The [original summary](evaluation/results-summary.md) and
[raw report](../evaluation/reports/offline-report.md) remain unchanged and include
all measured outcomes, not only the selected retrieval highlights below.

## Dataset and corpus binding

- 44 source-authored cases: 12 development and 32 held-out.
- Held-out: 20 answerable and 12 negative; direct-article, natural-language,
  multi-evidence, scope, temporal and safety cases are represented.
- All 44 labels remain provisional: **zero independent human approvals**.
- Gold relevance refers to exact version-specific chunks in the 2-document,
  90-chunk corpus with SHA-256
  `ce0df852742ea3144ae5c04bdef27580d88d53752ad6039a4cdd0b091a73508e`.
- The split is now observed; do not tune the product against it and then claim an
  independent held-out result. Independent review/adjudication remains necessary.

## Selected offline retrieval results

| Metric | Definition | Held-out result |
|---|---|---:|
| Recall@5 | Fraction of gold chunks retrieved in first five, averaged by query | 0.925 |
| MRR@5 | Reciprocal rank of first relevant chunk, zero if absent, averaged by query | 0.900 |
| Hit@5 | Fraction of answerable queries with at least one relevant chunk in first five | 0.950 |
| Exact article lookup | Correct explicit article lookup among five held-out direct-article cases | 5/5 |

Retrieval denominators exclude negative cases; exact-article lookup has its own
five-case denominator. Binary chunk relevance and macro averages are used.
Precision uses a fixed K denominator, including when fewer hits are returned.
The stored Recall@5 bootstrap 95% interval is [0.8, 1.0]; the small, correlated
sample does not establish population legal accuracy. See
[metric definitions](evaluation/metrics.md).

These values describe retrieval **before the evidence gate**. In the same held-out
run the gate accepted 9/20 answerable and 2/12 unsupported cases. Constructed
citation fixtures matched 11/20 expected behaviors. Valid IDs therefore do not
establish support for a legal claim. Human-reviewed generated-answer quality and
semantic citation-support precision remain unmeasured. Complete per-case results,
fixture outcomes and interpretation are preserved for technical review.

## Reproduce without replacing original evidence

Use the existing frozen Python environment. Verify corpus statistics with the
[corpus guide](corpus.md), then recompute rankings and macro metrics in memory:

```bash
uv run --frozen pytest tests/test_evaluation.py -q
```

The [evaluation runbook](../evaluation/README.md) documents full offline runs,
dataset materialization and review workflows. **Full runners overwrite generated
reports**; archive them before a new run. This maintenance pass preserves the
existing datasets, worksheets, reports, test XML and performance history and does
not regenerate them. Timing is machine/run-specific, not cloud capacity evidence.

| Evidence | Location |
|---|---|
| Frozen configuration | [offline.json](../evaluation/configs/offline.json) |
| Source-authored questions | [source-authored.tsv](../evaluation/datasets/source-authored.tsv) |
| Materialized cases and provenance | [cases.jsonl](../evaluation/datasets/cases.jsonl) |
| Machine-readable original results | [offline-results.json](../evaluation/reports/offline-results.json) |
| Per-question results | [per-question.csv](../evaluation/reports/per-question.csv) |
| Review and adjudication | [dataset review guide](evaluation/dataset-review-guide.md) |
| Full methodology | [methodology](evaluation/methodology.md) |

`benchmarks/` and the 20-question demo smoke script are separate retained tools;
their results are not the 44-case evaluation and are not Hanoi end-to-end QA
validation. Ragas is not an implemented runtime/evaluation dependency. Live
DeepEval judges are blocked; a prepared live evaluation plan is not authorization
to execute it.
