from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "templates" / "agents"
ROLES_DIR = ROOT / "templates" / "roles"

ROUTING = {
    "scout": ("read-only", "low"),
    "plan-verifier": ("read-only", "medium"),
    "security-reviewer": ("read-only", "high"),
    "mech-executor": ("all", "low"),
    "executor": ("all", "medium"),
    "verifier": ("execute", "medium"),
    "security-executor": ("all", "high"),
}


def load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def frontmatter_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?m)^name:\s*(\S+)\s*$", text)
    if not match:
        raise AssertionError(f"missing name frontmatter in {path}")
    return match.group(1)


class TemplateContractTests(unittest.TestCase):
    def test_complete_seven_role_routing_map(self) -> None:
        agent_files = {path.stem: path for path in AGENTS_DIR.glob("*.md")}
        role_files = {path.stem: path for path in ROLES_DIR.glob("*.toml")}

        self.assertEqual(len(ROUTING), 7)
        self.assertEqual(set(agent_files), set(ROUTING))
        self.assertEqual(set(role_files), set(ROUTING))
        self.assertNotIn("Explore", agent_files)
        self.assertNotIn("explore", agent_files)

        for role, (capability, effort) in ROUTING.items():
            agent_name = frontmatter_name(agent_files[role])
            self.assertEqual(agent_name, role)

            role_cfg = load_toml(role_files[role])
            self.assertEqual(role_cfg["default_capability_mode"], capability)
            self.assertEqual(role_cfg["reasoning_effort"], effort)

            body = agent_files[role].read_text(encoding="utf-8")
            self.assertIn("cannot delegate", body.lower())
            self.assertIn("Never spawn further subagents", body)
            self.assertIn("model: inherit", body)

    def test_review_and_execution_boundaries_stay_separate(self) -> None:
        plan = (AGENTS_DIR / "plan-verifier.md").read_text(encoding="utf-8")
        outcome = (AGENTS_DIR / "verifier.md").read_text(encoding="utf-8")
        security_review = (AGENTS_DIR / "security-reviewer.md").read_text(
            encoding="utf-8"
        )
        security_execute = (AGENTS_DIR / "security-executor.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("READY", plan)
        self.assertIn("REVISE", plan)
        self.assertIn("shared outcome, scope, non-goals", plan)
        self.assertIn("explicit outcome, scope and non-goals", plan)
        self.assertIn("acceptance that proves the slice outcome", plan)
        self.assertNotIn("CONFIRMED", plan)
        self.assertNotIn("REFUTED", plan)

        self.assertIn("CONFIRMED", outcome)
        self.assertIn("REFUTED", outcome)
        self.assertIn("INCONCLUSIVE", outcome)
        self.assertNotIn("READY", outcome)
        self.assertNotIn("REVISE", outcome)

        self.assertIn("security-executor", security_review)
        self.assertIn("security-reviewer", security_execute)
        self.assertIn("pre-approval", security_review.lower())

    def test_verifier_contract_is_calibrated_and_structured(self) -> None:
        outcome = (AGENTS_DIR / "verifier.md").read_text(encoding="utf-8")
        normalized = " ".join(outcome.split())

        self.assertIn("exact completed-work claim and acceptance", normalized)
        self.assertRegex(
            normalized,
            r"REFUTED.*at least one reproducible P0-P2 finding",
        )
        self.assertIn(
            "Regressions caused by the reviewed implementation are claim-relevant",
            normalized,
        )
        self.assertIn("For every finding or advisory under any verdict", normalized)
        self.assertIn(
            "any reproducible high-impact user/system failure that does not meet P0",
            normalized,
        )
        self.assertIn(
            "sufficient for every required acceptance condition",
            normalized,
        )
        self.assertIn("List each condition checked and its evidence/result", normalized)
        self.assertIn(
            "REFUTED takes precedence when a reproducible P0-P2 blocker coexists",
            normalized,
        )
        self.assertIn(
            "any unevaluated required acceptance condition makes the verdict INCONCLUSIVE",
            normalized,
        )
        self.assertRegex(
            normalized,
            r"Priority P0-P4.*Confidence.*Evidence.*Expected.*Actual.*Recheck",
        )
        self.assertIn(
            "P3/P4 are non-blocking advisories and cannot by themselves produce REFUTED",
            normalized,
        )
        self.assertRegex(
            normalized,
            r"INCONCLUSIVE.*reason, missing evidence, and retry condition",
        )
        self.assertRegex(
            normalized,
            r"Priority measures real user/system impact.*"
            r"failed acceptance that is bounded/recoverable is P2 unless it "
            r"independently meets P0 or high-impact P1 criteria",
        )
        self.assertNotIn("assume it is broken", outcome)
        self.assertNotIn("Do not trust", outcome)

    def test_bash_capable_roles_use_exact_context_handoff(self) -> None:
        for role in (
            "mech-executor",
            "executor",
            "verifier",
            "security-executor",
        ):
            content = (AGENTS_DIR / f"{role}.md").read_text(encoding="utf-8")
            self.assertNotIn("launch it detached", content)
            self.assertIn("Never detach", content)
            self.assertIn("exact command", content)
            self.assertIn("absolute working directory", content)
            self.assertIn("completion criterion", content)

    def test_config_keeps_main_model_user_controlled(self) -> None:
        config = load_toml(ROOT / "templates" / "config.snippet.toml")
        self.assertTrue(config["subagents"]["enabled"])
        self.assertFalse(config["subagents"]["toggle"]["Explore"])
        self.assertEqual(
            config["compat"]["claude"],
            {
                "skills": False,
                "rules": False,
                "agents": False,
                "mcps": False,
                "hooks": False,
                "sessions": False,
            },
        )
        self.assertNotIn("default", config.get("models", {}))
        self.assertNotIn("default_reasoning_effort", config.get("models", {}))
        # No forced model pins in the live snippet tables
        self.assertNotIn("models", config.get("subagents", {}))

    def test_policy_version_and_roster(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        policy = (ROOT / "templates" / "rules.pilotfish-grok.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"<!-- pilotfish-grok v{version} -->", policy)
        self.assertEqual(policy.count("pilotfish-grok:begin"), 1)
        self.assertEqual(policy.count("pilotfish-grok:end"), 1)

        for role in ROUTING:
            self.assertRegex(policy, rf"\| `{re.escape(role)}` \|")

        self.assertNotIn("| Model |", policy)
        self.assertNotIn("| Effort |", policy)
        self.assertIn("Discovery", policy)
        self.assertIn("Plan", policy)
        self.assertIn("Approval", policy)
        self.assertIn("Execution", policy)
        self.assertIn("Verification", policy)
        self.assertIn("spawn_subagent", policy)
        self.assertIn("background: true", policy)
        self.assertIn("isolation: \"worktree\"", policy)
        self.assertIn("run_terminal_command", policy)
        self.assertIn("delegation-planning layer", policy)
        self.assertIn("Never swap `plan-verifier` and `verifier`", policy)
        self.assertIn("first tool call MUST be", policy)
        self.assertIn(
            "Only `READY` verdicts for every required readiness unit", policy
        )
        self.assertNotIn("run_in_background", policy)
        self.assertNotIn("Bash(", policy)

    def test_installer_covers_grok_global_install(self) -> None:
        installer = (ROOT / "install" / "AGENT-INSTALL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Grok Build **0.2.106 or newer**", installer)
        self.assertIn("grok inspect", installer)
        self.assertIn("~/.grok/agents/", installer)
        self.assertIn("~/.grok/roles/", installer)
        self.assertIn("~/.grok/rules/pilotfish-grok.md", installer)
        self.assertIn("config.toml.pilotfish-grok-*", installer)
        self.assertIn("Do not write anything until the user explicitly approves", installer)
        self.assertIn("Never modify `~/.claude/`", installer)
        self.assertIn("[subagents.toggle]", installer)
        self.assertIn("[plugins] disabled", installer)
        self.assertIn("all six `[compat.claude]`", installer)
        self.assertIn("Uninstall", installer)

        for role in ROUTING:
            self.assertRegex(installer, rf"`{re.escape(role)}`")

    def test_readme_matches_seven_role_contract(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("seven", readme.lower())
        self.assertIn("Explore", readme)
        self.assertIn("~/.grok/", readme)

        for role in ROUTING:
            self.assertIn(f"`{role}`", readme)

        self.assertIn("enter_plan_mode", readme)
        self.assertIn("Mandatory fresh read-only `plan-verifier`", readme)
        self.assertIn("INCONCLUSIVE", readme)

    def test_design_explains_grok_adaptation_boundary(self) -> None:
        design = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
        self.assertIn("capability_mode", design)
        self.assertIn("Explore", design)
        self.assertIn("policy names roles but never embeds", design)
        self.assertIn("plan mode", design.lower())
        self.assertIn("Plan readiness is the deliberate exception", design)


if __name__ == "__main__":
    unittest.main()
