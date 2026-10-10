# Ryan R. Neely III — Curriculum vitae

An academic CV for the Professor of Atmospheric Physics at the University of
Leeds and the National Centre for Atmospheric Science. The site provides a
full CV, one-, two- and three-page summaries, and a publication list in PDF and
HTML.

- [CV website](https://rrniii.github.io/cv/)
- [University profile](https://environment.leeds.ac.uk/see/staff/1447/dr-ryan-neely-iii)
- [ORCID](https://orcid.org/0000-0003-4560-4812)
- [Google Scholar](https://scholar.google.com/citations?user=zK6Ngs0AAAAJ)

Content is adapted from the September 7, 2026 academic CV, with supporting
publication metadata from the earlier academic CV and primary journal pages.
Research contributions, leadership summaries and selected papers also draw on
the submitted Faraday Discovery Fellowship application of September 21, 2026.
These summaries describe established work; the fellowship's proposed research
is not presented as an awarded or completed programme.
The bibliography keeps preprints separate from journal articles, including
the WesCon--WOEST multi-Doppler wind-field preprint identified in the Faraday
publication list and checked against its publisher record. Publication provenance is recorded in
[data/publication_sources.json](data/publication_sources.json). This repository
is a maintained snapshot; build dates indicate when outputs were generated.

## Edit the content

`sections/` contains the Markdown sources. `publications/published.bib` and
`publications/submitted.bib` contain journal articles and preprints. Named
short-CV selections live in `publications/selections.json` and use explicit
BibTeX keys. The optional `recent` selection method orders records by date.

Each section starts with a metadata comment, a heading, and entries:

```markdown
<!--
type: dated
tex: generated/tex/education
-->

## Education

- 2012 | **PhD, Atmospheric and Oceanic Sciences**, University of Colorado Boulder
```

The `tex:` path must identify the generated file for that source. It is
particularly important when short variants share a heading with full sections.
Use `date | description` for dated sections and
`date | amount | description` for grants. Enumerated sections use
`type: enumerated`. Basic emphasis and Markdown HTTPS hyperlinks render in both
formats. Escape LaTeX special characters in prose (`\%`, `\&`, `\#`, `\_`).

Contact details are in `_quarto.yml` for HTML and `preamble.tex` for PDF. The
landing page is `web/index.html`; the portrait is `web/photo.png`. The PDF
preamble and publication renderer recognise the BibTeX name
`Neely, III, R. R.` and bold Ryan's name while preserving the suffix.

## Build

Requirements: Python 3.10 or later, Quarto, and a TeX Live/TinyTeX installation
with LuaLaTeX and Biber for PDFs. Python scripts use the standard library; no
virtual environment or Google Scholar scraper is required.

```sh
make all         # generate sources, render all PDFs/HTML, assemble landing page
make html        # HTML only; does not require TeX
make pdf         # PDF only
make 1p          # one-page PDF and HTML
make cv-pdf      # full CV PDF
```

`PYTHON` and `QUARTO` can be overridden, for example
`make PYTHON=/path/to/python3 QUARTO=/path/to/quarto html`.

Run `make generate` before calling `quarto render` directly on a clean checkout:
Quarto resolves includes before its pre-render hooks. Outputs go into `_build/`;
use `make all` to explicitly build both PDF and HTML, since a plain render uses
each document's default format.
`generated/` and `data/stats.json`/`data/macros.tex` are rebuilt automatically and
must not be edited by hand. `make clean` removes `_build/`.

The pipeline does not fetch citation metrics or calculate funding/student
aggregates. Publication counts describe the local bibliography only. Scholar
links are provided for readers who want the live profile.

## Deployment and review

GitHub Actions builds PDF and HTML on pull requests, main pushes and manual
runs. Every successful build produces a downloadable `cv-build` artifact.
The build checks that the short PDFs contain exactly one, two and three pages;
rendered files remain downloadable for review if that check fails.
Only main pushes and manual runs on main deploy GitHub Pages and create a PDF
release tagged with the source commit. Pull requests only build. Configure
repository Pages to use GitHub Actions.

CI verifies the installed TeX Live release against explicit CTAN mirror
metadata before updating packages. A stale mirror is skipped; an incompatible
cache/release fails with a diagnostic instead of attempting a downgrade.

Before publishing content changes, check source accuracy, render the HTML and
inspect PDF layout and the advertised short-variant page limits. The short
PDFs use a compact contact header and shortened author lists; the full CV
retains complete author lists.

## Template provenance

Forked from [mgrau/cv](https://github.com/mgrau/cv), preserving its Quarto,
Markdown and CurVe styling pipeline. The underlying LaTeX styling credits
LianTze Lim in `settings.sty`. No additional licence is asserted by this fork;
the upstream repository does not supply a licence file.
