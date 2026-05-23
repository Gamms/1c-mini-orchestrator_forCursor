"""Cancel a running Cursor agent phase for an orchestrator task."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from cursor_sdk import Agent
from cursor_sdk.errors import CursorAgentError

from orchestrator_config import cursor_api_key_env
from packet_io import update_packet, utc_now_iso


def cancel(args: argparse.Namespace) -> int:
    task_root = Path(args.task_root).resolve()
    from packet_io import load_packet

    packet = load_packet(task_root, args.phase)
    agent_id = packet.get("cursor_agent_id") or ""
    run_id = packet.get("cursor_run_id") or ""

    if not agent_id or not run_id:
        print(f"STATUS: no_cursor_run (agent_id={agent_id!r}, run_id={run_id!r})")
        return 2

    api_key = os.environ.get(cursor_api_key_env())
    if not api_key:
        print(f"{cursor_api_key_env()} is not set", file=sys.stderr)
        return 1

    try:
        run = Agent.get_run(
            run_id,
            runtime="local",
            agent_id=agent_id,
            api_key=api_key,
        )
        if run.supports("cancel"):
            run.cancel()
            update_packet(
                task_root,
                args.phase,
                cursor_run_status="cancelled",
                killed_at=utc_now_iso(),
            )
            print(f"cancelled run_id={run_id} agent_id={agent_id}")
            return 0
        reason = run.unsupported_reason("cancel")
        print(f"STATUS: cancel_unsupported ({reason})")
        return 2
    except CursorAgentError as exc:
        print(f"cancel failed: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cancel Cursor agent run")
    parser.add_argument("--task-root", required=True)
    parser.add_argument("--phase", required=True)
    return cancel(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
