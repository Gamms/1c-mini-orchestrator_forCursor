"""Stage 5 verification: 6 fixture cases for validate.py.

Runs from Orchestrator root: `python scripts/_python/_test_validate.py`.
Builds throwaway task_root dirs under a tempdir, runs validate.py
against each, asserts the expected exit code.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATE_PY = ROOT / "scripts/_python/validate.py"


def _valid_report() -> dict:
    return {
        "schema_version": "v2",
        "task_id": "TEST-2026-05-22-X",
        "goal_understanding": "Sample goal.",
        "tool_evidence": {
            "1c-codemetadata": {
                "server": "1c-codemetadata",
                "queries": [
                    {
                        "round": 1,
                        "tool": "list_objects",
                        "query": "Catalog Counterparties",
                        "raw_result_ref": (
                            "analysis_raw/1c-codemetadata/"
                            "r1-q0-aaaaaaaaaaaa.json"
                        ),
                        "summary": "Broad scan.",
                    },
                    {
                        "round": 2,
                        "tool": "get_metadata",
                        "query": "Counterparties attributes",
                        "raw_result_ref": (
                            "analysis_raw/1c-codemetadata/"
                            "r2-q0-bbbbbbbbbbbb.json"
                        ),
                        "summary": "Detail drill.",
                    },
                ],
            }
        },
        "relevant_files": [
            {
                "path": "src/Catalogs/Counterparties/Ext/Module.bsl",
                "line_range": "L:10-50",
                "why_relevant": "Object module.",
                "citations": [{"source": "code", "ref": "src/x.bsl:L1"}],
            }
        ],
        "self_review_notes": "Sufficient.",
    }


def _mcp_config(servers: list[str]) -> dict:
    return {"mcpServers": {s: {"type": "http", "url": f"http://x/{s}"} for s in servers}}


def _setup(tmp: Path, *, report: dict | None, raw_files: list[str], mcp_servers: list[str]) -> Path:
    task_root = tmp / "task"
    task_root.mkdir()
    (task_root / "analysis_raw" / "1c-codemetadata").mkdir(parents=True, exist_ok=True)
    for ref in raw_files:
        ref_path = task_root / ref
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        ref_path.write_text("{}", encoding="utf-8")
    if report is not None:
        if isinstance(report, str):
            (task_root / "analysis_report.json").write_text(report, encoding="utf-8")
        else:
            (task_root / "analysis_report.json").write_text(
                json.dumps(report), encoding="utf-8"
            )
    (task_root / ".mcp.json").write_text(
        json.dumps(_mcp_config(mcp_servers)), encoding="utf-8"
    )
    return task_root


def _run(task_root: Path) -> int:
    r = subprocess.run(
        [sys.executable, str(VALIDATE_PY), str(task_root)],
        capture_output=True,
        text=True,
    )
    return r.returncode


def _case(name: str, expected: int, setup_fn) -> bool:
    with tempfile.TemporaryDirectory() as tmpdir:
        task_root = setup_fn(Path(tmpdir))
        actual = _run(task_root)
    ok = actual == expected
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name} expected={expected} actual={actual}")
    return ok


def case_a(tmp: Path) -> Path:
    return _setup(
        tmp,
        report=_valid_report(),
        raw_files=[
            "analysis_raw/1c-codemetadata/r1-q0-aaaaaaaaaaaa.json",
            "analysis_raw/1c-codemetadata/r2-q0-bbbbbbbbbbbb.json",
        ],
        mcp_servers=["1c-codemetadata"],
    )


def case_b_missing_task_id(tmp: Path) -> Path:
    r = _valid_report()
    del r["task_id"]
    return _setup(
        tmp,
        report=r,
        raw_files=[
            "analysis_raw/1c-codemetadata/r1-q0-aaaaaaaaaaaa.json",
            "analysis_raw/1c-codemetadata/r2-q0-bbbbbbbbbbbb.json",
        ],
        mcp_servers=["1c-codemetadata"],
    )


def case_c_empty_evidence(tmp: Path) -> Path:
    r = _valid_report()
    r["tool_evidence"] = {}
    return _setup(
        tmp,
        report=r,
        raw_files=[],
        mcp_servers=["1c-codemetadata"],
    )


def case_d_missing_raw_file(tmp: Path) -> Path:
    return _setup(
        tmp,
        report=_valid_report(),
        raw_files=["analysis_raw/1c-codemetadata/r1-q0-aaaaaaaaaaaa.json"],
        mcp_servers=["1c-codemetadata"],
    )


def case_e_no_report(tmp: Path) -> Path:
    return _setup(
        tmp,
        report=None,
        raw_files=[],
        mcp_servers=["1c-codemetadata"],
    )


def case_f_broken_json(tmp: Path) -> Path:
    return _setup(
        tmp,
        report="not json{",
        raw_files=[
            "analysis_raw/1c-codemetadata/r1-q0-aaaaaaaaaaaa.json",
        ],
        mcp_servers=["1c-codemetadata"],
    )


CASES = [
    ("(a) valid report + all raw files present -> 0", 0, case_a),
    ("(b) task_id missing -> 1 (schema)", 1, case_b_missing_task_id),
    ("(c) empty tool_evidence -> 2 (tool-exhaustion)", 2, case_c_empty_evidence),
    ("(d) raw_result_ref points to missing file -> 3", 3, case_d_missing_raw_file),
    ("(e) no analysis_report.json -> 4", 4, case_e_no_report),
    ("(f) analysis_report.json = invalid JSON -> 5", 5, case_f_broken_json),
]


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
