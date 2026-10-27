# MVP evaluation — zero external LLM requests

**Provisional research evaluation, not verified legal QA accuracy.** The evaluator
does not change the corpus, ranking, prompts, application configuration, or deployment.

From the repository root, using the existing frozen Python 3.12 environment:

```bash
uv lock --check
uv pip check
uv run --frozen python -m evaluation.scripts.build_dataset
uv run --frozen python -m evaluation.scripts.run_offline
uv run --frozen python -m evaluation.scripts.prepare_live_plan
uv run --frozen pytest -q --junitxml=evaluation/reports/pytest.xml
uv run --frozen python -m evaluation.scripts.review_artifacts
```

Do **not** run `build_mvp_demo_corpus.py`: no corpus rebuild is needed or authorized.
No Ragas/DeepEval installation, extra model weights, or provider keys are needed.
The frozen runtime is `uv.lock`; evaluation knobs and corpus hash are in
`configs/offline.json`. The offline runner blocks network sockets, forbids provider
invocation, uses explicit keyless test settings, and isolates temporary databases
under `evaluation/reports/`. Startup probes have the same restrictions.

## Outputs

| Artifact | Purpose |
|---|---|
| `datasets/source-authored.tsv` | Source-inspected questions and explicit source ordinals; no retrieval-derived labels |
| `datasets/cases.jsonl` | Materialized exact source text, stable IDs, hashes, provisional labels |
| `datasets/source-review.md` | Readable reference evidence for each question |
| `datasets/label-review.csv` | Human approval/correction input, preserved on regeneration |
| `datasets/answer-review.csv` | Blank answer-quality rubric worksheet |
| `datasets/citation-review.csv` | Citation support/adversarial review worksheet |
| `fixtures/citations.json` | Constructed validator probes, not generated answers |
| `reports/offline-results.json` | Configuration, hashes, metrics, raw timings, responses, per-fixture outcomes |
| `reports/offline-report.md` | Compact tables, failures, interpretation |
| `reports/per-question.csv` | Sortable per-question results |
| `reports/pytest.xml`, `reports/test-summary.json` | API/evaluator regression evidence |
| `reports/live-plan.json` | Five offline-prepared cases; **not approval and not executed** |

The runner consumes explicit named/date-stamped human CSV decisions on subsequent
runs and separates reviewed from provisional scores. Blank worksheets confer no
review status. See [review guide](../docs/evaluation/dataset-review-guide.md).

Timing changes between runs; deterministic rankings/metrics should not change with
unchanged sources, labels, code, and configuration. Reports overwrite prior generated
reports, **not** review worksheets. Archive a run before changing labels/configuration.
This split has now been observed; do not tune production against it.
