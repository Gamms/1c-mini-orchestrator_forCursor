"""Validate analyst output for a given task_root.

Usage:
    python scripts/_python/validate.py <task_root>

Exit codes (per SDD Phase 1 §5.1):
    0  OK; summary printed to stdout
    1  Pydantic schema validation failed
    2  Tool-exhaustion: keys in tool_evidence do not cover .mcp.json servers
    3  raw_result_ref points to a file that does not exist on disk
    4  analysis_report.json absent at task_root
    5  analysis_report.json present but JSON is not parseable
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402

from schemas.analysis_v2 import AnalysisReport  # noqa: E402


def _load_mcp_servers(task_root: Path) -> list[str]:
    mcp_path = task_root / ".mcp.json"
    if not mcp_path.exists():
        return []
    try:
        text = mcp_path.read_text(encoding="utf-8-sig")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return []
    return sorted((data.get("mcpServers") or {}).keys())


def _summary(report: AnalysisReport, mcp_servers: list[str]) -> str:
    by_severity: dict[str, int] = {"info": 0, "decision": 0, "blocker": 0}
    for q in report.open_questions:
        by_severity[q.severity] = by_severity.get(q.severity, 0) + 1
    lines = [
        f"OK task_id={report.task_id}",
        f"  relevant_files={len(report.relevant_files)}",
        f"  existing_patterns={len(report.existing_patterns)}",
        f"  pitfalls_found={len(report.pitfalls_found)}",
        f"  constraints_discovered={len(report.constraints_discovered)}",
        (
            f"  open_questions={len(report.open_questions)} "
            f"(info={by_severity['info']}, "
            f"decision={by_severity['decision']}, "
            f"blocker={by_severity['blocker']})"
        ),
    ]
    for srv, ev in report.tool_evidence.items():
        rounds = sorted({q.round for q in ev.queries})
        lines.append(
            f"  evidence[{srv}]: queries={len(ev.queries)}, rounds={rounds}"
        )
    lines.append(f"  mcp_servers_configured={mcp_servers}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate.py <task_root>", file=sys.stderr)
        return 4
    task_root = Path(argv[1]).resolve()
    report_path = task_root / "analysis_report.json"

    if not report_path.exists():
        print(
            f"analyst did not produce analysis_report.json at {report_path} "
            f"-- check session log or restart",
            file=sys.stderr,
        )
        return 4

    try:
        raw = report_path.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(
            f"JSONDecodeError at line {exc.lineno} col {exc.colno}: {exc.msg}",
            file=sys.stderr,
        )
        return 5

    try:
        report = AnalysisReport.model_validate(data)
    except ValidationError as exc:
        print("Pydantic ValidationError:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    mcp_servers = _load_mcp_servers(task_root)
    declared = sorted(report.tool_evidence.keys())
    missing = sorted(set(mcp_servers) - set(declared))
    if missing:
        print(
            f"tool-exhaustion: missing servers: {missing}; "
            f"required (from .mcp.json): {mcp_servers}; "
            f"declared in tool_evidence: {declared}",
            file=sys.stderr,
        )
        return 2

    bad_refs: list[str] = []
    for srv, ev in report.tool_evidence.items():
        for q in ev.queries:
            ref_path = task_root / q.raw_result_ref
            if not ref_path.exists():
                bad_refs.append(f"{srv}/r{q.round}: {q.raw_result_ref}")
    if bad_refs:
        print(
            "raw_result_ref points to missing file(s):",
            file=sys.stderr,
        )
        for bad in bad_refs:
            print(f"  {bad}", file=sys.stderr)
        return 3

    print(_summary(report, mcp_servers))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
