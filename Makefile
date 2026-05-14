# Rural Geography Classification Pipeline
# =========================================
# Usage:
#   make parse           # parse PDFs → markdown (docling)
#   make embed           # SPECTER2 embeddings (GPU recommended)
#   make cluster         # EVoC clustering + viz.json
#   make sync-data       # copy latest viz.json into frontend
#   make frontend        # build static site
#   make all             # cluster → sync → build
#
#   make parse FORMAT=json            # parse PDFs → json
#   make parse PARSER=olmocr          # parse PDFs with olmOCR2 (conda env)
#   make embed cluster                # full transform pipeline
#
# Run tracking:
#   Each embed/cluster invocation creates a timestamped run in
#   transform/output/runs/<id>/ with a meta.json. The "latest"
#   symlink always points to the most recent run.
#
#   To reuse a run ID:  make embed RUN_ID=20240424-172522

# --- Paths ---
WOS_CSV    := extract/input/Full Dataset Rur Geog WoS 1986-2025 4-28-2026.csv
SUMMARIES  := summarize/output/all_summaries_same_style.json
LATEST     := transform/output/latest

# Optional: pass RUN_ID=<id> to reuse a run directory
RUN_ARGS   := $(if $(RUN_ID),--run-id $(RUN_ID),)

# Parse options
PARSER     := docling
FORMAT     := markdown

.PHONY: all parse parse-dots-flatten embed cluster sync-data export-annotations sync-annotations frontend deploy clean help

all: frontend

# --- Extract ---
extract/output/openalex_works.json: $(WOS_CSV)
	uv run python extract/src/fetch_openalex.py

# --- Parse ---
# olmocr & dots both run from .venv-olmocr and need pdftoppm from the
# conda-installed poppler prefix on PATH. Both also need a vllm server
# (typically started from .venv) loaded with the matching model:
#   olmocr → allenai/olmOCR-2-7B-1025-FP8, port 8001, --served-model-name olmocr
#   dots   → rednote-hilab/dots.ocr,       port 8002, --served-model-name dots
# Output layouts (after post-steps):
#   parse/output/olmocr/<doi>.md
#   parse/output/dots/<doi>.md       (concatenated from per-page files;
#                                     per-page json/jpg remain in <doi>/)
OLMOCR_VENV := .venv-olmocr
POPPLER_BIN := $(HOME)/.local/poppler/bin
DOTS_PORT   := 8002
DOTS_MODEL  := dots

