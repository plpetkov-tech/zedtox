#!/usr/bin/env python3
"""Add yaml-language-server schema modelines to a Kubernetes YAML file.

For every YAML document (--- separated) that has a top-level apiVersion and kind,
insert (or update) as its first line:

    # yaml-language-server: $schema=<url>

The URL is chosen in this order:
  1. a locally extracted CRD schema:  <local-crds>/<group>/<kind>_<version>.json
     (see crd_extract.py; good for in-house CRDs)
  2. built-in Kubernetes kinds:        yannh/kubernetes-json-schema, <k8s-version>-standalone-strict
  3. everything else (CRDs):           <crd-store>/<group>/<kind>_<version>.json (datree catalog by default)

A modeline wins over every other schema association, so this is also the fix for
YAML outside the folders mapped to Kubernetes in config.jsonc.
Standard library only; makes no network requests.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

YANNH = "https://raw.githubusercontent.com/yannh/kubernetes-json-schema/master"
DATREE = "https://raw.githubusercontent.com/datreeio/CRDs-catalog/main"
MODELINE = "# yaml-language-server: $schema="
MODELINE_RE = re.compile(r"^\s*#\s*yaml-language-server:\s*\$schema=\S*\s*$")
DOC_SEP_RE = re.compile(r"^---(\s.*)?$")
TOP_KEY_RE = re.compile(r"^(apiVersion|kind):\s*(.*?)\s*$")

# API groups served by kube-apiserver itself; anything else is a CRD.
BUILTIN_GROUPS = {
    "", "admissionregistration.k8s.io", "apiregistration.k8s.io", "apps", "authentication.k8s.io",
    "authorization.k8s.io", "autoscaling", "batch", "certificates.k8s.io", "coordination.k8s.io",
    "discovery.k8s.io", "events.k8s.io", "flowcontrol.apiserver.k8s.io", "internal.apiserver.k8s.io",
    "networking.k8s.io", "node.k8s.io", "policy", "rbac.authorization.k8s.io", "resource.k8s.io",
    "scheduling.k8s.io", "storage.k8s.io", "storagemigration.k8s.io",
}
# Built-in, but no standalone schema file is published for it.
NO_STANDALONE = {("apiextensions.k8s.io", "customresourcedefinition")}


def scalar(value: str) -> str:
    """The plain value of a one-line YAML scalar: strip a trailing comment and quotes."""
    value = re.sub(r"\s+#.*$", "", value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    return value


def schema_url(api_version: str, kind: str, k8s_version: str, crd_store: str, local_crds: Path | None) -> tuple[str | None, str]:
    """Return (url, source) for a GVK; url is None when nothing sensible exists."""
    group, _, version = api_version.rpartition("/")
    kind_l = kind.lower()
    if local_crds:
        local = local_crds / group / f"{kind_l}_{version}.json"
        if group and local.is_file():
            return str(local.resolve()), "local CRD"
    if (group, kind_l) in NO_STANDALONE:
        return None, "built-in kind without a published standalone schema (the folder mapping validates it)"
    if group in BUILTIN_GROUPS:
        # yannh names files <kind>[-<first part of the group>]-<version>.json
        ver = k8s_version if k8s_version.startswith("v") else f"v{k8s_version}"
        name = f"{kind_l}-{version}.json" if not group else f"{kind_l}-{group.split('.')[0]}-{version}.json"
        return f"{YANNH}/{ver}-standalone-strict/{name}", "kubernetes"
    return f"{crd_store.rstrip('/')}/{group}/{kind_l}_{version}.json", "CRD catalog"


def split_documents(lines: list[str]) -> list[tuple[int, int]]:
    """(start, end) line ranges of each YAML document, separators excluded."""
    docs, start = [], 0
    for i, line in enumerate(lines):
        if DOC_SEP_RE.match(line.rstrip("\r\n")):
            docs.append((start, i))
            start = i + 1
    docs.append((start, len(lines)))
    return [(s, e) for s, e in docs if any(l.strip() and not l.lstrip().startswith("#") for l in lines[s:e])]


def annotate(text: str, k8s_version: str, crd_store: str, local_crds: Path | None) -> tuple[str, list[str]]:
    lines = text.splitlines(keepends=True)
    newline = "\r\n" if text.count("\r\n") > text.count("\n") / 2 else "\n"
    report, edits = [], []  # edits: (line index, replace?, new line)
    for n, (start, end) in enumerate(split_documents(lines), 1):
        gvk = {}
        for line in lines[start:end]:
            m = TOP_KEY_RE.match(line.rstrip("\r\n"))
            if m and m.group(1) not in gvk:
                gvk[m.group(1)] = scalar(m.group(2))
        api_version, kind = gvk.get("apiVersion", ""), gvk.get("kind", "")
        if not api_version or not kind or "{{" in api_version + kind:
            report.append(f"doc {n}: skipped (no plain apiVersion/kind)")
            continue
        url, source = schema_url(api_version, kind, k8s_version, crd_store, local_crds)
        if not url:
            report.append(f"doc {n}: {api_version} {kind}: skipped ({source})")
            continue
        existing = next((i for i in range(start, end) if MODELINE_RE.match(lines[i])), None)
        new_line = f"{MODELINE}{url}{newline}"
        if existing is not None:
            if lines[existing].strip() == new_line.strip():
                report.append(f"doc {n}: {api_version} {kind}: already annotated")
                continue
            edits.append((existing, True, new_line))
        else:
            edits.append((start, False, new_line))
        report.append(f"doc {n}: {api_version} {kind} -> {url} ({source})")
    for index, replace, new_line in sorted(edits, reverse=True):
        if replace:
            lines[index] = new_line
        else:
            lines.insert(index, new_line)
    return "".join(lines), report


def yaml_files(root: Path):
    """Every YAML file under a directory worth annotating.

    Skips VCS/vendor directories and Helm charts: templates are Go templates
    (helm_ls handles them) and their values files aren't manifests.
    """
    skip_dirs = {".git", ".svn", "node_modules", ".venv", "venv", "__pycache__", "templates", "charts"}
    for path in sorted(root.rglob("*")):
        if path.suffix in (".yaml", ".yml") and not any(part in skip_dirs for part in path.relative_to(root).parts):
            yield path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", type=Path, help="a .yaml/.yml file, or a directory to walk")
    p.add_argument("--k8s-version", default="1.33.2")
    p.add_argument("--crd-store", default=DATREE)
    p.add_argument("--local-crds", type=Path, default=None, help="directory written by crd_extract.py")
    p.add_argument("--dry-run", action="store_true", help="print the result instead of writing the file")
    args = p.parse_args()

    if args.file.is_dir():
        changed = 0
        for path in yaml_files(args.file):
            text = path.read_text(encoding="utf-8")
            new_text, report = annotate(text, args.k8s_version, args.crd_store, args.local_crds)
            if new_text == text:
                continue
            rel = path.relative_to(args.file)
            print(f"{rel}: " + "; ".join(r for r in report if "skipped" not in r and "already" not in r))
            if not args.dry_run:
                path.write_text(new_text, encoding="utf-8")
            changed += 1
        verb = "would annotate" if args.dry_run else "annotated"
        print(f"{verb} {changed} file(s) under {args.file}"
              + ("" if changed else " (nothing to do: already annotated, or no Kubernetes manifests)"))
        return 0

    if args.file.suffix not in (".yaml", ".yml"):
        print(f"{args.file}: not a .yaml/.yml file or a directory", file=sys.stderr)
        return 1
    text = args.file.read_text(encoding="utf-8")
    new_text, report = annotate(text, args.k8s_version, args.crd_store, args.local_crds)
    for line in report:
        print(line)
    if args.dry_run:
        sys.stdout.write(new_text)
    elif new_text != text:
        args.file.write_text(new_text, encoding="utf-8")
        print(f"updated {args.file}")
    else:
        print("nothing to change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
