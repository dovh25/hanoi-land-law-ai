# Phase D — controlled corpus acquisition

> **Phase D evidence snapshot.** Acquisition counts describe this phase only.
> See the [current bundled corpus](corpus.md); later D.1/D.2 acquisition and review
> evidence remains separate from runtime legal-validity claims.

## Outcome

> **Phase D.1 update:** 8 instruments / 16 official PDFs were subsequently acquired from
> the official gazette file CDN `congbaocdn.chinhphu.vn` (robots.txt absent, HTTP 404;
> files linked from `congbao.chinhphu.vn` pages whose robots is `Allow: /`). The policy is
> `corpus/phase-d1-source-approvals.json`; results and counts are in
> [phase-d1-validation.md](phase-d1-validation.md). The Phase D outcome below is preserved
> as the historical record for the original attachment hosts.

**0 of the requested maximum 40 instruments were downloaded.** That is the correct
policy outcome, not a silent failure: every official metadata page exposed its full-text
attachment on a host whose `robots.txt` returned HTTP 403, or on a source whose document
access is ambiguous. No access control, CAPTCHA, login, rate limit, or anti-bot control
was bypassed. No proxy rotation or stealth automation was used.

The pilot still produced an evidence-bound **18-candidate registry** (12 national,
6 Hanoi) and an 18-item manual download/review queue. Candidate metadata is not corpus
membership; no document is represented as acquired or reviewed.

## Policy and request controls

Implemented in `law_crawler/pilot.py` and exercised by `tests/test_pilot.py`:

- HTTPS only; exact reviewed host allowlist; no credentials, fragments, dot segments,
  non-standard ports, backslashes, or control characters.
- `robots.txt` fetched before discovery/download. Longest matching path wins; `Allow`
  wins ties. Unavailable or disallowing robots means stop.
- One request at a time across the pilot; at least 3 seconds between requests per host,
  increased to 5 seconds where the source publishes `Crawl-delay: 5`.
- At most three retries for transient network/5xx/408/429 responses. `Retry-After` is
  honoured. A `Retry-After` over 300 seconds stops the interactive pilot.
- **Any** 401/403/429 stops that host immediately and persists the stop across process
  restarts. Repeated 403/429 was not needed to trigger the stop.
- Redirect destinations are validated before connecting. A redirect to an unregistered
  host is not followed. Redirect loops and overlong chains stop.
- A 200 page containing a CAPTCHA/challenge marker is classified
  `access_control_detected`; the host is stopped.
- Every request/response is journaled with URL, host, status, selected HTTP metadata,
  retrieval timestamp, SHA-256, byte count, purpose, and content-addressed evidence path.
  Cookies and authorization headers are not persisted.
- Document downloads additionally require a source-level
  `decision=approved_public_download`, a permission evidence field, and the exact URL in
  `approved_urls`. No source reached that state in this pilot.
- The 40-instrument cap is enforced with a persistent reservation ledger before any
  document request. A partial/corrupt run cannot silently exceed the cap.

The source decisions and exact evidence are in `docs/corpus-sources.md` and
`corpus/source-approvals.json`.

## What was accessed

Only ordinary public metadata/policy pages were fetched:

- `robots.txt` for `vbpl.vn`, `vanban.chinhphu.vn`, `hanoi.gov.vn`,
  `congbao.hanoi.gov.vn`, `vanban.hanoi.gov.vn`, `datafiles.chinhphu.vn`,
  `datafiles.hanoi.gov.vn`, and `storage-vnportal.vnpt.vn`.
- Homepages for the four requested portals and the newly reached official Hanoi
  document subdomain (5 pages).
- 18 targeted official metadata pages, plus two additional metadata probes: the
  `congbao.hanoi.gov.vn` page that redirected to `vanban.hanoi.gov.vn`, and one gazette
  contents page used to inspect the issue. No search-result pagination, sitemap crawl, or
  exhaustive listing was performed.
- One observed redirect (`congbao.hanoi.gov.vn` → `vanban.hanoi.gov.vn`). The destination
  was policy-checked before it was fetched. No redirect to an attachment host was followed,
  because those hosts' policies were blocked.

No attachment/PDF URL was requested. The network journal contains the evidence, including
the 403 robots responses and the `vbpl.vn` ambiguity.

## Why the full text was not acquired

| Host examined | Observed policy | Action |
|---|---|---|
| `datafiles.chinhphu.vn` | `robots.txt` HTTP 403 | Stopped; no PDF request (15 declared attachment URLs) |
| `datafiles.hanoi.gov.vn` | `robots.txt` HTTP 403 | Stopped; no PDF request (3 declared attachment URLs) |
| `storage-vnportal.vnpt.vn` | `robots.txt` HTTP 403 | Stopped; no PDF request (3 declared attachment URLs) |
| `vbpl.vn` | robots allows `/` but disallows `/api/` and `/Pages/`; document access tied to reCAPTCHA | No document request; source approval required (no candidate attachment used this host) |
| `congbao.hanoi.gov.vn` / `vanban.hanoi.gov.vn` | robots allows HTML, but attachments are on the blocked hosts above | Metadata discovery only |