parse: extract/output/pdfs
ifeq ($(PARSER),olmocr)
	PATH="$(POPPLER_BIN):$(CURDIR)/$(OLMOCR_VENV)/bin:$$PATH" \
	  $(OLMOCR_VENV)/bin/olmocr parse/output/olmocr --markdown \
	  --pdfs extract/output/pdfs/*.pdf
	mv parse/output/olmocr/markdown/extract/output/pdfs/*.md parse/output/olmocr/
	rm -rf parse/output/olmocr/markdown
else ifeq ($(PARSER),dots)
	@mkdir -p parse/output/dots
	@for pdf in extract/output/pdfs/*.pdf; do \
	  stem=$$(basename "$$pdf" .pdf); \
	  if [ -f "parse/output/dots/jsonl/$$stem.jsonl" ] || \
	     [ -f "parse/output/dots/$$stem.jsonl" ]; then \
	    echo "[dots] skip $$stem (already parsed)"; \
	    continue; \
	  fi; \
	  echo "[dots] $$pdf"; \
	  PATH="$(POPPLER_BIN):$$PATH" \
	    $(OLMOCR_VENV)/bin/python parse/dots.ocr/dots_ocr/parser.py "$$pdf" \
	    --output parse/output/dots \
	    --port $(DOTS_PORT) --model_name $(DOTS_MODEL) || exit $$?; \
	done
	$(MAKE) parse-dots-flatten
else
	uv run python parse/src/parse_pdfs.py extract/output/pdfs \
	  -o parse/output/$(PARSER) --format $(FORMAT)
endif

# Post-process dots.ocr output so the downstream pipeline can treat it like
# docling: parse/output/dots/<doi>.md (one file per PDF), with per-page jsonl
# layout files relocated to parse/output/dots/jsonl/. The per-PDF subdir keeps
# its jpegs / per-page jsons for inspection. The grep -v strips dots.ocr's
# inline base64 PNG data URIs (it embeds page renders in the markdown).
parse-dots-flatten:
	@for d in parse/output/dots/*/; do \
	  stem=$$(basename "$$d"); \
	  [ "$$stem" = "jsonl" ] && continue; \
	  files=$$(ls -v "$$d"$${stem}_page_*_nohf.md 2>/dev/null); \
	  if [ -n "$$files" ]; then \
	    echo "[flatten] $$stem"; \
	    echo "$$files" | xargs cat | grep -v 'data:image' \
	      > parse/output/dots/$${stem}.md; \
	  fi; \
	done
	@if ls parse/output/dots/*.jsonl >/dev/null 2>&1; then \
	  mkdir -p parse/output/dots/jsonl; \
	  mv parse/output/dots/*.jsonl parse/output/dots/jsonl/; \
	  echo "[flatten] moved jsonl → parse/output/dots/jsonl/"; \
	fi

# --- Transform ---
embed: $(SUMMARIES)
	cd transform/src && uv run python embed.py \
	  ../../$(SUMMARIES) \
	  "../../$(WOS_CSV)" \
	  --device cuda \
	  $(RUN_ARGS)

cluster: $(LATEST)/embeddings.npy $(SUMMARIES)
	cd transform/src && uv run python cluster.py \
	  ../../$(LATEST)/embeddings.npy \
	  ../../$(LATEST)/dois.json \
	  "../../$(WOS_CSV)" \
	  "../../$(WOS_CSV)" \
	  ../../$(SUMMARIES) \
	  $(RUN_ARGS)

# --- Annotations distribution (Label Studio) ---
# Pulls project 100 from LS, aggregates per-control / per-annotator counts,
# and writes transform/output/annotations.json. Needs LABEL_STUDIO_URL and
# LABEL_STUDIO_API_KEY (loaded from .env by the script).
export-annotations:
	cd transform/src && uv run python export_annotations.py

sync-annotations: transform/output/annotations.json
	cp transform/output/annotations.json frontend/src/lib/data/annotations.json
	@echo "Synced annotations.json"

# --- Frontend ---
sync-data: $(LATEST)/viz.json
	cp $(LATEST)/viz.json frontend/src/lib/data/viz.json
	@echo "Synced viz.json from $(LATEST)"

frontend: sync-data
	cd frontend && npm run build

deploy: frontend
	cd frontend && npm run build

# --- Utilities ---
help:
	@echo "Targets:"
	@echo "  parse       - Parse PDFs (PARSER=docling FORMAT=markdown)"
	@echo "  embed       - Run SPECTER2 embeddings (needs GPU)"
	@echo "  cluster     - Run EVoC clustering"
	@echo "  sync-data   - Copy latest viz.json into frontend"
	@echo "  export-annotations - Pull LS annotations → transform/output/annotations.json"
	@echo "  sync-annotations   - Copy annotations.json into frontend"
	@echo "  frontend    - Build static site"
	@echo "  deploy      - Build for deployment"
	@echo "  clean       - Remove all runs"
	@echo ""
	@echo "Options:"
	@echo "  PARSER=<name>    - Parser to use (default: docling)"
	@echo "  FORMAT=<fmt>     - Export format: markdown, text, json (default: markdown)"
	@echo "  RUN_ID=<id>      - Reuse a specific run directory"
	@echo ""
	@echo "Examples:"
	@echo "  make parse                          # docling → markdown"
	@echo "  make parse FORMAT=json              # docling → json"
	@echo "  make parse PARSER=olmocr            # olmOCR2 (needs vllm server on :8001)"
	@echo "  make parse PARSER=dots              # dots.ocr (needs vllm server on :8002)"
	@echo "  make embed cluster                  # full transform pipeline"
	@echo "  make embed RUN_ID=20240424-172522"

clean:
	rm -rf transform/output/runs transform/output/latest
