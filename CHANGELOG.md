# Changelog

All notable changes to pilotfish-grok are documented in this file.

## [1.0.5] — 2026-07-28

Require approved security-sensitive readiness units, including units reviewed
by `security-reviewer`, to execute only through a successfully spawned
`security-executor`. Direct implementation and orchestration exceptions cannot
waive this boundary; failed or unavailable spawns stop before mutation.

## [1.0.4] — 2026-07-23

Bound Plan review loops with program envelopes and independently approvable
execution slices. Review the envelope and next executable slice first; unrelated
downstream slices do not block approval. `READY` is bare, structured `REVISE`
includes evidence and a closure check, and two automatic revisions for one unit
pause it for user direction. Security findings enter the Plan before the first
readiness review for an affected unit. Two consecutive `REFUTED` verdicts for
one materially revised completed-work claim likewise stop automatic
fix-and-reverify cycling without becoming `CONFIRMED`.

## [1.0.3] — 2026-07-22

### Changed

- Require large, ambiguous, architectural, risky, and explicitly plan-first
  work to enter native Grok Plan Mode before repository discovery. If native
  Plan Mode is denied or unavailable, the orchestrator now fails closed instead
  of falling back to a prose-only Plan.
- Make the fresh read-only `plan-verifier` readiness pass mandatory for every
  native Plan Mode session, including user-initiated `/plan`. `REVISE` returns
  the Plan to the main session; only `READY` unlocks `exit_plan_mode` and the
  native approval surface.
- Clarify that always-approve and `bypassPermissions` authorize tools but do not
  constitute user approval of an implementation Plan.
- Make pure Grok isolation part of the install contract. All six
  `[compat.claude]` cells are false, Claude agent names discovered by inspect
  receive false `[subagents.toggle]` entries, and Claude plugin names are merged
  into `[plugins] disabled` without modifying `~/.claude/`.

### Added

- An `ambient-native-plan` live regression whose complex implementation prompt
  contains no Plan or role hints. Ordered session events must prove
  `enter_plan_mode` first, a non-empty session `plan.md`, read-only
  `plan-verifier` `READY`, and `exit_plan_mode`, with no source writes.
- Ordered tool/subagent event parsing that also strengthens the adversarial
  `approval-bypass` case with the same native Plan/readiness requirements.
- Fail-closed E2E contamination checks. Preflight validates all three Claude
  control planes; each model process receives six false compatibility
  environment variables; persisted sessions reject Claude path markers and
  all hook execution events.
- A `claude-isolation` live regression that calls the actual spawn boundary and
  requires uppercase Claude `Explore` to be disabled, Claude plugin agent
  `codex-rescue` to be unavailable, and zero foreign-agent spawn events.

### Notes

- The earlier segmented result was reclassified as Claude-contaminated after
  persisted evidence showed a 15,835-character Claude skill reminder and a
  successful Claude `SessionStart` hook. It remains historical evidence in the
  research report but is superseded for release acceptance.
- Measured fresh monolithic six-case pass on Grok 0.2.106 after isolation:
  no-hint ambient Plan entry, adversarial `REVISE` → fresh `READY`, Git clean,
  behavioral rejection of Claude agents/plugins, expected native role
  capabilities, zero Claude context markers, and zero hook events in every
  session. Aggregate case time was 593.745s with `$0.8523472` in client cost
  fields; run ID `ad46a576-544b-4a97-8379-026893b732c3`.
- Harness-only corrections now accept decorated verdict forms including
  `VERDICT: **REVISE**`, retain the adversarial 28-turn/600-second budget, and
  use native `awaiting_plan_approval` state instead of one English phrase.
- A fresh completed-work verifier independently reran 22 offline/install
  tests, replayed the native Plan and Claude-denial evidence, reconciled the
  six-case record, and returned `CONFIRMED`.
- A fresh completed-work `verifier` independently reran the 20-test suite,
  install inspection, persisted session replay, negative gate probes, cost
  arithmetic, and installed-template comparison, then returned `CONFIRMED`.

## [1.0.2] — 2026-07-21

### Fixed

- Front-load a non-negotiable approval gate in the global policy. Large,
  architectural, risky, and explicitly plan-first work cannot write source or
  call implementation tools until the main session presents a Plan and receives
  explicit approval in a separate later user turn. Requests to skip planning,
  skip approval, start immediately, or continue until files change do not waive
  the gate.
- Require the installed policy stamp to match repository `VERSION` before E2E,
  preventing a stale global policy from producing misleading live results.

### Added

- Live `approval-bypass` regression coverage under `benchmarks/e2e-dispatch/`.
  The case deliberately enables write permissions, requests an immediate OAuth2
  rewrite, and asserts a clean Git tree, Plan and approval language, and no
  write-capable role spawn.
- A versioned research report documenting the 28-session instruction-surface
  comparison, ablations, interpretation, and resulting policy decision.

### Notes

- Measured local full pass on Grok 0.2.106: approval-bypass plus `scout`,
  `plan-verifier`, and `verifier` all passed in 89.958s aggregate wall time with
  `$0.2358788` in total client cost fields.

## [1.0.1] — 2026-07-21

### Added

- Live e2e dispatch proof under `benchmarks/e2e-dispatch/`: headless `grok -p`
  spawns `scout`, `plan-verifier`, and `verifier`, asserts
  `subagent_spawned.capability_mode` from session `updates.jsonl`, and records
  measured cost/time in `results.json`.
- Optional unittest hooks (`tests/test_e2e_dispatch.py`): install-only probe by
  default when Grok + install are present; full live run when
  `PILOTFISH_GROK_E2E=1`.

### Notes

- Measured local live pass (Grok 0.2.106): three cases OK in ~51s wall,
  ~$0.18 total; scout/plan-verifier `read-only`, verifier `execute`.

## [1.0.0] — 2026-07-21

### Added

- Initial Grok Build port of Pilotfish phase-aware orchestration.
- Seven named roles (no Claude `Explore` shadow): `scout`, `plan-verifier`,
  `security-reviewer`, `mech-executor`, `executor`, `verifier`,
  `security-executor`.
- Dual install surface: `~/.grok/agents/*.md` + `~/.grok/roles/*.toml` for
  contracts, `capability_mode`, and `reasoning_effort`.
- Model-free orchestration policy in `~/.grok/rules/pilotfish-grok.md` with
  `pilotfish-grok` markers and Grok tool vocabulary (`spawn_subagent`,
  `background`, `run_terminal_command`, worktree isolation).
- Agent-guided install runbook with approval gate, backups, dual-harness
  warnings (does not modify `~/.claude/`), and uninstall steps.
- Static contract tests for templates, policy, and installer wording.
- Design doc covering capability mapping, plan-mode gap, and deliberately left
  out items.

### Notes

- v1.0 targets effort-first routing on single-model catalogs; optional
  `[subagents.models]` pins are documented for future multi-model layouts.
- Same orchestration family as pilotfish (Claude Code) and the seven-role
  host-port shape used by pilotfish-codex (Codex).
