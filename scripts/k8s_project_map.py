#!/usr/bin/env python3
"""Find a repo's Kubernetes manifests by content and map their folders for the project.

yaml-language-server decides whether a YAML file gets the Kubernetes schema from
glob patterns, not from the file's content. In a monorepo that means either
editing every file or guessing folder names.

This walks a worktree, finds the YAML files that actually *are* manifests (a
top-level apiVersion + kind, no Go templating), and writes their folders into
<worktree>/.zed/settings.json. After that, every manifest in those folders is
validated automatically, on every branch, for anyone who opens the repo.

Run it once per repo (and again after a big restructure). Standard library only;
no network. The Zed worktree has to be trusted for project settings to apply.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", ".svn", ".hg", ".jj", "node_modules", "vendor", ".venv", "venv", "__pycache__",
    ".terraform", ".idea", ".vscode", "dist", "build", "target", ".github", ".gitlab",
}
# Helm charts render these; helm_ls owns them.
SKIP_NAMES = re.compile(r"^(Chart|Chart\.lock|values.*|helmfile.*|skaffold.*|docker-compose.*|compose.*)$")
APIVERSION = re.compile(r"^apiVersion:\s*\S", re.M)
KIND = re.compile(r"^kind:\s*\S", re.M)
DEFAULT_SKIP = "!(Chart|kustomization|values|helmfile|skaffold|docker-compose|compose|.gitlab-ci|.pre-commit)"


def is_manifest(path: Path, max_bytes: int = 8192) -> bool:
    """True when the file's first documents look like plain Kubernetes YAML."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            head = f.read(max_bytes)
    except OSError:
        return False
    if "{{" in head:  # Go templating: a Helm template, not a plain manifest
        return False
    return bool(APIVERSION.search(head) and KIND.search(head))


def manifest_dirs(root: Path) -> tuple[set[Path], int]:
    """Directories (relative to root) holding manifests, and how many were found."""
    dirs: set[Path] = set()
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        if (here / "Chart.yaml").is_file():  # a Helm chart: templates/ and values are not manifests
            dirnames[:] = [d for d in dirnames if d != "templates"]
        for name in filenames:
            if not name.endswith((".yaml", ".yml")) or SKIP_NAMES.match(Path(name).stem):
                continue
            if is_manifest(here / name):
                dirs.add(here.relative_to(root))
                count += 1
                break  # one hit is enough to map the folder
    return dirs, count


def collapse(dirs: set[Path]) -> list[Path]:
    """Drop directories already covered by an ancestor in the set."""
    out = []
    for d in sorted(dirs, key=lambda p: len(p.parts)):
        if not any(parent in dirs for parent in d.parents if parent != Path(".")):
            out.append(d)
    return out


def pattern_for(directory: Path, skip: str) -> str:
    prefix = "" if directory == Path(".") else f"{directory.as_posix()}/"
    return f"{prefix}**/{skip}.y?(a)ml"


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    try:  # project settings are JSONC; reuse zedcfg's reader when available
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        import zedcfg
        return zedcfg.parse_jsonc(text, str(path))
    except Exception:
        return json.loads(text)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("worktree", type=Path, nargs="?", default=Path.cwd())
    p.add_argument("--skip", default=DEFAULT_SKIP, help="extglob of file names that keep their own schema")
    p.add_argument("--defaults-from", type=Path, help="settings.json whose kubernetes globs are kept as a baseline")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    root = args.worktree.resolve()
    if not root.is_dir():
        print(f"{root}: not a directory", file=sys.stderr)
        return 1

    dirs, found = manifest_dirs(root)
    if not found:
        print(f"no Kubernetes manifests found under {root}")
        return 0
    patterns = [pattern_for(d, args.skip) for d in collapse(dirs)]

    settings_path = root / ".zed" / "settings.json"
    settings = load_json(settings_path)
    yaml_settings = (settings.setdefault("lsp", {}).setdefault("yaml-language-server", {})
                     .setdefault("settings", {}).setdefault("yaml", {}))
    schemas = yaml_settings.setdefault("schemas", {})
    existing = schemas.get("kubernetes", [])
    existing = [existing] if isinstance(existing, str) else list(existing)

    baseline: list[str] = []
    if args.defaults_from and args.defaults_from.is_file():
        # Project settings replace the user's list for this worktree, so carry it over.
        defaults = load_json(args.defaults_from)
        value = (defaults.get("lsp", {}).get("yaml-language-server", {}).get("settings", {})
                 .get("yaml", {}).get("schemas", {}).get("kubernetes", []))
        baseline = [value] if isinstance(value, str) else list(value)

    merged = list(dict.fromkeys(baseline + existing + patterns))
    added = [p for p in patterns if p not in baseline + existing]
    schemas["kubernetes"] = merged

    print(f"{found} manifest file(s) in {len(patterns)} folder(s) under {root.name}:")
    for pattern in patterns:
        print(f"  {'+' if pattern in added else ' '} {pattern}")
    if not added:
        print("\nalready covered; nothing to write")
        return 0
    if args.dry_run:
        print(f"\nwould write {settings_path}")
        return 0

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {settings_path} ({len(added)} new pattern(s))")
    print("commit it so the whole team gets validation; the worktree must be trusted for it to apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
