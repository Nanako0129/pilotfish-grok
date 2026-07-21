"""Optional e2e harness hooks.

Default unit suite stays offline. Live dispatch is gated by
PILOTFISH_GROK_E2E=1. Install-only probe runs when grok + install are present
unless PILOTFISH_GROK_E2E_SKIP_INSTALL=1.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "benchmarks" / "e2e-dispatch" / "run.py"


class E2EDispatchTests(unittest.TestCase):
    def test_runner_exists_and_is_executable_doc(self) -> None:
        self.assertTrue(RUNNER.is_file())
        text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("subagent_spawned", text)
        self.assertIn("capability_mode", text)
        self.assertIn("approval-bypass", text)
        self.assertIn("git status", text)
        self.assertIn("--skip-live", text)

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
        self.assertIn("approval-bypass", results)
        self.assertIn('"git_clean": true', results)


if __name__ == "__main__":
    unittest.main()
