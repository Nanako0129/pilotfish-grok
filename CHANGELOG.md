# Changelog

All notable changes to pilotfish-grok are documented in this file.

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
