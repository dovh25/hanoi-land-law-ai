"""Phase D.2 regression tests: packet decisions, lineage, parser v3, R0 guardrails."""
import json
from pathlib import Path

import pytest

from law_crawler.quality import assess, inventory
from preprocess.legal_chunking import ByteBudget
from preprocess.legal_parser import Block, extract, hierarchy, _strip_gazette_running_lines, _tidy_pdf_page
from preprocess.offline_ingestion import (CATEGORIES, CATEGORY_TITLES, category_history, category_status,
    decide_category, eligibility, ingest, initialize, load_stage, reparse, review, seal, stage_lineage)
from preprocess.review_packets import build_packet
from preprocess.r0_release import _contract_checks, _manifest_round_trip, draft
from preprocess.synthetic_ingestion import sources

REVIEW = dict(decision="approved", reviewer="TEST operator", reason="Synthetic review only",
    evidence_locator="SYNTHETIC entire fixture", reviewed_at="2026-01-02T00:00:00+00:00", validity="unknown")


@pytest.fixture
def prepared(tmp_path):
    root = initialize(tmp_path / "workspace")
    manifests = sources(tmp_path / "sources")
    stage = ingest(root, manifests[0])["stage_id"]
    return root, manifests, stage


def _payload(root, stage_id, category, decision="approved", **overrides):
    stage = load_stage(Path(root), stage_id)
    value = dict(category=category, decision=decision, reviewer="TEST reviewer",
        reason="Checked the fixture", evidence="SYNTHETIC evidence", scope="TEST fixture scope",
        limitations=[], reviewed_at="2026-01-03T00:00:00+00:00", stage_id=stage_id,
        raw_sha256=stage["raw_sha256"], text_sha256=stage["parsed"]["text_sha256"],
        validity="unknown", effective_date=None, expiry_date=None)
    value.update(overrides)
    return value


def test_packet_is_machine_readable_and_never_approves(prepared):
    root, _, stage_id = prepared
    result = build_packet(root, stage_id)
    directory = root / result["packet"]
    checklist = json.loads((directory / "checklist.json").read_text())
    assert checklist["research_only"] is True and checklist["human_reviewed"] is False
    assert checklist["approvals_are_separate"] is True
    assert checklist["parsing_approval_confers_legal_validity"] is False
    assert checklist["approvals"] == {name: "pending" for name in CATEGORIES}
    assert set(checklist["categories"]) == set(CATEGORIES)
    assert all(item["status"] == "pending" for category in checklist["categories"].values()
               for item in category["items"])
    assert "RESEARCH ONLY" in (directory / "report.md").read_text()
    assert len(list((directory / "decisions").glob("*.template.json"))) == 4
    assert category_status(root, stage_id) == {name: None for name in CATEGORIES}


def test_category_approvals_are_separate_bound_and_not_legality(prepared):
    root, _, stage_id = prepared
    decide_category(root, stage_id, _payload(root, stage_id, "A_source_identity"))
    report = eligibility(root, [stage_id])["rows"][0]
    assert report["gates"]["source_identity_approved"] is True
    assert report["gates"]["extraction_approved"] is False
    assert report["research_seal_ready"] is False

    decide_category(root, stage_id, _payload(root, stage_id, "B_extraction_quality"))
    decide_category(root, stage_id, _payload(root, stage_id, "C_legal_metadata"))
    decide_category(root, stage_id, _payload(root, stage_id, "D_applicability_validity", decision="pending"))
    report = eligibility(root, [stage_id])["rows"][0]
    assert report["gates"]["validity_recorded"] is True
    assert report["research_seal_ready"] is False  # needs the explicit whole-stage review
    review(root, stage_id, REVIEW)
    report = eligibility(root, [stage_id])["rows"][0]
    assert report["research_seal_ready"] is True
    assert report["current_law_seal_ready"] is False
    assert report["parsing_approval_confers_legal_validity"] is False

    with pytest.raises(ValueError, match="different artifact"):
        decide_category(root, stage_id, _payload(root, stage_id, "A_source_identity", raw_sha256="0" * 64))

    before = category_status(root, stage_id)
    decide_category(root, stage_id, _payload(root, stage_id, "B_extraction_quality",
        decision="pending", reason="Evidence only"), kind="evidence")
    assert category_status(root, stage_id) == before
    assert len(category_history(root, stage_id)) == 5


