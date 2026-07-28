"""Optional e2e harness hooks.

Default unit suite stays offline. Live dispatch is gated by
PILOTFISH_GROK_E2E=1. Install-only probe runs when grok + install are present
unless PILOTFISH_GROK_E2E_SKIP_INSTALL=1.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "benchmarks" / "e2e-dispatch" / "run.py"
RESULTS = ROOT / "benchmarks" / "e2e-dispatch" / "results.json"


def populate_candidate_home(home: Path, installed_home: Path | None = None) -> None:
    home.mkdir(parents=True, exist_ok=True)
    if installed_home and (installed_home / "config.toml").is_file():
        shutil.copy2(installed_home / "config.toml", home / "config.toml")
    shutil.copytree(ROOT / "templates" / "agents", home / "agents")
    shutil.copytree(ROOT / "templates" / "roles", home / "roles")
    (home / "rules").mkdir()
    shutil.copy2(
        ROOT / "templates" / "rules.pilotfish-grok.md",
        home / "rules" / "pilotfish-grok.md",
    )


def load_runner_module():
    spec = importlib.util.spec_from_file_location("pilotfish_grok_e2e", RUNNER)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class E2EDispatchTests(unittest.TestCase):
    def test_runner_exists_and_is_executable_doc(self) -> None:
        self.assertTrue(RUNNER.is_file())
        text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("subagent_spawned", text)
        self.assertIn("capability_mode", text)
        self.assertIn("ambient-native-plan", text)
        self.assertIn("approval-bypass", text)
        self.assertIn("cue-free-discovery", text)
        self.assertIn("cue-free-mechanical", text)
        self.assertIn("cue-free-judgment", text)
        self.assertIn("cue-free-security", text)
        self.assertIn("claude-isolation", text)
        self.assertIn("enter_plan_mode", text)
        self.assertIn("exit_plan_mode", text)
        self.assertIn("plan.md", text)
        self.assertIn("ready_before_exit", text)
        self.assertIn("max_turns=28", text)
        self.assertIn("timeout_seconds=600", text)
        self.assertIn("git status", text)
        self.assertIn("assert_claude_isolation_config", text)
        self.assertIn("assert_session_claude_isolated", text)
        self.assertIn("GROK_CLAUDE_SKILLS_ENABLED", text)
        self.assertIn("--skip-live", text)

    def test_session_isolation_rejects_claude_context_and_hooks(self) -> None:
        runner = load_runner_module()
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp)
            (session / "chat_history.jsonl").write_text(
                json.dumps(
                    {
                        "type": "user",
                        "content": "/Users/nanako/.claude/skills/example/SKILL.md",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (session / "updates.jsonl").write_text("", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "Claude compatibility leaked"):
                runner.assert_session_claude_isolated(session)

            (session / "chat_history.jsonl").write_text("{}\n", encoding="utf-8")
            (session / "updates.jsonl").write_text(
                json.dumps(
                    {
                        "params": {
                            "update": {
                                "sessionUpdate": "hook_execution",
                                "source": {"plugin_name": "ponytail"},
                                "runs": [{"name": "post-tool"}],
                            }
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                AssertionError, "executed 1 Claude startup/runtime hooks"
            ):
                runner.assert_session_claude_isolated(
                    session, {"claude", "ponytail"}
                )
            (session / "updates.jsonl").write_text(
                json.dumps(
                    {
                        "params": {
                            "update": {
                                "sessionUpdate": "hook_execution",
                                "source": {"plugin_name": "native-tools"},
                                "runs": [
                                    {
                                        "name": "post-tool",
                                        "arguments": ["ponytail"],
                                    }
                                ],
                            }
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            isolation = runner.assert_session_claude_isolated(
                session, {"claude", "ponytail"}
            )
            self.assertEqual(isolation["claude_hook_execution_events"], 0)

            (session / "chat_history.jsonl").write_text("{}\n", encoding="utf-8")
            (session / "updates.jsonl").write_text(
                json.dumps(
                    {
                        "params": {
                            "update": {
                                "sessionUpdate": "hook_execution",
                                "runs": [{"name": "global/orca-status"}],
                            }
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            evidence = runner.assert_session_claude_isolated(session)
            self.assertEqual(evidence["hook_execution_events"], 1)
            self.assertEqual(evidence["claude_hook_execution_events"], 0)

            (session / "updates.jsonl").write_text(
                json.dumps(
                    {
                        "params": {
                            "update": {
                                "sessionUpdate": "hook_execution",
                                "runs": [
                                    {
                                        "name": (
                                            "/Users/test/.claude/plugins/example"
                                        )
                                    }
                                ],
                            }
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(AssertionError, "Claude compatibility leaked"):
                runner.assert_session_claude_isolated(session)

    def test_claude_hook_path_identifiers_reach_session_gate(self) -> None:
        runner = load_runner_module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "config.toml").write_text("", encoding="utf-8")
            inspected = {
                "externalCompat": {
                    "cells": [
                        {"vendor": "claude", "surface": surface, "enabled": False}
                        for surface in runner.CLAUDE_COMPAT_SURFACES
                    ]
                },
                "hooks": [
                    {
                        "path": "/tmp/.claude/hooks/start.py",
                        "disabled": True,
                    }
                ],
            }
            with (
                mock.patch.dict(os.environ, {"GROK_HOME": str(home)}),
                mock.patch.object(
                    runner,
                    "run_cmd",
                    return_value=subprocess.CompletedProcess(
                        ["grok", "inspect", "--json"],
                        0,
                        stdout=json.dumps(inspected),
                        stderr="",
                    ),
                ),
            ):
                identifiers = set(
                    runner.assert_claude_isolation_config()[
                        "claude_runtime_identifiers"
                    ]
                )
            self.assertIn("start", identifiers)

            session = home / "session"
            session.mkdir()
            (session / "chat_history.jsonl").write_text("{}\n", encoding="utf-8")
            (session / "updates.jsonl").write_text(
                json.dumps(
                    {
                        "params": {
                            "update": {
                                "sessionUpdate": "hook_execution",
                                "source": {"plugin_name": "start"},
                            }
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                AssertionError, "executed 1 Claude startup/runtime hooks"
            ):
                runner.assert_session_claude_isolated(session, identifiers)

    def test_candidate_agent_surface_must_match_active_home(self) -> None:
        runner = load_runner_module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            populate_candidate_home(home)
            with mock.patch.dict(
                os.environ,
                {
                    "GROK_HOME": str(home),
                    "PILOTFISH_GROK_E2E_POLICY": str(
                        ROOT / "templates" / "rules.pilotfish-grok.md"
                    ),
                },
            ):
                evidence = runner.assert_install_surface()
                self.assertEqual(
                    evidence["candidate_surface"]["agents_match"],
                    runner.ROLES,
                )
                self.assertEqual(
                    evidence["candidate_surface"]["agent_files"],
                    sorted(f"{role}.md" for role in runner.ROLES),
                )
                verifier = home / "agents" / "verifier.md"
                verifier.write_text(
                    verifier.read_text(encoding="utf-8") + "\nstale\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    AssertionError, "agent surface does not match"
                ):
                    runner.assert_install_surface()
                shutil.copy2(ROOT / "templates" / "agents" / "verifier.md", verifier)
                (home / "agents" / "extra.md").write_text("extra\n", encoding="utf-8")
                (home / "roles" / "extra.toml").write_text(
                    'default_capability_mode = "all"\n',
                    encoding="utf-8",
                )
                evidence = runner.assert_install_surface()["candidate_surface"]
                self.assertEqual(
                    evidence["owned_agent_files"],
                    sorted(f"{role}.md" for role in runner.ROLES),
                )
                self.assertEqual(
                    evidence["owned_role_files"],
                    sorted(f"{role}.toml" for role in runner.ROLES),
                )
                self.assertEqual(evidence["unrelated_agent_files"], ["extra.md"])
                self.assertEqual(evidence["unrelated_role_files"], ["extra.toml"])

    def test_cue_free_prompt_guard(self) -> None:
        runner = load_runner_module()
        runner.assert_cue_free_prompt(
            "Add bounded retry handling, preserve the public API, and add tests."
        )
        for prompt in (
            "Use the executor for this.",
            "Spawn a helper.",
            "Delegate this task.",
            "Write a plan first.",
            "Use the normal role workflow.",
        ):
            with self.assertRaisesRegex(AssertionError, "orchestration terms"):
                runner.assert_cue_free_prompt(prompt)
        for verdict in ("CONFIRMED", "\n  CONFIRMED\nEvidence"):
            self.assertTrue(runner.is_confirmed(verdict))
        for verdict in (
            "**CONFIRMED**",
            "## CONFIRMED\nEvidence",
            "REFUTED",
            "Evidence\nCONFIRMED",
            "REFUTED\nCONFIRMED behavior would require more",
            "CONFIRMED\nREFUTED by this probe",
            "CONFIRMED\nNo REFUTED verdict was applicable",
        ):
            self.assertFalse(runner.is_confirmed(verdict))
        with self.assertRaisesRegex(AssertionError, "selection is empty"):
            runner.selected_cases("")

    def test_executor_ownership_and_verifier_claim_are_enforced(self) -> None:
        runner = load_runner_module()
        events = [
            {
                "kind": "spawned",
                "sequence": 1,
                "subagent_type": "executor",
                "capability_mode": "all",
                "subagent_id": "executor-1",
                "raw_input": {
                    "prompt": "Implement approved SLICE-test in client.py."
                },
            },
            {
                "kind": "finished",
                "sequence": 2,
                "subagent_id": "executor-1",
                "status": "completed",
                "output": "Implemented.",
            },
            {
                "kind": "tool_call",
                "sequence": 3,
                "tool": "write",
            },
            {
                "kind": "spawned",
                "sequence": 4,
                "subagent_type": "verifier",
                "capability_mode": "execute",
                "subagent_id": "verifier-1",
                "raw_input": {"prompt": "Check the change."},
            },
            {
                "kind": "finished",
                "sequence": 5,
                "subagent_id": "verifier-1",
                "status": "completed",
                "output": "CONFIRMED",
            },
        ]
        result = {"events": events, "spawn_events": events, "text": ""}

        with self.assertRaisesRegex(AssertionError, "parent session mutated"):
            runner.require_role_owned_implementation(result, "executor")

        events[2]["tool"] = "run_terminal_command"
        events[2]["raw_input"] = {
            "command": (
                "python3 -m unittest test_client.py -v && "
                "python3 -m unittest test_auth.py -v"
            )
        }
        implementation = runner.require_role_owned_implementation(result, "executor")
        self.assertEqual(implementation["parent_mutation_tools"], [])
        self.assertEqual(
            implementation["parent_verification_tools"],
            ["run_terminal_command"],
        )
        with self.assertRaisesRegex(AssertionError, "approved contract"):
            runner.require_bound_implementation(
                result,
                implementation,
                ("SLICE-test", "client.py", "test_client.py"),
            )
        implementation = runner.require_bound_implementation(
            result,
            implementation,
            ("SLICE-test", "client.py"),
        )
        self.assertEqual(
            implementation["contract_terms"],
            ["SLICE-test", "client.py"],
        )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test.\n"
            "Files: auth.py, test_auth.py, README.md\n"
            "Create evil.py after updating auth.py."
        )
        with self.assertRaisesRegex(AssertionError, "outside approved scope"):
            runner.require_bound_implementation(
                result,
                implementation,
                ("SLICE-test", "auth.py"),
                approved_files=("auth.py", "test_auth.py", "README.md"),
                repository_files=(
                    "auth.py",
                    "test_auth.py",
                    "README.md",
                ),
            )
        for suffix in (
            "evil.sh.",
            "EVIL.SH.",
            "evil.execute.",
            "evil..sh",
            "evil...sh",
            "dir/evil..sh",
            ".env",
            "..env",
            ".config.json",
        ):
            events[0]["raw_input"]["prompt"] = (
                "Implement approved SLICE-test.\n"
                f"Files: auth.py, test_auth.py, README.md, {suffix}"
            )
            with self.assertRaisesRegex(AssertionError, "scope"):
                runner.require_bound_implementation(
                    result,
                    implementation,
                    ("SLICE-test", "auth.py"),
                    approved_files=("auth.py", "test_auth.py", "README.md"),
                    repository_files=(
                        "auth.py",
                        "test_auth.py",
                        "README.md",
                    ),
                )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test with `hmac.compare_digest` and "
            "`inspect.getsource`.\n"
            "Files: auth.py, test_auth.py, README.md"
        )
        implementation = runner.require_bound_implementation(
            result,
            implementation,
            (
                "SLICE-test",
                "auth.py",
                "hmac.compare_digest",
                "inspect.getsource",
            ),
            approved_files=("auth.py", "test_auth.py", "README.md"),
            repository_files=("auth.py", "test_auth.py", "README.md"),
            allowed_dotted_tokens=("hmac.compare_digest", "inspect.getsource"),
        )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test with `.config`.\n"
            "Files: auth.py, test_auth.py, README.md\n"
            "Use .config.json."
        )
        with self.assertRaisesRegex(AssertionError, "outside approved scope"):
            runner.require_bound_implementation(
                result,
                implementation,
                ("SLICE-test", "auth.py", ".config"),
                approved_files=("auth.py", "test_auth.py", "README.md"),
                repository_files=("auth.py", "test_auth.py", "README.md"),
                allowed_dotted_tokens=(".config",),
            )
        for allowed, masked in (
            ("evil.sh", "evil.sh."),
            ("evil.sh", "evil.sh.."),
            (".config", ".config."),
        ):
            events[0]["raw_input"]["prompt"] = (
                f"Implement approved SLICE-test with {masked}\n"
                "Files: auth.py, test_auth.py, README.md"
            )
            with self.assertRaisesRegex(AssertionError, "outside approved scope"):
                runner.require_bound_implementation(
                    result,
                    implementation,
                    ("SLICE-test", "auth.py", allowed),
                    approved_files=("auth.py", "test_auth.py", "README.md"),
                    repository_files=("auth.py", "test_auth.py", "README.md"),
                    allowed_dotted_tokens=(allowed,),
                )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test with .config\n"
            "Files: auth.py, test_auth.py, README.md"
        )
        runner.require_bound_implementation(
            result,
            implementation,
            ("SLICE-test", "auth.py", ".config"),
            approved_files=("auth.py", "test_auth.py", "README.md"),
            repository_files=("auth.py", "test_auth.py", "README.md"),
            allowed_dotted_tokens=(".config",),
        )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test.\n"
            "Files: auth.py, test_auth.py, README.md\n"
            "### Non-goals\n"
            "- Delete client.py."
        )
        with self.assertRaisesRegex(AssertionError, "outside approved scope"):
            runner.require_bound_implementation(
                result,
                implementation,
                ("SLICE-test", "auth.py"),
                approved_files=("auth.py", "test_auth.py", "README.md"),
                repository_files=(
                    "auth.py",
                    "test_auth.py",
                    "README.md",
                    "client.py",
                ),
            )
        for directive in (
            "Update client.py to keep callers aligned.",
            "Add client.py to the compatibility surface.",
            "Do not leave client.py unchanged; edit it.",
            "Do not touch client.py and update evil.py.",
            "Do not touch client.py, update it.",
            "Do not touch client.py. Update it.",
            "Do not touch client.py — update it.",
            "Do not touch client.py while updating it.",
            "Do not touch client.py except to update imports.",
            "Do not touch client.py, remove hardcoded key, or add third-party "
            "deps and update evil.py.",
            "Secret relocation; client.py changes; update evil.py.",
            "Secret relocation; client.py changes; updating evil.py.",
            "Secret relocation; client.py changes; introduce evil.py.",
            "Secret relocation; client.py changes; evil.py changes are required.",
            "Secret relocation; client.py changes; overwrite evil.py.",
            "Secret relocation; client.py changes; mutate evil.py.",
            "Secret relocation; client.py changes; revise evil.py.",
            "client.py changes; then update it.",
            "client.py changes; it must be updated.",
            "Create evil.sh after updating auth.py.",
            "Create EVIL.SH after updating auth.py.",
            "client.py changes\n  Update it to keep callers aligned.",
            "- client.py\n  Update it to keep callers aligned.",
            "- client.py\n\n  Update it to keep callers aligned.",
            "- client.py\n  Update it to keep callers aligned.\n- client.py",
            "packaging\n   ### Implementation\n- client.py",
            "packaging\n# Implementation\n- client.py",
            "packaging\n##### Implementation\n- client.py",
        ):
            events[0]["raw_input"]["prompt"] = (
                "Implement approved SLICE-test.\n"
                "Files: auth.py, test_auth.py, README.md\n"
                "### Non-goals\n"
                f"- {directive}"
            )
            with self.assertRaisesRegex(AssertionError, "outside approved scope"):
                runner.require_bound_implementation(
                    result,
                    implementation,
                    ("SLICE-test", "auth.py"),
                    approved_files=("auth.py", "test_auth.py", "README.md"),
                    repository_files=(
                        "auth.py",
                        "test_auth.py",
                        "README.md",
                        "client.py",
                        "evil.py",
                    ),
                )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test.\n"
            "### Exclusive ownership (only these files)\n"
            "1. `auth.py`\n"
            "2. `test_auth.py`\n"
            "3. `README.md`\n"
            "### Non-goals\n"
            "Do not change client.py."
        )
        implementation = runner.require_bound_implementation(
            result,
            implementation,
            ("SLICE-test", "auth.py"),
            approved_files=("auth.py", "test_auth.py", "README.md"),
            repository_files=(
                "auth.py",
                "test_auth.py",
                "README.md",
                "client.py",
            ),
        )
        self.assertEqual(
            implementation["approved_files"],
            ["auth.py", "test_auth.py", "README.md"],
        )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test.\n"
            "Files: auth.py, test_auth.py, README.md\n"
            "Do NOT modify `client.py`, `test_client.py`, or anything else.\n"
            "### test_auth.py requirements\n"
            "Path proof: use `unittest.mock`."
        )
        implementation = runner.require_bound_implementation(
            result,
            implementation,
            ("SLICE-test", "auth.py"),
            approved_files=("auth.py", "test_auth.py", "README.md"),
            repository_files=(
                "auth.py",
                "test_auth.py",
                "README.md",
                "client.py",
                "test_client.py",
            ),
            allowed_dotted_tokens=("unittest.mock",),
        )
        self.assertEqual(
            implementation["approved_files"],
            ["auth.py", "test_auth.py", "README.md"],
        )
        for escaped in (
            "9. Do not change client.py / test_client.py and update evil.py.",
            "Do not change client.py, test_client.py, or anything else except evil.py.",
            "9. Do not change client.py / test_client.py.\n"
            "   Update those files.",
        ):
            events[0]["raw_input"]["prompt"] = (
                "Implement approved SLICE-test.\n"
                "Files: auth.py, test_auth.py, README.md\n"
                f"{escaped}"
            )
            with self.assertRaisesRegex(AssertionError, "outside approved scope"):
                runner.require_bound_implementation(
                    result,
                    implementation,
                    ("SLICE-test", "auth.py"),
                    approved_files=("auth.py", "test_auth.py", "README.md"),
                    repository_files=(
                        "auth.py",
                        "test_auth.py",
                        "README.md",
                        "client.py",
                        "test_client.py",
                        "evil.py",
                    ),
                )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test.\n"
            "## Non-goals: auth.py, test_auth.py, README.md\n"
            "- client.py"
        )
        with self.assertRaisesRegex(AssertionError, "omitted approved files"):
            runner.require_bound_implementation(
                result,
                implementation,
                (
                    "SLICE-test",
                    "auth.py",
                    "test_auth.py",
                    "README.md",
                ),
                approved_files=("auth.py", "test_auth.py", "README.md"),
                repository_files=(
                    "auth.py",
                    "test_auth.py",
                    "README.md",
                    "client.py",
                ),
            )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test.\n"
            "### Files to change (exclusive ownership)\n"
            "1. **auth.py** uses `hmac.compare_digest`.\n"
            "2. **test_auth.py** adds a regression (e.g. empty input).\n"
            "3. **README.md** documents the behavior.\n"
            "### Out of scope\n"
            "- client.py, test_client.py, secret_marker.txt"
        )
        implementation = runner.require_bound_implementation(
            result,
            implementation,
            (
                "SLICE-test",
                "auth.py",
                "test_auth.py",
                "README.md",
                "hmac.compare_digest",
            ),
            approved_files=("auth.py", "test_auth.py", "README.md"),
            repository_files=(
                "auth.py",
                "test_auth.py",
                "README.md",
                "client.py",
                "test_client.py",
                "secret_marker.txt",
            ),
            allowed_dotted_tokens=("hmac.compare_digest", "e.g."),
        )
        self.assertEqual(
            implementation["approved_files"],
            ["auth.py", "test_auth.py", "README.md"],
        )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test.\n"
            "### Exclusive file ownership\n"
            "- auth.py\n"
            "- test_auth.py\n"
            "- README.md\n"
            "### Do not touch\n"
            "- client.py, test_client.py, secret_marker.txt\n"
            "### Implementation requirements\n"
            "return hmac.compare_digest(api_key.encode('utf-8'), _EXPECTED)\n"
            "Patch `auth.hmac.compare_digest` with `unittest.mock.patch`."
        )
        implementation = runner.require_bound_implementation(
            result,
            implementation,
            ("SLICE-test", "auth.py", "hmac.compare_digest"),
            approved_files=("auth.py", "test_auth.py", "README.md"),
            repository_files=(
                "auth.py",
                "test_auth.py",
                "README.md",
                "client.py",
                "test_client.py",
                "secret_marker.txt",
            ),
            allowed_dotted_tokens=(
                "hmac.compare_digest",
                "api_key.encode",
                "auth.hmac.compare_digest",
                "unittest.mock.patch",
            ),
        )
        self.assertEqual(
            implementation["approved_files"],
            ["auth.py", "test_auth.py", "README.md"],
        )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test.\n"
            "Files: auth.py, test_auth.py, README.md\n"
            "### Do not touch and update\n"
            "- client.py"
        )
        with self.assertRaisesRegex(AssertionError, "outside approved scope"):
            runner.require_bound_implementation(
                result,
                implementation,
                ("SLICE-test", "auth.py"),
                approved_files=("auth.py", "test_auth.py", "README.md"),
                repository_files=(
                    "auth.py",
                    "test_auth.py",
                    "README.md",
                    "client.py",
                ),
            )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test.\n"
            "### Scope (exclusive — only these files)\n"
            "1. **auth.py**\n"
            "2. **test_auth.py**\n"
            "3. **README.md**\n"
            "### Non-goals\n"
            "Do not touch client.py."
        )
        implementation = runner.require_bound_implementation(
            result,
            implementation,
            ("SLICE-test", "auth.py"),
            approved_files=("auth.py", "test_auth.py", "README.md"),
            repository_files=(
                "auth.py",
                "test_auth.py",
                "README.md",
                "client.py",
            ),
        )
        self.assertEqual(
            implementation["approved_files"],
            ["auth.py", "test_auth.py", "README.md"],
        )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test.\n"
            "### Exclusive file ownership\n"
            "- auth.py\n"
            "- test_auth.py\n"
            "- README.md\n"
            "### Implementation\n"
            "Use `hmac.compare_digest` (e.g. for a wrong-length key).\n"
            "### Non-goals (do not do)\n"
            "- client.py changes\n"
            "- Timing benchmark tests\n"
            "### Acceptance\n"
            "Run python unittest."
        )
        implementation = runner.require_bound_implementation(
            result,
            implementation,
            (
                "SLICE-test",
                "auth.py",
                "test_auth.py",
                "README.md",
                "hmac.compare_digest",
            ),
            approved_files=("auth.py", "test_auth.py", "README.md"),
            repository_files=(
                "auth.py",
                "test_auth.py",
                "README.md",
                "client.py",
            ),
            allowed_dotted_tokens=("hmac.compare_digest", "e.g."),
        )
        self.assertEqual(
            implementation["approved_files"],
            ["auth.py", "test_auth.py", "README.md"],
        )
        events[0]["raw_input"]["prompt"] = (
            "Implement approved SLICE-test.\n"
            "**Files (exclusive ownership — only these):**\n"
            "- `auth.py`\n"
            "- `test_auth.py`\n"
            "- `README.md`\n\n"
            "**Constraints:**\n"
            "Use `hmac.compare_digest`; path proof may use "
            "`unittest.mock.patch` or `inspect.getsource` (e.g. a spy).\n"
            "**Done criteria:** run python unittest.\n"
            "### Non-goals\n"
            "- client.py changes"
        )
        implementation = runner.require_bound_implementation(
            result,
            implementation,
            (
                "SLICE-test",
                "auth.py",
                "test_auth.py",
                "README.md",
                "hmac.compare_digest",
            ),
            approved_files=("auth.py", "test_auth.py", "README.md"),
            repository_files=(
                "auth.py",
                "test_auth.py",
                "README.md",
                "client.py",
            ),
            allowed_dotted_tokens=(
                "hmac.compare_digest",
                "inspect.getsource",
                "unittest.mock.patch",
                "e.g.",
            ),
        )
        self.assertEqual(
            implementation["approved_files"],
            ["auth.py", "test_auth.py", "README.md"],
        )
        for exclusion in (
            "7. Do not modify client.py or other files.",
            "Do not touch client.py, secret storage, packaging, microbenchmarks.",
            "Do not touch client.py, test_client.py, remove hardcoded key, "
            "or add third-party deps.",
            "Secret relocation; client.py/test_client.py changes; type-guard "
            "for non-str; timing benchmarks; rate limiting.",
        ):
            events[0]["raw_input"]["prompt"] = (
                "Implement approved SLICE-test.\n"
                "### Scope (exclusive — only these files)\n"
                "1. **auth.py**\n"
                "2. **test_auth.py**\n"
                "3. **README.md**\n"
                "### Non-goals\n"
                f"{exclusion}"
            )
            implementation = runner.require_bound_implementation(
                result,
                implementation,
                ("SLICE-test", "auth.py"),
                approved_files=("auth.py", "test_auth.py", "README.md"),
                repository_files=(
                    "auth.py",
                    "test_auth.py",
                    "README.md",
                    "client.py",
                ),
            )
            self.assertEqual(
                implementation["approved_files"],
                ["auth.py", "test_auth.py", "README.md"],
            )

        events[2]["raw_input"]["command"] += " && sed -i old new client.py"
        with self.assertRaisesRegex(AssertionError, "parent session mutated"):
            runner.require_role_owned_implementation(result, "executor")
        events[2]["raw_input"]["command"] = (
            "python3 -m unittest\nsed -i old new client.py"
        )
        with self.assertRaisesRegex(AssertionError, "parent session mutated"):
            runner.require_role_owned_implementation(result, "executor")
        events[2]["raw_input"]["command"] = (
            "python3 -m unittest test_client.py -v"
        )

        with self.assertRaisesRegex(AssertionError, "not bound"):
            runner.require_bound_verifier(
                result,
                after_role="executor",
                claim_terms=("client.py", "test_client.py"),
            )

        events[3]["raw_input"]["prompt"] = (
            "Verify client.py and test_client.py preserve the public API."
        )
        verification = runner.require_bound_verifier(
            result,
            after_role="executor",
            claim_terms=("client.py", "test_client.py", "public API"),
        )
        self.assertEqual(
            verification["claim_terms"],
            ["client.py", "test_client.py", "public API"],
        )

    def test_completed_role_uses_its_own_capability(self) -> None:
        runner = load_runner_module()
        events = [
            {
                "kind": "spawned",
                "sequence": 1,
                "subagent_type": "executor",
                "capability_mode": "all",
                "subagent_id": "executor-first",
            },
            {
                "kind": "spawned",
                "sequence": 2,
                "subagent_type": "executor",
                "capability_mode": "read-only",
                "subagent_id": "executor-completed",
            },
            {
                "kind": "finished",
                "sequence": 3,
                "subagent_id": "executor-completed",
                "status": "completed",
                "output": "Implemented.",
            },
        ]
        result = {"events": events, "spawn_events": events, "text": ""}
        with self.assertRaisesRegex(AssertionError, "capability_mode"):
            runner.require_completed_role(result, "executor")

    def test_exclusive_executor_rejects_alternate_write_role(self) -> None:
        runner = load_runner_module()
        events = [
            {
                "kind": "spawned",
                "sequence": 1,
                "subagent_type": "mech-executor",
                "capability_mode": "execute",
                "subagent_id": "alternate",
            },
            {
                "kind": "spawned",
                "sequence": 2,
                "subagent_type": "security-executor",
                "capability_mode": "all",
                "subagent_id": "security",
            },
            {
                "kind": "finished",
                "sequence": 3,
                "subagent_id": "security",
                "status": "completed",
                "output": "Implemented.",
            },
        ]
        result = {"events": events, "spawn_events": events, "text": ""}
        with self.assertRaisesRegex(AssertionError, "exclusive write-capable"):
            runner.require_role_owned_implementation(
                result,
                "security-executor",
                after_sequence=0,
                exclusive=True,
            )
        events[0].update(
            {
                "subagent_type": "security-executor",
                "capability_mode": "all",
            }
        )
        with self.assertRaisesRegex(AssertionError, "exclusive write-capable"):
            runner.require_role_owned_implementation(
                result,
                "security-executor",
                after_sequence=0,
                exclusive=True,
            )
        events[0].update(
            {
                "sequence": 4,
                "subagent_type": "mech-executor",
                "capability_mode": "execute",
            }
        )
        with self.assertRaisesRegex(AssertionError, "exclusive write-capable"):
            runner.require_role_owned_implementation(
                result,
                "security-executor",
                after_sequence=0,
                exclusive=True,
            )
        events[0].update(
            {
                "sequence": 4,
                "subagent_type": "verifier",
                "capability_mode": "execute",
            }
        )
        events.append(
            {
                "kind": "spawned",
                "sequence": 5,
                "subagent_type": "verifier",
                "capability_mode": "execute",
                "subagent_id": "second-verifier",
            }
        )
        with self.assertRaisesRegex(AssertionError, "exclusive write-capable"):
            runner.require_role_owned_implementation(
                result,
                "security-executor",
                after_sequence=0,
                exclusive=True,
            )
        events.pop()
        implementation = runner.require_role_owned_implementation(
            result,
            "security-executor",
            after_sequence=0,
            exclusive=True,
        )
        self.assertEqual(implementation["alternate_write_capable_spawns"], [])

    def test_worktree_cherry_pick_is_executor_owned_integration(self) -> None:
        runner = load_runner_module()
        events = [
            {
                "kind": "spawned",
                "sequence": 1,
                "subagent_type": "executor",
                "capability_mode": "all",
                "subagent_id": "executor-worktree",
                "raw_input": {"isolation": "worktree"},
            },
            {
                "kind": "finished",
                "sequence": 2,
                "subagent_id": "executor-worktree",
                "status": "completed",
                "output": "Implemented and committed as abc1234.",
            },
            {
                "kind": "spawned",
                "sequence": 3,
                "subagent_type": "verifier",
                "capability_mode": "execute",
                "subagent_id": "verifier-before-integration",
                "raw_input": {"prompt": "Verify client.py and test_client.py."},
            },
            {
                "kind": "tool_call",
                "sequence": 4,
                "tool": "run_terminal_command",
                "raw_input": {"command": "git cherry-pick abc1234"},
            },
            {
                "kind": "finished",
                "sequence": 6,
                "subagent_id": "verifier-before-integration",
                "status": "completed",
                "output": "CONFIRMED",
            },
        ]
        result = {"events": events, "spawn_events": events, "text": ""}
        implementation = runner.require_role_owned_implementation(result, "executor")
        self.assertEqual(
            implementation["parent_integration_tools"],
            ["run_terminal_command"],
        )
        self.assertEqual(implementation["result_ready_sequence"], 4)
        with self.assertRaisesRegex(AssertionError, "before executor integration"):
            runner.require_bound_verifier(
                result,
                after_role="executor",
                after_sequence=implementation["result_ready_sequence"],
                claim_terms=("client.py", "test_client.py"),
            )

        events[2]["sequence"] = 5
        verification = runner.require_bound_verifier(
            result,
            after_role="executor",
            after_sequence=implementation["result_ready_sequence"],
            claim_terms=("client.py", "test_client.py"),
        )
        self.assertEqual(verification["spawn_sequence"], 5)

        events[3]["raw_input"]["command"] = "git cherry-pick def5678"
        with self.assertRaisesRegex(AssertionError, "parent session mutated"):
            runner.require_role_owned_implementation(result, "executor")

    def test_scout_must_precede_parent_repository_tools(self) -> None:
        runner = load_runner_module()
        scout_input = {
            "subagent_type": "scout",
            "description": "Find the marker",
        }
        events = [
            {
                "kind": "tool_call",
                "sequence": 1,
                "tool": "search",
                "read_only": True,
            },
            {
                "kind": "tool_call",
                "sequence": 2,
                "tool": "spawn_subagent",
                "raw_input": scout_input,
            },
            {
                "kind": "spawned",
                "sequence": 3,
                "subagent_type": "scout",
                "capability_mode": "read-only",
                "subagent_id": "scout-1",
                "raw_input": scout_input,
            },
            {
                "kind": "finished",
                "sequence": 4,
                "subagent_id": "scout-1",
                "status": "completed",
                "output": "Found it.",
            },
        ]
        result = {"events": events, "spawn_events": events, "text": ""}
        with self.assertRaisesRegex(AssertionError, "before scout dispatch"):
            runner.require_scout_before_parent_tools(result)
        with self.assertRaisesRegex(AssertionError, "before scout dispatch"):
            runner.require_scout_before_parent_tools(result, strict_first=False)

        events[0].update(
            {
                "tool": "run_terminal_command",
                "read_only": False,
                "raw_input": {"command": "python3 -m unittest"},
            }
        )
        scout = runner.require_scout_before_parent_tools(
            result, strict_first=False
        )
        self.assertEqual(scout["parent_tools_before_scout"], [])
        with self.assertRaisesRegex(AssertionError, "before scout dispatch"):
            runner.require_scout_before_parent_tools(result)

        events[0]["raw_input"]["command"] = (
            "python3 -c \"print(open('auth.py').read())\""
        )
        with self.assertRaisesRegex(AssertionError, "before scout dispatch"):
            runner.require_scout_before_parent_tools(result, strict_first=False)

        events[0]["sequence"] = 5
        scout = runner.require_scout_before_parent_tools(result)
        self.assertEqual(scout["parent_tools_before_scout"], [])
        self.assertEqual(scout["spawn_tool_sequence"], 2)

        events.insert(
            0,
            {
                "kind": "tool_call",
                "sequence": 1,
                "tool": "spawn_subagent",
                "raw_input": {"subagent_type": "verifier"},
            },
        )
        with self.assertRaisesRegex(AssertionError, "before scout dispatch"):
            runner.require_scout_before_parent_tools(result)

    def test_source_snapshot_ignores_git_index_hiding(self) -> None:
        runner = load_runner_module()
        self.assertEqual(
            runner.changed_source_paths(
                {"auth.py": "old", "client.py": "same"},
                {"auth.py": "new", "client.py": "same", "extra.py": "new"},
            ),
            ["auth.py", "extra.py"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            fixture = runner.make_fixture(Path(tmp))
            before = runner.source_snapshot(fixture)
            (fixture / "auth.py").write_text(
                "def authenticate(api_key: str) -> bool:\n    return False\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "update-index", "--assume-unchanged", "auth.py"],
                cwd=fixture,
                check=True,
            )
            self.assertEqual(runner.git_status(fixture), [])
            self.assertNotEqual(runner.source_snapshot(fixture), before)

            client = fixture / "client.py"
            original_mode = client.stat().st_mode
            before_mode_change = runner.source_snapshot(fixture)
            client.chmod(original_mode ^ 0o100)
            self.assertEqual(
                runner.changed_source_paths(
                    before_mode_change,
                    runner.source_snapshot(fixture),
                ),
                ["client.py"],
            )
            client.chmod(original_mode)

            external = Path(tmp) / "external-client.py"
            external.write_bytes(client.read_bytes())
            before_type_change = runner.source_snapshot(fixture)
            client.unlink()
            client.symlink_to(external)
            self.assertEqual(
                runner.changed_source_paths(
                    before_type_change,
                    runner.source_snapshot(fixture),
                ),
                ["client.py"],
            )

    def test_harness_owned_behavior_probes_reject_baseline_fixture(self) -> None:
        runner = load_runner_module()
        with tempfile.TemporaryDirectory() as tmp:
            fixture = runner.make_fixture(Path(tmp))
            baseline_test = (fixture / "test_client.py").read_text(encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "repository retry tests"):
                runner.assert_retry_behavior(fixture, baseline_test)
            with self.assertRaisesRegex(AssertionError, "mechanical rename"):
                runner.assert_rename_behavior(fixture)
            with self.assertRaisesRegex(AssertionError, "does not use compare_digest"):
                runner.assert_security_behavior(fixture)

            (fixture / "client.py").write_text(
                "class TransientError(Exception):\n"
                "    pass\n\n"
                "class Client:\n"
                "    def __init__(self, transport):\n"
                "        self.transport = transport\n\n"
                "    def fetch(self):\n"
                "        for attempt in range(2):\n"
                "            try:\n"
                "                return self.transport.request()\n"
                "            except TransientError:\n"
                "                if attempt == 1:\n"
                "                    raise\n",
                encoding="utf-8",
            )
            (fixture / "test_client.py").write_text(
                "import unittest\n"
                "from client import Client, TransientError\n\n"
                "class RetryTest(unittest.TestCase):\n"
                "    def test_success(self):\n"
                "        self.assertTrue(Client)\n\n"
                "    def test_retry(self):\n"
                "        self.assertTrue(TransientError)\n\n"
                "    def test_exhaustion(self):\n"
                "        self.assertTrue(TransientError)\n\n"
                "    def test_permanent(self):\n"
                "        self.assertTrue(RuntimeError('permanent'))\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(AssertionError, "accepted mutant"):
                runner.assert_retry_behavior(fixture, baseline_test)

            (fixture / "test_client.py").write_text(
                "import unittest\n"
                "from client import Client, TransientError\n\n"
                "class Transport:\n"
                "    def __init__(self, outcomes):\n"
                "        self.outcomes = iter(outcomes)\n"
                "        self.calls = 0\n"
                "    def request(self):\n"
                "        self.calls += 1\n"
                "        outcome = next(self.outcomes)\n"
                "        if isinstance(outcome, BaseException):\n"
                "            raise outcome\n"
                "        return outcome\n\n"
                "class RetryTest(unittest.TestCase):\n"
                "    def test_success(self):\n"
                "        transport = Transport(['ok'])\n"
                "        self.assertEqual(Client(transport).fetch(), 'ok')\n\n"
                "    def test_retry(self):\n"
                "        transport = Transport([TransientError(), 'ok'])\n"
                "        self.assertEqual(Client(transport).fetch(), 'ok')\n"
                "        self.assertEqual(transport.calls, 2)\n\n"
                "    def test_exhaustion(self):\n"
                "        transport = Transport([TransientError(), TransientError()])\n"
                "        with self.assertRaises(TransientError):\n"
                "            Client(transport).fetch()\n"
                "        self.assertEqual(transport.calls, 2)\n\n"
                "    def test_permanent(self):\n"
                "        transport = Transport([RuntimeError('permanent')])\n"
                "        with self.assertRaises(RuntimeError):\n"
                "            Client(transport).fetch()\n"
                "        self.assertEqual(transport.calls, 1)\n",
                encoding="utf-8",
            )
            retry_probe = runner.assert_retry_behavior(fixture, baseline_test)
            self.assertTrue(retry_probe["passed"])
            self.assertEqual(
                retry_probe["repository_mutants_rejected"],
                [
                    "no-transient-retry",
                    "swallow-exhaustion",
                    "retry-permanent",
                ],
            )

            for filename in ("auth.py", "test_auth.py", "README.md"):
                path = fixture / filename
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        "authenticate", "validate_api_key"
                    ),
                    encoding="utf-8",
                )
            subprocess.run(
                ["git", "add", "auth.py", "test_auth.py", "README.md"],
                cwd=fixture,
                check=True,
            )
            self.assertEqual(
                subprocess.run(
                    [
                        "git",
                        "diff",
                        "--",
                        "auth.py",
                        "test_auth.py",
                        "README.md",
                    ],
                    cwd=fixture,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout,
                "",
            )
            self.assertTrue(runner.assert_rename_behavior(fixture)["passed"])
            stale = fixture / "compat.py"
            stale.write_text("from auth import authenticate\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "left old symbols"):
                runner.assert_rename_behavior(fixture)
            stale.unlink()

            (fixture / "auth.py").write_text(
                "import hmac\n\n"
                "def authenticate(api_key: str) -> bool:\n"
                "    return hmac.compare_digest(b'legacy-test-key', api_key.encode())\n",
                encoding="utf-8",
            )
            (fixture / "test_auth.py").write_text(
                "import unittest\n\n"
                "from auth import authenticate\n\n"
                "class AuthTest(unittest.TestCase):\n"
                "    def test_valid(self):\n"
                "        self.assertTrue(authenticate('legacy-test-key'))\n\n"
                "    def test_invalid(self):\n"
                "        self.assertFalse(authenticate('wrong'))\n",
                encoding="utf-8",
            )
            (fixture / "README.md").write_text(
                "Authentication uses timing-safe compare_digest.\n",
                encoding="utf-8",
            )
            self.assertTrue(runner.assert_security_behavior(fixture)["passed"])

            (fixture / "auth.py").write_text(
                "import hmac\n\n"
                "def authenticate(api_key: str) -> bool:\n"
                "    hmac.compare_digest(b'legacy-test-key', api_key.encode())\n"
                "    return api_key == 'legacy-test-key'\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(AssertionError, "ignored compare_digest"):
                runner.assert_security_behavior(fixture)

            (fixture / "auth.py").write_text(
                "import hmac\n\n"
                "def authenticate(api_key):\n"
                "    return hmac.compare_digest('legacy-test-key', api_key)\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(AssertionError, "signature changed"):
                runner.assert_security_behavior(fixture)

    def test_tool_failure_links_to_original_spawn_call(self) -> None:
        runner = load_runner_module()
        updates = [
            {
                "params": {
                    "update": {
                        "sessionUpdate": "tool_call",
                        "toolCallId": "call-1",
                        "title": "spawn_subagent",
                        "rawInput": {
                            "subagent_type": "Explore",
                            "description": "Retryable spawn",
                            "prompt": "stale prompt",
                        },
                        "_meta": {"x.ai/tool": {"name": "spawn_subagent"}},
                    }
                }
            },
            {
                "params": {
                    "update": {
                        "sessionUpdate": "tool_call_update",
                        "toolCallId": "call-1",
                        "status": "failed",
                        "rawOutput": {"message": "Subagent Explore is disabled"},
                    }
                }
            },
            {
                "params": {
                    "update": {
                        "sessionUpdate": "tool_call",
                        "toolCallId": "call-2",
                        "title": "spawn_subagent",
                        "rawInput": {
                            "subagent_type": "Explore",
                            "description": "Retryable spawn",
                            "prompt": "corrected prompt",
                        },
                        "_meta": {"x.ai/tool": {"name": "spawn_subagent"}},
                    }
                }
            },
            {
                "params": {
                    "update": {
                        "sessionUpdate": "subagent_spawned",
                        "subagent_type": "Explore",
                        "description": "Retryable spawn",
                        "subagent_id": "retry-1",
                    }
                }
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp)
            (session / "updates.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in updates),
                encoding="utf-8",
            )
            failures = [
                event
                for event in runner.parse_session_events(session)
                if event["kind"] == "tool_failure"
            ]
            spawned = [
                event
                for event in runner.parse_session_events(session)
                if event["kind"] == "spawned"
            ]
        self.assertEqual(failures[0]["tool"], "spawn_subagent")
        self.assertEqual(failures[0]["raw_input"]["subagent_type"], "Explore")
        self.assertEqual(spawned[0]["raw_input"]["prompt"], "corrected prompt")

    def test_ordered_native_plan_gate_parser(self) -> None:
        runner = load_runner_module()
        updates = [
            {
                "params": {
                    "update": {
                        "sessionUpdate": "tool_call",
                        "title": "enter_plan_mode",
                        "_meta": {"x.ai/tool": {"name": "enter_plan_mode"}},
                    }
                }
            },
            {
                "params": {
                    "update": {
                        "sessionUpdate": "tool_call",
                        "title": "spawn_subagent",
                        "rawInput": {
                            "description": "Verify envelope",
                            "prompt": (
                                "## Target readiness unit\n"
                                "- ID: ENV-test\n"
                                "- Kind: `program envelope`\n"
                            ),
                            "subagent_type": "plan-verifier",
                            "background": False,
                        },
                        "_meta": {"x.ai/tool": {"name": "spawn_subagent"}},
                    }
                }
            },
            {
                "params": {
                    "update": {
                        "sessionUpdate": "subagent_spawned",
                        "subagent_type": "plan-verifier",
                        "description": "Verify envelope",
                        "capability_mode": "read-only",
                        "subagent_id": "pv-1",
                    }
                }
            },
            {
                "params": {
                    "update": {
                        "sessionUpdate": "subagent_finished",
                        "subagent_id": "pv-1",
                        "status": "completed",
                        "output": "VERDICT: **REVISE**\nClarify ownership.",
                    }
                }
            },
            {
                "params": {
                    "update": {
                        "sessionUpdate": "tool_call",
                        "title": "spawn_subagent",
                        "rawInput": {
                            "description": "Reverify envelope",
                            "prompt": (
                                "## Target readiness unit\n"
                                "- ID: ENV-test\n"
                                "- Kind: program envelope\n"
                            ),
                            "subagent_type": "plan-verifier",
                            "background": False,
                        },
                        "_meta": {"x.ai/tool": {"name": "spawn_subagent"}},
                    }
                }
            },
            {
                "params": {
                    "update": {
                        "sessionUpdate": "subagent_spawned",
                        "subagent_type": "plan-verifier",
                        "description": "Reverify envelope",
                        "capability_mode": "read-only",
                        "subagent_id": "pv-2",
                    }
                }
            },
            {
                "params": {
                    "update": {
                        "sessionUpdate": "subagent_finished",
                        "subagent_id": "pv-2",
                        "status": "completed",
                        "output": "**VERDICT: READY**\nNo blocking defect.",
                    }
                }
            },
            {
                "params": {
                    "update": {
                        "sessionUpdate": "tool_call",
                        "title": "exit_plan_mode",
                        "_meta": {"x.ai/tool": {"name": "exit_plan_mode"}},
                    }
                }
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp)
            (session / "updates.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in updates),
                encoding="utf-8",
            )
            (session / "plan.md").write_text("# Plan\n\nVerified.\n", encoding="utf-8")
            (session / "plan_mode.json").write_text(
                json.dumps(
                    {"state": "Active", "awaiting_plan_approval": True}
                )
                + "\n",
                encoding="utf-8",
            )
            events = runner.parse_session_events(session)
            events.append(
                {
                    "kind": "tool_call",
                    "sequence": 0.5,
                    "tool": "write",
                    "read_only": False,
                    "raw_input": {"file_path": str(session / "plan.md")},
                }
            )
            gate = runner.assert_native_plan_gate(
                {"events": events, "session_dir": str(session)}
            )
            events.append(
                {
                    "kind": "tool_call",
                    "sequence": 0.75,
                    "tool": "run_terminal_command",
                    "read_only": False,
                    "raw_input": {
                        "command": "sed -i old new auth.py && git restore auth.py"
                    },
                }
            )
            with self.assertRaisesRegex(
                AssertionError, "mutation-capable tools before approval"
            ):
                runner.assert_native_plan_gate(
                    {"events": events, "session_dir": str(session)}
                )

        self.assertTrue(gate["entered_first"])
        self.assertEqual(gate["verdicts"], ["REVISE", "READY"])
        self.assertEqual(
            gate["ready_units"],
            [{"id": "ENV-test", "kind": "program envelope"}],
        )
        self.assertEqual(gate["revision_loops"], 1)
        self.assertTrue(gate["fresh_reverification_after_revise"])
        self.assertTrue(gate["ready_before_exit"])
        self.assertTrue(gate["awaiting_native_approval"])
        self.assertEqual(gate["parent_mutation_tools"], [])

    def test_native_plan_gate_rejects_invalid_review_sequences(self) -> None:
        runner = load_runner_module()

        def assert_rejected(reviews, message, *, background=False):
            events = [{"kind": "tool_call", "sequence": 0, "tool": "enter_plan_mode"}]
            for index, (unit_id, kind, verdict) in enumerate(reviews, start=1):
                subagent_id = f"pv-{index}"
                events.extend(
                    [
                        {
                            "kind": "spawned",
                            "sequence": index * 2 - 1,
                            "subagent_type": "plan-verifier",
                            "capability_mode": "read-only",
                            "subagent_id": subagent_id,
                            "raw_input": {
                                "background": background,
                                "prompt": (
                                    "## Target readiness unit\n"
                                    f"- ID: {unit_id}\n"
                                    f"- Kind: {kind}\n"
                                ),
                            },
                        },
                        {
                            "kind": "finished",
                            "sequence": index * 2,
                            "subagent_id": subagent_id,
                            "output": verdict,
                        },
                    ]
                )
            events.append(
                {
                    "kind": "tool_call",
                    "sequence": len(reviews) * 2 + 1,
                    "tool": "exit_plan_mode",
                }
            )
            with self.assertRaisesRegex(AssertionError, message):
                runner.assert_native_plan_gate(
                    {"events": events, "session_dir": "."}
                )

        assert_rejected(
            (
                ("ENV-test", "program envelope", "READY"),
                ("S1-test", "execution slice", "READY"),
                ("ENV-test", "program envelope", "REVISE"),
            ),
            "program envelope was reviewed after execution slice",
        )
        assert_rejected(
            (
                ("ENV-test", "program envelope", "READY"),
                ("S1-test", "execution slice", "READY"),
                ("S2-test", "execution slice", "READY"),
            ),
            "more than one execution slice",
        )
        assert_rejected(
            (("ENV-test", "program envelope", "READY"),),
            "plan-verifier was not foreground",
            background=True,
        )

    def test_security_review_finishes_before_readiness(self) -> None:
        runner = load_runner_module()
        events = [
            {
                "kind": "spawned",
                "sequence": 1,
                "subagent_type": "security-reviewer",
                "capability_mode": "read-only",
                "subagent_id": "security-1",
            },
            {
                "kind": "finished",
                "sequence": 2,
                "subagent_id": "security-1",
                "status": "completed",
                "output": "Security findings and dispositions for ENV-test.",
            },
            {
                "kind": "spawned",
                "sequence": 3,
                "subagent_type": "plan-verifier",
                "raw_input": {
                    "prompt": (
                        "## Target readiness unit\n"
                        "- ID: ENV-test\n"
                        "- Kind: program envelope\n"
                        "Security dispositions were folded into the Plan.\n"
                    )
                },
            },
            {
                "kind": "spawned",
                "sequence": 4,
                "subagent_type": "security-reviewer",
                "capability_mode": "read-only",
                "subagent_id": "security-2",
            },
            {
                "kind": "finished",
                "sequence": 5,
                "subagent_id": "security-2",
                "status": "completed",
                "output": "Security findings and dispositions for S1-test.",
            },
            {
                "kind": "spawned",
                "sequence": 6,
                "subagent_type": "plan-verifier",
                "raw_input": {
                    "prompt": (
                        "## Target readiness unit\n"
                        "- ID: S1-test\n"
                        "- Kind: execution slice\n"
                        "Security dispositions are in the Plan.\n"
                    )
                },
            },
        ]
        evidence = runner.assert_security_review_before_readiness({"events": events})
        self.assertTrue(evidence["finished_before_readiness"])
        self.assertTrue(evidence["dispositions_presented_to_readiness"])
        self.assertEqual(
            evidence["covered_readiness_unit_ids"], ["ENV-test", "S1-test"]
        )
        self.assertEqual(
            evidence["subagent_ids"], ["security-1", "security-2"]
        )

        events[4]["sequence"] = 7
        with self.assertRaisesRegex(AssertionError, "each affected readiness"):
            runner.assert_security_review_before_readiness({"events": events})

        events[4]["sequence"] = 5
        events[4]["output"] = "Security findings for S2-test."
        with self.assertRaisesRegex(AssertionError, "each affected readiness"):
            runner.assert_security_review_before_readiness({"events": events})

    def test_native_plan_gate_stops_after_two_revisions_per_unit(self) -> None:
        runner = load_runner_module()
        events = [{"kind": "tool_call", "sequence": 0, "tool": "enter_plan_mode"}]
        prompt = (
            "## Target readiness unit\n"
            "- ID: ENV-test\n"
            "- Kind: program envelope\n"
        )
        for index, verdict in enumerate(("REVISE", "REVISE", "READY"), start=1):
            subagent_id = f"pv-{index}"
            events.extend(
                [
                    {
                        "kind": "spawned",
                        "sequence": index * 2 - 1,
                        "subagent_type": "plan-verifier",
                        "capability_mode": "read-only",
                        "subagent_id": subagent_id,
                        "raw_input": {"background": False, "prompt": prompt},
                    },
                    {
                        "kind": "finished",
                        "sequence": index * 2,
                        "subagent_id": subagent_id,
                        "output": verdict,
                    },
                ]
            )
        events.append({"kind": "tool_call", "sequence": 7, "tool": "exit_plan_mode"})

        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp)
            (session / "plan.md").write_text("# Plan\n", encoding="utf-8")
            (session / "plan_mode.json").write_text(
                '{"state":"Active","awaiting_plan_approval":true}\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(AssertionError, "two-REVISE cap"):
                runner.assert_native_plan_gate(
                    {"events": events, "session_dir": str(session)}
                )

    def test_large_ready_units_requires_envelope_and_slice(self) -> None:
        runner = load_runner_module()
        runner.assert_large_ready_units(
            {
                "ready_units": [
                    {"id": "ENV-test", "kind": "program envelope"},
                    {"id": "S1-test", "kind": "execution slice"},
                ]
            }
        )
        with self.assertRaisesRegex(AssertionError, "distinct envelope and slice"):
            runner.assert_large_ready_units(
                {
                    "ready_units": [
                        {"id": "ENV-1", "kind": "program envelope"},
                        {"id": "ENV-2", "kind": "program envelope"},
                    ]
                }
            )
        with self.assertRaisesRegex(AssertionError, "distinct envelope and slice"):
            runner.assert_large_ready_units(
                {
                    "ready_units": [
                        {"id": "ENV-1", "kind": "program envelope"},
                        {"id": "ENV-2", "kind": "program envelope"},
                        {"id": "S1-test", "kind": "execution slice"},
                    ]
                }
            )
        with self.assertRaisesRegex(AssertionError, "distinct envelope and slice"):
            runner.assert_large_ready_units(
                {
                    "ready_units": [
                        {"id": "S1-test", "kind": "execution slice"},
                        {"id": "ENV-test", "kind": "program envelope"},
                    ]
                }
            )

    def test_recorded_result_covers_all_cue_free_roles(self) -> None:
        runner = load_runner_module()
        payload = json.loads(RESULTS.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "pilotfish-grok.e2e-dispatch.v5")
        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["install"]["policy_version"],
            (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        )
        self.assertEqual(
            payload["install"]["candidate_surface"]["agents_match"],
            runner.ROLES,
        )
        self.assertEqual(
            payload["install"]["candidate_surface"]["roles_match"],
            runner.ROLES,
        )
        self.assertEqual(
            payload["install"]["candidate_surface"]["owned_agent_files"],
            sorted(f"{role}.md" for role in runner.ROLES),
        )
        self.assertEqual(
            payload["install"]["candidate_surface"]["owned_role_files"],
            sorted(f"{role}.toml" for role in runner.ROLES),
        )
        self.assertEqual(
            payload["install"]["candidate_surface"]["unrelated_agent_files"],
            [],
        )
        self.assertEqual(
            payload["install"]["candidate_surface"]["unrelated_role_files"],
            [],
        )
        self.assertEqual(payload["claude_isolation"]["active_claude_entries"], 0)
        self.assertIn(
            "claude", payload["claude_isolation"]["claude_runtime_identifiers"]
        )
        cases = {case["case"]: case for case in payload["cases"]}
        self.assertEqual(
            set(cases),
            {
                "cue-free-discovery",
                "cue-free-mechanical",
                "cue-free-judgment",
                "cue-free-security",
            },
        )
        gate = cases["cue-free-security"]["gate"]
        self.assertTrue(gate["ready_before_exit"])
        self.assertTrue(gate["awaiting_native_approval"])
        self.assertTrue(gate["git_clean_before_approval"])
        self.assertTrue(gate["source_unchanged_before_approval"])
        self.assertEqual(gate["parent_mutation_tools"], [])
        self.assertEqual(gate["write_capable_spawns"], [])
        self.assertTrue(gate["security_review"]["finished_before_readiness"])
        self.assertTrue(
            gate["security_review"]["scout_finished_before_review"]
        )
        self.assertTrue(gate["resumed_after_user_continuation"])
        self.assertEqual(
            gate["implementation"]["alternate_write_capable_spawns"], []
        )
        self.assertEqual(
            gate["implementation"]["changed_files"],
            ["README.md", "auth.py", "test_auth.py"],
        )
        for term in (
            "auth.py",
            "test_auth.py",
            "README.md",
            "hmac.compare_digest",
            "legacy-test-key",
            "non-ASCII",
        ):
            self.assertIn(term, gate["implementation"]["contract_terms"])
        runner.assert_large_ready_units(gate)
        self.assertEqual(
            cases["cue-free-mechanical"]["expected_roles"],
            ["scout", "mech-executor", "verifier"],
        )
        self.assertEqual(
            cases["cue-free-discovery"]["gate"]["discovery"][
                "parent_tools_before_scout"
            ],
            [],
        )
        self.assertEqual(
            cases["cue-free-mechanical"]["gate"]["discovery"][
                "parent_tools_before_scout"
            ],
            [],
        )
        self.assertIn(
            "bounded",
            cases["cue-free-judgment"]["gate"]["verification"]["claim_terms"],
        )
        self.assertTrue(
            cases["cue-free-mechanical"]["gate"]["behavior_probe"]["passed"]
        )
        self.assertTrue(
            cases["cue-free-judgment"]["gate"]["behavior_probe"]["passed"]
        )
        self.assertEqual(
            cases["cue-free-judgment"]["gate"]["behavior_probe"][
                "repository_mutants_rejected"
            ],
            [
                "no-transient-retry",
                "swallow-exhaustion",
                "retry-permanent",
            ],
        )
        self.assertTrue(
            cases["cue-free-security"]["gate"]["behavior_probe"]["passed"]
        )
        for case_name in (
            "cue-free-mechanical",
            "cue-free-judgment",
            "cue-free-security",
        ):
            case_gate = cases[case_name]["gate"]
            self.assertEqual(
                case_gate["implementation"]["parent_mutation_tools"], []
            )
            self.assertEqual(
                case_gate["implementation"]["parent_integration_tools"], []
            )
            self.assertEqual(
                case_gate["implementation"]["alternate_write_capable_spawns"], []
            )
            self.assertLess(
                case_gate["implementation"]["result_ready_sequence"],
                case_gate["verification"]["spawn_sequence"],
            )
            self.assertTrue(case_gate["verification"]["claim_terms"])
        self.assertTrue(payload["cue_free_gate"]["complete"])
        self.assertEqual(payload["cue_free_gate"]["missing_roles"], [])
        self.assertEqual(
            set(payload["cue_free_gate"]["spawned_roles"]), set(runner.ROLES)
        )
        for case in cases.values():
            self.assertTrue(case["cue_free"])
            self.assertEqual(case["session_isolation"]["claude_context_markers"], [])
            self.assertEqual(
                case["session_isolation"]["claude_hook_execution_events"], 0
            )
            for spawn in case["spawns"]:
                self.assertNotIn("raw_input", spawn)

    def test_install_only_probe_when_available(self) -> None:
        if os.environ.get("PILOTFISH_GROK_E2E_SKIP_INSTALL") == "1":
            self.skipTest("install probe disabled")
        if not shutil.which("grok"):
            self.skipTest("grok not on PATH")
        installed_home = Path(os.environ.get("GROK_HOME", Path.home() / ".grok"))
        if not (installed_home / "agents" / "scout.md").is_file():
            self.skipTest("pilotfish-grok not installed")
        with tempfile.TemporaryDirectory() as tmp:
            candidate_home = Path(tmp)
            populate_candidate_home(candidate_home, installed_home)
            proc = subprocess.run(
                ["python3", str(RUNNER), "--skip-live"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=90,
                env={
                    **os.environ,
                    "GROK_HOME": str(candidate_home),
                    "PILOTFISH_GROK_E2E_POLICY": str(
                        ROOT / "templates" / "rules.pilotfish-grok.md"
                    ),
                },
            )
        self.assertEqual(
            proc.returncode,
            0,
            msg=f"stdout={proc.stdout[-2000:]}\nstderr={proc.stderr[-2000:]}",
        )
        self.assertIn('"ok": true', proc.stdout)

    def test_live_dispatch_when_enabled(self) -> None:
        if os.environ.get("PILOTFISH_GROK_E2E") != "1":
            self.skipTest("set PILOTFISH_GROK_E2E=1 to run live model dispatch")
        if not shutil.which("grok"):
            self.skipTest("grok not on PATH")
        proc = subprocess.run(
            ["python3", str(RUNNER)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=3000,
        )
        self.assertEqual(
            proc.returncode,
            0,
            msg=f"stdout={proc.stdout[-3000:]}\nstderr={proc.stderr[-3000:]}",
        )
        self.assertIn('"ok": true', proc.stdout)
        results = (ROOT / "benchmarks" / "e2e-dispatch" / "results.json").read_text(
            encoding="utf-8"
        )
        self.assertIn("scout", results)
        self.assertIn("read-only", results)
        self.assertIn("cue-free-mechanical", results)
        self.assertIn("cue-free-judgment", results)
        self.assertIn("cue-free-security", results)
        self.assertIn('"complete": true', results)
        self.assertIn('"entered_first": true', results)
        self.assertIn('"ready_before_exit": true', results)
        self.assertIn('"awaiting_native_approval": true', results)
        self.assertIn('"tests_passed": true', results)
        self.assertIn('"missing_roles": []', results)
        self.assertIn('"active_claude_entries": 0', results)
        self.assertIn('"claude_hook_execution_events": 0', results)


if __name__ == "__main__":
    unittest.main()
