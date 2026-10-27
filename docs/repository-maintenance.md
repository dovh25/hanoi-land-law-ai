# Repository maintenance record

## Audit scope and starting state

Audit date: 2026-10-27; starting commit: `ce62729`. The inventory covers tracked
files and nonignored additions recursively, Python imports, frontend references,
tests, package/build configuration, deployment files, documentation and local
generated-directory contents. No other project's files were inspected.

Existing user work is preserved: deleted `report.pdf`, untracked `evaluation/`,
`docs/evaluation/` and `tests/test_evaluation.py`. Evaluation artifacts are inputs
to this documentation pass, not newly authored or independently reviewed results.

## Inventory and decisions

| Category | Paths | Decision and evidence |
|---|---|---|
| Current MVP runtime | `backend/api/v1/demo.py`, `backend/services/mvp_corpus.py`, `backend/services/pipelines/mvp_rag_pipeline.py`, `backend/resources/`, `frontend/src/`, active public assets | Retain; application factory and frontend routes use them directly |
| Supporting runtime | `backend/core/`, `backend/db/`, `backend/models/`, lookup/auth/chat/session services and routes | Retain; startup migrations, document reader, API compatibility and ownership tests depend on them |
| Development/testing | `tests/`, `frontend/tests/`, `scripts/`, Python/frontend manifests and lockfiles | Retain; offline regression and build workflow |
| Deployment/security | `render.yaml`, Dockerfiles, `docker-compose.yaml`, redirect rules, ignore files, `.env.example` | Retain; reproducible deployment and secret isolation |
| Corpus/provenance | `corpus/`, bundled JSONL/manifest, ignored `data/` source workspaces | Retain; registries may look duplicated but record acquisition decisions/version evidence |
| Optional workflows | `batch/`, `preprocess/`, `law_crawler/`, `notebooks/`, `colab-exchange/`, embedding pipelines, rerankers | Retain; cross-imports, tests, builder and operator workflows depend on them; not MVP request dependencies |
| Evaluation evidence | `evaluation/`, `docs/evaluation/`, `benchmarks/`, `eval.txt` | Retain unchanged; original datasets/results must remain accessible |
| Academic/provenance material | `main.tex`, `presentation.txt`, `LICENSE` | Retain; academic deliverables and inherited legal attribution, not proven disposable artifacts |
| Older visual/validation evidence | `docs/screenshots/`, architecture HTML/JSON, phase reports, UI reports, browser audit scripts | Retain as scoped evidence; current documentation does not present these as current architecture or QA scores |
| Unused scaffold | `frontend/public/vite.svg`, `frontend/src/assets/react.svg`, `frontend/src/App.css`, `frontend/README.md` | Remove; no application/build/test references; `main.tsx` loads `index.css`, not `App.css`; README is untouched Vite template guidance duplicated by root setup |
| Local generated output | root `dist/` wheel/source archive; caches, `.venv/`, `frontend/node_modules/`, browser/hosting state | Leave local data untouched and ignored; no tracked build output found; avoid deleting user environments or deployment state |
| Dependencies | `pyproject.toml`, `uv.lock`, `frontend/package*.json` | Retain unchanged; optional/imported/test/build dependencies are not removable solely because BM25 does not use them |

## Cleanup and organization

Only the four unused scaffold files listed above are removed by this pass. No active runtime,
test, corpus, report, license, dependency or deployment file is removed. No
directories are relocated. Older documents remain at stable paths, with snapshot
context where needed; the [documentation index](README.md) separates current
guides from evidence and optional workflows.

Root README and focused architecture, pipeline, corpus, deployment and evaluation
guides describe the same bundled MVP. Setup guidance is reconciled with the
application factory and environment template. Live operations are not enabled.
Package READMEs for acquisition/preprocessing/benchmarks are reduced to current
module guidance rather than stale installer/notebook examples. The environment
template's budget comment is clarified without changing any setting value.

## Validation boundary

Validation uses local installed dependencies, frozen lock checks, network-blocked
pytest, frontend lint/typecheck/build/tests, corpus/hash/metric recomputation,
local-link checks and pattern-based secret checks. Raw evaluation reports are not
overwritten. No external documentation requests, public probes, Gemini calls,
downloads, Docker pulls, deployment, staging or commits are part of this pass.

See the task's final validation summary for execution results. Public URLs are
supported by preserved deployment evidence, not by a new uptime check. Secret
pattern checks do not establish absence of every possible credential or audit Git
history exhaustively.

## Executed results

| Check | Result |
|---|---|
| Network-blocked backend regression | 282 passed |
| Frontend ESLint / TypeScript / production build | Passed |
| Frontend Node tests | 8 passed |
| Frozen dependency resolution / installed compatibility | `uv lock --check` and `uv pip check` passed with offline resolution |
| Python syntax/compilation | Passed for backend, batch, preprocessing, acquisition, benchmarks, scripts, tests and evaluation |
| Isolated application import/lifespan | Passed with temporary SQLite and disabled network/provider |
| Demo health/info/chat | Liveness/demo readiness 200; separate authenticated readiness 503; 2 documents / 90 chunks; in-scope chat `llm_disabled` with sources |
| Corpus integrity | Manifest/JSONL hash, unique IDs, character counts and all 90 preserved raw/parsed source spans verified |
| Evaluation consistency | Held-out metrics, bootstrap summaries, gate outcomes and citation fixtures recomputed in memory; identical to original report |
| Markdown checks | 50 Markdown files; 149 local file/image/anchor links checked; no broken targets or unclosed fences |
| Secrets | 290 repository text/build files checked for high-confidence credential patterns; no matches; actual local Gemini/JWT values absent from repository/build files |
| Deployment configuration | YAML parsed; Render health/start/generation flags, Compose isolation/profiles and Pages redirect contracts checked |
| Whitespace | `git diff --check` passed |

No runtime code, dependency values, lockfiles, legal artifacts or original
evaluation results changed. Fresh dependency installation, container build/start,
external link availability, Mermaid rendering and hosted deployment were not
executed; Markdown/Mermaid structure was reviewed locally. Existing installed
packages and Node 24.21.0 were used for validation. Local checks are not a hosted
service certification or an end-to-end legal-answer evaluation.
