"""Human-review packets for preserved stages. No approval, sealing or legal inference.

Each packet contains a Markdown briefing plus a machine-readable checklist. Decisions are
recorded separately through ``preprocess.offline_cli`` and are bound to the exact raw and
parsed-text hashes, so a later artifact change can never inherit an earlier approval.
"""
import argparse
import json
from pathlib import Path
import re

from batch.contracts import canonical, digest
from batch.files import atomic_bytes
from law_crawler.quality import inventory
from preprocess.offline_ingestion import (CATEGORIES, CATEGORY_TITLES, category_status, eligibility,
    load_stage, require_workspace, stage_lineage, write_once)
from preprocess.legal_parser import extract, hierarchy

PACKET_VERSION = "phase-d2-review-packet-v1"
SEAL_EXAMPLE = "phase-d2-r0-research-v1"

ITEMS = {
    "A_source_identity": [
        ("A1", "Official identifier and number match the cover page, gazette header and acquisition manifest.", "identifier_number"),
        ("A2", "Document title and document type match the signed official text.", "title_type"),
        ("A3", "Issuing authority and jurisdiction match the signed/issued instrument.", "authority"),
        ("A4", "Source URL and acquisition receipt resolve to an official host and pin the retrieval.", "receipt"),
        ("A5", "Raw SHA-256 matches the preserved original; no duplicate bytes under another identifier.", "raw_hash"),
        ("A6", "The artifact is the complete standalone instrument, not an annex/continuation fragment.", "completeness"),
    ],
    "B_extraction_quality": [
        ("B1", "Every text page is present and the extraction covers the whole instrument.", "pages"),
        ("B2", "Chapter/section/article/clause/point hierarchy matches the printed structure.", "hierarchy"),
        ("B3", "Vietnamese diacritics and word spacing are intact; no replacement characters or CID glyphs.", "text"),
        ("B4", "Tables, forms and annex templates are not promoted into operative provisions.", "annex"),
        ("B5", "Stripped mastheads/page numbers did not remove legal text.", "stripped"),
        ("B6", "Article/clause/point counts reconcile with a visual page-by-page check.", "counts"),
        ("B7", "Source spans cover 100% of the extracted text and the reported text hash matches.", "spans"),
    ],
    "C_legal_metadata": [
        ("C1", "Issuance date matches the signed text.", "issuance"),
        ("C2", "Publication date / gazette number is recorded, or explicitly documented as unavailable.", "publication"),
        ("C3", "Effective-date and transitional clauses are transcribed exactly, not inferred.", "effect"),
        ("C4", "Amending/superseding relationships and amended instruments are correctly identified.", "relations"),
        ("C5", "Annexes are complete, correctly attached, and identified as templates where applicable.", "annex_meta"),
        ("C6", "Document type and consolidated/amending status are recorded correctly.", "doctype"),
    ],
    "D_applicability_validity": [
        ("D1", "Instrument-level validity (in_force / not_yet_effective / partially_expired / expired / repealed / suspended / unknown) is established from an official source.", "validity"),
        ("D2", "Effective date and any expiry/repeal date are recorded; unknown stays unknown.", "dates"),
        ("D3", "Territorial applicability (national vs Hanoi) is recorded.", "territory"),
        ("D4", "Amendments, suspensions or replacements issued after this text are checked.", "amendments"),
        ("D5", "Any provision relied on is not transitional-only or superseded.", "provisions"),
        ("D6", "No current-law claim is made while any applicability question remains open.", "current_law"),
    ],
}


def slug(stage):
    number = stage["metadata"]["official_number"]
    value = re.sub(r"[^0-9a-z]+", "-", number.casefold().replace("đ", "d")).strip("-")
    return f"{value}-{stage['raw_sha256'][:12]}"


def _receipt(root, raw_sha256):
    for path in sorted((root / "acquisitions").glob("*.json")):
        receipt = json.loads(path.read_text())
        artifacts = [a for a in receipt.get("artifacts", []) if a.get("sha256") == raw_sha256]
        if not artifacts:
            continue
        artifact = artifacts[0]
        chain = (artifact.get("http") or {}).get("chain") or []
        final = chain[-1] if chain else {}
        return dict(receipt=path.relative_to(root).as_posix(), receipt_sha256=digest(path.read_bytes()),
            retrieved_at=final.get("retrieved_at") or receipt.get("acquired_at"),
            status=final.get("status"), bytes=final.get("bytes"),
            final_url=artifact.get("final_url") or final.get("url"))
    return None


