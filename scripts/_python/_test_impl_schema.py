"""Fixture-tests for schemas/impl_v1.ImplementationResult (Phase 3 Stage 1 SDD section 5.1).

Runs from Orchestrator root: `python scripts/_python/_test_impl_schema.py`.
Prints PASS / FAIL per case + exits non-zero if any case fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from schemas.impl_v1 import ImplementationResult, Citation, MirrorCheck


_SHA_OK = "0123456789abcdef0123456789abcdef01234567"
_SHA_OK_2 = "fedcba9876543210fedcba9876543210fedcba98"

# 64-hex sha256 placeholders. _A == _B simulates equal raw bytes; _A != _C
# simulates either an EOL artefact (when normalized hashes match) or a true
# semantic mismatch (when normalized hashes also differ).
_HASH_A = "a" * 64
_HASH_B = "a" * 64
_HASH_C = "b" * 64
_HASH_D = "c" * 64
_HASH_NORM_X = "d" * 64
_HASH_NORM_Y = "e" * 64


def _valid_impl_dict() -> dict:
    return {
        "schema_version": "v1",
        "task_id": "2026-05-22-example-erp-02",
        "sdd_metadata_ref": "sdd_metadata.json",
        "sdd_ref": "sdd.md",
        "project_id": "example-erp",
        "path_local": "<workspace>/1c-projects/example-erp/src",
        "gitea_remote_url": "http://<gitea-host>:3000/admin/example-erp-src.git",
        "branch_name": "orchestrator/2026-05-22-example-erp-02",
        "commits": [
            {
                "sha": _SHA_OK,
                "subject": "feat(orch 2026-05-22-example-erp-02): stage 1 -- add Catalog.Counterparties.INN attribute",
                "files": ["src/Catalogs/Counterparties/Ext/ManagerModule.bsl"],
                "stage_ref": "Stage 1",
            }
        ],
        "files_changed": ["src/Catalogs/Counterparties/Ext/ManagerModule.bsl"],
        "validations_attempted": [
            {
                "name": "cfe-validate",
                "status": "ok",
                "diagnostic": "no errors",
                "mandatory": True,
            }
        ],
        "open_questions": [],
        "refusals": ["live db-update -- operator only"],
        "diff_baseline": {
            "before_sha": _SHA_OK_2,
            "after_branch_sha": _SHA_OK,
            "orchestrator_before": "",
            "orchestrator_after": "?? tasks/2026-05-22-example-erp-02/impl_metadata.json",
        },
        "ff_self_audit": {
            "FF1": {"status": "pass", "note": "external claims tagged"},
            "FF2": {"status": "na", "note": "no inlining required"},
            "FF3": {"status": "pass", "note": "failure modes per stage"},
            "FF4": {"status": "pass", "note": "re-verified via codemetadata"},
            "FF5": {"status": "pass", "note": "blast radius accepted, per-task branch"},
            "FF6": {"status": "pass", "note": "honor-system items tagged"},
            "FF7": {"status": "pass", "note": "pre+post DoD split"},
            "FF8": {"status": "na", "note": "no grep regex in sdd dod_post"},
        },
        "citations_used": [
            {
                "source": "sdd_metadata",
                "ref": "sdd_metadata.json#stages.1.deliverables.0",
            },
            {"source": "sdd", "ref": "sdd.md#5.1-stage-1"},
            {"source": "mcp", "ref": "codemetadata:tools/get_object/Catalog.Counterparties"},
        ],
        "status": "ready",
        "failures": [],
        "audit_inputs": [
            "branch orchestrator/2026-05-22-example-erp-02 in <workspace>/1c-projects/example-erp/src",
            "validations_attempted[0].name=cfe-validate",
        ],
        "self_review_notes": "minimal-scope edit; FF4 re-verify hit codemetadata once",
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
    _expect_ok("a) full valid, status=ready, mandatory val ok", lambda: ImplementationResult.model_validate(_valid_impl_dict()))


def case_b_ready_with_failed_mandatory() -> None:
    d = _valid_impl_dict()
    d["validations_attempted"][0]["status"] = "fail"
    _expect_fail("b) status=ready with mandatory validation failed", lambda: ImplementationResult.model_validate(d), "mandatory validation")


def case_c_needs_revision_empty_failures() -> None:
    d = _valid_impl_dict()
    d["status"] = "needs_revision"
    d["failures"] = []
    _expect_fail("c) status=needs_revision with failures=[]", lambda: ImplementationResult.model_validate(d), "failures non-empty")


def case_d_bad_branch_name() -> None:
    d = _valid_impl_dict()
    d["branch_name"] = "dispatch/2026-05-22-example-erp-02"
    _expect_fail("d) branch_name='dispatch/...'", lambda: ImplementationResult.model_validate(d), "branch_name")


def case_e_short_sha() -> None:
    d = _valid_impl_dict()
    d["commits"][0]["sha"] = "abc"
    _expect_fail("e) ImplCommit.sha too short", lambda: ImplementationResult.model_validate(d), "sha")


def case_f_bad_sdd_metadata_citation() -> None:
    d = _valid_impl_dict()
    d["citations_used"].append(
        {"source": "sdd_metadata", "ref": "something_else"}
    )
    _expect_fail("f) Citation(source='sdd_metadata') with bad ref", lambda: ImplementationResult.model_validate(d), "sdd_metadata.json#")


def case_g_good_sdd_citation() -> None:
    _expect_ok(
        "g) Citation(source='sdd', ref='sdd.md#stage1')",
        lambda: Citation(source="sdd", ref="sdd.md#stage1"),
    )


def case_h_missing_ff5() -> None:
    d = _valid_impl_dict()
    del d["ff_self_audit"]["FF5"]
    _expect_fail("h) ff_self_audit missing FF5", lambda: ImplementationResult.model_validate(d), "FF5")


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
        "local_path": "<workspace>/1c-projects/example-erp/src/docs/orchestrator/example-erp-02/attrs.md",
        "local_raw_sha256": local_raw,
        "local_normalized_sha256": local_norm,
        "local_raw_bytes": 5851,
        "local_normalized_bytes": 5851,
        "counterpart_path": "<orchestrator-root>/tasks/example-erp-02/audit_raw/attrs.md",
        "counterpart_raw_sha256": other_raw,
        "counterpart_normalized_sha256": other_norm,
        "counterpart_raw_bytes": 5881 if other_raw != local_raw else 5851,
        "counterpart_normalized_bytes": 5851,
        "raw_match": raw_match,
        "normalized_match": normalized_match,
    }


def case_i_mirror_check_absent() -> None:
    # Phase 5: mirror_check defaults to None; legacy fixtures unchanged.
    d = _valid_impl_dict()
    assert "mirror_check" not in d["validations_attempted"][0]
    _expect_ok("i) mirror_check absent (default None)", lambda: ImplementationResult.model_validate(d))


def case_j_mirror_check_match() -> None:
    d = _valid_impl_dict()
    d["validations_attempted"][0]["mirror_check"] = _mirror_check(
        _HASH_A, _HASH_NORM_X, _HASH_B, _HASH_NORM_X
    )
    _expect_ok("j) mirror_check raw+normalized match", lambda: ImplementationResult.model_validate(d))


def case_k_mirror_check_eol_artefact() -> None:
    # Raw hashes differ (autocrlf rewrite), normalized hashes match.
    # The exact Phase 4 Stage 6 example-erp-02 scenario.
    d = _valid_impl_dict()
    d["validations_attempted"][0]["mirror_check"] = _mirror_check(
        _HASH_A, _HASH_NORM_X, _HASH_C, _HASH_NORM_X
    )
    _expect_ok("k) mirror_check eol_artefact_only (raw differs, normalized matches)", lambda: ImplementationResult.model_validate(d))


def case_l_mirror_check_true_mismatch_non_mandatory() -> None:
    # True semantic mismatch -- both raw and normalized differ. The validation
    # status must be 'fail'; since we keep status='ready' on the impl report,
    # mark this attempt non-mandatory so _status_failures_consistent does not
    # trigger.
    d = _valid_impl_dict()
    d["validations_attempted"][0]["status"] = "fail"
    d["validations_attempted"][0]["mandatory"] = False
    d["validations_attempted"][0]["mirror_check"] = _mirror_check(
        _HASH_A, _HASH_NORM_X, _HASH_C, _HASH_NORM_Y
    )
    _expect_ok("l) mirror_check true mismatch on non-mandatory check", lambda: ImplementationResult.model_validate(d))


def case_m_mirror_check_raw_match_disagrees_with_hashes() -> None:
    # raw_sha256 fields are EQUAL but raw_match=false -- inconsistent.
    d = _valid_impl_dict()
    d["validations_attempted"][0]["mirror_check"] = _mirror_check(
        _HASH_A, _HASH_NORM_X, _HASH_A, _HASH_NORM_X, raw_match=False
    )
    _expect_fail("m) mirror_check raw_match=false but raw_sha256 fields equal", lambda: ImplementationResult.model_validate(d), "raw_match")


def case_n_mirror_check_norm_match_disagrees_with_hashes() -> None:
    # normalized_sha256 fields are EQUAL but normalized_match=false.
    d = _valid_impl_dict()
    d["validations_attempted"][0]["mirror_check"] = _mirror_check(
        _HASH_A, _HASH_NORM_X, _HASH_C, _HASH_NORM_X, normalized_match=False
    )
    _expect_fail("n) mirror_check normalized_match=false but normalized fields equal", lambda: ImplementationResult.model_validate(d), "normalized_match")


def case_o_mirror_check_raw_match_implies_norm_match() -> None:
    # raw_match=true but normalized_match=false -- impossible (raw equality
    # implies normalized equality). Trigger by setting normalized hashes to
    # different values while raw hashes match.
    d = _valid_impl_dict()
    d["validations_attempted"][0]["mirror_check"] = _mirror_check(
        _HASH_A, _HASH_NORM_X, _HASH_A, _HASH_NORM_Y
    )
    _expect_fail("o) mirror_check raw_match=true with normalized_match=false", lambda: ImplementationResult.model_validate(d), "impossible")


def case_p_mirror_check_bad_sha256_shape() -> None:
    d = _valid_impl_dict()
    d["validations_attempted"][0]["mirror_check"] = _mirror_check(
        "deadbeef", _HASH_NORM_X, _HASH_B, _HASH_NORM_X
    )
    _expect_fail("p) mirror_check local_raw_sha256 too short", lambda: ImplementationResult.model_validate(d), "local_raw_sha256")


def main() -> int:
    cases = [
        case_a_valid_full,
        case_b_ready_with_failed_mandatory,
        case_c_needs_revision_empty_failures,
        case_d_bad_branch_name,
        case_e_short_sha,
        case_f_bad_sdd_metadata_citation,
        case_g_good_sdd_citation,
        case_h_missing_ff5,
        case_i_mirror_check_absent,
        case_j_mirror_check_match,
        case_k_mirror_check_eol_artefact,
        case_l_mirror_check_true_mismatch_non_mandatory,
        case_m_mirror_check_raw_match_disagrees_with_hashes,
        case_n_mirror_check_norm_match_disagrees_with_hashes,
        case_o_mirror_check_raw_match_implies_norm_match,
        case_p_mirror_check_bad_sha256_shape,
    ]
    for c in cases:
        c()

    print("=== impl_v1 schema fixtures ===")
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
