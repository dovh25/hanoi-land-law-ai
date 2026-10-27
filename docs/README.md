# Documentation index

## Current MVP guides

Start with the [project README](../README.md), then use:

| Guide | Purpose |
|---|---|
| [Architecture](architecture.md) | Runtime, API boundaries, state and privacy |
| [RAG pipeline](rag-pipeline.md) | Ranking, evidence gate, generation, citation checks and fallback |
| [Corpus](corpus.md) | Included sources, scope, metadata, hashes and reproducibility |
| [Environment setup](environment-setup.md) | Root configuration, frozen dependencies and offline checks |
| [Deployment](deployment.md) | Cloudflare Pages, Render, containers and health checks |
| [Evaluation](evaluation.md) | Provisional methodology, highlights and full evidence links |
| [Maintenance record](repository-maintenance.md) | Inventory, cleanup decisions and preservation boundaries |

## Operational and optional workflows

- [Legal data model and migrations](legal-data-model.md)
- [Offline ingestion](offline-ingestion.md)
- [Corpus review runbook](corpus-review-runbook.md) and [publication gates](corpus-review.md)
- [Colab Web batch workflow](colab-web.md)
- [Evaluation runbook](../evaluation/README.md) and [review worksheets guide](evaluation/dataset-review-guide.md)

These tools support development/research but are not prerequisites for running the
bundled lexical MVP. Network acquisition, model downloads and live generation
require separate approval.

## Preserved evidence and snapshots

Phase A–D validation reports, discovery/quality inventories, R0 research records,
older design documents/screenshots and the HTML/JSON architecture diagram record
their original scope. They are not current setup instructions, comprehensive legal
coverage or current production/QA measurements. Evidence is retained rather than
rewritten to make earlier outcomes appear current.

- [Source discovery](corpus-sources.md), [acquisition](corpus-acquisition.md),
  [inventory](corpus-inventory.md), [quality](corpus-quality-report.md)
- [Phase A](phase-a-validation.md), [Phase B](phase-b-validation.md),
  [Phase C](phase-c-validation.md), [Phase D](phase-d-validation.md),
  [D.1](phase-d1-validation.md), [D.2](phase-d2-validation.md)
- [R0 record](research-release-r0.md) and [neural-workflow readiness](next-phase-readiness.md)
- [MVP implementation-stage record](mvp-demo.md), [M4 deployment evidence](m4-public-validation.md),
  [earlier public UI audit](public-ui-audit.md)
- [Current UI design system](ui-redesign/design-system.md),
  [implementation/release evidence](ui-redesign/implementation-summary.md),
  [visual QA](ui-redesign/visual-qa-report.md)
- [Detailed evaluation summary](evaluation/results-summary.md) and
  [raw report](../evaluation/reports/offline-report.md)

Public deployments/settings can change after recorded checks. The latest recorded
UI release verified generation disabled; no new public probe or live call was
performed for this documentation pass.
