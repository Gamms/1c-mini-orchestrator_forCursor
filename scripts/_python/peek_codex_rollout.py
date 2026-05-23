"""Peek a codex rollout file -- formatted tail for Phase 4 Stage 7.

Resolves the rollout file under a per-task codex_home, prints the last N
events using _codex_rollout.iter_events(), and emits a LAST_EVENT_AGO
health line. ASCII-only output.

Invoked by scripts/peek-auditor.ps1. Stand-alone CLI so the PowerShell
wrapper does not need to parse JSONL itself (parity with how Phase 3
peek scripts shell out to PowerShell's ConvertFrom-Json, except codex
schema is alien enough that pushing parsing into Python is cleaner).

Args:
  --codex-home <path>    Absolute path to the per-task .codex_home dir
                         containing sessions/<YYYY>/<MM>/<DD>/rollout-*.jsonl
  --started-at <iso>     Auditor session start timestamp (ISO-8601).
                         Used to disambiguate when multiple rollouts
                         exist. Optional -- falls back to newest by mtime.
  --task-id <id>         Optional cross-check: when set, peek prefers
                         the rollout whose first user_message mentions
                         this task id. Soft check; not used in v1
                         (best-effort fallback only).
  --tail <N>             Number of trailing events to print. Default 30.

Exits 0 on success even if the rollout file is missing (prints a
STATUS: header indicating not_started_yet).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _codex_rollout import (  # noqa: E402
    find_rollout_for_session,
    iter_events,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Peek a codex rollout tail.")
    parser.add_argument("--codex-home", required=True, type=str)
    parser.add_argument("--started-at", default="", type=str)
    parser.add_argument("--task-id", default="", type=str)
    parser.add_argument("--tail", default=30, type=int)
    args = parser.parse_args(argv)

    codex_home = Path(args.codex_home)
    sessions_root = codex_home / "sessions"
    if not sessions_root.exists() or not sessions_root.is_dir():
        print(f"STATUS: not_started_yet (no sessions dir under {codex_home})")
        return 0

    rollout = find_rollout_for_session(
        args.started_at,
        sessions_root=sessions_root,
        tolerance_seconds=120.0,
    )
    if rollout is None:
        print(f"STATUS: not_started_yet (no rollout file under {sessions_root})")
        return 0

    try:
        size = rollout.stat().st_size
        mtime = rollout.stat().st_mtime
    except OSError as exc:
        print(f"STATUS: stat_failed ({exc})")
        return 0

    print(f"session: {rollout}")
    print(f"size: {size} bytes")
    print()

    events = list(iter_events(rollout))
    if args.tail > 0:
        tail = events[-args.tail:]
    else:
        tail = events

    start_idx = len(events) - len(tail)
    for offset, ev in enumerate(tail):
        idx = start_idx + offset + 1
        kind = ev.get("kind", "<unknown>")
        summary = ev.get("summary", "")
        if summary:
            print(f"  [{idx}] {kind} {summary}")
        else:
            print(f"  [{idx}] {kind}")

    age_sec = int(time.time() - mtime)
    print()
    print(f"LAST_EVENT_AGO={age_sec}s")
    if age_sec > 300:
        print("WARNING: auditor may be stuck (no events for >300s)")
    print(f"EVENTS_TOTAL={len(events)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
