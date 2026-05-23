"""Fixture-tests for schemas/sdd_v1.SDDMetadata (Phase 2 Stage 1 SDD §5.1).

Runs from Orchestrator root: `python scripts/_python/_test_sdd_schema.py`.
Prints PASS / FAIL per case + exits non-zero if any case fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from schemas.sdd_v1 import SDDMetadata


def _valid_sdd_dict() -> dict:
    return {
        "schema_version": "v1",
        "task_id": "2026-05-22-example-erp-01",
        "analysis_report_ref": "analysis_report.json",
        "sdd_path": "sdd.md",
        "task_size": "M",
        "stages": [
            {
                "id": "Stage 0",
                "title": "Smoke",
                "deliverables": [
                    {"path": "scripts/_smoke_stub.ps1", "description": "smoke check only"}
                ],
                "verifications": ["wrapper stub exits 0"],
                "failure_modes": ["wt.exe absent on PATH"],
            }
        ],
        "open_questions": [],
        "risks": [
            {
                "summary": "writer trusts analyst blindly",
                "mitigation": "validate_sdd exit 7 enforces real MCP queries",
            }
        ],
        "refusals": ["external audit pass -- operator-triggered"],
        "dod_pre": ["all OQs closed", "Stage 0 smoke passes"],
        "dod_post": ["all stages green", "merged to main"],
        "ff_self_audit": {
            "FF1": {"status": "pass", "note": "all external claims tagged"},
            "FF2": {"status": "na", "note": "no inlining required this round"},
            "FF3": {"status": "pass", "note": "failure-modes per stage"},
            "FF4": {"status": "pass", "note": "session.jsonl checked, not narrative"},
            "FF5": {"status": "pass", "note": "blast radius documented in 7"},
            "FF6": {"status": "pass", "note": "honor-system items tagged"},
            "FF7": {"status": "pass", "note": "pre + post conditions split"},
            "FF8": {"status": "na", "note": "no grep regex in dod_post for this fixture"},
        },
        "citations_used": [
            {
                "source": "analysis_report",
                "ref": "analysis_report.json#tool_evidence.1c-codemetadata",
            },
            {"source": "code", "ref": "scripts/spawn-analyst.ps1:165-178"},
        ],
        "self_review_notes": "All 7 FFs pass; no blocker OQs; stage 0 ready.",
    }


def case_a_valid() -> bool:
    SDDMetadata.model_validate(_valid_sdd_dict())
    return True


def case_b_missing_ff() -> bool:
    data = _valid_sdd_dict()
    del data["ff_self_audit"]["FF4"]
    try:
        SDDMetadata.model_validate(data)
    except ValidationError as e:
        return "FF4" in str(e) and "missing" in str(e).lower()
    return False


def case_c_bad_task_size() -> bool:
    data = _valid_sdd_dict()
    data["task_size"] = "huge"
    try:
        SDDMetadata.model_validate(data)
    except ValidationError as e:
        return "task_size" in str(e)
    return False


def case_d_empty_dod_pre() -> bool:
    data = _valid_sdd_dict()
    data["dod_pre"] = []
    try:
        SDDMetadata.model_validate(data)
    except ValidationError as e:
        return "dod_pre" in str(e)
    return False


def case_e_bad_analysis_report_ref() -> bool:
    data = _valid_sdd_dict()
    data["citations_used"].append(
        {"source": "analysis_report", "ref": "something_else.json#x"}
    )
    try:
        SDDMetadata.model_validate(data)
    except ValidationError as e:
        return "analysis_report.json#" in str(e)
    return False


def case_f_extra_field() -> bool:
    data = _valid_sdd_dict()
    data["extra_field"] = "garbage"
    try:
        SDDMetadata.model_validate(data)
    except ValidationError as e:
        msg = str(e).lower()
        return "extra" in msg or "forbid" in msg
    return False


def case_g_unknown_ff_key() -> bool:
    data = _valid_sdd_dict()
    data["ff_self_audit"]["FF99"] = {"status": "pass", "note": "rogue"}
    try:
        SDDMetadata.model_validate(data)
    except ValidationError as e:
        return "FF99" in str(e) and "unknown" in str(e).lower()
    return False


def case_h_empty_stage_failure_modes() -> bool:
    data = _valid_sdd_dict()
    data["stages"][0]["failure_modes"] = []
    try:
        SDDMetadata.model_validate(data)
    except ValidationError as e:
        return "failure_modes" in str(e)
    return False


def case_i_deliverable_empty_path() -> bool:
    data = _valid_sdd_dict()
    data["stages"][0]["deliverables"] = [{"path": "   ", "description": "blank"}]
    try:
        SDDMetadata.model_validate(data)
    except ValidationError as e:
        return "path" in str(e).lower()
    return False


def case_j_deliverable_as_bare_string_rejected() -> bool:
    data = _valid_sdd_dict()
    data["stages"][0]["deliverables"] = ["scripts/_smoke_stub.ps1"]
    try:
        SDDMetadata.model_validate(data)
    except ValidationError as e:
        return "deliverables" in str(e).lower() or "dict" in str(e).lower()
    return False


def case_k_deliverable_description_optional() -> bool:
    data = _valid_sdd_dict()
    data["stages"][0]["deliverables"] = [{"path": "scripts/_smoke_stub.ps1"}]
    meta = SDDMetadata.model_validate(data)
    return meta.stages[0].deliverables[0].description is None


CASES = [
    ("(a) valid sdd_metadata parses OK", case_a_valid),
    ("(b) missing FF4 in ff_self_audit rejected", case_b_missing_ff),
    ("(c) task_size='huge' rejected", case_c_bad_task_size),
    ("(d) empty dod_pre rejected", case_d_empty_dod_pre),
    ("(e) analysis_report Citation with wrong ref rejected", case_e_bad_analysis_report_ref),
    ("(f) extra field rejected (extra=forbid)", case_f_extra_field),
    ("(g) unknown FF key in ff_self_audit rejected", case_g_unknown_ff_key),
    ("(h) empty stage.failure_modes rejected", case_h_empty_stage_failure_modes),
    ("(i) Deliverable with blank path rejected", case_i_deliverable_empty_path),
    ("(j) bare string in deliverables rejected (must be Deliverable dict)", case_j_deliverable_as_bare_string_rejected),
    ("(k) Deliverable.description is optional, defaults None", case_k_deliverable_description_optional),
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
