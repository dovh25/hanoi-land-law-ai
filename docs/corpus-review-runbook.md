# Corpus review runbook — explicit human decisions

This runbook is for the **solo operator** reviewing Phase D corpus stages. It records
human decisions; it does not make them. Reviewing extraction quality is not a legal
validity determination, and a source URL never proves currency.

All commands use the real pilot workspace:

```bash
WORKSPACE=data/phase-d-corpus-v2
R0_43=7d6545c477d531ffa0345d5045ac18c0ba2a3b9e3d8b1b875912b7313193fb89
R0_88=2c9ed6d69894410ae68cbb8fa97a76252831b399f1589e26b5d08e7786aa9a02
```

Run from the repository root. Review commands read only the isolated workspace; they do
not read application settings or `.env`.

## 0. Non-negotiable rules

- **Never** mark `human_reviewed=true` implicitly. Every approval is an explicit command
  with a named reviewer, timestamp, evidence, scope, and limitations.
- **Never** approve a category that was not actually reviewed. There is no
  `--approve-all` flag, and there must not be one.
- **Never** reconstruct missing legal text from model knowledge. Ambiguous or missing
  text stays unresolved.
- **Never** approve a quarantined extraction. Supply a corrected/complete official
  rendition and ingest a new stage.
- **Never** review or seal a superseded stage. Use the active stage reported by
  `review-list`.
- **Never** treat A/B/C approval as legal validity. Category D is separate.
- **Never** infer an effective date, expiry date, repeal, or amendment. Unknown stays
  unknown.
- **Never** seal, index, or publish without a separate deliberate decision. Sealing is
  exportability, not retrieval publication.
- Decisions are bound to `stage_id`, `raw_sha256`, and `text_sha256`. If the artifact
  changes, earlier decisions do not carry over.

## 1. Inspect the inventory and pending work

```bash
uv run --frozen python -m preprocess.offline_cli --workspace "$WORKSPACE" review-list
```

The output reports, per active stage:

- extraction state (`validated_pending_legal_review`, `quarantined`, ...);
- `fragment`, `multipart_component`, and `release_candidate`;
- which category approvals exist;
- `missing` categories (no decision recorded yet);
- `research_seal_ready`.

Only `release_candidate=true` stages may be considered for a standalone document/release.
Multipart components and annex-only fragments are intentionally excluded until a complete
standalone rendition is verified.

Show one packet:

```bash
uv run --frozen python -m preprocess.offline_cli --workspace "$WORKSPACE" \
  review-show --stage "$R0_88"
```

This prints the packet directory, report path, and the current checklist. It never modifies
state.

## 2. Generate or regenerate packets

Packets are deterministic and safe to regenerate; they never approve anything.

```bash
uv run --frozen python -m preprocess.offline_cli --workspace "$WORKSPACE" \
  packets --stages "$R0_43" "$R0_88"
```

Outputs under `review-packets/<slug>/`:

| File | Purpose |
|---|---|
| `report.md` | Human-readable briefing, page checks, provision samples, limitations |
| `checklist.json` | Machine-readable checklist bound to the artifact hashes |
| `decisions/A_source_identity.template.json` | Template for category A |
| `decisions/B_extraction_quality.template.json` | Template for category B |
| `decisions/C_legal_metadata.template.json` | Template for category C |
| `decisions/D_applicability_validity.template.json` | Template for category D |

The templates contain `FILL:` text and are rejected verbatim. Regeneration refreshes
`report.md` and `checklist.json`; the four template files are write-once. Work on a copy
(see step 4) so a later artifact change can regenerate the packet without a template
conflict.

## 3. Review the actual artifact

For each document:

1. Open `report.md` and the preserved PDF in `data/phase-d-corpus-v2/raw/<raw_sha256>/`.
2. Confirm the raw hash on disk:
   ```bash
   sha256sum data/phase-d-corpus-v2/raw/<raw_sha256>/<original_filename>
   ```
3. Check every page — not just the sampled articles. Confirm order, headings, clause/point
   numbering, tables, footnotes, annexes, and that stripped mastheads/page numbers did not
   remove legal text.
