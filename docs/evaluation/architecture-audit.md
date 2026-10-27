# Implementation / deployment audit — 2026-10-27

## Evaluated path

`backend.main.create_app` constructs FastAPI and owns database/application lifespan.
`/api/v1/demo/chat` uses `MvpRagPipeline`, a straight-line Python workflow:
greeting → lexical retrieval → sufficiency/scope gate → optional one generation →
validation/fallback. **It is not a LangGraph workflow.** React is the client; the
anonymous demo is stateless and separate from authenticated session/chat APIs.
Demo corpus loads at lifespan; legacy RAG stays uninitialized. `/healthz` is
liveness; `/demo/readyz` tests demo+database; `/readyz` additionally requires legacy
chat RAG and is expected to be 503 in this offline configuration.

## Corpus and units

`backend/resources/mvp_demo_corpus.jsonl` and its manifest match the reported
2 instruments / 90 chunks / 77,243 characters. SHA-256:
`ce0df852742ea3144ae5c04bdef27580d88d53752ad6039a4cdd0b091a73508e`.

| Instrument | Stage | Chunks | Articles | Review / validity |
|---|---|---:|---:|---|
| 43/2024/QH15 | `7d6545c4…` | 7 | 5 | technical_validation_only / unknown |
| 88/2024/NĐ-CP | `2c9ed6d6…` | 83 | 32 | technical_validation_only / unknown |

All **90 exact source spans** and both documents' raw/parsed hashes were checked
against preserved local stages and raw files without rebuilding. Full hashes are
in `evaluation/reports/offline-results.json` → `source_artifact_audit` and manifest.
This verifies local artifact consistency, not a legal review or current-law release.
Law 43 amends several laws and is **not** the complete Land Law 31/2024/QH15.
The decree's annex/forms are excluded. Referenced underlying laws and later
amendments are not supplied as complete operative evidence.

The builder uses article subtrees and contiguous ≤1,800-byte-budget chunks with
stable IDs, article locators, raw/parsed hashes, source offsets, URLs, heading
context and stage IDs. Search `Evidence` retains article-level metadata and spans,
not a structured clause/point identity. Clause boundaries may split across chunks.
E1–E6 aliases exist only within a response. Metrics use stable chunk IDs.

## Exact lexical configuration

`backend/services/mvp_corpus.py`:

- NFC and lowercase tokenization, regex Vietnamese/alphanumeric word units;
  both original accented and folded forms are indexed. This is **not** a learned
  Vietnamese word segmenter or an embedding model.
- Fold strips diacritics and maps đ→d. Coverage uses distinct folded content terms,
  stopwords, and token containment; score and gate have different token filtering.
- BM25: k1=1.5, b=.75; IDF `log(1+(N-df+.5)/(df+.5))`.
- Document-number token field ×2; article-heading field ×4 plus source text.
  Additional heading bonus `.8 × (matching-term IDFs + 2.5 × heading-bigram hits)`.
- Sort: descending rounded score, document number, source start. Explicit
  document/article filtering precedes diversification; accentless explicit-reference
  parsing is not equivalent to folded topical retrieval.
- Diversify the first 24 candidates: first two chunks per document/article,
  then overflow, returning K=6. No learned reranker or neural retrieval.
- Gate: domain phrase list, corpus-scope list, explicit reference presence,
  top score ≥5, coverage ≥.5, heading coverage ≥.30 unless exact reference or
  overview, ≥1 sufficiently scoring evidence. Generic document overviews use
  Article 1. These lexical heuristics do not assess all required provisions,
  personal facts, semantic contradiction, or temporal legal applicability.

The local root environment's safe allowlisted values show generation disabled,
model `gemini-3.5-flash-lite`, one call/turn, eight/day and zero retries. No MVP
ranking overrides were present; defaults match `render.yaml`: K=6, score=5,
coverage=.5. The runner pins these values explicitly and never prints credentials.

## Generation and validator

`backend/services/pipelines/mvp_rag_pipeline.py` bounds history to 2,000 prompt
characters and each evidence text to 1,400 characters. Up to six evidence chunks
are used. Generation goes through `backend/services/llm.py` only. One shared
`llm_turn` is forced to one call for the demo; SDK attempts=1, application retries
configured zero. SQLite reservations count attempted requests including failures,
before transport, with an immediate transaction and fail-closed daily limit.
Provider metadata/token usage is discarded: the adapter returns text only.
`llm_used=false` on provider failure does **not** mean no upstream attempt occurred.

Validator behavior: resolves bracketed E# aliases; requires at least one valid
citation; checks normalized long quotes, article references and dates against the
union of full cited chunks; replaces a small regex set of current-effect phrases.
It does not verify entailment, document/version references, clause/point identity,
per-claim citation attachment, every legal claim's citation, or complete temporal
applicability. A reference to another article inside a chunk is permitted even if
that article is not itself retrieved. Invalid markers may be stripped without
rejecting remaining text. On whole-answer failure the pipeline returns excerpts.
The test report documents these limitations rather than silently fixing them.

## API, rate, legacy, deployment

`backend/models/demo.py` has strict extra-forbidden request fields, blank-message
rejection, history schema limits, typed sources/status metadata. Route defaults:
message ≤1,000 characters, six history messages/4,000 chars, 6 requests/minute and
60/day per observed client. `DemoRateLimiter` is process-local, sliding-window,
bounded and thread-safe; CORS exposes Retry-After. Anonymous chat does not persist
chat rows. Authentication/ownership remain enforced on legacy endpoints.

Legacy `ChatService` lazily starts `AgenticRAGPipeline` only behind live consent.
That pipeline has LangGraph routing, retrieval, grading, rewriting, contextual/
direct generation and no-document nodes. Its current startup requires dense
Vietnamese embeddings and Qdrant; reranking is optional. **None was initialized,
downloaded, or benchmarked here.** `LawDocumentService` is separate JSON/document
lookup with bundled demo fallback; it is not the demo's ranked QA retriever.
Old `benchmarks/` neural/DeepEval results are unrelated and were not run.

`render.yaml` specifies Render Free, no-dev/offline dependencies, demo readiness,
no downloads, automatic deployment disabled, and Gemini disabled, model
`gemini-3.5-flash-lite`, eight/day. Compose places Qdrant behind an optional profile.
These are versioned desired settings, **not proof of live deployment settings**.
`docs/m4-public-validation.md` records prior live deployment/Gemini-enabled and
50/day observations, conflicting with the blueprint's disabled/eight/day values.
The current audit made only two read-only public metadata requests (`demo/info`,
`demo/readyz`), both timed out. It did not retry, generate, load-test, or alter the
deployment. Fresh public model/cap/commit settings are therefore **unverified**.

Full network-blocked regression output and API-module counts are in
`evaluation/reports/pytest.xml` and `test-summary.json`. Passing mocks do not prove
provider model availability or legal validity.
