from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "templates" / "agents"
POLICY = ROOT / "templates" / "rules.pilotfish-grok.md"
BASH_CAPABLE_ROLES = (
    "executor",
    "mech-executor",
    "security-executor",
    "verifier",
)


class PolicyTests(unittest.TestCase):
    def test_version_matches_policy_stamp(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        policy = POLICY.read_text(encoding="utf-8")
        self.assertIn(f"<!-- pilotfish-grok v{version} -->", policy)

    def test_policy_routes_by_role_instead_of_model(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        # No concrete Grok model product ids in policy
        self.assertNotRegex(policy, r"grok-\d")
        self.assertNotIn("gpt-", policy)
        self.assertNotIn("haiku", policy)
        self.assertNotIn("sonnet", policy)
        self.assertNotIn("opus", policy)

        self.assertIn("smallest useful execution shape", policy)
        self.assertIn("Keep a single unknown bug", policy)
        self.assertIn("spawn_subagent", policy)
        self.assertIn("background: true", policy)

    def test_non_negotiable_native_plan_gate_precedes_orchestration_policy(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        gate = "### Non-negotiable native Plan gate"
        main_policy = "Main-session policy for Grok Build"

        self.assertIn(gate, policy)
        self.assertLess(policy.index(gate), policy.index(main_policy))
        gate_text = " ".join(
            policy[policy.index(gate) : policy.index(main_policy)].split()
        )
        self.assertIn("native Grok Plan Mode", gate_text)
        self.assertIn("first tool call MUST be `enter_plan_mode`", gate_text)
        self.assertIn("before repository discovery or implementation", gate_text)
        self.assertIn("including user-initiated `/plan` sessions", gate_text)
        self.assertIn(
            "Treat every security-sensitive implementation as risky for this gate",
            gate_text,
        )
        self.assertIn(
            "spawn a fresh `plan-verifier` with `background: false`", gate_text
        )
        self.assertIn("exact target readiness-unit ID and kind", gate_text)
        self.assertIn("`## Target readiness unit` block", gate_text)
        self.assertIn(
            "Only `READY` verdicts for every required readiness unit", gate_text
        )
        self.assertIn("the envelope and current slice for large work", gate_text)
        self.assertIn("On `REVISE`", gate_text)
        self.assertIn("Automatic permission grants", gate_text)
        self.assertIn("always-approve or `bypassPermissions`", gate_text)
        self.assertIn("implementation tool calls remain prohibited", gate_text)
        self.assertIn(
            "explicitly approves the verified Plan in a later interaction", gate_text
        )
        self.assertIn("skip planning, skip approval, start immediately", gate_text)
        self.assertRegex(
            gate_text,
            r"continue until files change, does not waive this gate",
        )
        self.assertIn("unattended run must stop", gate_text)

    def test_security_execution_gate_is_front_loaded_and_fail_closed(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        security_gate = "Every approved security-sensitive execution slice"
        main_policy = "Main-session policy for Grok Build"

        self.assertLess(policy.index("### Non-negotiable native Plan gate"), policy.index(security_gate))
        self.assertLess(policy.index(security_gate), policy.index(main_policy))
        gate_text = " ".join(
            policy[policy.index(security_gate) : policy.index(main_policy)].split()
        )
        for phrase in (
            "Findings from `security-reviewer` on a program envelope remain constraints "
            "on each affected slice, but the envelope itself is not an executable contract",
            "Before any post-approval source mutation or implementation tool call "
            "for that slice, the main session MUST successfully spawn `security-executor`",
            "every role other than `security-executor` MUST NOT implement that slice directly",
            "direct-work allowance, dispatch brake, coordination-cost heuristic, "
            "cue-free routing gate, single-unknown-bug exception, and "
            "failed-attempt retry rule do not waive",
            "If the spawn is unavailable or fails, stop without source mutation "
            "or implementation tools",
            "If implementation attempts fail, stop or retask through `security-executor`",
            "neither the main session nor another role may take over the slice",
        ):
            self.assertIn(phrase, gate_text)
        self.assertIn(
            "A security-sensitive slice must stop or be retasked through "
            "`security-executor`",
            " ".join(policy.split()),
        )

    def test_cue_free_dispatch_gate_requires_all_seven_roles(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        gate = " ".join(
            policy[
                policy.index("### Cue-free dispatch gate") : policy.index(
                    "For large, ambiguous, architectural"
                )
            ].split()
        )

        self.assertIn(
            "even when the user never mentions agents, delegation, or this workflow",
            " ".join(policy.split()),
        )
        for phrase in (
            "apply every matching gate in phase order",
            "Only `security-executor` may implement that slice",
            "do not select `mech-executor` or `executor` for it",
            "spawn `scout` before any repository search that must locate an unknown file",
            "For non-security work, spawn `mech-executor` before a fully specified",
            "For non-security work, spawn `executor` before a bounded implementation",
            "spawn a fresh `verifier`",
            "routing gates, not prompt keywords",
            "cannot turn matching work into main-session execution",
            "do not silently perform its bounded work in the main session",
        ):
            self.assertIn(phrase, gate)

    def test_native_plan_lifecycle_requires_readiness_before_exit(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        lifecycle = policy[policy.index("| Discovery |") : policy.index("### Dispatch")]

        self.assertIn("Enter native Plan Mode first", lifecycle)
        self.assertIn("Mandatory fresh read-only `plan-verifier`", lifecycle)
        self.assertIn(
            "`READY` for the envelope and current slice unlocks `exit_plan_mode`",
            lifecycle,
        )
        self.assertIn(
            "mandatory `plan-verifier` readiness gate is not an optional delegation",
            policy,
        )
        for phrase in (
            "program envelope",
            "outcome, non-goals, scope",
            "proves the slice outcome",
            "next executable slice",
            "keep later slices to stable IDs",
            "Blocker:",
            "Evidence:",
            "Minimum revision:",
            "Acceptance check:",
            "two automatic `REVISE` verdicts for the same unit",
            "pause it and ask the user",
            "findings and dispositions into the Plan",
            "every initial review or fresh re-review of a security-affected unit",
            "do not rely on the Plan text alone for that handoff",
            "assign stable IDs to the affected program envelope",
            "Include every exact affected unit ID in its brief",
            "If an affected ID changes or is added, repeat security review",
        ):
            self.assertIn(phrase, policy)
        for phrase in (
            "two consecutive `REFUTED` verdicts",
            "fix the same claim",
            "stop automatic fix-and-reverify cycling",
            "the cap is not `CONFIRMED`",
            "user-directed continuation remains allowed",
            "substantially unchanged implementation",
        ):
            self.assertIn(phrase, " ".join(policy.split()))

    def test_agent_names_match_filenames_and_remain_leaf_roles(self) -> None:
        for path in AGENTS_DIR.glob("*.md"):
            content = path.read_text(encoding="utf-8")
            match = re.search(r"(?m)^name:\s*(\S+)\s*$", content)
            self.assertIsNotNone(match, path)
            self.assertEqual(path.stem, match.group(1))
            self.assertIn("Never spawn further subagents", content)

    def test_long_running_roles_use_exact_context_handoff(self) -> None:
        for role in BASH_CAPABLE_ROLES:
            content = (AGENTS_DIR / f"{role}.md").read_text(encoding="utf-8")
            self.assertNotIn("launch it detached", content)
            self.assertIn("Never detach", content)
            self.assertIn("exact command", content)
            self.assertIn("absolute working directory", content)
            self.assertIn("completion criterion", content)

    def test_policy_uses_grok_tool_vocabulary(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        self.assertIn("enter_plan_mode", policy)
        self.assertIn("exit_plan_mode", policy)
        self.assertIn("spawn_subagent", policy)
        self.assertIn("get_command_or_subagent_output", policy)
        self.assertIn("run_terminal_command", policy)
        self.assertIn('isolation: "worktree"', policy)
        # Claude-specific primary APIs must not appear
        self.assertNotIn("run_in_background", policy)
        self.assertNotIn("Bash(", policy)


if __name__ == "__main__":
    unittest.main()
