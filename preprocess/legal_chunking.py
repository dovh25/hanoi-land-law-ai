"""Deterministic citation-preserving extension of ViLeXa's hierarchical chunking."""
from batch.contracts import SourceRecord, canonical, digest

CHUNKER_VERSION = "legal-spans-v1"


class ByteBudget:
    """Conservative offline policy, NOT the checkpoint tokenizer or model inference."""
    identity = "utf8-byte-budget-v1"

    def count(self, text):
        return len(text.encode("utf-8")) + 2


class CachedTokenizerBudget:
    """Pinned checkpoint tokenizer loaded strictly offline; no weights/config or remote code."""
    def __init__(self):
        from importlib.metadata import version
        from pathlib import Path
        if version("transformers") != "4.57.3":
            raise ValueError("Use pinned transformers 4.57.3 before generating canonical chunks")
        from huggingface_hub import constants
        from batch.contracts import MODEL_ID, MODEL_REVISION
        snapshot = (Path(constants.HF_HUB_CACHE) / f"models--{MODEL_ID.replace('/', '--')}"
                    / "snapshots" / MODEL_REVISION)
        required = ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "sentencepiece.bpe.model")
        missing = [name for name in required if not (snapshot / name).is_file()]
        if missing:
            raise ValueError("Pinned tokenizer snapshot incomplete; run scripts/provision_tokenizer.py with "
                             "HF_HOME=data/model-cache (tokenizer files only, no weights)")
        # Load the tokenizer class directly: AutoTokenizer would also require the model config,
        # which is outside the authorized tokenizer-only provisioning scope.
        from transformers import XLMRobertaTokenizerFast
        self.snapshot = snapshot
        self.tokenizer = XLMRobertaTokenizerFast.from_pretrained(str(snapshot),
            local_files_only=True, trust_remote_code=False, token=False)
        if len(self.tokenizer) != 250002 or self.tokenizer.model_max_length != 8192:
            raise ValueError("Pinned tokenizer identity differs from the reviewed metadata; reprovision")
        self.identity = f"{MODEL_ID}@{MODEL_REVISION}"

    def count(self, text):
        return len(self.tokenizer.encode(text, add_special_tokens=True, truncation=False))


def chunk_id(pv_id, source_hash, start, end, context, tokenizer_id, preprocessing):
    return digest(canonical([pv_id, source_hash, start, end, context, CHUNKER_VERSION, tokenizer_id, preprocessing]))


def chunk_provision(pv, context, model, budget, *, max_tokens=512):
    if not 32 <= max_tokens <= model.max_tokens:
        raise ValueError("Choose a token budget from 32 to the model maximum")
    if budget.count(context + "\n") >= max_tokens - 8:
        raise ValueError("Parent headings exceed chunk budget; review headings or increase token budget")
    text, start, chunks = pv.text, 0, []
    while start < len(text):
        # Find a bounded prefix, then prefer paragraph/sentence boundaries. Never discard whitespace.
        end = start
        while end < len(text) and end - start < 15000:
            candidate = min(len(text), end + 128)
            if budget.count(context + "\n" + text[start:candidate]) <= max_tokens:
                end = candidate
            else:
                for last in range(end + 1, candidate + 1):
                    if budget.count(context + "\n" + text[start:last]) > max_tokens: break
                    end = last
                break
        if end == start: raise ValueError("Cannot fit source character with parent headings; increase budget")
        if end < len(text):
            boundaries = [text.rfind(sep, start, end) + len(sep) for sep in ("\n", ". ", "; ")]
            preferred = max(boundaries)
            if preferred > start + (end - start) // 2: end = preferred
        value = context + "\n" + text[start:end]
        chunks.append(SourceRecord(chunk_id=chunk_id(pv.id, pv.text_sha256, start, end, context,
            budget.identity, model.preprocessing_version), document_version_id=pv.document_version_id,
            provision_version_id=pv.id, text=value, text_sha256=digest(value), source_start=start,
            source_end=end, source_text_sha256=pv.text_sha256, context=context,
            chunker_version=CHUNKER_VERSION, tokenizer_id=budget.identity))
        start = end
    return chunks


def provision_context(session, pv):
    from backend.db.models.legal import DocumentVersion, LegalProvision, ProvisionVersion
    from sqlalchemy import select
    headings = []
    parent = pv.parent_provision_id
    while parent:
        ancestor = session.scalar(select(ProvisionVersion).where(
            ProvisionVersion.document_version_id == pv.document_version_id, ProvisionVersion.provision_id == parent))
        headings.append((ancestor.structured_content or {}).get("heading", session.get(LegalProvision, parent).locator))
        parent = ancestor.parent_provision_id
    title = session.get(DocumentVersion, pv.document_version_id).title
    return " | ".join([title, *reversed(headings)])
