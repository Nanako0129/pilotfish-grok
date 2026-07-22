# pilotfish-grok — Agent Install Runbook

> This runbook is for a Grok Build agent installing pilotfish-grok on a user's
> machine. Follow the steps in order, keep the approval gate, and preserve
> unrelated Grok configuration. Prefer file tools over shell for edits.

## Contents

- [What you are installing](#what-you-are-installing)
- [Updating an existing install](#updating-an-existing-install)
- [Step 1 — Preflight](#step-1--preflight)
- [Step 2 — Present the plan](#step-2--present-the-plan)
- [Step 3 — Apply](#step-3--apply)
- [Step 4 — Verify and hand off](#step-4--verify-and-hand-off)
- [Uninstall](#uninstall)

---

## What you are installing

pilotfish-grok ports Pilotfish phase-aware orchestration to seven native Grok
Build roles. Effort and optional model pins live in role TOMLs and config;
policy names roles only.

| Target | Change |
|---|---|
| `~/.grok/config.toml` | Enable native subagents; disable all six Claude compatibility cells, discovered Claude agent types, and discovered Claude plugins; leave main model and effort user-controlled |
| `~/.grok/agents/` | Seven agent markdown files |
| `~/.grok/roles/` | Seven role TOML files (capability + reasoning_effort) |
| `~/.grok/rules/pilotfish-grok.md` | One Orchestration block between `pilotfish-grok:begin` and `pilotfish-grok:end` markers |

Source of truth: the repository [templates](../templates) directory. When
running inside a local clone, use those files directly. Otherwise fetch every
template from the **same Git ref** as this runbook. Never mix a pinned runbook
with templates from `main`.

> **Commit pinning:** If the install prompt names a tag or commit SHA, fetch
> `VERSION`, `CHANGELOG.md`, and every template from that exact ref.

> **Does not touch Claude Code.** Never modify `~/.claude/`. Isolation is
> implemented only in Grok's `~/.grok/config.toml`, so Claude Code keeps its
> existing instructions, agents, skills, hooks, and plugins.

> **Capability boundary:** Read-only roles set
> `default_capability_mode = "read-only"` in role TOMLs. Parent plan mode does
> **not** block write-capable subagents — do not claim otherwise. Grok's
> subagent nesting depth of one enforces leaf-only spawning at the harness.

## Updating an existing install

1. Detect installed version: search `~/.grok/rules/pilotfish-grok.md` for
   `pilotfish-grok v` inside the marker block. A stamp such as
   `<!-- pilotfish-grok v1.0.0 -->` is the installed version; markers without a
   stamp mean a pre-release install.
2. Fetch `VERSION` and `CHANGELOG.md` from the same ref as the templates.
3. If already up to date (version, seven agents, seven roles, sole active policy
   block, and owned config keys match), say so and stop. Otherwise show the
   changelog delta and continue with Steps 1–4. Updates are idempotent.
4. If the user customized any agent or role file, show the diff before
   overwriting.

## Step 1 — Preflight

Gather state without writing:

1. Run `grok --version`. Require Grok Build **0.2.106 or newer**, the verified
   baseline for user agents, roles, `capability_mode`, worktree isolation, and
   `spawn_subagent`. If the command is missing, unparsable, or older, **stop
   before the write plan** and ask the user to update Grok Build.
2. Read `~/.grok/config.toml` if present. Record `[models]`, `[subagents]`,
   `[subagents.toggle]`, `[subagents.models]`, `[compat.claude]`, and
   `[plugins] disabled` if present. Preserve every unrelated key. Note whether
   a pristine backup already exists under
   `~/.grok/backups/config.toml.pilotfish-grok-*`.
3. Inspect `~/.grok/rules/pilotfish-grok.md` if present. Count
   `pilotfish-grok:begin` markers: must be `0` (fresh) or `1` (upgrade). Stop
   if `>1` or markers are unmatched.
4. List `~/.grok/agents/*.md` and `~/.grok/roles/*.toml`. Parse agent frontmatter
   `name:` and role filenames. Record collisions for all seven roles:
   `scout`, `plan-verifier`, `security-reviewer`, `mech-executor`, `executor`,
   `verifier`, `security-executor`.
5. Run `grok inspect --json`. Record every Claude compatibility cell and every
   discovered entry whose source or path is under `~/.claude/`. Build two
   machine-specific deny-lists:
   - Every Claude agent name, for `[subagents.toggle] <name> = false`.
   - Every Claude plugin name, for `[plugins] disabled`.
   Do not infer active state from `plugins[].enabled` alone: Grok may still list
   a discovered disabled plugin there. Validate component state and persisted
   sessions in Step 4.
6. Treat all six `[compat.claude]` cells as one isolation gate: `skills`,
   `rules`, `agents`, `mcps`, `hooks`, and `sessions` must all be `false`.
   The `agents` cell does not by itself block custom definitions found under
   `~/.claude/agents/`; the per-type toggle is also required.
7. Do **not** install an `Explore` or `explore` agent file. Built-in `explore`
   remains available; `scout` owns pilotfish-grok discovery.

## Step 2 — Present the plan

Show a table of every intended change: path, create / merge / replace-between-markers /
skip, and backup plan. Include the exact Claude agent/plugin deny-lists from
Step 1. **Do not write anything until the user explicitly approves.** A broad
"install pilotfish-grok" request is not approval of this plan.

## Step 3 — Apply

### 3.1 Backup and directories

```bash
mkdir -p ~/.grok/backups ~/.grok/agents ~/.grok/roles ~/.grok/rules
# config backup: first install only (pristine pre-pilotfish-grok state)
ls ~/.grok/backups/config.toml.pilotfish-grok-* >/dev/null 2>&1 || \
  cp ~/.grok/config.toml ~/.grok/backups/config.toml.pilotfish-grok-$(date +%Y%m%d-%H%M%S) 2>/dev/null || true
# rules backup: every run when the file exists
cp ~/.grok/rules/pilotfish-grok.md ~/.grok/backups/pilotfish-grok.md.pilotfish-grok-$(date +%Y%m%d-%H%M%S) 2>/dev/null || true
```

If `~/.grok/config.toml` did not exist, record that there is no pristine model
config to restore on uninstall.

### 3.2 config.toml — merge owned keys only

Never rewrite the whole file. From [templates/config.snippet.toml](../templates/config.snippet.toml):

| Key | Rule |
|---|---|
| `[subagents] enabled` | If absent or false → set `true` after approval. If already true → skip. |
| `[subagents.toggle]` | Set every Claude agent name discovered in Step 1 to `false`. Always keep the exact `"Explore" = false` baseline; do not disable lowercase built-in `explore`. |
| `[subagents.models]` | Do **not** force pins. Only add keys the user explicitly requested during approval. Leave comments out of the live file unless the user wants a documented stub. |
| Main `[models] default` | **Never** change unless the user explicitly asked in the approved plan. |
| `[compat.claude]` | Set `skills`, `rules`, `agents`, `mcps`, `hooks`, and `sessions` to `false`. Preserve unrelated compat vendors. |
| `[plugins] disabled` | Merge every Claude plugin name discovered in Step 1 into the existing list. Preserve existing entries. Claude plugin discovery is independent of `[compat.claude]`. |

Validate TOML after edit (parse with a TOML library or `python3 -c 'import tomllib; tomllib.load(open(...))'`).

### 3.3 Agent and role files

For each of the seven roles, install both:

- `templates/agents/<role>.md` → `~/.grok/agents/<role>.md`
- `templates/roles/<role>.toml` → `~/.grok/roles/<role>.toml`

| Existing state | Action |
|---|---|
| Missing | Write |
| Exists, identical content | Skip |
| Exists, different content | Show diff; ask overwrite or keep |
| Name collision with a non-pilotfish file | Stop and ask |

Never install `Explore.md` / `explore.md` as part of this product.

### 3.4 Policy rules file

Canonical content: [templates/rules.pilotfish-grok.md](../templates/rules.pilotfish-grok.md)
(includes begin/end markers and version stamp).

| Marker count in `~/.grok/rules/pilotfish-grok.md` | Action |
|---|---|
| File missing | Create with the full template content |
| `0` | Write the full template (file should be product-owned) |
| `1` | Replace exactly from `<!-- pilotfish-grok:begin -->` through `<!-- pilotfish-grok:end -->` inclusive |
| `>1` | **Stop** — do not greedy-replace |

Do not modify other files under `~/.grok/rules/`.

## Step 4 — Verify and hand off

1. Parse `~/.grok/config.toml` successfully if present.
2. `~/.grok/agents/` contains all seven `.md` files; `~/.grok/roles/` contains
   all seven `.toml` files.
3. `~/.grok/rules/pilotfish-grok.md` has exactly one begin and one end marker;
   stamp matches repo `VERSION`.
4. Each role TOML has the expected `default_capability_mode` and
   `reasoning_effort` from the routing table in the README.
5. Run `grok inspect --json` and confirm the seven native agents appear, the
   rules file is listed, and all six Claude compatibility cells are `false`.
   Every discovered Claude agent must have a matching false
   `[subagents.toggle]` entry; every discovered Claude plugin name must be in
   `[plugins] disabled`. Direct Claude skills, instructions, MCPs, and hooks may
   remain visible to inspect only when marked disabled.
6. Run `python3 benchmarks/e2e-dispatch/run.py --skip-live` from the matching
   repository ref when available. It is the fail-closed isolation/install gate.
7. Tell the user to **start a new Grok session**: agents and rules are scanned
   at session start.
8. Summarize what changed, what was skipped, isolation notes, and backup
   paths.

Optional manual smoke (user or agent after restart):

- Spawn `plan-verifier` on a dummy plan and confirm it cannot edit files.
- Spawn `verifier` and confirm it can run a read-only shell command but should
  refuse to edit (capability `execute`).
- Attempt the exact case-sensitive Claude agent names from Step 1 and confirm
  Grok rejects them as disabled. For a full live run, each persisted session
  must contain zero `/.claude/` context markers and zero `hook_execution`
  events.

## Uninstall

On request, reverse the owned targets:

1. Delete the seven agent files and seven role files **only if** they still match
   pilotfish-grok templates or the user confirms after a diff.
2. Remove the block from `<!-- pilotfish-grok:begin -->` through
   `<!-- pilotfish-grok:end -->` in `~/.grok/rules/pilotfish-grok.md`; delete
   the file if empty and the user confirms.
3. In `~/.grok/config.toml`, restore pilotfish-grok-owned keys from the oldest
   `config.toml.pilotfish-grok-*` backup when appropriate. Prefer removing only
   keys this install introduced (for example `subagents.enabled` if it was
   absent before). Never wipe unrelated user config.
4. Leave `~/.claude/` untouched.
