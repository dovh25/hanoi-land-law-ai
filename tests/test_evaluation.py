"""Evaluator correctness: known IR examples, non-circular labels and safe defaults."""
import json
import math
import csv
from copy import deepcopy

import pytest

from evaluation.scripts.metrics import aggregate, classification, percentile, retrieval_metrics
from evaluation.scripts.run_offline import ROOT, duplicate_audit, sha, validate_dataset


def test_ir_known_two_gold_example_distinguishes_hit_from_recall():
    result = retrieval_metrics(["noise", "a", "b"], ["a", "b"])
    assert result["recall@1"] == result["hit@1"] == 0
    assert result["recall@3"] == result["hit@3"] == 1
    assert result["precision@3"] == 2 / 3
    assert result["precision@5"] == 2 / 5
    assert result["mrr@5"] == .5
    assert result["ndcg@5"] == pytest.approx((1 / math.log2(3) + .5) / (1 + 1 / math.log2(3)))
    one = retrieval_metrics(["a"], ["a", "b"])
    assert one["recall@1"] == .5 and one["hit@1"] == 1
    assert one["precision@5"] == .2  # fixed-K denominator


def test_empty_and_duplicate_ir_inputs_fail_explicitly():
    for retrieved, gold in [(["a"], []), (["a", "a"], ["a"]), (["a"], ["a", "a"])]:
        with pytest.raises(ValueError):
            retrieval_metrics(retrieved, gold)
    assert all(v == 0 for v in retrieval_metrics([], ["a"]).values())


def test_refuse_everything_has_zero_answerable_coverage():
    rows = [{"answerable": True, "accepted": False}, {"answerable": False, "accepted": False}]
    metrics = classification(rows)
    assert metrics["abstention_recall"] == 1
    assert metrics["answerable_gate_coverage"] == 0
    assert metrics["false_refusal_rate"] == 1
    assert metrics["scope_accuracy"] == .5
    assert metrics["abstention_precision"] == .5
    assert classification([])["scope_accuracy"] is None


def test_empty_slice_is_not_reported_as_perfect():
    result = aggregate([])
    assert result["retrieval"] == {}
    assert result["exact_article"]["accuracy"] is None


def test_percentile_nearest_rank():
    assert percentile(list(range(1, 101)), .95) == 95


def test_source_pinned_dataset_and_no_historical_reuse():
    config = json.loads((ROOT / "evaluation/configs/offline.json").read_text())
    assert sha(ROOT / config["corpus_path"]) == config["corpus_sha256"]
    cases = [json.loads(line) for line in (ROOT / config["dataset_path"]).read_text().splitlines()]
    records = [json.loads(line) for line in (ROOT / config["corpus_path"]).read_text().splitlines()]
    validate_dataset(cases, records, config)
    assert len(cases) == 44
    assert len([c for c in cases if c["split"] == "held_out"]) == 32
    assert all(c["annotation_status"] == "provisional_source_authored" for c in cases)
    audit = duplicate_audit(cases)
    assert not audit["cross_split_token_jaccard_at_least_0.70"]
    assert not audit["historical_character_similarity_at_least_0.80"]
    assert config["external_provider_requests_allowed"] == 0


def test_citation_audit_exposes_support_and_version_gaps():
    from backend.services.mvp_corpus import MvpCorpusIndex
    from evaluation.scripts.run_offline import citation_evaluation
    report = citation_evaluation(MvpCorpusIndex.load())
    rows = {r["id"]: r for r in report["rows"]}
    assert report["citation_support_precision_human_reviewed"] is None
    assert rows["fabricated_article"]["passed"]
    # Document product defects as observations; do not improve the production validator here.
    assert rows["wrong_version"]["accepted"]
    assert rows["unsupported_claim_resolved_id"]["accepted"]
    assert not rows["wrong_cited_source_quote"]["accepted"]


def test_review_overlay_requires_explicit_identity_and_valid_ids(tmp_path, monkeypatch):
    import evaluation.scripts.run_offline as runner
    original = ROOT
    cases = [json.loads(line) for line in (original / "evaluation/datasets/cases.jsonl").read_text().splitlines()]
    records = [json.loads(line) for line in (original / "backend/resources/mvp_demo_corpus.jsonl").read_text().splitlines()]
    path = tmp_path / "evaluation/datasets/label-review.csv"
    path.parent.mkdir(parents=True)
    with (original / "evaluation/datasets/label-review.csv").open() as handle:
        reviews = list(csv.DictReader(handle))
    fields = list(reviews[0])
    def save():
        with path.open("w") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(reviews)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    save()
    assert runner.apply_reviews(deepcopy(cases), records)[0]["review_status"] == "pending_independent_human_review"
    reviews[0].update(decision="approved", reviewer="", reviewed_at="2026-10-27")
    save()
    with pytest.raises(ValueError, match="identity"):
        runner.apply_reviews(deepcopy(cases), records)
    reviews[0]["reviewer"] = "Test reviewer (synthetic test only)"
    save()
    assert runner.apply_reviews(deepcopy(cases), records)[0]["review_status"] == "human_reviewed_against_sources"
    reviews[0].update(decision="corrected", corrected_gold_ids="invented-id")
    save()
    with pytest.raises(ValueError, match="source artifact"):
        runner.apply_reviews(deepcopy(cases), records)
    reviews[0].update(corrected_gold_ids=reviews[0]["gold_ids"], expected_answerable="typo")
    save()
    with pytest.raises(ValueError, match="True or False"):
        runner.apply_reviews(deepcopy(cases), records)
