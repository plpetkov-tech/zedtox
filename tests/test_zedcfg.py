"""Unit tests for zedcfg.py and the helper scripts. Standard library only.

    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO), str(REPO / "scripts")]

import crd_extract  # noqa: E402
import helm_render  # noqa: E402
import k8s_schema_annotate as annotate_mod  # noqa: E402
import zedcfg  # noqa: E402


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


class JsoncTest(unittest.TestCase):
    def test_comments_and_trailing_commas(self):
        text = '{\n  // line\n  "a": 1, /* block */\n  "b": [1, 2,],\n}\n'
        self.assertEqual(zedcfg.parse_jsonc(text), {"a": 1, "b": [1, 2]})

    def test_comment_markers_inside_strings_survive(self):
        text = '{"url": "https://x/y", "g": "a/*b*/c", "q": "say \\"hi\\" // not a comment", "c": ",}"}'
        self.assertEqual(
            zedcfg.parse_jsonc(text),
            {"url": "https://x/y", "g": "a/*b*/c", "q": 'say "hi" // not a comment', "c": ",}"},
        )

    def test_errors_keep_line_numbers(self):
        text = '{\n/* one\n two\n*/\n"a": 1\n"b": 2\n}'
        with self.assertRaisesRegex(ValueError, "line 6"):
            zedcfg.parse_jsonc(text)


class MergeTest(unittest.TestCase):
    def test_deep_merge_and_list_append(self):
        m = zedcfg.Merger()
        base = m.merge({}, {"a": {"x": 1}, "l": [1, 2]}, "core")
        m.merge(base, {"a": {"y": 2}, "l": [2, 3]}, "p1")
        self.assertEqual(base, {"a": {"x": 1, "y": 2}, "l": [1, 2, 3]})
        self.assertEqual(m.warnings, [])

    def test_replace_marker(self):
        m = zedcfg.Merger()
        base = m.merge({}, {"langs": {"Python": {"servers": ["a", "b"]}}}, "p1")
        m.merge(base, {"langs": {"Python": {"servers": {"$replace": ["c"]}}}}, "local")
        self.assertEqual(base["langs"]["Python"]["servers"], ["c"])
        m.merge(base, {"new": {"$replace": {"k": 1}}}, "p2")
        self.assertEqual(base["new"], {"k": 1})

    def test_pack_conflict_warns_but_core_and_local_do_not(self):
        m = zedcfg.Merger()
        base = m.merge({}, {"tab": 4}, "core")
        m.merge(base, {"tab": 2}, "yaml")
        self.assertEqual(m.warnings, [])
        m.merge(base, {"tab": 8}, "helm")
        self.assertEqual(len(m.warnings), 1)
        self.assertIn("'helm' overrides pack 'yaml'", m.warnings[0])
        m.merge(base, {"tab": 3}, "local")
        self.assertEqual(len(m.warnings), 1)
        self.assertEqual(base["tab"], 3)

    def test_merge_does_not_alias_inputs(self):
        pack = {"l": [{"k": 1}], "d": {"x": [1]}}
        m = zedcfg.Merger()
        base = m.merge({}, pack, "p")
        base["l"].append("z")
        base["d"]["x"].append(2)
        self.assertEqual(pack, {"l": [{"k": 1}], "d": {"x": [1]}})


class SubstituteTest(unittest.TestCase):
    V = {"ver": "1.33.2", "globs": ["a/**", "b/**"], "extra": [], "skip": "!(Chart)", "nested": ["x/${skip}.yaml"]}

    def test_inline_full_and_splice(self):
        out = zedcfg.substitute({"k": "v${ver}", "g": "${globs}", "l": ["${globs}", "${extra}", "c"]}, self.V)
        self.assertEqual(out, {"k": "v1.33.2", "g": ["a/**", "b/**"], "l": ["a/**", "b/**", "c"]})

    def test_nested_variables(self):
        self.assertEqual(zedcfg.substitute(["${nested}"], self.V), ["x/!(Chart).yaml"])

    def test_zed_and_snippet_variables_are_left_alone(self):
        text = "$ZED_FILE ${ZED_WORKTREE_ROOT} ${1:default} $0"
        self.assertEqual(zedcfg.substitute(text, self.V), text)

    def test_unknown_and_cyclic_variables_fail(self):
        with self.assertRaises(SystemExit):
            quiet(zedcfg.substitute, "${nope}", self.V)
        with self.assertRaises(SystemExit):
            quiet(zedcfg.substitute, "${a}", {"a": "${b}", "b": "${a}"})

    def test_list_inside_string_fails(self):
        with self.assertRaises(SystemExit):
            quiet(zedcfg.substitute, "x${globs}", self.V)


class RepoBuildTest(unittest.TestCase):
    """Invariants of the real configuration in this repo."""

    @classmethod
    def setUpClass(cls):
        cls.b = zedcfg.build()
        cls.s = cls.b.settings

    def test_ai_is_off_and_copilot_is_the_only_way_back(self):
        s = self.s
        self.assertIsInstance(s["disable_ai"], bool)  # the ${ai_kill_switch} var, not the string
        self.assertIs(s["disable_ai"], True)
        self.assertIs(s["agent"]["enabled"], False)
        self.assertEqual(s["edit_predictions"]["provider"], "none")
        self.assertEqual(s["context_servers"], {})
        self.assertEqual(s["agent_servers"], {})
        profile = s["profiles"]["Copilot"]["settings"]
        self.assertEqual(profile["edit_predictions"]["provider"], "copilot")
        self.assertIs(profile["agent"]["enabled"], False)

    def test_security_posture(self):
        s = self.s
        self.assertIs(s["session"]["trust_all_worktrees"], False)
        self.assertFalse(s["telemetry"]["metrics"] or s["telemetry"]["diagnostics"])
        for cap in s["granted_extension_capabilities"]:
            self.assertNotIn("*", (cap.get("host"), cap.get("command"), cap.get("package")), cap)
            if cap["kind"] == "download_file":
                self.assertGreaterEqual(len(cap["path"]), 3, cap)  # owner/repo/** at least
        self.assertIs(s["auto_install_extensions"]["html"], False)
        for lang in ("JSON", "JSONC", "YAML", "Markdown"):
            self.assertIs(s["languages"][lang]["prettier"]["allowed"], False, lang)

    def test_no_placeholders_left(self):
        for name, text in self.b.files().items():
            self.assertNotRegex(text, r"\$\{[a-z][a-z0-9_]*\}", name)

    def test_generated_files_are_valid_jsonc(self):
        for name, text in self.b.files().items():
            zedcfg.parse_jsonc(text, name)

    def test_keymap_task_names_exist(self):
        labels = {t["label"] for t in self.b.tasks}
        self.assertEqual(len(labels), len(self.b.tasks), "duplicate task labels")
        for block in self.b.keymap:
            for keys, action in block["bindings"].items():
                if isinstance(action, list) and action[0] == "task::Spawn":
                    self.assertIn(action[1]["task_name"], labels, keys)

    def test_leader_only_in_vim_contexts(self):
        for block in self.b.keymap:
            if any(k.startswith("space ") for k in block["bindings"]):
                self.assertIn("vim_mode", block.get("context", ""), block)

    def test_toggles_reachable_in_both_modes(self):
        workspace = {k: v for blk in self.b.keymap if blk.get("context") == "Workspace" for k, v in blk["bindings"].items()}
        self.assertEqual(workspace.get("ctrl-alt-shift-a"), "settings_profile_selector::Toggle")
        self.assertEqual(workspace.get("ctrl-alt-shift-v"), "workspace::ToggleVimMode")

    def test_k8s_globs_expanded(self):
        k8s = self.s["lsp"]["yaml-language-server"]["settings"]["yaml"]["schemas"]["kubernetes"]
        self.assertIn("k8s/**/!(Chart|kustomization|values|helmfile|skaffold|docker-compose|compose|.gitlab-ci|.pre-commit).y?(a)ml", k8s)
        self.assertNotIn("{", "".join(k8s), "brace expansion leaks through extglob negation in picomatch")

    def test_helm_settings_use_extension_server_id_and_flat_shape(self):
        helm = self.s["lsp"]["helm"]["settings"]
        self.assertNotIn("helm-ls", helm)  # the extension nests it
        self.assertEqual(helm["yamlls"]["config"]["kubernetesVersion"], self.b.variables["k8s_version"])
        self.assertNotIn("helm_ls", self.s["lsp"])

    def test_every_pack_is_well_formed(self):
        for name in zedcfg.available_packs():
            pack = zedcfg.load_pack(name)
            self.assertTrue(pack.get("description"), name)
            for req in pack.get("requires", []):
                self.assertTrue(req.get("bin") and req.get("install"), (name, req))

    def test_snippets_escape_literal_dollars(self):
        for name, snippets in self.b.snippets.items():
            for key, snip in snippets.items():
                for line in snip["body"]:
                    stripped = line.replace("\\$", "")
                    for i, ch in enumerate(stripped):
                        if ch == "$":
                            nxt = stripped[i + 1:i + 2]
                            self.assertTrue(nxt.isdigit() or nxt == "{", f"{name}/{key}: unescaped $ in {line!r}")


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.target = root / "zed"
        self.target.mkdir()
        patcher = mock.patch.object(zedcfg, "DIST", root / "dist")
        patcher.start()
        self.addCleanup(patcher.stop)

    def install(self, **kw):
        args = argparse.Namespace(dry_run=False, force=False, reset_ui=False, no_windows=True,
                                  target_dir=[str(self.target)])
        for k, v in kw.items():
            setattr(args, k, v)
        return quiet(zedcfg.cmd_install, args)

    def settings(self):
        return zedcfg.parse_jsonc((self.target / "settings.json").read_text())

    def test_first_install_backs_up_and_keeps_ui_keys(self):
        (self.target / "settings.json").write_text('{"theme": "One Dark", "buffer_font_size": 18, "trust_all_worktrees": true}')
        self.assertEqual(self.install(), 0)
        s = self.settings()
        self.assertEqual(s["theme"], "One Dark")
        self.assertEqual(s["buffer_font_size"], 18)
        self.assertIs(s["session"]["trust_all_worktrees"], False)
        backups = list((self.target / zedcfg.BACKUP_DIR).glob("*/settings.json"))
        self.assertEqual(len(backups), 1)
        self.assertIn("One Dark", backups[0].read_text())
        self.assertTrue((self.target / "keymap.json").is_file())
        self.assertTrue((self.target / "snippets" / "helm.json").is_file())

    def test_reinstall_is_idempotent(self):
        self.install()
        before = {p: p.read_text() for p in self.target.rglob("*.json") if zedcfg.BACKUP_DIR not in str(p)}
        self.assertEqual(self.install(), 0)
        after = {p: p.read_text() for p in before}
        self.assertEqual({k: v for k, v in before.items() if k.name != zedcfg.STATE_FILE},
                         {k: v for k, v in after.items() if k.name != zedcfg.STATE_FILE})
        self.assertFalse((self.target / zedcfg.BACKUP_DIR).exists())

    def test_ui_toggles_in_zed_are_not_drift(self):
        self.install()
        s = self.settings()
        s["vim_mode"] = False  # what `workspace: toggle vim mode` writes
        (self.target / "settings.json").write_text(json.dumps(s))
        self.assertEqual(self.install(), 0)
        self.assertIs(self.settings()["vim_mode"], False)

    def test_dragging_a_panel_is_not_drift(self):
        self.install()
        s = self.settings()
        s["git_panel"]["dock"] = "right"  # what dragging the panel writes
        (self.target / "settings.json").write_text(json.dumps(s))
        self.assertEqual(self.install(), 0)
        self.assertEqual(self.settings()["git_panel"]["dock"], "right")

    def test_other_edits_block_until_forced(self):
        self.install()
        s = self.settings()
        s["tab_size"] = 8
        (self.target / "settings.json").write_text(json.dumps(s))
        self.assertEqual(self.install(), 1)
        self.assertEqual(self.settings()["tab_size"], 8)  # untouched
        self.assertEqual(self.install(force=True), 0)
        self.assertNotEqual(self.settings().get("tab_size"), 8)
        backup = next((self.target / zedcfg.BACKUP_DIR).glob("*/settings.json"))
        self.assertIn('"tab_size": 8', backup.read_text())

    def test_keymap_edits_block(self):
        self.install()
        (self.target / "keymap.json").write_text("[]")
        self.assertEqual(self.install(), 1)

    def test_dry_run_writes_nothing(self):
        self.assertEqual(self.install(dry_run=True), 0)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_reset_ui(self):
        (self.target / "settings.json").write_text('{"theme": "One Dark"}')
        self.install()
        self.install(force=True, reset_ui=True)
        self.assertNotEqual(self.settings()["theme"], "One Dark")

    def test_stale_snippet_file_removed(self):
        self.install()
        state = json.loads((self.target / zedcfg.STATE_FILE).read_text())
        stale = self.target / "snippets" / "old.json"
        stale.write_text("{}\n")
        state["files"]["snippets/old.json"] = zedcfg.sha256("{}\n")
        (self.target / zedcfg.STATE_FILE).write_text(json.dumps(state))
        self.assertEqual(self.install(), 0)
        self.assertFalse(stale.exists())


class TargetsTest(unittest.TestCase):
    def test_wsl_writes_both_sides(self):
        with mock.patch.object(zedcfg, "is_windows", return_value=False), \
             mock.patch.object(zedcfg, "is_wsl", return_value=True), \
             mock.patch.object(zedcfg, "windows_appdata_from_wsl", return_value=Path("/mnt/c/Users/me/AppData/Roaming")), \
             mock.patch.dict("os.environ", {"XDG_CONFIG_HOME": "/home/me/.config"}):
            targets = zedcfg.default_targets()
        self.assertEqual(targets, [Path("/home/me/.config/zed"), Path("/mnt/c/Users/me/AppData/Roaming/Zed")])

    def test_plain_linux(self):
        with mock.patch.object(zedcfg, "is_windows", return_value=False), \
             mock.patch.object(zedcfg, "is_wsl", return_value=False), \
             mock.patch.dict("os.environ", {"XDG_CONFIG_HOME": "/home/me/.config"}):
            self.assertEqual(zedcfg.default_targets(), [Path("/home/me/.config/zed")])


class AnnotateTest(unittest.TestCase):
    STORE = "https://crds.example"

    def url(self, api_version, kind, local=None):
        return annotate_mod.schema_url(api_version, kind, "1.33.2", self.STORE, local)[0]

    def test_urls(self):
        y = annotate_mod.YANNH + "/v1.33.2-standalone-strict/"
        self.assertEqual(self.url("v1", "Service"), y + "service-v1.json")
        self.assertEqual(self.url("apps/v1", "Deployment"), y + "deployment-apps-v1.json")
        self.assertEqual(self.url("rbac.authorization.k8s.io/v1", "ClusterRole"), y + "clusterrole-rbac-v1.json")
        self.assertEqual(self.url("networking.k8s.io/v1", "Ingress"), y + "ingress-networking-v1.json")
        self.assertEqual(self.url("networking.istio.io/v1beta1", "VirtualService"),
                         self.STORE + "/networking.istio.io/virtualservice_v1beta1.json")
        self.assertEqual(self.url("gateway.networking.k8s.io/v1", "HTTPRoute"),
                         self.STORE + "/gateway.networking.k8s.io/httproute_v1.json")
        self.assertIsNone(self.url("apiextensions.k8s.io/v1", "CustomResourceDefinition"))

    def test_local_crd_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "example.com" / "widget_v1.json"
            f.parent.mkdir()
            f.write_text("{}")
            self.assertEqual(self.url("example.com/v1", "Widget", Path(tmp)), str(f.resolve()))
            self.assertTrue(self.url("example.org/v1", "Widget", Path(tmp)).startswith(self.STORE))

    def test_multi_document_insert_and_idempotent(self):
        text = ("# header comment\napiVersion: v1\nkind: ConfigMap\n---\n"
                "# yaml-language-server: $schema=https://old\napiVersion: 'apps/v1'\nkind: Deployment # the app\n"
                "---\nfoo: bar\n")
        out, report = annotate_mod.annotate(text, "1.33.2", self.STORE, None)
        lines = out.splitlines()
        self.assertTrue(lines[0].endswith("configmap-v1.json"))
        self.assertEqual(sum("yaml-language-server" in line for line in lines), 2)
        self.assertIn("deployment-apps-v1.json", out)
        self.assertNotIn("https://old", out)
        self.assertIn("skipped", report[-1])
        again, _ = annotate_mod.annotate(out, "1.33.2", self.STORE, None)
        self.assertEqual(again, out)

    def test_directory_mode_skips_charts_and_non_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "env").mkdir()
            (root / "chart" / "templates").mkdir(parents=True)
            manifest = root / "env" / "deploy.yaml"
            manifest.write_text("apiVersion: apps/v1\nkind: Deployment\n")
            plain = root / "env" / "config.yaml"
            plain.write_text("database:\n  host: localhost\n")
            template = root / "chart" / "templates" / "deployment.yaml"
            template.write_text("apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {{ .Release.Name }}\n")
            with mock.patch.object(sys, "argv", ["a.py", str(root), "--crd-store", self.STORE]):
                self.assertEqual(quiet(annotate_mod.main), 0)
            self.assertIn("deployment-apps-v1.json", manifest.read_text())
            self.assertNotIn("yaml-language-server", plain.read_text())
            self.assertNotIn("yaml-language-server", template.read_text())
            before = manifest.read_text()
            with mock.patch.object(sys, "argv", ["a.py", str(root), "--crd-store", self.STORE]):
                quiet(annotate_mod.main)
            self.assertEqual(manifest.read_text(), before)  # idempotent

    def test_templated_documents_skipped(self):
        out, report = annotate_mod.annotate("apiVersion: {{ .Values.api }}\nkind: Thing\n", "1.33.2", self.STORE, None)
        self.assertNotIn("yaml-language-server", out)


class CrdExtractTest(unittest.TestCase):
    CRD = {
        "spec": {
            "group": "example.com",
            "names": {"kind": "Widget"},
            "versions": [
                {"name": "v1", "served": True, "schema": {"openAPIV3Schema": {
                    "type": "object",
                    "properties": {"spec": {"type": "object", "properties": {
                        "size": {"x-kubernetes-int-or-string": True},
                        "extra": {"type": "object", "x-kubernetes-preserve-unknown-fields": True, "properties": {"a": {}}},
                    }}},
                }}},
                {"name": "v0", "served": False, "schema": {"openAPIV3Schema": {"type": "object"}}},
            ],
        }
    }

    def test_versions_and_conversion(self):
        versions = list(crd_extract.crd_versions(self.CRD))
        self.assertEqual([v for v, _ in versions], ["v1"])
        schema = crd_extract.to_json_schema(versions[0][1], "example.com", "v1", "Widget", strict=True)
        spec = schema["properties"]["spec"]
        self.assertIs(spec["additionalProperties"], False)
        self.assertNotIn("additionalProperties", spec["properties"]["extra"])
        self.assertEqual(spec["properties"]["size"]["oneOf"], [{"type": "integer"}, {"type": "string"}])
        self.assertEqual(schema["properties"]["apiVersion"]["enum"], ["example.com/v1"])
        self.assertEqual(schema["properties"]["kind"]["enum"], ["Widget"])

    def test_from_file_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "crds.json"
            src.write_text(json.dumps({"items": [self.CRD]}))
            with mock.patch.object(sys, "argv", ["crd_extract.py", "--from-file", str(src), "--out", tmp]):
                self.assertEqual(quiet(crd_extract.main), 0)
            self.assertTrue((Path(tmp) / "example.com" / "widget_v1.json").is_file())


class HelmRenderTest(unittest.TestCase):
    CHART = REPO / "tests" / "fixtures" / "repo" / "charts" / "demo"

    def test_chart_root(self):
        self.assertEqual(helm_render.chart_root(self.CHART / "templates" / "deployment.yaml"), self.CHART)
        self.assertIsNone(helm_render.chart_root(REPO / "zedcfg.py"))

    def test_commands(self):
        t = self.CHART / "templates"
        self.assertEqual(helm_render.build_command("template", t / "deployment.yaml", self.CHART)[-2:],
                         ["--show-only", "templates/deployment.yaml"])
        self.assertNotIn("--show-only", helm_render.build_command("template", t / "_helpers.tpl", self.CHART))
        prod = helm_render.build_command("chart", self.CHART / "values-prod.yaml", self.CHART)
        self.assertIn(str(self.CHART / "values-prod.yaml"), prod)
        self.assertEqual(helm_render.build_command("lint", self.CHART / "values.yaml", self.CHART)[:2], ["helm", "lint"])


if __name__ == "__main__":
    unittest.main()