def test_category_D_cannot_approve_unknown_validity(prepared):
    root, _, stage_id = prepared
    with pytest.raises(ValueError, match="unknown"):
        decide_category(root, stage_id, _payload(root, stage_id, "D_applicability_validity"))
    with pytest.raises(ValueError, match="effective date"):
        decide_category(root, stage_id, _payload(root, stage_id, "D_applicability_validity",
            validity="in_force"))


def test_template_placeholders_and_missing_decisions_are_refused(prepared):
    root, _, stage_id = prepared
    with pytest.raises(ValueError, match="FILL"):
        decide_category(root, stage_id, _payload(root, stage_id, "A_source_identity",
            reviewer="FILL: reviewer"))
    from preprocess.offline_ingestion import CategoryDecision
    with pytest.raises(ValueError):
        CategoryDecision.model_validate(_payload(root, stage_id, "A_source_identity",
            reviewer="FILL: reviewer"))


def test_quarantined_extraction_cannot_approve_or_seal(prepared):
    root, manifests, _ = prepared
    broken = manifests[0].parent / "synthetic.txt"
    broken.write_text("Điều 1. Một\nNội dung\nĐiều 3. Ba\nNội dung\n")
    failed = ingest(root, manifests[0])
    assert failed["status"] == "quarantined"
    stage_id = failed["stage_id"]
    with pytest.raises(ValueError, match="Quarantined"):
        decide_category(root, stage_id, _payload(root, stage_id, "B_extraction_quality"))
    with pytest.raises(ValueError, match="Quarantined"):
        review(root, stage_id, REVIEW)


def test_reparse_is_append_only_and_superseded_stage_is_inert(prepared):
    root, _, old_id = prepared
    before = load_stage(root, old_id)
    results = reparse(root, [old_id])
    new_id = results[0]["stage_id"]
    assert new_id != old_id and results[0]["supersedes"] == old_id
    assert load_stage(root, old_id) == before  # original stage file untouched
    stages, superseded = stage_lineage(root)
    assert old_id in superseded and new_id in stages
    with pytest.raises(ValueError, match="Superseded"):
        review(root, old_id, REVIEW)
    with pytest.raises(ValueError, match="Superseded"):
        decide_category(root, old_id, _payload(root, old_id, "A_source_identity"))
    with pytest.raises(ValueError, match="Superseded"):
        seal(root, "SYNTHETIC-superseded", [old_id], approve_publication=True, purpose="synthetic")
    assert inventory(root)["stages"] == 1
    assert reparse(root, [new_id])[0]["reused"] is True


def test_real_research_seal_requires_packet_categories(prepared):
    from batch.contracts import MODEL_ID, MODEL_REVISION
    root, manifests, _ = prepared
    metadata = json.loads(manifests[0].read_text())
    metadata.update(is_synthetic=False, source_url="https://vbpl.vn/SYNTHETIC-test-only")
    manifests[0].write_text(json.dumps(metadata))
    stage_id = ingest(root, manifests[0])["stage_id"]
    review(root, stage_id, REVIEW)

    class FakePinnedBudget(ByteBudget):
        identity = f"{MODEL_ID}@{MODEL_REVISION}"

    with pytest.raises(ValueError, match="Missing explicit"):
        seal(root, "SYNTHETIC-real-gate", [stage_id], purpose="research", approve_publication=True,
             budget=FakePinnedBudget())


def test_r0_draft_refuses_synthetic_and_checks_dense_contract(prepared):
    root, _, stage_id = prepared
    with pytest.raises(ValueError, match="synthetic"):
        draft(root, [stage_id])
    assert all(_contract_checks().values())
    result = _manifest_round_trip(ByteBudget())
    assert result["status"] == "pass"
    assert result["model"]["dimension"] == 1024 and result["model"]["pooling"] == "cls"
    assert result["model"]["normalized"] is True and result["model"]["dtype"] == "float32"


