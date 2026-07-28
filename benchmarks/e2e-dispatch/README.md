# e2e-dispatch — live policy and role dispatch proof

Runtime proof that natural prompts spontaneously route through all seven
pilotfish-grok roles with the expected `capability_mode`. Complements static
template tests.

## What it proves

| Case | Assertion |
|---|---|
| Install surface | Seven agents + seven roles + policy present under `GROK_HOME` (default `~/.grok`) |
| `grok inspect` | All seven role names listed |
| Claude isolation | All six Claude compatibility cells are false; every discovered Claude agent and plugin has an explicit Grok deny entry |
| **cue-free-discovery** | Natural lookup dispatches `scout` without role hints |
| **cue-free-mechanical** | Cross-file rename dispatches `mech-executor`, then fresh `verifier`; tests pass |
| **cue-free-judgment** | Retry implementation dispatches `executor`, then fresh `verifier`; tests pass |
| **cue-free-security** | Constant-time comparison change dispatches `scout`, `security-reviewer`, `plan-verifier`, then after a cue-free user continuation `security-executor` and `verifier`; tests pass |

The four default cases contain none of the seven role names or the words agent,
subagent, spawn, delegate, delegation, Plan, approval, or verifier. Their
combined `subagent_spawned` events must cover all seven roles. Forced capability
and adversarial cases remain selectable with `--cases` for focused diagnosis.

Every live case also inspects its persisted `chat_history.jsonl` and
`updates.jsonl`. A `/.claude/` or `CLAUDE_PLUGIN_ROOT` context marker, or any
Claude-derived `hook_execution` event fails the run; unrelated native Grok
hooks are recorded but allowed. The harness additionally forces all six
`GROK_CLAUDE_*_ENABLED=false` environment variables as defense in depth; the
install-only preflight still checks that the persistent config is closed first.

Proof source for capability: parent session `updates.jsonl` event
`sessionUpdate=subagent_spawned` fields `subagent_type`, `role`,
`capability_mode`, `model`.

## Requirements

- Grok Build **≥ 0.2.106** on `PATH`
- Authenticated (`grok login` or `XAI_API_KEY`)
- pilotfish-grok already installed into `~/.grok` (or `$GROK_HOME`)
- Pure Grok isolation applied by the installer: six false
  `[compat.claude]` cells, false toggles for discovered Claude agents, and
  discovered Claude plugin names in `[plugins] disabled`
- Network access (live cases call the model)

## Run

```sh
# install + inspect only (no model spend)
python3 benchmarks/e2e-dispatch/run.py --skip-live

# full live policy + dispatch proof
python3 benchmarks/e2e-dispatch/run.py

# subset
python3 benchmarks/e2e-dispatch/run.py --cases cue-free-mechanical,cue-free-judgment
```

Live runs write [`results.json`](./results.json); `--skip-live` writes
`results.install-only.json`.

## Cost & time

Live runs are not free. Check `results.json` for the measured version, aggregate
case wall time, and `total_cost_usd`; do not treat one run as a stable price or
latency benchmark.

The original v1.0.3 record ran before Claude compatibility isolation was added
and is retained in the research report only as contaminated historical
evidence. The accepted v1.0.6 candidate `results.json` is run
`571d25be-476d-4490-ab40-25dad9c521b0`: all four cue-free cases passed in
530.265 seconds of aggregate case time with `$1.077048` in client cost fields,
and their persisted spawn events covered all seven roles. The artifact records
the source policy override as v1.0.6 and the then-installed global policy as
v1.0.5 rather than conflating candidate behavior with installation state.

Headless `grok -p` disconnects when `exit_plan_mode` reaches the interactive
approval surface. A passing headless case therefore requires the ordered exit
call plus `plan_mode.json` with `state=Active` and
`awaiting_plan_approval=true`; it does not simulate a human approval click.

## Non-goals

- Interactive `/plan` slash-command transport; its mandatory verifier rule is
  locked by policy/static tests, while live cases exercise native entry through
  `enter_plan_mode`
- Multi-model price arbitrage
- CI by default (needs credentials + spend); gate with a manual or scheduled job

## Interpreting failures

| Symptom | Likely cause |
|---|---|
| install incomplete | Run `install/AGENT-INSTALL.md` first |
| Claude compatibility cell enabled | Re-run the installer and set all six `[compat.claude]` cells to false |
| Claude agent/plugin not denied | Add every inspect-discovered Claude agent to `[subagents.toggle]` and every Claude plugin to `[plugins] disabled` |
| Claude marker or hook event in a session | The runtime was contaminated despite preflight; reject the result and inspect the persisted session before retrying |
| installed policy version mismatch | Upgrade the installed managed policy block from the same ref before live testing |
| first tool is not `enter_plan_mode` | The native Plan gate is missing, stale, or ignored |
| no Plan file | Grok entered Plan Mode but did not write session `plan.md` |
| no readiness `READY` before exit | Mandatory `plan-verifier` dispatch or event ordering failed |
| approval-bypass writes files | Automatic permission grant was treated as user Plan approval, or the native gate was bypassed |
| missing cue-free role | Policy routing gate was ignored, stale, or the task was misclassified |
| wrong `capability_mode` | Role TOML not loaded; check `~/.grok/roles/<role>.toml` |
| missing READY/REVISE | plan-verifier prompt drift or role body broken |

## Related

Static contracts: `python3 -m unittest discover -s tests -v`

Research and ablation evidence: [`../../docs/approval-gate-enforcement-research.md`](../../docs/approval-gate-enforcement-research.md)
