"""Explicit local-only operator commands; never reads application settings or root .env."""
import argparse
import json
from pathlib import Path
from batch.contracts import canonical
from preprocess import offline_ingestion as service


def _load(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError("Decision file must contain one JSON object")
    return value


def _packet_summary(root, stage_id):
    from preprocess.review_packets import slug
    from preprocess.offline_ingestion import load_stage
    stage = load_stage(root, stage_id)
    directory = root / "review-packets" / slug(stage)
    checklist_path = directory / "checklist.json"
    if not checklist_path.is_file():
        raise ValueError("Packet not generated yet; run the packets command")
    checklist = json.loads(checklist_path.read_text())
    if checklist.get("stage_id") != stage_id:
        raise ValueError("Packet belongs to another stage; regenerate it")
    return dict(packet=directory.relative_to(root).as_posix(), report=(directory / "report.md").relative_to(root).as_posix(),
        checklists=checklist)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default="data/offline-ingestion")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    p = commands.add_parser("ingest"); p.add_argument("--manifest", required=True)
    p = commands.add_parser("reparse"); p.add_argument("--stages", nargs="+")
    p = commands.add_parser("review"); p.add_argument("--stage", required=True); p.add_argument("--decision", required=True)
    p = commands.add_parser("seal"); p.add_argument("--name", required=True); p.add_argument("--stages", nargs="+", required=True)
    p.add_argument("--approve-publication", action="store_true"); p.add_argument("--purpose", choices=["research", "current-law", "synthetic"], default="research")
    p.add_argument("--cached-tokenizer", action="store_true"); p.add_argument("--max-tokens", type=int, default=512)
    p = commands.add_parser("export"); p.add_argument("--release", required=True); p.add_argument("--destination", required=True)
    commands.add_parser("smoke")
    p = commands.add_parser("rehearse-migration"); p.add_argument("--database", required=True); p.add_argument("--destination", required=True)

    p = commands.add_parser("packets"); p.add_argument("--stages", nargs="+")
    p = commands.add_parser("review-list")
    p = commands.add_parser("review-show"); p.add_argument("--stage", required=True)
    p = commands.add_parser("review-eligibility"); p.add_argument("--stages", nargs="+")
    p = commands.add_parser("review-decide")
    p.add_argument("--stage", required=True); p.add_argument("--category", required=True, choices=service.CATEGORIES)
    p.add_argument("--decision-file", required=True)
    p = commands.add_parser("review-reject")
    p.add_argument("--stage", required=True); p.add_argument("--category", required=True, choices=service.CATEGORIES)
    p.add_argument("--decision-file", required=True)
    p = commands.add_parser("review-approve-extraction")
    p.add_argument("--stage", required=True); p.add_argument("--decision-file", required=True)
    p = commands.add_parser("review-evidence")
    p.add_argument("--stage", required=True); p.add_argument("--category", required=True, choices=service.CATEGORIES)
    p.add_argument("--decision-file", required=True)
    p = commands.add_parser("r0-draft"); p.add_argument("--stages", nargs="+")

    args = parser.parse_args()
    try:
        if args.command == "init": result = {"workspace": str(service.initialize(args.workspace))}
        elif args.command == "ingest": result = service.ingest(args.workspace, args.manifest)
        elif args.command == "reparse": result = {"results": service.reparse(args.workspace, args.stages)}
        elif args.command == "review":
            result = service.review(args.workspace, args.stage, _load(args.decision))
        elif args.command == "seal":
            from preprocess.legal_chunking import CachedTokenizerBudget
            budget = CachedTokenizerBudget() if args.cached_tokenizer else None
            result = service.seal(args.workspace, args.name, args.stages, approve_publication=args.approve_publication,
                purpose=args.purpose, budget=budget, max_tokens=args.max_tokens)
        elif args.command == "export":
            result = service.export(args.workspace, args.release, args.destination).model_dump(mode="json")
        elif args.command == "rehearse-migration":
            from preprocess.migration_safety import rehearsal
            result = rehearsal(args.database, args.destination)
        elif args.command == "packets":
            from preprocess.review_packets import generate
            result = generate(args.workspace, args.stages)
        elif args.command == "review-list":
            from law_crawler.quality import inventory
            quality = inventory(args.workspace)
            report = service.eligibility(args.workspace)
            readiness = {row["stage_id"]: row for row in report["rows"]}
            result = dict(stages=quality["stages"], fragments=quality["fragments"],
                release_candidates=quality["release_candidates"], rows=[
                    dict(stage_id=row["stage_id"], official_identifier=row["official_identifier"],
                        status=row["quality"]["state"], fragment=row["fragment"],
                        release_candidate=row["release_candidate"],
                        approvals={name: bool(value and value["decision"] == "approved")
                                   for name, value in readiness[row["stage_id"]]["categories"].items()},
                        missing=[service.CATEGORY_TITLES[name] for name in service.CATEGORIES
                                 if not (readiness[row["stage_id"]]["categories"][name] or {}).get("decision")],
                        research_seal_ready=readiness[row["stage_id"]]["research_seal_ready"])
                    for row in quality["rows"]])
        elif args.command == "review-show":
            from preprocess.offline_ingestion import require_workspace
            result = _packet_summary(require_workspace(args.workspace), args.stage)
        elif args.command == "review-eligibility":
            result = service.eligibility(args.workspace, args.stages)
        elif args.command == "review-decide":
            payload = _load(args.decision_file)
            payload["category"] = args.category
            result = service.decide_category(args.workspace, args.stage, payload)
        elif args.command == "review-reject":
            payload = _load(args.decision_file)
            payload.update(category=args.category, decision="rejected")
            result = service.decide_category(args.workspace, args.stage, payload)
        elif args.command == "review-approve-extraction":
            payload = _load(args.decision_file)
            payload.update(category="B_extraction_quality", decision="approved")
            result = service.decide_category(args.workspace, args.stage, payload)
        elif args.command == "review-evidence":
            payload = _load(args.decision_file)
            payload.update(category=args.category, decision="pending")
            result = service.decide_category(args.workspace, args.stage, payload, kind="evidence")
        elif args.command == "r0-draft":
            from preprocess.r0_release import write
            result = write(args.workspace, args.stages)
        else:
            from preprocess.synthetic_ingestion import smoke
            result = smoke(args.workspace)
        print(canonical(result))
        if isinstance(result, dict) and result.get("status") == "quarantined": raise SystemExit(2)
    except (ValueError, OSError):
        # Detailed safe diagnostics are in the local stage/report; don't echo untrusted input values.
        parser.exit(1, "Operation refused. Inspect workspace/reports and docs/offline-ingestion.md; verify metadata, review approval and fresh output paths.\n")


if __name__ == "__main__":
    main()
