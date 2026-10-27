"""OFFLINE ONLY: prepare five replay records. There is deliberately no live switch."""
import json

from evaluation.scripts.run_offline import ROOT, disable_network, sha


def main():
    disable_network()
    from backend.services.mvp_corpus import MvpCorpusIndex
    from backend.services.pipelines.mvp_rag_pipeline import _format_evidence, _prompt
    config = json.loads((ROOT / "evaluation/configs/offline.json").read_text())
    if sha(ROOT / config["corpus_path"]) != config["corpus_sha256"]:
        raise ValueError("Corpus changed")
    cases = {c["id"]: c for c in map(json.loads, (ROOT / config["dataset_path"]).read_text().splitlines())}
    index = MvpCorpusIndex.load(ROOT / config["corpus_path"])
    rows = []
    for case_id in ("T01", "T07", "T13", "T21", "T24"):
        case = cases[case_id]
        hits = index.search(case["question"], config["top_k"])
        decision = index.assess(case["question"], hits, min_score=config["min_score"], min_coverage=config["min_coverage"])
        if decision.sufficient != case["answerable"]:
            raise ValueError("Live plan routing differs from expected: stop and review")
        evidence = [h.evidence for h in hits]
        rows.append({"case_id": case_id, "user_query": case["question"],
                     "expected_generation_requests": int(decision.sufficient),
                     "routing_reason": decision.reason,
                     "retrieved_context_ids": [e.chunk_id for e in evidence],
                     "exact_retrieved_evidence": [r for r in case["reference_evidence"]] if not hits else
                         [{"citation_id": f"E{i}", "chunk_id": e.chunk_id, "source_text": e.source_text,
                           "document_number": e.document_number, "raw_sha256": e.raw_sha256,
                           "parsed_text_sha256": e.parsed_text_sha256} for i, e in enumerate(evidence, 1)],
                     "exact_context_to_send": _format_evidence(evidence) if decision.sufficient else None,
                     "prompt_characters": sum(len(m.content) for m in _prompt(case["question"], evidence)) if decision.sufficient else 0,
                     "generated_answer": None, "citation_ids": None, "token_usage": None,
                     "latency_ms": None, "provider_attempt_count": 0, "validation_outcome": "not_executed",
                     "human_review_status": "pending"})
    plan = {"state": "PREPARED_NOT_APPROVED_NOT_EXECUTED", "corpus_sha256": config["corpus_sha256"],
            "expected_generation_requests": sum(r["expected_generation_requests"] for r in rows),
            "maximum_provider_attempts_including_failures": 8, "automatic_retries": 0,
            "judge_requests": 0, "model_id": None,
            "required_preflight": ["explicit user approval of exact budget", "model available in owning project",
                                   "Free Tier with billing disabled", "actual shared RPM/TPM/RPD and remaining quota",
                                   "single operator, no concurrent public usage consuming the budget",
                                   "process-scoped live settings and durable experiment attempt counter"],
            "responses": rows}
    path = ROOT / "evaluation/reports/live-plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    print(f"Prepared {len(rows)} cases, expected {plan['expected_generation_requests']} generation requests; executed 0")


if __name__ == "__main__":
    main()
