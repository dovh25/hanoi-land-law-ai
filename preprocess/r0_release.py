"""Build a RESEARCH_ONLY R0 draft. Never approves, seals, indexes or publishes.

The draft is a plan plus honest eligibility report. It is regenerated from stage/review
state, binds every document to raw/text hashes, and refuses to claim validity or readiness
that the review journals do not support.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

from sqlalchemy import text

from batch.contracts import MODEL_ID, MODEL_REVISION, SYNTHETIC_SPEC, VIETNAMESE_SPEC, canonical, digest
from batch.files import export_input, validate_input, atomic_bytes
from law_crawler.quality import inventory
from preprocess.legal_chunking import CHUNKER_VERSION, ByteBudget, CachedTokenizerBudget, chunk_provision
from preprocess.offline_ingestion import (CATEGORY_TITLES, CATEGORIES, database, eligibility, load_stage,
    require_workspace, stage_lineage)

R0_STAGES = {
    "43/2024/QH15": "7d6545c477d531ffa0345d5045ac18c0ba2a3b9e3d8b1b875912b7313193fb89",
    "88/2024/NĐ-CP": "2c9ed6d69894410ae68cbb8fa97a76252831b399f1589e26b5d08e7786aa9a02",
}
RELEASE_NAME = "phase-d2-r0-research-v1"
TOKENIZER_HOME = "data/model-cache"
MAX_TOKENS = 512
GATE_LABELS = {
    "not_superseded": "active stage lineage",
    "not_quarantined": "extraction not quarantined",
    "artifact_binding_current": "artifact binding is current",
    "source_identity_approved": CATEGORY_TITLES["A_source_identity"],
    "extraction_approved": CATEGORY_TITLES["B_extraction_quality"],
    "legal_metadata_approved": CATEGORY_TITLES["C_legal_metadata"],
    "validity_recorded": CATEGORY_TITLES["D_applicability_validity"],
    "validity_not_rejected": "validity not rejected",
    "legacy_review_approved": "explicit whole-stage review",
    "legacy_validity_in_force": "current-law validity (in force)",
    "validity_in_force": "current-law validity (in force)",
}
CURRENT_LAW_ONLY = {"legacy_validity_in_force", "validity_in_force"}


def _counts(workspace):
    tables = ("legal_documents", "document_versions", "legal_provisions", "provision_versions",
              "source_artifacts", "acquisition_manifests", "legal_relationships",
              "territorial_applicability", "corpus_releases", "corpus_release_documents")
    with database(workspace) as factory, factory() as session:
        values = {name: session.execute(text(f"SELECT count(*) FROM {name}")).scalar() for name in tables}
        releases = session.execute(text("SELECT id, name, published_at FROM corpus_releases ORDER BY name")).all()
    return dict(rows=values, releases=[dict(id=row[0], name=row[1], published=row[2] is not None) for row in releases])


def _tokenizer():
    import os
    previous = os.environ.get("HF_HOME")
    os.environ["HF_HOME"] = TOKENIZER_HOME
    try:
        budget = CachedTokenizerBudget()
    finally:
        if previous is None:
            os.environ.pop("HF_HOME", None)
        else:
            os.environ["HF_HOME"] = previous
    return budget


def _contract_checks():
    document = json.loads(Path("docs/model-compatibility-vietnamese-v2.json").read_text())
    checks = dict(
        model_id_pinned=VIETNAMESE_SPEC.model_id == MODEL_ID,
        revision_pinned=VIETNAMESE_SPEC.model_revision == MODEL_REVISION,
        dense_dimension_1024=VIETNAMESE_SPEC.dimension == 1024,
        dtype_float32=VIETNAMESE_SPEC.dtype == "float32",
        pooling_cls=VIETNAMESE_SPEC.pooling == "cls",
        normalize_embeddings=VIETNAMESE_SPEC.normalized is True,
        max_tokens_within_model=VIETNAMESE_SPEC.max_tokens == 2048,
        compatibility_doc_dimension=document.get("dimension") == 1024,
        compatibility_doc_cls="CLS" in document.get("pooling", ""),
        compatibility_doc_normalized="Normalize" in document.get("normalization", ""),
        compatibility_doc_model=document.get("model_id") == MODEL_ID,
        compatibility_doc_revision=document.get("revision") == MODEL_REVISION,
        synthetic_contract_separate=SYNTHETIC_SPEC.pooling == "synthetic_hash" and SYNTHETIC_SPEC.dimension == 8,
    )
    return checks


def _token_stats(stage, budget):
    nodes = stage["parsed"]["nodes"]
    text = stage["parsed"]["text"]
    values, total = [], 0
    for node in nodes:
        content = text[node["start"]:node["end"]]
        tokens = budget.count(content)
        total += tokens
        values.append(dict(locator=node["locator"], kind=node["kind"], tokens=tokens, characters=len(content)))
    worst = max(values, key=lambda item: item["tokens"]) if values else None
    return dict(provision_tokens=values, total_tokens=total, worst_provision=worst,
        over_chunk_budget=sum(item["tokens"] > MAX_TOKENS for item in values),
        chunk_count_if_whole=None, note="Exact chunk IDs/count are assigned only by seal/materialize")


def _tokenizer_smoke(budget):
    text = "1. Nội dung bồi thường, hỗ trợ, tái định cư khi Nhà nước thu hồi đất. " * 60
    pv = SimpleNamespace(id="readiness-only", document_version_id="readiness-only",
                         text=text, text_sha256=digest(text))
    first = chunk_provision(pv, "READINESS | Điều 1", VIETNAMESE_SPEC, budget, max_tokens=MAX_TOKENS)
    second = chunk_provision(pv, "READINESS | Điều 1", VIETNAMESE_SPEC, budget, max_tokens=MAX_TOKENS)
    return dict(deterministic=first == second, chunks=len(first),
        max_tokens_used=max(budget.count(row.text) for row in first),
        lossless="".join(text[row.source_start:row.source_end] for row in first) == text,
        unique_ids=len({row.chunk_id for row in first}) == len(first),
        chunker_version=CHUNKER_VERSION)


def _manifest_round_trip(budget):
    from batch.contracts import SourceRecord
    text = "Điều 1. Kiểm tra hợp đồng xuất embedding, không phải dữ liệu pháp luật."
    record = SourceRecord(chunk_id=digest(canonical(["readiness", text])),
        document_version_id="readiness-document", provision_version_id="readiness-provision",
        text=text, text_sha256=digest(text), source_start=0, source_end=len(text),
        source_text_sha256=digest(text), context="READINESS", chunker_version=CHUNKER_VERSION,
        tokenizer_id=budget.identity)
    with tempfile.TemporaryDirectory(prefix="r0-contract-") as directory:
        target = Path(directory) / "input"
        export_input(target, [record], release_id="readiness-only",
            release_sha256="0" * 64, is_synthetic=True, model=VIETNAMESE_SPEC)
        manifest = validate_input(target)
        records = [json.loads(line) for line in (target / "records.jsonl").read_text().splitlines()]
    return dict(status="pass", record_count=manifest.record_count, model=manifest.model.model_dump(),
        records_sha256=manifest.records_sha256, batch_id=manifest.batch_id,
        note="Temporary contract round-trip only; no corpus chunk/vector was written",
        record=records[0])


def _embedding(budget, tokenizer_error):
    checks = _contract_checks()
    result = dict(contract=VIETNAMESE_SPEC.model_dump(), checks=checks,
        checks_passed=all(checks.values()), tokenizer=None, blockers=[])
    if tokenizer_error:
        result["blockers"].append(tokenizer_error)
    else:
        result["tokenizer"] = dict(identity=budget.identity, snapshot=str(budget.snapshot),
            vocab_size=len(budget.tokenizer), model_max_length=budget.tokenizer.model_max_length,
            weights_loaded=False, remote_code=False)
        result["chunk_smoke"] = _tokenizer_smoke(budget)
        if not all((result["chunk_smoke"]["deterministic"], result["chunk_smoke"]["lossless"],
                    result["chunk_smoke"]["unique_ids"])):
            result["blockers"].append("Chunk determinism/losslessness/unique-ID check failed")
        result["manifest_round_trip"] = _manifest_round_trip(budget)
        if result["manifest_round_trip"]["status"] != "pass":
            result["blockers"].append("Batch manifest/checksum round-trip failed")
    if not all(checks.values()):
        result["blockers"].append("Model/dense contract checks failed")
    result["status"] = "ready_after_seal" if not result["blockers"] else "blocked"
    return result


def draft(workspace, stage_ids=None):
    root = require_workspace(workspace)
    stages_by_id, superseded = stage_lineage(root)
    selected = list(stage_ids or R0_STAGES.values())
    if len(set(selected)) != len(selected): raise ValueError("Duplicate R0 stage id")
    quality = inventory(root)
    quality_rows = {row["stage_id"]: row for row in quality["rows"]}
    review = {row["stage_id"]: row for row in eligibility(root, selected)["rows"]}

    tokenizer_error = None
    try:
        budget = _tokenizer()
    except Exception as exc:
        budget = ByteBudget()
        tokenizer_error = f"Pinned tokenizer unavailable: {type(exc).__name__}; provision tokenizer files before sealing"
        if "HF_HOME" not in str(exc):
            tokenizer_error += " (set HF_HOME=data/model-cache and run scripts/provision_tokenizer.py)"

    documents, blockers = [], []
    for stage_id in selected:
        if stage_id not in stages_by_id: raise ValueError("R0 stage is not present; restore or reparse the artifact")
        stage = stages_by_id[stage_id]
        if stage_id in superseded: raise ValueError("R0 stage is superseded; select the active stage")
        if stage["metadata"].get("is_synthetic"):
            raise ValueError("R0 research draft refuses synthetic stages; use the synthetic smoke path")
        row = quality_rows.get(stage_id, {})
        if not row.get("release_candidate"):
            raise ValueError("R0 stage is quarantined or a fragment; do not draft a release from it")
        gate = review[stage_id]
        stats = _token_stats(stage, budget)
        metadata = stage["metadata"]
        documents.append(dict(
            stage_id=stage_id,
            official_identifier=metadata["official_identifier"],
            official_number=metadata["official_number"],
            title=metadata["title"],
            issuer=metadata["issuing_authority"],
            jurisdiction=metadata["jurisdiction"],
            issuance_date=metadata["issuance_date"],
            publication_date=metadata.get("publication_date"),
            source_url=metadata["source_url"],
            raw_sha256=stage["raw_sha256"],
            raw_path=stage["raw_path"],
            original_filename=metadata["file"],
            parsed_text_sha256=stage["parsed"]["text_sha256"],
            extracted_characters=len(stage["parsed"]["text"]),
            parser_version=stage["parser_version"],
            quality_gate_version=stage.get("quality_gate_version"),
            counts=stage["quality"]["counts"],
            extraction_state=stage["quality"]["state"],
            validity=metadata.get("legal_validity", "unknown"),
            human_reviewed=False,
            token_stats=stats,
            approvals={name: (gate["categories"][name] or {}).get("decision", "pending") for name in CATEGORIES},
            gates=gate["gates"],
            parity="UNKNOWN — no consolidated/current text comparison performed",
        ))
        blockers.extend(f"{metadata['official_number']}: {GATE_LABELS.get(key, key)}"
                        for key in gate["blocking"] if key not in CURRENT_LAW_ONLY)
    if blockers:
        blockers = sorted(set(blockers))

    embedding = _embedding(budget, tokenizer_error)
    if embedding["status"] != "ready_after_seal":
        blockers.append("Embedding export not ready: " + "; ".join(embedding["blockers"]))
    blockers = sorted(set(blockers))

    commands = dict(
        eligibility=(f"uv run --frozen python -m preprocess.offline_cli --workspace {workspace} "
                    f"review-eligibility --stages {' '.join(selected)}"),
        seal=(f"HF_HOME={TOKENIZER_HOME} uv run --frozen python -m preprocess.offline_cli --workspace {workspace} "
              f"seal --name {RELEASE_NAME} --stages {' '.join(selected)} --purpose research "
              f"--cached-tokenizer --max-tokens {MAX_TOKENS} --approve-publication"),
        export=(f"HF_HOME={TOKENIZER_HOME} uv run --frozen python -m preprocess.offline_cli --workspace {workspace} "
                f"export --release <sealed-release-hash> --destination <fresh-directory>"),
    )
    result = dict(
        schema_version=1,
        draft_id=digest(canonical(dict(stages=selected, name=RELEASE_NAME, embedding=embedding["status"],
            blockers=blockers))),
        generated_at=datetime.now(timezone.utc).isoformat(),
        state="DRAFT",
        research_only=True,
        purpose="research",
        release_name=RELEASE_NAME,
        human_reviewed=False,
        approved_publication=False,
        indexed=False,
        published=False,
        legal_validity="unknown",
        current_law_ready=all(row["current_law_seal_ready"] for row in review.values()) and bool(review),
        notice=("No legal validity, completeness, or current-law sufficiency is claimed. "
                "Sealing remains blocked until every required human decision exists."),
        stages=selected,
        documents=documents,
        review_eligibility=review,
        canonical_state=_counts(root),
        embedding_export=embedding,
        blockers=blockers,
        commands=commands,
        limitations=sorted(set(
            ["Validity is unknown for every R0 instrument; no current-law use is permitted.",
             "Publication dates are not recorded in the acquired PDFs.",
             "43/2024/QH15 is an amending instrument; it does not restate the amended laws.",
             "88/2024/NĐ-CP includes an administrative form annex excluded from operative provisions.",
             "No OCR, crawl, consolidated-text comparison or Qdrant indexing was performed.",
             "Exact chunk IDs and dense vectors are created only by the sealed export path, not by this draft."]
            + [warning for stage_id in selected for warning in stages_by_id[stage_id].get("warnings", [])])),
    )
    return result


def render(result):
    lines = [
        f"# R0 research release draft — {result['release_name']}", "",
        "> **DRAFT — RESEARCH ONLY — NOT LEGAL ADVICE — NOT REVIEWED — NOT SEALED.**",
        "> No document here is asserted to be in force, complete, or sufficient for general Hanoi advice.",
        "> Unknown validity remains unknown. Nothing is indexed or published.", "",
        f"- Draft id: `{result['draft_id']}`",
        f"- State: **{result['state']}**",
        f"- Research only: {result['research_only']}",
        f"- Human reviewed: {result['human_reviewed']}",
        f"- Indexed / published: {result['indexed']} / {result['published']}",
        f"- Current-law ready: {result['current_law_ready']}",
        f"- Embedding export: **{result['embedding_export']['status']}**", "",
        "## Documents", "",
        "| Number | Title | Stage | Articles | Validity |",
        "|---|---|---|---|---|"]
    for doc in result["documents"]:
        title = doc["title"].replace("|", "\\|")
        lines.append(f"| {doc['official_number']} | {title[:90]} | `{doc['stage_id'][:12]}…` "
                     f"| {doc['counts'].get('article', 0)} | {doc['validity']} |")
    lines += ["", "## Blockers", ""]
    lines += [f"- {value}" for value in result["blockers"]] or ["- none (unexpected: reviews exist)"]
    lines += ["", "## Embedding contract", ""]
    for key, value in result["embedding_export"]["checks"].items():
        lines.append(f"- {key}: {'pass' if value else 'FAIL'}")
    tokenizer = result["embedding_export"].get("tokenizer")
    if tokenizer:
        lines += ["", f"- Tokenizer: `{tokenizer['identity']}` (vocab {tokenizer['vocab_size']}, "
                      f"max length {tokenizer['model_max_length']}), weights loaded: {tokenizer['weights_loaded']}"]
    lines += ["", "## Exact operator sequence (only after all decisions exist)", "",
        "```bash", result["commands"]["eligibility"], "```", "",
        "After A/B/C approvals plus a recorded D decision and an explicit whole-stage review:", "",
        "```bash", result["commands"]["seal"], "```", "",
        "Then export the sealed release (this still does not index it):", "",
        "```bash", result["commands"]["export"], "```", "",
        "## Canonical persistence state", ""]
    for key, value in result["canonical_state"]["rows"].items():
        lines.append(f"- {key}: {value}")
    lines += ["", "## Limitations", ""]
    lines += [f"- {value}" for value in result["limitations"]]
    lines += ["", "_This draft performs no approval, no canonical write, no neural embedding, no Qdrant indexing._", ""]
    return "\n".join(lines)


def write(workspace, stage_ids=None, destination="reports/r0-research-draft"):
    root = require_workspace(workspace)
    result = draft(root, stage_ids)
    target = root / destination
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_bytes(target.parent / (target.name + ".json"), (canonical(result) + "\n").encode())
    atomic_bytes(target.parent / (target.name + ".md"), render(result).encode())
    return dict(draft_id=result["draft_id"], state=result["state"],
        json=(target.parent / (target.name + ".json")).relative_to(root).as_posix(),
        markdown=(target.parent / (target.name + ".md")).relative_to(root).as_posix(),
        blockers=len(result["blockers"]), embedding=result["embedding_export"]["status"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default="data/phase-d-corpus-v2")
    parser.add_argument("--stages", nargs="+")
    args = parser.parse_args()
    print(canonical(write(args.workspace, args.stages)))


if __name__ == "__main__":
    main()
