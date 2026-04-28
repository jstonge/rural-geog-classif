# Rural Geography Classification Pipeline
# =========================================
# Usage:
#   make embed          # SPECTER2 embeddings (GPU recommended)
#   make cluster        # EVoC clustering + viz.json
#   make sync-data      # copy latest viz.json into frontend
#   make frontend       # build static site
#   make all            # cluster → sync → build
#
#   make embed cluster  # full transform pipeline
#
# Run tracking:
#   Each embed/cluster invocation creates a timestamped run in
#   transform/output/runs/<id>/ with a meta.json. The "latest"
#   symlink always points to the most recent run.
#
#   To reuse a run ID:  make embed RUN_ID=20240424-172522

# --- Paths ---
WOS_CSV    := extract/input/Coded Rural Geog All 1986-2025 WoS List 4-7-2026(savedrecs).csv
SUMMARIES  := summarize/output/all_summaries_same_style.json
LATEST     := transform/output/latest

# Optional: pass RUN_ID=<id> to reuse a run directory
RUN_ARGS   := $(if $(RUN_ID),--run-id $(RUN_ID),)

.PHONY: all embed cluster sync-data frontend deploy clean help

all: frontend

# --- Extract ---
extract/output/openalex_works.json: $(WOS_CSV)
	python extract/src/fetch_openalex.py

# --- Parse ---
parse/output/markdown: extract/output/pdfs
	python parse/src/parse_pdfs.py extract/output/pdfs -o parse/output/markdown

# --- Transform ---
embed: $(SUMMARIES)
	cd transform/src && python embed.py \
	  ../../$(SUMMARIES) \
	  "../../$(WOS_CSV)" \
	  --device cuda \
	  $(RUN_ARGS)

cluster: $(LATEST)/embeddings.npy $(SUMMARIES)
	cd transform/src && python cluster.py \
	  ../../$(LATEST)/embeddings.npy \
	  ../../$(LATEST)/dois.json \
	  "../../$(WOS_CSV)" \
	  "../../$(WOS_CSV)" \
	  ../../$(SUMMARIES) \
	  $(RUN_ARGS)

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
	@echo "  embed       - Run SPECTER2 embeddings (needs GPU)"
	@echo "  cluster     - Run EVoC clustering"
	@echo "  sync-data   - Copy latest viz.json into frontend"
	@echo "  frontend    - Build static site"
	@echo "  deploy      - Build for deployment"
	@echo "  clean       - Remove all runs"
	@echo ""
	@echo "Options:"
	@echo "  RUN_ID=<id> - Reuse a specific run directory"
	@echo ""
	@echo "Examples:"
	@echo "  make embed cluster    # full transform pipeline"
	@echo "  make sync-data        # update frontend data"
	@echo "  make embed RUN_ID=20240424-172522"

clean:
	rm -rf transform/output/runs transform/output/latest
