"""Explicit pilot commands; offline registry/report operations are the default."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from batch.contracts import canonical
from law_crawler.catalog import candidate_from_page, validate_catalog
from law_crawler.pilot import PilotClient, RobotsPolicy, acquire
from preprocess.offline_ingestion import write_once


def discover(seeds, network_root, destination):
    client = PilotClient(network_root)
    # Policy/discovery only; never follow attachment links here.
    journal = [json.loads(line) for line in client.journal.read_text().splitlines()] if client.journal.exists() else []
    cached = {e["url"]:e for e in journal if e["status"] == 200 and e["purpose"] == "discovery"}
    hosts = sorted({urlsplit(s["url"]).hostname for s in seeds})
    for host in hosts:
        evidence = next((e for e in reversed(journal) if e["url"] == f"https://{host}/robots.txt" and e["status"] == 200), None)
        if evidence:
            client.robots[host] = RobotsPolicy((client.root/evidence["evidence_path"]).read_text())
        else:
            client.inspect_robots(host)
    candidates, failures = [], []
    for seed in seeds:
        try:
            evidence = cached.get(seed["url"])
            if evidence is None:
                result = client.fetch(seed["url"], retries=0)
                if not result["ok"]: raise ValueError("Official metadata page unavailable; manual review needed")
                evidence = result["chain"][-1]
            candidate = candidate_from_page(seed["url"], (client.root/evidence["evidence_path"]).read_bytes(),
                retrieved_at=evidence["retrieved_at"],evidence_sha256=evidence["sha256"],topics=seed["topics"],expected_number=seed["number"])
            candidates.append(candidate)
        except ValueError as exc:
            failures.append(dict(number=seed["number"],url=seed["url"],reason=str(exc)))
    result = dict(schema_version=2,notice="Official metadata candidates only; no legal review or full-text acquisition implied",
        candidates=candidates,failures=failures,summary=validate_catalog(candidates))
    write_once(Path(destination),result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command",required=True)
    p=commands.add_parser("discover"); p.add_argument("--network",action="store_true",required=True)
    p.add_argument("--seeds",default="corpus/pilot-seeds.json");p.add_argument("--network-root",default="data/phase-d-network")
    p.add_argument("--destination",required=True)
    p=commands.add_parser("acquire");p.add_argument("--network",action="store_true",required=True)
    p.add_argument("--registry",default="corpus/phase-d-candidates.json");p.add_argument("--policies",default="corpus/source-approvals.json")
    p.add_argument("--workspace",default="data/phase-d-corpus-v2");p.add_argument("--network-root",default="data/phase-d-network")
    p=commands.add_parser("prepare");p.add_argument("--registry",default="corpus/phase-d-candidates.json")
    p.add_argument("--policies",default="corpus/source-approvals.json");p.add_argument("--workspace",default="data/phase-d-corpus-v2")
    p.add_argument("--release-name",default="phase-d-authoritative-pilot-draft-v2")
    p=commands.add_parser("prepare-d1");p.add_argument("--registry",default="corpus/phase-d1-instruments.json")
    p.add_argument("--policies",default="corpus/phase-d1-source-approvals.json");p.add_argument("--workspace",default="data/phase-d-corpus-v2")
    p.add_argument("--release-name",default="phase-d1-authoritative-pilot-draft")
    p=commands.add_parser("scan-manual-inbox")
    p.add_argument("--registry",nargs="+",default=["corpus/phase-d-candidates.json","corpus/phase-d1-instruments.json"])
    p.add_argument("--workspace",default="data/phase-d-corpus-v2");p.add_argument("--ingest",action="store_true")
    args=parser.parse_args()
    if args.command == "discover":
        seeds=json.loads(Path(args.seeds).read_text())["seeds"]
        if len(seeds)>40: parser.error("Pilot discovery is capped at 40 instruments")
        result=discover(seeds,args.network_root,args.destination)
        print(canonical(result["summary"]))
    elif args.command == "prepare":
        from law_crawler.reporting import prepare
        result=prepare(args.registry,args.policies,args.workspace,args.release_name)
        print(canonical({k:v for k,v in result.items() if k!='quality'}))
    elif args.command == "prepare-d1":
        from law_crawler.reporting import prepare_d1
        result=prepare_d1(args.registry,args.policies,args.workspace,args.release_name)
        print(canonical({k:v for k,v in result.items() if k!='quality'}))
    elif args.command == "scan-manual-inbox":
        from law_crawler.manual_inbox import scan
        result=scan(args.registry,args.workspace,ingest_files=args.ingest)
        print(canonical({k:len(v) if isinstance(v,list) else v for k,v in result.items()
                         if k in {'matched','ingested','quarantined','duplicates','ambiguous','unmatched','unconfirmed'}}))
    else:
        candidates=json.loads(Path(args.registry).read_text())["candidates"]
        validate_catalog(candidates)
        policies=json.loads(Path(args.policies).read_text())["sources"]
        from preprocess.offline_ingestion import require_workspace
        require_workspace(args.workspace)
        client=PilotClient(args.network_root)
        results=[]
        for candidate in candidates:
            urls=candidate["download_urls"]
            if not urls: continue
            hosts={urlsplit(url).hostname for url in urls}
            policies_by_host={host:next((p for p in policies if p["host"]==host),None) for host in hosts}
            if any(not policy or policy["decision"]!="approved_public_download" for policy in policies_by_host.values()):
                results.append({"number":candidate["official_number"],"state":"blocked_policy",
                    "hosts":{host:(policy["decision"] if policy else "unregistered") for host,policy in policies_by_host.items()}})
                continue
            for host in hosts: client.inspect_robots(host)
            # One instrument may have several attachments; each endpoint must belong to its approved host.
            for url in urls:
                policy=policies_by_host[urlsplit(url).hostname]
                if url not in policy.get("approved_urls",[]):
                    results.append({"number":candidate["official_number"],"state":"blocked_policy",
                        "reason":"endpoint not individually approved","url":url});break
            else:
                results.append(acquire(client,candidate,policies_by_host,args.workspace))
        print(canonical(results))


if __name__=="__main__": main()
