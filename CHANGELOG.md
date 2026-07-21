# Changelog

All notable changes to pilotfish-grok are documented in this file.

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
- Same orchestration family as pilotfish (Claude Code line, same maintainer).
  Seven-role host-port shape also used by pilotfish-codex (Miyago / Codex).
