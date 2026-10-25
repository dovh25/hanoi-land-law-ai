# Google Colab Web operator runbook

Use **https://colab.research.google.com in a browser**. No Colab VS Code extension,
WSL kernel integration, SSH, tunnel, remote server, persistent worker or paid fallback.
Local FastAPI/SQLite/Qdrant/chat do not depend on Colab. Initial workflow needs no Drive.

## Exact handoff paths

| Item | Path/name |
|---|---|
| Notebook to upload | `notebooks/embedding_batch.ipynb` |
| One local ZIP to upload | `colab-exchange/upload-to-colab/embedding-input.zip` |
| One result ZIP downloaded | `embedding-output.zip` |
| Local destination | `colab-exchange/download-from-colab/embedding-output.zip` |
| Reports | `colab-exchange/reports/` |

## 1. Prepare locally

```bash
uv sync --frozen
uv run --frozen python -m preprocess.offline_cli --workspace data/phase-c-smoke smoke
uv run --frozen python -m batch.cli pack-colab --input data/phase-c-smoke/embedding-input
```

This is a four-document **synthetic CPU** exercise. Copy `sha256` from
`colab-exchange/reports/pack-colab.json`. The one ZIP includes minimal credential-free
compute code, pinned requirements/license, and Phase B JSONL/JSON input. It excludes
backend settings, databases, `.env`, keys, arbitrary repository files and raw source
files. Preserve older standard ZIPs outside the upload folder before packing another
batch; different input/code never silently overwrites them. Keep local retained inputs.

For a real release later, follow [`offline-ingestion.md`](offline-ingestion.md) and
[`corpus-review.md`](corpus-review.md). Explicitly review, seal with the cached exact
tokenizer, export, then pass that export directory to `pack-colab`. Never upload private
case histories. No authoritative sources are supplied or acquired in Phase C.

## 2. Open the notebook in Colab Web

1. Sign in, select **File → Upload notebook**, upload `notebooks/embedding_batch.ipynb`.
2. For approved real inference: **Runtime → Change runtime type → GPU**, save.
   Free GPUs are not guaranteed; no fixed GPU model, memory, quota or session duration.
3. Read the notebook; paste the local ZIP SHA into `EXPECTED_INPUT_SHA256`.
4. Keep `SMOKE_ONLY=True` for the synthetic package. Enable `ALLOW_PACKAGE_INSTALL=True`
   only for the manual package-install cell if required. It installs only NumPy/Pydantic
   for smoke. Python 3.12 is required by the pinned contract; an incompatible runtime
   fails rather than silently resolving a different environment.
5. For real reviewed input only: set `SMOKE_ONLY=False`, and explicitly enable
   `ALLOW_MODEL_DOWNLOADS=True` to authorize the pinned checkpoint download **in Colab**.
   The notebook never downloads weights during local tests. It refuses a smoke/model mismatch.
6. Run upload; choose **only embedding-input.zip**. Before importing code the notebook
   verifies the independently supplied ZIP SHA, exact filename allowlist, checksums,
   regular-file types, duplicates, entry count and expansion size (256 MiB).
7. Install/check exact versions from `notebooks/colab-requirements.txt`. If replacing
   loaded packages, **Runtime → Restart session**, then repeat setup. Smoke has no
   dependency on torch. Real inference validates pinned torch/transformers/ST versions.

The report detects CUDA, GPU model, total/free VRAM, and records actual device/library
versions. No GPU fails clearly unless you explicitly select `ALLOW_CPU_FALLBACK=True`.
There is no automatic checkpoint switch or paid service fallback.

## 3. Run bounded inference and save output

Run the independent synthetic smoke cell, then bounded batch inference. Defaults:
32 records per checkpoint, 4 per neural inference batch. Tokenization/vector memory is
bounded to one shard; the corpus is not loaded into GPU memory. CUDA OOM halves only
inference batch size. At batch size 1, preserve checkpoints and restart/change runtime
or review shorter chunks. Do not change SHARD_SIZE while resuming.

