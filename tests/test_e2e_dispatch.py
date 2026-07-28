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


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "benchmarks" / "e2e-dispatch" / "run.py"
RESULTS = ROOT / "benchmarks" / "e2e-dispatch" / "results.json"


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
        for verdict in ("CONFIRMED", "**CONFIRMED**", "## **CONFIRMED**\nEvidence"):
            self.assertTrue(runner.is_confirmed(verdict))
        self.assertFalse(runner.is_confirmed("REFUTED"))
        self.assertFalse(runner.is_confirmed("Evidence\nCONFIRMED"))
        self.assertFalse(
            runner.is_confirmed("REFUTED\nCONFIRMED behavior would require more")
        )
        self.assertFalse(runner.is_confirmed("CONFIRMED\nREFUTED by this probe"))

    def test_executor_ownership_and_verifier_claim_are_enforced(self) -> None:
        runner = load_runner_module()
        events = [
            {
                "kind": "spawned",
                "sequence": 1,
                "subagent_type": "executor",
                "capability_mode": "all",
                "subagent_id": "executor-1",
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
                "capability_mode": "all",
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
            gate = runner.assert_native_plan_gate(
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
        self.assertEqual(payload["claude_isolation"]["active_claude_entries"], 0)
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
        self.assertEqual(gate["write_capable_spawns"], [])
        self.assertTrue(gate["security_review"]["finished_before_readiness"])
        self.assertTrue(gate["resumed_after_user_continuation"])
        self.assertEqual(
            gate["implementation"]["alternate_write_capable_spawns"], []
        )
        runner.assert_large_ready_units(gate)
        self.assertEqual(
            cases["cue-free-mechanical"]["expected_roles"],
            ["scout", "mech-executor", "verifier"],
        )
        self.assertIn(
            "bounded",
            cases["cue-free-judgment"]["gate"]["verification"]["claim_terms"],
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
        home = Path(os.environ.get("GROK_HOME", Path.home() / ".grok"))
        if not (home / "agents" / "scout.md").is_file():
            self.skipTest("pilotfish-grok not installed")
        proc = subprocess.run(
            ["python3", str(RUNNER), "--skip-live"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=90,
            env={
                **os.environ,
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
