"""Deterministic retrieval and abstention checks over the real MVP demo artifact."""
import pytest

from backend.services.mvp_corpus import (
    MvpCorpusIndex,
    heading_coverage,
    is_domain_query,
    load_manifest,
)


@pytest.fixture(scope="module")
def index():
    return MvpCorpusIndex.load()


def test_corpus_is_isolated_and_unknown_validity(index):
    manifest = load_manifest()
    assert manifest["corpus"] == "MVP_DEMO_CORPUS"
    assert manifest["publication_status"] == "not_published_not_current_law"
    assert manifest["strict_phase_d_gates_unchanged"] is True
    assert len(index.evidence) == manifest["chunk_count"] == 90
    assert len(index.documents()) == manifest["document_count"] == 2
    for item in index.evidence:
        assert item.validity_status == "unknown"
        assert item.review_status == "technical_validation_only"
        assert item.corpus_label == "MVP_DEMO_CORPUS"
        assert item.source_url.startswith("https://vanban.chinhphu.vn/")
        assert item.source_start < item.source_end
        assert item.source_text.strip()


@pytest.mark.parametrize(
    ("question", "article"),
    [
        ("Bồi thường khi Nhà nước thu hồi đất ở là gì?", "Điều 11"),
        ("Hồ sơ, trình tự bồi thường, hỗ trợ, tái định cư?", "Điều 3"),
        ("Mức bồi thường thiệt hại về nhà, công trình trên đất?", "Điều 14"),
        ("Hỗ trợ ổn định đời sống cho hộ gia đình bị thu hồi đất?", "Điều 19"),
        ("Ghi nợ tiền sử dụng đất khi nhận đất tái định cư?", "Điều 26"),
        ("Chi phí tổ chức thực hiện bồi thường, hỗ trợ, tái định cư?", "Điều 27"),
        ("Tái định cư bằng nhà ở, đất ở?", "Điều 24"),
        ("Điều 30 Nghị định 88 quy định gì?", "Điều 30"),
    ],
)
def test_retrieval_returns_expected_article(index, question, article):
    hits = index.search(question, top_k=6)
    assert hits
    assert hits[0].evidence.article_number == article
    assert hits[0].evidence.document_number == "88/2024/NĐ-CP"


def test_retrieval_for_amending_law(index):
    hits = index.search("Luật Đất đai 43/2024 sửa đổi những gì?", top_k=6)
    assert hits[0].evidence.document_number == "43/2024/QH15"
    assert {hit.evidence.article_number for hit in hits[:4]} >= {"Điều 1", "Điều 2", "Điều 3"}


@pytest.mark.parametrize(
    ("question", "reason"),
    [
        ("Thời hạn sử dụng đất ở là bao lâu?", "outside_corpus_scope"),
        ("Thủ tục cấp Giấy chứng nhận quyền sử dụng đất lần đầu?", "outside_corpus_scope"),
        ("Quy hoạch sử dụng đất cấp huyện được lập thế nào?", "outside_corpus_scope"),
        ("Chuyển mục đích sử dụng đất nông nghiệp sang đất ở?", "outside_corpus_scope"),
        ("Khiếu nại về quyết định thu hồi đất?", "outside_corpus_scope"),
        ("Bảng giá đất Hà Nội 2026?", "outside_corpus_scope"),
        ("Thủ tục ly hôn đơn phương cần giấy tờ gì?", "out_of_domain"),
        ("Giá vàng hôm nay bao nhiêu?", "out_of_domain"),
        ("Điều 99 Luật Đất đai 31/2024 quy định gì?", "explicit_citation_not_in_corpus"),
    ],
)
def test_abstention_inside_and_outside_domain(index, question, reason):
    hits = index.search(question, top_k=6)
    result = index.assess(question, hits, min_score=5.0, min_coverage=0.5)
    assert result.sufficient is False
    assert result.reason == reason


def test_document_overview_returns_scope_article(index):
    result = index.assess(
        "Nghị định 88 quy định gì?",
        index.search("Nghị định 88 quy định gì?", top_k=6),
        min_score=5.0,
        min_coverage=0.5,
    )
    assert result.sufficient is True
    assert result.reason == "document_overview"


def test_bm25_is_deterministic_and_heading_sensitive(index):
    first = [(hit.evidence.chunk_id, hit.score) for hit in index.search("bồi thường tái định cư", top_k=6)]
    second = [(hit.evidence.chunk_id, hit.score) for hit in index.search("bồi thường tái định cư", top_k=6)]
    assert first == second
    assert heading_coverage("tái định cư", "Điều 24. Bố trí tái định cư") == 1.0


def test_domain_gate_requires_land_terms():
    assert is_domain_query("đất đai") is True
    assert is_domain_query("giá vàng") is False
