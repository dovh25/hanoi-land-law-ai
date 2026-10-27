# Dataset and answer review guide

## Approve or correct labels without code

1. Open `evaluation/datasets/source-review.md`: each case includes question, proposed
   answerability, locators, key facts, exact evidence, offsets, and raw/parsed hashes.
   Check the preserved source rendition; source authenticity/meaning may require
   a qualified legal reviewer. All proposed answers are limited to that stored version.
2. Open `evaluation/datasets/label-review.csv` in a UTF-8 spreadsheet editor.
3. Check **all** required evidence, exceptions, cross-references and alternatives,
   not just the first matching article. Check question scope/ambiguity separately.
4. To approve unchanged: set `decision=approved`, `reviewer` to your identity, and
   `reviewed_at` to an ISO date/time, e.g. `2026-10-28T09:00:00+07:00`.
5. To correct: set `decision=corrected`; put the complete replacement chunk-ID list
   in `corrected_gold_ids` separated by `;`. Set `expected_answerable` to `True` or
   `False`; update `locators`, `key_facts` and `notes`. A negative case must have no
   gold IDs; an answerable case must have ≥1 source-resolving ID. Do not change the
   question, ID, or split in this worksheet.
6. Unresolved disagreements: leave `decision` blank, record notes, seek adjudication.
   Do not mark an AI check or a similarity score as independent human review.
7. Re-run `uv run --frozen python -m evaluation.scripts.run_offline`. The runner
   reads the CSV, checks identity/date, resolves corrected evidence against the
   hash-pinned artifact, and reports reviewed and provisional subsets separately.
   It records the review-worksheet hash. It cannot authenticate a reviewer's identity
   or professional competence; that is an organizational responsibility.

The immutable baseline JSONL stays provisional; a reviewed run records the overlaid
labels in per-question results. Archive baseline reports before replacing them.
`build_dataset` and `review_artifacts` never overwrite existing review worksheets.
Changing the corpus, question wording, split, or equivalence semantics needs a new
dataset version and fresh review, not a post-hoc correction to raise a score.

## Answer-quality rubric (0–2 per dimension)

Use `evaluation/datasets/answer-review.csv`. Current responses are retrieval-only
or deterministic refusals, **not generated legal answers**. Leave generation scores
blank until an approved saved answer exists. A blank is missing data, not zero.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Factual accuracy | Material contradiction or invented legal fact | Mostly correct but ambiguous/minor error or unresolved fact | All material claims correct against the reviewed source version |
| Faithfulness | Material claim unsupported by supplied context | Partly supported with overreach | Every material claim follows from supplied evidence |
| Completeness | Omits core answer/critical condition | Core answer present, some relevant conditions missing | Covers needed conditions, exceptions and limitations concisely |
| Question relevance | Off-topic or answers another question | Partially addresses user need | Directly addresses the actual question and its uncertainty |
| Citation support | Citation missing/wrong/does not support central claim | Some claims supported, some weak/misattached | Each substantive claim has correctly attached supporting evidence |
| Applicability caution | Unsupported current-law/personal definitive conclusion | Generic disclaimer but unclear date/version limits | Explicit stored-version and unknown-validity limitations, asks for missing facts where needed |

Report dimension scores and unresolved items, not just a 12-point total. A materially
false claim or unsafe applicability assertion blocks readiness regardless of total.
For refusals, separately review whether refusal/clarification was appropriate; do
not penalize a justified refusal for omitting an unsupported substantive conclusion.
Human correctness, source faithfulness, and legal applicability are distinct.

## Unresolved review priorities

- Gold completeness for T06 across a split clause, and T19/T20 across provisions.
- Whether bounded explanatory answers, clarification, or strict rejection are
  appropriate for ambiguous/personal/current-validity negative cases (T26/T27).
- Exceptions and cross-referenced laws absent from the two-document corpus.
- Amending-law targets versus outer article numbers (T17/T18).
- All applicability claims: later amendments/current institutional competence were
  not verified; no decision here establishes current Hanoi legal validity.
- Citation fixtures in `citation-review.csv`: distinguish syntactic integrity from
  actual claim support. Inspect the full fixture output and source record; no
  citation-support precision will be inferred automatically from this worksheet.
