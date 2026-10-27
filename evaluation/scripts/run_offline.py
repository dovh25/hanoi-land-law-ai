"""Reproduce the benchmark with all network sockets disabled and no provider key loaded."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

from evaluation.scripts.metrics import aggregate, percentile, ratio, retrieval_metrics

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def disable_network():
    # Also blocks unexpected telemetry/HTTP clients. No allowlisted Internet endpoints.
    import socket
    original = socket.socket

    class OfflineSocket(original):
        def __init__(self, family=socket.AF_INET, *args, **kwargs):
            if family != socket.AF_UNIX:
                raise RuntimeError("Evaluation forbids network sockets")
            super().__init__(family, *args, **kwargs)

    socket.socket = OfflineSocket


def safe_settings(config, temp):
    from backend.core.config import Config
    return Config(_env_file=None, APP_MODE="test", ENABLE_LIVE_LLM=False,
                  GEMINI_API_KEY="", JWT_SECRET_KEY="evaluation-only-0123456789-ABCDEFghijkl",
                  DATABASE_URL=f"sqlite:///{temp}/evaluation.sqlite3",
                  LLM_USAGE_DB=Path(temp) / "unused-ledger.sqlite3",
                  MVP_DEMO_CORPUS_PATH=ROOT / config["corpus_path"],
                  MVP_TOP_K=config["top_k"], MVP_MIN_SCORE=config["min_score"],
                  MVP_MIN_COVERAGE=config["min_coverage"])


def validate_dataset(cases, records, config):
    by_id = {r["chunk_id"]: r for r in records}
    if len(by_id) != len(records) or len({r["id"] for r in cases}) != len(cases):
        raise ValueError("Duplicate corpus or question IDs")
    for case in cases:
        if case["source_artifact_sha256"] != config["corpus_sha256"]:
            raise ValueError("Stale labels")
        if case["answerable"] != bool(case["gold_evidence_ids"]):
            raise ValueError("Answerable case needs gold")
        if case["acceptable_alternative_evidence_ids"]:
            raise ValueError("Alternative equivalence groups need explicit adjudication before scoring")
        if len(set(case["gold_evidence_ids"])) != len(case["gold_evidence_ids"]):
            raise ValueError("Repeated gold ID")
        if {r["chunk_id"] for r in case["reference_evidence"]} != set(case["gold_evidence_ids"]):
            raise ValueError("Missing reference evidence")
        for evidence in case["reference_evidence"]:
            if any(by_id[evidence["chunk_id"]][k] != v for k, v in evidence.items()):
                raise ValueError("Reference does not match source artifact")
    for a in cases:
        for b in cases:
            if a["split"] != b["split"]:
                if a["family"] == b["family"]:
                    raise ValueError("Question family leakage across splits")
    return by_id


def apply_reviews(cases, records):
    """An explicit human CSV decision can promote/correct labels; blank rows do nothing."""
    path = ROOT / "evaluation/datasets/label-review.csv"
    by_id = {r["chunk_id"]: r for r in records}
    reviews = {}
    with path.open() as handle:
        for row in csv.DictReader(handle):
            if row["id"] in reviews:
                raise ValueError("Duplicate review row")
            reviews[row["id"]] = row
    for case in cases:
        row = reviews.get(case["id"])
        if not row or not row["decision"].strip():
            continue
        if row["question"] != case["question"] or row["split"] != case["split"]:
            raise ValueError("Stale review worksheet")
        if row["decision"] not in {"approved", "corrected"}:
            raise ValueError("Use approved/corrected or leave decision blank with review notes")
        if not row["reviewer"].strip() or not row["reviewed_at"].strip():
            raise ValueError("Human review needs identity and ISO date")
        datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
        if row["expected_answerable"].lower() not in {"true", "false"}:
            raise ValueError("expected_answerable must be True or False")
        answerable = row["expected_answerable"].lower() == "true"
        gold = (row["corrected_gold_ids"] if row["decision"] == "corrected" else row["gold_ids"]).split(";")
        gold = [g.strip() for g in gold if g.strip()]
        if answerable != bool(gold) or any(g not in by_id for g in gold):
            raise ValueError("Corrected answerability and gold IDs must agree with source artifact")
        if row["decision"] == "approved" and (gold != case["gold_evidence_ids"] or answerable != case["answerable"]):
            raise ValueError("Use corrected for changed labels")
        case.update(answerable=answerable, gold_evidence_ids=gold,
                    expected_documents=sorted({by_id[g]["document_number"] for g in gold}),
                    reference_evidence=[{k: by_id[g][k] for k in (
                        "chunk_id", "document_number", "article_number", "source_text", "source_start", "source_end",
                        "raw_sha256", "parsed_text_sha256", "stage_id", "source_url")} for g in gold],
                    relevant_locators=row["locators"], key_facts_or_refusal_reason=row["key_facts"],
                    annotation_status="human_reviewed_against_sources", review_status="human_reviewed_against_sources",
                    reviewer=row["reviewer"], reviewed_at=row["reviewed_at"])
    return cases


def audit_sources(records):
    """Read preserved stages/raw files only. Never call ingestion/build/index writers."""
    workspace = ROOT / "data/phase-d-corpus-v2"
    rows = []
    for stage_id in sorted({r["stage_id"] for r in records}):
        path = workspace / "stages" / f"{stage_id}.json"
        if not path.exists():
            rows.append({"stage_id": stage_id, "status": "preserved_stage_unavailable", "checked_spans": 0})
            continue
        stage = json.loads(path.read_text())
        selected = [r for r in records if r["stage_id"] == stage_id]
        text = stage["parsed"]["text"]
        parsed_hash = hashlib.sha256(text.encode()).hexdigest()
        raw_path = (workspace / stage["raw_path"]).resolve()
        if not raw_path.is_relative_to(workspace.resolve()):
            raise ValueError("Source path escaped repository workspace")
        raw_hash = sha(raw_path) if raw_path.exists() else None
        spans_ok = all(text[r["source_start"]:r["source_end"]] == r["source_text"] for r in selected)
        hashes_ok = all(r["parsed_text_sha256"] == parsed_hash and r["raw_sha256"] == raw_hash for r in selected)
        rows.append({"stage_id": stage_id, "document": selected[0]["document_number"],
                     "status": "verified_local_artifacts" if spans_ok and hashes_ok else "mismatch",
                     "checked_spans": len(selected), "spans_match": spans_ok, "hashes_match": hashes_ok,
                     "raw_sha256": raw_hash, "parsed_text_sha256": parsed_hash})
        if not spans_ok or not hashes_ok:
            raise ValueError("Preserved source differs from bundled corpus")
    return rows


def duplicate_audit(cases):
    # Screening, not a proof of semantic independence. Reports rather than changes labels.
    from backend.services.mvp_corpus import fold, query_terms
    from scripts.evaluate_mvp_retrieval import QUESTIONS
    cross = []
    for i, a in enumerate(cases):
        for b in cases[i + 1:]:
            if a["split"] == b["split"]:
                continue
            x, y = set(query_terms(a["question"])), set(query_terms(b["question"]))
            score = len(x & y) / max(1, len(x | y))
            if score >= .70:
                cross.append({"ids": [a["id"], b["id"]], "token_jaccard": score})
    historic = []
    for case in cases:
        scores = [(difflib.SequenceMatcher(None, fold(case["question"]), fold(q[0])).ratio(), q[0]) for q in QUESTIONS]
        best = max(scores)
        if best[0] >= .80:
            historic.append({"id": case["id"], "similarity": best[0], "old_question": best[1]})
        if any(fold(case["question"]) == fold(q[0]) for q in QUESTIONS):
            raise ValueError("Historical benchmark question reused")
    return {"cross_split_token_jaccard_at_least_0.70": cross,
            "historical_character_similarity_at_least_0.80": historic,
            "limitation": "AI-curated frozen split, not independently sealed; lexical screening cannot prove semantic independence."}


def citation_evaluation(index):
    from backend.services.pipelines.mvp_rag_pipeline import validate_answer
    fixtures = json.loads((ROOT / "evaluation/fixtures/citations.json").read_text())
    rows = []
    for fixture in fixtures:
        evidence = [index.evidence[i] for i in fixture["source_indices"]]
        result = validate_answer(fixture["text"], evidence)
        passed = (not result.valid if fixture["expected"] == "reject" else
                  (not result.valid or any("hiệu lực hiện hành" in w for w in result.warnings))
                  if fixture["expected"] == "disarm" else result.valid)
        rows.append({**fixture, "accepted": result.valid, "passed": passed,
                     "output": asdict(result)})
    def kind(k):
        return [r for r in rows if r["kind"] == k]
    accepted = [r for r in rows if r["accepted"]]
    emitted = [(citation, len(r["source_indices"])) for r in accepted
               for citation in re.findall(r"\[E(\d+)\]", r["output"]["answer"])]
    claimed = [r for r in accepted if r["claim_integrity"] is not None]
    accepted_docs = [r for r in kind("document_version") if r["accepted"]]
    accepted_locators = [r for r in kind("article_clause") if r["accepted"]]
    invalid = [r for r in rows if r["expected"] == "reject" and r["kind"] != "support"]
    quote_rows = [r for r in kind("quote") if r["accepted"]]
    return {"fixture_count": len(rows), "fixture_passes": sum(r["passed"] for r in rows),
            "emitted_id_resolution": {"resolved": sum(1 <= int(c) <= n for c, n in emitted), "total": len(emitted),
                                      "rate": ratio(sum(1 <= int(c) <= n for c, n in emitted), len(emitted))},
            "document_version_test_accuracy": ratio(sum(r["passed"] for r in kind("document_version")), len(kind("document_version"))),
            "article_clause_test_accuracy": ratio(sum(r["passed"] for r in kind("article_clause")), len(kind("article_clause"))),
            "accepted_document_version_accuracy": ratio(sum(r["claim_integrity"] for r in accepted_docs), len(accepted_docs)),
            "accepted_article_clause_accuracy": ratio(sum(r["claim_integrity"] for r in accepted_locators), len(accepted_locators)),
            "accepted_quote_exact_match_rate": ratio(sum(r["strict_quote_match"] for r in quote_rows), len(quote_rows)),
            "invalid_citation_rejection_rate": ratio(sum(not r["accepted"] for r in invalid), len(invalid)),
            "fabricated_or_wrong_citation_fixture_acceptance_rate": ratio(sum(not r["claim_integrity"] for r in claimed), len(claimed)),
            "citation_support_precision_human_reviewed": None,
            "current_law_disarm": {"passed": sum(r["passed"] for r in kind("current_law")), "total": len(kind("current_law"))},
            "rows": rows}


def probe(config):
    # Fresh process: includes imports, application factory, database lifespan and corpus loading.
    start = time.perf_counter()
    from backend.core.config import settings_context
    with tempfile.TemporaryDirectory(prefix="startup-", dir=ROOT / "evaluation/reports") as temp:
        settings = safe_settings(config, temp)
        with settings_context(settings):
            from backend.main import create_app
            from fastapi.testclient import TestClient
            app = create_app(settings)
            with TestClient(app) as client:
                ready = client.get("/demo/readyz").status_code
                elapsed = (time.perf_counter() - start) * 1000
                rss = int(Path("/proc/self/status").read_text().split("VmRSS:")[1].split()[0]) * 1024
                return {"startup_to_inprocess_readiness_ms": elapsed, "demo_ready_status": ready,
                        "rss_bytes": rss, "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}


def performance(index, cases, config):
    from backend.services.mvp_corpus import MvpCorpusIndex
    for i in range(config["warmup_queries"]):
        index.search(cases[i % len(cases)]["question"], config["top_k"])
    samples = []
    per_query = {}
    for _ in range(config["timing_repetitions"]):
        for case in cases:
            start = time.perf_counter()
            index.search(case["question"], config["top_k"])
            elapsed = (time.perf_counter() - start) * 1000
            samples.append(elapsed)
            per_query.setdefault(case["id"], []).append(elapsed)
    loads = []
    for _ in range(5):
        start = time.perf_counter()
        MvpCorpusIndex.load(ROOT / config["corpus_path"])
        loads.append((time.perf_counter() - start) * 1000)
    children = []
    for _ in range(3):
        child = subprocess.run([sys.executable, "-m", "evaluation.scripts.run_offline", "--startup-probe"],
                               cwd=ROOT, capture_output=True, text=True, check=True, timeout=90)
        children.append(json.loads(child.stdout.splitlines()[-1]))
    cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")), "unknown")
    seen = set()
    def deep_size(obj):
        if id(obj) in seen:
            return 0
        seen.add(id(obj))
        size = sys.getsizeof(obj)
        if isinstance(obj, dict):
            size += sum(deep_size(k) + deep_size(v) for k, v in obj.items())
        elif isinstance(obj, (list, tuple, set, frozenset)):
            size += sum(deep_size(v) for v in obj)
        elif hasattr(obj, "__dict__"):
            size += deep_size(vars(obj))
        return size
    return {"samples": len(samples), "warmup_queries": config["warmup_queries"],
            "latency_ms": {"p50": percentile(samples, .5), "p95": percentile(samples, .95),
                           "p99": percentile(samples, .99) if len(samples) >= 1000 else None},
            "throughput_sequential_queries_per_second": 1000 * len(samples) / sum(samples),
            "index_loading_ms": loads, "startup_probes": children,
            "corpus_artifact_bytes": (ROOT / config["corpus_path"]).stat().st_size,
            "index_python_object_graph_bytes_approximate": deep_size(index),
            "index_serialized_bytes": None, "index_size_note": "In-memory Python index; no serialized index artifact",
            "timing_samples_ms": samples, "per_question_samples_ms": per_query,
            "environment": {"python": platform.python_version(), "os": platform.platform(),
                            "cpu": cpu, "logical_cpus": os.cpu_count(),
                            "mem_total": Path("/proc/meminfo").read_text().splitlines()[0],
                            "uv_lock_sha256": sha(ROOT / "uv.lock")}}


def write_report(payload, output):
    held = payload["provisional"]["held_out"]
    lines = ["# Offline MVP evaluation", "", f"Run: {payload['generated_at']}.", "",
             f"**Verdict: PARTIALLY EVALUATED. Provisional and human-reviewed scores are separated; human-reviewed labels: {payload['dataset']['reviewed_gold']}.**",
             "Gemini/provider requests: **0**. No generated-answer quality score is available.", "",
             "## Held-out retrieval (answerable cases only)", "", "| Metric | Provisional value | Query-bootstrap 95% interval |",
             "|---|---:|---|" ]
    for name, value in held["retrieval"].items():
        ci = held["bootstrap_95_ci"].get(name)
        lines.append(f"| {name} | {value:.4f} | {f'{ci[0]:.4f}–{ci[1]:.4f}' if ci else 'Too few cases'} |")
    lines += ["", f"Exact article lookup: {held['exact_article']['correct']}/{held['exact_article']['total']} (document + article + raw/parsed version hashes).",
              "", "Human-reviewed benchmark results (if any):", "", "```json",
              json.dumps(payload["validated_benchmark_scores"], indent=2), "```",
              "", "## Held-out categories (overlapping accent-free/temporal slices)", "",
              "| Slice | n | Answerable | Recall@5 | Hit@1 | Correct gate decisions |", "|---|---:|---:|---:|---:|---:|"]
    for category, summary in payload["categories"].items():
        retrieval = summary["retrieval"]
        confusion = summary["classification"]["confusion_matrix"]
        correct = confusion["answerable_accepted"] + confusion["unsupported_refused"]
        lines.append(f"| {category} | {summary['cases']} | {summary['answerable']} | {retrieval.get('recall@5', 'N/A')} | {retrieval.get('hit@1', 'N/A')} | {correct}/{summary['cases']} |")
    lines += ["", "## Scope / abstention (generation routing, not final-answer correctness)", "", "```json",
              json.dumps(held["classification"], indent=2), "```", "", "## Citation adversarial fixtures", "",
              "Constructed unit fixtures, not a distributional hallucination benchmark. Support annotations require independent review.", "", "```json",
              json.dumps({k: v for k, v in payload["citations"].items() if k != "rows"}, indent=2), "```", "",
              "## Local performance", "", "```json", json.dumps({k: v for k, v in payload["performance"].items()
              if k not in {"timing_samples_ms", "per_question_samples_ms"}}, indent=2), "```", "",
              "Sequential, warm local retrieval only; p99 suppressed below 1,000 samples. Startup is a fresh Python process with in-process ASGI readiness, not a TCP/Render cold start.", "",
              "## Failure cases", "", "| Case | Failure | Gate reason / top IDs |", "|---|---|---|"]
    for row in payload["per_question"]:
        failures = []
        if row["accepted"] != row["answerable"]:
            failures.append("false refusal" if row["answerable"] else "unsupported accepted for generation")
        if row["answerable"] and row["metrics"]["recall@5"] < 1:
            failures.append("gold evidence missing at 5")
        if row["answerable"] and not row["metrics"]["hit@1"]:
            failures.append("ranking miss at 1")
        if failures:
            lines.append(f"| {row['id']} ({row['split']}) | {', '.join(failures)} | {row['gate']['reason']} / {', '.join(x[:12] for x in row['retrieved_ids'][:3])} |")
    lines += ["", "Citation fixture failures: " + ", ".join(r["id"] for r in payload["citations"]["rows"] if not r["passed"]),
              "", "## Interpretation and limits", "",
              "- No retriever behavior, corpus, prompts, or deployment was changed. One frozen production configuration; no baseline tuning.",
              "- Strict chunk IDs avoid document-level false positives but split provisions penalize partial evidence. Gold completeness and negative labels are provisional.",
              "- Precision divides by K even when explicit lookup returns fewer results; fewer-than-K lists are padded with nonrelevant slots.",
              "- Confidence intervals resample questions, not independent provisions; correlated families and narrow corpus limit generalization. Perfect slices do not prove perfect population performance.",
              "- Validation resolves IDs but does not entail claim support, clause correctness, or version correctness. See fixture outputs before interpreting integrity rates.",
              "- The held-out split was frozen before scoring, but authored/observed by this evaluator, not independently sealed. Do not tune against it.",
              "- Live deployed metadata requests timed out; repository deployment configuration and prior M4 evidence are not fresh deployed-state verification.",
              "", "Reproduce: `uv run --frozen python -m evaluation.scripts.build_dataset` then `uv run --frozen python -m evaluation.scripts.run_offline`."]
    (output / "offline-report.md").write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--startup-probe", action="store_true")
    args = parser.parse_args()
    disable_network()
    # Overrides applied before any app import; never reads .env or writes application data.
    os.environ.update(ENABLE_LIVE_LLM="false", LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false",
                      OTEL_SDK_DISABLED="true")
    config = json.loads((ROOT / "evaluation/configs/offline.json").read_text())
    output = ROOT / "evaluation/reports"
    output.mkdir(exist_ok=True)
    if args.startup_probe:
        print(json.dumps(probe(config)))
        return
    if sha(ROOT / config["corpus_path"]) != config["corpus_sha256"]:
        raise ValueError("Corpus hash mismatch")
    from backend.services.mvp_corpus import MvpCorpusIndex
    from backend.services.pipelines.mvp_rag_pipeline import MvpRagPipeline
    from backend.services.llm import GeminiProvider
    from backend.core.config import settings_context
    cases = [json.loads(line) for line in (ROOT / config["dataset_path"]).read_text().splitlines()]
    records = [json.loads(line) for line in (ROOT / config["corpus_path"]).read_text().splitlines()]
    cases = apply_reviews(cases, records)
    validate_dataset(cases, records, config)
    index = MvpCorpusIndex(records)
    rows = []
    with tempfile.TemporaryDirectory(prefix="offline-", dir=output) as temp:
        settings = safe_settings(config, temp)
        with settings_context(settings), patch.object(GeminiProvider, "invoke", side_effect=AssertionError("No provider allowed")) as provider:
            pipeline = MvpRagPipeline(index=index)
            for case in cases:
                hits = index.search(case["question"], top_k=config["top_k"])
                gate = index.assess(case["question"], hits, min_score=config["min_score"],
                                    min_coverage=config["min_coverage"], min_heading_coverage=config["min_heading_coverage"])
                response = pipeline.respond(case["question"])
                if gate.sufficient != (response["status"] == "llm_disabled"):
                    raise ValueError("Evaluator decision differs from actual offline pipeline")
                expected = case["reference_evidence"]
                exact = None
                if case["category"] == "direct_article":
                    exact = bool(hits and any(
                        hits[0].evidence.document_number == e["document_number"] and
                        hits[0].evidence.article_number == e["article_number"] and
                        hits[0].evidence.raw_sha256 == e["raw_sha256"] and
                        hits[0].evidence.parsed_text_sha256 == e["parsed_text_sha256"] for e in expected))
                rows.append({**{k: case[k] for k in ("id", "split", "question", "category", "tags", "answerable", "review_status")},
                             "annotation_status": case["annotation_status"],
                             "reference_evidence": case["reference_evidence"],
                             "relevant_locators": case["relevant_locators"],
                             "key_facts_or_refusal_reason": case["key_facts_or_refusal_reason"],
                             "reviewer": case.get("reviewer"), "reviewed_at": case.get("reviewed_at"),
                             "accepted": gate.sufficient, "gate": asdict(gate),
                             "retrieved_ids": [h.evidence.chunk_id for h in hits],
                             "retrieved_scores": [h.score for h in hits],
                             "gold_ids": case["gold_evidence_ids"],
                             "metrics": retrieval_metrics([h.evidence.chunk_id for h in hits], case["gold_evidence_ids"]) if case["answerable"] else None,
                             "exact_article_correct": exact, "offline_response": response})
            provider_calls = provider.call_count
    held = [r for r in rows if r["split"] == "held_out"]
    provisional_held = [r for r in held if r["review_status"] != "human_reviewed_against_sources"]
    categories = {c: aggregate([r for r in provisional_held if r["category"] == c]) for c in sorted({r["category"] for r in provisional_held})}
    for tag in ("accent_free", "temporal"):
        categories[tag] = aggregate([r for r in provisional_held if tag in r["tags"]])
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "verdict": "PARTIALLY EVALUATED",
        "configuration": config, "corpus_sha256": sha(ROOT / config["corpus_path"]),
        "dataset_sha256": sha(ROOT / config["dataset_path"]),
        "review_worksheet_sha256": sha(ROOT / "evaluation/datasets/label-review.csv"),
        "evaluator_sha256": sha(Path(__file__)),
        "source_artifact_audit": audit_sources(records),
        "implementation_sha256": {p: sha(ROOT / p) for p in ("backend/services/mvp_corpus.py", "backend/services/pipelines/mvp_rag_pipeline.py", "backend/services/llm.py")},
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
        "dataset": {"total": len(cases), "reviewed_gold": sum(c["review_status"] == "human_reviewed_against_sources" for c in cases),
                    "provisional": sum(c["review_status"] != "human_reviewed_against_sources" for c in cases), "held_out": len(held),
                    "documents": index.documents(), "characters": sum(len(r["source_text"]) for r in records)},
        "provider_requests": provider_calls,
        "validated_benchmark_scores": {split: aggregate([r for r in rows if r["split"] == split and r["review_status"] == "human_reviewed_against_sources"])
                                       for split in ("development", "held_out")} if any(r["review_status"] == "human_reviewed_against_sources" for r in rows) else None,
        "duplicate_audit": duplicate_audit(cases),
        "provisional": {split: aggregate([r for r in rows if r["split"] == split and r["review_status"] != "human_reviewed_against_sources"], resamples=config["bootstrap_resamples"], seed=config["random_seed"])
                        for split in ("development", "held_out")},
        "categories": categories, "citations": citation_evaluation(index),
        "performance": performance(index, cases, config), "per_question": rows,
    }
    (output / "offline-results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    with (output / "per-question.csv").open("w") as handle:
        fields = ["id", "split", "category", "question", "answerable", "accepted", "reason", "review_status", "gold_ids", "retrieved_ids", "recall@1", "recall@3", "recall@5", "precision@3", "precision@5", "mrr@5", "ndcg@5", "hit@1", "hit@3", "hit@5"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({**{k: row[k] for k in fields if k in row}, "reason": row["gate"]["reason"], **(row["metrics"] or {})})
    write_report(payload, output)
    print(json.dumps({"dataset": payload["dataset"], "held_out": payload["provisional"]["held_out"],
                      "latency_ms": payload["performance"]["latency_ms"], "provider_requests": provider_calls}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
