# zed-initiative

A portable [Zed](https://zed.dev) setup for DevSecOps work: no AI unless you ask for it, vim-grade editing, Kubernetes/Helm/Python/Bash tooling, and a small attack surface. Needs only Python 3 (standard library) and Zed.

## Start here

**~10 minutes, most of it pacman.**

```sh
git clone <this repo> ~/zed-initiative && cd ~/zed-initiative
python3 zedcfg.py doctor
```

1. Run the two commands above. `doctor` lists what's missing and prints the exact install command; it installs nothing itself.
2. Install the tools it names:
   ```sh
   sudo pacman -S --needed yaml-language-server bash-language-server shellcheck shfmt \
                           vscode-json-languageserver dockerfile-language-server ruff actionlint helm kubectl
   npm install --global --prefix ~/.local --ignore-scripts basedpyright   # not in Arch's repos
   ```
3. Read what you're about to allow: `python3 zedcfg.py audit`
4. Install it: `python3 zedcfg.py install` (your current Zed config is backed up first; add `--dry-run` to see the diff)
5. Open your code folder in Zed, click **Restricted Mode** in the title bar, trust the folder and tick *"trust all subdirectories"*. Once, per machine.

After any change in this repo: `python3 zedcfg.py install`, or `space r r` → *zed-initiative: reinstall config*.

## What you get

- **Zero AI by default.** No agent panel, chat, threads sidebar, inline assistant, MCP servers or commit-message generation. Copilot ghost text is one keypress away and off again just as fast.
- **Vim with a Space leader** and a which-key popup, plus one key to flip to plain VSCode-style editing with the mouse.
- **Kubernetes validation that follows the repo,** including CRDs (Istio, Argo, Flux, cert-manager, ESO, prometheus-operator, Gateway API), resolved from `apiVersion`/`kind`.
- **Helm that understands your chart:** `.Values.` completion, hover showing the real value, go-to-definition into `values.yaml`, lint, and render-this-template.
- **Language servers from signed distro packages,** extensions restricted to an exact allowlist, and untrusted repos that can't start anything.

## Keys

Both toggles work in vim mode and in vanilla mode. Command palette equivalents: `copilot`, `vanilla`, `trust`.

| Key | Does |
|---|---|
| `ctrl-alt-shift-a` · `space t c` | AI picker: *Copilot* (ghost text) / *Disabled* (zero AI) |
| `ctrl-alt-shift-v` · `space t v` | Vim ↔ vanilla VSCode-style editing (remembered across reinstalls) |
| `space t s` | Trust / restrict the current folder |

**Files and navigation**

| Key | Does |
|---|---|
| `space space` | Find file |
| `space /` | Search project |
| `space ,` | Open buffers |
| `space e` · `ctrl-n` | File tree |
| `space f r` · `space f n` | Recent projects · new file |

**Search and replace**

| Key | Does |
|---|---|
| `/` · `space /` | Search this file · search the project (both seed from the word under the cursor) |
| `space s r` · `space s R` | Replace in this file · replace across the project |
| `space s /` | Search within the selection only |
| `space s g` · `space s s` · `space s S` | Grep project · symbols in file · symbols in project |
| in project search: `alt-r` · `alt-ctrl-f` | Regex · include/exclude file globs |

Project-search results are an **editable multibuffer**: change the results in place, `g a` selects
every match at once, `:w` saves every touched file. That's the cross-file refactor when LSP rename
(`space c r`) doesn't apply. `:%s/a/b/g` works too, and Zed rewrites vim-style regex groups for you.

**Pickers** (while a modal is open)

| Key | Does |
|---|---|
| `ctrl-/` | Toggle the preview pane |
| `ctrl-space` | Mark several entries, open them together |
| `ctrl-shift-i` | Include gitignored files (file finder) |

The leader isn't available inside a modal (space types a space), and alt belongs to your window
manager on a tiling WM, so these are ctrl chords.

**Code and LSP**

| Key | Does |
|---|---|
| `space c a` · `space c r` | Code actions · rename |
| `space c f` | Format (visual mode: selection only) |
| `space c d` · `space x x` | Hover docs · all diagnostics |
| `space c l` · `space c R` | LSP status and logs · restart LSP |
| `space s s` · `space s S` | Symbols in file · in workspace |

**Git and tasks**

| Key | Does |
|---|---|
| `space g g` · `space g b` | Git panel · blame |
| `space g l` · `space g d` | Inline blame · diff hunk |
| `space r r` · `space r l` | Run task · rerun last |

**Kubernetes and Helm**

| Key | Does |
|---|---|
| `space y m` | Map this repo's manifest folders (once per repo) |
| `space y a` · `space y A` | Schema modeline: this file · this folder |
| `space y c` · `space y r` | Extract cluster CRDs · restart yaml LSP |
| `space k d` · `space k v` | kubectl diff · server-side dry-run |
| `space h r` · `space h a` · `space h l` | Render template · render chart · lint |

**View and windows**

| Key | Does |
|---|---|
| `space t i` · `space t w` | Inlay hints · soft wrap |
| `space t d` · `space t m` | Inline diagnostics · minimap |
| `space t z` | Zen (centered) layout |
| `space w v` · `space w s` · `space w z` | Split right · split down · zoom |
| `space b d` · `space o t` | Close buffer · terminal |

Zed's built-in vim keys still apply:

- `gd`, `gD`, `gy`, `gI`: definition, declaration, type definition, implementation
- `grr`, `grn`, `gra`: references, rename, code action
- `K` / `gh`: hover
- `]d`, `[d`: next/previous diagnostic; `]c`, `[c`: next/previous git hunk
- `gc`: comment; `gs`, `gS`: symbols
- `s` / `S`: Sneak — jump to the next / previous occurrence of two characters (the `motion` pack;
  vim's `s` and `S` live on as `c l` and `c c`)

With Copilot on: `tab` accepts, `ctrl-alt-k` / `ctrl-alt-j` accept the next word / line, `alt-]` / `alt-[` cycle, `alt-\` asks for a suggestion. Completion docs appear beside the menu (Zed places them; not configurable).

**On a tiling WM, alt is usually the WM's modifier** (sway's `$mod`), so bare `alt-…` keys never reach Zed. Everything here avoids them: Copilot's partial accepts moved from `alt-k`/`alt-j` to `ctrl-alt-k`/`ctrl-alt-j`, and the picker keys are ctrl chords.

## Copilot

**Turn it on the first time — 2 minutes.**

1. `ctrl-alt-shift-a` → pick **Copilot**.
2. Click the Copilot icon in the status bar → *Sign in to GitHub Copilot* → enter the device code it shows.
3. Type in any file. Ghost text appears; `tab` accepts.

Zed needs its own sign-in. A Copilot login in opencode, `gh`, or a Neovim plugin does not carry over — those keep separate tokens. Zed stores its own in `~/.config/github-copilot/`, shared with other editors that use the official Copilot server.

**No ghost text?**

1. No status-bar icon: the profile isn't active. Re-pick *Copilot* (the *Disabled* entry is the AI-free default).
2. Struck-through icon: signed out. Repeat step 2 above.
3. Icon present, still nothing: Zed builds its Copilot object only while AI is enabled, so it must re-initialise when the profile flips `disable_ai`. Restart Zed once with the profile active.
4. Still nothing: set `"vars": {"ai_kill_switch": false}` in `local.jsonc` and reinstall. Copilot becomes a plain provider switch, still off until you pick the profile; agent, MCP, external agents and AI keys stay disabled. `zedcfg.py audit` prints the result.

**What "AI-detox" means here:** `disable_ai: true` is Zed's master switch and covers AI features Zed adds later. On top of it the agent is disabled, there are no MCP/context servers or external agents, the agent-review toolbar is off, and the AI keys (`ctrl-enter`, `ctrl-?`, commit-message `alt-l`) are unbound or rebound. Even with Copilot on, it never sees `.env*`, `*secret*.y*ml`, `*.sops.*`, `*.age`, kubeconfigs, `.kube/`, `*.tfvars`, `*.tfstate`, SSH keys, `.netrc`, `.npmrc`, `.pypirc` or Docker `config.json` (`edit_predictions.disabled_globs`).

## Kubernetes and Helm

**A repo whose manifests aren't validating — `space y m`, seconds.** It walks the worktree, finds the files that genuinely are manifests (top-level `apiVersion` + `kind`, no Go templating), and writes their folders into the repo's own `.zed/settings.json`. Commit it: every branch and teammate gets validation, no manifest edited, nothing to remember. Re-run after a big restructure. Helm charts, `.github/`, `node_modules` and ordinary config YAML are skipped. The worktree must be trusted for project settings to apply.

Two smaller levers:

- **Repos that share a layout:** set it once in `local.jsonc` → `"vars": {"k8s_extra_globs": ["platform/**/${k8s_skip}.y?(a)ml"]}`.
- **A single odd file:** type `schema` in it and pick from the completion menu (GitHub workflow, GitLab CI, compose, Ansible, Argo, Prometheus, Renovate, OpenAPI…), or `space y a` to fill in the exact Kubernetes schema from `apiVersion`/`kind`. `space y A` does a whole folder. A modeline outranks every mapping and travels with the file to VS Code and nvim users.

**Which files are Kubernetes out of the box:** `k8s/ kubernetes/ kube/ manifests/ deploy/ deployments/ kustomize/ overlays/ clusters/ gitops/ argocd/ flux/ flux-system/ crds/` and `*.k8s.yaml` (`k8s_globs` in `config.jsonc`). Inside them, `Chart.yaml`, `kustomization.yaml`, `values*.yaml`, compose, skaffold and helmfile files keep their own schemas.

**The folder list only picks the schema, never whether the LSP runs.** yaml-ls attaches to every YAML file anywhere: syntax errors, formatting and name-based SchemaStore matches (workflows, compose, kustomization, GitLab CI) work regardless of folder. A manifest outside the list isn't broken, just unvalidated.

**CRDs resolve themselves.** In mapped files, built-in kinds use the Kubernetes schema for `k8s_version`; CRDs come from the [datree CRDs-catalog](https://github.com/datreeio/CRDs-catalog). Hover shows each field's docs and the schema source.

**Your own CRDs:** `space y c` reads the CRDs of your current kube context (`kubectl get crd -o json`, read-only) into `~/.local/share/zed-initiative/crds/`, which `space y a` then prefers over the public catalog. Replaces piping `crd-extractor.sh` from curl into bash; output stays out of git.

**Helm** (`packs/helm`): templates, `values*.yaml` and helmfile.d are the *Helm* language, served by helm_ls.

- `.Values.` completion, with hover showing the value from every values file
- Go-to-definition into `values.yaml`, plus docs for sprig template functions
- helm lint diagnostics, and Kubernetes schema completion inside templates
- `space h r` renders the current template (from `values-prod.yaml` it layers that file on), `space h a` the whole chart, `space h l` lints

**Known issue (yaml-language-server ≤ 1.24.0).** Core-group kinds (`apiVersion: v1`: Service, ConfigMap, Secret, ServiceAccount) aren't auto-detected and report *"Matches multiple schemas when only one must validate"*. Cause: yaml-ls splits `apiVersion` on `/` and gives up without a group. Fixed upstream, ships in the next release. Fix now: `space y a` on the file.

## Security model

`python3 zedcfg.py audit` prints all of this from the actual config.

- **Untrusted repos can't run anything.** `trust_all_worktrees` is off, so an untrusted folder's `.zed/settings.json` is ignored and no language servers start. Self-test: create a folder with `.zed/settings.json` containing `{"lsp":{"yaml-language-server":{"binary":{"path":"/usr/bin/touch","arguments":["/tmp/zed-trust-FAILED"]}}}}` plus any `.yaml`, open it, and confirm Restricted Mode appears and `/tmp/zed-trust-FAILED` does not.
- **Language servers resolve by name from `$PATH`,** never hardcoded paths, so distro packages win and the config stays portable. `doctor` reports which binary each server actually used and flags anything Zed downloaded itself.
- **Extensions start with zero capabilities** (Zed's default is exec/download/npm-install anything) and get exactly one grant each:

  | Pack | Extension | Allowed |
  |---|---|---|
  | helm | `helm` (cabrinha/helm.zed) | download `github.com/mrjosh/helm-ls/**`, pinned v0.5.4, only if `helm_ls` isn't on PATH |
  | docker | `dockerfile` (zed-extensions) | npm-install `dockerfile-language-server-nodejs`, only if `docker-langserver` isn't on PATH |
  | jenkins | `groovy` | nothing: syntax only, LSP disabled |
  | terraform (off) | `terraform` (zed-extensions) | download `releases.hashicorp.com/terraform-ls/**` |
  | markdown (off) | `marksman` | download `github.com/artempyanykh/marksman/**` |

- **No surprise installs.** Prettier is off for JSON/YAML/Markdown, `package-version-server` is disabled, the default `html` extension isn't auto-installed, and suggested npm installs always use `--prefix ~/.local --ignore-scripts`.
- **Telemetry off; private files redacted on screen** (`.env`, keys, kubeconfigs, tfvars).

Deliberately skipped: Docker Inc.'s docker-language-server (compose files stay YAML with the compose-spec schema), the community gh-actions extension (schemas + actionlint cover it), and the groovy LSP (unpinned jar from a personal fork). Network traffic is data only: yaml-ls fetches JSON schemas from schemastore.org, the yannh Kubernetes schemas and the datree catalog when you open matching files — no code, though those hosts see which kinds of files you open.

## Packs

`python3 zedcfg.py list` shows them. On by default: `json yaml kubernetes helm python bash github-actions jenkins docker look motion`. Available: `terraform markdown`.

**Add one — about 5 minutes.**

1. `python3 zedcfg.py new-pack gitlab-ci` (copies `packs/_template`, fully commented)
2. Edit `packs/gitlab-ci/pack.jsonc`
3. Add `"gitlab-ci"` to `packs` in `config.jsonc` (or `enable` in `local.jsonc`)
4. `python3 zedcfg.py audit && python3 zedcfg.py install`

A pack holds `description`, `requires` (tools for `doctor`), `settings` (any Zed settings), `keymap`, `tasks`, and optionally `snippets/<language>.json` named like Zed's languages (`yaml.json`, `helm.json`, `shell script.json`).

**Merge rules**

- Order: core → packs (config order) → `local.jsonc`
- Objects merge, lists append; `{"$replace": [...]}` replaces a list instead
- Two packs setting the same value produces a warning
- `${name}` comes from `vars`, plus `${repo}`, `${home}`, `${python}`, `${data_dir}`, `${zed_config_dir}`
- Zed's own `$ZED_*` and snippet `${1:…}` variables are left alone

Switching Python to pacman's `pyright` (no inlay hints), in `local.jsonc`:

```jsonc
{ "settings": { "languages": { "Python": {
    "language_servers": { "$replace": ["pyright", "ruff", "!basedpyright", "..."] } } } } }
```

## Windows, via WSL2

**30–45 minutes, mostly the WSL install.** Zed runs natively on Windows and opens repos inside WSL; language servers, helm, kubectl, tasks and the terminal run in Linux. The Windows side needs only Zed.

1. Windows: `winget install -e --id ZedIndustries.Zed`, then `wsl --install archlinux` (official Arch image, so everything above applies unchanged).
2. In WSL: clone this repo, `python3 zedcfg.py doctor`, install what it lists, then `python3 zedcfg.py install`. It writes both `~/.config/zed` (WSL, where language servers read their settings) and `%APPDATA%\Zed` (Windows, UI and keymap). Add `--target-dir` if `%APPDATA%` isn't detected.
3. In Zed: command palette → `projects: open wsl` → your distro → a folder on the Linux filesystem (not `/mnt/c`: slow, plus CRLF surprises).
4. Sign in to Copilot on the Windows side, if you use it.

## Maintenance

- **Update:** `git pull && python3 zedcfg.py install`
- **Edits made inside Zed:** theme, font size, vim toggle and panel docks are kept on reinstall. Any other edit is reported with a diff and install stops until you move it into `local.jsonc` or pass `--force`; `--reset-ui` resets the kept keys.
- **Backups:** every overwritten file lands in `<zed config>/zed-initiative-backups/<timestamp>/`. The first one is your pre-zed-initiative config.
- **Old Zed downloads:** `doctor --clean-downloads` removes language servers Zed fetched itself that a PATH install now supersedes.
- **Uninstall:** restore that first backup, delete `zed-initiative.state.json`.

## Publishing this repo

Nothing here is secret: no credentials, no cluster data, no infrastructure names. Two habits keep it that way.

1. Employer-specific values go in `local.jsonc` (gitignored), not `config.jsonc` — real folder layouts, internal schema URLs.
2. Cluster CRD dumps stay outside the repo (`crd_extract.py` defaults there); `.gitignore` also covers `crds/`, kubeconfigs, tfvars and key material in case a path is redirected.

Commit metadata publishes the name and email from your git config. Set a GitHub noreply address first if you'd rather not have yours indexed.

## Tests

```sh
python3 -m unittest discover -s tests -v    # engine, security invariants, install/drift logic, scripts
python3 tests/lsp_smoke.py                  # real yaml-language-server over tests/fixtures (needs network)
```

## Troubleshooting

- **A language feature is missing:** run `python3 zedcfg.py doctor`, then `space c l` in the file for LSP status and logs.
- **Wrong schema, or none, on a YAML file:** hover a key; the popup ends with *Source: …*. Fix the repo with `space y m`, or the file by typing `schema`.
- **Nothing works in a repo:** it's untrusted. Title bar → Restricted Mode, or `space t s`.
- **A tool you just installed isn't found:** Zed caches resolved binaries per session and reads `$PATH` at startup. Restart Zed.
- **Install refuses to write:** something edited the file outside this repo. The diff names the keys; move them into `local.jsonc` or re-run with `--force`.

## Layout

```
zedcfg.py            the only tool (python3, stdlib): build | install | doctor | audit | list | new-pack
config.jsonc         enabled packs + variables (k8s version, which folders are Kubernetes, ...)
local.jsonc          per-machine overrides (gitignored; see local.jsonc.example)
core/                settings, keymap, tasks shared by everything
packs/<name>/        pack.jsonc (+ snippets/) per language or feature
scripts/             helpers behind the tasks (schema mapping, CRD extraction, helm render)
tests/               unit tests + an end-to-end yaml-language-server check
```