The metadata pages do not contain the legal full text. `vanban.chinhphu.vn` and
`congbao.hanoi.gov.vn` render bibliographic data; `vanban.hanoi.gov.vn` renders
bibliographic data and links the attachment. Treating those pages as legal text would
be a false acquisition.

## Reproduce the registry (offline after evidence exists)

```bash
uv run --frozen python -m law_crawler.pilot_cli discover \
  --network --seeds corpus/pilot-seeds.json \
  --network-root data/phase-d-network \
  --destination corpus/phase-d-candidates.json
```

`--network` is required by the CLI. It performs discovery/policy requests only when the
exact page is not already cached in the journal. It never follows attachment links.
Existing candidate registries are immutable outputs; use a new destination or preserve
the prior revision in `corpus/discovery-history/`.

Policy inspection is intentionally separate from document download. The CLI's
`acquire` command refuses every candidate unless all of its attachment hosts have an
explicit approved policy and every exact URL is individually approved. In this pilot
that condition is false, so the command would report `blocked_policy` without a request.

## Manual download and ingestion

Use a normal browser, not automation, only after you have decided the source policy
permits your access. Do not bypass a 403, CAPTCHA, login, or rate limit. If a portal
requires a manual browser session, that is a manual action, not an automation target.

For each instrument in:

`data/phase-d-corpus-v2/reports/manual-review-queue.json`

the queue gives:

- official number and identifier;
- official metadata/source page;
- declared attachment URL(s);
- destination folder under `data/phase-d-corpus-v2/manual-inbox/<digest>/`;
- state `pending_manual_download_and_legal_review`.

Procedure:

1. Open the official source page in a browser and confirm the document number, title,
   issuer, type, and every attachment/annex. Do not rely on a search-result snippet.
2. Download the original file(s) without renaming away the original identity. Save them
   in the queue's destination folder. If the browser supplies a name such as
   `file (1).pdf`, deliberately rename it to the original published filename and record
   that fact.
3. Replace `REPLACE_WITH_ORIGINAL_FILENAME.pdf` in
   `acquisition.template.json` with the actual local filename. Fill `acquired_at` with a
   timezone-aware retrieval timestamp. Keep `is_synthetic=false`. Do **not** guess
   missing dates or authority fields. Set `source_url` to the official metadata page,
   not to a transient attachment-storage URL.
4. Preserve the download; never move it over an existing different artifact. The
   ingestion pipeline is content-addressed and refuses conflicting bytes.
5. Ingest and inspect the stage:

```bash
uv run --frozen python -m preprocess.offline_cli \
  --workspace data/phase-d-corpus-v2 ingest \
  --manifest data/phase-d-corpus-v2/manual-inbox/<digest>/acquisition.template.json
```

6. Follow `docs/corpus-review.md`. Review is not implied by download or parsing.
7. Only after legal review may a release be considered. Sealing additionally requires
   the pinned cached tokenizer and explicit publication approval; it still does not
   index Qdrant or publish retrieval.

If a manually downloaded file is a scanned/image-only PDF, the current parser will
quarantine it (OCR is unsupported). Supply a reviewed text/HTML rendition or defer it
to a separately approved OCR workflow. Do not invent missing text with an LLM.

## Exact paths and preservation

- Original evidence and journal: `data/phase-d-network/`
- Candidate registry: `corpus/phase-d-candidates.json`
- Source policy registry: `corpus/source-approvals.json`
- Preserved earlier discovery revision: `corpus/discovery-history/`
- Isolated workspace: `data/phase-d-corpus-v2/`
- Draft release manifest: `data/phase-d-corpus-v2/reports/draft-release.json`
- Quality report: `data/phase-d-corpus-v2/reports/corpus-quality.json`
- Manual queue: `data/phase-d-corpus-v2/reports/manual-review-queue.json`
- Manual inbox: `data/phase-d-corpus-v2/manual-inbox/`

The earlier `data/phase-d-corpus/` draft is preserved. It covered 14 metadata candidates
and was superseded by the 18-candidate registry. Neither draft is sealed or published.

## Approval still required

1. **Automated attachment download approval** for any of
   `datafiles.chinhphu.vn`, `datafiles.hanoi.gov.vn`, or
   `storage-vnportal.vnpt.vn` (all returned robots 403), or for `vbpl.vn`
   (ambiguous/reCAPTCHA document access).
2. **Manual download** of the desired instruments if you prefer not to approve
   automation.
3. **Legal review** by a qualified human, including validity, amendment/repeal,
   territorial scope, transitional provisions, and annex completeness.
4. **Cached tokenizer provisioning** before a real release can be sealed.
5. **Real neural embedding execution** only in a later approved phase.

No paid API, Gemini request, model-weight download, GPU job, Qdrant connection, or
production deployment was performed.
