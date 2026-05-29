# Project layout

A map of how the repo is organized, and an honest reflection on whether
that organization is the right one. Companion to
[`methods.md`](methods.md) (what the project does),
[`prompt_anatonomy.md`](prompt_anatonomy.md) (the classifier's prompt
artifacts), and [`ground_truth.md`](ground_truth.md) (the epistemic
framing of the loop).

## The tree

```
.
├── extract/                 # acquire WoS records + PDF DOIs
│   ├── input/               #   raw WoS CSV exports
│   ├── src/                 #   fetch_openalex.py, parse_csv.py, pdf_to_dois.py
│   └── output/              #   fetched OpenAlex metadata
├── parse/                   # PDF → markdown
│   ├── src/                 #   parse_pdfs.py (docling), parse_pdfs_granite.py
│   ├── dots.ocr/            #   vendored alternative parser (whole repo)
│   └── output/              #   docling/<doi>.md, olmocr/<doi>.md, dots/<doi>.md
├── summarize/               # paper-level summaries (experimental, sparse)
│   ├── src/                 #   gemma4_test.ipynb
│   └── output/              #   all_summaries_same_style.json
├── transform/               # embed + cluster + topic modeling + annotation tooling
│   ├── src/                 #   embed.py (SPECTER2), cluster.py (EVoC),
│   │                        #   bertopic.ipynb, migrate_v1_to_v3.py,
│   │                        #   align_annotations.py, upload_to_labelstudio.py,
│   │                        #   export_annotations.py
│   └── output/runs/<id>/    #   timestamped runs w/ meta.json + symlinked `latest`
├── classify/                # THE classification loop (focus of methods.md)
│   ├── schemas/
│   │   ├── prompts/
│   │   │   ├── v1/          #   original prompt set
│   │   │   ├── v3/          #   current prompt set
│   │   │   │   ├── core/{task}_{NN}.md
│   │   │   │   ├── categories/{task}_{NN}.csv
│   │   │   │   ├── examples/{task}_{NN}.md
│   │   │   │   └── schema.xml      # Label Studio labeling config
│   │   │   └── shared/             # picker.md, picker_intro.md (cross-task)
│   │   └── mappings/v1_to_v3.json  # label renames across schema versions
│   ├── experiments/         # YAML configs — one per named experiment
│   ├── src/
│   │   ├── run.py           # entry point
│   │   ├── classify.py      # vLLM call wrapper
│   │   ├── prompt_builder.py
│   │   ├── input_strategies.py
│   │   ├── score.py
│   │   ├── validate.py
│   │   ├── rebuild_runs_index.py
│   │   ├── export_compare.py
│   │   ├── push_intro_to_ls.py        ┐
│   │   ├── push_sections_to_ls.py     │ Label Studio plumbing
│   │   ├── push_predictions_as_annotations.py │   (data flowing INTO LS)
│   │   ├── import_predictions_to_ls.py        │
│   │   ├── ls_backup.py                       ┘
│   │   ├── export_locations_viz.py    ┐
│   │   ├── export_methods_viz.py      │ frontend feeders
│   │   ├── compare_runs.py            │   (data flowing OUT of classify)
│   │   ├── build_xml.py               ┘
│   │   └── lib/             # config / llm / snapshots / tasks / wos /
│   │                        # intro_outline / annotations
│   └── output/
│       ├── runs/<id>/       # snapshot bundles: config + prompt + preds + metrics + gt
│       ├── ls_backups/      # Label Studio export dumps (timestamped)
│       └── picker_cache.parquet
├── frontend/                # SvelteKit dashboard
│   ├── src/
│   │   ├── lib/             # shared utils + data JSON (synced from classify/output)
│   │   └── routes/          # /runs, /compare, /prompts, /annotations, /about
│   └── build/               # static build output
├── docs/                    # methods.md, changelog.md, prompt_anatonomy.md,
│                            # ground_truth.md, project_layout.md (this file)
├── tests/                   # sparse — needs filling out
├── Makefile                 # the only place stage interconnections are declared
├── README.md
├── pyproject.toml, uv.lock  # one venv covers most stages
├── status.csv, status.py    # project tracking (manual)
└── diag.txt
```

