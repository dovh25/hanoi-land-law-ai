# Optional retrieval benchmark tooling

This retained package evaluates neural/Qdrant retrieval against separately
provided datasets, including the Zalo AI Legal Text Retrieval format. It is not
the public MVP evaluation and its examples do not establish Hanoi legal QA
accuracy. Use [MVP evaluation](../docs/evaluation.md) for the bundled BM25 corpus.

| Modules | Purpose |
|---|---|
| `dataset.py`, `metrics.py`, `evaluator.py`, `results.py` | Dataset loading, IR metrics and reports |
| `embeddings/`, `retriever.py`, `pipeline_adapter.py` | Optional model and Qdrant adapters |
| `ingest.py`, `run_eval.py` | Operator entry points for indexing/evaluation |
| `deepeval*.py`, `run_deepeval.py` | Retained judge integration; live judges deliberately blocked |

Use the root Python 3.12 frozen environment and optional extras only after their
prerequisites have been reviewed. Model weights, benchmark corpora and indexes are
not bundled. Do not expect an absent Kaggle notebook or downloaded embeddings to
be part of setup. The [Colab workflow](../docs/colab-web.md) is a separate,
controlled batch handoff, not an automatic benchmark installer.

Configuration is in `config.py`; inspect CLI arguments before running. Network
services, model downloads, provider calls and destructive collection recreation
require separate approval. Existing collections require the exact two-part
destructive confirmation enforced by `backend/core/index_safety.py`. Do not
bypass the shared LLM budget provider or run live judges to reproduce offline
tests. Preserve existing evaluation evidence rather than overwriting it.
