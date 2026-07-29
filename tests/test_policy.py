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

    def test_clear_cue_free_work_defaults_to_matching_roles(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        dispatch = " ".join(policy[policy.index("### Dispatch") :].split())

        self.assertIn("even when the user does not mention agents", dispatch)
        self.assertIn(
            "MUST spawn `scout` before repository search for an unknown file or symbol",
            dispatch,
        )
        self.assertIn("exact-text lookup whose file path is unknown", dispatch)
        self.assertIn(
            "MUST spawn `mech-executor` before fully specified multi-file mechanical work",
            dispatch,
        )
        self.assertIn(
            "MUST spawn `executor` before bounded non-security implementation requiring "
            "local judgment",
            dispatch,
        )
        self.assertIn(
            "must not silently convert it to main-session work",
            dispatch,
        )
        self.assertIn("Other delegation remains optional", dispatch)

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
            "matching-role-optional rule, single-unknown-bug exception, and "
            "failed-attempt takeover rule do not waive",
            "If the spawn is unavailable or fails, stop without source mutation "
            "or implementation tools",
            "If implementation attempts fail, stop or retask through `security-executor`",
            "neither the main session nor another role may take over the slice",
        ):
            self.assertIn(phrase, gate_text)
        self.assertIn(
            "The main session may take over only non-security-sensitive work; "
            "a security-sensitive slice must stop or be retasked through `security-executor`",
            " ".join(policy.split()),
        )

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

    def test_calibrated_adjudication_and_bounded_long_run_policy(self) -> None:
        policy = " ".join(POLICY.read_text(encoding="utf-8").split())

        self.assertIn("`CONFIRMED`, `REFUTED`, or `INCONCLUSIVE`", policy)
        for phrase in (
            "P0/P1 label requires reproducible evidence",
            "introduced P2 regression remains blocking",
            "fix other P2 findings only when bounded",
            "inside approved scope",
            "A documented regrade may use the verifier's cited evidence",
            "P3/P4 are non-blocking advisories",
            "`INCONCLUSIVE` gets one retry only",
        ):
            self.assertIn(phrase, policy)
        self.assertRegex(
            policy,
            r"announce `AUTO` or `ASK`.*"
            r"do not toggle Grok's `/auto` or permission mode",
        )
        self.assertRegex(
            policy,
            r"`AUTO` permits only approved-scope reversible work.*"
            r"no version-control action.*external-mutation.*spend authority",
        )
        self.assertRegex(
            policy,
            r"`PAUSED_NEEDS_USER`.*Headless execution emits that pause and exits.*"
            r"Only the main session asks, never a child",
        )
        self.assertRegex(
            policy,
            r"recovery budget and severity rules below apply to every verification run.*"
            r"P0 freezes its slice and dependents.*"
            r"Blocking P1/P2 recovery shares at most five materially changed "
            r"fix/reverify passes.*"
            r"passes 1-2 are normal and 3-5 are recovery.*"
            r"external evidence or prerequisites.*immediately preceding verifier's "
            r"verdict or output alone is not new evidence.*"
            r"tracked and staged diff.*untracked input paths plus content.*"
            r"input submodule's HEAD plus recursive working-tree content.*"
            r"artifact is explicitly the sole deliverable.*"
            r"Never reverify the same complete identity.*"
            r"`PAUSED_VERIFICATION`.*"
            r"blocking P2 counts against that shared budget.*"
            r"P3/P4 get no dedicated loop",
        )
        self.assertIn("introduced P2 regression remains blocking", policy)
        self.assertIn("headless likely-long run without an explicit mode", policy)

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
