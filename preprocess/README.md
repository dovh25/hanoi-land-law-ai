# Legal document preprocessing

The public MVP reads a committed JSONL artifact; preprocessing is not a runtime
prerequisite. See the [corpus guide](../docs/corpus.md) for its exact sources,
metadata, chunk budget and rebuild requirements.

| Modules | Purpose |
|---|---|
| `legal_parser.py`, `legal_chunking.py` | Structure extraction, source spans and deterministic chunking |
| `offline_ingestion.py`, `offline_cli.py` | Local-file staging, review, seal/export and operator CLI |
| `review_packets.py`, `r0_release.py` | Explicit review packets and research-release preparation |
| `migration_safety.py` | Guarded database migration checks |
| `synthetic_ingestion.py` | Offline synthetic validation workflow |
| `chunker.py`, `chunk_pipeline.py`, `ingest_data*.py` | Retained JSON/neural ingestion workflows; optional model dependencies |

Use Python 3.12 and root `pyproject.toml`/`uv.lock`; `requirements.txt` is only a
pointer. Read [offline ingestion](../docs/offline-ingestion.md) and
[review gates](../docs/corpus-review-runbook.md) before processing real sources.
A safe CLI inspection from repository root is:

```bash
uv run --frozen python -m preprocess.offline_cli --help
```

Legacy neural chunking needs optional extras and reviewed local/cached model
assets. Installing extras does not authorize downloads or remote model code.
Indexing an existing Qdrant collection is guarded by both `--recreate` and
`--confirm-collection DELETE:<exact-name>`; do not exercise it against real data
during offline setup. Preserve source artifacts, review decisions and hashes.
