#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUB_DIR = ROOT / "publications"
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "generated" / "md"
OUT_TEX_DIR = ROOT / "generated" / "tex"
OUT_PATH = OUT_DIR / "publications.md"
SELECTIONS_PATH = PUB_DIR / "selections.json"

ENTRY_RE = re.compile(r"@(?P<kind>\w+)\s*\{", re.IGNORECASE)

MONTH_INDEX = {
    "1": 1, "01": 1, "jan": 1, "january": 1,
    "2": 2, "02": 2, "feb": 2, "february": 2,
    "3": 3, "03": 3, "mar": 3, "march": 3,
    "4": 4, "04": 4, "apr": 4, "april": 4,
    "5": 5, "05": 5, "may": 5,
    "6": 6, "06": 6, "jun": 6, "june": 6,
    "7": 7, "07": 7, "jul": 7, "july": 7,
    "8": 8, "08": 8, "aug": 8, "august": 8,
    "9": 9, "09": 9, "sep": 9, "sept": 9, "september": 9,
    "10": 10, "oct": 10, "october": 10,
    "11": 11, "nov": 11, "november": 11,
    "12": 12, "dec": 12, "december": 12,
}

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


@dataclass
class BibEntry:
    entry_type: str
    key: str
    fields: dict[str, str]


def find_matching_brace(text: str, start: int) -> int:
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("Unmatched brace in BibTeX input.")


def split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    brace_depth = 0
    quote_open = False

    for char in text:
        if char == '"' and brace_depth == 0:
            quote_open = not quote_open
        elif char == "{" and not quote_open:
            brace_depth += 1
        elif char == "}" and not quote_open and brace_depth > 0:
            brace_depth -= 1

        if char == "," and brace_depth == 0 and not quote_open:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue

        current.append(char)

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def strip_wrapping(value: str) -> str:
    value = value.strip().rstrip(",")
    if len(value) >= 2 and value[0] == "{" and value[-1] == "}":
        return value[1:-1].strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].strip()
    return value


def strip_tex_wrappers(value: str) -> str:
    value = value.replace("~", " ")
    value = value.replace(r"\&", "&")
    value = value.replace(r"\%", "%")
    value = value.replace(r"\$", "$")
    value = value.replace(r"\_", "_")
    value = re.sub(r"\{([^{}]*)\}", r"\1", value)
    return value.strip()


def parse_bib(path: Path) -> tuple[dict[str, str], list[BibEntry]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    strings: dict[str, str] = {}
    entries: list[BibEntry] = []
    index = 0

    while True:
        match = ENTRY_RE.search(text, index)
        if not match:
            break
        kind = match.group("kind").lower()
        open_brace = text.find("{", match.start())
        close_brace = find_matching_brace(text, open_brace)
        body = text[open_brace + 1 : close_brace].strip()
        index = close_brace + 1

        if kind in {"comment", "preamble"}:
            continue

        parts = split_top_level(body)
        if not parts:
            continue

        if kind == "string":
            if "=" not in parts[0]:
                continue
            key, value = parts[0].split("=", 1)
            strings[key.strip().lower()] = strip_tex_wrappers(strip_wrapping(value))
            continue

        key = parts[0].strip()
        fields: dict[str, str] = {}
        for part in parts[1:]:
            if "=" not in part:
                continue
            field_name, raw_value = part.split("=", 1)
            field_name = field_name.strip().lower()
            raw_value = strip_wrapping(raw_value)
            replacement = strings.get(raw_value.strip().lower(), raw_value)
            fields[field_name] = strip_tex_wrappers(replacement)

        entries.append(BibEntry(entry_type=kind, key=key, fields=fields))

    return strings, entries


def normalize_name(name: str) -> str:
    name = strip_tex_wrappers(name)
    if "," in name:
        family, given = [part.strip() for part in name.split(",", 1)]
        return f"{given} {family}".strip()
    return name.strip()


def format_author_name(name: str) -> str:
    name = strip_tex_wrappers(name).strip()
    suffix = ""
    if "," in name:
        parts = [part.strip() for part in name.split(",")]
        family = parts[0]
        if len(parts) >= 3:
            suffix, given = parts[1], parts[2]
        else:
            given = parts[1]
    else:
        parts = name.split()
        if not parts:
            return ""
        if parts[-1].rstrip(".") in {"II", "III", "IV", "Jr", "Sr"}:
            suffix = parts.pop()
        family = parts[-1]
        given = " ".join(parts[:-1])

    # Handle common exports alongside BibTeX's "Neely, III, Ryan R." form.
    for field in ("family", "given"):
        value = family if field == "family" else given
        match = re.search(r"\s+(II|III|IV|Jr\.?|Sr\.?)$", value)
        if match:
            suffix = suffix or match.group(1)
            value = value[:match.start()]
            if field == "family":
                family = value
            else:
                given = value
    initials = [part[0].upper() + "." for part in re.findall(r"[A-Za-zÀ-ÿ]+", given)]
    formatted = " ".join(initials + [family] + ([suffix] if suffix else []))

    normalized_family = re.sub(r"[^a-z]", "", family.lower())
    if normalized_family == "neely" and initials and initials[0] == "R.":
        return f"**{formatted}**"
    return formatted


def join_authors(authors: list[str]) -> str:
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} and {authors[1]}"
    return ", ".join(authors[:-1]) + f", and {authors[-1]}"


