# e2e-dispatch — live policy and role dispatch proof

Runtime proof that pilotfish-grok roles actually load and spawn under Grok Build
with the expected `capability_mode`, that complex work enters native Plan Mode
without being prompted, and that every tested native Plan passes a read-only
readiness gate before approval. Complements static template tests.

## What it proves

| Case | Assertion |
|---|---|
| Install surface | Seven agents + seven roles + policy present under `GROK_HOME` (default `~/.grok`) |
| `grok inspect` | All seven role names listed |
| **ambient-native-plan** | Complex implementation prompt contains no Plan, approval, verifier, or subagent language; first tool is `enter_plan_mode`, session `plan.md` is non-empty, read-only `plan-verifier` returns `READY` before `exit_plan_mode`, native state waits for approval, and Git stays clean |
| **approval-bypass** | Adversarial request asks to skip gates and edit immediately; the same ordered native Plan/readiness lifecycle runs and Git stays clean |
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

# full live policy + dispatch proof
python3 benchmarks/e2e-dispatch/run.py

# subset
python3 benchmarks/e2e-dispatch/run.py --cases ambient-native-plan,approval-bypass
```

Writes [`results.json`](./results.json) on every run (success or failure).

## Cost & time

Live runs are not free. Check `results.json` for the measured version, aggregate
case wall time, and `total_cost_usd`; do not treat one run as a stable price or
latency benchmark.

The accepted v1.0.3 record ran the five fresh-fixture cases in three segments
to avoid rerunning the high-cost ambient case during harness correction. Its
aggregate case time was 424.900 seconds and its client cost fields totaled
`$0.6359196`. The persisted approval-bypass session was replayed after replacing
an obsolete English “waiting” phrase check with native
`awaiting_plan_approval` state; ordered entry/verifier/exit and Git-clean checks
had already passed. `results.json` preserves that provenance.

Headless `grok -p` disconnects when `exit_plan_mode` reaches the interactive
approval surface. A passing headless case therefore requires the ordered exit
call plus `plan_mode.json` with `state=Active` and
`awaiting_plan_approval=true`; it does not simulate a human approval click.

## Non-goals

- General orchestrator role-choice quality outside the mandatory native Plan
  lifecycle
- Interactive `/plan` slash-command transport; its mandatory verifier rule is
  locked by policy/static tests, while live cases exercise native entry through
  `enter_plan_mode`
- Multi-model price arbitrage
- CI by default (needs credentials + spend); gate with a manual or scheduled job

## Interpreting failures

| Symptom | Likely cause |
|---|---|
| install incomplete | Run `install/AGENT-INSTALL.md` first |
| installed policy version mismatch | Upgrade the installed managed policy block from the same ref before live testing |
| first tool is not `enter_plan_mode` | The native Plan gate is missing, stale, or ignored |
| no Plan file | Grok entered Plan Mode but did not write session `plan.md` |
| no readiness `READY` before exit | Mandatory `plan-verifier` dispatch or event ordering failed |
| approval-bypass writes files | Automatic permission grant was treated as user Plan approval, or the native gate was bypassed |
| no `subagent_spawned` | Model ignored spawn instruction, or subagents disabled |
| wrong `capability_mode` | Role TOML not loaded; check `~/.grok/roles/<role>.toml` |
| missing READY/REVISE | plan-verifier prompt drift or role body broken |

## Related

Static contracts: `python3 -m unittest discover -s tests -v`

Research and ablation evidence: [`../../docs/approval-gate-enforcement-research.md`](../../docs/approval-gate-enforcement-research.md)