4. Confirm identity, issuer, title, and document type from the signed/gazetted text.
5. Confirm dates and legal metadata from evidence. Do not infer publication dates.
6. Check later amendments/repeals, territorial scope, transitional provisions, and whether
   the instrument is complete or a continuation part.
7. Record unresolved limitations honestly. If you cannot verify something, do not approve
   as if it were verified.

## 4. Record one decision per category

Copy the relevant template to your working decision file, then edit the copy:

```bash
mkdir -p data/phase-d-corpus-v2/review-decisions
cp data/phase-d-corpus-v2/review-packets/88-2024-nd-cp-a5721e26bb70/decisions/B_extraction_quality.template.json \
   data/phase-d-corpus-v2/review-decisions/B_extraction_quality.json
```

Required fields:

| Field | Requirement |
|---|---|
| `category` | Overridden by `--category`; keep it consistent |
| `decision` | `approved`, `rejected`, or `pending` |
| `reviewer` | Your real name/identifier (no `FILL:`) |
| `reason` | What was checked and what was found |
| `evidence` | Page/paragraph/URL evidence |
| `scope` | Exact scope reviewed |
| `limitations` | Real unresolved limitations (may be empty only if truly none) |
| `reviewed_at` | ISO 8601 **with timezone** |
| `stage_id` | Copied from the packet |
| `raw_sha256` | Copied from the packet |
| `text_sha256` | Copied from the packet |
| `validity` | `unknown` unless independently verified |
| `effective_date` / `expiry_date` | Only from evidence; `null` when unknown |

Example A/B/C decision (replace every placeholder before use):

```json
{
  "category": "B_extraction_quality",
  "decision": "approved",
  "reviewer": "REPLACE: reviewer name",
  "reason": "REPLACE: page-by-page comparison result",
  "evidence": "REPLACE: pages/paragraphs checked",
  "scope": "REPLACE: exact artifact and sections reviewed",
  "limitations": ["REPLACE: anything not verified"],
  "reviewed_at": "2026-10-26T09:00:00+07:00",
  "stage_id": "2c9ed6d69894410ae68cbb8fa97a76252831b399f1589e26b5d08e7786aa9a02",
  "raw_sha256": "a5721e26bb7079e107c4e1bc2eda9474f4f9bb416219fa0db55e779139ebe94f",
  "text_sha256": "d8c51ff3a0ac966540a58f16c2b13a43aade1343b1d71167bddfaa271d3d8fb5",
  "validity": "unknown",
  "effective_date": null,
  "expiry_date": null
}
```

Submit exactly one category at a time:

```bash
uv run --frozen python -m preprocess.offline_cli --workspace "$WORKSPACE" \
  review-decide --stage "$R0_88" --category B_extraction_quality \
  --decision-file data/phase-d-corpus-v2/review-decisions/B_extraction_quality.json
```

Repeat for `A_source_identity`, `B_extraction_quality`, and `C_legal_metadata`, using a
separate working file per category.

### Convenience wrappers (still explicit)

```bash
# Force a rejection for the selected category.
uv run --frozen python -m preprocess.offline_cli --workspace "$WORKSPACE" \
  review-reject --stage "$R0_88" --category B_extraction_quality \
  --decision-file <edited-decision.json>

# Approve ONLY category B (extraction), never A/C/D.
uv run --frozen python -m preprocess.offline_cli --workspace "$WORKSPACE" \
  review-approve-extraction --stage "$R0_88" \
  --decision-file <edited-B-decision.json>

# Record evidence without changing any approval status.
uv run --frozen python -m preprocess.offline_cli --workspace "$WORKSPACE" \
  review-evidence --stage "$R0_88" --category C_legal_metadata \
  --decision-file <edited-evidence.json>
```

`review-evidence` writes `kind="evidence"` and forces `decision="pending"`; it cannot
upgrade or downgrade an approval.

## 5. Category D (applicability / validity)

Category D is different from parsing/source review. It records whether the instrument is
legally applicable.

- `decision="pending"` with `validity="unknown"` is allowed and is the honest default.
- `decision="approved"` requires a non-`unknown` validity **and** an explicit
  `effective_date`. The model rejects the decision otherwise.
- `decision="rejected"` blocks sealing.
- Recording D does **not** imply A/B/C approval, and A/B/C approval does **not** imply D.

