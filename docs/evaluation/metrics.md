# Metric definitions and denominators

Let G be the unique required, version-pinned **chunk IDs** for an answerable query;
Rₖ the actual ranked first K unique chunk IDs. All metrics are macro-averaged over
answerable queries; negative cases have null retrieval metrics, not zero recall.

| Metric | Definition |
|---|---|
| Recall@1/3/5 | `len(set(Rₖ) ∩ G) / len(G)` |
| Hit@1/3/5 | `1` iff at least one gold ID occurs in Rₖ |
| Precision@3/5 | `len(set(Rₖ) ∩ G) / K` |
| MRR@5 | Reciprocal rank of first relevant chunk within five, else zero |
| Binary nDCG@5 | `Σ relevance(rank)/log₂(rank+1)` divided by ideal DCG for `min(5,len(G))` positives |
| Exact article accuracy | Top-1 document number, article number, raw hash and parsed hash match a source reference, for the explicit direct-article category only |

Precision uses **fixed K**, padding short results as nonrelevant slots. Thus a
perfect one-chunk explicit lookup has Precision@5=.2; this should not be mistaken
for four observed false citations. Hit and recall differ for multi-chunk gold.
Duplicate input IDs are errors, not repeated credit. Gold alternatives are empty;
future alternative-equivalence groups require explicit adjudication and a documented
denominator change before scoring. Currently they fail closed if introduced.

## Retrieval-unit choice

The search corpus has 2 documents, 37 distinct document/article pairs (5+32), and
90 chunks. The search unit is a byte-budgeted contiguous article span, **not a
clause or point**. Chunks can split a clause and contain several clauses. Stable
`chunk_id` plus raw/parsed hashes is the primary unit. E1/E2 are request-local
aliases and must never be used as cross-query gold IDs.

- Document-level matching is too coarse: almost every decree chunk could count.
- Article matching is useful for exact lookup, but hides within-article misses and
  confused cross-references to the underlying Land Law.
- Clause/point locators are manually annotated review targets; the demo Evidence
  schema does not resolve them. Do not report automatic clause semantic recall.
- Strict chunks make version identity precise, but boundary/context dependencies,
  alternative provisions, and incomplete annotations can distort precision/recall.
- Stored-version identity **does not** establish current temporal applicability.

## Scope and abstention

Positive class = answerable/accepted by gate. Confusion matrix cells:
TP=answerable accepted, FN=answerable refused, FP=unsupported accepted,
TN=unsupported refused.

- Scope classification accuracy: `(TP+TN)/N` (binary scope/sufficiency combined).
- Unsupported rejection / abstention recall: `TN/(TN+FP)`.
- Abstention precision: `TN/(TN+FN)`.
- False refusal: `FN/(TP+FN)`; answerable gate coverage: `TP/(TP+FN)`.
- Unsupported gate acceptance: `FP/(TN+FP)`, **not** generated incorrect-answer rate.
- Generated incorrect-answer acceptance: unmeasured, null without generated answers.

`llm_disabled` is retrieval-only coverage, not an answered legal question and not
an epistemic abstention. Reporting rejection together with coverage prevents the
refuse-everything system from appearing successful. Out-of-scope, unsupported,
safety, and legal-validity slices are distinct; accent-free/temporal tags overlap.

## Citation integrity versus support

Constructed validator probes have explicit expected accept/reject/disarm labels.
Their outcomes are unit-test evidence, not estimated production hallucination rates.

| Output | Denominator / interpretation |
|---|---|
| Emitted ID resolution rate | Valid request-local aliases / all emitted E# aliases in accepted fixture text |
| Document/version test accuracy | Correct accept/reject decisions / document-version probes |
| Accepted document/version accuracy | Accepted source-matching document-version claims / accepted document-version probes |
| Article/clause test accuracy | Correct accept/reject decisions / article/clause/point probes |
| Accepted article/clause accuracy | Source-matching locator claims / accepted locator probes |
| Exact quote match rate | Strict source-matching quotes / accepted quotation fixtures; includes case-changing and short fake quotes as failures |
| Invalid citation rejection | Rejected invalid integrity fixtures / invalid integrity fixtures (excludes semantic-only support probe and current-law disarm probes) |
| Fabricated/wrong citation fixture acceptance | Accepted fixtures with known wrong citation/quote identity / accepted fixtures with binary integrity labels |
| Citation support precision | **Null** until independently reviewed claim–evidence support judgments exist |
| Current-law disarm | Rejected or explicitly neutralized fixture outputs / current-law assertion fixtures |

The validator normalizes quote case/whitespace and ignores quotes under 12
characters; that is not strict exact quoting. It checks against the union of cited
full chunks, not necessarily the particular sentence's cited chunk or bounded text
actually sent to Gemini. It does not validate document numbers or clause/point
locators, and it can remove an invalid marker while retaining its unsupported claim.
An emitted-ID resolution rate of 100% therefore says **nothing** about faithfulness.

Fixture expectations are source-inspected but pending independent review. No
metric here certifies legal reasoning or legal effect. Rates with tiny denominators
are accompanied by fixture-level rows; no inferential citation accuracy claim.
