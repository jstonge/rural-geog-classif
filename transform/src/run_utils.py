"""Lightweight filesystem-based run tracking (wandb-style)."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RUNS_DIR = Path(__file__).resolve().parent.parent / "output" / "runs"


def get_git_commit() -> str:
    """Return short git commit hash, or 'unknown' if not in a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def get_git_dirty() -> bool:
    """Return True if the working tree has uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def init_run(
    script: str,
    params: dict,
    run_id: str | None = None,
    runs_dir: Path | None = None,
) -> Path:
    """Create a new run directory and write meta.json.

    Parameters
    ----------
    script : str
        Name of the script (e.g., "embed.py" or "cluster.py").
    params : dict
        The parsed CLI arguments to record.
    run_id : str | None
        Optional explicit run ID. If None, generates from timestamp.
    runs_dir : Path | None
        Override the default runs directory.

    Returns
    -------
    Path
        The created run directory.
    """
    if runs_dir is None:
        runs_dir = RUNS_DIR

    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")

    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "run_id": run_id,
        "script": script,
        "timestamp": datetime.now().isoformat(),
        "git_commit": get_git_commit(),
        "git_dirty": get_git_dirty(),
        "params": params,
        "python_version": sys.version,
        "status": "running",
    }

    meta_path = run_dir / "meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            existing = json.load(f)
        if "steps" not in existing:
            existing["steps"] = [{
                "script": existing.pop("script"),
                "timestamp": existing.pop("timestamp"),
                "params": existing.pop("params"),
                "status": existing.pop("status"),
            }]
        existing["steps"].append({
            "script": script,
            "timestamp": meta["timestamp"],
            "params": params,
            "status": "running",
        })
        meta = existing

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)

    print(f"[run_utils] Started run {run_id} in {run_dir}")
    return run_dir


def finish_run(run_dir: Path, outputs: list[str] | None = None):
    """Mark a run as completed and update the latest symlink."""
    meta_path = run_dir / "meta.json"
    with open(meta_path) as f:
        meta = json.load(f)

    if "steps" in meta:
        meta["steps"][-1]["status"] = "completed"
        if outputs:
            meta["steps"][-1]["outputs"] = outputs
    else:
        meta["status"] = "completed"
        if outputs:
            meta["outputs"] = outputs

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)

    latest = run_dir.parent.parent / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(run_dir.resolve())

    print(f"[run_utils] Finished run {run_dir.name} -> latest")


def add_run_args(parser):
    """Add --run-id argument to an argparse parser."""
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Explicit run ID. If omitted, a new timestamped run is created.",
    )


def params_from_args(args, exclude=("output", "run_id")) -> dict:
    """Convert argparse Namespace to a serializable dict."""
    return {
        k: str(v) if isinstance(v, Path) else v
        for k, v in vars(args).items()
        if k not in exclude
    }
