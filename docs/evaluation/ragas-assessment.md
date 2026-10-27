# Cost-aware Ragas assessment

Checked on 2026-10-27 using official Ragas documentation (via Context7) and
PyPI package metadata. The repository does **not** include Ragas in `uv.lock`.
PyPI reports **ragas 0.4.3**, Python ≥3.9, released 2026-01-13. No package was
downloaded/installed, and no Ragas metric or LLM evaluator was executed.

## EVAL-B decision: skip redundant integration

The official stable docs expose `IDBasedContextRecall` and
`IDBasedContextPrecision` using `SingleTurnSample(retrieved_context_ids=…,
reference_context_ids=…)` and `single_turn_ascore`. These are deterministic,
non-LLM, non-embedding methods. IDs should be **version-pinned chunk IDs**, not
request-local E# aliases or ambiguous document numbers.

- ID recall at K equals this evaluator's Recall@K with the same unique ID lists.
- ID precision divides by the number of actually retrieved IDs. This equals our
  Precision@K only when K IDs are returned. Our fixed-K denominator deliberately
  differs for short exact-lookup results; do not conflate the definitions.
- The non-LLM text context metrics use string/similarity matching. They add no
  defensible legal-semantic evidence beyond exact IDs, especially with near-identical
  provisions and versions. Thresholded text overlap is not proof of legal correctness.

Thus EVAL-B provides no incremental evidence here. Deterministic equivalents were
implemented and executed directly; **Ragas metrics implemented/executed: none**.
No dependency changes or pin are necessary. If an integration is later justified,
start with an isolated **`ragas==0.4.3`** experiment, verify that version's imports,
check the frozen dependency resolution, and test only the ID metrics. The official
new collections API and older stable `ragas.metrics` examples coexist; do not
blindly paste an outdated `evaluate(...)` or judge-provider initialization recipe.

## EVAL-D: judge request accounting, deferred

Official current source documentation describes Faithfulness as two prompt stages:
1. extract atomic claims from the answer;
2. judge those claims against the provided context (NLI).

For three saved nonempty answers, the usual unbatched/no-retry path is **about
6 logical LLM generations**, **not 3**. Empty claim extraction may skip NLI;
parsing repair, batching choices, SDK/application retries or evaluator internals
can cause more requests. A library-level score call is not a quota accounting unit.
No exact production call count is asserted without a pinned implementation and
mocked transport trace. Any judge adapter must use this repository's shared
`backend/services/llm.py` budget boundary; do not introduce a direct Ragas SDK client.

Before approval, estimate tokens from the **saved actual answers and exact contexts**,
which do not yet exist as live outputs. Let Aᵢ be answer tokens, Cᵢ context tokens,
Qᵢ question tokens, Hₛ/Hₙ prompt/schema overhead and Sᵢ extracted-statement tokens.
Nominal input ≈ Σ[(Qᵢ+Aᵢ+Hₛ)+(Cᵢ+Sᵢ+Hₙ)] and output ≈ Σ[Sᵢ+NLIᵢ]. This is
two requests per scored answer in the nominal path; claims and token counts are
unknown until saved generation results exist. For coarse budget planning only,
2,000–6,000 input tokens per stage and ≤1,024 output tokens per stage imply
**12,000–36,000 input / ≤6,144 output tokens for six calls**, not a measurement or
guarantee. Replace that range with a tokenized prompt manifest before requesting
an exact judge budget. If it cannot fit Free Tier limits, skip the experiment.

Recommended priority is human correctness and citation-support review, then an
optional Faithfulness-only diagnostic if it adds value. Defer Response Relevancy,
LLM Context Precision/Recall, and Factual Correctness: overlapping costs, additional
calls, embeddings or claim-comparison stages, no established incremental value.
Judge requests must be approved **separately**, counted in addition to generation
including failed attempts, and hard-stopped by the transport budget. The current
eight-request generation ceiling does not authorize any judge calls.

LLM judges are non-authoritative legal diagnostics, not legal verification.

Sources:
- https://pypi.org/pypi/ragas/json
- https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/
- https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/
- https://github.com/vibrantlabsai/ragas/blob/main/docs/howtos/customizations/metrics/modifying-prompts-metrics.md
- https://github.com/vibrantlabsai/ragas/blob/main/docs/howtos/customizations/run_config.md

The main-branch source docs inform the two-stage caution, not a claim that a
particular uninstalled version's exact transport behavior was empirically traced.
