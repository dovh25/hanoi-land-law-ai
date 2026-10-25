# Colab Web exchange (generated contents are ignored)

| Path | Operator action |
|---|---|
| `upload-to-colab/embedding-input.zip` | Upload this **one file** to the notebook in Colab Web. |
| `download-from-colab/embedding-output.zip` | Save the notebook's **one downloaded result** here. Preserve older runs outside this standard filename first. |
| `extracted/` | Retained original inputs, validated extraction, and `indexed=false` imports; do not edit. |
| `reports/` | Read `pack-colab.json`, `verify-colab.json`, `receive-colab.json`. |

Notebook to upload: **`notebooks/embedding_batch.ipynb`**.
Browser: https://colab.research.google.com → **File → Upload notebook**.
No VS Code extension, Drive mount, remote kernel, tunnel, or server is required.

```bash
# All commands from repository root, using the Python 3.12 uv environment:
uv run --frozen python -m preprocess.offline_cli --workspace data/phase-c-smoke smoke
uv run --frozen python -m batch.cli pack-colab --input data/phase-c-smoke/embedding-input
# Manually run Colab Web, download embedding-output.zip to download-from-colab/:
uv run --frozen python -m batch.cli verify-colab
uv run --frozen python -m batch.cli receive-colab --workspace data/phase-c-smoke
```

The smoke input is **four synthetic documents**, unknown validity, CPU hash vectors
only—not official law or neural inference. For real data use a reviewed sealed
ingestion release instead. Never upload `.env`, a database, case histories or keys.
Packing refuses to overwrite a different standard input ZIP. Partial output exits
with status 2 and is retained as checkpoints, never imported. Rejected output exits
nonzero with an actionable report. No exchange command indexes Qdrant.

See [`docs/colab-web.md`](../docs/colab-web.md) and
[`docs/offline-ingestion.md`](../docs/offline-ingestion.md). Generated ZIPs, vectors,
extractions and reports are intentionally not versioned; this README/placeholders are.
