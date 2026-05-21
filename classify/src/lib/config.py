"""YAML config support for run_*.py / validate_*.py scripts.

Convention: if `--config path.yaml` is given on the CLI, every key in the YAML
that matches an argparse attribute overrides the CLI default. CLI flags set on
the same invocation still take precedence over YAML — but the simplest pattern
is to use one OR the other, not mix.

Path-valued fields in YAML can be plain strings; this helper converts them back
to Path objects if the existing argparse value was a Path.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def merge_yaml_into_args(args: argparse.Namespace,
                          yaml_path: Path | str | None,
                          parser: argparse.ArgumentParser | None = None
                          ) -> argparse.Namespace:
    """Apply YAML keys to argparse args, but only when the CLI value still matches
    the parser's default — that way explicit CLI flags override YAML, as the
    docstring on this module promises. Pass `parser` so we can read defaults; if
    omitted, YAML overrides everything (old behavior, for back-compat)."""
    if yaml_path is None:
        return args
    cfg = yaml.safe_load(Path(yaml_path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError(f"expected a top-level dict in {yaml_path}; got {type(cfg).__name__}")
    defaults = parser.parse_args([]) if parser is not None else None
    for k, v in cfg.items():
        if not hasattr(args, k):
            print(f"  config: ignoring unknown key {k!r}")
            continue
        if defaults is not None and getattr(args, k) != getattr(defaults, k, object()):
            # User passed this on the CLI — don't let YAML clobber.
            continue
        current = getattr(args, k)
        if isinstance(current, Path) and isinstance(v, str):
            v = Path(v)
        setattr(args, k, v)
    return args
