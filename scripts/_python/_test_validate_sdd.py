"""Stage 5 verification: 9 fixture cases for validate_sdd.py exit codes 0..8.

Runs from Orchestrator root: `python scripts/_python/_test_validate_sdd.py`.
Builds throwaway task_root + fake home dirs under a tempdir, runs validate_sdd.py
against each with USERPROFILE/HOME pointed at the fake home, asserts the
expected exit code.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATE_PY = ROOT / "scripts/_python/validate_sdd.py"

TASK_ID = "2026-05-22-test-01"


def _valid_sdd_meta() -> dict:
    return {
        "schema_version": "v1",
        "task_id": TASK_ID,
        "analysis_report_ref": "analysis_report.json",
        "sdd_path": "sdd.md",
        "task_size": "M",
        "stages": [
            {
                "id": "Stage 0",
                "title": "Smoke",
                "deliverables": [{"path": "scripts/_smoke_stub.ps1"}],
                "verifications": ["wrapper stub exits 0"],
                "failure_modes": ["wt.exe absent"],
            }
        ],
        "open_questions": [],
        "risks": [],
        "refusals": [],
        "dod_pre": ["all OQs closed"],
        "dod_post": ["stages green"],
        "ff_self_audit": {
            "FF1": {"status": "pass", "note": "claims tagged"},
            "FF2": {"status": "na", "note": "no inlining"},
            "FF3": {"status": "pass", "note": "failure-modes per stage"},
            "FF4": {"status": "pass", "note": "real MCP"},
            "FF5": {"status": "pass", "note": "blast radius documented"},
            "FF6": {"status": "pass", "note": "honor-system items tagged"},
            "FF7": {"status": "pass", "note": "pre + post conditions split"},
            "FF8": {"status": "na", "note": "no grep regex in dod_post"},
        },
        "citations_used": [
            {
                "source": "analysis_report",
                "ref": "analysis_report.json#tool_evidence.1c-codemetadata",
            },
        ],
        "self_review_notes": "Fixture metadata.",
    }


_VALID_SDD_MD = (
    "# SDD test\n\n"
    "## 1. Context\n\nx\n\n"
    "## 2. Constraints\n\nx\n\n"
    "## 3. Layout\n\nx\n\n"
    "## 4. Flow\n\nx\n\n"
    "## 5. Stages\n\nx\n\n"
    "## 6. Open Questions\n\nx\n\n"
    "## 7. Risks\n\nx\n\n"
    "## 8. DoD\n\nx\n\n"
    "## 9. Refusals\n\nx\n\n"
    "## 10. Resolutions\n\nx\n"
)


def _valid_analysis_report() -> dict:
    return {
        "schema_version": "v2",
        "task_id": TASK_ID,
        "goal_understanding": "test goal",
        "tool_evidence": {},
        "relevant_files": [],
        "self_review_notes": "test",
    }


def _jsonl_event_with_mcp(name: str) -> str:
    return json.dumps(
        {"message": {"content": [{"type": "tool_use", "name": name, "input": {}}]}}
    )


def _jsonl_event_no_mcp() -> str:
    return json.dumps(
        {"message": {"content": [{"type": "tool_use", "name": "Bash", "input": {}}]}}
    )


def _write_session(session_path: Path, mcp_count: int) -> None:
    if mcp_count > 0:
        lines = [_jsonl_event_with_mcp(f"mcp__server__tool_{i}") for i in range(mcp_count)]
    else:
        lines = [_jsonl_event_no_mcp()]
    session_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _setup(
    tmp: Path,
    *,
    sdd_meta,
    sdd_md,
    analysis_report,
    analyst_mcp_count: int,
    writer_mcp_count: int,
    write_packet: bool = True,
):
    """Build a fixture. Returns (task_root, fake_home).

    Mirrors real Claude Code 2.1.119 layout: analyst + writer share ONE
    cwd-encoded session dir; partitioning is by mtime vs packet.created_at.
    """
    fake_home = tmp / "home"
    projects_root = fake_home / ".claude" / "projects"
    projects_root.mkdir(parents=True)

    session_dir = projects_root / f"C--shared-Orchestrator-tasks-{TASK_ID}"
    session_dir.mkdir()

    analyst_jsonl = session_dir / "analyst-uuid.jsonl"
    writer_jsonl = session_dir / "writer-uuid.jsonl"
    _write_session(analyst_jsonl, analyst_mcp_count)
    _write_session(writer_jsonl, writer_mcp_count)

    now = time.time()
    analyst_mtime = now - 1000
    cutoff_iso = _dt.datetime.fromtimestamp(now - 500, tz=_dt.timezone.utc).isoformat()
    writer_mtime = now
    os.utime(analyst_jsonl, (analyst_mtime, analyst_mtime))
    os.utime(writer_jsonl, (writer_mtime, writer_mtime))

    task_root = tmp / "task"
    task_root.mkdir()

    if sdd_meta is not None:
        sdd_path = task_root / "sdd_metadata.json"
        if isinstance(sdd_meta, str):
            sdd_path.write_text(sdd_meta, encoding="utf-8")
        else:
            sdd_path.write_text(json.dumps(sdd_meta), encoding="utf-8")

    if sdd_md is not None:
        (task_root / "sdd.md").write_text(sdd_md, encoding="utf-8")

    if analysis_report is not None:
        (task_root / "analysis_report.json").write_text(
            json.dumps(analysis_report), encoding="utf-8"
        )

    if write_packet:
        packet = {
            "task_id": TASK_ID,
            "analyst_session_dir": str(session_dir),
            "created_at": cutoff_iso,
        }
        (task_root / "sdd_writer_packet.json").write_text(
            json.dumps(packet), encoding="utf-8"
        )

    return task_root, fake_home


def _run(task_root: Path, fake_home: Path) -> int:
    env = dict(os.environ)
    env["USERPROFILE"] = str(fake_home)
    env["HOME"] = str(fake_home)
    r = subprocess.run(
        [sys.executable, str(VALIDATE_PY), str(task_root)],
        capture_output=True,
        text=True,
        env=env,
    )
    return r.returncode


def case_a(tmp: Path):
    return _setup(
        tmp,
        sdd_meta=_valid_sdd_meta(),
        sdd_md=_VALID_SDD_MD,
        analysis_report=_valid_analysis_report(),
        analyst_mcp_count=2,
        writer_mcp_count=2,
    )


def case_b_drop_ff1(tmp: Path):
    meta = _valid_sdd_meta()
    del meta["ff_self_audit"]["FF1"]
    return _setup(
        tmp,
        sdd_meta=meta,
        sdd_md=_VALID_SDD_MD,
        analysis_report=_valid_analysis_report(),
        analyst_mcp_count=2,
        writer_mcp_count=2,
    )


def case_c_sdd_md_missing_h5(tmp: Path):
    bad_md = _VALID_SDD_MD.replace("## 5. Stages\n\nx\n\n", "")
    return _setup(
        tmp,
        sdd_meta=_valid_sdd_meta(),
        sdd_md=bad_md,
        analysis_report=_valid_analysis_report(),
        analyst_mcp_count=2,
        writer_mcp_count=2,
    )


def case_d_task_id_mismatch(tmp: Path):
    ar = _valid_analysis_report()
    ar["task_id"] = "different-task-id"
    return _setup(
        tmp,
        sdd_meta=_valid_sdd_meta(),
        sdd_md=_VALID_SDD_MD,
        analysis_report=ar,
        analyst_mcp_count=2,
        writer_mcp_count=2,
    )


def case_e_no_metadata(tmp: Path):
    return _setup(
        tmp,
        sdd_meta=None,
        sdd_md=_VALID_SDD_MD,
        analysis_report=_valid_analysis_report(),
        analyst_mcp_count=2,
        writer_mcp_count=2,
    )


def case_f_unparseable(tmp: Path):
    return _setup(
        tmp,
        sdd_meta="not json{",
        sdd_md=_VALID_SDD_MD,
        analysis_report=_valid_analysis_report(),
        analyst_mcp_count=2,
        writer_mcp_count=2,
    )


def case_g_analyst_zero_mcp(tmp: Path):
    return _setup(
        tmp,
        sdd_meta=_valid_sdd_meta(),
        sdd_md=_VALID_SDD_MD,
        analysis_report=_valid_analysis_report(),
        analyst_mcp_count=0,
        writer_mcp_count=2,
    )


def case_h_writer_zero_mcp(tmp: Path):
    return _setup(
        tmp,
        sdd_meta=_valid_sdd_meta(),
        sdd_md=_VALID_SDD_MD,
        analysis_report=_valid_analysis_report(),
        analyst_mcp_count=2,
        writer_mcp_count=0,
    )


def case_i_ff_fail(tmp: Path):
    meta = _valid_sdd_meta()
    meta["ff_self_audit"]["FF4"] = {
        "status": "fail",
        "note": "writer issued 0 MCP queries",
    }
    return _setup(
        tmp,
        sdd_meta=meta,
        sdd_md=_VALID_SDD_MD,
        analysis_report=_valid_analysis_report(),
        analyst_mcp_count=2,
        writer_mcp_count=2,
    )


CASES = [
    ("(a) full valid task -> 0", 0, case_a),
    ("(b) drop ff_self_audit[FF1] -> 1 (pydantic)", 1, case_b_drop_ff1),
    ("(c) sdd.md missing heading 5 -> 2", 2, case_c_sdd_md_missing_h5),
    ("(d) sdd_metadata.task_id != analysis_report.task_id -> 3", 3, case_d_task_id_mismatch),
    ("(e) sdd_metadata.json absent -> 4", 4, case_e_no_metadata),
    ("(f) sdd_metadata.json = 'not json{' -> 5", 5, case_f_unparseable),
    ("(g) analyst session 0 mcp__ -> 6", 6, case_g_analyst_zero_mcp),
    ("(h) writer session 0 mcp__ -> 7", 7, case_h_writer_zero_mcp),
    ("(i) ff_self_audit[FF4].status=fail -> 8", 8, case_i_ff_fail),
]


def _case(name: str, expected: int, setup_fn) -> bool:
    with tempfile.TemporaryDirectory() as tmpdir:
        task_root, fake_home = setup_fn(Path(tmpdir))
        actual = _run(task_root, fake_home)
    ok = actual == expected
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name} expected={expected} actual={actual}")
    return ok


def main() -> int:
    failures = 0
    for name, expected, fn in CASES:
        if not _case(name, expected, fn):
            failures += 1
    if failures:
        print(f"\n{failures} of {len(CASES)} cases failed.")
        return 1
    print(f"\nAll {len(CASES)} cases passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
