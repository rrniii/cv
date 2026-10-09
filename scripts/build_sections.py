#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "sections"
OUT_DIR = ROOT / "generated" / "tex"
MD_OUT_DIR = ROOT / "generated" / "md"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class SectionGroup:
    title: Optional[str]
    items: List[str]


@dataclass
class SectionDoc:
    title: str
    type: str
    groups: List[SectionGroup]
    postamble: Optional[str] = None
    date_position: str = "start"
    numbering_groups: Optional[List[List[str]]] = None
    subrubric_preamble: Optional[str] = None


class ParseError(RuntimeError):
    pass


def parse_frontmatter(text: str) -> Tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text

    lines = text.splitlines()
    fm: dict = {}
    i = 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == "---":
            body = "\n".join(lines[i + 1 :])
            return fm, body
        if not line.strip():
            i += 1
            continue
        if ":" not in line:
            raise ParseError(f"Invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "|":
            i += 1
            block: List[str] = []
            while i < len(lines):
                block_line = lines[i]
                if block_line.startswith("  "):
                    block.append(block_line[2:])
                    i += 1
                    continue
                if block_line.startswith("\t"):
                    block.append(block_line.lstrip("\t"))
                    i += 1
                    continue
                break
            fm[key] = "\n".join(block).rstrip()
            continue
        # Handle list values (lines starting with -)
        if value == "":
            i += 1
            list_items: List = []
            while i < len(lines):
                list_line = lines[i]
                if list_line.strip().startswith("- "):
                    # Check if it's a nested list (for numbering_groups)
                    indent = len(list_line) - len(list_line.lstrip())
                    item_text = list_line.strip()[2:].strip()
                    if item_text.startswith("[") and item_text.endswith("]"):
                        # Parse inline list like [a, b, c]
                        inner = item_text[1:-1]
                        inner_items = [s.strip().strip('"').strip("'") for s in inner.split(",")]
                        list_items.append(inner_items)
                    else:
                        list_items.append(item_text)
                    i += 1
                    continue
                elif list_line.startswith("  ") or list_line.startswith("\t"):
                    # Continuation of list
                    i += 1
                    continue
                break
            fm[key] = list_items
            continue
        fm[key] = value
        i += 1
    return fm, ""


def parse_metadata(text: str) -> Tuple[dict, str]:
    if text.startswith("<!--"):
        end = text.find("-->")
        if end != -1:
            block = text[4:end]
            fake = "---\n" + block.strip("\n") + "\n---\n"
            fm, _ = parse_frontmatter(fake)
            body = text[end + 3 :]
            return fm, body.lstrip("\n")
    if text.startswith("---"):
        return parse_frontmatter(text)
    return {}, text


def parse_markdown(body: str, fm: dict) -> Tuple[str, List[SectionGroup]]:
    title = fm.get("title")
    groups: List[SectionGroup] = []
    current_group_title: Optional[str] = None
    current_items: List[str] = []
    current_item_lines: Optional[List[str]] = None

    def flush_item() -> None:
        nonlocal current_item_lines
        if current_item_lines is None:
            return
        text = "\n".join(current_item_lines).strip()
        if text:
            current_items.append(text)
        current_item_lines = None

    def flush_group() -> None:
        nonlocal current_items
        flush_item()
        if current_items:
            groups.append(SectionGroup(current_group_title, current_items))
        current_items = []

    in_comment = False
    for raw_line in body.splitlines():
        line = raw_line.rstrip()

        # Skip HTML comments anywhere in the body. Only the leading metadata
        # comment is consumed by parse_metadata; without this, an explanatory
        # comment mid-file would be emitted as literal text in the PDF.
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        stripped = line.strip()
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_comment = True
            continue

        if not line.strip():
            if current_item_lines is not None:
                current_item_lines.append("")
            continue

        heading = HEADING_RE.match(line)
        if heading:
            text = heading.group(2).strip()
            if not title:
                title = text
            else:
                flush_group()
                current_group_title = text
            continue

        if line.startswith("- "):
            flush_item()
            current_item_lines = [line[2:].strip()]
            continue

        if current_item_lines is not None:
            if line.startswith("  ") or line.startswith("\t"):
                current_item_lines.append(line.strip())
            else:
                current_item_lines.append(line.strip())

    flush_group()
    if not title:
        raise ParseError("Missing title in frontmatter or H1 heading.")
    return title, groups


def md_inline_to_latex(text: str) -> str:
    links: list[str] = []

    def protect_link(match: re.Match[str]) -> str:
        label, url = match.groups()
        url = url.replace("%", r"\%").replace("#", r"\#").replace("&", r"\&")
        links.append(rf"\href{{{url}}}{{{label}}}")
        return f"CVLINKTOKEN{len(links) - 1}END"

    # Protect URLs from the emphasis conversion, particularly underscores in
    # DOI paths. Markdown hyperlinks remain clickable in the PDF.
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", protect_link, text)
    # Convert basic markdown emphasis to LaTeX, leaving other LaTeX intact.
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    # Single-asterisk italics after bold conversion.
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\\emph{\1}", text)
    # Single-underscore italics (avoid LaTeX math like $x_1$ or escaped underscores).
    text = re.sub(r"(?<![$\\])_(?!\s)(.+?)(?<!\s)_(?!_)", r"\\emph{\1}", text)
    # Line breaks become paragraph breaks.
    text = text.replace("\n", "\\par\n")
    for index, link in enumerate(links):
        text = text.replace(f"CVLINKTOKEN{index}END", link)
    return text



# Detailed grant entries: the credit share written after the role and the
# trailing "Investigators: ..." sentence (by convention the last sentence of an
# entry). A grants section renders WITHOUT them under its own name, so the
# ordinary CV variants show less detail; a "_full" md+tex pair keeps them for
# any document that includes those instead.
GRANT_ROLE_SHARE_RE = re.compile(r"(Role:[^.(]*?)\s*\(\d+\s*\\?%\)")
GRANT_INVESTIGATORS_RE = re.compile(r"\s*Investigators:.*\Z", re.S)


def brief_grant_item(item: str) -> str:
    item = GRANT_ROLE_SHARE_RE.sub(r"\1", item)
    return GRANT_INVESTIGATORS_RE.sub("", item).rstrip()


def grants_brief(doc: SectionDoc) -> SectionDoc:
    return SectionDoc(
        title=doc.title, type=doc.type, postamble=doc.postamble,
        date_position=doc.date_position, numbering_groups=doc.numbering_groups,
        subrubric_preamble=doc.subrubric_preamble,
        groups=[SectionGroup(g.title, [brief_grant_item(i) for i in g.items]) for g in doc.groups],
    )


def render_markdown(doc: SectionDoc, meta: dict) -> str:
    """Re-emit a parsed section as Markdown for the HTML build. `meta` lines go
    in the leading comment (e.g. the tex: override for the PDF build)."""
    lines = ["<!--"] + [f"{k}: {v}" for k, v in meta.items()] + ["-->", "", f"## {doc.title}"]
    for group in doc.groups:
        if group.title:
            lines += ["", f"### {group.title}"]
        lines.append("")
        for item in group.items:
            lines.append("- " + item.replace("\n", "\n  "))
    return "\n".join(lines) + "\n"


GRANT_INVESTIGATORS_LABEL_RE = re.compile(r"Investigators:\s*")


def full_grant_item(item: str) -> str:
    """The source keeps the "Investigators:" label as the marker for the detailed
    detail; the rendered full entry drops the word, since the parenthetical
    roles already identify the list."""
    return GRANT_INVESTIGATORS_LABEL_RE.sub("", item)


def write_full_grants(doc: SectionDoc, md_path: pathlib.Path, rel: pathlib.Path, out_dir: pathlib.Path) -> None:
    doc = SectionDoc(
        title=doc.title, type=doc.type, postamble=doc.postamble,
        date_position=doc.date_position, numbering_groups=doc.numbering_groups,
        subrubric_preamble=doc.subrubric_preamble,
        groups=[SectionGroup(g.title, [full_grant_item(i) for i in g.items]) for g in doc.groups],
    )
    stem = rel.with_name(rel.stem + "_full")
    (out_dir / stem.with_suffix(".tex")).write_text(render_section(doc, md_path), encoding="utf-8")
    md_out = MD_OUT_DIR / stem.with_suffix(".md")
    md_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.write_text(
        render_markdown(doc, {"type": doc.type, "detail": "full", "tex": f"generated/tex/{stem.as_posix()}"}),
        encoding="utf-8",
    )


def split_fields(text: str, expected: int, context: str) -> List[str]:
    parts = [p.strip() for p in text.split("|", expected - 1)]
    if len(parts) < expected:
        raise ParseError(
            f"Expected {expected} fields separated by '|' in {context}, got: {text}"
        )
    return parts


def render_section(doc: SectionDoc, source_path: pathlib.Path) -> str:
    lines: List[str] = []
    rel_source = source_path.relative_to(ROOT)
    lines.append(f"% Generated from {rel_source}. Do not edit by hand.")

    if doc.type == "bibliography":
        lines.extend(
            [
                rf"\makerubrichead{{{doc.title}}}",
                "",
                r"\begin{refsection}[submitted]",
                r"\nocite{*}",
                r"\printbibliography[heading={subbibliography},title={Submitted Manuscripts},resetnumbers=true]",
                r"\end{refsection}",
                "",
                r"\begin{refsection}[published]",
                r"\nocite{*}",
                r"\printbibliography[heading={subbibliography},title={Peer Reviewed Articles},resetnumbers=true]",
                r"\end{refsection}",
            ]
        )
    elif doc.type == "dated":
        lines.append(rf"\begin{{rubric}}{{{doc.title}}}")
        for group in doc.groups:
            if group.title:
                lines.append("")
                lines.append(rf"\subrubric{{{group.title}}}")
            for item in group.items:
                date, text = split_fields(item, 2, f"{rel_source}")
                lines.append(rf"\entry*[{date}] {md_inline_to_latex(text)}")
        lines.append("")
        lines.append(r"\end{rubric}")
    elif doc.type == "enumerated":
        # Build numbering group mapping
        group_to_counter: dict = {}
        counter_totals: dict = {}

        if doc.numbering_groups:
            # Assign groups to shared counters based on numbering_groups
            for counter_idx, group_list in enumerate(doc.numbering_groups):
                for group_name in group_list:
                    group_to_counter[group_name] = counter_idx
            # Calculate totals for each counter
            for group in doc.groups:
                if group.title and group.title in group_to_counter:
                    counter_idx = group_to_counter[group.title]
                    counter_totals[counter_idx] = counter_totals.get(counter_idx, 0) + len(group.items)

        # For groups not in any numbering_group, assign individual counters
        next_counter = len(doc.numbering_groups) if doc.numbering_groups else 0
        for group in doc.groups:
            if group.title and group.title not in group_to_counter:
                group_to_counter[group.title] = next_counter
                counter_totals[next_counter] = len(group.items)
                next_counter += 1

        # If no numbering_groups specified at all, use single counter (original behavior)
        if not doc.numbering_groups:
            total = sum(len(group.items) for group in doc.groups)
            counter_totals = {0: total}
            for group in doc.groups:
                if group.title:
                    group_to_counter[group.title] = 0

        # Track current count per counter
        current_counts = {k: v for k, v in counter_totals.items()}

        lines.append(rf"\begin{{enumeratedrubric}}{{{doc.title}}}")
        if doc.subrubric_preamble:
            # Emitted once for the whole rubric, before any subrubric.
            # Use \entry*[] (CurVe-native; \multicolumn and \noalign cause issues with \LTXtable)
            lines.append(rf"\entry*[]{{\small {doc.subrubric_preamble}}}")
        for group in doc.groups:
            if group.title:
                lines.append("")
                lines.append(rf"\subrubric{{{group.title}}}")

            counter_idx = group_to_counter.get(group.title, 0) if group.title else 0

            for item in group.items:
                if "|" in item:
                    date, text = split_fields(item, 2, f"{rel_source}")
                    if doc.date_position == "end":
                        content = rf"{text} \textit{{{date}}}"
                    else:
                        content = rf"\textit{{{date}}}. {text}"
                else:
                    content = item
                lines.append(rf"\entry*[{current_counts[counter_idx]}.] {md_inline_to_latex(content)}")
                current_counts[counter_idx] -= 1
        lines.append("")
        lines.append(r"\end{enumeratedrubric}")
    elif doc.type == "grants":
        total = sum(len(group.items) for group in doc.groups)
        current = total
        lines.append(rf"\begin{{grantrubric}}{{{doc.title}}}")
        for group in doc.groups:
            if group.title:
                lines.append("")
                lines.append(rf"\subrubric{{{group.title}}}")
            for item in group.items:
                parts = [p.strip() for p in item.split("|", 3)]
                if len(parts) == 4:
                    date, amount, _source_type, text = parts
                else:
                    date, amount, text = split_fields(item, 3, f"{rel_source}")
                lines.append(
                    rf"\grantentry{{{current}.}}{{{date}}}{{{md_inline_to_latex(text)}}}{{{md_inline_to_latex(amount)}}}"
                )
                current -= 1
        lines.append("")
        lines.append(r"\end{grantrubric}")
    else:
        raise ParseError(f"Unknown section type: {doc.type}")

    if doc.postamble:
        lines.append("")
        lines.append(doc.postamble.rstrip())

    return "\n".join(lines) + "\n"


def build_all(src_dir: pathlib.Path, out_dir: pathlib.Path) -> int:
    if not src_dir.exists():
        print(f"No sections directory at {src_dir}", file=sys.stderr)
        return 1

    errors = 0
    for md_path in sorted(src_dir.rglob("*.md")):
        # Skip markdown files under generated output dirs.
        if "tex" in md_path.parts or "html" in md_path.parts or "generated" in md_path.parts:
            continue
        rel = md_path.relative_to(src_dir)
        out_path = out_dir / rel.with_suffix(".tex")
        try:
            text = md_path.read_text(encoding="utf-8")
            fm, body = parse_metadata(text)
            title, groups = parse_markdown(body, fm)
            doc = SectionDoc(
                title=title,
                type=fm.get("type", "dated"),
                groups=groups,
                postamble=fm.get("postamble"),
                date_position=fm.get("date_position", "start"),
                numbering_groups=fm.get("numbering_groups"),
                subrubric_preamble=fm.get("subrubric_preamble"),
            )
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if doc.type == "grants":
                out_path.write_text(render_section(grants_brief(doc), md_path), encoding="utf-8")
                write_full_grants(doc, md_path, rel, out_dir)
            else:
                out_path.write_text(render_section(doc, md_path), encoding="utf-8")
        except Exception as exc:
            errors += 1
            print(f"Error processing {md_path}: {exc}", file=sys.stderr)
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LaTeX sections from markdown.")
    parser.add_argument("--src", default=str(SRC_DIR), help="Source directory")
    parser.add_argument("--out", default=str(OUT_DIR), help="Output directory")
    args = parser.parse_args()
    return build_all(pathlib.Path(args.src), pathlib.Path(args.out))


if __name__ == "__main__":
    raise SystemExit(main())
