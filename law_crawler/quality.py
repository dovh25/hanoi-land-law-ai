"""Offline extraction QA. Heuristic flags are review gates, never legal truth."""
from collections import Counter
import json
from pathlib import Path
import re

from batch.contracts import canonical, digest


def _inside_annex(nodes, index):
    parent = nodes[index]["parent"]
    while parent is not None:
        if nodes[parent]["kind"] == "annex":
            return True
        parent = nodes[parent]["parent"]
    return False


def assess(parsed):
    text, nodes = parsed["text"], parsed["nodes"]
    critical, warnings, position, locators = [], [], 0, set()
    if not text.strip(): critical.append("empty_extraction")
    if digest(text) != parsed["text_sha256"]: critical.append("extracted_text_checksum_mismatch")
    if any(marker in text for marker in ("\ufffd", "\x00", "(cid:")): critical.append("suspected_encoding_or_glyph_loss")
    # Article numbering is global to the instrument, not restarted by each chapter/section.
    articles = []
    for index, node in enumerate(nodes):
        if node["locator"] in locators: critical.append("duplicate_locator")
        locators.add(node["locator"])
        if node["start"] != position or not node["start"] < node["end"] <= len(text): critical.append("broken_source_span_coverage")
        position = node["end"]
        parent = node["parent"]
        if parent is not None and not 0 <= parent < index: critical.append("invalid_parent_order")
        if node["kind"] == "article" and not _inside_annex(nodes, index):
            match = re.search(r"article:(\d+)([a-zđ]?)$", node["locator"])
            if match: articles.append(int(match.group(1)))
    if position != len(text): critical.append("uncovered_tail")
    if articles and min(articles) > 1: warnings.append("article_sequence_starts_after_one; possible multipart source")
    if articles:
        missing = sorted(set(range(min(articles), max(articles)+1)) - set(articles))
        if missing: critical.append("missing_article_numbers:" + ",".join(map(str, missing)))
    if not articles: warnings.append("no_article_headings; inspect unstructured/annex material")
    if any(node["kind"] == "annex" and node.get("form") for node in nodes):
        warnings.append("annex_form_template_not_structured; verify placeholders visually")
    extraction = parsed.get("extraction") or {}
    if extraction.get("stripped_running_lines"):
        warnings.append(f"gazette_running_lines_stripped:{extraction['stripped_running_lines']}")
    if extraction.get("blank_pages"):
        warnings.append("blank_pages_skipped:" + ",".join(map(str, extraction["blank_pages"])))
    return dict(state="quarantined" if critical else "validated_pending_legal_review",
        critical=sorted(set(critical)), warnings=sorted(set(warnings)),
        counts=dict(Counter(node["kind"] for node in nodes)), extracted_characters=len(text),
        source_text_sha256=parsed["text_sha256"], legal_validity="unknown", human_reviewed=False)


def inventory(workspace):
    from preprocess.offline_ingestion import load_stage, require_workspace, review_history, stage_lineage
    root = require_workspace(workspace)
    stages, superseded = stage_lineage(root)
    rows, seen_raw, duplicates = [], set(), 0
    for stage_id, stage in sorted(stages.items()):
        if stage_id in superseded:
            continue
        duplicate = stage["raw_sha256"] in seen_raw
        duplicates += duplicate; seen_raw.add(stage["raw_sha256"])
        report = assess(stage["parsed"]) if stage.get("parsed") else dict(state="quarantined",critical=[stage.get("action","extraction_failed")],counts={})
        nodes = (stage.get("parsed") or {}).get("nodes", [])
        standalone_articles = sum(1 for index, node in enumerate(nodes)
            if node["kind"] == "article" and not _inside_annex(nodes, index))
        # An annex-only continuation is real extracted text, but not a standalone instrument:
        # it must never be promoted to a document/release on its own.
        fragment = bool(nodes) and standalone_articles == 0
        report["fragment"] = fragment
        report["standalone_articles"] = standalone_articles
        reviews=review_history(root, stage_id)
        rows.append(dict(stage_id=stage_id, official_identifier=stage["metadata"]["official_identifier"],
            source_url=stage["metadata"]["source_url"], raw_sha256=stage["raw_sha256"], duplicate_raw=duplicate,
            fragment=fragment, standalone_articles=standalone_articles,
            release_candidate=report["state"] != "quarantined" and not duplicate and standalone_articles > 0,
            quality=report))
        rows[-1]['human_reviewed']=bool(reviews and reviews[-1]['review']['decision']=='approved')
    # Several acquired artifacts under one identifier form a multipart instrument. Until a
    # reviewer verifies a complete standalone rendition, no single part is a release candidate.
    group_sizes = Counter(row["official_identifier"] for row in rows)
    for row in rows:
        row["multipart_component"] = group_sizes[row["official_identifier"]] > 1
        if row["multipart_component"]:
            row["release_candidate"] = False
    counts = Counter()
    for row in rows: counts.update(row["quality"]["counts"])
    return dict(stages=len(rows), parsed=sum(bool(row["quality"]["counts"]) for row in rows),
        quarantined=sum(row["quality"]["state"] == "quarantined" for row in rows), duplicates=duplicates,
        fragments=sum(row["fragment"] for row in rows),
        multipart_components=sum(row["multipart_component"] for row in rows),
        release_candidates=sum(row["release_candidate"] for row in rows),
        provision_counts=dict(counts), reviewed=sum(row['human_reviewed'] for row in rows), rows=rows)
