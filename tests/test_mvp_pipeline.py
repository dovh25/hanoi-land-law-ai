"""Bounded MVP pipeline: one call, citation validation, and deterministic fallbacks."""
import pytest

from backend.core.config import settings_context
from backend.services.llm import LLMUnavailable
from backend.services.mvp_corpus import MvpCorpusIndex
from backend.services.pipelines.mvp_rag_pipeline import MvpRagPipeline

QUESTION = "Bồi thường khi Nhà nước thu hồi đất ở là gì?"


class FakeProvider:
    def __init__(self, answer: str = "", error: Exception | None = None):
        self.answer = answer
        self.error = error
        self.calls = 0
        self.prompt = None

    def invoke(self, prompt):
        self.calls += 1
        self.prompt = prompt
        if self.error is not None:
            raise self.error
        return self.answer


@pytest.fixture(scope="module")
def index():
    return MvpCorpusIndex.load()


def run(settings, index, provider, question=QUESTION):
    pipeline = MvpRagPipeline(provider=provider, index=index)
    with settings_context(settings):
        return pipeline.respond(question)


def test_greeting_and_thanks_do_not_call_llm(settings, index):
    provider = FakeProvider("should not be used")
    for greeting in ("Xin chào", "Cảm ơn bạn", "Bạn là ai?"):
        result = run(settings, index, provider, greeting)
        assert result["status"] == "greeting"
        assert result["llm_used"] is False
        assert result["sources"] == []
    assert provider.calls == 0


def test_insufficient_evidence_does_not_call_llm(settings, index):
    provider = FakeProvider("should not be used")
    result = run(settings, index, provider, "Thời hạn sử dụng đất ở là bao lâu?")
    assert result["status"] == "abstained"
    assert result["abstention_reason"] == "outside_corpus_scope"
    assert result["llm_used"] is False
    assert provider.calls == 0


def test_llm_disabled_returns_retrieval_only(settings, index):
    result = run(settings, index, None)
    assert result["status"] == "llm_disabled"
    assert result["llm_used"] is False
    assert result["sources"]
    assert all(source["validity_status"] == "unknown" for source in result["sources"])
    assert "Gemini đang tắt" in result["answer"]


def test_valid_citation_is_accepted_with_one_call(settings, index):
    provider = FakeProvider(
        "Hộ gia đình có đất ở bị thu hồi được xem xét bồi thường theo trích đoạn [E1]."
    )
    result = run(settings, index, provider)
    assert result["status"] == "answered"
    assert result["llm_used"] is True
    assert provider.calls == 1
    assert result["sources"]
    assert result["sources"][0]["evidence_id"] == "E1"
    assert "Đây là bản demo nghiên cứu" in result["answer"]


def test_prompt_contains_bounded_evidence(settings, index):
    provider = FakeProvider("Theo trích đoạn [E1].")
    run(settings, index, provider)
    messages = provider.prompt
    text = "\n".join(str(message.content) for message in messages)
    assert "[E1]" in text
    assert "NGỮ CẢNH" in text
    assert "Không được tự bịa" in text


def test_rejects_undefined_evidence_marker(settings, index):
    provider = FakeProvider("Khẳng định không có căn cứ [E99].")
    result = run(settings, index, provider)
    assert result["status"] == "citation_rejected"
    assert result["rejected_citations"] == ["[E99]"]
    assert result["sources"]
    assert provider.calls == 1


def test_rejects_answer_without_citation(settings, index):
    result = run(settings, index, FakeProvider("Hộ gia đình được bồi thường."))
    assert result["status"] == "citation_rejected"


def test_rejects_invented_date(settings, index):
    result = run(
        settings,
        index,
        FakeProvider("Quy định có hiệu lực từ ngày 01 tháng 1 năm 2030 [E1]."),
        "Nghị định 88/2024/NĐ-CP có hiệu lực khi nào?",
    )
    assert result["status"] == "citation_rejected"
    assert any("ngày" in warning for warning in result["warnings"])


def test_rejects_unknown_article_reference(settings, index):
    result = run(settings, index, FakeProvider("Theo Điều 250, mức bồi thường do Ủy ban quyết định [E1]."))
    assert result["status"] == "citation_rejected"


def test_rejects_unverified_quotation(settings, index):
    result = run(
        settings,
        index,
        FakeProvider('Quy định nêu “mức bồi thường do Chủ tịch thành phố tự quyết định” [E1].'),
    )
    assert result["status"] == "citation_rejected"


def test_current_effect_claim_is_neutralised(settings, index):
    result = run(settings, index, FakeProvider("Đây là quy định hiện hành về bồi thường [E1]."))
    assert result["status"] == "answered"
    assert "theo văn bản được trích dẫn" in result["answer"]
    assert any("hiệu lực hiện hành" in warning for warning in result["warnings"])


def test_provider_failure_returns_sources_not_fake_answer(settings, index):
    result = run(settings, index, FakeProvider(error=LLMUnavailable("rate limited")))
    assert result["status"] == "llm_unavailable"
    assert result["llm_used"] is False
    assert result["sources"]
    assert "chưa có câu trả lời tổng hợp" in result["answer"]


def test_document_overview_is_answered_from_scope_article(settings, index):
    result = run(settings, index, None, "Nghị định 88 quy định gì?")
    assert result["status"] == "llm_disabled"
    assert result["sources"][0]["article_number"] == "Điều 1"
