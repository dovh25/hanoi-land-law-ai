"""Simplified, bounded MVP pipeline: retrieve -> sufficiency -> one Gemini call -> validate.

Advanced Agentic RAG pipelines remain available for later work, but the public demo uses
this deterministic path. Retrieval is lexical BM25 over MVP_DEMO_CORPUS, so startup does
not download models or contact Qdrant. Every legal statement must cite an application
evidence ID; unsupported citations, article references, quotations, and dates cause the
generated answer to be rejected in favour of verbatim source excerpts.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Iterable

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.config import Config, get_settings, settings_context
from backend.services.llm import GeminiProvider, LLMUnavailable, llm_turn
from backend.services.mvp_corpus import (
    Evidence,
    Hit,
    MvpCorpusIndex,
    load_manifest,
    normalize_text,
)

logger = logging.getLogger(__name__)

CORPUS_LABEL = "MVP_DEMO_CORPUS"
VALIDITY_NOTICE = (
    "Đây là bản demo nghiên cứu. Hiệu lực hiện hành của các văn bản chưa được xác minh; "
    "không dùng nội dung này làm tư vấn pháp lý."
)
MAX_EVIDENCE_CHARS = 1400
MAX_HISTORY_CHARS = 2000

GREETING_PATTERNS = (
    r"xin chào( bạn| anh| chị)?", r"chào( bạn| anh| chị)?", r"hello", r"hi", r"hey", r"hí",
)
THANKS_PATTERNS = (
    r"cảm ơn( bạn| anh| chị| nhé| ạ| nhiều)?", r"cam on( ban| anh| chi| nhe| a| nhieu)?",
    r"thanks", r"thank you", r"tks",
)
CAPABILITY_PATTERNS = (
    r"bạn là ai", r"ban la ai", r"bạn làm được gì", r"ban lam duoc gi",
    r"bạn có thể làm gì", r"ban co the lam gi", r"hướng dẫn sử dụng", r"huong dan su dung",
    r"giúp gì", r"giup gi",
)
GREETING_SUFFIX = r"[\s!.,?~]*"

EVIDENCE_MARKER = re.compile(r"\[([^\]]{1,40})\]")
EVIDENCE_ID = re.compile(r"\bE\s*(\d{1,2})\b", re.IGNORECASE)
ARTICLE_REFERENCE = re.compile(r"Điều\s+(\d+[a-zđ]?)", re.IGNORECASE)
QUOTE = re.compile(r"“([^”]{3,600})”|«([^»]{3,600})»|\"([^\"]{3,600})\"")
DATE_DMY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
DATE_TEXT = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.IGNORECASE)
CURRENT_EFFECT = re.compile(
    r"\b(hiện hành|đang có hiệu lực|còn hiệu lực|đang áp dụng|hiện đang áp dụng)\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """Bạn là trợ lý nghiên cứu pháp luật đất đai cho Hà Nội, trả lời bằng tiếng Việt.

Quy tắc bắt buộc:
1. Chỉ sử dụng các trích đoạn được cung cấp trong phần NGỮ CẢNH. Không dùng kiến thức bên ngoài.
2. Mỗi nhận định pháp lý phải kết thúc bằng mã trích dẫn dạng [E1], [E2] tương ứng với trích đoạn đã dùng.
3. Không được tự bịa số điều, số khoản, số văn bản, ngày có hiệu lực hoặc đường dẫn.
4. Nếu trích đoạn không đủ trả lời, hãy nói rõ: "Các trích đoạn hiện có không đủ để kết luận".
5. Không khẳng định văn bản đang có hiệu lực hiện hành. Hiệu lực được xem là chưa xác minh.
6. Nếu trích dẫn nguyên văn, phải sao chép chính xác và đặt trong dấu ngoặc kép.
7. Trả lời ngắn gọn (tối đa 6 câu hoặc 4 gạch đầu dòng), nêu căn cứ theo từng trích đoạn.

