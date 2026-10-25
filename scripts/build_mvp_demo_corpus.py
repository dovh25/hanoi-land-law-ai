"""Build the isolated MVP_DEMO_CORPUS retrieval artifact from reviewed-source stages.

This is deliberately separate from the strict Phase D publication path. It selects only
complete, technically validated standalone stages, preserves exact source spans and official
metadata, and labels every chunk ``validity_status=unknown``. It never approves legal
validity, seals a release, writes the legal database, or indexes Qdrant.

Run from the repository root:

    uv run --frozen python scripts/build_mvp_demo_corpus.py

Outputs (safe to commit; contains no PDFs, secrets, or embeddings):

    backend/resources/mvp_demo_corpus.jsonl
    backend/resources/mvp_demo_corpus.manifest.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from batch.contracts import canonical, digest
from batch.files import atomic_bytes, file_hash
from law_crawler.quality import inventory
from preprocess.legal_chunking import CHUNKER_VERSION, chunk_provision
from preprocess.offline_ingestion import load_stage

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = ROOT / "data/phase-d-corpus-v2"
DEFAULT_OUTPUT = ROOT / "backend/resources"

# Only standalone, technically validated stages are eligible. The other requested Phase D
# documents are multipart gazette continuations or quarantined and are intentionally excluded.
SELECTED = {
    "43/2024/QH15": "7d6545c477d531ffa0345d5045ac18c0ba2a3b9e3d8b1b875912b7313193fb89",
    "88/2024/NĐ-CP": "2c9ed6d69894410ae68cbb8fa97a76252831b399f1589e26b5d08e7786aa9a02",
}
EXCLUDED = {
    "31/2024/QH15": "Only multipart gazette continuations are validated; the final part is quarantined, so no complete standalone rendition is available.",
    "101/2024/NĐ-CP": "Validated stages are separate gazette parts; the annex/form continuation is not a complete operative instrument.",
    "102/2024/NĐ-CP": "The continuation part (Công báo 933+934) is quarantined; the main part ends with a continuation marker.",
    "133/VBHN-VPQH": "Validated stages are separate consolidated-law parts with ambiguous ordering; assembly was not verified.",
}
MAX_CHUNK_BYTES = 1800
MVP_PREPROCESSING = "mvp-demo-v1"


class MvpByteBudget:
    """Deterministic character transport budget for the demo index only (not a model tokenizer)."""

    identity = "mvp-utf8-byte-budget-v1"

    def count(self, text: str) -> int:
        return len(text.encode("utf-8")) + 2


MVP_MODEL = SimpleNamespace(max_tokens=4096, preprocessing_version=MVP_PREPROCESSING)


def _article_number(heading: str) -> str | None:
    import re

    match = re.match(r"^Điều\s+(\d+[a-zđ]?)[.:]", heading.strip(), re.I)
    return f"Điều {match.group(1)}" if match else None


def _ancestor_headings(nodes, index):
    values = []
    parent = nodes[index].get("parent")
    while parent is not None:
        values.append(nodes[parent]["heading"])
        parent = nodes[parent].get("parent")
    return list(reversed(values))


def _subtree_end(nodes, index):
    """End offset of the article including every descendant clause/point span.

    Parsed article nodes cover only their heading; operative text lives in child nodes,
    so a plain ``node['end']`` slice would index headings without any legal content.
    """
    end = nodes[index]["end"]
    for child in nodes[index + 1:]:
        parent = child.get("parent")
        in_subtree = False
        while parent is not None:
            if parent == index:
                in_subtree = True
                break
            parent = nodes[parent].get("parent")
        if not in_subtree:
            break
        end = max(end, child["end"])
    return end


def build(workspace: Path = DEFAULT_WORKSPACE) -> tuple[list[dict], dict]:
    quality = inventory(workspace)
    rows = {row["stage_id"]: row for row in quality["rows"]}
    text = workspace / "canonical.sqlite3"
    if text.exists():
        # The demo builder never modifies the canonical database; this is only a guard.
        before_hash = file_hash(text)
    else:
        before_hash = None

    records: list[dict] = []
    documents: list[dict] = []
    for number, stage_id in SELECTED.items():
        row = rows.get(stage_id)
        if not row:
            raise ValueError(f"{number}: selected stage is absent from the workspace inventory")
        if not row.get("release_candidate"):
            raise ValueError(f"{number}: stage is not a complete standalone release candidate")
        stage = load_stage(workspace, stage_id)
        metadata = stage["metadata"]
        if stage["status"] != "pending" or stage["quality"]["state"] != "validated_pending_legal_review":
            raise ValueError(f"{number}: stage did not pass the technical extraction gate")
        raw = workspace / stage["raw_path"]
        if not raw.is_file() or file_hash(raw) != stage["raw_sha256"]:
            raise ValueError(f"{number}: preserved artifact hash does not match the stage")
        if stage["parsed"]["text_sha256"] != digest(stage["parsed"]["text"]):
            raise ValueError(f"{number}: parsed text hash is inconsistent")
        if "\ufffd" in stage["parsed"]["text"] or "\x00" in stage["parsed"]["text"]:
            raise ValueError(f"{number}: replacement/control characters in parsed text")

        nodes = stage["parsed"]["nodes"]
        parsed_text = stage["parsed"]["text"]
        document_version_id = digest(canonical(["mvp-document-version", stage_id]))
        document_chunks = 0
        for index, node in enumerate(nodes):
            if node["kind"] != "article":
                continue
            article_start = node["start"]
            article_end = _subtree_end(nodes, index)
            article_text = parsed_text[article_start:article_end]
            if not article_text.strip():
                raise ValueError(f"{number}: empty article span at {node['locator']}")
            article_number = _article_number(node["heading"])
            if not article_number:
                raise ValueError(f"{number}: unparseable article heading at {node['locator']}")
            headings = _ancestor_headings(nodes, index)
            context = " | ".join([f"{number} — {metadata['title']}", *headings, node["heading"]])
            provision_id = digest(canonical(["mvp-provision", stage_id, node["locator"]]))
            pv = SimpleNamespace(id=provision_id, document_version_id=document_version_id,
                text=article_text, text_sha256=digest(article_text))
            chunks = chunk_provision(pv, context, MVP_MODEL, MvpByteBudget(), max_tokens=MAX_CHUNK_BYTES)
            if "".join(article_text[c.source_start:c.source_end] for c in chunks) != article_text:
                raise ValueError(f"{number}: article chunking is not lossless at {node['locator']}")
            for chunk in chunks:
                absolute_start = article_start + chunk.source_start
                absolute_end = article_start + chunk.source_end
                if absolute_start < article_start or absolute_end > article_end:
                    raise ValueError(f"{number}: chunk span escapes the article")
                records.append(dict(
                    chunk_id=chunk.chunk_id,
                    document_id=metadata["official_identifier"],
                    document_number=number,
                    document_title=metadata["title"],
                    document_type=metadata["document_type"],
                    issuing_authority=metadata["issuing_authority"],
                    jurisdiction=metadata["jurisdiction"],
                    source_url=metadata["source_url"],
                    source_start=absolute_start,
                    source_end=absolute_end,
                    page=node.get("page"),
                    article_locator=node["locator"],
                    article_number=article_number,
                    article_heading=node["heading"],
                    heading_path=" | ".join(headings),
                    context=chunk.context,
                    source_text=article_text[chunk.source_start:chunk.source_end],
                    text=chunk.text,
                    text_sha256=chunk.text_sha256,
                    chunker_version=CHUNKER_VERSION,
                    tokenizer_id=MvpByteBudget.identity,
                    stage_id=stage_id,
                    raw_sha256=stage["raw_sha256"],
                    parsed_text_sha256=stage["parsed"]["text_sha256"],
                    parser_version=stage["parser_version"],
                    quality_gate_version=stage["quality_gate_version"],
                    review_status="technical_validation_only",
                    validity_status="unknown",
                    corpus_label="MVP_DEMO_CORPUS",
                    partial=False,
                ))
                document_chunks += 1
        if document_chunks == 0:
            raise ValueError(f"{number}: no article chunks produced")
        documents.append(dict(
            number=number,
            stage_id=stage_id,
            official_identifier=metadata["official_identifier"],
            title=metadata["title"],
            document_type=metadata["document_type"],
            issuing_authority=metadata["issuing_authority"],
            source_url=metadata["source_url"],
            raw_sha256=stage["raw_sha256"],
            parsed_text_sha256=stage["parsed"]["text_sha256"],
            acquired_at=metadata["acquired_at"],
            issuance_date=metadata.get("issuance_date"),
            chunks=document_chunks,
            validity_status="unknown",
            review_status="technical_validation_only",
            annex_excluded=any(n["kind"] == "annex" for n in stage["parsed"]["nodes"]),
        ))

    if len({record["chunk_id"] for record in records}) != len(records):
        raise ValueError("Duplicate demo chunk IDs")
    for record in records:
        if record["validity_status"] != "unknown" or record["partial"]:
            raise ValueError("MVP demo chunks must stay unknown-validity and non-partial")
        if record["document_number"] not in SELECTED:
            raise ValueError("Unexpected document in MVP corpus")
    records.sort(key=lambda row: (row["document_number"], row["source_start"], row["chunk_id"]))
    payload = "".join(canonical(record) + "\n" for record in records).encode("utf-8")
    manifest = dict(
        schema_version=1,
        corpus="MVP_DEMO_CORPUS",
        purpose="research_retrieval_demo_only",
        publication_status="not_published_not_current_law",
        validity_status="unknown",
        review_status="technical_validation_only",
        strict_phase_d_gates_unchanged=True,
        generated_by="scripts/build_mvp_demo_corpus.py",
        chunker_version=CHUNKER_VERSION,
        tokenizer_id=MvpByteBudget.identity,
        max_chunk_bytes=MAX_CHUNK_BYTES,
        chunk_count=len(records),
        document_count=len(documents),
        records_sha256=digest(payload.decode("utf-8")),
        documents=documents,
        excluded=EXCLUDED,
        notes=[
            "MVP_DEMO_CORPUS is isolated from the reviewed/current-law publication path.",
            "Only complete standalone stages with validated extraction are indexed.",
            "Annex/form templates are excluded from operative retrieval.",
            "Every chunk keeps an exact parsed-text span and the official source page URL.",
            "Legal validity is unknown for every document; the UI must disclose this.",
            "No embeddings, Qdrant index, PDFs, or secrets are included in this artifact.",
        ],
    )
    if before_hash is not None and file_hash(text) != before_hash:
        raise ValueError("Build unexpectedly modified the canonical database")
    return records, manifest


def write(workspace: Path = DEFAULT_WORKSPACE, output: Path = DEFAULT_OUTPUT) -> dict:
    records, manifest = build(workspace)
    output.mkdir(parents=True, exist_ok=True)
    payload = "".join(canonical(record) + "\n" for record in records).encode("utf-8")
    atomic_bytes(output / "mvp_demo_corpus.jsonl", payload)
    atomic_bytes(output / "mvp_demo_corpus.manifest.json", (canonical(manifest) + "\n").encode())
    return dict(corpus=manifest["corpus"], documents=manifest["document_count"],
        chunks=manifest["chunk_count"], records_sha256=manifest["records_sha256"],
        path=(output / "mvp_demo_corpus.jsonl").as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(canonical(write(args.workspace, args.output)))


if __name__ == "__main__":
    main()
