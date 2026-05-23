"""Stage 5 helper verification: _codex_rollout.count_mcp_tool_use shape.

The codex 0.130.0 rollout JSONL format was inspected at Phase 4 Stage 5
kickoff (sample file used: rollout from ~/.codex/sessions/2026/05/21/
showed event types session_meta / event_msg / response_item / etc., and
function-call items at payload.type=='function_call'). MCP tool calls
are not yet confirmed by a live MCP-using fixture; that lands at Stage 6
e2e. This test exercises the helper with synthetic JSONL constructed to
match the schema assumed by _codex_rollout.MCP_TOOL_NAME_RE.

If Stage 6 reveals that codex 0.130.0 emits a different shape, fix
_codex_rollout.MCP_TOOL_NAME_RE and any synthesised expectations here.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _codex_rollout import (  # noqa: E402
    MCP_NAMESPACE_RE,
    count_mcp_tool_use,
    find_rollout_for_session,
    iter_events,
    iter_mcp_tool_uses,
)


def _line(type_: str, payload: dict, timestamp: str = "2026-05-22T16:00:00.000Z") -> str:
    return json.dumps({"timestamp": timestamp, "type": type_, "payload": payload})


def _make_rollout(lines: list[str], sessions_root: Path, session_id: str,
                  timestamp_iso: str) -> Path:
    day_dir = sessions_root / "2026" / "05" / "22"
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"rollout-2026-05-22T16-00-00-{session_id}.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # nudge mtime so find_rollout sees the file as fresh
    import os
    import time
    now = time.time()
    os.utime(path, (now, now))
    return path


def check(name: str, cond: bool, detail: str = "") -> bool:
    status = "PASS" if cond else "FAIL"
    suffix = f" -- {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return cond


def main() -> int:
    failures = 0

    # ----- MCP_NAMESPACE_RE shape coverage -----
    # Real codex 0.130.0 rollout shape locked at Stage 6 e2e:
    #   MCP function_call has payload.namespace = "mcp__<server>__"
    #   Built-in function_call has no namespace field at all.
    positives = [
        "mcp__codemetadata__",
        "mcp__1c-codemetadata__",
        "mcp__naparnik__",
        "mcp__a__",
    ]
    negatives = [
        "mcp__codemetadata",
        "codemetadata__",
        "shell_command",
        "Capital__BadCase",
        "mcp__Codemetadata__",
        "mcp____",
        "mcp__",
        "",
    ]
    for n in positives:
        if not check(
            f"MCP_NAMESPACE_RE matches MCP namespace {n!r}",
            bool(MCP_NAMESPACE_RE.match(n)),
        ):
            failures += 1
    for n in negatives:
        if not check(
            f"MCP_NAMESPACE_RE does NOT match non-MCP namespace {n!r}",
            not MCP_NAMESPACE_RE.match(n),
        ):
            failures += 1

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp) / "sessions"

        # ----- synthetic rollout: zero MCP calls -----
        zero_lines = [
            _line("session_meta", {"id": "sess0", "timestamp": "2026-05-22T16:00:00.000Z"}),
            _line("event_msg", {"type": "task_started"}),
            _line("response_item", {"type": "message", "role": "assistant",
                                    "content": [{"type": "output_text", "text": "hello"}]}),
            _line("response_item", {"type": "function_call",
                                    "name": "shell_command",
                                    "arguments": "{\"command\":\"ls\"}",
                                    "call_id": "call_0"}),
            _line("event_msg", {"type": "task_complete"}),
        ]
        zero_path = _make_rollout(zero_lines, tmp_root, "sess0",
                                  "2026-05-22T16:00:00.000Z")
        n0 = count_mcp_tool_use(zero_path)
        if not check(
            "synthetic zero-MCP rollout -> count_mcp_tool_use == 0",
            n0 == 0,
            f"got {n0}",
        ):
            failures += 1

        # ----- synthetic rollout: N=3 MCP calls (mixed with non-MCP) -----
        # Stage 6 lock: MCP iff payload.namespace startswith "mcp__".
        n_lines = [
            _line("session_meta", {"id": "sessN", "timestamp": "2026-05-22T16:00:30.000Z"}),
            _line("event_msg", {"type": "task_started"}),
            _line("response_item", {"type": "function_call",
                                    "name": "get_object_details",
                                    "namespace": "mcp__codemetadata__",
                                    "arguments": "{\"object\":\"Counterparties\"}",
                                    "call_id": "call_a"}),
            _line("response_item", {"type": "function_call",
                                    "name": "shell_command",
                                    "arguments": "{\"command\":\"ls\"}",
                                    "call_id": "call_b"}),
            _line("response_item", {"type": "function_call",
                                    "name": "list_attributes",
                                    "namespace": "mcp__codemetadata__",
                                    "arguments": "{\"object\":\"Counterparties\"}",
                                    "call_id": "call_c"}),
            _line("response_item", {"type": "function_call",
                                    "name": "get_form_layout",
                                    "namespace": "mcp__1c-codemetadata__",
                                    "arguments": "{}",
                                    "call_id": "call_d"}),
            _line("event_msg", {"type": "task_complete"}),
        ]
        n_path = _make_rollout(n_lines, tmp_root, "sessN",
                               "2026-05-22T16:00:30.000Z")
        n3 = count_mcp_tool_use(n_path)
        if not check(
            "synthetic 3-MCP rollout -> count_mcp_tool_use == 3",
            n3 == 3,
            f"got {n3}",
        ):
            failures += 1

        # ----- iter_mcp_tool_uses yields payloads with name + arguments -----
        payloads = list(iter_mcp_tool_uses(n_path))
        if not check(
            "iter_mcp_tool_uses yields 3 payloads",
            len(payloads) == 3,
            f"got {len(payloads)}",
        ):
            failures += 1
        names = [p.get("name") for p in payloads]
        expected_names = [
            "get_object_details",
            "list_attributes",
            "get_form_layout",
        ]
        if not check(
            "iter_mcp_tool_uses yields names in source order",
            names == expected_names,
            f"got {names}",
        ):
            failures += 1
        namespaces = [p.get("namespace") for p in payloads]
        expected_namespaces = [
            "mcp__codemetadata__",
            "mcp__codemetadata__",
            "mcp__1c-codemetadata__",
        ]
        if not check(
            "iter_mcp_tool_uses preserves namespace field",
            namespaces == expected_namespaces,
            f"got {namespaces}",
        ):
            failures += 1

        # ----- find_rollout_for_session picks the matching session by timestamp -----
        chosen = find_rollout_for_session(
            "2026-05-22T16:00:30.500Z",  # matches sessN within tolerance
            sessions_root=tmp_root,
            tolerance_seconds=60.0,
        )
        if not check(
            "find_rollout_for_session matches sessN by timestamp",
            chosen == n_path,
            f"got {chosen}",
        ):
            failures += 1

        chosen_zero = find_rollout_for_session(
            "2026-05-22T16:00:00.500Z",  # matches sess0
            sessions_root=tmp_root,
            tolerance_seconds=5.0,
        )
        if not check(
            "find_rollout_for_session matches sess0 by tight timestamp",
            chosen_zero == zero_path,
            f"got {chosen_zero}",
        ):
            failures += 1

        # ----- find_rollout_for_session with no timestamp -> newest by mtime -----
        chosen_fallback = find_rollout_for_session(
            "",
            sessions_root=tmp_root,
        )
        if not check(
            "find_rollout_for_session('') falls back to newest by mtime",
            chosen_fallback is not None,
            f"got {chosen_fallback}",
        ):
            failures += 1

        # ----- nonexistent root returns None -----
        nope = find_rollout_for_session(
            "2026-05-22T16:00:00.000Z",
            sessions_root=Path(tmp) / "does-not-exist",
        )
        if not check(
            "find_rollout_for_session on missing root -> None",
            nope is None,
        ):
            failures += 1

        # ----- iter_events normalizes the 6-event N=3 fixture -----
        events = list(iter_events(n_path))
        if not check(
            "iter_events yields one dict per non-empty line",
            len(events) == 7,
            f"got {len(events)} events",
        ):
            failures += 1
        kinds = [e["kind"] for e in events]
        expected_kinds = [
            "session_meta",
            "event_msg/task_started",
            "response_item/function_call(mcp)",
            "response_item/function_call(builtin)",
            "response_item/function_call(mcp)",
            "response_item/function_call(mcp)",
            "event_msg/task_complete",
        ]
        if not check(
            "iter_events kinds tag MCP vs builtin",
            kinds == expected_kinds,
            f"got {kinds}",
        ):
            failures += 1
        summaries = [e["summary"] for e in events]
        if not check(
            "iter_events MCP summary includes namespace+name",
            summaries[2].startswith("mcp__codemetadata__get_object_details"),
            f"got {summaries[2]!r}",
        ):
            failures += 1
        if not check(
            "iter_events builtin summary has no namespace prefix",
            summaries[3].startswith("shell_command"),
            f"got {summaries[3]!r}",
        ):
            failures += 1
        if not check(
            "iter_events session_meta summary records id + started_at",
            "id=sessN" in summaries[0] and "started_at=" in summaries[0],
            f"got {summaries[0]!r}",
        ):
            failures += 1

        # ----- iter_events on missing file -> empty -----
        missing_events = list(iter_events(Path(tmp) / "no-such.jsonl"))
        if not check(
            "iter_events on missing file yields nothing",
            missing_events == [],
            f"got {missing_events}",
        ):
            failures += 1

        # ----- iter_events tolerates unparseable lines -----
        broken_path = Path(tmp) / "broken.jsonl"
        broken_path.write_text(
            "\n".join([
                "this is not json",
                _line("event_msg", {"type": "task_started"}),
                "{also broken",
            ]) + "\n",
            encoding="utf-8",
        )
        broken_events = list(iter_events(broken_path))
        if not check(
            "iter_events tolerates unparseable lines (3 yielded)",
            len(broken_events) == 3,
            f"got {len(broken_events)} events",
        ):
            failures += 1
        if not check(
            "iter_events flags unparseable lines",
            broken_events[0]["kind"] == "<unparseable>"
            and broken_events[2]["kind"] == "<unparseable>",
            f"got {[e['kind'] for e in broken_events]}",
        ):
            failures += 1

        # ----- iter_events handles message + user_message -----
        chat_path = Path(tmp) / "chat.jsonl"
        chat_lines = [
            _line("session_meta", {"id": "sessC", "timestamp": "2026-05-22T16:01:00.000Z"}),
            _line("user_message", {"content": "Audit the implementation now."}),
            _line("response_item", {"type": "message", "role": "assistant",
                                    "content": [{"type": "output_text",
                                                 "text": "Reading the SDD."}]}),
            _line("agent_message", {"text": "AUDIT READY"}),
        ]
        chat_path.write_text("\n".join(chat_lines) + "\n", encoding="utf-8")
        chat_events = list(iter_events(chat_path))
        chat_kinds = [e["kind"] for e in chat_events]
        if not check(
            "iter_events normalizes message / user_message / agent_message",
            chat_kinds == ["session_meta", "user_message",
                            "response_item/message", "agent_message"],
            f"got {chat_kinds}",
        ):
            failures += 1
        if not check(
            "iter_events message preview includes role and text",
            chat_events[2]["summary"].startswith("assistant:") and "Reading the SDD" in chat_events[2]["summary"],
            f"got {chat_events[2]['summary']!r}",
        ):
            failures += 1

    if failures:
        print(f"\n{failures} check(s) failed.")
        return 1
    print("\nAll _codex_rollout checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
