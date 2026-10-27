# Phase D — authoritative Vietnamese land-law sources

> **Source-discovery evidence snapshot.** Access/status findings apply to the
> recorded discovery phase; do not treat them as new online checks. See
> [current bundled sources](corpus.md) and preserve all acquisition approvals.

## Status

> **Phase D.1 update:** the acquisition blocker below was resolved by an alternate
> official representation. Eight instruments (16 official PDF originals) were acquired
> from the official gazette file CDN `congbaocdn.chinhphu.vn`; see
> [phase-d1-validation.md](phase-d1-validation.md) and
> `corpus/phase-d1-instruments.json`. The Phase D registries on this page are preserved
> unchanged. All acquired documents remain `legal_validity=unknown`.

**Source discovery and policy verification only. No legal instrument was acquired in
Phase D.** The registry below records official metadata pages and their declared
attachment links. A metadata page is not full text, and a declared effective date is
not a verified current-validity determination.

- Candidate registry: `corpus/phase-d-candidates.json`
- Candidate registry SHA-256: `44fd41d45642067452c6547571cb22e0506ff6bb9c1d509038c277798a17befa`
- Source approval registry: `corpus/source-approvals.json`
- Source approval registry SHA-256: `8964c6d31b654a6d1706b845374bf54797089d5d20fdfd05aafdf4d29ded7a5a`
- Seed list SHA-256: `e2ea70e0489dcad65400d2e34e225920f2748c0d40c1ac1af5722bcb035623e5`
- Discovery/network evidence: `data/phase-d-network/http-journal.jsonl`
- Evidence journal SHA-256: `b73b58365dc8450b4b01d408d1f3cb79ce2cb611a8bf0ece09e78a0dc513135c`

The registry is deliberately **not** a list of acquired corpus members. No candidate is
marked `full_text_acquired=true`, reviewed, valid, sealed, or indexed.

## Official sources and access policy

The four requested portals were inspected, together with the official document
subdomain and attachment hosts reached from their metadata pages.

| Host | robots.txt | Discovery decision | Document decision | Constraint |
|---|---|---|---|---|
| `congbao.hanoi.gov.vn` | HTTP 200; `User-agent: * / Crawl-delay: 5 / Allow: /` | `discovery_only` | `blocked_pending_explicit_source_approval` | Metadata/HTML discovery only under robots.txt; document endpoints require explicit source approval; linked attachment hosts are blocked |
| `datafiles.chinhphu.vn` | HTTP 403; not available | `blocked_http_403` | `blocked_attachment_host_http_403` | Stop: robots.txt returned HTTP 403; no document request attempted; manual download or explicit source approval required |
| `datafiles.hanoi.gov.vn` | HTTP 403; not available | `blocked_http_403` | `blocked_attachment_host_http_403` | Stop: robots.txt returned HTTP 403; no document request attempted; manual download or explicit source approval required |
| `hanoi.gov.vn` | HTTP 200; `User-agent: * / Crawl-delay: 5 / Allow: /` | `discovery_only` | `blocked_pending_explicit_source_approval` | Metadata/HTML discovery only under robots.txt; document endpoints require explicit source approval; linked attachment hosts are blocked |
| `storage-vnportal.vnpt.vn` | HTTP 403; not available | `blocked_http_403` | `blocked_attachment_host_http_403` | Stop: robots.txt returned HTTP 403; no document request attempted; manual download or explicit source approval required |
| `vanban.chinhphu.vn` | HTTP 200; `User-agent: * / Allow: /` | `discovery_only` | `blocked_pending_explicit_source_approval` | Metadata/HTML discovery only under robots.txt; document endpoints require explicit source approval; linked attachment hosts are blocked |
| `vanban.hanoi.gov.vn` | HTTP 200; `User-agent: * / Crawl-delay: 5 / Allow: /` | `discovery_only` | `blocked_pending_explicit_source_approval` | Metadata/HTML discovery only under robots.txt; document endpoints require explicit source approval; linked attachment hosts are blocked |
| `vbpl.vn` | HTTP 200; `User-Agent: * / Allow: / / Disallow: /api/ / Disallow: /Pages/` | `blocked_ambiguous_access_controls` | `blocked_ambiguous_or_recaptcha` | No CAPTCHA challenge was served to this client, but document access is tied to reCAPTCHA and robots.txt disallows `/api/` and `/Pages/`; no document request attempted |

