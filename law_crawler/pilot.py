"""Small policy-gated pilot, separate from the inherited bulk crawler. No embeddings/LLM.

Requests are sequential, HTTPS-only, bounded, visibly identified and journaled. Every
redirect destination is checked *before* connecting. A robots permission is not a
terms-of-use approval; document downloads need both an explicit source decision and
an individually registered public endpoint.
"""
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import fcntl
from types import SimpleNamespace
from urllib import request, error, robotparser
from urllib.parse import urlsplit, urljoin, unquote

from batch.archive import safe_root
from batch.contracts import canonical, digest

USER_AGENT = "HanoiLandLawPilot/1.0 (limited public legal-document research; no bulk crawling)"
HOSTS = {"vbpl.vn", "vanban.chinhphu.vn", "hanoi.gov.vn", "congbao.hanoi.gov.vn",
         # Official national gazette portal (alternate official representation); policy checked separately.
         "congbao.chinhphu.vn",
         # National gazette file CDN referenced by official download links; policy checked separately.
         "g7.cdnchinhphu.vn",
         # Official public gazette file CDN serving the PDFs linked from congbao.chinhphu.vn
         # pages; robots.txt is absent (HTTP 404), so it needs an explicit approved policy.
         "congbao.cdnchinhphu.vn", "congbaocdn.chinhphu.vn",
         # Official Hanoi document subdomain reached by a congbao redirect; policy checked separately.
         "vanban.hanoi.gov.vn",
         # Attachment storage linked by official Hanoi metadata pages; policy checked separately.
         "storage-vnportal.vnpt.vn",
         # Exact attachment hosts observed in official portal links; independent policy check required.
         "datafiles.chinhphu.vn", "datafiles.hanoi.gov.vn"}
MAX_BYTES = 20 * 1024 * 1024
CHALLENGE_MARKERS = (b"cf-chl-", b"just a moment", b"attention required", b"verify you are human",
                     b"enable javascript and cookies to continue", b"access denied")


def is_access_challenge(body):
    """Detect an interstitial challenge page, not an ordinary contact-form CAPTCHA."""
    head = body[:200000].lower()
    return any(marker in head for marker in CHALLENGE_MARKERS)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def check_url(url, hosts=HOSTS):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in hosts or parsed.port not in {None, 443}
            or parsed.username or parsed.password or parsed.fragment or "\\" in url
            or re.search(r"[\x00-\x20]", url)):
        raise ValueError("Unapproved URL/redirect; review and explicitly register the exact HTTPS host")
    from backend.services.legal_service import _validate
    _validate({"source_url": url})
    if any(part in {".", ".."} for part in unquote(parsed.path).split("/")):
        raise ValueError("Dot-segment URL refused; review the exact official endpoint")
    return parsed.hostname


class RobotsPolicy:
    """Longest matching path wins; Allow wins ties (stdlib robotparser uses first match)."""
    def __init__(self, text):
        self.groups, agents, rules, self.delays, self.rates = [], [], [], [], []
        seen_directive = False
        text = text.lstrip("\ufeff")
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if ":" not in line: continue
            key, value = [part.strip() for part in line.split(":", 1)]
            key = key.lower()
            if key == "user-agent":
                if seen_directive:
                    self.groups.append((agents, rules)); agents, rules, seen_directive = [], [], False
                agents.append(value.lower())
            elif agents:
                seen_directive = True
                if key in {"allow", "disallow"} and value: rules.append((key == "allow", value))
                if key == "crawl-delay":
                    try: self.delays.append(max(0, float(value)))
                    except ValueError: raise ValueError("Unparseable robots crawl delay; stop for source review")
                if key == "request-rate":
                    match = re.fullmatch(r"(\d+)\s*/\s*(\d+)", value)
                    if not match or int(match[1]) == 0: raise ValueError("Unparseable robots request rate; stop for source review")
                    self.rates.append(SimpleNamespace(requests=int(match[1]), seconds=int(match[2])))
        if agents: self.groups.append((agents, rules))

    def can_fetch(self, agent, url):
        agent = agent.lower()
        groups = [(max((len(a) if a != "*" else 0 for a in agents if a == "*" or a in agent), default=-1), rules)
                  for agents, rules in self.groups]
        specificity = max((value for value, _ in groups), default=-1)
        path = unquote(urlsplit(url).path or "/")
        if urlsplit(url).query: path += "?" + unquote(urlsplit(url).query)
        matches = []
        for value, rules in groups:
            if value != specificity or value < 0: continue
            for allow, pattern in rules:
                terminal = pattern.endswith("$")
                expression = re.escape(unquote(pattern[:-1] if terminal else pattern)).replace(r"\*", ".*")
                if re.match("^" + expression + ("$" if terminal else ""), path):
                    matches.append((len(pattern.replace("*", "").rstrip("$")), allow))
        return max(matches)[1] if matches else True

    def crawl_delay(self, agent):
        return max(self.delays, default=0)

    def request_rate(self, agent):
        return max(self.rates, key=lambda r:r.seconds/r.requests) if self.rates else None


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass
class Response:
    status: int
    headers: dict
    body: bytes


