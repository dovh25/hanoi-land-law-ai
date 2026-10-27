# Public MVP demo guide

> **M4 presentation snapshot.** The ON/model/daily-budget settings below record
> that validation stage, not current service configuration. The later
> [UI release](ui-redesign/implementation-summary.md#deployment-readiness) verified
> Gemini disabled. Use [current deployment guidance](deployment.md) and inspect
> metadata before presenting; no provider quota or current uptime is implied.

Validated 2026-10-27. Frontend: https://hanoi-land-law-ai.pages.dev
Backend: https://hanoi-land-law-ai-demo.onrender.com
Readiness: `/demo/readyz` (not the legacy `/readyz`).

## Before presenting

Open the frontend and wait for **2 văn bản / 90 trích đoạn**. Render Free may need
30–60 seconds to wake: this validation observed a 52.62-second first readiness
request, then a 0.22-second info request. Keep the tab open; try again if startup
fails. Do not repeatedly press Send. Limits: 6 questions/minute and 60/day/IP;
multiple people behind one network share the limit.

Gemini is configured ON (`gemini-3.5-flash-lite`). M4 made **zero live Gemini
calls**; it verified retrieval offline and generation/budget behavior with mocks.
Provider availability and free-tier quota are not guaranteed. A fallback response
with excerpts is valid demo behavior, not a generated legal answer.

## Five supported examples

These exact prompts were executed against the bundled corpus with generation off;
all retrieved sources. This is a prompt smoke check, not a QA benchmark.

| Question | Expected evidence |
| --- | --- |
| Khi Nhà nước thu hồi đất ở, hộ gia đình được bồi thường những gì? | NĐ 88/2024, including Điều 11; up to 6 retrieved excerpts |
| Điều 5 Nghị định 88/2024/NĐ-CP quy định gì? | Điều 5; 2 retrieved excerpts |
| Điều 11 Nghị định 88/2024/NĐ-CP quy định gì? | Điều 11; 2 retrieved excerpts |
| Điều 19 Nghị định 88/2024/NĐ-CP quy định gì? | Điều 19; 3 retrieved excerpts |
| Điều 30 Nghị định 88/2024/NĐ-CP quy định gì? | Điều 30; 1 retrieved excerpt |

For a live generated answer, cited-source counts can differ from retrieval counts.
Click a gold E# chip to jump to its source card, then “Nguồn chính thức” to open
the government portal. Check article, excerpt, and **Hiệu lực: chưa xác minh**.
Citation validation checks IDs, quotations, dates and article references; it does
not certify that every generated claim is legally correct.

## Three out-of-scope examples

All three returned `abstained`, no sources and `llm_used=false` on the public API:

- Quy hoạch sử dụng đất cấp huyện được lập thế nào?
- Thuế thu nhập cá nhân khi bán nhà được tính thế nào?
- Thủ tục ly hôn cần giấy tờ gì?

Use “Xin chào” for a deterministic greeting without a model call.

## Limits, privacy and disclaimer

Only **43/2024/QH15 (7 chunks)** and **88/2024/NĐ-CP (83 chunks)** are bundled.
This is **not all Hanoi land law**. Annexes of NĐ 88 are excluded. Documents
31/2024/QH15, 101/2024, 102/2024 and 133/VBHN are excluded because complete,
ordered operative renditions were not verified. Review is technical only;
current legal validity is unknown. Some broad prompts, including the existing
suggestion “Luật 43/2024/QH15 sửa đổi những nội dung gì?”, conservatively abstain.

Anonymous conversations are request-local and not saved as chat sessions. Recent
turns are sent with each request. In-scope generation sends prompt/context to
Google; do not enter personal, client or confidential case information. Hosting
providers may retain operational metadata; “no saved chat” is not “no third-party
processing”. Reload clears the browser conversation. Authenticated pages are a
separate feature with ownership checks.

The model ledger permits at most 50 attempted calls/day on the current instance,
1/turn, no retries, 20-second timeout, 1,024 output tokens. The SQLite ledger and
IP counters reset on Render restart/redeploy. This is not a permanent global
quota or a provider-side billing guarantee. Suitable for a supervised demo, not
an unlimited unattended public launch. No paid resources were enabled by M4.

**Đây là bản demo nghiên cứu. Hiệu lực hiện hành của các văn bản chưa được xác
minh; không dùng nội dung này làm tư vấn pháp lý. Hãy đối chiếu nguồn chính thức
và tham khảo người có chuyên môn trước khi quyết định.**
