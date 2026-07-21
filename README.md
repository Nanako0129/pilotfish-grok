# pilotfish-grok

> Grok Build–native multi-model orchestration, inspired by
> [pilotfish](https://github.com/Nanako0129/pilotfish).

**pilotfish-grok** is an independent Grok Build adaptation of Pilotfish
orchestration. It keeps the separation between machine configuration, role
bindings, and model-free policy while translating lifecycle and capability
boundaries to native Grok agents and roles. Quality comes from explicit
approval gates and fresh-context verification—not from using the strongest
model for every step.

Everything installs globally under `~/.grok/`: one setup for every project.

Primary credit for the original architecture goes to
[@Nanako0129](https://github.com/Nanako0129) (pilotfish). The seven-role host
port pattern follows [pilotfish-codex](https://github.com/miyago9267/pilotfish-codex).

[繁體中文](./README.zh-TW.md)

## Why

A coding session spends most tokens on search, mechanical edits, tests, and
docs—not on architecture judgments. Pilotfish routes volume work to leaf roles
and keeps planning, approval, and final judgment in the main session.

On Grok Build today, accounts may only expose a single frontier model. In that
regime pilotfish-grok still helps by:

- Protecting main-session context (recon and bulk work run in child sessions)
- Tiering **reasoning effort** per role (low for recon/mechanical, higher for security)
- Enforcing **capability modes** (`read-only` / `execute` / `all`) on named roles
- Requiring fresh `verifier` passes for non-trivial outcomes

When cheaper models appear in your catalog, pin them in `[subagents.models]`
without rewriting the policy.

## How it works

Three layers, all under `~/.grok/`:

| Layer | File(s) | Job |
|---|---|---|
| **Machine** | `config.toml` | Subagents enabled; optional model pins; main model stays yours |
| **Roles** | `agents/*.md` + `roles/*.toml` | Seven contracts with capability + effort |
| **Policy** | `rules/pilotfish-grok.md` | When to delegate and to which role |

### The seven Grok roles

| Role | Capability | Effort | When |
|---|---|---|---|
| `scout` | read-only | low | Broad or focused read-only discovery |
| `plan-verifier` | read-only | medium | Plan readiness; `READY` / `REVISE` |
| `security-reviewer` | read-only | high | Pre-approval security evidence |
| `mech-executor` | all | low | Mechanical work from a complete spec |
| `executor` | all | medium | Features and fixes needing judgment |
| `verifier` | execute | medium | Outcome challenge; `CONFIRMED` / `REFUTED` |
| `security-executor` | all | high | Approved security-sensitive implementation |

> **Claude-only `Explore` override is not installed.** Pilotfish uses that name
> to shadow Claude Code's built-in agent. Grok needs no such shim; `scout` owns
> discovery. Built-in `explore` remains available if you want it.

### Dispatch principles

- Keep planning, architecture, ambiguity resolution, and final judgment in the main session.
- Spawn named roles with `spawn_subagent`; use `background: true` when independent work can run in parallel.
- Give writing agents exclusive ownership or `isolation: "worktree"`.
- Do not override `model` or `capability_mode` on named roles at spawn time.
- Treat delegated results as evidence. Non-trivial changes get a fresh `verifier` pass.

## Install

> Requires Grok Build **0.2.106 or newer**.

From a local clone (recommended):

```sh
git clone https://github.com/Nanako0129/pilotfish-grok.git
cd pilotfish-grok
grok
```

Paste into the session:

```text
Read the local file install/AGENT-INSTALL.md in the current checkout and follow it to install pilotfish-grok into my global Grok Build configuration.
Show me the full plan of changes and get my approval before writing anything.
```

The agent will preflight your `~/.grok/` state, show a merge plan, and wait for
approval. Install is idempotent—re-running upgrades in place.

## What gets installed

| Target | Change |
|---|---|
| `~/.grok/config.toml` | Ensure subagents are enabled; never force main model by default |
| `~/.grok/agents/` | Seven markdown agent definitions |
| `~/.grok/roles/` | Seven TOML role defaults (capability + effort) |
| `~/.grok/rules/pilotfish-grok.md` | Orchestration block between `pilotfish-grok` markers |

Fresh installs touch only `~/.grok/`. **Claude Code's `~/.claude/` is never
modified.** If Claude pilotfish is already present, the installer warns about
dual-load via Grok's Claude compatibility layer.

## Updating

Re-run the install prompt. The installer reads the version stamp in the rules
file, shows the changelog delta, and applies changes idempotently.

## Limitations (v1.0)

- Static template contracts are tested; live spawn/capability e2e is not yet automated.
- Parent plan mode does not block write-capable subagents—read-only roles rely on role capability defaults.
- Single-model catalogs do not get multi-model price arbitrage; effort and context savings still apply.
- Does not uninstall or rewrite Claude pilotfish.

## Versioning

pilotfish-grok uses its own semantic versioning. Upstream pilotfish versions are
attribution / compatibility notes only.

## License

MIT. See [LICENSE](./LICENSE).
