"""Official-page metadata candidates, not authoritative applicability determinations."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit, unquote

from bs4 import BeautifulSoup
from batch.contracts import canonical, digest
from law_crawler.pilot import check_url


def parse_date(value):
    if not value: return None
    for pattern in ("%d-%m-%Y", "%d/%m/%Y"):
        try: return datetime.strptime(value.strip(), pattern).date().isoformat()
        except ValueError: pass
    return None


def candidate_from_page(url, html, *, retrieved_at, evidence_sha256, topics, expected_number):
    check_url(url)
    soup = BeautifulSoup(html, "html.parser")
    attributes = {}
    attachment_links = []
    attachment_names = []
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) == 2:
            key = cells[0].get_text(" ", strip=True).rstrip(":")
            if key in {"Số ký hiệu", "Số, ký hiệu", "Số ký hiệu văn bản", "Ngày ban hành",
                       "Ngày có hiệu lực", "Ngày hiệu lực", "Loại văn bản", "Cơ quan ban hành",
                       "Trích yếu", "Văn bản liên quan"}:
                value = cells[1].get_text(" ", strip=True)
                if key in attributes and attributes[key] != value:
                    raise ValueError("Conflicting metadata tables; manual page review required")
                attributes[key] = value
            if key == "Tài liệu đính kèm":
                attachment_names = re.findall(r"[\w.\-]+\.(?:pdf|docx?|txt)", cells[1].get_text(" ", strip=True), re.I)
                for anchor in cells[1].select("a[href]"):
                    href = urljoin(url, anchor["href"].strip())
                    if re.search(r"\.(pdf|docx?|txt)(?:\?|$)", href, re.I) and href not in attachment_links:
                        attachment_links.append(href)
    number = attributes.get("Số ký hiệu") or attributes.get("Số, ký hiệu") or attributes.get("Số ký hiệu văn bản")
    if number != expected_number: raise ValueError("Official page number differs from discovered candidate; do not guess identity")
    issuer = attributes.get("Cơ quan ban hành")
    issuer_evidence = "official metadata page" if issuer else None
    if not issuer and number.endswith("/QĐ-UBND"):
        masthead = soup.get_text(" ", strip=True)[:5000]
        if re.search(r"ỦY BAN NHÂN DÂN THÀNH PHỐ HÀ NỘI", masthead, re.I):
            # Observed masthead plus document-number suffix; still pending human confirmation.
            issuer = "UBND Thành phố Hà Nội"
            issuer_evidence = "official page masthead and QĐ-UBND number suffix; pending human confirmation"
    required = ("Trích yếu", "Loại văn bản")
    if any(not attributes.get(key) for key in required) or not issuer:
        raise ValueError("Required official metadata missing; manual review required")
    title = attributes["Trích yếu"]
    if not attachment_links and attachment_names:
        for anchor in soup.select("a[href]"):
            href = urljoin(url, anchor["href"].strip())
            label = unquote(href.rsplit("/", 1)[-1])
            if any(name.lower() in label.lower() for name in attachment_names):
                if href not in attachment_links: attachment_links.append(href)
    if not attachment_links:
        # Gazette metadata pages may expose only a "Văn bản công báo" download action;
        # match the instrument number and issuance year to avoid unrelated sidebar files.
        number_tokens = re.findall(r"\d+", number)
        year = (parse_date(attributes.get("Ngày ban hành")) or "").split("-", 1)[0]
        for anchor in soup.select("a[href]"):
            label = anchor.get_text(" ", strip=True)
            href = urljoin(url, anchor["href"].strip())
            filename = unquote(href.rsplit("/", 1)[-1]).lower()
            if (re.search(r"\.(pdf|docx?|txt)(?:\?|$)", href, re.I)
                    and all(token in filename for token in number_tokens)
                    and (not year or year in filename)
                    and (label in {"Văn bản công báo", "Tài liệu đính kèm", "Tải về"}
                         or re.fullmatch(r"[\w.\-]+\.(?:pdf|docx?|txt)", label, re.I))
                    and href not in attachment_links):
                attachment_links.append(href)
    if not attachment_links:
        # Some official gazette pages publish the attachment as a direct filename link
        # outside the metadata table; unrelated sidebar links use action text instead.
        for anchor in soup.select("a[href]"):
            label = anchor.get_text(" ", strip=True)
            href = urljoin(url, anchor["href"].strip())
            if (re.fullmatch(r"[\w.\-]+\.(?:pdf|docx?|txt)", label, re.I)
                    and re.search(r"\.(pdf|docx?|txt)(?:\?|$)", href, re.I)
                    and href not in attachment_links):
                attachment_links.append(href)
    links = attachment_links
    attachment_status = "published_on_metadata_page" if links else "not_published_on_metadata_page"
    jurisdiction = "VN-HN" if "hanoi.gov.vn" in urlsplit(url).hostname else "VN"
    mentioned = sorted(set(re.findall(r"\d+/\d{4}/[\wĐđ-]+", title)) - {number})
    related = sorted(set(re.findall(r"\d+/\d{4}/[\wĐđ-]+", attributes.get("Văn bản liên quan", ""))) - {number})
    relationships = [dict(target_number=target, kind="mentioned_in_title", review_status="pending",
        evidence_url=url, evidence_quote=title) for target in mentioned]
    relationships += [dict(target_number=target, kind="declared_related_document", review_status="pending",
        evidence_url=url, evidence_quote=attributes["Văn bản liên quan"]) for target in related if target not in mentioned]
    return dict(official_identifier=f"{jurisdiction}:{issuer}:{number}",
        official_number=number, title=title, document_type=attributes["Loại văn bản"],
        issuing_authority=issuer, issuing_authority_evidence=issuer_evidence, jurisdiction=jurisdiction,
        territorial_applicability={"claim": "Hà Nội" if "Hà Nội" in title or "Thành phố" in title and jurisdiction == "VN-HN" else None,
            "status": "pending_scope_review", "basis": "official title; operative scope not yet inspected"},
        source_url=url, download_urls=links, attachment_status=attachment_status,
        issuance_date=parse_date(attributes.get("Ngày ban hành")),
        publication_date=None, effective_date=None, expiry_date=None, legal_validity="unknown",
        effective_date_claim={"date":parse_date(attributes.get("Ngày có hiệu lực") or attributes.get("Ngày hiệu lực")),
            "evidence":"official metadata page", "review_status":"pending", "may_be_amended":True},
        replacement_status="unknown", topics=topics, relationships=relationships,
        discovery_timestamp=retrieved_at, discovery_evidence_sha256=evidence_sha256,
        source_access_policy="discovery_only; attachment host blocked or source approval pending",
        state="discovered", review_status="pending", full_text_acquired=False)


def validate_catalog(candidates):
    identities, numbers = set(), set()
    for candidate in candidates:
        check_url(candidate["source_url"])
        identity = candidate["official_identifier"]
        number = (candidate["jurisdiction"], candidate["issuing_authority"], candidate["official_number"])
        if identity in identities or number in numbers: raise ValueError("Duplicate canonical instrument in discovery registry")
        identities.add(identity); numbers.add(number)
        if candidate["legal_validity"] != "unknown" or candidate["review_status"] != "pending":
            raise ValueError("Discovery cannot certify legal review/status")
        if not re.fullmatch(r"[0-9a-f]{64}", candidate["discovery_evidence_sha256"]): raise ValueError("Missing source evidence hash")
        if not candidate["topics"]: raise ValueError("Candidate needs a relevance classification")
        for url in candidate["download_urls"]: check_url(url)
    if len(identities) > 40: raise ValueError("Pilot registry exceeds 40-instrument scope")
    return dict(discovered=len(candidates), national=sum(c["jurisdiction"] == "VN" for c in candidates),
        hanoi=sum(c["jurisdiction"] == "VN-HN" for c in candidates),
        unknown_validity=len(candidates), missing_publication_date=sum(c["publication_date"] is None for c in candidates),
        topic_candidates=dict(Counter(t for c in candidates for t in c["topics"])),
        title_reference_claims=sum(len(c["relationships"]) for c in candidates))
