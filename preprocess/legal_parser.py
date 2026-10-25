"""Bounded local extraction and conservative Vietnamese hierarchy; no status inference."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import unicodedata
import zipfile
from xml.etree import ElementTree as ET

PARSER_VERSION = "local-legal-parser-v3"
# A real heading is "Điều N." or "Điều N:"; a wrapped cross-reference ("Điều 86 của Luật này")
# starts with the number followed by a space, so it must not be treated as a heading.
ARTICLE = re.compile(r"^(Điều\s+(\d+[a-zđ]?))[.:](?:\s|$)", re.I)
PATTERNS = [
    # Container headings are standalone lines in the gazette ("Chương III", "Mục 1"). Requiring the
    # line to end after the heading avoids reading a wrapped cross-reference ("Mục 5 Chương III của
    # Nghị định này.", "Phụ lục ban hành kèm theo Nghị định này;", "Phần diện tích giao đất") as a
    # new heading, which otherwise detaches later articles/clauses from their legal parent.
    ("annex", re.compile(r"^(Phụ lục|Phụ đính|Tài liệu kèm theo)(?:\s+([^\s.:]+))?\s*$", re.I)),
    ("part", re.compile(r"^(Phần\s+(?:thứ\s+)?([^\s.:]+))\s*$", re.I)),
    ("chapter", re.compile(r"^(Chương\s+([IVXLCDM]+|\d+))\s*$", re.I)),
    ("subsection", re.compile(r"^(Tiểu mục\s+([IVXLCDM]+|\d+))\s*$", re.I)),
    ("section", re.compile(r"^(Mục\s+([IVXLCDM]+|\d+))\s*$", re.I)),
    ("article", ARTICLE),
    ("clause", re.compile(r"^((\d+[a-zđ]?)\.)\s+", re.I)),
    ("point", re.compile(r"^(([a-zđ])\))\s+", re.I)),
]
RANK = {"annex": 0, "part": 1, "chapter": 2, "section": 3, "subsection": 4,
        "article": 5, "clause": 6, "point": 7, "table": 8, "unstructured": 8}
# A gazette annex that is an administrative form ("MẪU QUYẾT ĐỊNH ...") uses the same
# "Điều 1." style as the instrument itself. Its headings are placeholders, not provisions.
FORM_ANNEX = re.compile(r"(?:\bM[ẪA]U\b|\bMẫu\s+số\b|Kèm\s+theo|ban\s+hành\s+kèm\s+theo)", re.I)


class ExtractionError(ValueError):
    """Fail closed, with an operator action rather than silent loss."""


def normalize(text):
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    if "\ufffd" in text or "\x00" in text:
        raise ExtractionError("Invalid text encoding; supply a verified UTF-8/text-layer source")
    return text.replace("\u00a0", " ").lstrip("\ufeff")


@dataclass
class Block:
    text: str
    kind: str = "text"
    page: int | None = None
    rows: list | None = None


def _tidy_pdf_page(text):
    """Collapse position-preserving PDF whitespace without joining lines.

    pypdf's plain mode often inserts spaces *inside* Vietnamese syllables on justified
    gazette lines ("b ồi thư ờng"); pdfminer keeps the words intact but pads justified
    gaps with runs of spaces. Collapsing horizontal runs recovers the words while
    preserving the line structure used by the hierarchy parser.
    """
    text = text.replace("\x0c", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.rstrip() for line in text.split("\n"))


def _pdfminer_pages(path):
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer
    pages = []
    for page in extract_pages(str(path)):
        pages.append("".join(element.get_text() for element in page if isinstance(element, LTTextContainer)))
    return pages


def _strip_gazette_running_lines(pages, report):
    """Remove repeated Official Gazette mastheads and bare page numbers only.

    The function is deliberately narrow: it acts only when most pages carry a
    ``CÔNG BÁO/Số`` masthead, and only on lines in the top/bottom three non-empty
    lines. Legal text is never matched by these patterns.
    """
    mastheads = [any("CÔNG BÁO/SỐ" in line.upper() for line in page.splitlines()[:4]) for page in pages]
    if sum(mastheads) < max(1, len(pages) // 2):
        return pages, 0
    cleaned, stripped = [], 0
    for page in pages:
        lines = page.splitlines()
        nonempty = [index for index, line in enumerate(lines) if line.strip()]
        boundary = set(nonempty[:3] + nonempty[-3:])
        kept = []
        for index, line in enumerate(lines):
            candidate = line.strip()
            if index in boundary and ("CÔNG BÁO/SỐ" in candidate.upper()
                                      or re.fullmatch(r"\d{1,3}", candidate)):
                stripped += 1
                continue
            kept.append(line)
        value = "\n".join(kept).strip("\n")
        cleaned.append(value if value.strip() else page)
    report["stripped_running_lines"] = stripped
    return cleaned, stripped


def extract(path, *, report=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
        raise ExtractionError("Use a regular local file of at most 20 MiB; symlinks are refused")
    suffix = path.suffix.lower()
    report = {} if report is None else report
    report.update(format=suffix.lstrip("."), extractor=f"{PARSER_VERSION}:{suffix.lstrip('.') or 'unknown'}")
    warnings = []
    if suffix == ".txt":
        blocks = [Block(normalize(path.read_text(encoding="utf-8")))]
        report["blocks"] = len(blocks)
    elif suffix in {".html", ".htm"}:
        from bs4 import BeautifulSoup, NavigableString, Comment
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        if soup.find(["img", "object", "iframe", "embed", "svg"]):
            raise ExtractionError("HTML embedded visual/attachment content unsupported; supply a reviewed text-body rendition")
        for tag in soup.find_all(["script", "style", "head"]):
            tag.decompose()
        blocks, pending = [], []
        def flush():
            if pending:
                text = "".join(pending)
                if text.strip():
                    blocks.append(Block(text))
                pending.clear()
        def walk(node):
            if isinstance(node, Comment):
                return
            if isinstance(node, NavigableString):
                pending.append(str(node)); return
            if node.name == "table":
                flush()
                if node.find("table"):
                    raise ExtractionError("Nested HTML tables need a reviewed flattened rendition")
                rows = [[cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"], recursive=False)]
                        for row in node.find_all("tr")]
                blocks.append(Block("\n".join(" | ".join(row) for row in rows), "table", rows=rows))
                return
            boundary = node.name in {"p", "div", "section", "article", "h1", "h2", "h3", "h4", "li", "br", "hr"}
            if boundary: pending.append("\n")
            for child in node.children: walk(child)
            if boundary: pending.append("\n")
        walk(soup.body or soup); flush()
        report["blocks"] = len(blocks)
    elif suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted or len(reader.pages) > 500:
            raise ExtractionError("Encrypted/oversized PDF refused; supply a reviewed text-based PDF")
        page_count = len(reader.pages)
        fallback_pages = []
        try:
            raw_pages = _pdfminer_pages(path)
        except Exception:
            raw_pages = [""] * page_count
        if len(raw_pages) != page_count:
            raw_pages = [""] * page_count
        for index in range(page_count):
            if not raw_pages[index].strip():
                plain = reader.pages[index].extract_text() or ""
                if plain.strip():
                    raw_pages[index] = plain
                    fallback_pages.append(index + 1)
        raw_pages = [_tidy_pdf_page(page) for page in raw_pages]
        raw_pages, stripped = _strip_gazette_running_lines(raw_pages, report)
        pages = [(number, text) for number, text in enumerate(raw_pages, 1)]
        text_pages = [number for number, text in pages if text.strip()]
        if not text_pages:
            raise ExtractionError("PDF has no extractable text layer; OCR is unsupported, obtain reviewed transcription")
        last_text_page = text_pages[-1]
        blank_pages = [number for number, text in pages if not text.strip()]
        blocks = []
        for number, text in pages:
            if not text.strip():
                # A non-text *trailing* page is normally a blank gazette signature leaf; skip it
                # with a warning. A non-text page before the last text page could hide content, so
                # it still quarantines rather than silently dropping legal text.
                if number > last_text_page:
                    warnings.append(f"Trailing non-text PDF page {number} skipped; verify visually (OCR unsupported)")
                    continue
                raise ExtractionError(f"PDF page {number} has no text; OCR is unsupported, obtain reviewed transcription")
            blocks.append(Block(text, page=number))
        report.update(pages=page_count, text_pages=text_pages, blank_pages=blank_pages,
                      fallback_pages=fallback_pages, page_characters={str(n): len(t) for n, t in pages})
        if fallback_pages:
            warnings.append(f"PDF text extractor fallback used on pages {fallback_pages}; verify visually")
        if stripped:
            warnings.append(f"Stripped {stripped} gazette masthead/page-number lines; legal text untouched")
        warnings.append("PDF reading order/tables/footnotes require visual review; OCR not performed")
    elif suffix == ".docx":
        from docx import Document
        from docx.table import Table
        with zipfile.ZipFile(path) as archive:
            if len(archive.infolist()) > 2000 or sum(i.file_size for i in archive.infolist()) > 64 * 1024 * 1024:
                raise ExtractionError("DOCX expansion limit exceeded; split/review the source")
            # These features cannot safely be reconstructed by python-docx's body iterator.
            xml = archive.read("word/document.xml")
            if any(marker in xml for marker in (b"<w:numPr", b"<w:ins", b"<w:del", b"<w:altChunk", b"<w:txbxContent", b"<w:drawing", b"<w:sdt")):
                raise ExtractionError("DOCX automatic numbering/tracked changes/embedded content unsupported; supply verified plain-text rendition")
            doc = Document(path)
            blocks = []
            for item in doc.iter_inner_content():
                if isinstance(item, Table):
                    if item._tbl.xpath('.//w:tbl'):
                        raise ExtractionError("Nested DOCX tables require a reviewed text/HTML rendition")
                    rows = [[cell.text for cell in row.cells] for row in item.rows]
                    blocks.append(Block("\n".join(" | ".join(row) for row in rows), "table", rows=rows))
                else:
                    style = item.style
                    while style is not None:
                        if style.element.xpath('.//w:numPr'):
                            raise ExtractionError("DOCX inherited automatic numbering unsupported; supply a reviewed explicit-number rendition")
                        style = style.base_style
                    blocks.append(Block(item.text))
            for name in sorted(archive.namelist()):
                if re.fullmatch(r"word/(?:footnotes|endnotes|header\d+|footer\d+)\.xml", name):
                    element = ET.fromstring(archive.read(name))
                    texts = [el.text for el in element.iter() if el.tag.endswith("}t") and el.text]
                    if texts: blocks.append(Block("\n".join(texts)))
            warnings.append("DOCX notes/headers/footers appended in named-part order; verify citation placement")
        report["blocks"] = len(blocks)
    else:
        raise ExtractionError("Unsupported format; use UTF-8 HTML/TXT, text PDF, or DOCX (OCR unsupported)")
    blocks = [Block(normalize(b.text), b.kind, b.page, b.rows) for b in blocks if b.text.strip()]
    if not blocks or sum(len(b.text) for b in blocks) > 4_000_000:
        raise ExtractionError("Empty or oversized extraction; review source and split into smaller files")
    return blocks, warnings


def hierarchy(blocks):
    """Non-overlapping spans cover *all* extracted characters; ambiguous numbering quarantines."""
    text = ""
    ranges = []
    for block in blocks:
        start = len(text)
        text += block.text + "\n"
        ranges.append((start, len(text), block))
    nodes, stack, seen = [], [], set()
    def node(kind, identifier, heading, start, parent):
        locator = (nodes[parent]["locator"] + "/" if parent is not None else "") + f"{kind}:{identifier}"
        if locator in seen:
            raise ExtractionError("Repeated legal locator; review TOC, numbering or combined instruments before retrying")
        seen.add(locator)
        nodes.append(dict(kind=kind, locator=locator, heading=heading, parent=parent,
                          start=start, end=len(text), page=None, rows=None))
        return len(nodes) - 1
    for start, end, block in ranges:
        if block.kind == "table":
            if nodes: nodes[-1]["end"] = start
            index = node("table", str(start), "Bảng", start, stack[-1] if stack else None)
            nodes[index].update(end=end, page=block.page, rows=block.rows)
            continue
        position = start
        for line in (block.text + "\n").splitlines(keepends=True):
            stripped = line.strip()
            match = next(((kind, pattern.match(stripped)) for kind, pattern in PATTERNS if pattern.match(stripped)), None)
            if match:
                kind, found = match
                inside_form = any(nodes[i]["kind"] == "annex" and nodes[i].get("form") for i in stack)
                if inside_form and kind in {"article", "clause", "point"}:
                    # The form's "Điều 1." / "1." labels are template text, not provisions.
                    position += len(line)
                    continue
                identifier = found.group(2) or "1"
                if kind == "clause" and not any(nodes[i]["kind"] == "article" for i in stack):
                    raise ExtractionError("Numbered clause outside an article; review extraction before approval")
                if kind == "point" and not any(nodes[i]["kind"] in {"article", "clause"} for i in stack):
                    raise ExtractionError("Lettered point outside an article; review extraction before approval")
                while stack and RANK[nodes[stack[-1]]["kind"]] >= RANK[kind]: stack.pop()
                if nodes: nodes[-1]["end"] = position
                heading = found.group(1) if kind in {"clause", "point"} else stripped
                index = node(kind, identifier.casefold(), heading, position, stack[-1] if stack else None)
                nodes[index]["page"] = block.page
                if kind == "annex" and FORM_ANNEX.search(text[position:position + 800]):
                    nodes[index]["form"] = True
                stack.append(index)
            elif not nodes:
                node("unstructured", "preamble", "Mở đầu", position, None)
            elif nodes[-1]["end"] != len(text) and position >= nodes[-1]["end"]:
                # Content after a table remains attached to the legal context, not the table.
                node("unstructured", str(position), "Nội dung tiếp theo", position, stack[-1] if stack else None)
            position += len(line)
    if nodes: nodes[-1]["end"] = len(text)
    return dict(parser_version=PARSER_VERSION, text=text, text_sha256=hashlib.sha256(text.encode()).hexdigest(), nodes=nodes)
