"""Optional interactive GPU/CPU experiment; not imported by production chat."""
import math
import re
import time


def load_reranker(model_id, revision, *, device="cpu", allow_downloads=False):
    if not model_id or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Review a model license and supply an exact 40-character commit revision")
    if device not in {"cpu", "cuda"}:
        raise ValueError("Choose CPU or CUDA explicitly")
    from huggingface_hub import snapshot_download
    from sentence_transformers import CrossEncoder
    path = snapshot_download(model_id, revision=revision, local_files_only=not allow_downloads, token=False)
    return CrossEncoder(path, device=device, trust_remote_code=False)


def evaluate_pairs(predictor, pairs, *, batch_size=8, max_pairs=128):
    if not pairs or len(pairs) > max_pairs or not 1 <= batch_size <= 32:
        raise ValueError("Choose a bounded interactive evaluation")
    if any(len(pair) != 2 or any(not isinstance(text, str) or len(text) > 16000 for text in pair) for pair in pairs):
        raise ValueError("Each pair must contain bounded query and passage text")
    started = time.monotonic()
    scores = []
    for offset in range(0, len(pairs), batch_size):
        scores.extend(float(score) for score in predictor.predict(pairs[offset:offset + batch_size]))
    if len(scores) != len(pairs) or not all(math.isfinite(score) for score in scores):
        raise ValueError("Invalid reranker scores")
    return {"scores": scores, "ranked_indices": sorted(range(len(scores)), key=lambda i: scores[i], reverse=True),
            "elapsed_seconds": time.monotonic() - started, "processed_pairs": len(scores)}
