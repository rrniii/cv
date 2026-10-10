# CV compilation via Quarto. Python scripts use only the standard library.
.PHONY: all generate site pdf html cv 3p 2p 1p cv-pdf cv-html \
        3p-pdf 3p-html 2p-pdf 2p-html 1p-pdf 1p-html clean

.DEFAULT_GOAL := all

PYTHON ?= python3
QUARTO ?= quarto

# Includes must exist before Quarto enumerates project input files.
generate:
	$(PYTHON) scripts/build_sections.py
	$(PYTHON) scripts/update_metrics.py
	$(PYTHON) scripts/render_publications_web.py

all: generate
	$(QUARTO) render --to pdf
	$(QUARTO) render --to html --no-clean
	$(MAKE) site

site:
	mkdir -p _build
	cp web/robots.txt web/photo.png _build/
	sed "s/{{BUILD_DATE}}/$$(date -u +%Y-%m-%d)/" web/index.html > _build/index.html

pdf: generate
	$(QUARTO) render --to pdf

html: generate
	$(QUARTO) render --to html
	$(MAKE) site

cv 3p 2p 1p: generate
	$(QUARTO) render $(if $(filter cv,$@),cv.qmd,cv-$@.qmd) --to pdf
	$(QUARTO) render $(if $(filter cv,$@),cv.qmd,cv-$@.qmd) --to html --no-clean

cv-pdf cv-html: generate
	$(QUARTO) render cv.qmd --to $(subst cv-,,$@)

3p-pdf 2p-pdf 1p-pdf: generate
	$(QUARTO) render cv-$(subst -pdf,,$@).qmd --to pdf

3p-html 2p-html 1p-html: generate
	$(QUARTO) render cv-$(subst -html,,$@).qmd --to html

clean:
	rm -rf _build/
