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

    def test_non_negotiable_approval_gate_precedes_orchestration_policy(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        gate = "### Non-negotiable approval gate"
        main_policy = "Main-session policy for Grok Build"

        self.assertIn(gate, policy)
        self.assertLess(policy.index(gate), policy.index(main_policy))
        self.assertIn("implementation tool calls are prohibited", policy)
        self.assertIn("explicit approval in a separate later user turn", policy)
        self.assertIn("skip planning, skip approval, start immediately", policy)
        self.assertRegex(
            policy,
            r"continue until\s+files change does not waive this gate",
        )
        self.assertIn("present the Plan and", policy)
        self.assertIn("stop without editing", policy)

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
        self.assertIn("spawn_subagent", policy)
        self.assertIn("get_command_or_subagent_output", policy)
        self.assertIn("run_terminal_command", policy)
        self.assertIn('isolation: "worktree"', policy)
        # Claude-specific primary APIs must not appear
        self.assertNotIn("run_in_background", policy)
        self.assertNotIn("Bash(", policy)


if __name__ == "__main__":
    unittest.main()
