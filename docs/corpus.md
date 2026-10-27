# Legal corpus and provenance

## Included runtime artifact

The application reads the committed
[`mvp_demo_corpus.jsonl`](../backend/resources/mvp_demo_corpus.jsonl) and
[manifest](../backend/resources/mvp_demo_corpus.manifest.json). No source download,
embedding build or local acquisition workspace is needed to run the demo.

| Instrument | Official source page | Chunks |
|---|---|---:|
| `43/2024/QH15` | [Government portal, docid 211201](https://vanban.chinhphu.vn/?pageid=27160&docid=211201) | 7 |
| `88/2024/NĐ-CP` | [Government portal, docid 210658](https://vanban.chinhphu.vn/?pageid=27160&docid=210658) | 83 |

Verified totals: **2 instruments, 90 unique chunks, 77,243 source-text characters**;
the JSONL file is **381,381 bytes**. Counts do not describe all Vietnamese or
Hanoi land law. The amending Law 43 is not the complete Land Law 31. Annex/form
templates of Decree 88 are excluded from searchable operative text.

JSONL SHA-256:
`ce0df852742ea3144ae5c04bdef27580d88d53752ad6039a4cdd0b091a73508e`.

Every chunk is `validity_status=unknown`, `review_status=technical_validation_only`.
Extraction checks and official URLs do not establish current force, amendment
coverage, applicability or independent legal review.

## Processing and format

The offline parser supports PDF, DOCX and HTML and extracts legal hierarchy with
exact text offsets. The demo builder selects two complete standalone stages that
passed technical extraction checks. It verifies raw/parsed hashes, includes each
article's descendant text, excludes annex nodes, and chunks article spans using
`legal-spans-v1` with `mvp-utf8-byte-budget-v1` and a 1,800-byte chunk budget.
This budget is not a Gemini tokenizer. Source spans are losslessly partitioned
within selected articles; contextual headers are separate from source text.

Important JSONL fields:

| Group | Fields |
|---|---|
| Identity | `chunk_id`, `document_id`, `document_number`, `stage_id` |
| Legal structure | `article_number`, `article_heading`, `article_locator`, `heading_path`, `page` |
| Evidence | `source_text`, `source_start`, `source_end`, `source_url` |
| Index context | `context`, `text`, tokenizer/chunker/parser versions |
| Provenance | `raw_sha256`, `parsed_text_sha256`, `text_sha256` |
| Review | `validity_status`, `review_status`, `partial`, `corpus_label` |

Offsets address the complete stage's parsed text, not PDF byte positions.
`source_end - source_start == len(source_text)` for every chunk. BM25 indexes
document number, heading and source text in memory. Lookup reconstructs the
selected document/article text for browsing; it is not a complete original-PDF
viewer or a legal consolidation service.

## Reproducibility

Verify the committed artifact without network access:

```bash
uv run --frozen python - <<'PY'
import hashlib, json
from pathlib import Path
p = Path('backend/resources/mvp_demo_corpus.jsonl')
m = json.loads(p.with_suffix('.manifest.json').read_text())
rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
assert hashlib.sha256(p.read_bytes()).hexdigest() == m['records_sha256']
assert len(rows) == m['chunk_count'] == 90
assert len({r['document_number'] for r in rows}) == m['document_count'] == 2
assert sum(len(r['source_text']) for r in rows) == 77243
assert len({r['chunk_id'] for r in rows}) == len(rows)
assert all(r['source_end'] - r['source_start'] == len(r['source_text']) for r in rows)
assert all(r['validity_status'] == 'unknown' for r in rows)
print('Corpus integrity and statistics verified')
PY
```

Full rebuilding with `scripts/build_mvp_demo_corpus.py` additionally requires the
preserved `data/phase-d-corpus-v2` acquisition/stage workspace and exact selected
stage IDs/hashes. That ignored workspace and raw PDFs are **not distributed in
Git**. A fresh clone can run/verify the bundled artifact but cannot reconstruct
its raw source acquisition solely from the runtime JSONL. Do not casually rebuild,
recrawl or replace it; separately approved acquisition and artifact review are
prerequisites. Never treat acquisition as ordinary setup.

Registries and approvals under `corpus/` preserve provenance history. The
[review runbook](corpus-review-runbook.md), [offline ingestion guide](offline-ingestion.md)
and [R0 research record](research-release-r0.md) describe the stricter canonical
review/seal path; this isolated research demo does not bypass or satisfy that path.
Software licensing does not license government-portal assets or third-party data.
