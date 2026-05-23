"""Validate sdd_writer output for a given task_root.

Usage:
    python scripts/_python/validate_sdd.py <task_root>

Exit codes (per Phase 2 SDD section 5.1):
    0  OK; summary printed to stdout
    1  sdd_metadata.json Pydantic schema validation failed
    2  sdd.md missing OR fewer than 10 top-level numbered headings (1..10)
    3  sdd_metadata.task_id != analysis_report.task_id
    4  sdd_metadata.json absent at task_root
    5  sdd_metadata.json present but JSON is not parseable
    6  analyst session.jsonl shows 0 tool_use entries matching ^mcp__
    7  writer session.jsonl shows 0 tool_use entries matching ^mcp__
    8  one or more ff_self_audit.<FFi>.status == "fail"
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydantic import ValidationError  # noqa: E402

from schemas.sdd_v1 import SDDMetadata  # noqa: E402
from _session_jsonl import (  # noqa: E402
    count_mcp_in_jsonls,
    parse_iso,
    partition_jsonls_2way,
)


EXIT_OK = 0
EXIT_PYDANTIC = 1
EXIT_SDD_MD_SHAPE = 2
EXIT_TASK_ID_MISMATCH = 3
EXIT_NO_METADATA = 4
EXIT_METADATA_PARSE = 5
EXIT_ANALYST_NO_MCP = 6
EXIT_WRITER_NO_MCP = 7
EXIT_FF_FAIL = 8


_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+", re.M)


def _summary(
    meta: SDDMetadata, analyst_mcp: int, writer_mcp: int
) -> str:
    by_sev = {"info": 0, "decision": 0, "blocker": 0}
    for q in meta.open_questions:
        by_sev[q.severity] = by_sev.get(q.severity, 0) + 1
    audit_summary = {
        k: meta.ff_self_audit[k].status for k in sorted(meta.ff_self_audit)
    }
    lines = [
        f"OK task_id={meta.task_id}",
        f"  task_size={meta.task_size}",
        f"  stages={len(meta.stages)}",
        f"  open_questions={len(meta.open_questions)} "
        f"(info={by_sev['info']}, decision={by_sev['decision']}, "
        f"blocker={by_sev['blocker']})",
        f"  risks={len(meta.risks)}",
        f"  refusals={len(meta.refusals)}",
        f"  citations_used={len(meta.citations_used)}",
        f"  ff_self_audit={audit_summary}",
        f"  analyst_session_mcp_tool_use={analyst_mcp}",
        f"  writer_session_mcp_tool_use={writer_mcp}",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_sdd.py <task_root>", file=sys.stderr)
        return EXIT_NO_METADATA

    task_root = Path(argv[1]).resolve()
    md_path = task_root / "sdd.md"
    meta_path = task_root / "sdd_metadata.json"
    packet_path = task_root / "sdd_writer_packet.json"
    analysis_path = task_root / "analysis_report.json"

    # exit 4: no sdd_metadata.json
    if not meta_path.exists():
        print(
            f"sdd_writer did not produce sdd_metadata.json at {meta_path}",
            file=sys.stderr,
        )
        return EXIT_NO_METADATA

    # exit 5: metadata not parseable
    try:
        raw = meta_path.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(
            f"sdd_metadata.json JSONDecodeError at line {exc.lineno} col {exc.colno}: {exc.msg}",
            file=sys.stderr,
        )
        return EXIT_METADATA_PARSE

    # exit 1: pydantic
    try:
        meta = SDDMetadata.model_validate(data)
    except ValidationError as exc:
        print("sdd_metadata Pydantic ValidationError:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return EXIT_PYDANTIC

    # exit 2: sdd.md missing or heading shape broken
    if not md_path.exists():
        print(f"sdd.md missing at {md_path}", file=sys.stderr)
        return EXIT_SDD_MD_SHAPE
    md_text = md_path.read_text(encoding="utf-8-sig")
    found = {int(m.group(1)) for m in _HEADING_RE.finditer(md_text)}
    required = set(range(1, 11))
    missing = sorted(required - found)
    if missing:
        print(
            f"sdd.md missing top-level numbered headings (## N.): {missing}; "
            f"found: {sorted(found)}",
            file=sys.stderr,
        )
        return EXIT_SDD_MD_SHAPE

    # exit 3: task_id mismatch
    if analysis_path.exists():
        try:
            ar_data = json.loads(analysis_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            ar_data = {}
        analyst_task_id = ar_data.get("task_id", "")
        if analyst_task_id and meta.task_id != analyst_task_id:
            print(
                f"task_id mismatch: sdd_metadata.task_id={meta.task_id!r} != "
                f"analysis_report.task_id={analyst_task_id!r}",
                file=sys.stderr,
            )
            return EXIT_TASK_ID_MISMATCH

    # exit 8: FF self-audit fails
    failed_ffs = sorted(
        k for k, v in meta.ff_self_audit.items() if v.status == "fail"
    )
    if failed_ffs:
        notes = {k: meta.ff_self_audit[k].note for k in failed_ffs}
        print(
            f"ff_self_audit entries failed: {failed_ffs}; notes: {notes}",
            file=sys.stderr,
        )
        return EXIT_FF_FAIL

    # exit 6/7: partition session.jsonls into analyst vs writer
    analyst_session_dir = ""
    cutoff_ts: float | None = None
    if packet_path.exists():
        try:
            packet = json.loads(packet_path.read_text(encoding="utf-8-sig"))
            analyst_session_dir = packet.get("analyst_session_dir", "") or ""
            cutoff_ts = parse_iso(packet.get("created_at", "") or "")
        except json.JSONDecodeError:
            analyst_session_dir = ""

    if not analyst_session_dir or not Path(analyst_session_dir).exists():
        print(
            "analyst session.jsonl dir not found (sdd_writer_packet.json missing or "
            "session cleared) -- cannot verify real-MCP gate; re-run analyst before SDD",
            file=sys.stderr,
        )
        return EXIT_ANALYST_NO_MCP

    analyst_files, writer_files = partition_jsonls_2way(Path(analyst_session_dir), cutoff_ts)

    if not analyst_files:
        print(
            f"no analyst session.jsonl found in {analyst_session_dir} "
            f"(cutoff_ts={cutoff_ts}); cannot verify real-MCP gate",
            file=sys.stderr,
        )
        return EXIT_ANALYST_NO_MCP

    analyst_mcp = count_mcp_in_jsonls(analyst_files)
    if analyst_mcp == 0:
        print(
            f"input analysis was synthesized without real MCP "
            f"(0 mcp__ tool_use entries in {[str(p) for p in analyst_files]}) -- "
            f"re-run analyst before SDD",
            file=sys.stderr,
        )
        return EXIT_ANALYST_NO_MCP

    if not writer_files:
        print(
            f"no sdd_writer session.jsonl found in {analyst_session_dir} "
            f"(cutoff_ts={cutoff_ts}); writer never ran or session was cleared",
            file=sys.stderr,
        )
        return EXIT_WRITER_NO_MCP

    writer_mcp = count_mcp_in_jsonls(writer_files)
    if writer_mcp == 0:
        print(
            f"sdd_writer did not consult MCP "
            f"(0 mcp__ tool_use entries in {[str(p) for p in writer_files]}); refused.",
            file=sys.stderr,
        )
        return EXIT_WRITER_NO_MCP

    print(_summary(meta, analyst_mcp, writer_mcp))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
