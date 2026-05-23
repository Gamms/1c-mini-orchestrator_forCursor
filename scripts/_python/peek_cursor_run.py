"""Tail Cursor agent run output for an orchestrator task phase."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from cursor_sdk import Agent

from orchestrator_config import cursor_api_key_env
from packet_io import load_packet


def _tail_file(path: Path, tail: int) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-tail:]


def _format_sdk_messages(messages: list[object], tail: int) -> None:
    subset = messages[-tail:]
    for idx, message in enumerate(subset, start=max(1, len(messages) - tail + 1)):
        msg_type = getattr(message, "type", "<unknown>")
        if msg_type == "assistant":
            msg = getattr(message, "message", None)
            if msg is not None:
                for block in getattr(msg, "content", ()) or ():
                    btype = getattr(block, "type", "")
                    if btype == "text":
                        text = getattr(block, "text", "") or ""
                        if len(text) > 200:
                            text = text[:200] + "..."
                        print(f"  [{idx}] assistant: {text}")
                    elif btype == "tool_use":
                        name = getattr(block, "name", "?")
                        print(f"  [{idx}] tool_use {name}")
                    elif btype == "tool_result":
                        print(f"  [{idx}] tool_result")
                continue
        print(f"  [{idx}] {msg_type}")


def peek(args: argparse.Namespace) -> int:
    task_root = Path(args.task_root).resolve()
    packet = load_packet(task_root, args.phase)
    if not packet:
        print(f"STATUS: packet_missing for phase={args.phase}")
        return 0

    agent_id = packet.get("cursor_agent_id") or ""
    run_id = packet.get("cursor_run_id") or ""
    log_path = task_root / f"{args.phase}.log"
    status_path = task_root / f"{args.phase}.status"

    print(f"runtime: cursor")
    print(f"phase: {args.phase}")
    print(f"agent_id: {agent_id or '<none>'}")
    print(f"run_id: {run_id or '<none>'}")

    if status_path.exists():
        print(f"status_file: {status_path}")
        for line in _tail_file(status_path, 10):
            print(f"  {line}")

    api_key = os.environ.get(cursor_api_key_env())
    if api_key and agent_id and run_id:
        try:
            run = Agent.get_run(
                run_id,
                runtime="local",
                agent_id=agent_id,
                api_key=api_key,
            )
            if run.supports("conversation"):
                conversation = run.conversation()
                turns = getattr(conversation, "turns", None) or []
                messages: list[object] = []
                for turn in turns:
                    messages.extend(getattr(turn, "messages", ()) or ())
                if messages:
                    print("")
                    print("conversation:")
                    _format_sdk_messages(messages, args.tail)
                    return 0
        except Exception as exc:
            print(f"STATUS: sdk_conversation_unavailable ({exc})")

    if log_path.exists():
        print("")
        print(f"log: {log_path}")
        print(f"size: {log_path.stat().st_size} bytes")
        print("")
        for line in _tail_file(log_path, args.tail):
            print(f"  {line[:240]}")
        mtime = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc)
        age_sec = int((datetime.now(timezone.utc) - mtime).total_seconds())
        print("")
        print(f"LAST_EVENT_AGO={age_sec}s")
        if age_sec > 300:
            print(f"WARNING: {args.phase} may be stuck (no log updates for >300s)")
        return 0

    started_at = packet.get("cursor_started_at")
    if started_at and not run_id:
        print("STATUS: starting (packet stamped, run not created yet)")
    else:
        print("STATUS: not_started_yet (no log or run id)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Peek Cursor agent run for a task phase")
    parser.add_argument("--task-root", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--tail", type=int, default=30)
    return peek(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
