#!/usr/bin/env python3
"""Render or lint the Helm chart that contains a file.

  helm_render.py template <file>   render just this template (helm template --show-only)
  helm_render.py chart <file>      render the whole chart
  helm_render.py lint <file>       helm lint the chart

The chart root is found by walking up from <file> to the nearest Chart.yaml.
If <file> is a values*.yaml other than values.yaml, it's layered on with -f,
so you can preview an environment's overrides. Standard library only.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

RELEASE = "preview"


def chart_root(path: Path) -> Path | None:
    for directory in [path if path.is_dir() else path.parent, *path.parents]:
        if (directory / "Chart.yaml").is_file():
            return directory
    return None


def build_command(mode: str, file: Path, root: Path, helm: str = "helm") -> list[str]:
    rel = file.resolve().relative_to(root.resolve()).as_posix()
    values = []
    if file.name.startswith("values") and file.suffix in (".yaml", ".yml") and file.name != "values.yaml":
        values = ["-f", str(file)]
    if mode == "lint":
        return [helm, "lint", str(root), *values]
    cmd = [helm, "template", RELEASE, str(root), *values]
    renderable = rel.startswith("templates/") and file.suffix in (".yaml", ".yml") and not file.name.startswith("_")
    if mode == "template" and renderable:
        cmd += ["--show-only", rel]
    return cmd


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=["template", "chart", "lint"])
    p.add_argument("file", type=Path)
    p.add_argument("--helm", default="helm")
    args = p.parse_args()

    if not shutil.which(args.helm):
        print(f"{args.helm} not found on PATH", file=sys.stderr)
        return 1
    root = chart_root(args.file.resolve())
    if not root:
        print(f"no Chart.yaml above {args.file}", file=sys.stderr)
        return 1
    cmd = build_command(args.mode, args.file, root, args.helm)
    if args.mode == "template" and "--show-only" not in cmd:
        print(f"# {args.file.name} isn't a renderable template on its own; rendering the whole chart")
    print("$ " + " ".join(cmd), flush=True)
    result = subprocess.run(cmd)
    if result.returncode != 0 and not (root / "charts").is_dir() and "dependencies:" in (root / "Chart.yaml").read_text(encoding="utf-8"):
        print(f"\nhint: the chart has dependencies; run `helm dependency build {root}` first", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
