# Phase D — corpus inventory

> **Phase D inventory snapshot.** These are discovery-stage counts, not the
> current runtime corpus. See [bundled corpus scope and statistics](corpus.md).

## Executive inventory

| Measure | Count | Meaning |
|---|---:|---|
| Candidate metadata pages discovered | **18** | Official pages; not acquired legal text |
| National candidates (`VN`) | **12** | Law, decrees from national portals |
| Hanoi candidates (`VN-HN`) | **6** | Hanoi People's Committee and gazette pages |
| Full-text instruments acquired | **0** | No attachment downloaded |
| Raw artifacts preserved | **0** | No acquisition receipts |
| Parsed instruments | **0** | No stage exists for real documents |
| Quarantined real instruments | **0** | No real extraction attempted |
| Duplicate real artifacts | **0** | Deduplication not applicable to zero artifacts |
| Human-reviewed documents | **0** | No legal review approval |
| Sealed releases | **0** | Draft only |
| Canonical document rows | **0** | Isolated DB contains no document |
| Provision rows | **0** | No legal hierarchy persisted |
| Chunks | **0** | No export/sealing |
| Embeddings | **0** | Explicitly out of Phase D scope |
| Indexed/published | **0** | No Qdrant or retrieval action |

The draft release `phase-d-authoritative-pilot-draft-v2` exists in the isolated
workspace `data/phase-d-corpus-v2/`. Its `published_at` and `manifest_sha256` are
`null`; `legal_documents`, `document_versions`, `legal_provisions`,
`provision_versions`, and `source_artifacts` all contain **0 rows**. The release has no
members and must not be described as a corpus release.

## Discovery inventory

Full titles, official source URLs, topics, attachment counts, and policy notes are in
`docs/corpus-sources.md`. This table is the reviewable identity/status inventory.

| # | Official number | Jurisdiction | Issuer | Issued | Effective claim | Attachment host | State | Review |
|---|---|---|---|---|---|---|---|---|
| 1 | 31/2024/QH15 | VN | Quốc hội | 2024-01-18 | 2025-01-01 | datafiles.chinhphu.vn | discovered | pending |
| 2 | 43/2024/QH15 | VN | Quốc hội | 2024-06-29 | 2024-08-01 | datafiles.chinhphu.vn | discovered | pending |
| 3 | 88/2024/NĐ-CP | VN | Chính phủ | 2024-07-15 | 2024-08-01 | datafiles.chinhphu.vn | discovered | pending |
| 4 | 102/2024/NĐ-CP | VN | Chính phủ | 2024-07-30 | 2024-08-01 | datafiles.chinhphu.vn | discovered | pending |
| 5 | 71/2024/NĐ-CP | VN | Chính phủ | 2024-06-27 | unknown | datafiles.chinhphu.vn | discovered | pending |
| 6 | 101/2024/NĐ-CP | VN | Chính phủ | 2024-07-29 | 2024-08-01 | datafiles.chinhphu.vn | discovered | pending |
| 7 | 103/2024/NĐ-CP | VN | Chính phủ | 2024-07-30 | 2024-08-01 | datafiles.chinhphu.vn | discovered | pending |
| 8 | 151/2025/NĐ-CP | VN | Chính phủ | 2025-06-12 | 2025-07-01 | datafiles.chinhphu.vn | discovered | pending |
| 9 | 226/2025/NĐ-CP | VN | Chính phủ | 2025-08-15 | 2025-08-15 | datafiles.chinhphu.vn | discovered | pending |
| 10 | 291/2025/NĐ-CP | VN | Chính phủ | 2025-11-06 | 2025-11-06 | datafiles.chinhphu.vn | discovered | pending |
| 11 | 49/2026/NĐ-CP | VN | Chính phủ | 2026-01-31 | 2026-01-31 | datafiles.chinhphu.vn | discovered | pending |
| 12 | 50/2026/NĐ-CP | VN | Chính phủ | 2026-01-31 | 2026-01-31 | datafiles.chinhphu.vn | discovered | pending |
| 13 | 10/2026/QĐ-UBND | VN-HN | UBND Thành phố Hà Nội | 2026-01-18 | 2026-01-18 | datafiles.hanoi.gov.vn | discovered | pending |
| 14 | 566/QĐ-UBND | VN-HN | UBND Thành phố Hà Nội | 2026-02-05 | 2026-02-05 | datafiles.hanoi.gov.vn | discovered | pending |
| 15 | 40/2026/QĐ-UBND | VN-HN | UBND Thành phố Hà Nội | 2026-04-02 | 2026-04-02 | datafiles.hanoi.gov.vn | discovered | pending |
| 16 | 56/2024/QĐ-UBND | VN-HN | UBND Thành phố Hà Nội | 2024-09-06 | 2024-09-20 | storage-vnportal.vnpt.vn | discovered | pending |
| 17 | 38/2025/QĐ-UBND | VN-HN | UBND Thành phố Hà Nội | 2025-06-30 | 2025-07-01 | storage-vnportal.vnpt.vn | discovered | pending |
| 18 | 29/QĐ-UBND | VN-HN | UBND Thành phố Hà Nội | 2025-01-05 | 2025-01-05 | storage-vnportal.vnpt.vn | discovered | pending |

