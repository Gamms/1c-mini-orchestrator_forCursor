"""Shared helpers for parsing Claude Code session.jsonl artifacts.

Factored out of validate_sdd.py during Phase 3 Stage 5 (per Phase 3 SDD
OQ9 resolution): both validate_sdd.py (Phase 2) and validate_impl.py
(Phase 3) need the same parser + partitioning logic. Parsing the
Claude Code session.jsonl format is a system contract, not a per-phase
contract -- single source of truth wins over schema-style
standalone-ness.

Behavioural invariants:
- The cwd-encoded session dir is shared across analyst, writer, and
  (Phase 3) implementer because all three spawn with CWD = task_root.
- Their jsonls are differentiated by mtime relative to packet
  cutoff timestamps recorded at spawn time
  (sdd_writer_packet.created_at, implementer_packet.created_at).
- Fallback when cutoffs do not partition cleanly: order by mtime
  ascending, the newest entries correspond to the latest spawned
  phase. Matches the carrying-forward fallback proven during Phase 2
  Stage 6 (commits 4317ec9 + ed090ef).

This module has no Pydantic imports and no <prior-iteration> imports. It is a
pure-stdlib helper.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path


def count_mcp_in_jsonls(jsonls: list[Path]) -> int:
    """Count tool_use.name ~ ^mcp__ across an explicit list of jsonl files.

    Tolerates malformed lines (skipped silently) and missing files.
    """
    count = 0
    for jsonl in jsonls:
        try:
            text = jsonl.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = ev.get("message") or {}
            content = msg.get("content") or []
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use":
                    name = c.get("name") or ""
                    if name.startswith("mcp__"):
                        count += 1
    return count


def parse_iso(stamp: str) -> float | None:
    """Parse an ISO-8601 timestamp into a POSIX float; tolerates trailing Z."""
    if not stamp:
        return None
    s = stamp.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return _dt.datetime.fromisoformat(s).timestamp()
    except (ValueError, TypeError):
        return None


def partition_jsonls_2way(
    session_dir: Path, cutoff_ts: float | None
) -> tuple[list[Path], list[Path]]:
    """Split *.jsonl files into (analyst_files, writer_files).

    Primary: by mtime vs cutoff_ts (sdd_writer_packet.created_at).
    Fallback (always used if cutoff partition yields empty side):
    newest jsonl by mtime is the writer, every other is analyst.
    """
    if not session_dir.exists() or not session_dir.is_dir():
        return [], []
    jsonls = sorted(session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not jsonls:
        return [], []
    if cutoff_ts is not None:
        analyst = [p for p in jsonls if p.stat().st_mtime < cutoff_ts]
        writer = [p for p in jsonls if p.stat().st_mtime >= cutoff_ts]
        if analyst and writer:
            return analyst, writer
    if len(jsonls) == 1:
        return [], jsonls
    return jsonls[:-1], [jsonls[-1]]


def partition_jsonls_3way(
    session_dir: Path,
    writer_cutoff_ts: float | None,
    impl_cutoff_ts: float | None,
) -> tuple[list[Path], list[Path], list[Path]]:
    """Split *.jsonl files into (analyst, writer, implementer).

    Primary: by mtime with two cutoffs:
      analyst       < writer_cutoff_ts
      writer        in [writer_cutoff_ts, impl_cutoff_ts)
      implementer   >= impl_cutoff_ts

    Fallback: when cutoff partition yields any empty group, order by
    mtime ascending and treat newest = implementer, second-newest =
    writer, everything older = analyst. With fewer than 3 jsonls,
    surface empty analyst (and possibly empty writer) groups so
    upstream gates fire the appropriate "session not found" exit.
    """
    if not session_dir.exists() or not session_dir.is_dir():
        return [], [], []
    jsonls = sorted(session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not jsonls:
        return [], [], []

    if writer_cutoff_ts is not None and impl_cutoff_ts is not None:
        analyst = [p for p in jsonls if p.stat().st_mtime < writer_cutoff_ts]
        writer = [
            p
            for p in jsonls
            if writer_cutoff_ts <= p.stat().st_mtime < impl_cutoff_ts
        ]
        impl = [p for p in jsonls if p.stat().st_mtime >= impl_cutoff_ts]
        if analyst and writer and impl:
            return analyst, writer, impl

    if len(jsonls) >= 3:
        return jsonls[:-2], [jsonls[-2]], [jsonls[-1]]
    if len(jsonls) == 2:
        return [], [jsonls[0]], [jsonls[1]]
    return [], [], jsonls


__all__ = [
    "count_mcp_in_jsonls",
    "parse_iso",
    "partition_jsonls_2way",
    "partition_jsonls_3way",
]
