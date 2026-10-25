<div align="center">

# Hanoi Land Law AI — Vietnamese Legal Expert Assistant

> **Current status: Phase D source discovery and policy verification.** Use
> [docs/environment-setup.md](docs/environment-setup.md) for the authoritative setup,
> root `.env` creation, offline checks, and live-use controls. Run
> `python3 scripts/setup_env.py` from root to create your ignored local `.env`.
> Gemini and model downloads are disabled by default. The historical ViLeXa feature
> descriptions and benchmark results below do not establish Hanoi legal QA readiness.
> Phase D discovered 18 official metadata candidates and acquired **0** full-text legal
> instruments: attachment hosts returned robots HTTP 403 and `vbpl.vn` document access is
> ambiguous. No candidate is reviewed, valid, sealed, or indexed.
>
> **MVP demo (implemented, not deployed or live-validated):** an anonymous demo using a
> bundled 2-document / 90-chunk corpus, deterministic Vietnamese BM25, a one-call Gemini
> path, and validated citations is documented in [docs/mvp-demo.md](docs/mvp-demo.md).
> It is not current law, every chunk is `validity_status=unknown`, and live Gemini plus
> public deployment remain disabled pending explicit approval.
>
> New: [legal data model](docs/legal-data-model.md),
> [offline ingestion](docs/offline-ingestion.md), [corpus review](docs/corpus-review.md),
> [corpus sources](docs/corpus-sources.md),
> [corpus acquisition](docs/corpus-acquisition.md),
> [corpus inventory](docs/corpus-inventory.md),
> [corpus quality report](docs/corpus-quality-report.md),
> [Phase D validation](docs/phase-d-validation.md),
> [Phase E readiness](docs/next-phase-readiness.md), and
> [Colab Web workflow](docs/colab-web.md). No real legal corpus or GPU run is supplied.