## The organizing principle

The layout follows **Patrick Ball's Principled Data Processing (PDP)**
convention from HRDAG ([talk](https://www.youtube.com/watch?v=ZSunU9GQdcI),
[pdpp tool](https://pypi.org/project/pdpp/)). The core ideas:

- Each top-level folder is a **discrete data-processing task**:
  self-contained, self-documenting, kept as small as is reasonable so
  the operation it performs and the test for whether it succeeded are
  both obvious.
- Each task owns the same three sub-folders: **`src/`** for code,
  **`input/`** for external data the task consumes but did not
  generate (in `pdpp` parlance: `import/`), and **`output/`** for the
  artifacts the task produces.
- Tasks compose by reading from each other's `output/`. The
  `Makefile` at the project root is the only place this composition is
  declared — no task knows another task's internals, only its output
  file paths.
- Hand-curated data (annotations, manual fixes) lives in a `hand/`
  subfolder, distinguished from workflow-generated inputs so a reader
  can immediately tell which artifacts came from a human and which
  from a previous task.

The stage names mirror the ETL vocabulary directly: `extract/` is the
*E*, `parse/` and `transform/` cover the *T*, `classify/` is the
project-specific analytical stage, and `frontend/` is the *L* (load,
in the sense of materializing the results for human consumption).

```
extract  →  parse  →  (summarize)  →  transform  →  classify  →  frontend
   PDFs       md       summaries       embeddings    metrics      dashboard
              ↑                         clusters     snapshots
              │                         annotation
              │                         alignment
              └─ also feeds → classify (via input strategies)
```

## Where this shape works well

- **A new contributor can locate "where does X live?" by task name.**
  PDF parsing → `parse/`. The classification loop → `classify/`. Adding
  a new input strategy → `classify/src/input_strategies.py`. There's no
  package hierarchy to memorize.
- **Inter-task contracts are file paths, not imports.** classify reads
  `parse/output/docling/<doi>.md` as a file, not as an imported module.
  This means classify can be rerun while parse is broken, and vice
  versa — boundaries are observable on disk, which is exactly the
  property PDP is designed to produce.
- **Each task's outputs are isolated.** Running classify won't trample
  on transform's clustering runs. The timestamped-runs convention
  (`classify/output/runs/<id>/`, `transform/output/runs/<id>/`) means
  you can keep months of historical state without it polluting the
  current working set.
- **Hand vs workflow inputs are distinguished by folder.** `extract/hand/`
  vs `extract/input/` makes it obvious which artifacts a human supplied
  directly. A reader doesn't have to git-blame to find out.
- **The classify task has the depth it deserves.** The prompt
  anatomy maps directly onto folders (`schemas/prompts/v3/{core,categories,examples}/`),
  named experiments are first-class artifacts in `experiments/`, and
  snapshot bundles in `output/runs/` carry everything needed to
  reproduce a result.
- **One Python env covers most of it (`uv.lock`, `pyproject.toml`).**
  Cross-task scripts (e.g. `push_intro_to_ls.py` reading both docling
  output and the WoS df) don't need package install gymnastics.

## Where it strains

Places where the project diverges from a strict PDP reading, in ways
worth knowing about:

- **`classify/` and `transform/` are bigger than a PDP "task" should
  be.** Ball's framework wants tasks small enough that "what does this
  do, and did it work?" is obvious at a glance. `classify/` does
  prompt assembly, vLLM calls, picker calls, snapshot writing,
  scoring, run-index rebuilding, viz exports, and LS pushes — at least
  five tasks crammed into one folder. `transform/` is similar (embed,
  cluster, bertopic, schema migration, annotation alignment, LS
  upload). A purist refactor would split each of these into its own
  task folder (e.g. `classify-prompt/`, `classify-run/`,
  `classify-score/`, `classify-export/`). Whether that purity is worth
  the navigation overhead is a judgment call — the current shape
  trades PDP granularity for the practical convenience of "everything
  about the classifier in one place."
- **Annotation infrastructure is split across `classify/` and
  `transform/`.** `classify/src/push_*_to_ls.py` and
  `transform/src/upload_to_labelstudio.py` /
  `export_annotations.py` are doing related things — pushing data to
  / pulling data from Label Studio. Under PDP this is clearly its own
  task: a peer `annotations/` (or `labelstudio/`) folder would absorb
  both, with its own `input/`, `src/`, `output/`, and a `hand/` for
  any manual review notes. This is the strongest restructure
  candidate.
- **`summarize/` is a stub task.** Just a notebook. PDP says tasks
  should be discrete; an empty-shell task is a tell that either the
  task should be deleted or its scope should be fleshed out.
- **Vendored `parse/dots.ocr/` is enormous.** A whole upstream repo
  including its `.git` directory, model code, demo assets, docker
  files. Should be a git submodule or shallow-cloned, not committed in
  full. (Orthogonal to PDP — just hygiene.)
- **`classify/schemas/mappings/v1_to_v3.json` is isolated.** A tiny
  folder for one file. Worth co-locating with the schemas it bridges
  (e.g. `classify/schemas/prompts/v3/from_v1.json`) — or letting the
  folder grow as more inter-version artifacts appear.
- **`status.csv` / `status.py` / `diag.txt` sit at the project root.**
  Project-management artifacts at the top level make the root feel
  cluttered. Under PDP these'd typically live in their own `tracking/`
  task or under `docs/`. Minor.
- **`tests/` is sparse.** For a system whose epistemic claim rests on
  `prompt_builder.py` producing the prompt the experimenter intended,
  the absence of unit tests on the assembler — especially around the
  placeholder gotchas documented in `prompt_anatonomy.md` — is a real
  hole. PDP doesn't say much about testing one way or the other, but
  "self-documenting tasks" implicitly assumes tests exist to verify
  the task did what it claimed.

## Where PDP is genuinely weak for this project

PDP is designed for projects whose data flow is *acyclic* — extract
once, transform once, load once. Two places this project already
breaks that assumption:

1. **The Label Studio annotation loop is genuinely cyclic.** Annotators
   produce GT → classify produces predictions → comparison surfaces
   disagreements → annotators revise GT. Under PDP, each cycle would
   be a new task folder, but the cycle here is continuous (the
   most-recent-wins GT loader exists precisely to keep the loop
   tight). Splitting LS-push and LS-pull into separate tasks would
   make the *file* contracts cleaner but lose the conceptual coherence
   of the loop. The compromise — annotation tooling scattered across
   `classify/` and `transform/` — is the current pain point flagged
   above.
2. **The frontend is a consumer of every task's output, not just the
   last one.** It reads `classify/output/runs/`, transform-side
   annotation exports, and clustering results. A `make sync-data`
   target makes this work, but the n-to-1 fan-in is invisible from the
   tree alone. PDP doesn't have a clean idiom for "this task depends
   on all upstream tasks' outputs"; a dependency manifest
   (`frontend/data_contracts.md` or similar) would surface it
   explicitly.

Neither is acute enough to force a reorg today. The right triggers:

- **Annotations gets a third caller** beyond classify and transform
  (e.g. a separate adjudication tool) → factor `annotations/` as a
  peer task.
- **Frontend grows a second-stage backend** (not just static-data
  syncing) → write the data-contracts manifest.

## Summary

PDP — task-per-folder, `src/input/output/hand`, file-path contracts,
Makefile orchestration — is a good fit for this project. The places it
strains are the places PDP is theoretically known to strain: cyclic
flows (the annotation loop) and many-to-one fan-in (the frontend
consuming every task). Worth knowing about; not worth restructuring
around until those concerns grow another caller.

## Sources

- [Patrick Ball — Principled Data Processing (HRDAG)](https://hrdag.org/author/pball/)
- [Principled Data Processing: talk recording](https://www.youtube.com/watch?v=ZSunU9GQdcI)
- [pdpp (Python implementation), NetLab Waterloo](https://uwaterloo.ca/networks-lab/projects/pdpp-principled-data-processing-python)
- [pdpp on PyPI](https://pypi.org/project/pdpp/)