def transport(url, user_agent=USER_AGENT):
    opener = request.build_opener(NoRedirect())
    req = request.Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    try:
        response = opener.open(req, timeout=40)
    except error.HTTPError as exc:
        response = exc
    with response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES: raise ValueError("Response exceeded 20 MiB; manual size review required")
        # Never persist cookies/authentication headers.
        headers = {k.lower(): v for k, v in response.headers.items() if k.lower() in {
            "content-type", "content-length", "content-disposition", "location", "retry-after",
            "etag", "last-modified", "date", "x-robots-tag"}}
        return Response(response.status, headers, body)


class PilotClient:
    def __init__(self, root, *, send=transport, clock=time.monotonic, sleep=time.sleep):
        self.root = safe_root(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.send, self.clock, self.sleep = send, clock, sleep
        self.last, self.robots, self.blocked = {}, {}, set()
        self.robots_absent = set()  # hosts that publish no robots.txt (HTTP 404); still need explicit approval
        self.lock = threading.RLock()  # deliberately serial across all hosts
        self.journal = self.root / "http-journal.jsonl"
        if self.journal.is_symlink(): raise ValueError("Journal symlink refused")
        # Preserve host stops and last request times across process restarts.
        if self.journal.exists():
            for line in self.journal.read_text().splitlines():
                event = json.loads(line)
                if event.get("status") in {403, 429}: self.blocked.add(event["host"])
                if event.get("purpose") == "policy" and event.get("status") == 404 and event["url"].endswith("/robots.txt"):
                    self.robots_absent.add(event["host"])
                try:
                    elapsed = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(event["retrieved_at"])).total_seconds())
                    self.last[event["host"]] = self.clock() - elapsed
                except (KeyError, ValueError):
                    pass

    @contextmanager
    def network_lock(self):
        path = safe_root(self.root / ".network.lock")
        with path.open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            if self.journal.exists():
                for line in self.journal.read_text().splitlines():
                    event = json.loads(line)
                    if event.get("status") in {401,403,429}: self.blocked.add(event["host"])
                    if event.get("purpose") == "policy" and event.get("status") == 404 and event["url"].endswith("/robots.txt"):
                        self.robots_absent.add(event["host"])
                    if event.get("access_control_detected"):
                        # Re-verify old detections against the preserved body so a broad marker
                        # false positive (e.g. an ordinary contact-form CAPTCHA) does not stop a host.
                        path = self.root / event.get("evidence_path", "")
                        try: challenged = is_access_challenge(path.read_bytes())
                        except (OSError, ValueError): challenged = True
                        if challenged: self.blocked.add(event["host"])
                    elapsed = max(0,(datetime.now(timezone.utc)-datetime.fromisoformat(event["retrieved_at"])).total_seconds())
                    self.last[event["host"]] = max(self.last.get(event["host"],-1e12),self.clock()-elapsed)
            yield

    def record(self, url, response, purpose):
        sha = hashlib.sha256(response.body).hexdigest()
        store = safe_root(self.root / "evidence" / sha)
        store.parent.mkdir(exist_ok=True)
        if store.exists():
            if hashlib.sha256(store.read_bytes()).hexdigest() != sha: raise ValueError("Evidence collision; restore original")
        else:
            with store.open("xb") as handle: handle.write(response.body)
        event = dict(url=url, host=urlsplit(url).hostname, status=response.status, headers=response.headers,
            retrieved_at=utcnow(), sha256=sha, bytes=len(response.body), purpose=purpose,
            evidence_path=store.relative_to(self.root).as_posix())
        with self.journal.open("a", encoding="utf-8") as handle: handle.write(canonical(event) + "\n")
        return event

    def fetch(self, url, *, purpose="discovery", policy=None, retries=3):
        if purpose not in {"policy", "discovery", "document"}: raise ValueError("Unknown acquisition purpose")
        if not 0 <= retries <= 3: raise ValueError("At most three retries are allowed")
        chain = []
        with self.lock, self.network_lock():
            for hop in range(6):
                host = check_url(url)
                if purpose == "policy" and (urlsplit(url).path != "/robots.txt" or urlsplit(url).query):
                    raise ValueError("Policy probes are restricted to robots.txt; metadata needs discovery permission and documents need source approval")
                if host in self.blocked: raise ValueError("Host stopped after access-control/rate response; manual review required")
                robots = self.robots.get(host)
                if purpose != "policy":
                    # A host that publishes no robots.txt is treated as unrestricted (RFC 9309
                    # 2.3.1.3), but document downloads still require the explicit per-URL source
                    # approval below; an unavailable/erroring robots.txt remains a hard stop.
                    if robots is not None and not robots.can_fetch(USER_AGENT, url):
                        raise ValueError("Robots disallows path; skip and request source approval")
                    if robots is None and host not in self.robots_absent:
                        raise ValueError("Robots unavailable; skip and request source approval")
                if purpose == "document":
                    if (not policy or policy.get("decision") != "approved_public_download"
                            or policy.get("host") != host or not policy.get("permission_evidence")
                            or url not in policy.get("approved_urls", [])):
                        raise ValueError("Document endpoint lacks explicit source approval/evidence; manual approval required")
                delay = max(3.0, float((policy or {}).get("min_interval_seconds", 3)))
                if robots:
                    delay = max(delay, robots.crawl_delay(USER_AGENT) or robots.crawl_delay("*") or 0)
                    rate = robots.request_rate(USER_AGENT) or robots.request_rate("*")
                    if rate: delay = max(delay, rate.seconds / rate.requests)
                response = None
                for attempt in range(retries + 1):
                    self.sleep(max(0, delay - (self.clock() - self.last.get(host, -1e12))))
                    self.last[host] = self.clock()
                    try:
                        response = self.send(url)
                    except (OSError, error.URLError, TimeoutError) as exc:
                        response = Response(0, {}, type(exc).__name__.encode())
                    event = self.record(url, response, purpose)
                    chain.append(event)
                    if response.status in {401, 403, 429}:
                        self.blocked.add(host)  # stricter than the required repeated-response stop
                        break
                    if response.status not in {0, 408, 500, 502, 503, 504} or attempt == retries: break
                    retry_after = response.headers.get("retry-after", "")
                    wait = 3 * (attempt + 1)
                    if retry_after:
                        try: wait = max(wait, float(retry_after))
                        except ValueError:
                            try: wait = max(wait, (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds())
                            except (ValueError, TypeError): raise ValueError("Invalid Retry-After; stop for manual review")
                    if wait > 300: raise ValueError("Retry-After exceeds this interactive pilot window; stop and retry manually later")
                    self.sleep(wait)
                if response.status in {301, 302, 303, 307, 308}:
                    destination = urljoin(url, response.headers.get("location", ""))
                    check_url(destination)  # never connect to an unregistered host or HTTP downgrade
                    if destination == url: raise ValueError("Redirect loop; skip source")
                    url = destination
                    continue
                if response.status != 200: return dict(ok=False, chain=chain, final_url=url, status=response.status)
                if is_access_challenge(response.body):
                    self.blocked.add(host)
                    with self.journal.open("a") as handle:
                        handle.write(canonical(dict(chain[-1],access_control_detected=True))+"\n")
                    return dict(ok=False, chain=chain, final_url=url, status="access_control_detected")
                return dict(ok=True, chain=chain, final_url=url, status=200, sha256=event["sha256"], evidence_path=event["evidence_path"])
            raise ValueError("Redirect limit exceeded; skip source")

    def inspect_robots(self, host):
        if host not in HOSTS: raise ValueError("Unapproved source host")
        result = self.fetch(f"https://{host}/robots.txt", purpose="policy", retries=0)
        if result["ok"]:
            body = (self.root / result["evidence_path"]).read_text(encoding="utf-8", errors="replace")
            body = body.lstrip("\ufeff")
            # A login/error HTML page is not a robots policy.
            if "<html" not in body.lower() and re.search(r"(?im)^\s*user-agent\s*:", body):
                self.robots[host] = RobotsPolicy(body)
                result["robots_parsed"] = True
            else:
                result["robots_parsed"] = False
        elif result["status"] == 404:
            # Absent robots.txt (HTTP 404) is recorded explicitly, not treated as a 403 stop.
            self.robots_absent.add(host)
            result["robots_absent"] = True
        return result


def original_filename(url, headers):
    disposition = headers.get("content-disposition", "")
    match = re.search(r"filename\*?=(?:UTF-8''|\")?([^\";]+)", disposition, re.I)
    value = unquote(match.group(1)) if match else unquote(urlsplit(url).path.rsplit("/", 1)[-1])
    if not value or Path(value).name != value or "\\" in value or value in {".", ".."}:
        raise ValueError("Unsafe/unknown original filename; manual source review required")
    return value


def acquire(client, candidate, policy, workspace):
    """One registered instrument with one/multiple original attachments; never self-approve law.

    ``policy`` is either one approved source record or a host -> approved source record
    mapping when an instrument has attachments on more than one approved host.
    """
    from preprocess.offline_ingestion import require_workspace, ingest, write_once, locked
    root = require_workspace(workspace)
    def policy_for(url):
        if "decision" in policy and "host" in policy:
            return policy
        return policy[urlsplit(url).hostname]
    ledger_dir = safe_root(root / "acquisitions")
    ledger_dir.mkdir(exist_ok=True)
    instrument_id = digest(candidate["official_identifier"])
    receipt_path = ledger_dir / (instrument_id + ".json")
    if receipt_path.exists(): return json.loads(receipt_path.read_text())
    endpoints = candidate.get("download_urls", [])
    if not endpoints: raise ValueError("No verified official endpoint; use the manual review queue")
    reservations = safe_root(ledger_dir / "reservations")
    with locked(root):
        reservations.mkdir(exist_ok=True)
        reservation = reservations / (instrument_id+".json")
        if not reservation.exists() and len(list(reservations.glob("*.json"))) >= 40: raise ValueError("40-instrument pilot cap reached")
        write_once(reservation,{"official_identifier":candidate["official_identifier"]})
    results = []
    for url in endpoints:
        fetched = client.fetch(url, purpose="document", policy=policy_for(url))
        if not fetched["ok"]:
            results.append(dict(url=url, state="blocked", http=fetched)); continue
        event = fetched["chain"][-1]
        name = original_filename(fetched["final_url"], event["headers"])
        target_dir = safe_root(root / "incoming" / event["sha256"])
        target_dir.mkdir(parents=True, exist_ok=True)
        target = safe_root(target_dir / name)
        raw = (client.root / event["evidence_path"]).read_bytes()
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != event["sha256"]: raise ValueError("Existing original differs; never overwrite")
        else:
            with target.open("xb") as handle: handle.write(raw)
        metadata = {k: candidate[k] for k in ("official_identifier", "official_number", "title", "document_type", "issuing_authority", "jurisdiction")}
        # The official metadata/document page is the recorded provenance; the exact transient
        # download URL, its HTTP metadata and SHA-256 are retained in the acquisition receipt.
        metadata.update(file=name, source_url=candidate["source_url"], acquired_at=event["retrieved_at"], is_synthetic=False,
            issuance_date=candidate.get("issuance_date"), publication_date=candidate.get("publication_date"))
        manifest_path = target_dir / "acquisition.json"
        write_once(manifest_path, metadata)
        parsed = ingest(root, manifest_path)
        results.append(dict(url=url, filename=name, sha256=event["sha256"], http=fetched,
                            stage=parsed, state="pending_legal_review" if parsed["status"] == "pending" else "quarantined"))
    receipt = dict(official_identifier=candidate["official_identifier"], acquired_at=utcnow(), artifacts=results,
                   candidate_sha256=digest(canonical(candidate)),source_policy_sha256=digest(canonical(policy)),
                   discovery_url=candidate['source_url'],review_status="pending", legal_validity="unknown", indexed=False, sealed=False)
    write_once(receipt_path, receipt)
    return receipt
