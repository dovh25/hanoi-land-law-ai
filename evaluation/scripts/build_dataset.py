"""Materialize source-authored labels WITHOUT invoking the retriever or an LLM."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    config = json.loads((ROOT / "evaluation/configs/offline.json").read_text())
    source = ROOT / config["corpus_path"]
    if digest(source) != config["corpus_sha256"]:
        raise ValueError("Corpus changed: review labels before rebuilding")
    records = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    rows = []
    with (ROOT / "evaluation/datasets/source-authored.tsv").open() as handle:
        for seed in csv.DictReader(handle, delimiter="\t"):
            evidence = [records[int(i)] for i in seed["indices"].split(",") if i]
            rows.append({
                "id": seed["id"], "split": seed["split"], "question": seed["question"],
                "category": seed["category"], "tags": seed["tags"].split(";"),
                "topic": seed["family"], "family": seed["family"],
                "difficulty": "hard" if seed["category"] in {"multi_evidence", "safety", "legal_validity"} else "medium",
                "answerable": bool(evidence),
                "expected_documents": sorted({r["document_number"] for r in evidence}),
                "relevant_locators": seed["locators"],
                "gold_evidence_ids": [r["chunk_id"] for r in evidence],
                "acceptable_alternative_evidence_ids": [],
                "reference_evidence": [{k: r[k] for k in (
                    "chunk_id", "document_number", "article_number", "source_text", "source_start",
                    "source_end", "raw_sha256", "parsed_text_sha256", "stage_id", "source_url"
                )} for r in evidence],
                "key_facts_or_refusal_reason": seed["key_facts_or_refusal_reason"],
                "source_artifact_sha256": config["corpus_sha256"],
                "annotation_status": "provisional_source_authored",
                "review_status": "pending_independent_human_review",
                "annotator": "AI source inspection; no retriever-derived labels",
            })
    path = ROOT / config["dataset_path"]
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    # Separate worksheet; never erase reviewer work on regeneration.
    worksheet = ROOT / "evaluation/datasets/label-review.csv"
    if not worksheet.exists():
        with worksheet.open("w") as handle:
            fields = ["id", "split", "question", "expected_answerable", "locators", "gold_ids",
                      "key_facts", "decision", "reviewer", "reviewed_at", "corrected_gold_ids", "notes"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for r in rows:
                writer.writerow(dict(zip(fields[:7], [r["id"], r["split"], r["question"],
                    r["answerable"], r["relevant_locators"], ";".join(r["gold_evidence_ids"]),
                    r["key_facts_or_refusal_reason"]])))
    print(f"Wrote {len(rows)} provisional cases; independent reviewed gold labels: 0")


if __name__ == "__main__":
    build()
