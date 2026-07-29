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
                            "update": {"sessionUpdate": "hook_execution"}
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(AssertionError, "executed 1 startup/runtime hooks"):
                runner.assert_session_claude_isolated(session)

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

    def test_recorded_result_has_known_release_provenance(self) -> None:
        runner = load_runner_module()
        payload = json.loads(RESULTS.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "pilotfish-grok.e2e-dispatch.v4")
        self.assertTrue(payload["ok"])
        current = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertIn(
            payload["install"]["policy_version"],
            {"1.0.5", current},
        )
        self.assertEqual(payload["claude_isolation"]["active_claude_entries"], 0)
        cases = {case["case"]: case for case in payload["cases"]}
        self.assertEqual(
            set(cases),
            {
                "ambient-native-plan",
                "approval-bypass",
                "claude-isolation",
                "scout",
                "plan-verifier",
                "verifier",
            },
        )
        for name in ("ambient-native-plan", "approval-bypass"):
            gate = cases[name]["gate"]
            self.assertTrue(gate["git_clean"])
            self.assertTrue(gate["entered_first"])
            self.assertEqual(
                gate["fresh_reverification_after_revise"],
                gate["revision_loops"] > 0,
            )
            self.assertTrue(gate["ready_before_exit"])
            self.assertTrue(gate["awaiting_native_approval"])
            self.assertEqual(gate["write_capable_spawns"], [])
            self.assertTrue(
                gate["security_review"]["finished_before_readiness"]
            )
            self.assertTrue(
                gate["security_review"]["dispositions_presented_to_readiness"]
            )
            self.assertEqual(
                set(gate["security_review"]["covered_readiness_unit_ids"]),
                {unit["id"] for unit in gate["ready_units"]},
            )
            runner.assert_large_ready_units(gate)
        isolation_gate = cases["claude-isolation"]["gate"]
        self.assertTrue(isolation_gate["explore_denied"])
        self.assertTrue(isolation_gate["claude_plugin_agent_denied"])
        self.assertEqual(isolation_gate["foreign_spawns"], [])
        for case in cases.values():
            self.assertEqual(case["session_isolation"]["claude_context_markers"], [])
            self.assertEqual(case["session_isolation"]["hook_execution_events"], 0)
            if "spawn" in case:
                self.assertNotIn("raw_input", case["spawn"])

    def test_install_only_probe_when_available(self) -> None:
        if os.environ.get("PILOTFISH_GROK_E2E_SKIP_INSTALL") == "1":
            self.skipTest("install probe disabled")
        if not shutil.which("grok"):
            self.skipTest("grok not on PATH")
        home = Path(os.environ.get("GROK_HOME", Path.home() / ".grok"))
        if not (home / "agents" / "scout.md").is_file():
            self.skipTest("pilotfish-grok not installed")
        runner = load_runner_module()
        try:
            runner.assert_install_surface()
        except AssertionError as exc:
            if "installed policy version" in str(exc):
                self.skipTest(str(exc))
            raise
        proc = subprocess.run(
            ["python3", str(RUNNER), "--skip-live"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=90,
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
        self.assertIn("ambient-native-plan", results)
        self.assertIn("approval-bypass", results)
        self.assertIn('"entered_first": true', results)
        self.assertIn('"ready_before_exit": true', results)
        self.assertIn('"awaiting_native_approval": true', results)
        self.assertIn('"git_clean": true', results)
        self.assertIn('"active_claude_entries": 0', results)
        self.assertIn('"hook_execution_events": 0', results)


if __name__ == "__main__":
    unittest.main()