After success **or an interrupted inference cell**, run the output/download cell.
It packages only verified completed shards and downloads exactly **embedding-output.zip**.
It includes:
- Phase B `output.json` only if complete; per-shard ID/hash/model metadata and NPY vectors;
- `exchange.json` with all package checksums, expected counts, release/model bindings;
- `execution-report.json`, `processing-summary.json`, `failed-records.json`.

No corpus text copies, secrets, pickles or raw files are in the result. A failed-record
entry means not completed, not silently skipped. If no shard finished, a zero-progress
partial package still explains what to retry. Invalid/corrupt checkpoints fail validation
instead of being repackaged as trusted progress.

## 4. Save and validate locally

Move the browser download to the exact local destination above; preserve older output
ZIPs before replacing the standard filename. Browser names like `embedding-output (1).zip`
must be deliberately renamed to the standard name for the selected batch.

```bash
uv run --frozen python -m batch.cli verify-colab
uv run --frozen python -m batch.cli receive-colab --workspace data/phase-c-smoke
```

For a real release replace `--workspace` with its isolated ingestion workspace.
`verify-colab` validates compatibility without opening SQLite. `receive-colab` additionally
checks canonical source spans/headings/text hashes and sealed SQLite membership, and
creates an `indexed=false` receipt under `extracted/verified-imports/`. It never indexes
Qdrant or publishes to retrieval. Duplicate identical imports are idempotent.

Inspect `reports/verify-colab.json` / `reports/receive-colab.json`. Corrupt checksums,
unknown revisions, wrong dimensions/dtype, NaN/Infinity, duplicate/missing IDs, wrong
release or unsafe paths are rejected. Generated extracted files are not trusted merely
because they came from Colab. An envelope can verify integrity/declared compatibility,
**not attest that an untrusted third party actually ran the neural model**.

Exit status: 0 complete success; 2 verified **partial** output (never imported);
nonzero rejection otherwise. Keep the matching input archive/retained local manifest.
If the active batch is wrong, run pack-colab for the intended retained input first;
never edit manifests/checksums to force acceptance.

## 5. Resume after disconnection

While the kernel is still alive, run the final download cell to preserve completed
shards. A terminated runtime loses unexported runtime-disk checkpoints; there is no
keepalive workaround. Reopen the notebook, upload the identical input ZIP with the
same SHA, select `RESUME=True` in the optional resume cell, upload the previous
embedding-output.zip. Source/model/ID/checksum checks run before resuming, and completed
shards are not recomputed. A complete archive can also be verified/reused without
loading model weights. Preserve SHARD_SIZE; reduce INFERENCE_BATCH_SIZE after OOM.

No Drive mounting is implemented/required. Optional user-approved durable Drive
checkpointing is a future enhancement, not a hidden dependency.

## Reviewed model contract and validation levels

Checkpoint unchanged: `AITeamVN/Vietnamese_Embedding_v2` at
`18b44161e041bf1d3a333ab5144b5b7b93f914d2`. Phase B's recorded pinned configuration
declares Transformer → CLS Pooling → Normalize, standard XLM-R, 1,024 dimensions.
`batch/embedding.py` checks dimension, XLM-R architecture, CLS-only flags and Normalize
module on actual load; normalization is also explicit. No remote model code. Published
files/module evidence does not support learned-sparse output. Token policy stays 2,048
including specials (card/config length disagreement), rejecting rather than truncating.
See [`model-compatibility-vietnamese-v2.json`](model-compatibility-vietnamese-v2.json).

- **Static:** pinned source/config evidence and implementation reviewed; no new weight
  inspection, no claim of numerical correctness from compilation alone.
- **Synthetic:** deterministic CPU vectors, mocked model/browser transport and archive
  corruption/resume tests; not a model benchmark or a live Colab connection.
- **Real inference:** manual Colab execution still required. GPU report alone is
  declared evidence; retain it with actual run details. Compare the same pinned local
  CPU query encoder against GPU vectors and evaluate retrieval before any index switch.

Old BGEM3-loaded sparse/dense indexes are not assumed equivalent; rebuild into a new
approved index. Local CPU weights/RAM/latency remain a separate operator prerequisite
for real-time chat. Reranker tooling remains optional/independent in `batch/rerank.py`.
Official resource limitations: https://research.google.com/colaboratory/faq.html.
