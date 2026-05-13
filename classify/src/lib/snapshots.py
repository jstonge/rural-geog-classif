"""Run snapshots — every classify run lands in classify/output/runs/{run_id}/
with everything you need to reproduce or score it later.

Files inside a snapshot directory:
  config.json        — control / schema / strategy / examples_used / max_tokens / ...
  prompt.md          — the FULL composed prompt (template + chosen examples) actually used
  predictions.parquet
  metrics.json       — written by validate.py after scoring (optional until then)
  gt.parquet         — the ground-truth used for scoring (optional)
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

RUNS_DIR = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/classify/output/runs")


def make_run_id(control: str, name: str) -> str:
    """Snapshot directory name: {YYYY-MM-DD}_{control}_{name}."""
    return f"{datetime.now():%Y-%m-%d}_{control}_{name}"


def save_classify_snapshot(run_id: str, *,
                           control: str,
                           config: dict,
                           prompt: str,
                           predictions: pd.DataFrame) -> Path:
    """Persist what `run_*.py` produces. Returns the snapshot directory path."""
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cfg = {**config, "control": control,
           "saved_at": datetime.now().isoformat(timespec="seconds")}
    (run_dir / "config.json").write_text(json.dumps(cfg, indent=2, default=str))
    (run_dir / "prompt.md").write_text(prompt)
    predictions.to_parquet(run_dir / "predictions.parquet")
    return run_dir


def save_validation(run_dir: Path, *, metrics: dict,
                    gt: pd.DataFrame | None = None) -> None:
    """Attach scoring artifacts to an existing snapshot."""
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    if gt is not None:
        gt.to_parquet(run_dir / "gt.parquet")


def load_snapshot(name_or_path: str | Path) -> dict:
    """Load a snapshot by directory name or path. Returns dict with all artifacts."""
    p = Path(name_or_path)
    if not p.is_absolute() and not p.exists():
        p = RUNS_DIR / name_or_path
    if not p.exists():
        available = sorted(d.name for d in RUNS_DIR.iterdir() if d.is_dir()) if RUNS_DIR.exists() else []
        hint = "\n  ".join(available) if available else "(none yet — run classify/src/run.py first)"
        raise FileNotFoundError(
            f"snapshot not found: {name_or_path}\n"
            f"available snapshots in {RUNS_DIR}:\n  {hint}"
        )
    out = {
        "path": p,
        "config":      json.loads((p / "config.json").read_text()),
        "prompt":      (p / "prompt.md").read_text(),
        "predictions": pd.read_parquet(p / "predictions.parquet"),
    }
    if (p / "metrics.json").exists():
        out["metrics"] = json.loads((p / "metrics.json").read_text())
    if (p / "gt.parquet").exists():
        out["gt"] = pd.read_parquet(p / "gt.parquet")
    return out


def list_snapshots(control: str | None = None) -> list[Path]:
    """List snapshot dirs, optionally filtered by control name in config."""
    if not RUNS_DIR.exists():
        return []
    out = []
    for d in sorted(RUNS_DIR.iterdir()):
        if not d.is_dir() or not (d / "config.json").exists():
            continue
        cfg = json.loads((d / "config.json").read_text())
        if control is None or cfg.get("control") == control:
            out.append(d)
    return out