Mẫu câu trả lời:
- Kết luận trực tiếp dựa trên trích đoạn [E1].
- Điều kiện/ngoại lệ bổ sung [E2].
- Giới hạn: hiệu lực hiện hành chưa được xác minh."""


@dataclass
class ValidationResult:
    answer: str
    sources: list[dict]
    cited_ids: list[str]
    rejected_citations: list[str]
    warnings: list[str]
    valid: bool


def _is_greeting(message: str) -> bool:
    text = normalize_text(message)
    if len(text) > 60:
        return False
    for pattern in (*GREETING_PATTERNS, *THANKS_PATTERNS, *CAPABILITY_PATTERNS):
        if re.fullmatch(pattern + GREETING_SUFFIX, text):
            return True
    return False


def _greeting_answer(message: str, corpus: MvpCorpusIndex) -> str:
    text = normalize_text(message)
    if any(re.fullmatch(pattern + GREETING_SUFFIX, text) for pattern in THANKS_PATTERNS):
        return (
            "Rất vui được hỗ trợ. Bạn có thể hỏi tiếp về bồi thường, hỗ trợ, tái định cư "
            "khi Nhà nước thu hồi đất theo Nghị định 88/2024/NĐ-CP, hoặc về các nội dung "
            "sửa đổi tại Luật số 43/2024/QH15."
        )
    if any(re.fullmatch(pattern + GREETING_SUFFIX, text) for pattern in CAPABILITY_PATTERNS):
        documents = corpus.documents()
        names = ", ".join(
            f"{number}" for number in documents
        )
        return (
            "Tôi là trợ lý nghiên cứu pháp luật đất đai Hà Nội (bản demo). Tôi tìm trích đoạn "
            f"trong kho {CORPUS_LABEL} gồm {names} và trả lời kèm trích dẫn nguồn. "
            "Kho demo còn hẹp và hiệu lực văn bản chưa được xác minh."
        )
    return (
        "Xin chào! Tôi là trợ lý nghiên cứu pháp luật đất đai Hà Nội (bản demo). "
        "Bạn có thể hỏi về bồi thường, hỗ trợ, tái định cư khi Nhà nước thu hồi đất, "
        "hoặc về các nội dung sửa đổi của Luật số 43/2024/QH15."
    )


def _abstention_reason_message(reason: str) -> str:
    if reason == "out_of_domain":
        return (
            "Câu hỏi này không thuộc phạm vi pháp luật đất đai mà bản demo đang hỗ trợ. "
            "Bản demo chỉ tìm trong hai văn bản: Nghị định 88/2024/NĐ-CP (bồi thường, hỗ trợ, "
            "tái định cư) và Luật 43/2024/QH15 (sửa đổi một số luật)."
        )
    if reason == "outside_corpus_scope":
        return (
            "Nội dung này chưa có trong kho MVP_DEMO_CORPUS. Kho hiện chỉ gồm Nghị định "
            "88/2024/NĐ-CP về bồi thường, hỗ trợ, tái định cư và Luật 43/2024/QH15 về sửa đổi "
            "một số điều luật. Vì vậy tôi không thể kết luận cho câu hỏi này."
        )
    if reason == "explicit_citation_not_in_corpus":
        return (
            "Điều/văn bản bạn nêu không có trong kho MVP_DEMO_CORPUS, nên tôi không thể trích "
            "dẫn hoặc kết luận. Kho demo chỉ có Nghị định 88/2024/NĐ-CP và Luật 43/2024/QH15."
        )
    if reason == "weak_query_match":
        return (
            "Tôi tìm thấy một số trích đoạn nhưng chúng không khớp đủ với câu hỏi để trả lời "
            "an toàn. Vui lòng nêu rõ hơn đối tượng, loại đất hoặc tình huống thu hồi đất."
        )
    return (
        "Tôi không tìm thấy trích đoạn đủ rõ trong kho MVP_DEMO_CORPUS để trả lời câu hỏi này. "
        "Bạn có thể hỏi cụ thể hơn về bồi thường, hỗ trợ, tái định cư khi Nhà nước thu hồi đất."
    )


def _format_evidence(evidence: Iterable[Evidence]) -> str:
    blocks = []
    for index, item in enumerate(evidence, start=1):
        text = item.source_text.strip()
        if len(text) > MAX_EVIDENCE_CHARS:
            text = text[:MAX_EVIDENCE_CHARS].rstrip() + "…"
        blocks.append(
            f"[E{index}] {item.document_number} — {item.article_heading}\n"
            f"Nguồn chính thức: {item.source_url}\n"
            f"Trích đoạn:\n{text}"
        )
    return "\n\n".join(blocks)


def _bounded_history(history: Iterable[Any] | None) -> str:
    lines: list[str] = []
    used = 0
    for message in reversed(list(history or [])[-8:]):
        content = getattr(message, "content", str(message))
        role = "Người dùng" if getattr(message, "type", "") == "human" else "Trợ lý"
        line = f"{role}: {content}".strip()
        if used + len(line) > MAX_HISTORY_CHARS:
            break
        lines.append(line)
        used += len(line)
    return "\n".join(reversed(lines))


def _prompt(question: str, evidence: list[Evidence], history: Iterable[Any] | None = None):
    context = _format_evidence(evidence)
    previous = _bounded_history(history)
    user = f"CÂU HỎI: {question}\n\nNGỮ CẢNH:\n{context}"
    if previous:
        user = f"HỘI THOẠI TRƯỚC (chỉ để hiểu ngữ cảnh):\n{previous}\n\n{user}"
    user += (
        "\n\nHãy trả lời chỉ dựa trên NGỮ CẢNH, gắn [E#] cho từng nhận định, "
        "và nêu rõ nếu ngữ cảnh không đủ."
    )
    return [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user)]


def _evidence_text(evidence: Iterable[Evidence]) -> str:
    return normalize_text("\n".join(item.source_text for item in evidence))


def _date_is_supported(answer: str, evidence: Iterable[Evidence]) -> bool:
    corpus = _evidence_text(evidence)
    for day, month, year in DATE_DMY.findall(answer) + DATE_TEXT.findall(answer):
        day, month = int(day), int(month)
        variants = (
            f"{day:02d}/{month:02d}/{year}", f"{day}/{month}/{year}",
            f"{day:02d} tháng {month} năm {year}", f"{day} tháng {month} năm {year}",
        )
        if not any(variant in corpus for variant in variants):
            return False
    return True


def _quote_is_supported(answer: str, evidence: Iterable[Evidence]) -> bool:
    corpus = _evidence_text(evidence)
    for groups in QUOTE.findall(answer):
        quote = next((value for value in groups if value), "")
        quote = unicodedata.normalize("NFC", quote).strip().strip("…").strip()
        if len(quote) < 12:
            continue
        if normalize_text(quote) not in corpus:
            return False
    return True


def _article_references_supported(answer: str, cited: Iterable[Evidence]) -> bool:
    corpus = _evidence_text(cited)
    allowed = {item.article_number.replace("Điều ", "") for item in cited}
    allowed.update(number for number in ARTICLE_REFERENCE.findall(corpus))
    for number in ARTICLE_REFERENCE.findall(answer):
        if number.lower() not in {value.lower() for value in allowed}:
            return False
    return True


def _sanitize_current_effect(answer: str) -> tuple[str, bool]:
    parts: list[str] = []
    last = 0
    changed = False
    for match in QUOTE.finditer(answer):
        outside = CURRENT_EFFECT.sub("theo văn bản được trích dẫn", answer[last:match.start()])
        changed = changed or outside != answer[last:match.start()]
        parts.extend([outside, match.group(0)])
        last = match.end()
    outside = CURRENT_EFFECT.sub("theo văn bản được trích dẫn", answer[last:])
    changed = changed or outside != answer[last:]
    parts.append(outside)
    return "".join(parts), changed



def validate_answer(
    answer: str,
    evidence: list[Evidence],
    *,
    require_citation: bool = True,
) -> ValidationResult:
    rejected: list[str] = []
    warnings: list[str] = []
    by_id = {f"E{index}": item for index, item in enumerate(evidence, start=1)}
    cited: list[str] = []

    def replace_marker(match: re.Match) -> str:
        identifiers = EVIDENCE_ID.findall(match.group(1))
        if not identifiers:
            return match.group(0)
        kept = []
        for number in identifiers:
            key = f"E{int(number)}"
            if key in by_id:
                if key not in cited:
                    cited.append(key)
                kept.append(f"[{key}]")
            else:
                rejected.append(match.group(0))
        return "".join(kept)

    clean = EVIDENCE_MARKER.sub(replace_marker, answer).strip()

    if require_citation and not cited:
        warnings.append("Câu trả lời không có trích dẫn [E#] hợp lệ nên đã bị loại.")

    cited_evidence = [by_id[key] for key in cited]
    if cited_evidence and not _quote_is_supported(clean, cited_evidence):
        warnings.append("Có đoạn trích dẫn nguyên văn không khớp với nguồn đã trích.")
        clean = ""
    if cited_evidence and not _article_references_supported(clean, cited_evidence):
        warnings.append("Có số điều không xuất hiện trong nguồn đã trích.")
        clean = ""
    if cited_evidence and not _date_is_supported(clean, cited_evidence):
        warnings.append("Có ngày/ hiệu lực không xuất hiện trong nguồn đã trích.")
        clean = ""

    clean, changed = _sanitize_current_effect(clean)
    if changed:
        warnings.append("Đã thay thế cụm từ khẳng định hiệu lực hiện hành bằng cách diễn đạt trung tính.")

    valid = bool(clean) and (bool(cited) or not require_citation)
    if not valid:
        clean = ""
    return ValidationResult(
        answer=clean,
        sources=[item.to_source(key) for key, item in by_id.items() if key in cited],
        cited_ids=cited,
        rejected_citations=list(dict.fromkeys(rejected)),
        warnings=list(dict.fromkeys(warnings)),
        valid=valid,
    )


def _excerpt_summary(evidence: list[Evidence], notice: str) -> str:
    lines = [notice]
    for index, item in enumerate(evidence, start=1):
        text = item.source_text.strip()
        if len(text) > 420:
            text = text[:420].rstrip() + "…"
        lines.append(f"[E{index}] {item.document_number} — {item.article_heading}\n{text}")
    return "\n\n".join(lines)


class MvpRagPipeline:
    """Bounded demo workflow with at most one Gemini generation call per turn."""

    def __init__(self, corpus_path=None, *, provider=None, index: MvpCorpusIndex | None = None):
        self.corpus_path = corpus_path
        self.provider = provider
        self.index = index
        self.manifest: dict = {}

    @property
    def is_initialized(self) -> bool:
        return self.index is not None

    def startup(self) -> None:
        if self.index is None:
            if self.corpus_path:
                source = Path(self.corpus_path)
                self.index = MvpCorpusIndex.load(source)
                self.manifest = load_manifest(source.with_suffix(".manifest.json"))
            else:
                self.index = MvpCorpusIndex.load()
                self.manifest = load_manifest()
            logger.info("MVP demo corpus loaded: %d chunks", len(self.index.evidence))

    def info(self, settings: Config | None = None) -> dict:
        settings = settings or get_settings()
        self.startup()
        documents = list(self.index.documents().values())
        return {
            "corpus": CORPUS_LABEL,
            "publication_status": "not_published_not_current_law",
            "validity_status": "unknown",
            "review_status": "technical_validation_only",
            "document_count": len(documents),
            "chunk_count": len(self.index.evidence),
            "documents": documents,
            "limitations": self.manifest.get("excluded", {}),
            "disclaimer": VALIDITY_NOTICE,
            "llm_enabled": bool(settings.ENABLE_LIVE_LLM),
            "model": settings.MODEL,
            "retrieval": "BM25 lexical (deterministic, no embeddings)",
            "rate_limit_per_minute": settings.MVP_RATE_LIMIT_PER_MINUTE,
            "rate_limit_per_day": settings.MVP_RATE_LIMIT_PER_DAY,
        }

    def respond(self, query: str, history: Iterable[Any] | None = None) -> dict:
        settings = get_settings()
        self.startup()
        assert self.index is not None

        if _is_greeting(query):
            return self._response(
                _greeting_answer(query, self.index), "greeting", [], llm_used=False, warnings=[]
            )

        hits = self.index.search(query, top_k=settings.MVP_TOP_K)
        sufficiency = self.index.assess(
            query,
            hits,
            min_score=settings.MVP_MIN_SCORE,
            min_coverage=settings.MVP_MIN_COVERAGE,
        )
        if not sufficiency.sufficient:
            if sufficiency.reason == "document_overview":
                evidence = [hit.evidence for hit in hits]
            else:
                return self._response(
                    _abstention_reason_message(sufficiency.reason),
                    "abstained",
                    [],
                    llm_used=False,
                    warnings=[sufficiency.reason],
                    extra={"abstention_reason": sufficiency.reason},
                )

        evidence = [hit.evidence for hit in hits]
        if not settings.ENABLE_LIVE_LLM and self.provider is None:
            notice = (
                "Gemini đang tắt trong môi trường này. Hệ thống đã truy xuất các trích đoạn "
                "liên quan dưới đây nhưng không tạo câu trả lời tổng hợp. "
                f"{VALIDITY_NOTICE}"
            )
            return self._response(
                _excerpt_summary(evidence, notice),
                "llm_disabled",
                [item.to_source(f"E{index}") for index, item in enumerate(evidence, start=1)],
                llm_used=False,
                warnings=["live_llm_disabled"],
                extra={"abstention_reason": sufficiency.reason},
            )

        bounded = settings.model_copy(update={"MAX_LLM_CALLS_PER_TURN": 1})
        prompt = _prompt(query, evidence, history)
        try:
            if self.provider is not None:
                raw = self.provider.invoke(prompt)
            else:
                with settings_context(bounded), llm_turn(bounded):
                    raw = GeminiProvider(bounded).invoke(prompt)
        except LLMUnavailable as exc:
            logger.warning(
                "MVP LLM unavailable: %s upstream_status=%s",
                type(exc).__name__, exc.upstream_status,
            )
            notice = (
                "Dịch vụ Gemini hiện không khả dụng hoặc đã chạm giới hạn. "
                "Dưới đây là các trích đoạn nguồn đã truy xuất, chưa có câu trả lời tổng hợp. "
                f"{VALIDITY_NOTICE}"
            )
            return self._response(
                _excerpt_summary(evidence, notice),
                "llm_unavailable",
                [item.to_source(f"E{index}") for index, item in enumerate(evidence, start=1)],
                llm_used=False,
                warnings=["llm_unavailable"],
            )

        validation = validate_answer(str(raw), evidence)
        if not validation.valid:
            notice = (
                "Câu trả lời do AI tạo đã bị loại vì không đáp ứng kiểm tra trích dẫn/ngày/điều "
                "khoản. Dưới đây là các trích đoạn nguồn nguyên văn để bạn tự đối chiếu."
            )
            return self._response(
                _excerpt_summary(evidence, notice),
                "citation_rejected",
                [item.to_source(f"E{index}") for index, item in enumerate(evidence, start=1)],
                llm_used=True,
                warnings=validation.warnings,
                extra={"rejected_citations": validation.rejected_citations},
            )

        answer = f"{validation.answer}\n\n{VALIDITY_NOTICE}"
        return self._response(
            answer,
            "answered",
            validation.sources,
            llm_used=True,
            warnings=validation.warnings,
            extra={"rejected_citations": validation.rejected_citations},
        )

    def _response(
        self,
        answer: str,
        status: str,
        sources: list[dict],
        *,
        llm_used: bool,
        warnings: list[str],
        extra: dict | None = None,
    ) -> dict:
        self.startup()
        assert self.index is not None
        payload = {
            "answer": answer,
            "status": status,
            "sources": sources,
            "warnings": warnings,
            "rejected_citations": [],
            "llm_used": llm_used,
            "corpus": {
                "label": CORPUS_LABEL,
                "validity_status": "unknown",
                "review_status": "technical_validation_only",
                "document_count": len(self.index.documents()),
                "chunk_count": len(self.index.evidence),
                "limitations": self.manifest.get("excluded", {}),
                "disclaimer": VALIDITY_NOTICE,
            },
        }
        if extra:
            payload.update(extra)
        return payload
