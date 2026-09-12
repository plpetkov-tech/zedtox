#!/usr/bin/env python3
"""End-to-end check of the generated yaml-language-server configuration.

Starts `yaml-language-server --stdio` with the YAML settings zedcfg builds (the
same ones Zed sends), opens the fixture files and checks, per file, which schema
applies (from hover's "Source:" link) and which diagnostics show up.

Needs yaml-language-server on PATH and network access (schemas come from
schemastore.org and raw.githubusercontent.com). Standard library only.

    python3 tests/lsp_smoke.py [-v]
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
FIXTURES = HERE / "fixtures" / "repo"
sys.path.insert(0, str(REPO))
import zedcfg  # noqa: E402

VERBOSE = "-v" in sys.argv
TIMEOUT = 90


class Client:
    def __init__(self, settings: dict):
        self.settings = settings
        self.proc = subprocess.Popen(
            [shutil.which("yaml-language-server") or "yaml-language-server", "--stdio"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        self.next_id = 0
        self.responses: dict[int, queue.Queue] = {}
        self.diagnostics: dict[str, list] = {}
        self.diag_event = threading.Condition()
        threading.Thread(target=self._read, daemon=True).start()

    # -- transport
    def _send(self, msg: dict) -> None:
        body = json.dumps(msg).encode()
        self.proc.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        self.proc.stdin.flush()

    def _read(self) -> None:
        out = self.proc.stdout
        while True:
            headers = {}
            while True:
                line = out.readline()
                if not line:
                    return
                line = line.decode().strip()
                if not line:
                    break
                k, _, v = line.partition(":")
                headers[k.lower()] = v.strip()
            msg = json.loads(out.read(int(headers["content-length"])))
            if "id" in msg and "method" in msg:
                self._send({"jsonrpc": "2.0", "id": msg["id"], "result": self._answer(msg)})
            elif "id" in msg:
                self.responses.setdefault(msg["id"], queue.Queue()).put(msg)
            elif msg.get("method") == "textDocument/publishDiagnostics":
                with self.diag_event:
                    self.diagnostics[msg["params"]["uri"]] = msg["params"]["diagnostics"]
                    self.diag_event.notify_all()

    def _answer(self, msg: dict):
        if msg["method"] == "workspace/configuration":
            sections = {"yaml": self.settings.get("yaml", {}), "editor": {"tabSize": 2}}
            return [sections.get(item.get("section"), None) for item in msg["params"]["items"]]
        return None

    def request(self, method: str, params: dict):
        self.next_id += 1
        rid = self.next_id
        q = self.responses.setdefault(rid, queue.Queue())
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        msg = q.get(timeout=TIMEOUT)
        if "error" in msg:
            raise RuntimeError(f"{method}: {msg['error']}")
        return msg.get("result")

    def notify(self, method: str, params: dict) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    # -- helpers
    def start(self, root: Path) -> None:
        self.request("initialize", {
            "processId": os.getpid(),
            "rootUri": root.as_uri(),
            "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}],
            "capabilities": {
                "workspace": {"configuration": True, "didChangeConfiguration": {"dynamicRegistration": True}},
                "textDocument": {
                    "hover": {"contentFormat": ["markdown", "plaintext"]},
                    "completion": {"completionItem": {"snippetSupport": True, "documentationFormat": ["markdown"]}},
                    "publishDiagnostics": {},
                },
            },
        })
        self.notify("initialized", {})
        self.notify("workspace/didChangeConfiguration", {"settings": self.settings})

    def open(self, path: Path, text: str | None = None) -> str:
        uri = path.as_uri()
        self.notify("textDocument/didOpen", {"textDocument": {
            "uri": uri, "languageId": "yaml", "version": 1, "text": text if text is not None else path.read_text()}})
        return uri

    def hover(self, uri: str, line: int, char: int, wait_for_schema: bool = False) -> str:
        """Hover text. With wait_for_schema, retry while schemas are still downloading."""
        deadline = time.time() + (TIMEOUT if wait_for_schema else 0)
        while True:
            result = self.request("textDocument/hover", {"textDocument": {"uri": uri}, "position": {"line": line, "character": char}})
            c = (result or {}).get("contents", "")
            text = c.get("value", "") if isinstance(c, dict) else (c if isinstance(c, str) else json.dumps(c))
            if "Source:" in text or time.time() > deadline:
                return text
            time.sleep(1)

    def settled_diagnostics(self, uri: str, text: str) -> list:
        """Re-validate once schemas are cached (after a hover), then wait for quiet."""
        self.notify("textDocument/didChange", {"textDocument": {"uri": uri, "version": 2}, "contentChanges": [{"text": text}]})
        deadline = time.time() + TIMEOUT
        last, last_change = None, time.time()
        while time.time() < deadline:
            with self.diag_event:
                self.diag_event.wait(timeout=0.5)
                current = self.diagnostics.get(uri)
            if current != last:
                last, last_change = current, time.time()
            elif current is not None and time.time() - last_change > 2.5:
                return current
        return last or []

    def completion(self, uri: str, line: int, char: int) -> list:
        result = self.request("textDocument/completion", {"textDocument": {"uri": uri}, "position": {"line": line, "character": char}})
        return result.get("items", []) if isinstance(result, dict) else (result or [])

    def stop(self) -> None:
        try:
            self.request("shutdown", {})
            self.notify("exit", {})
        except Exception:
            pass
        self.proc.kill()


def yamlls_version() -> tuple[int, ...]:
    """Version of the yaml-language-server on PATH, from its package.json."""
    exe = Path(os.path.realpath(shutil.which("yaml-language-server")))
    for parent in exe.parents:
        pkg = parent / "package.json"
        if pkg.is_file():
            data = json.loads(pkg.read_text())
            if data.get("name") == "yaml-language-server":
                return tuple(int(x) for x in data["version"].split("-")[0].split("."))
    return (0,)


# yaml-ls <= 1.24.0 can't auto-detect core-group kinds (apiVersion: v1 - Service,
# ConfigMap, Secret, ...) and falls back to the all-kinds schema, which reports
# this. Fixed upstream after 1.24.0; until then `space y a` pins those documents.
CORE_KIND_BUG = "Matches multiple schemas when only one must validate."
CORE_KIND_BUG_FIXED_IN = (1, 24, 1)


def position_of(text: str, needle: str, occurrence: int = 1) -> tuple[int, int]:
    for i, line in enumerate(text.splitlines()):
        col = line.find(needle)
        if col != -1:
            occurrence -= 1
            if occurrence == 0:
                return i, col + 1
    raise AssertionError(f"'{needle}' not in fixture")


# file, key to hover, expected schema-source fragment (None = no schema), expected error text (None = no errors)
# Built-in kinds resolve into yannh's _definitions.json, so their source is the yannh repo.
CASES = [
    ("k8s/deployment.yaml", "replicas", "yannh/kubernetes-json-schema", None),
    ("k8s/bad-deployment.yaml", "selector", "yannh/kubernetes-json-schema", "replicass"),
    ("k8s/virtualservice.yaml", "hosts", "networking.istio.io/virtualservice", None),
    ("k8s/bad-certificate.yaml", "secretName", "cert-manager.io/certificate", "issuerReff"),
    ("k8s/kustomization.yaml", "resources", "kustomization", None),
    ("k8s/chart/Chart.yaml", "appVersion", "chart", None),
    (".github/workflows/ci.yml", "runs-on", "github-workflow", None),
    (".github/workflows/bad.yml", "steps", "github-workflow", "runs_on"),
    ("docker-compose.yml", "services", "compose", None),
    ("other/random.yaml", "database", None, None),
]


def main() -> int:
    if not shutil.which("yaml-language-server"):
        print("yaml-language-server not on PATH", file=sys.stderr)
        return 2
    settings = zedcfg.build().settings["lsp"]["yaml-language-server"]["settings"]
    version = yamlls_version()
    core_bug = version < CORE_KIND_BUG_FIXED_IN
    print(f"yaml-language-server {'.'.join(map(str, version))}")
    client = Client(settings)
    client.start(FIXTURES)
    failures = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"  {'ok' if cond else 'FAIL'}  {name}" + (f"  ({detail})" if detail and (VERBOSE or not cond) else ""))
        failures += 0 if cond else 1

    try:
        for rel, key, schema, error in CASES:
            path = FIXTURES / rel
            text = path.read_text()
            uri = client.open(path)
            line, col = position_of(text, key)
            hover = client.hover(uri, line, col, wait_for_schema=bool(schema))
            diags = client.settled_diagnostics(uri, text)
            errors = [d["message"] for d in diags if d.get("severity", 1) == 1]
            if schema:
                check(f"{rel}: schema ~ {schema}", schema in hover, hover.replace("\n", " ")[:200])
            else:
                check(f"{rel}: no schema", "Source:" not in hover, hover.replace("\n", " ")[:200])
            if core_bug and errors and set(errors) == {CORE_KIND_BUG}:
                print(f"  --  {rel}: known yaml-ls <= 1.24.0 issue on core kinds ({CORE_KIND_BUG}); `space y a` fixes the file")
                errors = []
            if error:
                check(f"{rel}: error mentions '{error}'", any(error in m for m in errors), "; ".join(errors)[:300])
            else:
                check(f"{rel}: no errors", not errors, "; ".join(errors)[:300])

        # the `space y a` workaround: modelines pin every document to its exact schema
        sys.path.insert(0, str(REPO / "scripts"))
        import k8s_schema_annotate
        variables = zedcfg.build().variables
        text, _ = k8s_schema_annotate.annotate(
            (FIXTURES / "k8s/deployment.yaml").read_text(), variables["k8s_version"], variables["crd_store_url"], None)
        uri = client.open(FIXTURES / "k8s" / "_annotated.yaml", text)
        line, col = position_of(text, "selector", occurrence=2)  # the Service's selector
        hover = client.hover(uri, line, col, wait_for_schema=True)
        errors = [d["message"] for d in client.settled_diagnostics(uri, text) if d.get("severity", 1) == 1]
        check("annotated deployment.yaml (Deployment + Service): no errors", not errors, "; ".join(errors)[:300])
        check("annotated Service doc uses service-v1.json", "service-v1.json" in hover, hover.replace("\n", " ")[:200])

        # multi-document file: the 2nd document (a Service) is detected on its own
        path = FIXTURES / "k8s/deployment.yaml"
        line, col = position_of(path.read_text(), "ports", occurrence=2)
        hover = client.hover(path.as_uri(), line, col, wait_for_schema=True)
        check("k8s/deployment.yaml: 2nd doc (Service) gets Service docs", "Source:" in hover and "service" in hover.lower(),
              hover.replace("\n", " ")[:200])

        # completion inside a Deployment spec carries documentation
        text = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: x\nspec:\n  \n"
        uri = client.open(FIXTURES / "k8s" / "_completion.yaml", text)
        client.hover(uri, 4, 1, wait_for_schema=True)
        items = client.completion(uri, 5, 2)
        labels = {i["label"] for i in items}
        documented = [i for i in items if i.get("documentation")]
        check("completion under Deployment.spec offers replicas/selector/template",
              {"replicas", "selector", "template"} <= labels, ", ".join(sorted(labels))[:200])
        check("completion items carry documentation", len(documented) >= 3, f"{len(documented)} documented")

        # a modeline pointing at a locally extracted CRD schema (what `space y a` writes) wins
        with tempfile.TemporaryDirectory() as tmp:
            schema_path = Path(tmp) / "example.com" / "widget_v1.json"
            schema_path.parent.mkdir(parents=True)
            import crd_extract
            schema_path.write_text(json.dumps(crd_extract.to_json_schema(
                {"type": "object", "properties": {"spec": {"type": "object", "properties": {"size": {"type": "integer"}}}}},
                "example.com", "v1", "Widget", strict=True)))
            text = (f"# yaml-language-server: $schema={schema_path}\n"
                    "apiVersion: example.com/v1\nkind: Widget\nmetadata:\n  name: w\nspec:\n  size: big\n  colour: red\n")
            uri = client.open(Path(tmp) / "widget.yaml", text)
            client.hover(uri, 6, 3, wait_for_schema=True)
            errors = [d["message"] for d in client.settled_diagnostics(uri, text)]
            check("local CRD modeline: wrong type flagged", any("integer" in m.lower() for m in errors), "; ".join(errors))
            check("local CRD modeline: unknown key flagged", any("colour" in m for m in errors), "; ".join(errors))
    finally:
        client.stop()

    print(f"\n{'all checks passed' if not failures else f'{failures} check(s) failed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
