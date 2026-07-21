#!/usr/bin/env python3
"""Live Grok Build e2e for pilotfish-grok role dispatch.

Proves (against a real grok CLI + network):

1. Named roles from ~/.grok/agents are spawnable via spawn_subagent.
2. Role TOML default_capability_mode is applied at spawn
   (subagent_spawned.capability_mode).
3. Scout can complete a read-only recon task.
4. plan-verifier returns READY/REVISE vocabulary only.
5. verifier spawns with execute capability (read+shell, not write).

Usage:
  python3 benchmarks/e2e-dispatch/run.py
  python3 benchmarks/e2e-dispatch/run.py --skip-live   # install/inspect only

Exit 0 on all assertions. Writes results.json next to this script.
Requires: grok on PATH, authenticated session or XAI_API_KEY, pilotfish-grok
roles installed under ~/.grok (or GROK_HOME).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BENCH = Path(__file__).resolve().parent
RESULTS_PATH = BENCH / "results.json"
INSTALL_ONLY_RESULTS_PATH = BENCH / "results.install-only.json"
MARKER = "PILOTFISH_GROK_E2E_MARKER_42"
MIN_GROK = (0, 2, 106)
EXPECTED_CAPABILITY = {
    "scout": "read-only",
    "plan-verifier": "read-only",
    "security-reviewer": "read-only",
    "mech-executor": "all",
    "executor": "all",
    "verifier": "execute",
    "security-executor": "all",
}
ROLES = list(EXPECTED_CAPABILITY)


def grok_home() -> Path:
    return Path(os.environ.get("GROK_HOME", Path.home() / ".grok")).expanduser()


def parse_version(text: str) -> tuple[int, int, int] | None:
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def run_cmd(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 300,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=merged,
    )


def assert_install_surface() -> dict[str, Any]:
    home = grok_home()
    agents = home / "agents"
    roles = home / "roles"
    policy = home / "rules" / "pilotfish-grok.md"
    missing = []
    for role in ROLES:
        if not (agents / f"{role}.md").is_file():
            missing.append(f"agents/{role}.md")
        if not (roles / f"{role}.toml").is_file():
            missing.append(f"roles/{role}.toml")
    if not policy.is_file():
        missing.append("rules/pilotfish-grok.md")
    if missing:
        raise AssertionError(f"pilotfish-grok install incomplete under {home}: {missing}")

    # capability map from installed role TOMLs
    try:
        import tomllib
    except ImportError:  # pragma: no cover
        import tomli as tomllib  # type: ignore

    caps: dict[str, str] = {}
    for role in ROLES:
        data = tomllib.loads((roles / f"{role}.toml").read_text(encoding="utf-8"))
        caps[role] = data["default_capability_mode"]
        if caps[role] != EXPECTED_CAPABILITY[role]:
            raise AssertionError(
                f"{role} capability {caps[role]!r} != {EXPECTED_CAPABILITY[role]!r}"
            )

    stamp = re.search(r"pilotfish-grok v([\d.]+)", policy.read_text(encoding="utf-8"))
    return {
        "grok_home": str(home),
        "roles_present": ROLES,
        "capabilities": caps,
        "policy_version": stamp.group(1) if stamp else None,
    }


def assert_grok_inspect_lists_roles() -> dict[str, Any]:
    proc = run_cmd(["grok", "inspect"], timeout=60)
    if proc.returncode != 0:
        raise AssertionError(f"grok inspect failed: {proc.stderr or proc.stdout}")
    out = proc.stdout
    found = [r for r in ROLES if re.search(rf"\b{re.escape(r)}\b", out)]
    missing = [r for r in ROLES if r not in found]
    if missing:
        raise AssertionError(f"grok inspect missing roles: {missing}\n---\n{out[:2000]}")
    return {"roles_listed": found, "inspect_chars": len(out)}


def make_fixture(base: Path) -> Path:
    fixture = base / "fixture"
    fixture.mkdir(parents=True)
    (fixture / "secret_marker.txt").write_text(f"{MARKER}\n", encoding="utf-8")
    (fixture / "README.md").write_text(
        "# e2e fixture\n\nNot the marker.\n", encoding="utf-8"
    )
    plan = fixture / "sample-plan.md"
    plan.write_text(
        """# Sample Plan

## Outcome
Confirm e2e marker file exists and is documented.

## Non-goals
No production code changes.

## Scope
- Read secret_marker.txt
- Report path only

## Ownership
scout-owned discovery only.

## Sequence
1. Locate marker
2. Report

## Verification
File contains PILOTFISH_GROK_E2E_MARKER_42

## Budgets
One scout.

