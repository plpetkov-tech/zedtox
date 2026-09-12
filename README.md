# zed-initiative

A portable [Zed](https://zed.dev) setup for DevSecOps work. It has four goals:

- **AI-detoxed.** No agent panel, chat, threads sidebar, inline assistant, MCP or commit-message generation. The only AI allowed is Copilot inline ghost text, and it starts **off** every time. You switch it on with one key when you want it.
- **Neovim-grade editing.** Vim mode, a Space leader with a which-key popup, and LSP completion with docs next to each suggestion, hover, inline diagnostics, signature help and inlay hints. One key flips everything to **vanilla VSCode-style** editing (mouse, no vim) and back.
- **Built for** Kubernetes manifests (CRDs included), heavy Helm templating, Python, Bash, GitHub Actions, Dockerfiles and the occasional Jenkinsfile. **Packs** make it easy to extend.
- **Small attack surface.** Language servers come from your distro's signed packages. Extensions can only fetch exactly what an allowlist names, and untrusted repos can't run anything. The only dependencies are Python 3 (standard library) and Zed.

```
zedcfg.py            the only tool (python3, stdlib): build | install | doctor | audit | list | new-pack
config.jsonc         enabled packs + variables (k8s version, which folders are Kubernetes, ...)
local.jsonc          your per-machine overrides (gitignored; see local.jsonc.example)
core/                settings, keymap, tasks shared by everything
packs/<name>/        pack.jsonc (+ snippets/) per language or feature
scripts/             helpers used by tasks (schema modelines, CRD extraction, helm render)
tests/               unit tests + an end-to-end yaml-language-server check
```

---

## Quick start (Linux / Arch)

```sh
git clone <this repo> ~/zed-initiative && cd ~/zed-initiative
python3 zedcfg.py doctor      # what's missing + the exact install commands (runs nothing)
sudo pacman -S --needed yaml-language-server bash-language-server shellcheck shfmt \
                        vscode-json-languageserver dockerfile-language-server ruff actionlint helm kubectl
npm install --global --prefix ~/.local --ignore-scripts basedpyright   # not in Arch's repos
python3 zedcfg.py audit       # read what you're about to allow
python3 zedcfg.py install --dry-run
python3 zedcfg.py install     # backs up your current config first
```

Zed picks up the changes live. On first open of your code folder, click **Restricted Mode** in the title bar (or `space t s`). Trust the folder that holds your repos and tick *"trust all subdirectories"*, once.

After changing anything in this repo: `python3 zedcfg.py install`. Or, inside Zed, `space r r` → *zed-initiative: reinstall config*.

---

## Keys

**Two toggles work everywhere**, in vim and in vanilla mode:

| Key | What |
|---|---|
| `ctrl-alt-shift-a` (vim: `space t c`) | **AI**: picker → *Copilot* (ghost text on) / *Disabled* (zero AI) |
| `ctrl-alt-shift-v` (vim: `space t v`) | **Vim ↔ vanilla** VSCode-style editing. Zed remembers it, and reinstalls keep it |

You can also type these in the command palette (`ctrl-shift-p`): `copilot`, `vanilla`, `trust`.

**Space leader** (vim normal mode; press `space` and wait for which-key):

| | | | |
|---|---|---|---|
| `space space` files | `space /` search project | `space ,` open buffers | `space e` / `ctrl-n` file tree |
| `space f r` recent projects | `space f n` new file | `space s s` symbols in file | `space s S` symbols in workspace |
| `space c a` code actions | `space c r` rename | `space c f` format | `space c d` hover/diagnostic |
| `space c l` LSP status/logs | `space c R` restart LSP | `space x x` all diagnostics | `space r r` run task / `space r l` rerun |
| `space g g` git panel | `space g b` blame | `space g l` inline blame | `space g d` diff hunk |
| `space t i` inlay hints | `space t w` soft wrap | `space t d` inline diagnostics | `space t z` zen / `space t m` minimap |
| `space w v` / `space w s` split | `space w z` zoom | `space b d` close buffer | `space o t` terminal |
| `space y a` k8s schema modeline | `space y c` extract cluster CRDs | `space y r` restart yaml LSP | `space k d` / `space k v` kubectl diff / dry-run |
| `space h r` render template | `space h a` render chart | `space h l` helm lint | |

Zed's built-in vim LSP keys still apply:
- `gd`, `gD`, `gy`, `gI`: definition, declaration, type definition, implementation
- `grr`, `grn`, `gra`: references, rename, code action
- `K` / `gh`: hover
- `]d`, `[d`: next/previous diagnostic; `]c`, `[c`: next/previous git hunk
- `gc`: comment; `gs`, `gS`: symbols

While Copilot is on:
- `tab` accepts (when the completion menu is closed); `alt-l` also accepts.
- `alt-k` / `alt-j` accept the next word / line.
- `alt-]` / `alt-[` cycle suggestions; `alt-\` asks for one.

The completion menu shows the LSP's docs **next to** the list (Zed places it; there's no setting to put it underneath).

---

## Copilot, and what "AI-detox" means here

- `disable_ai: true` is Zed's master switch. It also covers AI features Zed adds later.
- On top of that: the agent is disabled, there are no MCP/context servers and no external agents, the agent review toolbar is off, and AI keys (`ctrl-enter` inline assist, `ctrl-?`, commit-message `alt-l`) are rebound or unbound.
- The **Copilot** settings profile flips `disable_ai` off and turns on *only* Copilot predictions (the agent stays disabled). Picking *Disabled* puts you back to zero.
- Secrets never reach Copilot, even when it's on: `.env*`, `*secret*.y*ml`, `*.sops.*`, `*.age`, kubeconfigs, `.kube/`, `*.tfvars`, `*.tfstate`, SSH keys, `.netrc`, `.npmrc`, `.pypirc`, Docker `config.json`. See `edit_predictions.disabled_globs` in `core/settings.jsonc`.
### Turning Copilot on the first time

1. `ctrl-alt-shift-a` (or `space t c`) → pick **Copilot**.
2. A Copilot icon appears in the status bar. Click it → *Sign in to GitHub Copilot* → it shows a device code and opens github.com/login/device.
3. Zed fetches GitHub's `@github/copilot-language-server` from npm the first time (the only thing it downloads for AI) and stores the login in `~/.config/github-copilot/`, which other editors using the official Copilot server share.

**Zed needs its own sign-in.** Being logged into Copilot in opencode, the `gh` CLI or a Neovim plugin doesn't carry over: those keep their own tokens (opencode, for instance, in `~/.local/share/opencode/auth.json`).

**If no ghost text appears:**
- Check the status bar icon: no icon means the profile isn't active (the picker's *Disabled* entry is the AI-free default), and a struck-through icon means signed out.
- Zed only builds its Copilot object while AI is enabled, so it has to re-initialise when the profile flips `disable_ai`. Restart Zed once with the profile active.
- Still nothing? Set `"vars": {"ai_kill_switch": false}` in `local.jsonc` and reinstall. Copilot then becomes a plain provider switch (off until you pick the profile), and the agent, MCP servers, external agents and AI keybindings stay disabled exactly as before. `python3 zedcfg.py audit` prints the resulting posture.

---

## Kubernetes and Helm

**Which YAML is Kubernetes?** yaml-language-server can't tell from content, so it goes by folder. `k8s/ kubernetes/ kube/ manifests/ deploy/ deployments/ kustomize/ overlays/ clusters/ gitops/ argocd/ flux/ flux-system/ crds/` and `*.k8s.yaml` are mapped (`k8s_globs` in `config.jsonc`). Inside those folders, `Chart.yaml`, `kustomization.yaml`, `values*.yaml`, compose, skaffold and helmfile files are skipped, because they have their own schemas.

- **Your layout:** add folders in `local.jsonc` → `"vars": {"k8s_extra_globs": ["platform/**/${k8s_skip}.y?(a)ml"]}`.
- **One repo:** add to its `.zed/settings.json` (applies once the folder is trusted):
  ```jsonc
  { "lsp": { "yaml-language-server": { "settings": { "yaml": { "schemas": {
      "kubernetes": ["env/**/*.yaml"] } } } } } }
  ```
- **One file:** `space y a` writes `# yaml-language-server: $schema=…` into each document, based on its `apiVersion`/`kind`. A modeline beats every other mapping and also helps teammates on VS Code.

**CRDs are automatic.** In mapped files, yaml-ls resolves `apiVersion`/`kind`: built-in kinds use the Kubernetes schema for `k8s_version`, and CRDs are fetched from the [datree CRDs-catalog](https://github.com/datreeio/CRDs-catalog) (Istio, Argo CD, Flux, cert-manager, External Secrets, prometheus-operator, Gateway API and many more). Hover shows each field's docs and the schema's source.

**Your own CRDs:** `space y c` runs `scripts/crd_extract.py`. It reads the CRDs of your current kube context (`kubectl get crd -o json`, read-only) and writes schemas to `~/.local/share/zed-initiative/crds/`. `space y a` then prefers those over the public catalog. This replaces piping `crd-extractor.sh` from curl into bash: nothing is downloaded, and the output stays out of git.

**Helm** (`packs/helm`): templates, `values*.yaml` and helmfile.d are the *Helm* language, served by helm_ls. That gives you:
- `.Values.` completion, and hover that shows the actual value from every values file.
- Go-to-definition into `values.yaml`, and docs for template functions (sprig).
- helm lint diagnostics, plus Kubernetes schema completion inside templates (helm_ls runs yaml-ls with the same k8s version and CRD catalog).

`space h r` renders the template you're in (`helm template --show-only`); from `values-prod.yaml` it layers that file on. `space h a` renders the whole chart and `space h l` lints it.

> **Known issue (yaml-language-server ≤ 1.24.0):** kinds in the core group (`apiVersion: v1`: Service, ConfigMap, Secret, ServiceAccount, …) aren't auto-detected. In mapped folders they show *"Matches multiple schemas when only one must validate"*. It's fixed upstream and will arrive with the next yaml-language-server release. Until then, `space y a` on the file fixes it permanently.

---

## Security model

`python3 zedcfg.py audit` prints all of this from the actual config.

- **Worktree trust.** `trust_all_worktrees` is **off**. An untrusted folder's `.zed/settings.json` is ignored and no language servers start for it. That blocks the "malicious repo points an LSP binary at a script" class of attack.
  - Self-test: make a folder containing `.zed/settings.json` with `{"lsp":{"yaml-language-server":{"binary":{"path":"/usr/bin/touch","arguments":["/tmp/zed-trust-FAILED"]}}}}` and a `a.yaml`, then open it. Zed should show Restricted Mode, and `/tmp/zed-trust-FAILED` must not appear.
- **Language servers come from PATH.** Zed uses a server it finds on `$PATH` before downloading its own. That's why the packs list signed pacman packages. `zedcfg.py doctor` shows which binary each server actually used last session, and flags anything Zed downloaded into `~/.local/share/zed/languages/`.
- **Extensions are sandboxed and get only exact grants.** `granted_extension_capabilities` starts empty (Zed's default is "exec anything, download anything, npm-install anything"):

  | Pack | Extension | Allowed |
  |---|---|---|
  | helm | `helm` (cabrinha/helm.zed) | download from `github.com/mrjosh/helm-ls/**` (pinned v0.5.4), only if `helm_ls` isn't on PATH |
  | docker | `dockerfile` (zed-extensions) | npm-install `dockerfile-language-server-nodejs`, only if `docker-langserver` isn't on PATH |
  | jenkins | `groovy` | nothing: syntax only, LSP disabled |
  | terraform (off) | `terraform` (zed-extensions) | download from `releases.hashicorp.com/terraform-ls/**` |
  | markdown (off) | `marksman` | download from `github.com/artempyanykh/marksman/**` |

  Skipped on purpose: Docker Inc.'s docker-language-server (compose files stay YAML with the compose-spec schema instead), the community gh-actions extension (schemas plus actionlint cover it), and the groovy LSP (unpinned jar from a personal fork).
- **No surprise installs.** Prettier is disabled for JSON, YAML and Markdown, so Zed never npm-installs it. `package-version-server` is off, and the default `html` extension is no longer auto-installed. npm installs this repo suggests are always `--prefix ~/.local --ignore-scripts` (no root, no lifecycle scripts).
- **Telemetry is off.** Values in private files (`.env`, keys, kubeconfigs, tfvars) are redacted on screen.
- **Network, data only:** yaml-ls fetches JSON schemas (schemastore.org, the yannh k8s schemas, the datree CRD catalog) when you open matching files. No code, but it does show those hosts which kinds of files you open.

---

## Packs

`python3 zedcfg.py list` shows them. Enabled by default: `json yaml kubernetes helm python bash github-actions jenkins docker`. Also available: `terraform markdown`.

Add your own (e.g. for a new schema, a linter task or a language):

```sh
python3 zedcfg.py new-pack gitlab-ci     # copies packs/_template with comments
$EDITOR packs/gitlab-ci/pack.jsonc
# add "gitlab-ci" to "packs" in config.jsonc (or "enable" in local.jsonc)
python3 zedcfg.py audit && python3 zedcfg.py install
```

A pack can contain:
- `description`
- `requires`: tools on PATH, with install names per package manager, for `doctor`
- `settings`: any Zed settings
- `keymap`, `tasks`
- a `snippets/<language>.json` directory, named like Zed's language names: `yaml.json`, `helm.json`, `python.json`, `shell script.json`

**Merge rules:**
- Order is core → packs (in config order) → `local.jsonc`.
- Objects merge and lists append. `{"$replace": [...]}` replaces a list instead (e.g. `language_servers`).
- If two packs set the same value, you get a warning.
- `${name}` pulls from `vars`, plus the built-ins `${repo}`, `${home}`, `${python}` and `${data_dir}`. Zed's own `$ZED_*` variables are left alone.

Example: switching Python to pacman's `pyright` (no inlay hints) in `local.jsonc`:
```jsonc
{ "settings": { "languages": { "Python": {
    "language_servers": { "$replace": ["pyright", "ruff", "!basedpyright", "..."] } } } } }
```

---

## Windows (via WSL2)

Zed runs natively on Windows and opens your repos *inside* WSL. Language servers, helm, kubectl, shellcheck, tasks and the terminal all run in Linux. The Windows side only needs Zed.

1. Windows: `winget install -e --id ZedIndustries.Zed` and `wsl --install archlinux` (the official Arch image, so everything above applies 1:1).
2. In WSL: clone this repo, run `python3 zedcfg.py doctor`, install what it lists with pacman, then `python3 zedcfg.py install`. Under WSL, install writes **both** `~/.config/zed` (WSL; Zed's remote server reads LSP settings from here) and `%APPDATA%\Zed` (Windows; UI and keymap). Use `--target-dir` if Windows' `%APPDATA%` isn't detected.
3. In Zed: command palette → `projects: open wsl` → your distro → a folder in the Linux filesystem (not `/mnt/c`, which is slow and has CRLF surprises).
4. Copilot (if you use it) signs in on the Windows side.

---

## Updating, drift and backups

- `git pull && python3 zedcfg.py install`.
- **Edits made in Zed.** Theme picker, font zoom and the vim toggle write to `settings.json`, and those keys (`vim_mode`, `theme`, `icon_theme`, `ui_font_size`, `buffer_font_size`) are kept on reinstall. Any other edit made in Zed is reported with a diff, and install refuses until you move it into `local.jsonc` or re-run with `--force`. `--reset-ui` resets the kept keys.
- **Backups.** Every overwritten file goes to `<zed config>/zed-initiative-backups/<timestamp>/`. Your pre-zed-initiative config is the first one there.
- **Old Zed downloads.** `doctor` lists language servers Zed fetched itself before you installed the system ones, and `doctor --clean-downloads` deletes exactly those that a PATH install now supersedes.
- **Uninstall.** Restore that first backup and delete `zed-initiative.state.json`.

## Tests

```sh
python3 -m unittest discover -s tests -v    # engine, security invariants, install/drift logic, scripts
python3 tests/lsp_smoke.py                  # real yaml-language-server against tests/fixtures (needs network)
```

## Troubleshooting

- A language feature is missing: `python3 zedcfg.py doctor`, then `space c l` in the file (LSP status and logs), or `zed: open log`.
- The wrong schema is on a YAML file: hover a key. The popup ends with *Source: …* naming the schema in use. `space y a` pins the right one.
- Nothing works in a repo: it's probably untrusted (title-bar Restricted Mode, `space t s`).
