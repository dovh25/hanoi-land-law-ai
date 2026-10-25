"""Deterministic Vietnamese BM25 retrieval over the isolated MVP_DEMO_CORPUS.

The demo corpus is a small, immutable JSONL artifact built by
``scripts/build_mvp_demo_corpus.py``. Retrieval is lexical so the API can run inside a
Render Free instance without model weights, Qdrant, or network access at startup.
This module never writes to the database and never touches the strict Phase D release
path; every chunk remains ``validity_status=unknown``.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

DEFAULT_CORPUS_PATH = Path(__file__).resolve().parents[1] / "resources" / "mvp_demo_corpus.jsonl"
DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "resources" / "mvp_demo_corpus.manifest.json"

_WORD = re.compile(r"[0-9a-zà-ỹđ]+", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")

# Function words carry little retrieval signal and would inflate coverage scores.
STOPWORDS = frozenset(
    """
    va la cua cho trong khi duoc co khong nhung mot cac de tu den voi thi ma ve nay
    do nao gi the ra vao tren duoi boi vi nen cung nhu hoac neu hoi xin toi minh
    cau tra loi biet ro hon lam sao bao nhieu ai dau day
    """.split()
)

# Reference boilerplate is not topical signal for the scope gate.
GENERIC_REFERENCE_TERMS = frozenset(
    "nghi luat thong tu nd cp qh vbhn vpqh dieu khoan so".split()
)

# Questions must name one of these covered topics; the corpus has only two documents.
SCOPE_TOPICS = (
    "boi thuong", "ho tro", "tai dinh cu", "thu hoi", "thu hoi dat",
    "phuong an boi thuong", "gia dat", "tien su dung dat", "ghi no", "chi phi",
    "di doi mo ma", "vat nuoi", "on dinh doi song", "on dinh san xuat",
    "dao tao", "chuyen doi nghe", "tim kiem viec lam", "nha o",
    "cong trinh xay dung", "tai san gan lien voi dat", "hieu luc",
    "sua doi", "bo sung", "luat dat dai", "nghi dinh 88", "nghi dinh so 88",
    "43/2024", "88/2024",
)

# A conservative domain gate: unrelated questions abstain without calling the LLM.
DOMAIN_TERMS = (
    "dat dai", "thua dat", "dat o", "nha o", "boi thuong", "thu hoi", "tai dinh cu",
    "giai phong mat bang", "giay chung nhan", "quyen su dung", "chuyen muc dich",
    "gia dat", "thue dat", "dang ky dat", "dia chinh", "quy hoach", "cuong che",
    "khieu nai", "tranh chap", "bang gia dat", "dinh gia dat", "su dung dat",
    "so do", "ban do", "cap giay", "tai chinh ve dat", "nghia vu tai chinh",
    "khu tai dinh cu", "nguoi co dat", "nha nuoc thu hoi", "chu so huu",
    "tai san gan lien voi dat", "hop dong", "the chap", "chuyen nhuong", "tang cho",
    "thua ke", "luat dat dai", "nghi dinh", "dat",
)


def fold(text: str) -> str:
    """Lowercase, NFC-normalise and strip Vietnamese diacritics deterministically."""
    text = unicodedata.normalize("NFC", text).lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokenize(text: str) -> list[str]:
    """Index both accented and unaccented forms so unaccented queries still match."""
    tokens: list[str] = []
    for word in _WORD.findall(unicodedata.normalize("NFC", text).lower()):
        tokens.append(word)
        folded = fold(word)
        if folded != word:
            tokens.append(folded)
    return tokens


def query_terms(text: str) -> list[str]:
    """Unique content terms used for coverage scoring (accent-folded)."""
    seen: list[str] = []
    for word in _WORD.findall(fold(text)):
        if len(word) < 2 and not word.isdigit():
            continue
        if word in STOPWORDS or word in seen:
            continue
        seen.append(word)
    return seen


def normalize_text(text: str) -> str:
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFC", text)).strip().lower()


def _words(text: str) -> list[str]:
    return _WORD.findall(fold(text))


def is_domain_query(text: str) -> bool:
    padded = f" {' '.join(_words(text))} "
    return any(f" {term} " in padded for term in DOMAIN_TERMS)


def heading_coverage(query: str, heading: str) -> float:
    """Share of query focus terms present in an article heading.

    This is the topical-scope gate: a question about land-use duration may score well
    lexically against compensation text while still being outside this small corpus.
    """
    terms = [
        term for term in query_terms(query)
        if not term.isdigit() and term not in GENERIC_REFERENCE_TERMS
    ]
    if not terms:
        return 0.0
    heading_terms = set(_words(heading))
    return len([term for term in terms if term in heading_terms]) / len(terms)


def in_scope(text: str) -> bool:
    padded = f" {' '.join(_words(text))} "
    return any(f" {term} " in padded for term in SCOPE_TOPICS)



def explicit_reference(query: str) -> tuple[str | None, str | None]:
    """Return (document number fragment, article number) explicitly named in the query."""
    text = unicodedata.normalize("NFC", query)
    article = re.search(r"Điều\s+(\d+[a-zđ]?)", text, re.IGNORECASE)
    number = re.search(r"\b(\d{1,4}/\d{4}/(?:QH\d+|NĐ-CP|VBHN-VPQH))\b", text, re.IGNORECASE)
    if not number:
        # "Nghị định 88" / "Luật 43" refers to the leading document number.
        named = re.search(r"(?:Nghị định|Luật|Thông tư)\s+(?:số\s+)?(\d{1,4})\b", text, re.IGNORECASE)
        if named:
            number = named
    return (
        number.group(1) if number else None,
        f"Điều {article.group(1)}" if article else None,
    )


def is_generic_document_query(query: str, document: str | None = None) -> bool:
    """True for "Nghị định 88 quy định gì" style overviews with no specific topic."""
    if not document:
        return False
    filler = GENERIC_REFERENCE_TERMS | {"dinh"}
    words = [
        word for word in _words(query)
        if word not in STOPWORDS and not word.isdigit() and word not in filler
    ]
    return len(words) <= 1


def _document_matches(number: str, reference: str) -> bool:
    ref = fold(reference)
    num = fold(number)
    return len(ref) >= 2 and (num == ref or num.startswith(f"{ref}/"))




@dataclass(frozen=True)
class Evidence:
    """One retrievable provision chunk with exact provenance."""

    chunk_id: str
    document_number: str
    document_title: str
    document_type: str
    issuing_authority: str
    article_number: str
    article_heading: str
    heading_path: str
    source_url: str
    source_start: int
    source_end: int
    source_text: str
    validity_status: str
    review_status: str
    stage_id: str
    raw_sha256: str
    parsed_text_sha256: str
    corpus_label: str = "MVP_DEMO_CORPUS"
    tokens: tuple[str, ...] = field(default=(), repr=False, compare=False)

    @classmethod
    def from_record(cls, record: dict) -> "Evidence":
        # Field boost: article headings are short but highly topical, while body text is long.
        tokens = (
            tuple(tokenize(record["document_number"])) * 2
            + tuple(tokenize(record.get("article_heading", ""))) * 4
            + tuple(tokenize(record["source_text"]))
        )
        return cls(
            chunk_id=record["chunk_id"],
            document_number=record["document_number"],
            document_title=record["document_title"],
            document_type=record.get("document_type", ""),
            issuing_authority=record.get("issuing_authority", ""),
            article_number=record["article_number"],
            article_heading=record.get("article_heading", ""),
            heading_path=record.get("heading_path", ""),
            source_url=record["source_url"],
            source_start=int(record["source_start"]),
            source_end=int(record["source_end"]),
            source_text=record["source_text"],
            validity_status=record.get("validity_status", "unknown"),
            review_status=record.get("review_status", "technical_validation_only"),
            stage_id=record.get("stage_id", ""),
            raw_sha256=record.get("raw_sha256", ""),
            parsed_text_sha256=record.get("parsed_text_sha256", ""),
            corpus_label=record.get("corpus_label", "MVP_DEMO_CORPUS"),
            tokens=tokens,
        )

    def to_source(self, evidence_id: str, excerpt_chars: int = 700) -> dict:
        excerpt = self.source_text.strip()
        if len(excerpt) > excerpt_chars:
            excerpt = excerpt[:excerpt_chars].rstrip() + "…"
        return {
            "evidence_id": evidence_id,
            "chunk_id": self.chunk_id,
            "document_number": self.document_number,
            "document_title": self.document_title,
            "document_type": self.document_type,
            "issuing_authority": self.issuing_authority,
            "article_number": self.article_number,
            "article_heading": self.article_heading,
            "source_url": self.source_url,
            "source_start": self.source_start,
            "source_end": self.source_end,
            "excerpt": excerpt,
            "validity_status": self.validity_status,
            "review_status": self.review_status,
            "corpus_label": self.corpus_label,
        }


@dataclass(frozen=True)
class Hit:
    evidence: Evidence
    score: float
    coverage: float


@dataclass(frozen=True)
class Sufficiency:
    sufficient: bool
    reason: str
    coverage: float
    top_score: float
    document_count: int


class MvpCorpusIndex:
    """Immutable BM25 index. Construction is pure and requires no downloads."""

    def __init__(self, records: Iterable[dict], *, k1: float = 1.5, b: float = 0.75):
        self.evidence = tuple(Evidence.from_record(record) for record in records)
        if not self.evidence:
            raise ValueError("MVP demo corpus is empty")
        self.k1 = k1
        self.b = b
        self._lengths = tuple(len(item.tokens) for item in self.evidence)
        self._avg_length = sum(self._lengths) / len(self._lengths)
        self._df: dict[str, int] = {}
        self._tf: list[dict[str, int]] = []
        for item in self.evidence:
            counts: dict[str, int] = {}
            for token in item.tokens:
                counts[token] = counts.get(token, 0) + 1
            self._tf.append(counts)
            for token in counts:
                self._df[token] = self._df.get(token, 0) + 1
        self._n = len(self.evidence)

    @classmethod
    def load(cls, path: Path | str = DEFAULT_CORPUS_PATH) -> "MvpCorpusIndex":
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(
                f"MVP demo corpus not found at {source}; run scripts/build_mvp_demo_corpus.py"
            )
        records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        return cls(records)

    def _idf(self, token: str) -> float:
        df = self._df.get(token, 0)
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int = 8) -> list[Hit]:
        terms = [token for token in tokenize(query) if token not in STOPWORDS]
        if not terms:
            return []
        unique = list(dict.fromkeys(terms))
        scores = [0.0] * self._n
        for term in unique:
            idf = self._idf(term)
            if idf <= 0:
                continue
            for index, counts in enumerate(self._tf):
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * self._lengths[index] / self._avg_length
                )
                scores[index] += idf * frequency * (self.k1 + 1) / denominator
        content_terms = set(query_terms(query))
        hits = []
        for index, score in enumerate(scores):
            if score <= 0:
                continue
            document_terms = set(fold(token) for token in self._tf[index])
            coverage = (
                len(content_terms & document_terms) / len(content_terms) if content_terms else 0.0
            )
            # A short article heading containing several query terms is a stronger topical
            # signal than repeated body mentions alone.
            heading_terms = set(tokenize(self.evidence[index].article_heading))
            heading_bonus = sum(self._idf(term) for term in unique if term in heading_terms)
            heading_bonus += 2.5 * len(self._heading_bigram_hits(query, self.evidence[index].article_heading))
            hits.append(Hit(
                self.evidence[index],
                round(score + 0.8 * heading_bonus, 4),
                round(coverage, 4),
            ))
        hits.sort(key=lambda hit: (-hit.score, hit.evidence.document_number, hit.evidence.source_start))
        ordered = self._apply_explicit_reference(query, hits)
        return self._diversify(ordered, top_k)

    def _heading_bigram_hits(self, query: str, heading: str) -> set[str]:
        words = [word for word in _words(query) if word not in STOPWORDS]
        heading_words = _words(heading)
        query_pairs = {f"{a} {b}" for a, b in zip(words, words[1:])}
        heading_pairs = {f"{a} {b}" for a, b in zip(heading_words, heading_words[1:])}
        return query_pairs & heading_pairs

    def _diversify(self, hits: list[Hit], top_k: int, max_per_article: int = 2) -> list[Hit]:
        counts: dict[tuple[str, str], int] = {}
        primary: list[Hit] = []
        overflow: list[Hit] = []
        for hit in hits[:24]:
            key = (hit.evidence.document_number, hit.evidence.article_number)
            if counts.get(key, 0) < max_per_article:
                primary.append(hit)
                counts[key] = counts.get(key, 0) + 1
            else:
                overflow.append(hit)
        return (primary + overflow)[:top_k]


    def _apply_explicit_reference(self, query: str, hits: list[Hit]) -> list[Hit]:
        """Honour an explicit "Điều N" / "Nghị định N" lookup without inventing answers."""
        document, article = explicit_reference(query)
        if article:
            matched = [hit for hit in hits if hit.evidence.article_number == article]
            if matched:
                if document and not any(
                    _document_matches(hit.evidence.document_number, document) for hit in matched
                ):
                    return []
                return [hit for hit in matched if not document or _document_matches(
                    hit.evidence.document_number, document
                )]
            return []
        if document:
            if is_generic_document_query(query, document):
                overview = [
                    hit for hit in hits
                    if hit.evidence.article_number == "Điều 1"
                    and _document_matches(hit.evidence.document_number, document)
                ]
                if overview:
                    return overview
            return [hit for hit in hits if _document_matches(hit.evidence.document_number, document)]
        return hits

    def assess(
        self,
        query: str,
        hits: list[Hit],
        *,
        min_score: float,
        min_coverage: float,
        min_heading_coverage: float = 0.30,
        min_evidence: int = 1,
    ) -> Sufficiency:
        if not is_domain_query(query):
            return Sufficiency(False, "out_of_domain", 0.0, 0.0, 0)
        document, article = explicit_reference(query)
        generic_document = is_generic_document_query(query, document)
        if not in_scope(query) and not generic_document:
            return Sufficiency(False, "outside_corpus_scope", 0.0, 0.0, 0)
        if article and not hits:
            return Sufficiency(False, "explicit_citation_not_in_corpus", 0.0, 0.0, 0)
        if not hits:
            return Sufficiency(False, "no_evidence", 0.0, 0.0, 0)
        top = hits[0]
        if generic_document and top.evidence.article_number == "Điều 1":
            return Sufficiency(True, "document_overview", top.coverage, top.score, len(hits))
        strong = [hit for hit in hits if hit.score >= min_score]
        if top.score < min_score:
            return Sufficiency(False, "insufficient_evidence", top.coverage, top.score, 0)
        if top.coverage < min_coverage:
            return Sufficiency(False, "weak_query_match", top.coverage, top.score, 0)
        explicit_match = article and all(hit.evidence.article_number == article for hit in hits)
        if not explicit_match and not is_generic_document_query(query, document):
            if heading_coverage(query, top.evidence.article_heading) < min_heading_coverage:
                return Sufficiency(False, "outside_corpus_scope", top.coverage, top.score, len(strong))
        if len(strong) < min_evidence:
            return Sufficiency(False, "insufficient_evidence", top.coverage, top.score, len(strong))
        return Sufficiency(True, "sufficient", top.coverage, top.score, len(strong))


    def documents(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for item in self.evidence:
            info = result.setdefault(
                item.document_number,
                {
                    "document_number": item.document_number,
                    "title": item.document_title,
                    "document_type": item.document_type,
                    "issuing_authority": item.issuing_authority,
                    "source_url": item.source_url,
                    "validity_status": item.validity_status,
                    "review_status": item.review_status,
                    "chunks": 0,
                },
            )
            info["chunks"] += 1
        return result


def load_manifest(path: Path | str = DEFAULT_MANIFEST_PATH) -> dict:
    source = Path(path)
    if not source.is_file():
        return {}
    return json.loads(source.read_text(encoding="utf-8"))