`storage-vnportal.vnpt.vn` is attachment storage linked from official Hanoi metadata
pages, not an official portal. Its access policy is not established by the link alone.
The robots 403 is treated as a stop, not as permission to probe attachment URLs.

The public attribution notices on the portals ("Ghi rõ nguồn ... khi phát hành lại")
are recorded as attribution obligations. They are **not** interpreted as a blanket
automation, bulk-download, or data-relicensing permission.

## Candidate registry

All 18 candidates came from official metadata pages. Effective dates below are
**claims published on the official page**, not independently verified applicability.
Publication dates were not exposed on these pages and remain unknown. Legal validity is
unknown for every candidate. `QĐ-UBND` / `NĐ-CP` / `QH15` numbers are reproduced as the
official pages display them.

| # | Number | Title (official trích yếu) | Type | Issuer | Jurisdiction | Issued | Effective claim | Topics | Source page | Attachments |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 31/2024/QH15 | Luật Đất đai | Luật | Quốc hội | VN | 2024-01-18 | 2025-01-01 | land_law | https://vanban.chinhphu.vn/?pageid=27160&docid=211189 | 3 |
| 2 | 43/2024/QH15 | Luật sửa đổi, bổ sung một số điều của Luật Đất đai số 31/2024/QH15, Luật Nhà ở số 27/2023/QH15, Luật Kinh doanh bất động sản số 29/2023/QH15 và Luật Các tổ chức tín dụng số 32/2024/QH15 | Luật | Quốc hội | VN | 2024-06-29 | 2024-08-01 | land_law, amendments | https://vanban.chinhphu.vn/?pageid=27160&docid=211201 | 1 |
| 3 | 88/2024/NĐ-CP | Quy định về bồi thường, hỗ trợ, tái định cư khi Nhà nước thu hồi đất | Nghị định | Chính phủ | VN | 2024-07-15 | 2024-08-01 | land_recovery, compensation, support, resettlement | https://vanban.chinhphu.vn/?pageid=27160&docid=210658 | 1 |
| 4 | 102/2024/NĐ-CP | Quy định chi tiết thi hành một số điều của Luật Đất đai | Nghị định | Chính phủ | VN | 2024-07-30 | 2024-08-01 | land_law, implementation | https://vanban.chinhphu.vn/?pageid=27160&docid=210795 | 2 |
| 5 | 71/2024/NĐ-CP | Quy định về giá đất | Nghị định | Chính phủ | VN | 2024-06-27 | unknown | land_prices, compensation | https://vanban.chinhphu.vn/?pageid=27160&docid=210523 | 1 |
| 6 | 101/2024/NĐ-CP | Quy định về điều tra cơ bản đất đai; đăng ký, cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất và Hệ thống thông tin đất đai | Nghị định | Chính phủ | VN | 2024-07-29 | 2024-08-01 | registration, land_information | https://vanban.chinhphu.vn/?pageid=27160&docid=210791 | 1 |
| 7 | 103/2024/NĐ-CP | Quy định về tiền sử dụng đất, tiền thuê đất | Nghị định | Chính phủ | VN | 2024-07-30 | 2024-08-01 | land_use_fees, land_rent | https://vanban.chinhphu.vn/?pageid=27160&docid=210797 | 1 |
| 8 | 151/2025/NĐ-CP | Quy định về phân định thẩm quyền của chính quyền địa phương 02 cấp, phân quyền, phân cấp trong lĩnh vực đất đai | Nghị định | Chính phủ | VN | 2025-06-12 | 2025-07-01 | implementation, administrative_applicability | https://vanban.chinhphu.vn/?pageid=27160&docid=213927 | 1 |
| 9 | 226/2025/NĐ-CP | Sửa đổi, bổ sung một số điều của các nghị định quy định chi tiết thi hành Luật Đất đai | Nghị định | Chính phủ | VN | 2025-08-15 | 2025-08-15 | amendments, implementation | https://vanban.chinhphu.vn/?pageid=27160&docid=214955 | 1 |
| 10 | 291/2025/NĐ-CP | Sửa đổi, bổ sung một số điều của Nghị định số 103/2024/NĐ-CP ngày 30 tháng 7 năm 2024 của Chính phủ quy định về tiền sử dụng đất, tiền thuê đất | Nghị định | Chính phủ | VN | 2025-11-06 | 2025-11-06 | amendments, land_use_fees | https://vanban.chinhphu.vn/?pageid=27160&docid=215808 | 1 |
| 11 | 49/2026/NĐ-CP | Quy định chi tiết và hướng dẫn một số điều của Nghị quyết số 254/2025/QH15 của Quốc hội quy định một số cơ chế, chính sách đặc thù | Nghị định | Chính phủ | VN | 2026-01-31 | 2026-01-31 | land_law, implementation | https://vanban.chinhphu.vn/?pageid=27160&docid=216860 | 1 |
| 12 | 50/2026/NĐ-CP | Quy định chi tiết một số điều của Nghị quyết số 254/2025/QH15 ngày 11 tháng 12 năm 2025 của Quốc hội quy định một số cơ chế, chính sách đặc thù | Nghị định | Chính phủ | VN | 2026-01-31 | 2026-01-31 | land_use_fees, land_rent | https://vanban.chinhphu.vn/?pageid=27160&docid=216861 | 1 |
| 13 | 10/2026/QĐ-UBND | Về việc sửa đổi, bổ sung một số điều của Quyết định số 56/2024/QĐ-UBND ngày 06/9/2024 của UBND Thành phố quy định một số nội dung về bồi thường, hỗ trợ và tái định cư khi Nhà nước thu hồi đất trên địa bàn Thành phố | Quyết định | UBND Thành phố Hà Nội | VN-HN | 2026-01-18 | 2026-01-18 | hanoi_implementation, amendments, compensation, support, resettlement | https://congbao.hanoi.gov.vn/Default.aspx?pageid=45002&p_attribute=5204 | 1 |
| 14 | 566/QĐ-UBND | Về việc đính chính Quyết định số 10/2026/QĐ-UBND ngày 18/01/2026 của UBND Thành phố về việc sửa đổi, bổ sung một số điều của Quyết định số 56/2024/QĐ-UBND | Quyết định | UBND Thành phố Hà Nội | VN-HN | 2026-02-05 | 2026-02-05 | hanoi_implementation, corrections, compensation | https://congbao.hanoi.gov.vn/Default.aspx?pageid=45002&p_attribute=5255 | 1 |
| 15 | 40/2026/QĐ-UBND | Về việc ban hành Quy định một số nội dung về bồi thường, hỗ trợ, tái định cư khi Nhà nước thu hồi đất trên địa bàn thành phố Hà Nội | Quyết định | UBND Thành phố Hà Nội | VN-HN | 2026-04-02 | 2026-04-02 | hanoi_implementation, land_recovery, compensation, support, resettlement | https://vanban.hanoi.gov.vn/chi-tiet-van-ban/ve-viec-ban-hanh-quy-dinh-mot-so-noi-dung-ve-boi-thuong-ho-tro-tai-dinh-cu-khi-nha-nuoc-thu-hoi-dat-238352 | 1 |
| 16 | 56/2024/QĐ-UBND | Về việc ban hành Quy định một số nội dung về bồi thường, hỗ trợ, tái định cư khi Nhà nước thu hồi đất trên địa bàn thành phố Hà Nội | Quyết định | UBND Thành phố Hà Nội | VN-HN | 2024-09-06 | 2024-09-20 | hanoi_implementation, land_recovery, compensation, support, resettlement | https://vanban.hanoi.gov.vn/van-ban/ve-viec-ban-hanh-quy-dinh-mot-so-noi-dung-ve-boi-thuong-ho-tro-tai-dinh-cu-khi-nha-nuoc-thu-hoi--210964 | 1 |
| 17 | 38/2025/QĐ-UBND | Về việc sửa đổi, bổ sung một số điều của Quy định ban hành kèm theo Quyết định số 56/2024/QĐ-UBND ngày 06/9/2024 của UBND Thành phố quy định một số nội dung về bồi thường, hỗ trợ và tái định cư khi Nhà nước thu hồi đất trên địa bàn thành phố Hà Nội | Quyết định | UBND Thành phố Hà Nội | VN-HN | 2025-06-30 | 2025-07-01 | hanoi_implementation, amendments, compensation, support, resettlement | https://vanban.hanoi.gov.vn/chi-tiet-van-ban/ve-viec-sua-doi-bo-sung-mot-so-dieu-cua-quy-dinh-ban-hanh-kem-theo-quyet-dinh-so-56-2024-qd-ubnd-221034 | 1 |
| 18 | 29/QĐ-UBND | Về việc phê duyệt Kế hoạch sử dụng đất năm 2025 quận Hai Bà Trưng | Quyết định | UBND Thành phố Hà Nội | VN-HN | 2025-01-05 | 2025-01-05 | hanoi_implementation, land_use_planning | https://vanban.hanoi.gov.vn/chi-tiet-van-ban/ve-viec-phe-duyet-ke-hoach-su-dung-dat-nam-2025-quan-hai-ba-trung-217938 | 1 |

