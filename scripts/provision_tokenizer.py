"""Provision ONLY the pinned tokenizer files for the Vietnamese embedding model.

Authorized scope: `AITeamVN/Vietnamese_Embedding_v2@18b44161e041bf1d3a333ab5144b5b7b93f914d2`
tokenizer configuration only. This script:

* downloads four allowlisted tokenizer files, never weights/ONNX/remote code;
* verifies declared sizes and records SHA-256 for every file;
* writes a standard Hugging Face cache layout under ``--cache-dir``;
* can verify the tokenizer offline and print deterministic tokenization evidence.

It never loads a model, never calls inference, and never touches corpus/review state.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

from batch.contracts import MODEL_ID, MODEL_REVISION

REPO = "AITeamVN/Vietnamese_Embedding_v2"
FILES = ("tokenizer_config.json", "tokenizer.json", "sentencepiece.bpe.model", "special_tokens_map.json")
CACHE_PREFIX = "models--AITeamVN--Vietnamese_Embedding_v2"
SAMPLE = "Người sử dụng đất được bồi thường, hỗ trợ, tái định cư khi Nhà nước thu hồi đất."
TREE_API = f"https://huggingface.co/api/models/{REPO}/tree/{MODEL_REVISION}?recursive=true"


def _get(url, *, timeout=120):
    request = urllib.request.Request(url, headers={"User-Agent": "local-tokenizer-provision/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"Download failed with HTTP {response.status}")
        return response.read()


def _sha256(value):
    return hashlib.sha256(value).hexdigest()


def tree():
    data = json.loads(_get(TREE_API))
    return {entry["path"]: entry for entry in data if entry.get("type") == "file"}


def provision(cache_dir):
    if MODEL_REVISION != "18b44161e041bf1d3a333ab5144b5b7b93f914d2":
        raise SystemExit("Refusing: batch.contracts.MODEL_REVISION is not the reviewed pin")
    catalog = tree()
    missing = [name for name in FILES if name not in catalog]
    if missing:
        raise SystemExit(f"Refusing: tokenizer files absent from the pinned revision: {missing}")
    snapshot = Path(cache_dir) / CACHE_PREFIX / "snapshots" / MODEL_REVISION
    snapshot.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(cache_dir) / CACHE_PREFIX / "provision.json"
    pinned = {}
    if manifest_path.is_file():
        previous = json.loads(manifest_path.read_text())
        if previous.get("revision") == MODEL_REVISION:
            pinned = {item["path"]: item["sha256"] for item in previous.get("files", [])}
    records = []
    for name in FILES:
        expected = catalog[name]["size"]
        if expected > 64 * 1024 * 1024:
            raise SystemExit(f"Refusing oversized tokenizer file: {name}")
        target = snapshot / name
        if target.is_file():
            payload = target.read_bytes()
        else:
            payload = _get(f"https://huggingface.co/{REPO}/resolve/{MODEL_REVISION}/{name}")
            if len(payload) != expected:
                raise SystemExit(f"Size mismatch for {name}: expected {expected}, got {len(payload)}")
            temporary = target.with_suffix(target.suffix + ".part")
            temporary.write_bytes(payload)
            temporary.replace(target)
        if len(payload) != expected:
            raise SystemExit(f"Local tokenizer file size mismatch for {name}")
        digest = _sha256(payload)
        if name in pinned and pinned[name] != digest:
            raise SystemExit(f"Existing tokenizer file hash differs from the provision manifest: {name}")
        records.append(dict(path=name, bytes=len(payload), sha256=digest,
            url=f"https://huggingface.co/{REPO}/resolve/{MODEL_REVISION}/{name}"))
    refs = Path(cache_dir) / CACHE_PREFIX / "refs"
    refs.mkdir(exist_ok=True)
    (refs / "main").write_text(MODEL_REVISION, encoding="utf-8")
    manifest = dict(model_id=MODEL_ID, revision=MODEL_REVISION, scope="tokenizer-only",
        weights_downloaded=False, remote_code=False, authentication=False,
        license_declared_by_publisher="Apache-2.0", files=records)
    (Path(cache_dir) / CACHE_PREFIX / "provision.json").write_text(
        json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return manifest, snapshot


def verify(snapshot):
    import importlib.metadata as metadata
    if metadata.version("transformers") != "4.57.3":
        raise SystemExit("transformers==4.57.3 is required for tokenizer verification")
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True,
        trust_remote_code=False, token=False)
    first = tokenizer.encode(SAMPLE, add_special_tokens=True)
    second = tokenizer.encode(SAMPLE, add_special_tokens=True)
    if first != second:
        raise SystemExit("Tokenizer is not deterministic")
    return dict(tokenizer_class=type(tokenizer).__name__, vocab_size=len(tokenizer),
        model_max_length=tokenizer.model_max_length, sample=SAMPLE, token_ids=first,
        token_count=len(first), deterministic=True,
        decoded_round_trip=tokenizer.decode(first, skip_special_tokens=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", default="data/model-cache/hub")
    parser.add_argument("--check", action="store_true", help="verify an existing cache without downloading")
    parser.add_argument("--verify", action="store_true", help="load the tokenizer offline and print evidence")
    args = parser.parse_args()
    snapshot = Path(args.cache_dir) / CACHE_PREFIX / "snapshots" / MODEL_REVISION
    if args.check:
        missing = [name for name in FILES if not (snapshot / name).is_file()]
        if missing:
            raise SystemExit(f"Missing tokenizer files: {missing}")
    else:
        manifest, snapshot = provision(args.cache_dir)
    result = dict(cache_dir=str(Path(args.cache_dir).resolve()), snapshot=str(snapshot.resolve()),
        revision=MODEL_REVISION, files=FILES, weights_downloaded=False)
    if args.verify:
        result["verification"] = verify(snapshot)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
