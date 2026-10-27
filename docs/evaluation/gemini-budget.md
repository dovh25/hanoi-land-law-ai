# Gemini evaluation budget — NOT APPROVED / NOT EXECUTED

**Actual generation requests: 0. Judge requests: 0.** All offline runs use keyless
test configuration, blocked network sockets and a provider-invocation guard.
Public deployment metadata checks are read-only and made no generation request.
Documentation retrieval is not a Gemini/judge request.

## Five frozen cases

`uv run --frozen python -m evaluation.scripts.prepare_live_plan` prepares this
manifest **offline**; the script has no live flag and cannot send requests.

| ID | Case | Expected routing | Expected provider requests |
|---|---|---|---:|
| T01 | Điều 4 decree 88: valuation timing for different-purpose compensation land | sufficient | 1 |
| T07 | Điều 20 decree 88: document required for contracted-land production support | sufficient | 1 |
| T13 | Điều 29 decree 88: inspecting ministry in stored rendition | sufficient | 1 |
| T21 | Fabricated Điều 777 | abstain | 0 |
| T24 | Medical dosage question | out of domain | 0 |
| | Expected total | | **3** |

Manifest `evaluation/reports/live-plan.json` stores the exact five Vietnamese
queries, retrieval IDs, full retrieved text, exact bounded context, expected gate
decisions, source hashes and blank result fields. Its three generation prompts
contain **3,647 / 4,607 / 2,097 characters** including system text. Character counts
are not Gemini token usage. No full corpus is sent; only approved bounded contexts.
The held-out retrieval cases are reused deliberately for this diagnostic replay;
do not describe the later answer test as another independent dataset.

## Approval and preflight gates

Do not use an existing public chat endpoint for generation: its current model,
shared usage, cap and live flag were not verified by this audit. The versioned
blueprint differs from prior M4 observed settings (eight versus fifty/day).
No public deployment/environment change is authorized for this experiment.

Before **any** live call, obtain all of:

1. User approval of the exact five-case manifest and request budget (expected 3,
   absolute ceiling **8 attempts including failures**, **no automatic retries**,
   **no judges**). Eight is a safety ceiling, not a target.
2. Account owner confirmation that the selected key belongs to the intended
   project, Free Tier applies to the selected model, and billing remains disabled.
   Never save the key/project credentials in the report.
3. Current official/model-picker verification that the exact model is available
   in that project. Local `.env` / Render blueprint say `gemini-3.5-flash-lite`,
   while the typed default is `gemini-2.5-flash-lite`; neither is proof of access
   or Free Tier eligibility. `live-plan.json` deliberately leaves model_id null.
4. Actual **project-wide** RPM, TPM and RPD from AI Studio, remaining shared quota,
   UTC timestamp and reset window; published generic limits are insufficient.
   Pause concurrent usage administratively without changing the public deployment,
   or choose a time/project with demonstrably sufficient headroom; otherwise stop.
5. A single local operator/process, a fresh process-scoped live configuration
   (not an edit to `.env`) and an experiment attempt counter persisted **before**
   each provider transport attempt. All transport must remain through
   `backend/services/llm.py`; preserve its daily ledger and shared budget.

## Execution contract after approval

An approved local replay runner must enforce: one call/turn; experiment total ≤8
including failures; SDK attempts=1; application retries=0; timeout=20s; output
≤1,024 tokens; no query rewrites, grounding/search tools, fallback model or judge.
The repository's UTC daily ledger is shared with any other local calls and differs
from Google's reset window. Do not reset/delete it. If today's shared count leaves
insufficient approved headroom, wait or stop; never increase the application cap
to compensate. Ephemeral public ledgers are not a global spend guarantee.

Run each of the five cases once, sequentially, with spacing respecting verified
RPM/TPM. Stop immediately on timeout, 429/quota error, invalid answer/fallback,
unexpected routing, counter discrepancy, or quota uncertainty. Do not retry or
rerun successful cases. The eight-attempt ceiling is never permission for retries.
If routing consumes a call for a negative case, stop and record the defect.
Review saved outputs deterministically and using the human rubric; do not add
unapproved follow-up questions to obtain a better answer.

Persist per case: user query; exact retrieved chunk IDs/full text; exact bounded
prompt context; generated raw/final answer; citation IDs; source hashes; latency;
attempt counters before/after; routing and validation outcome/warnings; token
usage **if available**; redacted upstream numeric status. The existing adapter
returns only text, so token usage is currently unavailable and must stay null
rather than be fabricated. `llm_used=false` is not an attempt counter, especially
on failures. A separately approved observability change is needed if SDK token
metadata must be preserved. Keep keys, hidden credentials and personal case data
out of all artifacts. Use only these public legal questions.

Afterwards restore process live-off state, verify counters/AI Studio usage and
archive immutable response files. No server push/deployment is needed. The
three-generation output ceiling is 3,072 tokens; the eight-attempt absolute ceiling
is 8,192 output tokens, not an input-token estimate or expected consumption.

## Judge experiment

EVAL-D requires a separate exact request/token approval after the saved answers
exist. Nominal Faithfulness is two LLM stages per answer, about six additional
calls for three answers, potentially more with repair/retries unless bounded.
No judge adapter or executable live runner is enabled here. See
`ragas-assessment.md`; human correctness and citation-support review come first.
