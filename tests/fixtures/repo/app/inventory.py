"""Tiny module to exercise basedpyright hovers, inlay hints and ruff."""

import json
from pathlib import Path


def load_pods(path: Path) -> list[dict]:
    """Read a `kubectl get pods -o json` dump and return its items."""
    data = json.loads(path.read_text())
    items = data.get("items", [])
    return items


def names(pods):
    return [p["metadata"]["name"] for p in pods]
