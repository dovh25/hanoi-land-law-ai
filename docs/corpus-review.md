# Solo-operator corpus review and publication gates

> **Phase D.2 update:** the current per-document workflow uses four separate category
> decisions (A source identity, B extraction quality, C legal metadata, D applicability/
> validity) plus the legacy whole-stage review described below. Use
> [corpus-review-runbook.md](corpus-review-runbook.md) for the exact commands. The
> legacy `review` gate alone is not sufficient to seal a real Phase D.2 release.

Review extraction **and** legal evidence; neither a model nor a source URL proves
currency. No Gemini inference is used for legal status.

## State vocabulary

| State | Meaning |
|---|---|
| Draft / pending | Local raw source + parsed stage; not approved or canonical retrieval data. |
| Quarantined extraction | Parser detected unsupported/ambiguous material. Cannot approve; provide corrected rendition/new stage. |
| Reviewed | Latest append-only decision approved; still not exportable until explicitly sealed. |
| Rejected | Latest decision rejected; no sealing/export. Reasons remain in the journal. |
| Sealed | Immutable reviewed release + chunk/provenance manifest. Exportable, **not indexed**. |
| Indexed | Future separately approved local vector publication; not performed by these tools. |
| Published | Future explicit retrieval routing decision after QA; not implied by seal/import. |

Phase B's `CorpusRelease.published_at` means the one-way *metadata seal* in this
workflow. Phase C manifests explicitly keep `indexed=false`, `published=false`.

Review statuses are pending/approved/rejected; quarantine is an extraction state.
Legal validity separately supports unknown/in_force/partially_expired/expired/repealed/
suspended/not_yet_effective. `legal_change` records none/amended/superseded as a reviewed
note; it does not invent an amendment relationship or automatically rewrite other law.
Phase B `LegalRelationship` remains available for separately evidenced relationship
curation; automatic relationship resolution is not implemented.

## Checklist before approval

1. Compare raw bytes/file and recorded checksum; verify official identity/title/issuer.
2. Inspect all normalized text, not only article headings. Check paragraph order,
   tables, annexes, footnotes, page boundaries, clause/point numbering and source spans.
3. Confirm source URL/provenance and dates from evidence. Acquisition/verification dates
   are not legal effective dates. Unknown stays unknown until independently verified.
4. Review amendments, repeal/replacement, territorial scope and transitional provisions.
   A current-law release must not include unresolved legal applicability.
5. Inspect chunk context/spans and the intended research/current-law/synthetic purpose.

Create `review.json` (template below is **synthetic**, not an authoritative assertion):

```json
{
  "decision": "approved",
  "reviewer": "SYNTHETIC operator",
  "reason": "Compared entire synthetic extraction to fixture",
  "evidence_locator": "SYNTHETIC entire fixture",
  "reviewed_at": "2026-10-25T09:00:00+07:00",
  "validity": "unknown",
  "effective_date": null,
  "expiry_date": null,
  "legal_change": "none",
  "provisions": {}
}
```

```bash
uv run --frozen python -m preprocess.offline_cli --workspace data/offline-ingestion review --stage STAGE_ID --decision review.json
```

Non-unknown assertions require an explicit effective date; expiry is the first
non-applicable date. Partial validity requires per-locator assertions in `provisions`:
each value contains `validity`, `effective_date`, `expiry_date`. Use locators from the
stage, not guessed citations. Publication does not turn unknown legal status into current.

Review events are numbered, hash-linked and never overwritten. Repeating the exact
latest decision is idempotent. A subsequent rejection/correction leaves old release
history intact but blocks fresh exports of that stale release. Historical exports and
receipts remain evidence; there is no automatic deletion/revocation of a live index
because these tools never publish one. Future serving must enforce revocations/freshness.

To seal, pass `--approve-publication` deliberately. That flag authorizes only metadata
sealing, not public deployment or retrieval routing. Current-law releases also require
all included provision assertions current at the seal date, no amended/superseded note,
and the pinned tokenizer. Research purpose is never implicitly routed to current-law QA.
Freshness, transitional-case reasoning and actual legal review remain human obligations.
