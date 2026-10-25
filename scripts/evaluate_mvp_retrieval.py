"""Offline benchmark for the MVP demo retrieval and abstention policy.

Run from the repository root:

    uv run --frozen python scripts/evaluate_mvp_retrieval.py

The question set is a deterministic demo benchmark, not a legal-accuracy evaluation.
It reports article-level retrieval hit rate and abstention decisions only.
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from backend.services.mvp_corpus import MvpCorpusIndex

ROOT = Path(__file__).resolve().parents[1]

# (question, expected document, expected article, should_answer)
QUESTIONS = [
    ("Bồi thường khi Nhà nước thu hồi đất ở là gì?", "88/2024/NĐ-CP", "Điều 11", True),
    ("Điều kiện được bồi thường về đất khi Nhà nước thu hồi đất?", "88/2024/NĐ-CP", "Điều 11", True),
    ("Hồ sơ, trình tự bồi thường, hỗ trợ, tái định cư?", "88/2024/NĐ-CP", "Điều 3", True),
    ("Mức bồi thường thiệt hại về nhà, công trình trên đất?", "88/2024/NĐ-CP", "Điều 14", True),
    ("Hỗ trợ ổn định đời sống cho hộ gia đình bị thu hồi đất?", "88/2024/NĐ-CP", "Điều 19", True),
    ("Chi phí tổ chức thực hiện bồi thường, hỗ trợ, tái định cư?", "88/2024/NĐ-CP", "Điều 27", True),
    ("Ghi nợ tiền sử dụng đất khi nhận đất tái định cư?", "88/2024/NĐ-CP", "Điều 26", True),
    ("Tái định cư bằng nhà ở, đất ở?", "88/2024/NĐ-CP", "Điều 24", True),
    ("Người Việt Nam định cư ở nước ngoài có được bồi thường về đất không?", "88/2024/NĐ-CP", "Điều 11", True),
    ("Nghị định 88/2024/NĐ-CP có hiệu lực khi nào?", "88/2024/NĐ-CP", "Điều 30", True),
    ("Điều 30 Nghị định 88 quy định gì?", "88/2024/NĐ-CP", "Điều 30", True),
    ("Luật Đất đai 43/2024 sửa đổi những gì?", "43/2024/QH15", "Điều 1", True),
    ("Thời hạn sử dụng đất ở là bao lâu?", None, None, False),
    ("Thủ tục cấp Giấy chứng nhận quyền sử dụng đất lần đầu?", None, None, False),
    ("Quy hoạch sử dụng đất cấp huyện được lập thế nào?", None, None, False),
    ("Chuyển mục đích sử dụng đất nông nghiệp sang đất ở?", None, None, False),
    ("Bảng giá đất Hà Nội 2026?", None, None, False),
    ("Thủ tục ly hôn đơn phương cần giấy tờ gì?", None, None, False),
    ("Giá vàng hôm nay bao nhiêu?", None, None, False),
    ("Điều 99 Luật Đất đai 31/2024 quy định gì?", None, None, False),
]


def main() -> None:
    index = MvpCorpusIndex.load()
    rows = []
    latencies = []
    for question, document, article, should_answer in QUESTIONS:
        started = time.perf_counter()
        hits = index.search(question, top_k=6)
        decision = index.assess(question, hits, min_score=5.0, min_coverage=0.5)
        latencies.append((time.perf_counter() - started) * 1000)
        expected = should_answer
        correct = decision.sufficient == expected
        hit_at_1 = bool(
            should_answer and hits and hits[0].evidence.document_number == document
            and hits[0].evidence.article_number == article
        )
        hit_at_3 = any(
            hit.evidence.document_number == document and hit.evidence.article_number == article
            for hit in hits[:3]
        ) if should_answer else None
        rows.append({
            "question": question,
            "expected": "answer" if should_answer else "abstain",
            "decision": "answer" if decision.sufficient else decision.reason,
            "correct": correct,
            "hit_at_1": hit_at_1 if should_answer else None,
            "hit_at_3": hit_at_3,
            "top": (
                f"{hits[0].evidence.document_number} {hits[0].evidence.article_number}"
                if hits else None
            ),
        })

    answerable = [row for row in rows if row["expected"] == "answer"]
    summary = {
        "corpus": "MVP_DEMO_CORPUS",
        "chunks": len(index.evidence),
        "documents": len(index.documents()),
        "questions": len(rows),
        "decision_accuracy": round(sum(row["correct"] for row in rows) / len(rows), 4),
        "abstention_accuracy": round(
            sum(row["correct"] for row in rows if row["expected"] == "abstain")
            / max(1, len(rows) - len(answerable)), 4
        ),
        "answerable_hit_at_1": round(sum(bool(row["hit_at_1"]) for row in answerable) / len(answerable), 4),
        "answerable_hit_at_3": round(sum(bool(row["hit_at_3"]) for row in answerable) / len(answerable), 4),
        "latency_ms_median": round(statistics.median(latencies), 2),
        "latency_ms_p95": round(sorted(latencies)[int(len(latencies) * 0.95) - 1], 2),
        "wrong_decisions": [row for row in rows if not row["correct"]],
    }
    payload = {"summary": summary, "results": rows}
    output = ROOT / "data" / "mvp-retrieval-benchmark.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nWrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
