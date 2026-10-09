#!/usr/bin/env python3
"""Remove LaTeX build artifacts from the Quarto output directory."""
from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    if os.environ.get("CV_SKIP_CLEAN") == "1" or os.environ.get("CURVE_SKIP_CLEAN") == "1":
        print("Skipping LaTeX artifact cleanup (CV_SKIP_CLEAN/CURVE_SKIP_CLEAN=1).")
        return 0

    project_dir = Path(os.environ.get("QUARTO_PROJECT_DIR", Path(__file__).resolve().parents[1]))
    output_dir = Path(os.environ.get("QUARTO_PROJECT_OUTPUT_DIR", project_dir / "_build"))

    if not output_dir.exists():
        return 0

    extensions = {
        ".aux",
        ".bbl",
        ".bcf",
        ".blg",
        ".fdb_latexmk",
        ".fls",
        ".log",
        ".out",
        ".run.xml",
        ".synctex",
        ".toc",
        ".lof",
        ".lot",
        ".nav",
        ".snm",
        ".tex",
    }

    removed = 0
    for path in output_dir.rglob("*"):
        if not path.is_file():
            continue

        name = path.name
        suffix = path.suffix
        if name.endswith(".synctex.gz"):
            path.unlink(missing_ok=True)
            removed += 1
            continue

        if suffix in extensions:
            path.unlink(missing_ok=True)
            removed += 1

    # Clean latexmk database files in the project root.
    for path in project_dir.glob("*.fdb_latexmk"):
        path.unlink(missing_ok=True)
        removed += 1

    # Also clean root-level artifacts for Quarto-rendered PDFs (e.g., cv-full-quarto.*)
    for pdf_path in output_dir.glob("*.pdf"):
        stem = pdf_path.stem
        if not stem.endswith("-quarto"):
            continue
        for ext in extensions:
            candidate = project_dir / f"{stem}{ext}"
            if candidate.exists():
                candidate.unlink(missing_ok=True)
                removed += 1
        synctex = project_dir / f"{stem}.synctex.gz"
        if synctex.exists():
            synctex.unlink(missing_ok=True)
            removed += 1

    # Clean root-level bibliography artifacts.
    for bbl in project_dir.glob("*.bbl"):
        bbl.unlink(missing_ok=True)
        removed += 1
    dm_cfg = project_dir / "biblatex-dm.cfg"
    if dm_cfg.exists():
        dm_cfg.unlink(missing_ok=True)
        removed += 1

    if removed:
        print(f"Removed {removed} LaTeX artifact(s).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
