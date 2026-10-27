"""Small, dependency-free IR definitions with explicit empty-set semantics."""
import math
import random
import statistics


def retrieval_metrics(retrieved, gold):
    if not gold:
        raise ValueError("Negative cases are not retrieval-recall observations")
    if len(retrieved) != len(set(retrieved)) or len(gold) != len(set(gold)):
        raise ValueError("Evidence IDs must be unique")
    relevant = set(gold)
    result = {}
    for k in (1, 3, 5):
        found = len(set(retrieved[:k]) & relevant)
        result[f"recall@{k}"] = found / len(relevant)
        result[f"hit@{k}"] = float(found > 0)
        if k in (3, 5):
            result[f"precision@{k}"] = found / k
    result["mrr@5"] = next((1 / rank for rank, item in enumerate(retrieved[:5], 1)
                             if item in relevant), 0.0)
    dcg = sum(1 / math.log2(rank + 1) for rank, item in enumerate(retrieved[:5], 1)
              if item in relevant)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(5, len(relevant)) + 1))
    result["ndcg@5"] = dcg / ideal
    return result


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def classification(rows):
    # Positive class = answerable / accepted for generation; NOT a generated correct answer.
    tp = sum(r["answerable"] and r["accepted"] for r in rows)
    fn = sum(r["answerable"] and not r["accepted"] for r in rows)
    fp = sum(not r["answerable"] and r["accepted"] for r in rows)
    tn = sum(not r["answerable"] and not r["accepted"] for r in rows)
    return {
        "confusion_matrix": {"answerable_accepted": tp, "answerable_refused": fn,
                             "unsupported_accepted": fp, "unsupported_refused": tn},
        "scope_accuracy": ratio(tp + tn, len(rows)),
        "unsupported_rejection_rate": ratio(tn, tn + fp),
        "abstention_precision": ratio(tn, tn + fn),
        "abstention_recall": ratio(tn, tn + fp),
        "false_refusal_rate": ratio(fn, tp + fn),
        "unsupported_gate_acceptance_rate": ratio(fp, fp + tn),
        "answerable_gate_coverage": ratio(tp, tp + fn),
        "generated_incorrect_answer_acceptance_rate": None,
    }


def aggregate(rows, *, resamples=2000, seed=20261027):
    answerable = [r for r in rows if r["answerable"]]
    summary = {"cases": len(rows), "answerable": len(answerable),
               "classification": classification(rows), "retrieval": {}, "bootstrap_95_ci": {}}
    if answerable:
        for metric in answerable[0]["metrics"]:
            values = [r["metrics"][metric] for r in answerable]
            summary["retrieval"][metric] = statistics.mean(values)
            if len(values) >= 10:
                rng = random.Random(seed)
                means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(resamples))
                summary["bootstrap_95_ci"][metric] = [means[int(.025 * resamples)], means[int(.975 * resamples)]]
    direct = [r for r in rows if r["exact_article_correct"] is not None]
    summary["exact_article"] = {"correct": sum(r["exact_article_correct"] for r in direct),
                                 "total": len(direct),
                                 "accuracy": ratio(sum(r["exact_article_correct"] for r in direct), len(direct))}
    return summary


def percentile(values, p):
    """Nearest-rank sample percentile; no interpolation."""
    return sorted(values)[max(0, math.ceil(p * len(values)) - 1)]
