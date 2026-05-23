"""Phase 4 Stage 7: peek_codex_rollout CLI smoke fixtures.

Exercises the CLI end-to-end against synthetic codex_home dirs:
  - missing sessions dir -> STATUS: not_started_yet
  - empty sessions dir   -> STATUS: not_started_yet
  - rollout present      -> "session: ..." + tail of events + LAST_EVENT_AGO
  - aged rollout (mtime backdated >300s) -> WARNING line
  - --tail bounds        -> printed indices respect requested tail size

The peek CLI is invoked as a subprocess to mirror how peek-auditor.ps1
calls it. Captures stdout/stderr and asserts on substrings.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PEEK_CLI = HERE / "peek_codex_rollout.py"


def _line(type_: str, payload: dict, timestamp: str = "2026-05-22T17:00:00.000Z") -> str:
    return json.dumps({"timestamp": timestamp, "type": type_, "payload": payload})


def _run(codex_home: Path, **kw) -> subprocess.CompletedProcess:
    started_at = kw.get("started_at", "")
    task_id = kw.get("task_id", "")
    tail = kw.get("tail", 30)
    args = [
        sys.executable, str(PEEK_CLI),
        "--codex-home", str(codex_home),
        "--started-at", started_at,
        "--task-id", task_id,
        "--tail", str(tail),
    ]
    return subprocess.run(args, capture_output=True, text=True, check=False)


def check(name: str, cond: bool, detail: str = "") -> bool:
    status = "PASS" if cond else "FAIL"
    suffix = f" -- {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return cond


def main() -> int:
    failures = 0

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # ----- missing sessions dir -----
        ch_missing = tmp_path / "codex_home_missing"
        ch_missing.mkdir()
        r = _run(ch_missing)
        if not check(
            "missing sessions dir -> STATUS: not_started_yet, exit 0",
            r.returncode == 0 and "not_started_yet" in r.stdout,
            f"exit={r.returncode} stdout={r.stdout!r}",
        ):
            failures += 1

        # ----- empty sessions dir -----
        ch_empty = tmp_path / "codex_home_empty"
        (ch_empty / "sessions").mkdir(parents=True)
        r = _run(ch_empty)
        if not check(
            "empty sessions dir -> STATUS: not_started_yet",
            r.returncode == 0 and "not_started_yet" in r.stdout,
            f"exit={r.returncode} stdout={r.stdout!r}",
        ):
            failures += 1

        # ----- rollout present (fresh) -----
        ch_fresh = tmp_path / "codex_home_fresh"
        sessions = ch_fresh / "sessions" / "2026" / "05" / "22"
        sessions.mkdir(parents=True)
        rollout = sessions / "rollout-2026-05-22T17-00-00-sessP.jsonl"
        rollout.write_text("\n".join([
            _line("session_meta", {"id": "sessP",
                                    "timestamp": "2026-05-22T17:00:00.000Z"}),
            _line("event_msg", {"type": "task_started"}),
            _line("response_item", {"type": "function_call",
                                    "name": "get_object_details",
                                    "namespace": "mcp__codemetadata__",
                                    "arguments": "{\"object\":\"Counterparties\"}",
                                    "call_id": "c0"}),
            _line("event_msg", {"type": "task_complete"}),
        ]) + "\n", encoding="utf-8")
        now = time.time()
        os.utime(rollout, (now, now))

        r = _run(ch_fresh, started_at="2026-05-22T17:00:00.500Z", tail=10)
        if not check(
            "fresh rollout -> session: header present",
            r.returncode == 0 and "session: " in r.stdout,
            f"exit={r.returncode} stdout={r.stdout!r}",
        ):
            failures += 1
        if not check(
            "fresh rollout -> MCP function_call event printed with namespace",
            "mcp__codemetadata__get_object_details" in r.stdout
            and "function_call(mcp)" in r.stdout,
            f"stdout={r.stdout!r}",
        ):
            failures += 1
        if not check(
            "fresh rollout -> LAST_EVENT_AGO header present",
            "LAST_EVENT_AGO=" in r.stdout,
            f"stdout={r.stdout!r}",
        ):
            failures += 1
        if not check(
            "fresh rollout -> no WARNING line",
            "WARNING:" not in r.stdout,
            f"stdout={r.stdout!r}",
        ):
            failures += 1
        if not check(
            "fresh rollout -> EVENTS_TOTAL=4",
            "EVENTS_TOTAL=4" in r.stdout,
            f"stdout={r.stdout!r}",
        ):
            failures += 1

        # ----- aged rollout (mtime backdated >300s) -----
        ch_aged = tmp_path / "codex_home_aged"
        sessions = ch_aged / "sessions" / "2026" / "05" / "22"
        sessions.mkdir(parents=True)
        aged_rollout = sessions / "rollout-2026-05-22T17-00-00-sessA.jsonl"
        aged_rollout.write_text("\n".join([
            _line("session_meta", {"id": "sessA",
                                    "timestamp": "2026-05-22T17:00:00.000Z"}),
            _line("event_msg", {"type": "task_started"}),
        ]) + "\n", encoding="utf-8")
        long_ago = time.time() - 600
        os.utime(aged_rollout, (long_ago, long_ago))

        r = _run(ch_aged)
        if not check(
            "aged rollout -> WARNING line",
            "WARNING:" in r.stdout,
            f"stdout={r.stdout!r}",
        ):
            failures += 1

        # ----- --tail respects bound -----
        ch_many = tmp_path / "codex_home_many"
        sessions = ch_many / "sessions" / "2026" / "05" / "22"
        sessions.mkdir(parents=True)
        many_rollout = sessions / "rollout-2026-05-22T17-00-00-sessM.jsonl"
        many_events = [_line("session_meta", {"id": "sessM",
                                              "timestamp": "2026-05-22T17:00:00.000Z"})]
        for i in range(15):
            many_events.append(_line("event_msg",
                                     {"type": "token_count", "count": i}))
        many_rollout.write_text("\n".join(many_events) + "\n", encoding="utf-8")
        now = time.time()
        os.utime(many_rollout, (now, now))

        r = _run(ch_many, tail=5)
        if not check(
            "tail=5 prints exactly 5 indexed lines",
            r.stdout.count("\n  [") == 5,
            f"stdout={r.stdout!r}",
        ):
            failures += 1
        if not check(
            "tail=5 indices are last 5 of 16 events (12..16)",
            "[12]" in r.stdout and "[16]" in r.stdout
            and "[11]" not in r.stdout,
            f"stdout={r.stdout!r}",
        ):
            failures += 1

    if failures:
        print(f"\n{failures} peek-codex-rollout check(s) failed.")
        return 1
    print("\nAll peek_codex_rollout checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