def _page_preview(blocks, page):
    text = "\n".join(block.text for block in blocks if block.page == page)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return dict(characters=len(text), first=lines[:2], last=lines[-2:])


def _samples(nodes, text):
    articles = [node for node in nodes if node["kind"] == "article"]
    if not articles:
        return []
    chosen = {0, 1, len(articles) // 2, len(articles) - 1}
    values = []
    for index in sorted(chosen):
        if 0 <= index < len(articles):
            node = articles[index]
            excerpt = text[node["start"]:node["end"]]
            values.append(dict(locator=node["locator"], heading=node["heading"], page=node["page"],
                characters=node["end"] - node["start"],
                excerpt=excerpt if len(excerpt) <= 900 else excerpt[:900] + " …"))
    annexes = [node for node in nodes if node["kind"] == "annex"]
    for node in annexes[:1]:
        excerpt = text[node["start"]:node["end"]]
        values.append(dict(locator=node["locator"], heading=node["heading"], page=node["page"],
            characters=node["end"] - node["start"], form=bool(node.get("form")),
            excerpt=excerpt if len(excerpt) <= 500 else excerpt[:500] + " …"))
    return values


def build_packet(workspace, stage_id):
    root = require_workspace(workspace)
    stages, superseded = stage_lineage(root)
    if stage_id not in stages: raise ValueError("Unknown stage; use the exact stage id from the inventory")
    if stage_id in superseded: raise ValueError("Superseded stage has no current packet; use the active stage")
    stage = stages[stage_id]
    metadata = stage["metadata"]
    parsed = stage.get("parsed") or {}
    nodes = parsed.get("nodes", [])
    if not nodes:
        raise ValueError("Stage has no extracted hierarchy; quarantine it instead of building a review packet")
    raw = root / stage["raw_path"]
    blocks = []
    if Path(metadata["file"]).suffix.lower() == ".pdf":
        blocks, _ = extract(raw)
        # The packet must describe the *same* extraction it asks a human to approve.
        if hierarchy(blocks)["text_sha256"] != parsed["text_sha256"]:
            raise ValueError("Re-extraction differs from the staged text; reparse before reviewing")
    quality = stage.get("quality") or {}
    categories = category_status(root, stage_id)
    inventory_rows = {row["stage_id"]: row for row in inventory(root)["rows"]}
    row = inventory_rows.get(stage_id, {})
    receipt = _receipt(root, stage["raw_sha256"])
    extraction = parsed.get("extraction") or {}
    page_numbers = extraction.get("text_pages") or sorted({node["page"] for node in nodes if node.get("page")})
    reported_pages = extraction.get("pages")
    limitations = sorted(set(
        list(stage.get("warnings") or []) + list(quality.get("warnings") or [])
        + (["Publication date is not recorded; do not infer it."] if not metadata.get("publication_date") else [])
        + ["No OCR was applied; scanned-only pages are refused rather than guessed."]
        + ["Legal validity is unknown until an explicit category D decision exists."]
        + ["A source/parsing approval does not certify legal validity or completeness."]
        + (["Annex contains an administrative form template; template headings are not provisions."]
           if any(node.get("form") for node in nodes) else [])))

    checklist = dict(
        schema=PACKET_VERSION,
        research_only=True,
        state="pending",
        stage_id=stage_id,
        official_identifier=metadata["official_identifier"],
        official_number=metadata["official_number"],
        title=metadata["title"],
        document_type=metadata["document_type"],
        issuing_authority=metadata["issuing_authority"],
        jurisdiction=metadata["jurisdiction"],
        issuance_date=metadata["issuance_date"],
        publication_date=metadata.get("publication_date"),
        source_url=metadata["source_url"],
        artifact=dict(original_filename=metadata["file"], raw_sha256=stage["raw_sha256"],
            raw_path=stage["raw_path"], text_sha256=parsed["text_sha256"],
            extracted_characters=len(parsed["text"]), pages=page_numbers, page_count=len(page_numbers),
            reported_pages=reported_pages, parser_version=stage["parser_version"],
            quality_gate_version=stage.get("quality_gate_version"), extraction=parsed.get("extraction")),
        receipt=receipt,
        quality=dict(state=quality.get("state"), counts=quality.get("counts", {}),
            critical=quality.get("critical", []), warnings=quality.get("warnings", []),
            fragment=row.get("fragment"), standalone_articles=row.get("standalone_articles"),
            release_candidate=row.get("release_candidate")),
        approvals={name: (categories[name]["decision"] if categories[name] else "pending") for name in CATEGORIES},
        approvals_are_separate=True,
        parsing_approval_confers_legal_validity=False,
        categories={name: dict(title=CATEGORY_TITLES[name], status=categories[name]["decision"] if categories[name] else "pending",
            items=[dict(id=identifier, requirement=requirement, recorded_fact="", required_evidence="",
                        status="pending", decision=None, reviewer=None, reviewed_at=None,
                        evidence=None, scope=None, limitations=[])
                   for identifier, requirement, _ in ITEMS[name]])
            for name in CATEGORIES},
        unresolved_limitations=limitations,
        legal_validity="unknown",
        human_reviewed=False,
        indexed=False,
        published=False,
    )

    facts = {
        "identifier_number": f"`{metadata['official_identifier']}` / `{metadata['official_number']}`",
        "title_type": f"{metadata['document_type']}: {metadata['title']}",
        "authority": f"{metadata['issuing_authority']} / {metadata['jurisdiction']}",
        "receipt": (f"`{receipt['receipt']}` ({receipt.get('retrieved_at')}, HTTP {receipt.get('status')})"
                    if receipt else "receipt not found: resolve before approval"),
        "raw_hash": f"`{stage['raw_sha256']}`",
        "completeness": f"{row.get('standalone_articles', 0)} standalone articles; fragment={row.get('fragment')}",
        "pages": f"{len(page_numbers)} text page(s); PDF pages={reported_pages or 'unknown'}",
        "hierarchy": ", ".join(f"{key}={value}" for key, value in sorted(quality.get("counts", {}).items())),
        "text": f"{len(parsed['text'])} characters; text SHA `{parsed['text_sha256']}`",
        "annex": ("annex form template detected; operative articles exclude template headings"
                  if any(node.get("form") for node in nodes) else "no annex form template"),
        "stripped": str((parsed.get("extraction") or {}).get("stripped_running_lines", 0)),
        "counts": ", ".join(f"{key}={value}" for key, value in sorted(quality.get("counts", {}).items())),
        "spans": "spans cover the full text" if quality.get("state") != "quarantined" else "span QA failed",
        "issuance": str(metadata.get("issuance_date")),
        "publication": str(metadata.get("publication_date") or "not recorded"),
        "effect": "transcribe from the instrument; unknown stays unknown",
        "relations": ("amending instrument; confirm each amended law and article"
                      if "sửa đổi" in metadata["title"].casefold() else "confirm amendments/supersessions separately"),
        "annex_meta": ("annex present; verify attachment/completeness" if "annex" in quality.get("counts", {}) else "no annex"),
        "doctype": metadata["document_type"],
        "validity": "unknown (not a legal determination)",
        "dates": f"issuance {metadata.get('issuance_date')}; publication {metadata.get('publication_date') or 'unrecorded'}",
        "territory": metadata["jurisdiction"],
        "amendments": "not yet checked against later instruments",
        "provisions": "reviewer must identify any transitional/superseded provision",
        "current_law": "blocked while validity is unknown",
    }
    for name, entries in ITEMS.items():
        for item, (_, _, fact_key) in zip(checklist["categories"][name]["items"], entries):
            item["recorded_fact"] = facts[fact_key]
            item["required_evidence"] = _evidence_for(name, item["id"])

    packet_dir = root / "review-packets" / slug(stage)
    packet_dir.mkdir(parents=True, exist_ok=True)
    (packet_dir / "decisions").mkdir(exist_ok=True)
    atomic_bytes(packet_dir / "checklist.json", (canonical(checklist) + "\n").encode())
    atomic_bytes(packet_dir / "report.md", _markdown(checklist, stage, _samples(nodes, parsed["text"]),
        [dict(page=page, **(_page_preview(blocks, page))) for page in page_numbers if blocks]).encode())
    for name in CATEGORIES:
        template = dict(category=name, decision="pending", reviewer="FILL: reviewer name",
            reason="FILL: what was checked and what was found", evidence="FILL: page/paragraph/URL evidence",
            scope=f"FILL: exact scope reviewed for stage {stage_id}", limitations=[], reviewed_at="2026-01-01T00:00:00+00:00",
            stage_id=stage_id, raw_sha256=stage["raw_sha256"], text_sha256=parsed["text_sha256"],
            validity="unknown", effective_date=None, expiry_date=None)
        write_once(packet_dir / "decisions" / f"{name}.template.json",
            template)
    return dict(stage_id=stage_id, packet=packet_dir.relative_to(root).as_posix(),
        checklist=checklist, report=(packet_dir / "report.md").relative_to(root).as_posix())


def _evidence_for(category, item_id):
    return {
        "A1": "PDF cover page and gazette masthead; acquisition manifest",
        "A2": "PDF title block and signed text",
        "A3": "PDF signature block and issuing body",
        "A4": "Acquisition receipt and official source page screenshot/URL",
        "A5": "`sha256sum` of the preserved original plus duplicate check",
        "A6": "Visible first/last page; confirm no continuation marker",
        "B1": "Page-by-page visual check against the PDF",
        "B2": "Compare the printed hierarchy with the packet outline",
        "B3": "Spot-check diacritics and word spacing on sampled pages",
        "B4": "Inspect annex/form pages; confirm they are excluded from provisions",
        "B5": "Confirm removed lines were only mastheads/page numbers",
        "B6": "Count articles/clauses/points on the visible text",
        "B7": "Packet span/coverage report plus text hash",
        "C1": "Signed date in the PDF",
        "C2": "Gazette header or official publication record",
        "C3": "Effective-date and transitional articles",
        "C4": "Amending title, cited instruments and amendment articles",
        "C5": "Annex pages and attachment statement",
        "C6": "Document type heading and any consolidation statement",
        "D1": "Official validity database/decision or gazette notice",
        "D2": "Effective, expiry, repeal or suspension text",
        "D3": "Territorial scope clause or issuing authority",
        "D4": "Later amending/suspending instruments",
        "D5": "Provision text and amendment history",
        "D6": "Explicit statement that current-law use is not claimed",
    }[item_id]


def _markdown(checklist, stage, samples, page_previews):
    metadata = stage["metadata"]
    lines = [
        f"# Review packet: {metadata['official_number']}", "",
        "> **RESEARCH ONLY — NOT LEGAL ADVICE — NOT YET REVIEWED.**",
        "> Parsing and source approval do not certify legal validity. Unknown validity stays unknown.",
        "> This packet never approves, seals, indexes or publishes anything by itself.", "",
        f"- Stage: `{checklist['stage_id']}`",
        f"- Official identifier: `{checklist['official_identifier']}`",
        f"- Title: {checklist['title']}",
        f"- Issuing authority: {checklist['issuing_authority']}",
        f"- Jurisdiction: {checklist['jurisdiction']}",
        f"- Issuance date: {checklist['issuance_date']}",
        f"- Publication date: {checklist['publication_date'] or 'not recorded'}",
        f"- Source page: {checklist['source_url']}",
        f"- Original file: `{metadata['file']}`",
        f"- Raw SHA-256: `{checklist['artifact']['raw_sha256']}`",
        f"- Parsed text SHA-256: `{checklist['artifact']['text_sha256']}`",
        f"- Parser: `{checklist['artifact']['parser_version']}` / `{checklist['artifact']['quality_gate_version']}`",
        f"- Pages: {checklist['artifact']['page_count']} text page(s); PDF pages {checklist['artifact']['reported_pages']}",
        f"- Extracted characters: {checklist['artifact']['extracted_characters']}",
        f"- Provision counts: {checklist['quality']['counts']}",
        f"- Extraction state: **{checklist['quality']['state']}**",
        f"- Fragment / standalone articles: {checklist['quality']['fragment']} / {checklist['quality']['standalone_articles']}",
        "",
        "## Approval status (all separate)", "",
        "| Category | Status |", "|---|---|",
    ]
    for name in CATEGORIES:
        lines.append(f"| {CATEGORY_TITLES[name]} | **{checklist['approvals'][name]}** |")
    lines += ["", "No category approval implies another. Category B (extraction) does not approve "
        "source identity, metadata, or legal validity.", "",
        "## Acquisition receipt", ""]
    if checklist["receipt"]:
        for key, value in checklist["receipt"].items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- **Missing receipt: stop and resolve provenance before any approval.**")
    lines += ["", "## Extraction report", ""]
    for key, value in (checklist["artifact"]["extraction"] or {}).items():
        if key != "page_characters":
            lines.append(f"- {key}: {value}")
    lines += ["", "## Page checks", "",
        "| Page | Characters | First lines | Last lines |", "|---|---|---|---|"]
    for preview in page_previews:
        first = " / ".join(line[:90] for line in preview["first"]).replace("|", "\\|")
        last = " / ".join(line[:90] for line in preview["last"]).replace("|", "\\|")
        lines.append(f"| {preview['page']} | {preview['characters']} | {first} | {last} |")
    lines += ["", "## Provision samples (parsed text)", ""]
    for sample in samples:
        lines += [f"### `{sample['locator']}` — page {sample['page']}", "",
            f"Heading: {sample['heading']}", "", "```text", sample["excerpt"], "```", ""]
    lines += ["## Checklist", ""]
    for name in CATEGORIES:
        category = checklist["categories"][name]
        lines += [f"### {category['title']} — **{category['status']}**", "",
            "| ID | Requirement | Recorded fact | Required evidence | Status |",
            "|---|---|---|---|---|"]
        for item in category["items"]:
            lines.append(f"| {item['id']} | {item['requirement'].replace('|', chr(92)+'|')} "
                         f"| {item['recorded_fact'].replace('|', chr(92)+'|')} "
                         f"| {item['required_evidence'].replace('|', chr(92)+'|')} | {item['status']} |")
        lines.append("")
    lines += ["## Unresolved limitations", ""]
    lines += [f"- {value}" for value in checklist["unresolved_limitations"]]
    lines += ["", "## How to record decisions (explicit, per category)", "",
        f"Packet directory: `data/phase-d-corpus-v2/review-packets/{slug(stage)}`", "",
        "Edit only the relevant template, then run one command per category. Replace `FILL:` text,",
        "set your real name, timestamp, evidence, scope and limitations, and choose the decision.", ""]
    for name in CATEGORIES:
        lines += ["```bash",
            f"uv run --frozen python -m preprocess.offline_cli review-decide \\",
            f"  --workspace data/phase-d-corpus-v2 --stage {checklist['stage_id']} \\",
            f"  --category {name} --decision-file data/phase-d-corpus-v2/review-packets/{slug(stage)}/decisions/{name}.template.json",
            "```", ""]
    lines += ["Convenience wrappers: `review-reject` (forces `rejected`), "
        "`review-approve-extraction` (only category B), `review-evidence` (records evidence as pending).", "",
        "Whole-stage legal review (legacy gate used by sealing) still needs an explicit decision file:", "",
        "```bash",
        "uv run --frozen python -m preprocess.offline_cli review \\",
        f"  --workspace data/phase-d-corpus-v2 --stage {checklist['stage_id']} --decision <review.json>",
        "```", "",
        "Check readiness at any time:", "",
        "```bash",
        f"uv run --frozen python -m preprocess.offline_cli review-eligibility --workspace data/phase-d-corpus-v2 --stage {checklist['stage_id']}",
        "```", "",
        "Sealing is a separate, explicit publication action and requires every category plus "
        "`--approve-publication`. It does **not** index or publish to retrieval.", ""]
    return "\n".join(lines)


def generate(workspace, stage_ids=None):
    root = require_workspace(workspace)
    stages, superseded = stage_lineage(root)
    selected = sorted(stage_ids or [sid for sid in stages if sid not in superseded])
    results = []
    for stage_id in selected:
        if stage_id not in stages: raise ValueError("Unknown stage; use the exact stage id from the inventory")
        if stage_id in superseded: raise ValueError("Superseded stage has no current packet; use the active stage")
        packet = build_packet(root, stage_id)
        results.append(dict(stage_id=stage_id, packet=packet["packet"], report=packet["report"],
            status=packet["checklist"]["quality"]["state"],
            fragment=packet["checklist"]["quality"]["fragment"]))
    return dict(packets=len(results), results=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default="data/phase-d-corpus-v2")
    parser.add_argument("--stages", nargs="+")
    args = parser.parse_args()
    try:
        result = generate(args.workspace, args.stages)
    except (ValueError, OSError):
        parser.exit(1, "Packet generation refused. Inspect the workspace stage and docs/corpus-review-runbook.md.\n")
    print(canonical(result))


if __name__ == "__main__":
    main()