## Stop conditions
Marker found or absent after search.
""",
        encoding="utf-8",
    )
    run_cmd(["git", "init"], cwd=fixture, timeout=30)
    run_cmd(["git", "add", "."], cwd=fixture, timeout=30)
    run_cmd(
        ["git", "-c", "user.email=e2e@pilotfish-grok.local", "-c", "user.name=e2e", "commit", "-m", "fixture"],
        cwd=fixture,
        timeout=30,
    )
    return fixture


def find_session_dir(session_id: str) -> Path | None:
    sessions = grok_home() / "sessions"
    if not sessions.is_dir():
        return None
    matches = list(sessions.rglob(session_id))
    for m in matches:
        if m.is_dir() and (m / "updates.jsonl").is_file():
            return m
    return None


def parse_spawn_events(session_dir: Path) -> list[dict[str, Any]]:
    path = session_dir / "updates.jsonl"
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        update = (
            obj.get("params", {}).get("update")
            if isinstance(obj.get("params"), dict)
            else None
        )
        if not isinstance(update, dict):
            continue
        if update.get("sessionUpdate") == "subagent_spawned":
            events.append(
                {
                    "kind": "spawned",
                    "subagent_type": update.get("subagent_type"),
                    "role": update.get("role"),
                    "capability_mode": update.get("capability_mode"),
                    "model": update.get("model"),
                    "subagent_id": update.get("subagent_id"),
                }
            )
        elif update.get("sessionUpdate") == "subagent_finished":
            events.append(
                {
                    "kind": "finished",
                    "subagent_id": update.get("subagent_id"),
                    "status": update.get("status"),
                    "output": update.get("output"),
                    "duration_ms": update.get("duration_ms"),
                }
            )
    return events


def run_grok_prompt(prompt: str, cwd: Path, *, max_turns: int = 16) -> dict[str, Any]:
    args = [
        "grok",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--max-turns",
        str(max_turns),
        "--always-approve",
        "--permission-mode",
        "bypassPermissions",
        "--cwd",
        str(cwd),
        "--no-memory",
    ]
    t0 = time.monotonic()
    proc = run_cmd(args, cwd=cwd, timeout=420)
    wall = time.monotonic() - t0
    if proc.returncode != 0:
        raise AssertionError(
            f"grok failed rc={proc.returncode}\nstdout={proc.stdout[:1500]}\nstderr={proc.stderr[:1500]}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"non-JSON grok output: {proc.stdout[:500]}") from exc
    session_id = payload.get("sessionId")
    if not session_id:
        raise AssertionError(f"missing sessionId in {payload!r}")
    session_dir = find_session_dir(session_id)
    if not session_dir:
        raise AssertionError(f"session dir not found for {session_id}")
    events = parse_spawn_events(session_dir)
    return {
        "session_id": session_id,
        "session_dir": str(session_dir),
        "text": payload.get("text") or "",
        "usage": payload.get("usage"),
        "total_cost_usd": payload.get("total_cost_usd"),
        "num_turns": payload.get("num_turns"),
        "wall_seconds": round(wall, 3),
        "spawn_events": events,
        "model_usage": payload.get("modelUsage"),
    }


def require_spawn(result: dict[str, Any], role: str) -> dict[str, Any]:
    spawned = [
        e
        for e in result["spawn_events"]
        if e.get("kind") == "spawned" and e.get("subagent_type") == role
    ]
    if not spawned:
        raise AssertionError(
            f"no subagent_spawned for {role}; events={result['spawn_events']!r} text={result['text'][:400]!r}"
        )
    event = spawned[0]
    expected = EXPECTED_CAPABILITY[role]
    actual = event.get("capability_mode")
    if actual != expected:
        raise AssertionError(
            f"{role} capability_mode {actual!r} != expected {expected!r}"
        )
    return event


def case_scout(fixture: Path) -> dict[str, Any]:
    prompt = (
        "You MUST call spawn_subagent exactly once with subagent_type=\"scout\" "
        "and background=false. Do not set capability_mode or model. "
        f'Prompt the scout: "Find the file containing {MARKER}. '
        'Reply with file:line only." '
        "After it returns, reply with exactly one line: "
        "SCOUT_OK:<path> or SCOUT_FAIL:<reason>."
    )
    result = run_grok_prompt(prompt, fixture)
    event = require_spawn(result, "scout")
    text = result["text"]
    if "SCOUT_OK:" not in text:
        raise AssertionError(f"scout parent reply missing SCOUT_OK: {text!r}")
    if "secret_marker.txt" not in text and MARKER not in text:
        # path may appear only in subagent output; parent should still surface it
        finished = [e for e in result["spawn_events"] if e.get("kind") == "finished"]
        outputs = " ".join(str(e.get("output") or "") for e in finished)
        if "secret_marker.txt" not in outputs:
            raise AssertionError(f"marker path not found in parent or child output: {text!r} / {outputs!r}")
    return {"case": "scout", "ok": True, "spawn": event, **{k: result[k] for k in ("session_id", "wall_seconds", "total_cost_usd", "num_turns")}}


def case_plan_verifier(fixture: Path) -> dict[str, Any]:
    prompt = (
        "You MUST call spawn_subagent exactly once with subagent_type=\"plan-verifier\" "
        "and background=false. Do not set capability_mode or model. "
        'Prompt: "Read sample-plan.md in the workspace. Return only READY or REVISE '
        'with brief reasons. Do not edit files." '
        "After it returns, reply with exactly one line: "
        "PV_OK:<READY|REVISE> or PV_FAIL:<reason>."
    )
    result = run_grok_prompt(prompt, fixture)
    event = require_spawn(result, "plan-verifier")
    text = result["text"]
    finished = [e for e in result["spawn_events"] if e.get("kind") == "finished"]
    child_out = " ".join(str(e.get("output") or "") for e in finished)
    blob = f"{text}\n{child_out}"
    if not re.search(r"\bREADY\b|\bREVISE\b", blob):
        raise AssertionError(f"plan-verifier missing READY/REVISE: {blob[:800]!r}")
    # must not create unexpected write artifacts
    unexpected = list(fixture.glob("**/plan-verifier-wrote*"))
    if unexpected:
        raise AssertionError(f"plan-verifier wrote files: {unexpected}")
    return {"case": "plan-verifier", "ok": True, "spawn": event, **{k: result[k] for k in ("session_id", "wall_seconds", "total_cost_usd", "num_turns")}}


def case_verifier(fixture: Path) -> dict[str, Any]:
    prompt = (
        "You MUST call spawn_subagent exactly once with subagent_type=\"verifier\" "
        "and background=false. Do not set capability_mode or model. "
        f'Prompt: "Claim: secret_marker.txt contains {MARKER}. '
        "Independently verify by reading the file and/or running a shell command. "
        'Return only CONFIRMED or REFUTED with one evidence line. Do not edit files." '
        "After it returns, reply with exactly one line: "
        "VF_OK:<CONFIRMED|REFUTED> or VF_FAIL:<reason>."
    )
    result = run_grok_prompt(prompt, fixture)
    event = require_spawn(result, "verifier")
    text = result["text"]
    finished = [e for e in result["spawn_events"] if e.get("kind") == "finished"]
    child_out = " ".join(str(e.get("output") or "") for e in finished)
    blob = f"{text}\n{child_out}"
    if not re.search(r"\bCONFIRMED\b|\bREFUTED\b", blob):
        raise AssertionError(f"verifier missing CONFIRMED/REFUTED: {blob[:800]!r}")
    return {"case": "verifier", "ok": True, "spawn": event, **{k: result[k] for k in ("session_id", "wall_seconds", "total_cost_usd", "num_turns")}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help="Only check install surface + grok inspect (no model calls)",
    )
    parser.add_argument(
        "--cases",
        default="scout,plan-verifier,verifier",
        help="Comma-separated live cases (default: scout,plan-verifier,verifier)",
    )
    args = parser.parse_args()

    started = datetime.now(timezone.utc).isoformat()
    results: dict[str, Any] = {
        "schema": "pilotfish-grok.e2e-dispatch.v1",
        "started_at": started,
        "repo": str(ROOT),
        "run_id": str(uuid.uuid4()),
        "cases": [],
        "ok": False,
    }

    try:
        ver_proc = run_cmd(["grok", "--version"], timeout=30)
        version_text = (ver_proc.stdout or ver_proc.stderr or "").strip()
        version = parse_version(version_text)
        results["grok_version_raw"] = version_text
        results["grok_version"] = list(version) if version else None
        if not version or version < MIN_GROK:
            raise AssertionError(
                f"need grok >= {'.'.join(map(str, MIN_GROK))}, got {version_text!r}"
            )

        results["install"] = assert_install_surface()
        results["inspect"] = assert_grok_inspect_lists_roles()

        if args.skip_live:
            results["mode"] = "install-only"
            results["ok"] = True
            results["finished_at"] = datetime.now(timezone.utc).isoformat()
            out_path = INSTALL_ONLY_RESULTS_PATH
            out_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(results, indent=2, ensure_ascii=False))
            return 0

        results["mode"] = "live"
        case_names = [c.strip() for c in args.cases.split(",") if c.strip()]
        runners = {
            "scout": case_scout,
            "plan-verifier": case_plan_verifier,
            "verifier": case_verifier,
        }
        unknown = [c for c in case_names if c not in runners]
        if unknown:
            raise AssertionError(f"unknown cases: {unknown}")

        with tempfile.TemporaryDirectory(prefix="pilotfish-grok-e2e-") as tmp:
            fixture = make_fixture(Path(tmp))
            results["fixture"] = str(fixture)
            for name in case_names:
                print(f"== running case {name} ==", file=sys.stderr)
                case_result = runners[name](fixture)
                results["cases"].append(case_result)
                print(
                    f"OK {name} capability={case_result['spawn'].get('capability_mode')} "
                    f"cost=${case_result.get('total_cost_usd')} wall={case_result.get('wall_seconds')}s",
                    file=sys.stderr,
                )

        results["ok"] = all(c.get("ok") for c in results["cases"])
        results["finished_at"] = datetime.now(timezone.utc).isoformat()
        total_cost = sum(float(c.get("total_cost_usd") or 0) for c in results["cases"])
        results["total_cost_usd"] = total_cost
    except Exception as exc:  # noqa: BLE001 — surface as structured failure
        results["ok"] = False
        results["error"] = f"{type(exc).__name__}: {exc}"
        results["finished_at"] = datetime.now(timezone.utc).isoformat()
        RESULTS_PATH.write_text(
            json.dumps(results, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"E2E FAILED: {exc}", file=sys.stderr)
        return 1

    RESULTS_PATH.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
