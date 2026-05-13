"""Side-by-side comparison of validated snapshots.

Usage:
    python classify/src/compare_runs.py <run1> <run2> [<run3> ...]
    python classify/src/compare_runs.py --control methods    # all methods runs
"""
from __future__ import annotations

import argparse

from lib.snapshots import list_snapshots, load_snapshot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*", help="Snapshot names or paths.")
    ap.add_argument("--control", default=None,
                    help="If set, ignore positional args and compare all snapshots for this control.")
    args = ap.parse_args()

    if args.control:
        paths = list_snapshots(control=args.control)
    else:
        paths = [load_snapshot(r)["path"] for r in args.runs]
    if not paths:
        print("No snapshots to compare.")
        return

    rows = []
    for p in paths:
        snap = load_snapshot(p)
        cfg = snap["config"]
        metrics = snap.get("metrics", {})
        rows.append({
            "run":         p.name,
            "control":     cfg.get("control"),
            "schema":      cfg.get("schema", "-"),
            "strategy":    cfg.get("strategy", "-"),
            "n_examples":  len(cfg.get("examples_used") or []) if cfg.get("examples_used") else "-",
            "n_with_gt":   metrics.get("n_total", "-"),
            "exact":       _pct(metrics.get("exact_match")),
            "jaccard":     _fmt(metrics.get("mean_jaccard")),
        })

    cols = ["run", "control", "schema", "strategy", "n_examples", "n_with_gt", "exact", "jaccard"]
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}

    def line(values):
        return "  ".join(f"{str(v):<{widths[c]}}" for c, v in zip(cols, values))

    print(line(cols))
    print(line(["-" * widths[c] for c in cols]))
    for r in rows:
        print(line([r[c] for c in cols]))


def _pct(v):
    return f"{v:.1%}" if isinstance(v, (int, float)) else "-"


def _fmt(v, n=3):
    return f"{v:.{n}f}" if isinstance(v, (int, float)) else "-"


if __name__ == "__main__":
    main()
