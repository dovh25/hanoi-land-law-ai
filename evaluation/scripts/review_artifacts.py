"""Render readable source references and blank human score sheets (no model calls)."""
import csv
import json
import xml.etree.ElementTree as ET
from collections import Counter
import statistics

from evaluation.scripts.run_offline import ROOT


def main():
    cases = [json.loads(line) for line in (ROOT / "evaluation/datasets/cases.jsonl").read_text().splitlines()]
    results = json.loads((ROOT / "evaluation/reports/offline-results.json").read_text())
    lines = ["# Source review packet", "", "**All labels are provisional until a named independent reviewer checks them.**",
             "Edit `evaluation/datasets/label-review.csv`, not this generated reference packet.",
             "For every answerable case check ALL required chunks, the clause/point locator, key facts, version hashes, and missing alternatives.",
             "For negative cases check whether a bounded source-based answer is possible; distinguish general explanation from a definitive personal/current-law conclusion.",
             "Corpus hash: `" + results["corpus_sha256"] + "`.", ""]
    for case in cases:
        lines += [f"## {case['id']} — {case['split']} / {case['category']}", "", case["question"], "",
                  f"Answerable within stored-version scope: **{case['answerable']}**.",
                  f"Locators: {case['relevant_locators'] or 'None'}.", "",
                  "Provisional key facts / refusal reason: " + case["key_facts_or_refusal_reason"], ""]
        for source in case["reference_evidence"]:
            lines += [f"### {source['document_number']} — {source['article_number']}", "",
                      f"- Chunk: `{source['chunk_id']}`",
                      f"- Parsed text hash: `{source['parsed_text_sha256']}`",
                      f"- Raw artifact hash: `{source['raw_sha256']}`",
                      f"- Parsed offsets: [{source['source_start']}, {source['source_end']})",
                      f"- Source: {source['source_url']}", "", "```text", source["source_text"], "```", ""]
    (ROOT / "evaluation/datasets/source-review.md").write_text("\n".join(lines) + "\n")
    answers = ROOT / "evaluation/datasets/answer-review.csv"
    if not answers.exists():
        with answers.open("w") as handle:
            fields = ["id", "question", "response_artifact", "response_status", "factual_accuracy_0_2",
                      "faithfulness_0_2", "completeness_0_2", "relevance_0_2", "citation_support_0_2",
                      "applicability_caution_0_2", "reviewer", "reviewed_at", "unresolved_items"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in results["per_question"]:
                writer.writerow({"id": row["id"], "question": row["question"],
                                 "response_artifact": "evaluation/reports/offline-results.json#" + row["id"],
                                 "response_status": row["offline_response"]["status"],
                                 "unresolved_items": "No generated answer; leave scores blank. Review a separately saved response if live evaluation is approved."})
    citation_sheet = ROOT / "evaluation/datasets/citation-review.csv"
    if not citation_sheet.exists():
        with citation_sheet.open("w") as handle:
            fields = ["fixture_id", "claim", "source_indices", "expected_behavior", "observed_acceptance",
                      "human_support_decision", "reviewer", "reviewed_at", "notes"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in results["citations"]["rows"]:
                writer.writerow({"fixture_id": row["id"], "claim": row["text"],
                                 "source_indices": row["source_indices"], "expected_behavior": row["expected"],
                                 "observed_acceptance": row["accepted"]})
    junit = ROOT / "evaluation/reports/pytest.xml"
    if junit.exists():
        root = ET.parse(junit).getroot()
        suite = root.find("testsuite")
        if suite is None:
            raise ValueError("Missing pytest suite")
        groups = {}
        for test in suite.findall("testcase"):
            module = test.attrib["classname"]
            group = groups.setdefault(module, {"tests": 0, "failures": 0, "errors": 0, "skipped": 0})
            group["tests"] += 1
            for tag in ("failure", "error", "skipped"):
                if test.find(tag) is not None:
                    group[{"failure": "failures", "error": "errors", "skipped": "skipped"}[tag]] += 1
        summary = {"tests": int(suite.attrib["tests"]), "failures": int(suite.attrib["failures"]),
                   "errors": int(suite.attrib["errors"]), "skipped": int(suite.attrib["skipped"]),
                   "seconds": float(suite.attrib["time"]), "by_module": groups,
                   "scope": "Offline network-blocked pytest; local API contracts and mocks, not public uptime or live provider reliability."}
        (ROOT / "evaluation/reports/test-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    else:
        summary = None
    write_summary(results, cases, summary)
    print("Rendered source packet and review sheets; no existing human worksheets overwritten")


def write_summary(results, cases, test_summary):
    held = results["provisional"]["held_out"]
    retrieval = held["retrieval"]
    citations = results["citations"]
    performance = results["performance"]
    matrix = held["classification"]["confusion_matrix"]
    def pct(value):
        return f"{100 * value:.2f}%" if value is not None else "Unmeasured"
    def metric_value(name, digits=4):
        value = retrieval.get(name)
        return f"{value:.{digits}f}" if value is not None else "N/A"
    lines = ["# Evaluation results summary", "", "## Verdict: PARTIALLY EVALUATED", "",
             "The offline framework was implemented and executed. Retrieval is promising on a narrow",
             "stored-version corpus, but the gate rejects many supported questions and syntactic",
             "citation checks do not establish legal support. **Not validated for legal advice or",
             "unattended current-law QA.** No product ranking, prompt, corpus or deployment was changed.", "",
             "## A. Architecture and provenance", "",
             "- Actual demo: React → FastAPI → straight-line `MvpRagPipeline` → BM25 → gate → optional Gemini → validator.",
             "- No LangGraph, neural embeddings, Qdrant or learned reranker on the evaluated demo path; legacy paths are separate.",
             "- Two stored instruments (43/2024/QH15, 88/2024/NĐ-CP), 90 chunks, 77,243 characters; all validity unknown.",
             f"- Corpus SHA-256: `{results['corpus_sha256']}`.",
             "- Both preserved raw/parsed artifacts and all 90 source spans match. This is provenance consistency, not legal validation.",
             "- BM25 k1=1.5/b=.75, document/heading boosts, heading bigrams, explicit reference filter, article diversification; K=6, score≥5, coverage≥.5, heading≥.30.",
             "- Two public read-only metadata checks timed out. Current deployed model/cap/commit settings are unverified; blueprint and prior M4 evidence differ.", "",
             "## B. Dataset", "",
             f"- {results['dataset']['total']} new cases: 12 development / 32 held-out (20 answerable + 12 negative held-out).",
             f"- {results['dataset']['reviewed_gold']} independent human-reviewed labels / {results['dataset']['provisional']} provisional source-authored labels. No fully validated benchmark score yet.",
             "- Category distribution (all cases): " + ", ".join(f"{k}={v}" for k, v in sorted(Counter(c["category"] for c in cases).items())) + ".",
             "- Four accent-free questions overall (three held-out); two stored-version temporal questions held-out. These are overlapping slices, not extra cases.",
             "- No historical questions reused or lexical duplicate-screen flags. Frozen but not independently sealed; now observed, so do not tune against it.", "",
             "## C. Provisional held-out retrieval", "",
             "| Metric | Value |", "|---|---:|"]
    for metric in ("recall@1", "recall@3", "recall@5", "precision@3", "precision@5", "mrr@5", "ndcg@5", "hit@1", "hit@3", "hit@5"):
        lines.append(f"| {metric} | {metric_value(metric)} |")
    lines += [f"| Exact article lookup | {held['exact_article']['correct']}/{held['exact_article']['total']} |", "",
              "Binary, version-specific chunk relevance; fixed-K precision denominator. Macro query averages, negatives excluded.",
              "Recall@5 bootstrap 95% interval: " + str(held["bootstrap_95_ci"].get("recall@5")) + ". Small/correlated sample; not population legal accuracy.", "",
              "| Held-out slice | n | Recall@5 | Correct gate decisions |", "|---|---:|---:|---:|"]
    for name, group in results["categories"].items():
        counts = group["classification"]["confusion_matrix"]
        lines.append(f"| {name} | {group['cases']} | {group['retrieval'].get('recall@5', 'N/A')} | {counts['answerable_accepted'] + counts['unsupported_refused']}/{group['cases']} |")
    lines += ["", "## D. Safety and citations", "",
              "| Expected / gate outcome | Accepted | Refused |", "|---|---:|---:|",
              f"| Answerable | {matrix['answerable_accepted']} | {matrix['answerable_refused']} |",
              f"| Unsupported | {matrix['unsupported_accepted']} | {matrix['unsupported_refused']} |", "",
              f"- Scope accuracy: {pct(held['classification']['scope_accuracy'])}; answerable coverage {pct(held['classification']['answerable_gate_coverage'])}; false refusal {pct(held['classification']['false_refusal_rate'])}.",
              f"- Unsupported rejection: {pct(held['classification']['unsupported_rejection_rate'])}; abstention precision {pct(held['classification']['abstention_precision'])}; recall {pct(held['classification']['abstention_recall'])}.",
              "- Two unsupported cases accepted **for generation**, not proven incorrect generated answers: T26 (definitive personal eligibility without facts), T27 (unamended-current-law guarantee).",
              f"- Citation fixtures: {citations['fixture_passes']}/{citations['fixture_count']} expected behaviors pass. Emitted ID resolution {citations['emitted_id_resolution']['resolved']}/{citations['emitted_id_resolution']['total']}; invalid-integrity fixture rejection {pct(citations['invalid_citation_rejection_rate'])}.",
              f"- Accepted document/version claim accuracy {pct(citations['accepted_document_version_accuracy'])}; accepted article/clause locator accuracy {pct(citations['accepted_article_clause_accuracy'])}; strict accepted-quote matching {pct(citations['accepted_quote_exact_match_rate'])}.",
              f"- Fabricated/wrong-citation acceptance among accepted integrity-labeled fixtures: {pct(citations['fabricated_or_wrong_citation_fixture_acceptance_rate'])}. This is an adversarial fixture rate, **not** production hallucination prevalence.",
              "- Current-law assertion fixtures disarmed 1/2. Human-reviewed citation-support precision and generated-answer quality are **unmeasured**, not inferred from IDs.", "",
              "## E. Local performance and API reliability", "",
              f"- Last run, 220 timed retrievals after 10 warm-ups: p50 **{performance['latency_ms']['p50']:.2f} ms**, p95 **{performance['latency_ms']['p95']:.2f} ms**, p99 withheld (too few observations).",
              f"- Sequential throughput **{performance['throughput_sequential_queries_per_second']:.2f} queries/s**; index-loading median **{statistics.median(performance['index_loading_ms']):.2f} ms** (five samples).",
              f"- Fresh-process in-process ASGI readiness median **{statistics.median(x['startup_to_inprocess_readiness_ms'] for x in performance['startup_probes']):.2f} ms** (three samples). Not TCP or Render cold-start latency.",
              f"- Ready-process median RSS **{statistics.median(x['rss_bytes'] for x in performance['startup_probes']) / 1048576:.2f} MiB**; index object graph ≈{performance['index_python_object_graph_bytes_approximate'] / 1048576:.2f} MiB (approximate, not RSS); corpus JSONL {performance['corpus_artifact_bytes']:,} bytes; no serialized index.",
              f"- Python {performance['environment']['python']}; {performance['environment']['cpu']}; {performance['environment']['logical_cpus']} logical CPUs; WSL2/Linux. Lock hash and memory details in JSON.",
              "- Local timing varied materially between runs (see `performance-run-history.json`); do not extrapolate to free-cloud latency or capacity.",
              (f"- Network-blocked pytest: **{test_summary['tests']} tests**, {test_summary['failures']} failures, {test_summary['errors']} errors, {test_summary['skipped']} skipped. Includes local API contracts and mocked budgets, not public uptime." if test_summary else "- Regression result unavailable; run the documented pytest command."),
              "- `uv lock --check` and `uv pip check` passed; no evaluation dependency additions.", "",
              "## F. Ragas", "",
              "Ragas 0.4.3 metadata/official APIs inspected; no package installed or Ragas metrics implemented/executed.",
              "Exact-ID recall/precision would duplicate local arithmetic (precision denominator differs for short results).",
              "Text similarity adds no legal-semantic proof. EVAL-B skipped as redundant. LLM Faithfulness and all other judges deferred; nominal two stages/answer, not one API call/score.", "",
              "## G. Gemini", "",
              "Live provider requests **0**; judge requests **0**. Five-case manifest prepared: three answerable, one unsupported, one out of scope; expected **3** generation requests, absolute ceiling **8 including failures**, no retries or judges.",
              "Explicit budget approval, exact model access, Free Tier/billing-disabled status, actual shared RPM/TPM/RPD/headroom, and transport-level experiment accounting remain required. No live execution is enabled.", "",
              "## H. Failure analysis and next decisions", "",
              "1. **Gate coverage is the main observed bottleneck:** topical heading/domain lists reject useful paraphrases, accent-free and temporal/amending-law questions despite relevant retrieval. Both multi-evidence cases retrieve all gold at 5 yet refuse.",
              "2. **Cross-reference parsing:** T18 names target articles 200/210; the outer amending article is 4. The first explicit article reference drives filtering and yields no hits.",
              "3. **Partial-clause miss:** T06 retrieves the continuation but misses the beginning of the split clause at 5. T04/T11 rank neighboring chunk content first.",
              "4. **Validator gaps:** wrong documents/versions, invented clause/point locators, short fake quotes, mixed valid/invalid markers, semantic contradictions and unrecognized current-law paraphrases can survive. ID validity is not support.",
              "5. **Product fixes are proposals only:** add separately reviewed clause/version/per-claim support checks and evaluate gate/parsing changes using new independent test data. No automatic correctness gain is claimed.",
              "6. **Review before conclusions:** complete label/adjudication and human citation support; generated answer correctness/applicability remain unresolved. No accuracy claim beyond provisional stored-version retrieval.", "",
              "## Reproduce and review", "", "```bash",
              "uv run --frozen python -m evaluation.scripts.build_dataset",
              "uv run --frozen python -m evaluation.scripts.run_offline",
              "uv run --frozen python -m evaluation.scripts.prepare_live_plan",
              "uv run --frozen pytest -q --junitxml=evaluation/reports/pytest.xml",
              "uv run --frozen python -m evaluation.scripts.review_artifacts", "```", "",
              "Primary reports: `evaluation/reports/offline-report.md`, `offline-results.json`, `per-question.csv`.",
              "Review inputs: `evaluation/datasets/label-review.csv`, `answer-review.csv`, `citation-review.csv`; readable evidence: `source-review.md`.", "",
              "### Presentation summary", "",
              f"> Zero Gemini requests. {results['dataset']['total']} new cases ({results['dataset']['provisional']} provisional), {results['dataset']['held_out']} held-out. Provisional Recall@5={metric_value('recall@5', 3)}; {matrix['answerable_accepted']}/{matrix['answerable_accepted'] + matrix['answerable_refused']} supported questions pass the gate, with {matrix['unsupported_accepted']}/{matrix['unsupported_accepted'] + matrix['unsupported_refused']} unsupported questions also passing. Citation IDs resolve but do not guarantee legal support. Independent answer review is still required. **PARTIALLY EVALUATED.**"]
    (ROOT / "docs/evaluation/results-summary.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