### Issuer evidence note

`vanban.hanoi.gov.vn` pages do not repeat a separate "Cơ quan ban hành" row. For six
Hanoi `QĐ-UBND` candidates, the issuer was taken from the official page masthead
("ỦY BAN NHÂN DÂN THÀNH PHỐ HÀ NỘI") plus the `QĐ-UBND` number suffix. This is recorded
as `issuing_authority_evidence` and remains **pending human confirmation**. It is not a
silent inference that the document is currently in force.

## Relationships and gaps

The registry contains **14 unverified relationship claims** derived only from document
titles and the official "Văn bản liên quan" row. They include amendment/correction
mentions such as:

- `43/2024/QH15` mentions `31/2024/QH15` and other laws.
- `291/2025/NĐ-CP` mentions `103/2024/NĐ-CP`.
- `10/2026/QĐ-UBND`, `566/QĐ-UBND`, `40/2026/QĐ-UBND`, and `38/2025/QĐ-UBND`
  reference `56/2024/QĐ-UBND` and/or each other.

None of these claims establishes amendment scope, repeal, replacement, transitional
effect, or current validity. Relationship review is pending.

Unresolved metadata and coverage gaps:

- Publication dates: **0/18** exposed on the inspected metadata pages.
- Effective dates: **17/18** have a published claim; `71/2024/NĐ-CP` has none.
- Legal validity: **unknown 18/18**.
- Expiry/replacement: **unknown 18/18**.
- Full text/annexes: **0/18 acquired**.
- Document-level duplicate detection: not possible without full text; one raw-byte
  duplicate counter is implemented for acquired artifacts only.
- Territorial scope: recorded as a pending claim, not verified operative scope.
- Hanoi land-use planning coverage is thin: one district-level plan lead
  (`29/QĐ-UBND`) and one official news lead for Tây Hồ that is not a legal instrument.

## Manual leads

The `hanoi.gov.vn` news article about the Tây Hồ 2025 land-use plan is retained only as
an unresolved lead in `corpus/pilot-seeds.json`:

`https://hanoi.gov.vn/chi-dao-cua-ubnd-thanh-pho-ha-noi/phe-duyet-ke-hoach-su-dung-dat-nam-2025-quan-tay-ho-4250109100611519.htm`

It is a news report, not the instrument or its annexes. Do not ingest it as a legal
document without locating the official decision and attachments.
