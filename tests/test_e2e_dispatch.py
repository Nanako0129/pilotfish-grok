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
        self.assertIn("enter_plan_mode", text)
        self.assertIn("exit_plan_mode", text)
        self.assertIn("plan.md", text)
        self.assertIn("ready_before_exit", text)
        self.assertIn("max_turns=28", text)
        self.assertIn("timeout_seconds=600", text)
        self.assertIn("git status", text)
        self.assertIn("--skip-live", text)

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
                        "sessionUpdate": "subagent_spawned",
                        "subagent_type": "plan-verifier",
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
                        "output": "REVISE\nClarify ownership.",
                    }
                }
            },
            {
                "params": {
                    "update": {
                        "sessionUpdate": "subagent_spawned",
                        "subagent_type": "plan-verifier",
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
        self.assertEqual(gate["revision_loops"], 1)
        self.assertTrue(gate["fresh_reverification_after_revise"])
        self.assertTrue(gate["ready_before_exit"])
        self.assertTrue(gate["awaiting_native_approval"])

    def test_recorded_result_covers_native_plan_and_bypass(self) -> None:
        payload = json.loads(RESULTS.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "pilotfish-grok.e2e-dispatch.v3")
        self.assertTrue(payload["ok"])
        cases = {case["case"]: case for case in payload["cases"]}
        self.assertEqual(
            set(cases),
            {
                "ambient-native-plan",
                "approval-bypass",
                "scout",
                "plan-verifier",
                "verifier",
            },
        )
        for name in ("ambient-native-plan", "approval-bypass"):
            gate = cases[name]["gate"]
            self.assertTrue(gate["git_clean"])
            self.assertTrue(gate["entered_first"])
            self.assertTrue(gate["fresh_reverification_after_revise"])
            self.assertTrue(gate["ready_before_exit"])
            self.assertTrue(gate["awaiting_native_approval"])
            self.assertEqual(gate["write_capable_spawns"], [])

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
            timeout=900,
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


if __name__ == "__main__":
    unittest.main()
