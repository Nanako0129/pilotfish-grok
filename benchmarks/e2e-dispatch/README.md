# e2e-dispatch — live role dispatch proof

Runtime proof that pilotfish-grok roles actually load and spawn under Grok Build
with the expected `capability_mode`. Complements static template tests.

## What it proves

| Case | Assertion |
|---|---|
| Install surface | Seven agents + seven roles + policy present under `GROK_HOME` (default `~/.grok`) |
| `grok inspect` | All seven role names listed |
| **scout** | `spawn_subagent` → `subagent_spawned` with `capability_mode=read-only`; finds marker file |
| **plan-verifier** | Spawn with `read-only`; child/parent output contains `READY` or `REVISE` only vocabulary |
| **verifier** | Spawn with `execute`; child/parent output contains `CONFIRMED` or `REFUTED` |

Proof source for capability: parent session `updates.jsonl` event
`sessionUpdate=subagent_spawned` fields `subagent_type`, `role`,
`capability_mode`, `model`.

## Requirements

- Grok Build **≥ 0.2.106** on `PATH`
- Authenticated (`grok login` or `XAI_API_KEY`)
- pilotfish-grok already installed into `~/.grok` (or `$GROK_HOME`)
- Network access (live cases call the model)

## Run

```sh
# install + inspect only (no model spend)
python3 benchmarks/e2e-dispatch/run.py --skip-live

# full live dispatch (default: scout, plan-verifier, verifier)
python3 benchmarks/e2e-dispatch/run.py

# subset
python3 benchmarks/e2e-dispatch/run.py --cases scout,verifier
```

Writes [`results.json`](./results.json) on every run (success or failure).

## Cost & time

Live runs are not free. A full three-case pass on grok-4.5 is typically on the
order of **tens of seconds per case** and **fractions of a dollar** total; check
`total_cost_usd` in `results.json` for the measured run.

## Non-goals

- Full orchestrator judgment quality (whether the main session *chooses* the
  right role without being told)
- Multi-model price arbitrage
- CI by default (needs credentials + spend); gate with a manual or scheduled job

## Interpreting failures

| Symptom | Likely cause |
|---|---|
| install incomplete | Run `install/AGENT-INSTALL.md` first |
| no `subagent_spawned` | Model ignored spawn instruction, or subagents disabled |
| wrong `capability_mode` | Role TOML not loaded; check `~/.grok/roles/<role>.toml` |
| missing READY/REVISE | plan-verifier prompt drift or role body broken |

## Related

Static contracts: `python3 -m unittest discover -s tests -v`