def format_authors(value: str) -> str:
    authors = [format_author_name(part) for part in value.split(" and ") if part.strip()]
    return join_authors([author for author in authors if author])


def format_date(fields: dict[str, str]) -> str:
    month = fields.get("month", "").strip().lower()
    year = fields.get("year", "").strip()
    month_num = MONTH_INDEX.get(month, 0)
    if month_num and year:
        return f"{MONTH_NAMES[month_num]} {year}"
    return year


def format_year(year: str) -> str:
    year = year.strip()
    return f"**{year}**" if year else ""


def trim_terminal_period(text: str) -> str:
    return text.rstrip().rstrip(".")


def doi_fragment(fields: dict[str, str]) -> str:
    doi = fields.get("doi", "").strip()
    if doi:
        href = doi if doi.startswith("http") else f"https://doi.org/{doi}"
        label = doi.removeprefix("https://doi.org/")
        return f'<span class="doi-fragment">DOI: <a href="{href}" class="doi-link">{label}</a></span>'

    url = fields.get("url", "").strip()
    if url:
        return f'<span class="doi-fragment doi-fragment--generic"><a href="{url}" class="doi-link doi-link--generic">{url}</a></span>'

    return ""


def sort_key(entry: BibEntry) -> tuple[int, int, str]:
    try:
        year = int(entry.fields.get("year", "0"))
    except ValueError:
        year = 0
    month = MONTH_INDEX.get(entry.fields.get("month", "").strip().lower(), 0)
    return (year, month, entry.fields.get("title", "").lower())


def format_publication(entry: BibEntry, submitted: bool) -> str:
    fields = entry.fields
    pieces: list[str] = []

    authors = fields.get("author")
    if authors:
        pieces.append(f"{format_authors(authors)}.")

    title = fields.get("title")
    if title:
        pieces.append(f"“{trim_terminal_period(title)}”.")

    journal = fields.get("journal")
    date = format_date(fields)
    year = fields.get("year", "").strip()
    volume = fields.get("volume")
    number = fields.get("number") or fields.get("issue")
    pages = fields.get("pages")

    if submitted:
        note = fields.get("note", "Submitted").capitalize()
        venue = f"*{journal}*" if journal else ""
        if venue and note:
            venue += f" {note}"
        elif note:
            venue = note
        if date:
            month_year = date
            if year:
                month_year = month_year.replace(year, format_year(year))
            venue += f", {month_year}"
        venue = trim_terminal_period(venue) + "."
    else:
        detail_parts: list[str] = []
        if volume:
            detail_parts.append(volume)
        if pages:
            detail_parts.append(pages)
        elif number:
            detail_parts.append(number)

        venue = f"*{journal}*" if journal else ""
        if detail_parts:
            venue += " " + ", ".join(detail_parts)
        if year:
            venue += f" ({format_year(year)})"
        venue = trim_terminal_period(venue) + "."

    if venue:
        pieces.append(venue)

    doi = doi_fragment(fields)
    if doi:
        pieces.append(doi)

    return " ".join(pieces)


def render_section(title: str, entries: list[BibEntry], submitted: bool) -> str:
    items = "\n".join(
        f"1. {format_publication(entry, submitted=submitted)}"
        for entry in sorted(entries, key=sort_key, reverse=True)
    )
    return f"### {title}\n\n{items}"


def load_stats() -> dict:
    stats_path = DATA_DIR / "stats.json"
    if not stats_path.exists():
        return {}
    return json.loads(stats_path.read_text(encoding="utf-8"))


def metrics_line(stats: dict) -> str:
    published = (stats.get("publications") or {}).get("published")
    return f"*{published} peer-reviewed publications in this bibliography*" if published is not None else ""


def select_entries(spec: dict, entries: list[BibEntry]) -> list[BibEntry]:
    """Select explicitly named or recent entries without citation-cache input."""
    method = spec.get("method", "keys")
    count = int(spec.get("count", 5))
    excluded = set(spec.get("exclude", []))
    entries = [e for e in entries if e.key not in excluded]
    if method == "keys":
        key_set = set(spec.get("keys", []))
        return [e for e in entries if e.key in key_set]
    if method == "recent":
        return sorted(entries, key=sort_key, reverse=True)[:count]
    raise ValueError(f"Unsupported selection method: {method}; use keys or recent")


def load_selections() -> dict[str, dict]:
    if not SELECTIONS_PATH.exists():
        return {}
    config = json.loads(SELECTIONS_PATH.read_text(encoding="utf-8"))
    return {name: spec for name, spec in config.items() if not name.startswith("_")}


