# Contributor guidance

This is Ryan R. Neely III's academic CV, built with Quarto and the CurVe LaTeX
class. Read README.md for source provenance, build requirements and deployment.

- Edit source content in sections/ and publications/, preserving source facts.
- Every Markdown section needs a `tex: generated/tex/<relative source stem>`
  metadata line so the PDF filter selects the correct full or short section.
- Do not edit generated/, data/stats.json or data/macros.tex by hand.
- Contact metadata lives in _quarto.yml (HTML), preamble.tex (PDF) and
  web/index.html (landing page). Keep these consistent.
- BibTeX encodes Ryan's suffix as `Neely, III, R. R.`. The HTML and PDF
  formatting preserve III and bold the name.
- Short publication selections use explicit keys (or recent date order).
  Builds never scrape Scholar or reuse citation caches.
- Do not infer current metrics, grant shares, award decisions or student
  statuses. Retain the source's distinctions between journal articles,
  preprints, datasets and other scholarly outputs.
- Build with `make all`, or `make html` without a TeX installation. Python
  scripts use only the standard library. No .venv is required.
- Run `make generate` before direct Quarto calls on a fresh checkout.
- Check the source record, HTML behaviour and PDF layout; verify the short
  variants' one-, two- and three-page limits after meaningful content edits.
- GitHub Actions produces a downloadable cv-build artifact for every build.
  Only main pushes/manual runs on main deploy Pages and create PDF releases.
  CI validates TeX Live mirror freshness and release compatibility before
  updating packages; clear an incompatible cache rather than downgrading TeX.

Preserve upstream history and template attribution in settings.sty. Do not
add an invented licence or publish private source documents.