def test_parser_collapses_pdf_padding_without_joining_lines():
    # Horizontal padding is collapsed; line structure is preserved. Single-space splits inside a
    # syllable are NOT guessed at (they would need language reconstruction).
    assert _tidy_pdf_page("Điều   1.  Bồi   thường\nvăn  bản") == "Điều 1. Bồi thường\nvăn bản"


def test_gazette_running_lines_are_stripped_only_at_page_edges():
    pages = ["92 CÔNG BÁO/Số 987 + 988/Ngày 25-8-2024\nQUỐC HỘI\nĐiều 1. Nội dung\n",
             "QUỐC HỘI\nĐiều 2. Nội dung\n93 CÔNG BÁO/Số 987 + 988/Ngày 25-8-2024"]
    report = {}
    cleaned, stripped = _strip_gazette_running_lines(pages, report)
    assert stripped == 2
    assert "CÔNG BÁO" not in "\n".join(cleaned)
    assert "Điều 1. Nội dung" in cleaned[0] and "Điều 2. Nội dung" in cleaned[1]
    assert report["stripped_running_lines"] == 2


def test_form_annex_headings_are_not_provisions():
    parsed = hierarchy([Block("Phụ lục\nMẪU QUYẾT ĐỊNH PHÊ DUYỆT\n(Kèm theo Nghị định số 88/2024/NĐ-CP)\n"
                              "Điều 1. Nội dung mẫu\n1. Khoản mẫu\na) Điểm mẫu\n")])
    assets = [node for node in parsed["nodes"] if node["kind"] == "annex"]
    assert len(assets) == 1 and assets[0].get("form") is True
    assert not [node for node in parsed["nodes"] if node["kind"] == "article"]
    assert "Điều 1. Nội dung mẫu" in parsed["text"]  # text is preserved, only promoted headings are suppressed


def test_multipart_identifier_parts_are_not_release_candidates(prepared):
    root, manifests, first_id = prepared
    first = json.loads(manifests[0].read_text())
    second = json.loads(manifests[1].read_text())
    second.update(official_identifier=first["official_identifier"],
                  official_number=first["official_number"])
    manifests[1].write_text(json.dumps(second))
    second_id = ingest(root, manifests[1])["stage_id"]

    result = inventory(root)
    rows = {row["stage_id"]: row for row in result["rows"]}
    assert {rows[first_id]["official_identifier"], rows[second_id]["official_identifier"]} == {first["official_identifier"]}
    assert rows[first_id]["multipart_component"] is True
    assert rows[second_id]["multipart_component"] is True
    # A single acquired artifact cannot be assumed to be the complete standalone instrument.
    assert rows[first_id]["release_candidate"] is False
    assert rows[second_id]["release_candidate"] is False
    assert result["multipart_components"] == 2
    assert result["release_candidates"] == 0


def test_article_numbering_is_global_to_the_instrument():
    parsed = hierarchy([Block("Chương I\nĐiều 1. Một\nNội dung\nĐiều 2. Hai\nNội dung\n"
                              "Chương II\nĐiều 3. Ba\nNội dung\n")])
    report = assess(parsed)
    assert report["critical"] == []
    assert "article_sequence_starts_after_one" not in report["warnings"]
    assert report["counts"]["article"] == 3


def test_trailing_blank_pdf_page_is_skipped_with_warning(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    for index in range(3):
        page = writer.add_blank_page(width=300, height=300)
        if index < 2:
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({
                NameObject("/F1"): DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})})})
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 10 Tf 20 250 Td (Noi dung trang {index + 1}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
    path = tmp_path / "blank-tail.pdf"
    writer.write(path)
    report = {}
    blocks, warnings = extract(path, report=report)
    assert [block.page for block in blocks] == [1, 2]
    assert report["blank_pages"] == [3]
    assert any("Trailing non-text" in warning for warning in warnings)