def write_selection_outputs(
    name: str,
    selected: list[BibEntry],
    submitted_keys: set[str],
    full_cv_url: str | None = None,
) -> None:
    """Write the md (HTML render, with tex: override) and tex (PDF render) for one selection."""
    keys = [e.key for e in sorted(selected, key=sort_key, reverse=True)]
    tex_stem = f"publications_selected_{name}"

    selected_submitted = [e for e in selected if e.key in submitted_keys]
    selected_published = [e for e in selected if e.key not in submitted_keys]

    md_body = [
        f"<!--\ntex: input:generated/tex/{tex_stem}\n-->",
        "## Selected Publications",
    ]
    if selected_submitted:
        md_body.append(render_section("Preprints", selected_submitted, submitted=True))
    if selected_published:
        md_body.append(render_section("Peer Reviewed Articles", selected_published, submitted=False))
    md_note = "\n\n*See the full CV for the complete publication list.*"
    tex_note = "\\noindent\\textit{See the full CV for the complete publication list.}"
    if full_cv_url:
        label = full_cv_url.removeprefix("https://")
        md_note = f"\n\n*Full CV and publication list: [{label}]({full_cv_url}).*"
        tex_note = (
            "\\noindent\\textit{Full CV and publication list: "
            + rf"\href{{{full_cv_url}}}{{{label}}}"
            + ".}"
        )
    (OUT_DIR / f"{tex_stem}.md").write_text(
        "\n\n".join(md_body) + md_note + "\n", encoding="utf-8"
    )

    tex_lines = [
        f"% Generated from publications/selections.json ('{name}'). Do not edit by hand.",
        "\\makerubrichead{Selected Publications}",
        "",
        "\\begin{refsection}[publications/published.bib,publications/submitted.bib]",
        "\\nocite{" + ",".join(keys) + "}",
        "\\printbibliography[heading=none,resetnumbers=true]",
        "\\end{refsection}",
        "",
        "\\vspace{0.5em}",
        tex_note,
    ]
    OUT_TEX_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_TEX_DIR / f"{tex_stem}.tex").write_text("\n".join(tex_lines) + "\n", encoding="utf-8")



STUDENT_LEGEND_TEX = (
    "\\iftoggle{studentmarkers}{\\textsuperscript{\\textdagger}\\emph{indicates graduate and "
    "\\textsuperscript{\\textdaggerdbl}undergraduate student co-authors}}{}"
)


def write_split_publication_sections(
    published: list[BibEntry], submitted: list[BibEntry], stats: dict
) -> None:
    """Generate optional separate published and under-review sections."""
    OUT_TEX_DIR.mkdir(parents=True, exist_ok=True)

    md = [
        "<!--\ntex: input:generated/tex/publications_peer_reviewed\n-->",
        "## Publications",
        metrics_line(stats),
        render_section("Peer Reviewed Articles", published, submitted=False),
    ]
    (OUT_DIR / "publications_peer_reviewed.md").write_text(
        "\n\n".join(part for part in md if part) + "\n", encoding="utf-8"
    )
    tex = [
        "% Generated by scripts/render_publications_web.py. Do not edit by hand.",
        "\\makerubrichead{Publications}",
        STUDENT_LEGEND_TEX,
        "",
        "\\begin{refsection}[published]",
        "\\nocite{*}",
        "\\printbibliography[heading={subbibliography},title={Peer Reviewed Articles},resetnumbers=true]",
        "\\end{refsection}",
    ]
    (OUT_TEX_DIR / "publications_peer_reviewed.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")

    md = [
        "<!--\ntex: input:generated/tex/manuscripts_under_review\n-->",
        "## Research and Manuscripts Under Review or In-Progress",
        render_section("Preprints", submitted, submitted=True),
    ]
    (OUT_DIR / "manuscripts_under_review.md").write_text(
        "\n\n".join(part for part in md if part) + "\n", encoding="utf-8"
    )
    tex = [
        "% Generated by scripts/render_publications_web.py. Do not edit by hand.",
        "\\makerubrichead{Research and Manuscripts Under Review or In-Progress}",
        STUDENT_LEGEND_TEX,
        "",
        "\\begin{refsection}[submitted]",
        "\\nocite{*}",
        "\\printbibliography[heading={subbibliography},title={Preprints},resetnumbers=true]",
        "\\end{refsection}",
    ]
    (OUT_TEX_DIR / "manuscripts_under_review.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _, submitted_entries = parse_bib(PUB_DIR / "submitted.bib")
    _, published_entries = parse_bib(PUB_DIR / "published.bib")
    stats = load_stats()

    body = [
        "## Publications",
        metrics_line(stats),
        render_section("Preprints", submitted_entries, submitted=True),
        render_section("Peer Reviewed Articles", published_entries, submitted=False),
    ]
    OUT_PATH.write_text("\n\n".join(part for part in body if part) + "\n", encoding="utf-8")
    write_split_publication_sections(published_entries, submitted_entries, stats)

    all_entries = published_entries + submitted_entries
    submitted_keys = {e.key for e in submitted_entries}
    for name, spec in load_selections().items():
        selected = select_entries(spec, all_entries)
        missing = set(spec.get("keys", [])) - {e.key for e in all_entries}
        if missing:
            print(f"Warning: selection '{name}' references unknown keys: {sorted(missing)}")
        write_selection_outputs(name, selected, submitted_keys, spec.get("full_cv_url"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