**An Agentic RAG system for Vietnamese legal documents, powered by LangGraph, Qdrant, and Gemini.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.127+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-darkgreen?style=for-the-badge)](https://langchain-ai.github.io/langgraph/)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.7+-FF6B35?style=for-the-badge&logo=qdrant&logoColor=white)](https://qdrant.tech)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

</div>

---

## Overview

Vietnamese legal documents are complex, hierarchical, and notoriously difficult to navigate. Citizens and legal professionals must sift through thousands of Laws (Luật), Decrees (Nghị định), Circulars (Thông tư), and Decisions (Quyết định) to find relevant provisions — a process that can take hours.

**Hanoi Land Law AI** solves this by combining modern Retrieval-Augmented Generation with an agentic pipeline that thinks before it answers. Instead of blindly retrieving and generating, Hanoi Land Law AI:

1. **Classifies** whether a query actually needs legal document retrieval
2. **Retrieves** documents using hybrid dense + sparse vector search
3. **Grades** each document for relevance using the LLM itself
4. **Rewrites** the query up to 3 times if no relevant documents are found
5. **Generates** accurate, citation-backed responses in Vietnamese

The result is a system that achieved **77.3% Hit Rate@1** and **95.0% Recall@10** on the Zalo AI Legal Retrieval benchmark (150 queries), with **NDCG@10 of 0.867** and **MRR of 0.842**.

---

## Screenshots

Live product UI — captured from the running Hanoi Land Law AI application.

### Chat Interface

<p align="center">
  <img src="docs/screenshots/chat.png" alt="Hanoi Land Law AI Chat Interface" width="90%" />
</p>

### Document Lookup

<p align="center">
  <img src="docs/screenshots/lookup.png" alt="Hanoi Land Law AI Document Lookup" width="90%" />
</p>

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Agentic RAG Pipeline** | Multi-step agentic pipeline with query routing, document grading, and adaptive retry |
| **Hybrid Search** | Dense + Sparse vector retrieval via Qdrant's native fusion — combining semantic similarity with lexical matching |
| **Cross-Encoder Reranker** | `Alibaba-NLP/gte-multilingual-reranker-base` for precision reranking (optional, improves precision at k=10) |
| **Vietnamese Embeddings** | `AITeamVN/Vietnamese_Embedding_v2` — 1024-dim BGE-M3 fine-tuned for Vietnamese |
| **Hierarchical Chunking** | Part → Chapter → Section → Article structure-aware document splitting |
| **Legal Document Crawler** | Automated scraping from the Vietnamese National Legal Information Portal (vbpl.vn) |
| **JWT Authentication** | Secure user registration, login, and session management |
| **Persistent Chat History** | SQLite-backed session storage with full message and source tracking |
| **Multi-Pipeline Support** | GTE, Vietnamese Embedding, BGE-M3, and Agentic pipelines — swappable at config |
| **GPU Acceleration** | NVIDIA CUDA support with torch.compile, TF32, and FP16 optimizations |
| **Docker Deployment** | 3-service architecture (backend, Qdrant, frontend) with GPU passthrough |
| **DeepEval Integration** | Automated RAG evaluation with AnswerRelevancy and Faithfulness metrics |

---

## Architecture

### System Architecture

<p align="center">
  <img src="docs/screenshots/architecture.png" alt="Hanoi Land Law AI System Architecture" width="100%" />
</p>

<p align="center">
  <em>Generated with <a href="https://github.com/tt-a1i/archify">Archify</a> — open the live <a href="docs/hanoi-land-law-ai-architecture.html">interactive diagram</a> for focus modes, zoom, and guided story views.</em>
</p>

### Agentic RAG Pipeline

The core innovation is a multi-step agentic LangGraph state machine that routes, retrieves, evaluates, and adapts:

```mermaid
flowchart TD
    Q[User Query] --> R{route_query}
    R -->|needs retrieval| RET[retrieve]
    R -->|no retrieval| GD[generate_direct]
    RET --> GRADE{grade_documents}
    GRADE -->|relevant| GEN[generate_with_context]
    GRADE -->|no relevant, < max| RW[rewrite_query]
    RW --> RET
    GRADE -->|no relevant, max reached| HND[handle_no_docs]
    GD --> END[Final Response]
    GEN --> END
    HND --> END
```

### State Flow

| State Field | Type | Description |
|-------------|------|-------------|
| `query` | `str` | Original user query (immutable) |
| `current_query` | `str` | Current query (may be rewritten) |
| `history` | `List[BaseMessage]` | Chat history for multi-turn |
| `documents` | `List[Document]` | Retrieved documents from Qdrant |
| `relevant_documents` | `List[Document]` | Filtered by LLM grading |
| `rewrite_count` | `int` | Current retry attempt (max 3) |
| `needs_retrieval` | `bool` | Route decision result |
| `answer` | `str` | Generated response |
| `sources` | `List[Dict]` | Document metadata for citations |

---

## Tech Stack

### Backend

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Framework | FastAPI | 0.127+ | Async REST API |
| Language | Python | 3.12 | Core runtime |
| Orchestration | LangGraph | 0.2+ | Agentic RAG pipeline |
| LLM | Google Gemini | `gemini-2.5-flash-lite` | Query routing, grading, generation |
| Vector DB | Qdrant | 1.7+ | Hybrid dense + sparse retrieval |
| Embeddings | AITeamVN/Vietnamese_Embedding_v2 | 1024-dim | BGE-M3 fine-tuned for Vietnamese |
| Reranker | Alibaba-NLP/gte-multilingual-reranker-base | CrossEncoder | Precision reranking |
| Auth DB | SQLite + SQLAlchemy | - | User accounts, sessions, messages |
| Security | JWT (python-jose) + bcrypt | - | Token-based authentication |

### Frontend

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Framework | React | 19.2+ | UI framework |
| Language | TypeScript | 5.9+ | Type-safe development |
| Bundler | Vite (rolldown) | 7.2+ | Fast build tooling |
| Styling | Tailwind CSS | 4.1+ | Utility-first CSS |
| Routing | React Router | 7.11+ | Client-side routing |
| Markdown | react-markdown | 10.1+ | Chat message rendering |

### Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| Containerization | Docker + Docker Compose | Multi-service orchestration |
| GPU | NVIDIA CUDA | Embedding + reranker acceleration |
| Crawler | requests + BeautifulSoup | Legal document scraping from vbpl.vn |
| Evaluation | DeepEval + Custom IR Metrics | RAG quality assessment |

---

## Project Structure

```
hanoi-land-law-ai/
├── backend/                         # FastAPI + LangGraph + Qdrant
│   ├── api/
│   │   └── v1/                     # REST API endpoints
│   │       ├── auth.py             # Register, login, JWT
│   │       ├── chat.py             # RAG chat with history
│   │       ├── sessions.py         # Session CRUD
│   │       └── lookup.py           # Document browsing
│   ├── core/
│   │   ├── config.py               # Pydantic settings (env-based)
│   │   ├── database.py             # SQLAlchemy engine & session
│   │   ├── security.py             # JWT token creation/validation
│   │   └── logging.py              # Structured logging setup
│   ├── db/models/                  # SQLAlchemy ORM models
│   │   ├── user.py                 # User accounts
│   │   ├── chat_session.py         # Chat sessions
│   │   ├── message.py              # Messages + sources
│   │   └── message_source.py       # Citation metadata
│   ├── models/                     # Pydantic request/response schemas
│   │   ├── auth.py                 # UserCreate, TokenResponse
│   │   ├── chat.py                 # ChatRequest, ChatResponse
│   │   ├── session.py              # SessionCreate, MessageResponse
│   │   └── lookup.py               # DocumentResponse
│   └── services/
│       ├── chat_service.py         # Chat orchestration
│       ├── auth_service.py         # User management
│       ├── session_service.py      # Session persistence
│       ├── lookup_service.py       # Document search & retrieval
│       ├── adapters.py             # Embedding adapters (GTE, Vietnamese, BGE-M3)
│       ├── pipelines/              # RAG pipeline implementations
│       │   ├── base.py             # Abstract RAGPipeline interface
│       │   ├── agentic_rag_pipeline.py  # LangGraph agentic workflow
│       │   ├── gte_pipeline.py     # Alibaba GTE pipeline
│       │   ├── vietnamese_embedding_pipeline.py  # Vietnamese BGE-M3
│       │   └── bge_m3_pipeline.py  # BAAI BGE-M3 pipeline
│       └── rerankers/
│           ├── base.py             # Abstract BaseReranker interface
│           └── cross_encoder.py    # CrossEncoder reranker with GPU optimization
│   └── main.py                     # FastAPI app initialization
│
├── frontend/                        # React + TypeScript + Vite
│   └── src/
│       ├── components/             # Reusable UI components
│       ├── contexts/               # React contexts (auth)
│       ├── hooks/                  # Custom React hooks
│       ├── pages/                  # Page components
│       ├── services/               # API client functions
│       └── types/                  # TypeScript type definitions
│
├── benchmarks/                      # Evaluation framework
│   ├── run_eval.py                 # Retrieval benchmark CLI
│   ├── run_deepeval.py             # DeepEval RAG evaluation
│   ├── metrics.py                  # IR metrics (P, R, F1, NDCG, MRR, MAP)
│   ├── evaluator.py                # Evaluation orchestrator
│   ├── retriever.py                # Qdrant retriever wrapper
│   ├── deepeval_evaluator.py       # DeepEval integration
│   ├── deepeval_dataset.py         # Dataset preparation for DeepEval
│   ├── embeddings/                 # Embedding providers
│   │   ├── base.py                 # Abstract EmbeddingProvider
│   │   ├── gte.py                  # Alibaba GTE
│   │   ├── vietnamese.py           # Vietnamese Embedding v2
│   │   └── bge_m3.py              # BAAI BGE-M3
│   └── results/                    # Evaluation result JSON files
│
├── preprocess/                      # Data ingestion pipeline
│   ├── chunker.py                  # Hierarchical legal document chunker
│   ├── chunk_pipeline.py           # End-to-end chunking pipeline
│   ├── ingest_data.py              # Base ingestion script
│   ├── ingest_data_alibaba.py      # GTE embedding ingestion
│   └── ingest_data_vietnamese.py   # Vietnamese embedding ingestion
│
├── law_crawler/                     # Legal document scraper
│   ├── main.py                     # Crawler entry point
│   ├── config.py                   # Crawler configuration
│   └── vbpl_documents/             # Crawled JSON documents
│
├── data/                            # Pre-computed embeddings
│   ├── processed_chunksize_512_vietnamese/
│   ├── processed_chunksize_1024_alibaba/
│   └── processed_chunksize_1024/
│
├── qdrant_data/                     # Qdrant persistent storage
├── docker-compose.yaml              # 3-service Docker orchestration
├── pyproject.toml                   # Python project configuration
├── uv.lock                          # uv dependency lockfile
└── LICENSE                          # MIT License
```

---

## Getting Started — Offline Foundation (Phases A/B/C)

Python 3.12 and Node 22.21+/24 are required. From this repository's root:

```bash
python3 scripts/setup_env.py
uv sync --frozen
npm --prefix frontend ci --ignore-scripts --no-audit --no-fund
uv run --frozen pytest -q
npm --prefix frontend test
```

Start the offline API and frontend in separate terminals:

```bash
uv run --frozen uvicorn backend.main:app --host 127.0.0.1 --port 8000
npm --prefix frontend run dev
```

Your ignored root `.env` can be edited locally. New files disable Gemini, leave its
key blank, and generate a JWT secret without printing it. Existing `.env` values
are never overwritten by setup.
No GPU, corpus, Qdrant, or model weights are needed for offline startup/tests.
`/healthz` returns 200; `/readyz` and legal chat return 503 until explicitly enabled
and initialized. No live legal QA readiness is claimed.

See [environment setup](docs/environment-setup.md) for all settings, Compose behavior,
budget enforcement, and optional runtime limitations. Do not crawl, index, download
weights, or enable Gemini as part of ordinary setup.

Phase B additionally provides guarded Alembic migrations and a weight-free CPU batch
smoke test. Back up an existing database before its next startup/upgrade; follow
[the model guide](docs/legal-data-model.md#migrations-and-existing-application-data).

```bash
uv run --frozen python -m batch.cli smoke --workspace data/phase-b-smoke
```

For the Phase C synthetic end-to-end ingestion and browser-only Colab handoff:

```bash
uv run --frozen python -m preprocess.offline_cli --workspace data/phase-c-smoke smoke
uv run --frozen python -m batch.cli pack-colab --input data/phase-c-smoke/embedding-input
```

Upload `notebooks/embedding_batch.ipynb` in **Colab Web → File → Upload notebook**.
See [the Colab Web runbook](docs/colab-web.md) for the one-ZIP exchange and local
validation/import commands. Real GPU execution remains untested.

---

## API Documentation

### Authentication

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/auth/register` | Create new user account | No |
| `POST` | `/api/v1/auth/login` | Login, returns JWT token | No |
| `GET` | `/api/v1/auth/me` | Get current user info | Yes |

### Chat

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/chat` | Send message, get RAG response with sources | Yes |

### Sessions

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/sessions` | Create new chat session | Yes |
| `GET` | `/api/v1/sessions` | List all sessions | Yes |
| `GET` | `/api/v1/sessions/{id}` | Get session with messages | Yes |
| `PATCH` | `/api/v1/sessions/{id}` | Update session title | Yes |
| `DELETE` | `/api/v1/sessions/{id}` | Delete session and messages | Yes |

### Documents

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/documents` | List all documents (paginated) | No |
| `GET` | `/api/v1/documents/search` | Search documents by query | No |
| `GET` | `/api/v1/documents/types` | Get all document types | No |
| `GET` | `/api/v1/documents/{id}` | Get document with full content | No |
| `GET` | `/api/v1/documents/{id}/articles` | Get parsed articles | No |
| `POST` | `/api/v1/documents/search-by-content` | Find document by content match | No |

### Example: Chat Request

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{
    "message": "Thời gian thử việc tối đa là bao lâu?",
    "session_id": "abc123"
  }'
```

### Example: Chat Response

```json
{
  "reply": "Theo quy định tại Điều 25 Bộ luật Lao động 2019, thời gian thử việc tối đa là 60 ngày đối với công việc có chức danh nghề cần trình độ chuyên môn, kỹ thuật cao...",
  "sources": [
    {
      "document_id": "96172",
      "document_type": "Bộ luật",
      "document_title": "Bộ luật Lao động 2019",
      "phan": null,
      "chuong": "Chương III - Hợp đồng lao động",
      "muc": "Mục 2 - Thử việc",
      "dieu": "Điều 25"
    }
  ],
  "session_id": "abc123"
}
```

---

## RAG Pipeline Deep Dive

### Embedding Models

| Model | Dims | Type | Vietnamese Optimization | Use Case |
|-------|------|------|------------------------|----------|
| `AITeamVN/Vietnamese_Embedding_v2` | 1024 | Dense + Sparse | Fine-tuned BGE-M3 | **Production (default)** |
| `BAAI/bge-m3` | 1024 | Dense + Sparse | Multilingual (100+ langs) | General multilingual |
| `Alibaba-NLP/gte-multilingual-base` | 768 | Dense + Sparse | Multilingual | Benchmark comparison |

### Retrieval Modes

| Mode | Description | Best For |
|------|-------------|----------|
| `hybrid` | Dense + Sparse via RRF | Best overall quality |
| `dense` | Semantic similarity only | Fast, good recall |
| `sparse` | Keyword/BM25-style matching | Exact term matching |

### Cross-Encoder Reranker

The reranker uses `Alibaba-NLP/gte-multilingual-reranker-base` with these optimizations:

- **torch.compile()** — ~2x inference speedup on PyTorch 2.0+
- **FP16 inference** — Halves memory usage on GPU
- **TF32 matmul** — Faster computation on Ampere+ GPUs
- **CUDA warmup** — Pre-compiles kernels on startup
- **argpartition** — O(n) top-k selection vs O(n log n) sort

Performance on GTX 1650 (4GB VRAM):

| RETRIEVAL_K | Reranking Time | Total Latency |
|-------------|----------------|---------------|
| 5 | ~0.9s | ~1.2s |
| 10 | ~1.8s | ~2.1s |
| 20 | ~3.7s | ~4.0s |

### Hierarchical Document Chunking

Vietnamese legal documents follow a strict hierarchy:

```
Phần (Part)
└── Chương (Chapter)
    └── Mục (Section)
        └── Điều (Article)
            └── Khoản (Clause)
```

The `VietLegalChunker` parses this structure using regex patterns and creates chunks at the Article (Điều) level with rich metadata:

```python
{
    "document_id": "96172",
    "document_type": "Bộ luật",
    "document_title": "Bộ luật Lao động 2019",
    "phan": "Phần thứ nhất",
    "chuong": "Chương III - Hợp đồng lao động",
    "muc": "Mục 2 - Thử việc",
    "dieu": "Điều 25",
    "id": "uuid-string"
}
```

Large articles (>512 tokens) are split using `RecursiveTextSplitter` with the model's tokenizer.

---

## Benchmark Results

### Zalo AI Legal Retrieval Benchmark

Evaluated on 150 queries from the Zalo AI Legal Text Retrieval dataset.

#### Retrieval Metrics by Pipeline

| Pipeline | Hit Rate@1 | Recall@5 | Recall@10 | NDCG@10 | MRR | MAP |
|----------|-----------|----------|-----------|---------|-----|-----|
| **Vietnamese Dense** | **0.773** | **0.943** | **0.950** | **0.867** | **0.842** | **0.840** |
| Vietnamese Hybrid | 0.440 | 0.903 | 0.937 | 0.721 | 0.650 | 0.649 |
| Vietnamese Dense + Reranker (k=20) | 0.500 | 0.870 | 0.917 | 0.718 | 0.653 | 0.652 |
| GTE Hybrid | 0.527 | 0.793 | 0.880 | 0.700 | 0.647 | 0.646 |
| GTE Dense | — | — | — | — | — | — |

#### Best Configuration: Vietnamese Dense

```
Retrieval Mode:   Dense
Embedding Model:  AITeamVN/Vietnamese_Embedding_v2 (1024-dim)
Vector Size:      1024
Reranker:         None (fast inference)

Precision@1:   0.773    Recall@1:     0.773
Precision@5:   0.189    Recall@5:     0.943
Precision@10:  0.095    Recall@10:    0.950
Precision@20:  0.048    Recall@20:    0.957
Precision@50:  0.020    Recall@50:    0.977
Precision@100: 0.010    Recall@100:   0.977

NDCG@1:  0.773    NDCG@5:  0.865
NDCG@10: 0.867    NDCG@20: 0.869

MRR:  0.842    MAP:  0.840
```

#### Key Insights

1. **Vietnamese-optimized embeddings outperform multilingual models** — `AITeamVN/Vietnamese_Embedding_v2` achieves 77.3% Hit Rate@1 vs 52.7% for GTE
2. **Dense retrieval is sufficient** — Adding hybrid search (sparse) does not improve Hit Rate@1 for this Vietnamese legal domain
3. **Reranking does not improve top-1 accuracy** — The cross-encoder reranker adds latency without meaningful gains at k=1
4. **Near-perfect recall at k=10** — 95% of relevant documents are found in the top 10 results

### DeepEval RAG Evaluation

The system includes automated evaluation using DeepEval with these metrics:

| Metric | Description | What It Measures |
|--------|-------------|------------------|
| **Answer Relevancy** | How relevant the answer is to the query | Generation quality |
| **Faithfulness** | How faithful the answer is to the retrieved context | Groundedness / hallucination |

```bash
# Run DeepEval evaluation
python benchmarks/run_deepeval.py
```

---

## Vietnamese Legal Document Processing

### Crawler

The `law_crawler/` module scrapes legal documents from the [Vietnamese National Legal Information Portal](https://vbpl.vn):

- **Concurrency:** Configurable thread pool (default: 10 workers)
- **Retry strategy:** Exponential backoff with 3 retries
- **Rate limiting:** Configurable timeout (default: 30s)
- **Output format:** JSON with `Id`, `Title`, and `Content` fields

### Document Types Crawled

| Type | Vietnamese | Count (approx) |
|------|------------|-----------------|
| Luật | Laws | 400+ |
| Bộ luật | Codes | 10+ |
| Nghị định | Decrees | 1500+ |
| Thông tư | Circulars | 800+ |
| Quyết định | Decisions | 500+ |
| Nghị quyết | Resolutions | 200+ |
| Pháp lệnh | Ordinances | 50+ |

### Preprocessing Pipeline

```mermaid
flowchart TD
    JSON[Raw JSON from vbpl.vn] --> CH[VietLegalChunker<br/>Parse hierarchy, extract articles,<br/>split >512 token articles]
    CH --> EMB[Embedding Engine<br/>BGE-M3: 1024-dim dense + sparse]
    EMB --> QD[Qdrant Ingestion<br/>Hybrid collection config,<br/>batch upload with progress tracking]
```

---

## Environment Variables

See [`.env.example`](.env.example) and the
[settings reference](docs/environment-setup.md#configuration-and-consent-controls).
Use one root `.env`; never expose backend credentials through `VITE_*`.

---

## Docker Configuration

[`docker-compose.yaml`](docker-compose.yaml) is CPU-first, injects backend settings
explicitly, binds host ports to loopback, and puts Qdrant behind an optional profile
without a host port. The default backend image is the offline foundation, not an
ML-enabled legal QA deployment. See [setup details](docs/environment-setup.md).

---

## Troubleshooting

Offline `/readyz` and chat returning 503 is expected, not a reason to enable Gemini
or download models. Check the [environment guide](docs/environment-setup.md) first.

---

## Known Limitations

- The cross-encoder reranker showed mixed results on this dataset — Hit Rate@1 dropped from 77.3% to 50.0% with reranking enabled. This suggests the dense retrieval alone is already highly effective for this Vietnamese legal corpus.
- Hybrid search (dense+sparse) underperformed pure dense search (77.3% vs 82.7% Hit Rate@1), likely because the sparse weights from BGE-M3 add noise for highly specialized Vietnamese legal terminology.
- The pipeline uses `gemini-2.5-flash-lite` (the smallest Gemini model) to keep API costs low. A larger model would likely improve answer quality.
- Phase A uses an explicit CORS allowlist; public deployment hardening remains out of scope.

---

## Contributing

Contributions are welcome. Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow existing code style (ruff for Python, ESLint for TypeScript)
- Add tests for new functionality
- Update documentation for API changes
- Run `pytest` and `npm run lint` before committing

---

## License

This project is licensed under the MIT License (No Attribution Required) — see [LICENSE](LICENSE) for details.

Copyright (c) 2025 Tran Tuan Kiet, Nguyen My Thong

---

## Contact

**Nguyen My Thong**
- Email: mythonggg@gmail.com
- GitHub: [iknizzz1807](https://github.com/iknizzz1807)

---

<div align="center">

**Built with passion for Vietnamese legal accessibility**

</div>
