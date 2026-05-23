"""Fixture-tests for schemas/audit_v1.AuditReport (Phase 4 Stage 1 SDD section 5.1).

Runs from Orchestrator root: `python scripts/_python/_test_audit_schema.py`.
Prints PASS / FAIL per case + exits non-zero if any case fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from schemas.audit_v1 import (
    AuditFinding,
    AuditReport,
    Citation,
    McpQuery,
    MirrorCheck,
)


_SHA_OK = "0123456789abcdef0123456789abcdef01234567"
_SHA12_OK = "0123456789ab"
_SHA12_OK_2 = "fedcba987654"

# 64-hex sha256 placeholders. _HASH_A == _HASH_B simulates equal raw bytes;
# _HASH_A != _HASH_C simulates a difference (autocrlf artefact OR true mismatch
# depending on whether the normalized hashes also differ).
_HASH_A = "a" * 64
_HASH_B = "a" * 64
_HASH_C = "b" * 64
_HASH_NORM_X = "d" * 64
_HASH_NORM_Y = "e" * 64


def _valid_audit_dict() -> dict:
    return {
        "schema_version": "v1",
        "task_id": "2026-05-22-example-erp-02",
        "sdd_metadata_ref": "sdd_metadata.json",
        "sdd_ref": "sdd.md",
        "impl_metadata_ref": "impl_metadata.json",
        "analysis_ref": "analysis_report.json",
        "project_id": "example-erp",
        "path_local": "<workspace>/1c-projects/example-erp/src",
        "branch_audited": "orchestrator/2026-05-22-example-erp-02",
        "branch_sha_audited": _SHA_OK,
        "findings": [],
        "ff_re_audit": {
            "FF1": {"status": "pass", "note": "external claims re-verified via codemetadata"},
            "FF2": {"status": "na", "note": "no schema inlining to re-walk"},
            "FF3": {"status": "pass", "note": "failure modes cross-checked per stage"},
            "FF4": {"status": "pass", "note": "code-over-doc: get_object hit confirms attribute"},
            "FF5": {"status": "pass", "note": "blast radius unchanged; no new dangerous primitive"},
            "FF6": {"status": "pass", "note": "REFUSE list cross-checked against commit log"},
            "FF7": {"status": "pass", "note": "DoD pre/post present"},
            "FF8": {"status": "pass", "note": "dod_post regexes re-grep, all match"},
        },
        "re_verifications_attempted": [
            {
                "name": "cfe-validate",
                "status": "ok",
                "diagnostic": "structural equivalence via codemetadata.get_object",
                "mandatory": True,
            }
        ],
        "mcp_queries_issued": [
            {
                "server": "codemetadata",
                "tool": "get_object",
                "args_sha12": _SHA12_OK,
                "response_sha12": _SHA12_OK_2,
                "raw_path": "audit_raw/codemetadata/r0-q0-0123456789ab.json",
            }
        ],
        "recommended_verdict": "ack",
        "citations": [
            {
                "source": "impl_metadata",
                "ref": "impl_metadata.json#commits.0.files.0",
            },
            {
                "source": "audit_raw",
                "ref": "audit_raw/codemetadata/r0-q0-0123456789ab.json",
            },
            {
                "source": "mcp",
                "ref": "codemetadata:tools/get_object/Catalog.Counterparties",
            },
        ],
        "audit_started_at": "2026-05-22T19:00:00Z",
        "audit_ended_at": "2026-05-22T19:08:42Z",
        "audit_self_review_notes": "cold-context optic; re-verified one mandatory cfe-validate via codemetadata get_object; no out-of-scope edits found",
    }


_RESULTS: list[tuple[str, bool, str]] = []


def _expect_ok(name: str, builder) -> None:
    try:
        result = builder()
        _RESULTS.append((name, True, f"validated: {type(result).__name__}"))
    except ValidationError as exc:
        _RESULTS.append((name, False, f"unexpected ValidationError: {exc}"))


def _expect_fail(name: str, builder, must_mention: str) -> None:
    try:
        builder()
        _RESULTS.append((name, False, "expected ValidationError but got success"))
    except ValidationError as exc:
        msg = str(exc)
        if must_mention.lower() not in msg.lower():
            _RESULTS.append(
                (name, False, f"ValidationError did not mention '{must_mention}': {msg}")
            )
        else:
            _RESULTS.append((name, True, f"raised on {must_mention!r}"))


def case_a_valid_full() -> None:
    _expect_ok(
        "a) full valid, findings=[], recommended_verdict=ack",
        lambda: AuditReport.model_validate(_valid_audit_dict()),
    )


def case_b_missing_ff6() -> None:
    d = _valid_audit_dict()
    del d["ff_re_audit"]["FF6"]
    _expect_fail(
        "b) ff_re_audit missing FF6",
        lambda: AuditReport.model_validate(d),
        "FF6",
    )


def case_c_bad_branch() -> None:
    d = _valid_audit_dict()
    d["branch_audited"] = "dispatch/foo"
    _expect_fail(
        "c) branch_audited='dispatch/foo'",
        lambda: AuditReport.model_validate(d),
        "branch_audited",
    )


def case_d_short_sha() -> None:
    d = _valid_audit_dict()
    d["branch_sha_audited"] = "abc"
    _expect_fail(
        "d) branch_sha_audited too short",
        lambda: AuditReport.model_validate(d),
        "branch_sha_audited",
    )


def case_e_bad_sha12() -> None:
    _expect_fail(
        "e) McpQuery.args_sha12='0123abc' (too short)",
        lambda: McpQuery(
            server="codemetadata",
            tool="get_object",
            args_sha12="0123abc",
            response_sha12=_SHA12_OK_2,
            raw_path="audit_raw/codemetadata/r0-q0-x.json",
        ),
        "args_sha12",
    )


def case_f_bad_impl_metadata_citation() -> None:
    _expect_fail(
        "f) Citation(source='impl_metadata') with bad ref",
        lambda: Citation(source="impl_metadata", ref="something_else"),
        "impl_metadata.json#",
    )


def case_g_good_audit_raw_citation() -> None:
    _expect_ok(
        "g) Citation(source='audit_raw', ref='audit_raw/codemetadata/r0-q0-abc.json')",
        lambda: Citation(
            source="audit_raw",
            ref="audit_raw/codemetadata/r0-q0-abc.json",
        ),
    )


def case_h_blocker_finding_with_ack_recommendation() -> None:
    d = _valid_audit_dict()
    d["findings"] = [
        {
            "id": "AF1",
            "category": "out_of_scope_edit",
            "severity": "blocker",
            "surface": "impl",
            "description": "implementer touched Catalog.Currencies which is not in any SDD deliverable",
            "evidence": "git diff: src/Catalogs/Currencies/Ext/ManagerModule.bsl",
        }
    ]
    d["recommended_verdict"] = "ack"  # decoupled by design; validate_audit catches the mismatch
    _expect_ok(
        "h) 1 blocker finding + recommended_verdict=ack (decoupled, schema OK)",
        lambda: AuditReport.model_validate(d),
    )


def case_i_empty_findings_with_reject_recommendation() -> None:
    d = _valid_audit_dict()
    d["findings"] = []
    d["recommended_verdict"] = "reject"
    _expect_ok(
        "i) findings=[] + recommended_verdict=reject (decoupled, schema OK)",
        lambda: AuditReport.model_validate(d),
    )


def case_j_duplicate_finding_ids() -> None:
    d = _valid_audit_dict()
    d["findings"] = [
        {
            "id": "AF1",
            "category": "other",
            "severity": "info",
            "surface": "sdd",
            "description": "x",
            "evidence": "y",
        },
        {
            "id": "AF1",
            "category": "other",
            "severity": "info",
            "surface": "sdd",
            "description": "x2",
            "evidence": "y2",
        },
    ]
    _expect_fail(
        "j) duplicate AuditFinding.id",
        lambda: AuditReport.model_validate(d),
        "duplicate ids",
    )


def case_k_bad_finding_id() -> None:
    _expect_fail(
        "k) AuditFinding.id='F1' (missing AF prefix)",
        lambda: AuditFinding(
            id="F1",
            category="other",
            severity="info",
            surface="sdd",
            description="x",
            evidence="y",
        ),
        "AuditFinding.id",
    )


def _mirror_check(
    local_raw: str,
    local_norm: str,
    other_raw: str,
    other_norm: str,
    raw_match: bool | None = None,
    normalized_match: bool | None = None,
) -> dict:
    if raw_match is None:
        raw_match = local_raw == other_raw
    if normalized_match is None:
        normalized_match = local_norm == other_norm
    return {
        "local_path": "<orchestrator-root>/tasks/example-erp-02/audit_raw/attrs.md",
        "local_raw_sha256": local_raw,
        "local_normalized_sha256": local_norm,
        "local_raw_bytes": 5851,
        "local_normalized_bytes": 5851,
        "counterpart_path": "<workspace>/1c-projects/example-erp/src/docs/orchestrator/example-erp-02/attrs.md",
        "counterpart_raw_sha256": other_raw,
        "counterpart_normalized_sha256": other_norm,
        "counterpart_raw_bytes": 5881 if other_raw != local_raw else 5851,
        "counterpart_normalized_bytes": 5851,
        "raw_match": raw_match,
        "normalized_match": normalized_match,
    }


def case_l_mirror_check_absent() -> None:
    # Phase 5: mirror_check defaults to None; legacy Phase 4 fixtures unchanged.
    d = _valid_audit_dict()
    assert "mirror_check" not in d["re_verifications_attempted"][0]
    _expect_ok("l) mirror_check absent (default None)", lambda: AuditReport.model_validate(d))


def case_m_mirror_check_match() -> None:
    d = _valid_audit_dict()
    d["re_verifications_attempted"][0]["mirror_check"] = _mirror_check(
        _HASH_A, _HASH_NORM_X, _HASH_B, _HASH_NORM_X
    )
    _expect_ok("m) mirror_check raw+normalized match", lambda: AuditReport.model_validate(d))


def case_n_mirror_check_eol_artefact() -> None:
    # Exact Phase 4 Stage 6 example-erp-02 scenario: raw differs, normalized matches.
    d = _valid_audit_dict()
    d["re_verifications_attempted"][0]["mirror_check"] = _mirror_check(
        _HASH_A, _HASH_NORM_X, _HASH_C, _HASH_NORM_X
    )
    _expect_ok("n) mirror_check eol_artefact_only (raw differs, normalized matches)", lambda: AuditReport.model_validate(d))


def case_o_mirror_check_true_mismatch() -> None:
    # True semantic mismatch -- both raw and normalized differ.
    d = _valid_audit_dict()
    d["re_verifications_attempted"][0]["status"] = "fail"
    d["re_verifications_attempted"][0]["mirror_check"] = _mirror_check(
        _HASH_A, _HASH_NORM_X, _HASH_C, _HASH_NORM_Y
    )
    _expect_ok("o) mirror_check true semantic mismatch (status=fail)", lambda: AuditReport.model_validate(d))


def case_p_mirror_check_raw_match_disagrees_with_hashes() -> None:
    d = _valid_audit_dict()
    d["re_verifications_attempted"][0]["mirror_check"] = _mirror_check(
        _HASH_A, _HASH_NORM_X, _HASH_A, _HASH_NORM_X, raw_match=False
    )
    _expect_fail("p) mirror_check raw_match=false but raw_sha256 fields equal", lambda: AuditReport.model_validate(d), "raw_match")


def case_q_mirror_check_norm_match_disagrees_with_hashes() -> None:
    d = _valid_audit_dict()
    d["re_verifications_attempted"][0]["mirror_check"] = _mirror_check(
        _HASH_A, _HASH_NORM_X, _HASH_C, _HASH_NORM_X, normalized_match=False
    )
    _expect_fail("q) mirror_check normalized_match=false but normalized fields equal", lambda: AuditReport.model_validate(d), "normalized_match")


def case_r_mirror_check_raw_match_implies_norm_match() -> None:
    # raw_match=true but normalized_match=false -- impossible.
    d = _valid_audit_dict()
    d["re_verifications_attempted"][0]["mirror_check"] = _mirror_check(
        _HASH_A, _HASH_NORM_X, _HASH_A, _HASH_NORM_Y
    )
    _expect_fail("r) mirror_check raw_match=true with normalized_match=false", lambda: AuditReport.model_validate(d), "impossible")


def case_s_mirror_check_bad_sha256_shape() -> None:
    d = _valid_audit_dict()
    d["re_verifications_attempted"][0]["mirror_check"] = _mirror_check(
        "deadbeef", _HASH_NORM_X, _HASH_B, _HASH_NORM_X
    )
    _expect_fail("s) mirror_check local_raw_sha256 too short", lambda: AuditReport.model_validate(d), "local_raw_sha256")


def main() -> int:
    cases = [
        case_a_valid_full,
        case_b_missing_ff6,
        case_c_bad_branch,
        case_d_short_sha,
        case_e_bad_sha12,
        case_f_bad_impl_metadata_citation,
        case_g_good_audit_raw_citation,
        case_h_blocker_finding_with_ack_recommendation,
        case_i_empty_findings_with_reject_recommendation,
        case_j_duplicate_finding_ids,
        case_k_bad_finding_id,
        case_l_mirror_check_absent,
        case_m_mirror_check_match,
        case_n_mirror_check_eol_artefact,
        case_o_mirror_check_true_mismatch,
        case_p_mirror_check_raw_match_disagrees_with_hashes,
        case_q_mirror_check_norm_match_disagrees_with_hashes,
        case_r_mirror_check_raw_match_implies_norm_match,
        case_s_mirror_check_bad_sha256_shape,
    ]
    for c in cases:
        c()

    print("=== audit_v1 schema fixtures ===")
    failed = 0
    for name, ok, msg in _RESULTS:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name} -- {msg}")
        if not ok:
            failed += 1
    print(f"=== {len(_RESULTS) - failed} / {len(_RESULTS)} passed ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
