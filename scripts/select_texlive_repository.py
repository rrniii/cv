#!/usr/bin/env python3
"""Choose an explicit CTAN repository compatible with the installed TinyTeX.

This reads local and remote package metadata only; it does not install TeX.
Mirrors are listed at https://ctan.org/mirrors. Checking the release year and
texlive-scripts revision prevents a stale mirror or cross-year cache downgrade.
"""
from __future__ import annotations

import concurrent.futures
import lzma
import re
import sys
import urllib.request
from pathlib import Path

REPOSITORIES = (
    "https://ctan.math.illinois.edu/systems/texlive/tlnet",
    "https://ftp.fau.de/ctan/systems/texlive/tlnet",
)


def metadata(text: str) -> tuple[int, int]:
    release = re.search(r"^depend release/(\d+)$", text, re.MULTILINE)
    record = re.search(r"^name texlive-scripts\n(.*?)(?=\n\n|\Z)", text, re.MULTILINE | re.DOTALL)
    revision = re.search(r"^revision (\d+)$", record.group(1), re.MULTILINE) if record else None
    if not release or not revision:
        raise ValueError("TeX Live release/revision metadata is missing")
    return int(release.group(1)), int(revision.group(1))


def remote_metadata(repository: str) -> tuple[str, tuple[int, int] | None, str | None]:
    try:
        with urllib.request.urlopen(repository + "/tlpkg/texlive.tlpdb.xz", timeout=20) as response:
            compressed = response.read(10_000_001)
            if len(compressed) > 10_000_000:
                raise ValueError("repository metadata exceeds the expected size")
            text = lzma.decompress(compressed).decode("utf-8")
        return repository, metadata(text), None
    except Exception as exc:
        return repository, None, str(exc)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: select_texlive_repository.py <TinyTeX root>", file=sys.stderr)
        return 1
    local_path = Path(sys.argv[1]) / "tlpkg" / "texlive.tlpdb"
    try:
        local_year, local_revision = metadata(local_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Cannot verify installed TinyTeX: {exc}", file=sys.stderr)
        return 1

    candidates: list[tuple[int, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(REPOSITORIES)) as executor:
        for repository, remote, error in executor.map(remote_metadata, REPOSITORIES):
            if error or remote is None:
                print(f"Repository unavailable: {repository}: {error}", file=sys.stderr)
                continue
            year, revision = remote
            print(f"Repository {repository}: release {year}, scripts revision {revision}", file=sys.stderr)
            if year == local_year and revision >= local_revision:
                candidates.append((revision, repository))

    if not candidates:
        print(
            f"No repository matches installed TeX Live {local_year} revision {local_revision}. "
            "Check mirror freshness; clear the TinyTeX cache if its release year is stale.",
            file=sys.stderr,
        )
        return 1
    # Preserve preference for the first mirror when both carry the same revision.
    newest = max(revision for revision, _ in candidates)
    selected = next(repository for revision, repository in candidates if revision == newest)
    print(selected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
