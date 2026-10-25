"""Local commands; no command connects to Qdrant or calls an LLM."""
import argparse
import zipfile
from pathlib import Path

from batch.files import validate_output
from batch.transfer import bundle_code, pack_transfer, unpack_transfer
from batch.smoke import smoke


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("smoke"); p.add_argument("--workspace", required=True)
    p = commands.add_parser("bundle-code"); p.add_argument("--archive", required=True)
    p = commands.add_parser("pack"); p.add_argument("--directory", required=True); p.add_argument("--archive", required=True); p.add_argument("--kind", choices=["input", "output"], required=True)
    p = commands.add_parser("unpack"); p.add_argument("--archive", required=True); p.add_argument("--destination", required=True); p.add_argument("--kind", choices=["input", "output"], required=True)
    p = commands.add_parser("validate"); p.add_argument("--input", required=True); p.add_argument("--output", required=True)
    p = commands.add_parser("export"); p.add_argument("--release-id", required=True); p.add_argument("--destination", required=True)
    p = commands.add_parser("import"); p.add_argument("--input", required=True); p.add_argument("--output", required=True); p.add_argument("--destination", required=True)
    p = commands.add_parser("pack-colab"); p.add_argument("--input", required=True); p.add_argument("--exchange", default="colab-exchange")
    for command in ("receive-colab", "verify-colab"):
        p = commands.add_parser(command); p.add_argument("--exchange", default="colab-exchange"); p.add_argument("--workspace")
    args = parser.parse_args()
    if args.command == "smoke":
        smoke(args.workspace)
    elif args.command == "bundle-code":
        bundle_code(args.archive)
    elif args.command == "pack":
        pack_transfer(args.directory, args.archive, args.kind)
    elif args.command == "unpack":
        unpack_transfer(args.archive, args.destination, args.kind)
    elif args.command == "validate":
        validate_output(args.input, args.output)
    elif args.command == "pack-colab":
        from batch.colab import pack_colab
        from batch.contracts import canonical
        try:
            print(canonical(pack_colab(args.input, args.exchange)))
        except (ValueError, OSError, zipfile.BadZipFile):
            from batch.archive import safe_root
            from batch.files import atomic_bytes
            reports = safe_root(Path(args.exchange) / "reports"); reports.mkdir(parents=True, exist_ok=True)
            result = dict(status="rejected", indexed=False, action="Validate source export; preserve a previous input ZIP before packing a different batch. See docs/colab-web.md")
            atomic_bytes(reports / "pack-colab.json", (canonical(result) + "\n").encode())
            parser.exit(1, result["action"] + "\n")
    elif args.command in {"receive-colab", "verify-colab"}:
        from batch.colab import receive_colab
        from batch.contracts import canonical
        try:
            result = receive_colab(args.exchange, workspace=args.workspace, verify_only=args.command == "verify-colab")
        except ValueError:
            parser.exit(1, "Exchange rejected. Inspect colab-exchange/reports (or --exchange/reports), restore the matching ZIP, and follow docs/colab-web.md.\n")
        print(canonical(result))
        if result["status"] == "partial": raise SystemExit(2)
    else:
        # Local-only commands explicitly enter application settings; worker/notebook never do.
        from backend.core.config import get_settings
        from backend.core.database import create_engine_only
        from sqlalchemy import text
        from sqlalchemy.orm import sessionmaker
        from batch.local import export_release, import_output
        engine = create_engine_only(get_settings().DATABASE_URL)
        try:
            with engine.connect() as connection:
                if connection.scalar(text("SELECT version_num FROM alembic_version")) != "0002_legal_domain":
                    raise ValueError("Database migration is required; run an explicitly approved backup/rehearsal before upgrading, or use the isolated offline workspace")
            factory = sessionmaker(bind=engine, expire_on_commit=False)
            with factory.begin() as session:
                if args.command == "export":
                    export_release(session, args.release_id, args.destination)
                else:
                    import_output(session, args.input, args.output, args.destination)
        finally:
            engine.dispose()
    print("Validated offline batch operation completed; no indexing or LLM calls.")


if __name__ == "__main__":
    main()
