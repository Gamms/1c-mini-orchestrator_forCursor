"""Shared helpers for parsing codex CLI rollout JSONL artifacts.

The codex CLI (0.130.0) writes one rollout JSONL per session under
`$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl`. Each line
is a JSON event with a `timestamp` and `type` field. Event types
observed in 0.130.0 include:
    session_meta        first line; payload.id is the session UUID
    event_msg           task_started / task_complete / token_count / ...
    response_item       model response items (message / function_call / ...)
    user_message        user prompts
    agent_message       agent text replies

MCP tool calls are surfaced as `response_item` -> `payload.type ==
"function_call"` whose `payload.name` follows the convention
`<server>__<tool>` (double-underscore separator, matching the OpenAI
function-call adapter codex uses for MCP servers). The exact
convention is locked at Phase 4 Stage 6 e2e -- if codex 0.130.0 emits
a different shape, the single fix point is `MCP_TOOL_NAME_RE` below.

This module has no Pydantic imports and no <prior-iteration> imports. Pure stdlib.

Phase 4 Stage 5 -- companion to validate_audit.py.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
from pathlib import Path
from typing import Iterable


# MCP function-call detection.
#
# Stage 6 e2e (example-erp-02) LOCKED the shape: codex 0.130.0 distinguishes MCP
# function_calls from built-ins via a separate `payload.namespace` field,
# NOT via a name-prefix convention. Examples observed in a real
# rollout-2026-05-22T21-35-39-*.jsonl:
#
#   MCP (codemetadata server, single get_object_details query):
#     {"type": "function_call",
#      "name": "get_object_details",
#      "namespace": "mcp__codemetadata__",
#      "arguments": "...",
#      "call_id": "..."}
#
#   Built-in (codex shell + apply_patch surfaces, no namespace field):
#     {"type": "function_call",
#      "name": "shell_command",
#      "arguments": "...",
#      "call_id": "..."}
#     {"type": "function_call",
#      "name": "apply_patch",
#      "arguments": "...",
#      "call_id": "..."}
#
# Pre-Stage-6 implementation used the (wrong) regex
#   ^[a-z0-9][a-z0-9_-]*__[a-z0-9][a-z0-9_-]*$
# matched against payload.name. Stage 6 e2e produced 0 MCP matches on
# a rollout that contained one real codemetadata query (validate_audit
# exit 9). Fix: detect by namespace presence + pattern. Tool name is
# kept in payload.name and surfaced as-is to callers.
MCP_NAMESPACE_RE = re.compile(r"^mcp__[a-z0-9][a-z0-9_-]*__$")

# Back-compat alias (the original public symbol name). Old callers
# checking name shape will now get False on every name -- correct, since
# MCP detection no longer lives on name.
MCP_TOOL_NAME_RE = MCP_NAMESPACE_RE


def _is_mcp_function_call(payload: dict) -> bool:
    """Return True iff payload is a function_call from an MCP server.

    Stage 6 contract: payload must have type=function_call AND a
    `namespace` string matching MCP_NAMESPACE_RE.
    """
    if payload.get("type") != "function_call":
        return False
    ns = payload.get("namespace")
    if not isinstance(ns, str):
        return False
    return bool(MCP_NAMESPACE_RE.match(ns))


def _codex_sessions_root() -> Path:
    """Resolve the codex sessions root.

    Honours $CODEX_HOME if set (codex 0.130.0 reads this); falls back to
    ~/.codex/sessions otherwise. The auditor session sets $CODEX_HOME
    to a per-task directory, so rollout discovery must follow the same
    redirect or it will look in the wrong place.
    """
    codex_home = os.environ.get("CODEX_HOME", "").strip()
    if codex_home:
        root = Path(codex_home) / "sessions"
    else:
        root = Path(os.path.expanduser("~/.codex")) / "sessions"
    return root


def _parse_session_meta(line: str) -> dict | None:
    """Return the session_meta payload dict from a single JSONL line, or None."""
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(ev, dict):
        return None
    if ev.get("type") != "session_meta":
        return None
    payload = ev.get("payload")
    return payload if isinstance(payload, dict) else None


def find_rollout_for_session(
    started_at_iso: str,
    sessions_root: Path | None = None,
    tolerance_seconds: float = 60.0,
) -> Path | None:
    """Locate the rollout file for the auditor's codex session.

    Search strategy:
      1. Parse `started_at_iso` (ISO-8601). If absent, return the newest
         rollout under today's date directory (best-effort fallback).
      2. Scan rollout files under sessions_root whose mtime is >=
         started_at_iso - tolerance_seconds.
      3. For each candidate, parse the first line (session_meta) and
         compare its `payload.timestamp` against started_at_iso. The
         closest match within tolerance wins.

    Returns None if no rollout file exists at all (e.g. codex has not
    run yet, or sessions_root does not exist).
    """
    root = sessions_root if sessions_root is not None else _codex_sessions_root()
    if not root.exists() or not root.is_dir():
        return None

    rollouts = sorted(
        root.rglob("rollout-*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not rollouts:
        return None

    target_ts = _parse_iso(started_at_iso)
    if target_ts is None:
        return rollouts[0]

    best: tuple[float, Path] | None = None
    for path in rollouts:
        mtime = path.stat().st_mtime
        if mtime < target_ts - tolerance_seconds:
            continue
        first_line = _first_nonempty_line(path)
        if first_line is None:
            continue
        meta = _parse_session_meta(first_line)
        if not meta:
            continue
        meta_ts = _parse_iso(meta.get("timestamp", "") or "")
        if meta_ts is None:
            continue
        delta = abs(meta_ts - target_ts)
        if delta > tolerance_seconds:
            continue
        if best is None or delta < best[0]:
            best = (delta, path)

    if best is not None:
        return best[1]
    return rollouts[0]


def _first_nonempty_line(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\r\n")
                if line.strip():
                    return line
    except OSError:
        return None
    return None


def _parse_iso(stamp: str) -> float | None:
    if not stamp:
        return None
    s = stamp.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return _dt.datetime.fromisoformat(s).timestamp()
    except (ValueError, TypeError):
        return None


def iter_mcp_tool_uses(rollout_path: Path) -> Iterable[dict]:
    """Yield each MCP function-call payload dict from a codex rollout.

    A function-call event is matched when:
        ev["type"] == "response_item"
        ev["payload"]["type"] == "function_call"
        ev["payload"]["namespace"] matches MCP_NAMESPACE_RE

    The yielded dict is the payload itself, so callers can read
    `name`, `namespace`, `arguments`, `call_id` directly.

    Tolerates malformed lines silently. If the file does not exist,
    yields nothing.
    """
    if not rollout_path.exists() or not rollout_path.is_file():
        return
    try:
        text = rollout_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        if ev.get("type") != "response_item":
            continue
        payload = ev.get("payload")
        if not isinstance(payload, dict):
            continue
        if _is_mcp_function_call(payload):
            yield payload


def count_mcp_tool_use(rollout_path: Path) -> int:
    """Count MCP function-call events in a single rollout file."""
    return sum(1 for _ in iter_mcp_tool_uses(rollout_path))


def iter_events(rollout_path: Path) -> Iterable[dict]:
    """Yield normalized event dicts from a codex rollout file.

    Each yielded dict has:
        kind:    short event kind tag, one of:
                   "session_meta",
                   "event_msg/<subtype>"           (event_msg with payload.type)
                   "response_item/function_call",
                   "response_item/message",
                   "response_item/<payload_type>", (other response_item kinds)
                   "user_message",
                   "agent_message",
                   "<other>"                       (unknown event type)
                   "<unparseable>"                 (json failed)
        ts:      timestamp string from event (may be empty)
        summary: human-readable preview (function name + truncated args,
                 message text preview, payload subtype)

    Tolerates malformed lines (yields kind="<unparseable>" with raw preview).
    If the file does not exist, yields nothing.
    """
    if not rollout_path.exists() or not rollout_path.is_file():
        return
    try:
        text = rollout_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        try:
            ev = json.loads(s)
        except json.JSONDecodeError:
            preview = s[:80]
            yield {"kind": "<unparseable>", "ts": "", "summary": preview}
            continue
        if not isinstance(ev, dict):
            yield {"kind": "<unparseable>", "ts": "", "summary": s[:80]}
            continue
        ts = ev.get("timestamp", "") or ""
        etype = ev.get("type", "")
        payload = ev.get("payload")
        if etype == "session_meta":
            sid = ""
            mts = ""
            if isinstance(payload, dict):
                sid = str(payload.get("id", ""))
                mts = str(payload.get("timestamp", ""))
            yield {"kind": "session_meta", "ts": ts,
                   "summary": f"id={sid} started_at={mts}"}
            continue
        if etype == "event_msg":
            sub = ""
            if isinstance(payload, dict):
                sub = str(payload.get("type", ""))
            kind = f"event_msg/{sub}" if sub else "event_msg"
            extra = ""
            if isinstance(payload, dict):
                copy = {k: v for k, v in payload.items() if k != "type"}
                if copy:
                    extra = json.dumps(copy, ensure_ascii=False)
                    if len(extra) > 120:
                        extra = extra[:120] + "..."
            yield {"kind": kind, "ts": ts, "summary": extra}
            continue
        if etype == "response_item":
            if not isinstance(payload, dict):
                yield {"kind": "response_item", "ts": ts, "summary": ""}
                continue
            ptype = str(payload.get("type", ""))
            if ptype == "function_call":
                name = str(payload.get("name", ""))
                args = payload.get("arguments", "")
                if not isinstance(args, str):
                    args = json.dumps(args, ensure_ascii=False)
                if len(args) > 100:
                    args = args[:100] + "..."
                is_mcp = _is_mcp_function_call(payload)
                tag = "mcp" if is_mcp else "builtin"
                ns = payload.get("namespace", "") if is_mcp else ""
                label = f"{ns}{name}" if ns else name
                yield {"kind": f"response_item/function_call({tag})",
                       "ts": ts,
                       "summary": f"{label} {args}".strip()}
                continue
            if ptype == "message":
                role = str(payload.get("role", ""))
                text_preview = ""
                content = payload.get("content")
                if isinstance(content, list):
                    parts = []
                    for c in content:
                        if not isinstance(c, dict):
                            continue
                        ctext = c.get("text")
                        if isinstance(ctext, str):
                            parts.append(ctext)
                    text_preview = " ".join(parts).strip()
                    if len(text_preview) > 200:
                        text_preview = text_preview[:200] + "..."
                yield {"kind": "response_item/message", "ts": ts,
                       "summary": f"{role}: {text_preview}"}
                continue
            yield {"kind": f"response_item/{ptype}", "ts": ts, "summary": ""}
            continue
        if etype == "user_message" or etype == "agent_message":
            text_preview = ""
            if isinstance(payload, dict):
                content = payload.get("content") or payload.get("text") or ""
                if isinstance(content, list):
                    parts = []
                    for c in content:
                        if isinstance(c, dict) and isinstance(c.get("text"), str):
                            parts.append(c["text"])
                    text_preview = " ".join(parts).strip()
                elif isinstance(content, str):
                    text_preview = content.strip()
            if len(text_preview) > 200:
                text_preview = text_preview[:200] + "..."
            yield {"kind": etype, "ts": ts, "summary": text_preview}
            continue
        yield {"kind": etype or "<unknown>", "ts": ts, "summary": ""}


__all__ = [
    "MCP_NAMESPACE_RE",
    "MCP_TOOL_NAME_RE",
    "find_rollout_for_session",
    "iter_mcp_tool_uses",
    "count_mcp_tool_use",
    "iter_events",
]
