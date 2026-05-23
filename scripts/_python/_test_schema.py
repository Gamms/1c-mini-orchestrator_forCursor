"""Fixture-tests for schemas/analysis_v2.AnalysisReport (Stage 2 SDD §5.2).

Runs from Orchestrator root: `python scripts/_python/_test_schema.py`.
Prints PASS / FAIL per case + exits non-zero if any case fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from schemas.analysis_v2 import AnalysisReport


def _valid_report_dict() -> dict:
    return {
        "schema_version": "v2",
        "task_id": "2026-05-22-example-erp-01",
        "goal_understanding": "Add INN attribute to Counterparties.",
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
                        "summary": "Found catalog with 12 attributes.",
                    },
                    {
                        "round": 2,
                        "tool": "get_metadata",
                        "query": "Counterparties attributes detail",
                        "raw_result_ref": (
                            "analysis_raw/1c-codemetadata/"
                            "r2-q0-bbbbbbbbbbbb.json"
                        ),
                        "summary": "INN not present; TaxID is closest.",
                    },
                ],
            }
        },
        "relevant_files": [
            {
                "path": "src/Catalogs/Counterparties/Ext/Module.bsl",
                "line_range": "L:10-50",
                "why_relevant": "Object module for Counterparties.",
                "citations": [
                    {"source": "code", "ref": "src/Catalogs/Counterparties/Ext/Module.bsl:L10"}
                ],
            }
        ],
        "self_review_notes": "Two rounds sufficient; no contradiction found.",
    }


def case_a_valid() -> bool:
    AnalysisReport.model_validate(_valid_report_dict())
    return True


def case_b_extra_field() -> bool:
    data = _valid_report_dict()
    data["extra_field"] = "garbage"
    try:
        AnalysisReport.model_validate(data)
    except ValidationError as e:
        return "extra" in str(e).lower() or "forbid" in str(e).lower() or "extra_field" in str(e)
    return False


def case_c_single_round() -> bool:
    data = _valid_report_dict()
    data["tool_evidence"]["1c-codemetadata"]["queries"] = [
        data["tool_evidence"]["1c-codemetadata"]["queries"][0]
    ]
    try:
        AnalysisReport.model_validate(data)
    except ValidationError as e:
        return "2-4 distinct rounds" in str(e)
    return False


def case_d_absolute_path() -> bool:
    data = _valid_report_dict()
    data["relevant_files"][0]["path"] = "/absolute/path/Module.bsl"
    try:
        AnalysisReport.model_validate(data)
    except ValidationError as e:
        return "repo-relative" in str(e)
    return False


CASES = [
    ("(a) valid report parses OK", case_a_valid),
    ("(b) extra_field rejected (extra=forbid)", case_b_extra_field),
    ("(c) single round rejected (2-4 enforced)", case_c_single_round),
    ("(d) absolute path rejected", case_d_absolute_path),
]


def main() -> int:
    failures = 0
    for name, fn in CASES:
        try:
            ok = fn()
            status = "PASS" if ok else "FAIL"
        except Exception as exc:  # noqa: BLE001
            ok = False
            status = f"ERROR ({type(exc).__name__}: {exc})"
        if not ok:
            failures += 1
        print(f"[{status}] {name}")
    if failures:
        print(f"\n{failures} of {len(CASES)} cases failed.")
        return 1
    print(f"\nAll {len(CASES)} cases passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