`Effective claim` is the date printed on the official metadata page. It is not a
validity determination and does not account for amendments, repeals, suspensions,
transitional provisions, or later documents. `State=discovered` means metadata only.

## Topic coverage

Counts describe **candidate relevance classification**, not validated full-text
coverage. A document can have several topics.

| Topic | Candidates |
|---|---:|
| compensation | 7 |
| hanoi_implementation | 6 |
| amendments | 5 |
| resettlement | 5 |
| support | 5 |
| land_law | 4 |
| implementation | 4 |
| land_recovery | 3 |
| land_use_fees | 3 |
| land_rent | 2 |
| land_information | 1 |
| land_prices | 1 |
| land_use_planning | 1 |
| registration | 1 |
| administrative_applicability | 1 |
| corrections | 1 |

There is no validated coverage percentage because no full text was acquired. In
particular, the requested land-use planning category has only one district-level lead
(`29/QĐ-UBND`) and is not adequately represented for a Hanoi land-law assistant.

## Metadata and provenance completeness

| Field | Present/verified | Note |
|---|---:|---|
| Official number | 18/18 | Extracted from official metadata table |
| Official title/trích yếu | 18/18 | Official page text |
| Document type | 18/18 | Official page text |
| Issuing authority | 18/18 | 12 direct rows; 6 Hanoi masthead + number suffix, pending confirmation |
| Issuance date | 18/18 | Official page text |
| Effective date | 17/18 claims | `71/2024/NĐ-CP` unknown; claims unverified |
| Publication date | 0/18 | Not exposed on inspected pages |
| Expiry/replacement | 0/18 | Unknown |
| Legal validity | 0/18 verified | All 18 explicitly unknown |
| Source page URL | 18/18 | Official metadata page |
| Discovery timestamp | 18/18 | In candidate registry |
| Discovery evidence SHA-256 | 18/18 | Content-addressed evidence |
| Declared attachment URL | 18/18 | Metadata-level link; none fetched |
| Full-text acquisition | 0/18 | Blocked/awaiting approval |
| Human legal review | 0/18 | Pending |
| Release membership | 0/18 | Draft is empty |

## Review queue and manual inbox

`data/phase-d-corpus-v2/reports/manual-review-queue.json` contains 18 entries. Each has
an exact destination directory under
`data/phase-d-corpus-v2/manual-inbox/<official-identifier-sha256>/` with an
`acquisition.template.json` that deliberately says
`REPLACE_WITH_ORIGINAL_FILENAME.pdf` and `acquired_at: null`. It is not ingestible until
an operator supplies the real filename, timestamp, and downloaded original.

`data/phase-d-corpus-v2/reports/draft-release.json` records:

- candidate registry SHA-256 `44fd41d45642067452c6547571cb22e0506ff6bb9c1d509038c277798a17befa`;
- policy registry SHA-256 `8964c6d31b654a6d1706b845374bf54797089d5d20fdfd05aafdf4d29ded7a5a`;
- `automated_downloads=0`, `manual_queue_count=18`, `legal_review_approvals=0`;
- empty `document_versions`, `provision_versions`, and `chunks`;
- `sealed=false`, `indexed=false`, `published=false`, `approved_publication=false`.

## Inventory limitations

- Metadata pages can change. The registry records the retrieval timestamp and evidence
  hash; it does not freeze the live portal.
- A declared title/number is not a check of the actual attachment bytes. No attachment
  was opened.
- No real duplicate detection, hierarchy extraction, article/clause/point count, table
  extraction, or annex completeness check has been performed. Those metrics remain
  unavailable rather than guessed.
- The 14 relationship claims are title/related-row observations. They are not reviewed
  amendment/repeal relationships.
