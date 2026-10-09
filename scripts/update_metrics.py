#!/usr/bin/env python3
"""Generate publication counts from the local bibliography using only stdlib.

Citation metrics and monetary/student totals are deliberately omitted: they
need independently verified sources and cannot be inferred from this CV.
Google Scholar is linked in the contact header but is never scraped on build.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from render_publications_web import parse_bib

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PUB_DIR = ROOT / "publications"


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _, published = parse_bib(PUB_DIR / "published.bib")
    _, submitted = parse_bib(PUB_DIR / "submitted.bib")
    entries = published + submitted
    years = Counter(e.fields.get("year", "undated") for e in entries)
    types = Counter(e.entry_type for e in entries)
    stats = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "local_bibliography",
        "publications": {
            "published": len(published),
            "submitted": len(submitted),
            "total": len(entries),
            "by_year": dict(sorted(years.items(), reverse=True)),
            "by_type": dict(sorted(types.items())),
        },
    }
    (DATA_DIR / "stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    (DATA_DIR / "macros.tex").write_text(
        "% Generated from the local bibliography; no live citation metrics.\n"
        + rf"\newcommand{{\CVpublications}}{{{len(published)}}}" + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
