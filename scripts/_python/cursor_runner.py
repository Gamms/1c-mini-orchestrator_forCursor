"""Run an L3 orchestrator phase via the Cursor SDK (local agent)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

from cursor_sdk import Agent, LocalAgentOptions, SendOptions
from cursor_sdk.errors import CursorAgentError

from mcp_from_task import load_mcp_servers
from orchestrator_config import cursor_api_key_env, cursor_model, load_cursor_api_key
from packet_io import update_packet, utc_now_iso
from win_bridge import ensure_cursor_bridge

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PHASE_PROMPT_FILES: dict[str, str] = {
    "analyst": "prompt.md",
    "sdd-writer": "prompt.sdd-writer.md",
    "implementer": "prompt.implementer.md",
    "auditor": "prompt.auditor.md",
}

PHASE_LOG_FILES: dict[str, str] = {
    "analyst": "analyst.log",
    "sdd-writer": "sdd-writer.log",
    "implementer": "implementer.log",
    "auditor": "auditor.log",
}


def _unique_paths(*paths: str | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in paths:
        if not raw:
            continue
        resolved = str(Path(raw).resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def _write_status(path: Path, **fields: object) -> None:
    lines = [f"{key}={value}" for key, value in fields.items()]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _extract_text(message: object) -> str:
    msg_type = getattr(message, "type", "")
    if msg_type != "assistant":
        return ""
    msg = getattr(message, "message", None)
    if msg is None:
        return ""
    chunks: list[str] = []
    for block in getattr(msg, "content", ()) or ():
        if getattr(block, "type", "") == "text":
            chunks.append(getattr(block, "text", "") or "")
    return "".join(chunks)


def run_phase(args: argparse.Namespace) -> int:
    task_root = Path(args.task_root).resolve()
    phase = args.phase
    if phase not in PHASE_PROMPT_FILES:
        print(f"unknown phase: {phase}", file=sys.stderr)
        return 1

    prompt_path = task_root / PHASE_PROMPT_FILES[phase]
    if not prompt_path.exists():
        print(f"prompt file missing: {prompt_path}", file=sys.stderr)
        return 1

    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        print(f"prompt file empty: {prompt_path}", file=sys.stderr)
        return 1

    try:
        mcp_servers = load_mcp_servers(task_root, phase)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    cwds = _unique_paths(
        str(task_root),
        args.project_path,
        args.orchestrator_root,
        args.path_local,
        args.extra_writable_dir,
    )
    if not cwds:
        print("no cwd paths resolved", file=sys.stderr)
        return 1

    api_key_env = cursor_api_key_env()
    api_key = load_cursor_api_key()
    if not api_key:
        print(f"{api_key_env} is not set", file=sys.stderr)
        return 1

    model = cursor_model(args.model or None)
    log_path = task_root / PHASE_LOG_FILES[phase]
    status_path = task_root / f"{phase}.status"
    started_at = utc_now_iso()

    update_packet(
        task_root,
        phase,
        runtime="cursor",
        cursor_model=model,
        cursor_started_at=started_at,
    )

    exit_code = 99
    agent_id = ""
    run_id = ""
    run_status = "error"
    try:
        ensure_cursor_bridge(task_root)
        with Agent.create(
            model=model,
            api_key=api_key,
            local=LocalAgentOptions(cwd=cwds, setting_sources=[]),
        ) as agent:
            agent_id = agent.agent_id
            update_packet(task_root, phase, cursor_agent_id=agent_id)

            run = agent.send(prompt, SendOptions(mcp_servers=mcp_servers))
            run_id = run.run_id
            update_packet(task_root, phase, cursor_run_id=run_id)

            print(f"cursor agent_id={agent_id} run_id={run_id} phase={phase}")
            sys.stdout.flush()

            with log_path.open("w", encoding="utf-8") as log_file:
                for message in run.stream():
                    log_file.write(json.dumps(getattr(message, "__dict__", str(message)), default=str))
                    log_file.write("\n")
                    text = _extract_text(message)
                    if text:
                        print(text, end="", flush=True)

            result = run.wait()
            run_status = str(getattr(result, "status", "") or "error")
            exit_code = 0 if run_status == "finished" else 2
    except CursorAgentError as exc:
        print(f"cursor startup failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        exit_code = 1
    except Exception as exc:  # pragma: no cover
        print(f"cursor run failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        exit_code = 99
    finally:
        ended_at = utc_now_iso()
        update_packet(
            task_root,
            phase,
            cursor_agent_id=agent_id or None,
            cursor_run_id=run_id or None,
            cursor_run_status=run_status,
            cursor_finished_at=ended_at,
        )
        _write_status(
            status_path,
            phase=phase,
            agent_id=agent_id,
            run_id=run_id,
            status=run_status,
            exit=exit_code,
            started_at=started_at,
            ended_at=ended_at,
            log=str(log_path),
        )

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an orchestrator L3 phase via Cursor SDK")
    parser.add_argument("--phase", required=True, choices=sorted(PHASE_PROMPT_FILES))
    parser.add_argument("--task-root", required=True)
    parser.add_argument("--project-path", default="")
    parser.add_argument("--orchestrator-root", default="")
    parser.add_argument("--path-local", default="")
    parser.add_argument("--extra-writable-dir", default="")
    parser.add_argument("--model", default="")
    return run_phase(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
