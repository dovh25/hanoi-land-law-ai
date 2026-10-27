# Controlled legal-source acquisition

This package supports source discovery, approval-bound acquisition, manual inbox
handling, quality inventories and provenance reporting. It is **not needed** to
run the bundled Hanoi Land Law AI demo; see the [runtime corpus](../docs/corpus.md).

| Module | Purpose |
|---|---|
| [pilot.py](pilot.py), [pilot_cli.py](pilot_cli.py) | Bounded acquisition and operator CLI |
| [catalog.py](catalog.py) | Official metadata discovery |
| [manual_inbox.py](manual_inbox.py) | Artifact binding and manual-source handling |
| [quality.py](quality.py), [reporting.py](reporting.py) | Extraction quality and provenance inventory |
| [main.py](main.py), [config.py](config.py) | Retained bulk JSON crawler and its configuration |

Use Python 3.12 and the root frozen environment, not a separate requirements
installation. See [source policy](../docs/corpus-sources.md),
[acquisition records](../docs/corpus-acquisition.md) and the
[review runbook](../docs/corpus-review-runbook.md) before operating on real sources.
Root `.env` is the only settings file. A safe CLI inspection is:

```bash
uv run --frozen python -m law_crawler.pilot_cli --help
```

Help is not permission to crawl. Network access, source-policy approval, artifact
licensing and legal review are separate prerequisites. Preserve raw artifacts and
provenance; do not infer current validity from the retained crawler's expiry filter.
The legacy crawler writes `Id`/`Content` JSON under its configured document folder;
those local files are ignored and are not the bundled demo corpus.