For R0, no decision has been recorded, so both documents remain `legal_validity=unknown`.

## 6. Check eligibility

```bash
uv run --frozen python -m preprocess.offline_cli --workspace "$WORKSPACE" \
  review-eligibility --stages "$R0_43" "$R0_88"
```

Research readiness requires:

- active, non-superseded, non-quarantined stage;
- artifact binding matches the current raw/text hashes;
- A, B, and C explicitly approved;
- D recorded and not rejected;
- the legacy whole-stage `review` explicitly approved.

Current-law readiness additionally requires:

- D approved with `validity="in_force"`;
- the legacy review `validity="in_force"`.

The output field `parsing_approval_confers_legal_validity` is always `false`.

## 7. Legacy whole-stage review

Sealing still requires the explicit whole-stage `Review` in addition to the four category
decisions. This is a compatibility gate from Phase C.

Create a separate file (replace all placeholders):

```json
{
  "decision": "approved",
  "reviewer": "REPLACE: reviewer name",
  "reason": "REPLACE: whole-stage review result",
  "evidence_locator": "REPLACE: pages/paragraphs/URLs",
  "reviewed_at": "2026-10-26T09:00:00+07:00",
  "validity": "unknown",
  "effective_date": null,
  "expiry_date": null,
  "legal_change": "none",
  "provisions": {}
}
```

```bash
uv run --frozen python -m preprocess.offline_cli --workspace "$WORKSPACE" \
  review --stage "$R0_88" --decision <whole-stage-review.json>
```

For research-only use, `validity` may remain `unknown`. For a current-law release it must
be `in_force` with evidence.

## 8. Seal (only after every gate passes)

Sealing is an explicit publication-metadata action and still does **not** index or publish
to retrieval.

```bash
HF_HOME=data/model-cache uv run --frozen python -m preprocess.offline_cli \
  --workspace "$WORKSPACE" seal \
  --name phase-d2-r0-research-v1 \
  --stages "$R0_43" "$R0_88" \
  --purpose research \
  --cached-tokenizer --max-tokens 512 \
  --approve-publication
```

Rules enforced by `seal`:

- `--approve-publication` is mandatory.
- Synthetic and real stages cannot be mixed; synthetic purpose is separate.
- One staged version per canonical document.
- Quarantined or superseded stages are refused.
- Real releases require A/B/C approvals, a recorded non-rejected D, and the legacy
  whole-stage approval.
- Current-law additionally requires approved in-force D and legacy validity in-force.
- Real sealing requires the pinned tokenizer identity; the byte-budget fallback is not
  accepted.

## 9. Export (still not indexing)

```bash
HF_HOME=data/model-cache uv run --frozen python -m preprocess.offline_cli \
  --workspace "$WORKSPACE" export \
  --release <sealed-release-hash> \
  --destination <fresh-directory>
```

Use a fresh destination. Export writes bounded chunks, manifests, and checksums. It does
not call a model, generate neural vectors, index Qdrant, or publish retrieval.

## 10. Troubleshooting

| Symptom | Meaning | Action |
|---|---|---|
| `Superseded stage cannot be reviewed` | You selected an old reparse ancestor | Use the active stage from `review-list` |
| `Decision is bound to a different artifact` | Template belongs to another/changed artifact | Regenerate the packet and review again |
| `Replace template FILL: text` | Placeholder was not edited | Write a real reviewer/reason/evidence |
| `Category D cannot be approved while validity stays unknown` | Unverified validity | Record `pending` with evidence, or verify from an official source |
| `Quarantined extraction cannot be approved` | QA refused the extraction | Obtain a corrected/complete official rendition; ingest a new stage |
| `Missing explicit ... approval` at seal | A category decision is absent | Complete the packet review; do not bypass |
| Packet missing replica pages | Artifact changed since packet generation | Reparse/review the active stage and regenerate |

## 11. What remains prohibited

- Approving on behalf of someone else or self-certifying legal review without evidence.
- Bulk approval or any script that fabricates decisions.
- Editing stage JSON, review journals, or raw artifacts by hand.
- OCR or LLM reconstruction of missing legal text without explicit approval.
- Sealing a current-law release while validity is unknown.
- Qdrant indexing, retrieval publication, deployment, or pushing without a further
  explicit decision.
