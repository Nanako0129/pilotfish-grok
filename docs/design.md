# pilotfish-grok Design Rationale

> Grok Build port of [pilotfish](https://github.com/Nanako0129/pilotfish)
> orchestration. Same architecture and phase-aware lifecycle; install surface
> and capability primitives are native Grok. The seven-role host-port shape
> also appears in [pilotfish-codex](https://github.com/miyago9267/pilotfish-codex).
> This project has its own release train.

## Purpose

Preserve pilotfish's separation of concerns and phase-aware orchestration in
native Grok Build configuration. Role-based policy, approval gates, leaf
workers, and fresh-context verification stay; Claude-specific mechanisms
(`settings.json`, `tools:` allowlists, `Explore` shadowing, Sonnet buckets)
are replaced with Grok surfaces.

## Three-layer translation

| Layer | Grok surface | Owns |
|---|---|---|
| Machine | `~/.grok/config.toml` | Subagent enablement; optional `[subagents.models]` pins; never forces main-session model by default |
| Roles | `~/.grok/agents/*.md` + `~/.grok/roles/*.toml` | Role contract, capability mode, reasoning effort, optional model |
| Policy | `~/.grok/rules/pilotfish-grok.md` | Phase gates, delegation boundaries, approval, integration, verification |

```mermaid
flowchart LR
    CONFIG["Grok config.toml<br>optional model pins"] --> ORCH["Main-session orchestrator"]
    ORCH --> POLICY["Policy<br>role names only"]
    POLICY --> AGENTS["agents/*.md + roles/*.toml"]
    AGENTS --> MODELS["Available Grok models"]
```

> **Core invariant:** The orchestration **policy names roles but never embeds**
> model IDs or effort levels. Routing changes in agent/role files or
> `[subagents.models]` must not require rewriting the policy.

## Seven Grok roles

| Role | Phase | Capability | Effort | Responsibility |
|---|---|---|---|---|
| `scout` | Discovery | `read-only` | low | Broad or focused recon |
| `plan-verifier` | Plan | `read-only` | medium | `READY` / `REVISE` |
| `security-reviewer` | Plan / Approval | `read-only` | high | Pre-approval security evidence |
| `mech-executor` | Execution | `all` | low | Complete mechanical specs |
| `executor` | Execution | `all` | medium | Local design judgment |
| `verifier` | Verification | `execute` | medium | `CONFIRMED` / `REFUTED` |
| `security-executor` | Execution | `all` | high | Approved security implementation |

Pilotfish's uppercase `Explore` role is deliberately absent. That name exists
to shadow Claude Code's built-in Explore agent so expensive main-session models
do not silently run exploration. Grok already has a separate built-in `explore`
type; `scout` covers pilotfish-grok discovery. Installing a second discovery
agent would duplicate boundaries without the Claude-specific benefit.

### Why verifier uses `execute`, not `read-only`

Claude Pilotfish lets the verifier run Bash while denying Write tools. Grok's
`read-only` capability mode also denies shell. Outcome verification needs tests
and flow reproduction, so the Grok mapping is `execute` (read + shell, no file
edits).

### Capability enforcement order

1. Harness depth limit (subagents cannot spawn subagents)
2. Role `default_capability_mode` on named types
3. Agent prompt contracts (leaf language, no-edit language)
4. Orchestrator discipline: do not override `capability_mode` on named roles

Parent **plan mode does not protect child writes**. Read-only roles must not
rely on the parent remaining in plan mode.

## Effort-first economics

On accounts with a single coding model (for example only `grok-4.5`), multi-model
subscription savings do not apply. pilotfish-grok still pays for itself by:

- Keeping high-volume recon off the main context window
- Bounding mechanical work to low reasoning effort
- Requiring fresh-context verification for non-trivial claims

When cheaper models appear in the catalog, pin them under `[subagents.models]`
without editing policy prose.

## Phase-aware orchestration

Role matching makes work eligible for delegation; it does not make delegation
mandatory. The main session retains framing, Plan synthesis, architecture,
ambiguity resolution, integration, and final judgment.

A single unknown bug should not become a sequential `scout` → `executor`
pipeline when diagnosis, patch design, and live verification share one evidence
chain.

## Deliberately left out

| Not included | Why |
|---|---|
| Eighth `Explore` agent | No Claude-style shadow need; `scout` is enough |
| Forced main-session model | User-controlled; Grok has no `best` alias story |
| Claude-style baton gate | [e2e-dispatch](../benchmarks/e2e-dispatch/README.md) covers adversarial approval bypass plus forced spawn plumbing, not a complete multi-turn Baton workflow |
| Unprompted orchestrator routing eval | e2e forces role names; free-form role choice quality is out of scope |
| Enforcement hooks | Policy-first, matching Pilotfish philosophy |
| Per-project install | Global `~/.grok/` is the product surface |
| Editing `~/.claude/` | Dual-harness coexistence; Claude pilotfish remains independent |

## Relationship to siblings

| Project | Host | Policy markers | Roles |
|---|---|---|---|
| pilotfish | Claude Code | `pilotfish` | 8 (incl. Explore) |
| pilotfish-grok | Grok Build | `pilotfish-grok` | 7 |
| pilotfish-codex | Codex CLI | `pilotfish-codex` | 7 |

Useful pilotfish changes may be adapted when they fit Grok. Source parity is
not an independent goal; Grok-specific needs take priority.
