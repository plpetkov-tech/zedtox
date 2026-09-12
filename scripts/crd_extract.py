#!/usr/bin/env python3
"""Extract JSON schemas for the CRDs installed in a Kubernetes cluster.

Runs `kubectl get customresourcedefinitions -o json` (read-only) against your
current (or --context) kube context and writes, for every version that has a
schema:

    <out>/<group>/<kind>_<version>.json

That's the datree CRDs-catalog layout, so k8s_schema_annotate.py picks these up
before the public catalog. This replaces piping datree's crd-extractor.sh from
curl into bash: nothing is downloaded, and the output stays outside git (it
describes your cluster). Standard library only.
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path


def to_json_schema(openapi: dict, group: str, version: str, kind: str, strict: bool) -> dict:
    """Make a CRD's openAPIV3Schema usable as a standalone JSON schema.

    - apiVersion/kind are pinned with enums, so a typo'd group or kind is flagged.
    - strict: objects that list `properties` reject unknown keys, unless the CRD
      says x-kubernetes-preserve-unknown-fields or allows additionalProperties.
    - x-kubernetes-int-or-string becomes an explicit integer-or-string type.
    """
    schema = copy.deepcopy(openapi)

    def walk(node):
        if isinstance(node, dict):
            if node.get("x-kubernetes-int-or-string") and "type" not in node and "anyOf" not in node and "oneOf" not in node:
                node["oneOf"] = [{"type": "integer"}, {"type": "string"}]
            if (
                strict
                and "properties" in node
                and "additionalProperties" not in node
                and not node.get("x-kubernetes-preserve-unknown-fields")
            ):
                node["additionalProperties"] = False
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    props = schema.setdefault("properties", {})
    props["apiVersion"] = {**props.get("apiVersion", {"type": "string"}), "enum": [f"{group}/{version}"]}
    props["kind"] = {**props.get("kind", {"type": "string"}), "enum": [kind]}
    props.setdefault("metadata", {"type": "object"})
    return {"$schema": "http://json-schema.org/draft-07/schema#", "title": f"{kind} ({group}/{version})", **schema}


def crd_versions(crd: dict):
    """Yield (version, openAPIV3Schema) for apiextensions v1 (and legacy v1beta1) CRDs."""
    spec = crd.get("spec", {})
    legacy = spec.get("validation", {}).get("openAPIV3Schema")
    for v in spec.get("versions") or [{"name": spec.get("version")}]:
        schema = (v.get("schema") or {}).get("openAPIV3Schema") or legacy
        if v.get("name") and schema and v.get("served", True):
            yield v["name"], schema


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, required=True, help="output directory, e.g. ~/.local/share/zed-initiative/crds")
    p.add_argument("--context", help="kube context (default: current)")
    p.add_argument("--kubectl", default="kubectl")
    p.add_argument("--no-strict", action="store_true", help="don't reject unknown keys in objects")
    p.add_argument("--from-file", type=Path, help="read `kubectl get crd -o json` output from a file instead")
    args = p.parse_args()

    if args.from_file:
        raw = args.from_file.read_text(encoding="utf-8")
    else:
        if not shutil.which(args.kubectl):
            print(f"{args.kubectl} not found on PATH", file=sys.stderr)
            return 1
        cmd = [args.kubectl, "get", "customresourcedefinitions", "-o", "json"]
        if args.context:
            cmd[1:1] = ["--context", args.context]
        ctx = args.context or subprocess.run(
            [args.kubectl, "config", "current-context"], capture_output=True, text=True
        ).stdout.strip()
        print(f"reading CRDs from context: {ctx or '?'}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr.strip(), file=sys.stderr)
            return result.returncode
        raw = result.stdout

    items = json.loads(raw).get("items", [])
    out = args.out.expanduser()
    written = 0
    for crd in items:
        spec = crd.get("spec", {})
        group, kind = spec.get("group"), spec.get("names", {}).get("kind")
        if not group or not kind:
            continue
        for version, openapi in crd_versions(crd):
            schema = to_json_schema(openapi, group, version, kind, strict=not args.no_strict)
            path = out / group / f"{kind.lower()}_{version}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
            written += 1
    print(f"wrote {written} schemas for {len(items)} CRDs into {out}")
    print("next: `space y a` in a manifest uses them (local schemas win over the public catalog)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
