"""Stage 5 verification: validate_audit.py exit codes 0..15.

16 fixtures, one per exit code. Each stages a fake task_root with:
  - audit_report.json (varies per exit code)
  - sdd_metadata.json + impl_metadata.json + auditor_packet.json +
    implementer_packet.json + sdd_writer_packet.json
  - claude session.jsonl dir with synthetic mcp__ tool_use events
  - codex rollout under per-task .codex_home/sessions/ with MCP entries
  - path_local: throwaway git repo with branch orchestrator/<task_id>
  - ORCH_TEST_ORCHESTRATOR_ROOT: throwaway git repo (clean by default)

Run: `python scripts/_python/_test_validate_audit.py`
Exits non-zero on any failure.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run_validate(task_root: Path, env_overrides: dict[str, str]) -> tuple[int, str, str]:
    env = os.environ.copy()
    env.update(env_overrides)
    # Force orchestrator root override unless caller explicitly cleared it.
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/_python/validate_audit.py"), str(task_root)],
        capture_output=True,
        text=True,
        env=env,
    )
    return r.returncode, r.stdout, r.stderr


def _git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q", "-b", "main"], path)
    _git(["config", "user.email", "test@test"], path)
    _git(["config", "user.name", "test"], path)
    (path / "README").write_text("init", encoding="utf-8")
    _git(["add", "README"], path)
    _git(["commit", "-q", "-m", "init"], path)


def _make_session_jsonl(path: Path, mcp_count: int, when: float) -> None:
    """Write a synthetic claude session.jsonl with `mcp_count` mcp__ tool_use."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(mcp_count):
        lines.append(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": f"toolu_{i}",
                    "name": f"mcp__1c-codemetadata__get_object_{i}",
                    "input": {"object": "x"},
                }],
            },
        }))
    if not lines:
        # claude session.jsonl messages are always dicts; mirror that shape so
        # count_mcp_in_jsonls' `msg.get(...)` doesn't crash on synthetic zeros.
        lines.append(json.dumps({
            "type": "system",
            "message": {"role": "system", "content": []},
        }))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.utime(path, (when, when))


def _make_codex_rollout(rollout_path: Path, mcp_count: int, session_ts_iso: str) -> None:
    rollout_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({
        "timestamp": session_ts_iso,
        "type": "session_meta",
        "payload": {"id": "test-session", "timestamp": session_ts_iso},
    })]
    for i in range(mcp_count):
        # Phase 4 Stage 6 lock: codex 0.130.0 distinguishes MCP function_calls
        # from built-ins via payload.namespace (regex ^mcp__<server>__$), NOT
        # via payload.name prefix. _codex_rollout._is_mcp_function_call reads
        # payload.namespace; fixture must include it.
        lines.append(json.dumps({
            "timestamp": session_ts_iso,
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": f"get_object_{i}",
                "namespace": "mcp__codemetadata__",
                "arguments": "{}",
                "call_id": f"call_{i}",
            },
        }))
    rollout_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


_TASK_ID = "2026-05-22-example-erp-99"
_BRANCH = f"orchestrator/{_TASK_ID}"
_FF_KEYS = ("FF1", "FF2", "FF3", "FF4", "FF5", "FF6", "FF7", "FF8")


def _valid_ff_re_audit() -> dict:
    return {k: {"status": "na", "note": f"synthetic {k} note"} for k in _FF_KEYS}


def _valid_ff_self_audit() -> dict:
    return {k: {"status": "na", "note": f"synthetic {k} note"} for k in _FF_KEYS}


def _stage_baseline(tmp: Path) -> tuple[Path, Path, Path, dict[str, str]]:
    """Stage a fully-valid baseline. Returns (task_root, path_local, orch_root, env)."""
    task_root = tmp / "task_root"
    task_root.mkdir()
    path_local = tmp / "path_local"
    orch_root = tmp / "orch_root"
    _init_git_repo(path_local)
    _init_git_repo(orch_root)
    # path_local: branch with one commit
    _git(["checkout", "-q", "-b", _BRANCH], path_local)
    (path_local / "deliverable.txt").write_text("body", encoding="utf-8")
    _git(["add", "deliverable.txt"], path_local)
    _git(["commit", "-q", "-m", f"orch {_TASK_ID} initial"], path_local)
    rc, sha_out, _ = _git(["rev-parse", f"refs/heads/{_BRANCH}"], path_local)
    assert rc == 0
    branch_sha = sha_out.strip()

    # claude session dir with three jsonls (analyst < writer < impl by mtime)
    session_dir = tmp / "session_dir"
    base = time.time() - 10000
    _make_session_jsonl(session_dir / "analyst.jsonl",     mcp_count=2, when=base + 100)
    _make_session_jsonl(session_dir / "writer.jsonl",      mcp_count=2, when=base + 300)
    _make_session_jsonl(session_dir / "implementer.jsonl", mcp_count=2, when=base + 500)
    writer_cutoff_iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(base + 250))
    impl_cutoff_iso   = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(base + 450))

    # codex rollout under per-task .codex_home
    codex_home = task_root / ".codex_home"
    codex_sessions = codex_home / "sessions" / "2026" / "05" / "22"
    audit_started_iso = "2026-05-22T16:00:00+00:00"
    _make_codex_rollout(
        codex_sessions / "rollout-2026-05-22T16-00-00-test.jsonl",
        mcp_count=2,
        session_ts_iso=audit_started_iso,
    )

    # impl_metadata.json (one mandatory validation entry)
    impl_meta = {
        "schema_version": "v1",
        "task_id": _TASK_ID,
        "sdd_metadata_ref": "sdd_metadata.json",
        "sdd_ref": "sdd.md",
        "project_id": "example-erp",
        "path_local": str(path_local),
        "gitea_remote_url": "http://example/repo.git",
        "branch_name": _BRANCH,
        "commits": [{
            "sha": branch_sha,
            "subject": f"orch {_TASK_ID} initial",
            "stage_ref": "stage-1",
            "rationale": "test",
        }],
        "files_changed": ["deliverable.txt"],
        "validations_attempted": [
            {"name": "cf-validate", "status": "ok", "diagnostic": "ok", "mandatory": True},
        ],
        "open_questions": [],
        "refusals": [],
        "diff_baseline": {
            "before_sha": "0" * 40,
            "after_branch_sha": branch_sha,
            "orchestrator_before": "",
            "orchestrator_after": "",
        },
        "ff_self_audit": _valid_ff_self_audit(),
        "citations_used": [
            {"source": "code", "ref": "deliverable.txt:1"},
        ],
        "status": "ready",
        "failures": [],
        "audit_inputs": [],
        "self_review_notes": "noop",
    }
    (task_root / "impl_metadata.json").write_text(
        json.dumps(impl_meta, indent=2), encoding="utf-8"
    )

    # sdd_metadata.json (minimal valid v1 not strictly needed -- validate_audit
    # only reads task_id from it as a dict)
    sdd_meta = {"schema_version": "v1", "task_id": _TASK_ID}
    (task_root / "sdd_metadata.json").write_text(
        json.dumps(sdd_meta, indent=2), encoding="utf-8"
    )

    # auditor_packet.json
    auditor_pkt = {
        "task_id": _TASK_ID,
        "project_id": "example-erp",
        "path_local": str(path_local),
        "branch_audited": _BRANCH,
        "before_sha_at_audit_start": branch_sha,
        "codex_home": str(codex_home),
        "created_at": audit_started_iso,
        "orch_porcelain_baseline": [],
    }
    (task_root / "auditor_packet.json").write_text(
        json.dumps(auditor_pkt, indent=2), encoding="utf-8"
    )

    # implementer_packet.json (session_dir + cutoffs)
    impl_pkt = {
        "task_id": _TASK_ID,
        "session_dir": str(session_dir),
        "created_at": impl_cutoff_iso,
        "orch_porcelain_baseline": [],
    }
    (task_root / "implementer_packet.json").write_text(
        json.dumps(impl_pkt, indent=2), encoding="utf-8"
    )

    # sdd_writer_packet.json (writer cutoff)
    writer_pkt = {
        "task_id": _TASK_ID,
        "analyst_session_dir": str(session_dir),
        "created_at": writer_cutoff_iso,
    }
    (task_root / "sdd_writer_packet.json").write_text(
        json.dumps(writer_pkt, indent=2), encoding="utf-8"
    )

    # audit_report.json (clean, computed_verdict=ack)
    audit_report = {
        "schema_version": "v1",
        "task_id": _TASK_ID,
        "sdd_metadata_ref": "sdd_metadata.json",
        "sdd_ref": "sdd.md",
        "impl_metadata_ref": "impl_metadata.json",
        "analysis_ref": "analysis_report.json",
        "project_id": "example-erp",
        "path_local": str(path_local),
        "branch_audited": _BRANCH,
        "branch_sha_audited": branch_sha,
        "findings": [],
        "ff_re_audit": _valid_ff_re_audit(),
        "re_verifications_attempted": [
            {"name": "cf-validate", "status": "ok", "diagnostic": "ok", "mandatory": True},
        ],
        "mcp_queries_issued": [{
            "server": "codemetadata",
            "tool": "get_object",
            "args_sha12": "0123456789ab",
            "response_sha12": "cba987654321",
            "raw_path": "audit_raw/codemetadata/r0-q0.json",
        }],
        "recommended_verdict": "ack",
        "citations": [{
            "source": "audit_raw",
            "ref": "audit_raw/codemetadata/r0-q0.json",
        }],
        "audit_started_at": audit_started_iso,
        "audit_ended_at": "2026-05-22T16:05:00+00:00",
        "audit_self_review_notes": "cold-context optic notes about example-erp-99",
    }
    (task_root / "audit_report.json").write_text(
        json.dumps(audit_report, indent=2), encoding="utf-8"
    )

    env = {
        "ORCH_TEST_ORCHESTRATOR_ROOT": str(orch_root),
        "ORCH_TEST_CODEX_SESSIONS_ROOT": str(codex_home / "sessions"),
    }
    return task_root, path_local, orch_root, env


def _expect(name: str, expected: int, actual: int, stdout: str, stderr: str) -> bool:
    if expected == actual:
        print(f"[PASS] {name} -- exit {actual}")
        return True
    print(f"[FAIL] {name} -- expected exit {expected}, got {actual}")
    if stdout:
        print(f"        stdout: {stdout.strip()[:300]}")
    if stderr:
        print(f"        stderr: {stderr.strip()[:300]}")
    return False


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> int:
    failures = 0
    base_tmp = Path(tempfile.mkdtemp(prefix="va_test_"))
    try:
        # ----- exit 0: clean baseline -----
        case = base_tmp / "case00"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 0 (clean ack)", 0, rc, so, se):
            failures += 1
        if "computed_verdict=ack" not in so:
            print(f"        WARN: summary missing computed_verdict=ack")

        # ----- exit 1: pydantic ValidationError (bad branch_sha shape) -----
        case = base_tmp / "case01"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        data = json.loads((tr / "audit_report.json").read_text())
        data["branch_sha_audited"] = "not-a-valid-sha"
        _write_json(tr / "audit_report.json", data)
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 1 (pydantic)", 1, rc, so, se):
            failures += 1

        # ----- exit 2: no audit_report.json -----
        case = base_tmp / "case02"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        (tr / "audit_report.json").unlink()
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 2 (no report)", 2, rc, so, se):
            failures += 1

        # ----- exit 3: task_id mismatch -----
        case = base_tmp / "case03"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        data = json.loads((tr / "audit_report.json").read_text())
        data["task_id"] = "2026-05-22-example-erp-OTHER"
        _write_json(tr / "audit_report.json", data)
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 3 (task_id mismatch)", 3, rc, so, se):
            failures += 1

        # ----- exit 4: unparseable JSON -----
        case = base_tmp / "case04"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        (tr / "audit_report.json").write_text("{not json", encoding="utf-8")
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 4 (parse)", 4, rc, so, se):
            failures += 1

        # ----- exit 5: Gate A -- branch tip moved since audit -----
        case = base_tmp / "case05"
        case.mkdir()
        tr, pl, _or, env = _stage_baseline(case)
        # Add a new commit to the branch after audit, then run validate_audit
        (pl / "extra.txt").write_text("post-audit", encoding="utf-8")
        _git(["add", "extra.txt"], pl)
        _git(["commit", "-q", "-m", f"orch {_TASK_ID} post-audit"], pl)
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 5 (Gate A stale)", 5, rc, so, se):
            failures += 1

        # ----- exit 6: analyst session.jsonl 0 mcp -----
        case = base_tmp / "case06"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        wp = json.loads((tr / "sdd_writer_packet.json").read_text())
        session_dir = Path(wp["analyst_session_dir"])
        _make_session_jsonl(session_dir / "analyst.jsonl", mcp_count=0,
                            when=time.time() - 9900)
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 6 (analyst no MCP)", 6, rc, so, se):
            failures += 1

        # ----- exit 7: writer session.jsonl 0 mcp -----
        case = base_tmp / "case07"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        wp = json.loads((tr / "sdd_writer_packet.json").read_text())
        session_dir = Path(wp["analyst_session_dir"])
        _make_session_jsonl(session_dir / "writer.jsonl", mcp_count=0,
                            when=time.time() - 9700)
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 7 (writer no MCP)", 7, rc, so, se):
            failures += 1

        # ----- exit 8: impl session.jsonl 0 mcp -----
        case = base_tmp / "case08"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        wp = json.loads((tr / "sdd_writer_packet.json").read_text())
        session_dir = Path(wp["analyst_session_dir"])
        _make_session_jsonl(session_dir / "implementer.jsonl", mcp_count=0,
                            when=time.time() - 9500)
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 8 (impl no MCP)", 8, rc, so, se):
            failures += 1

        # ----- exit 9: auditor codex rollout 0 MCP -----
        case = base_tmp / "case09"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        ap = json.loads((tr / "auditor_packet.json").read_text())
        rollout_dir = Path(ap["codex_home"]) / "sessions" / "2026" / "05" / "22"
        # Replace with zero-MCP rollout
        for old in rollout_dir.glob("*.jsonl"):
            old.unlink()
        _make_codex_rollout(
            rollout_dir / "rollout-2026-05-22T16-00-00-zero.jsonl",
            mcp_count=0,
            session_ts_iso="2026-05-22T16:00:00+00:00",
        )
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 9 (auditor no MCP)", 9, rc, so, se):
            failures += 1

        # ----- exit 10: Gate B -- orch_root has dirt outside tasks/<id>/ -----
        case = base_tmp / "case10"
        case.mkdir()
        tr, _pl, orch_root, env = _stage_baseline(case)
        # Add an untracked file outside tasks/ to orch_root
        (orch_root / "stray.txt").write_text("bleed", encoding="utf-8")
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 10 (Gate B orch bleed)", 10, rc, so, se):
            failures += 1

        # ----- exit 11: Gate D -- coverage gap -----
        case = base_tmp / "case11"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        # impl has mandatory cf-validate; audit's re_verifications has it -- drop it
        data = json.loads((tr / "audit_report.json").read_text())
        data["re_verifications_attempted"] = []
        _write_json(tr / "audit_report.json", data)
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 11 (Gate D coverage)", 11, rc, so, se):
            failures += 1

        # ----- exit 12: Gate E -- ff_re_audit missing FF8 -----
        case = base_tmp / "case12"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        data = json.loads((tr / "audit_report.json").read_text())
        del data["ff_re_audit"]["FF8"]
        _write_json(tr / "audit_report.json", data)
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 12 (Gate E FF missing)", 12, rc, so, se):
            failures += 1

        # ----- exit 13: finding ids invalid (duplicates + bad prefix) -----
        case = base_tmp / "case13"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        data = json.loads((tr / "audit_report.json").read_text())
        data["findings"] = [
            {
                "id": "AF1",
                "category": "other",
                "severity": "info",
                "surface": "process",
                "description": "first",
                "evidence": "ev",
            },
            {
                "id": "XF99",  # bad prefix
                "category": "other",
                "severity": "info",
                "surface": "process",
                "description": "bad-prefix id",
                "evidence": "ev",
            },
        ]
        _write_json(tr / "audit_report.json", data)
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 13 (finding ids)", 13, rc, so, se):
            failures += 1

        # ----- exit 14: computed_verdict=request_changes (1 decision finding) -----
        case = base_tmp / "case14"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        data = json.loads((tr / "audit_report.json").read_text())
        data["findings"] = [{
            "id": "AF1",
            "category": "ff_audit_disagreement",
            "severity": "decision",
            "surface": "impl",
            "description": "decision-severity test finding",
            "evidence": "synthetic",
        }]
        data["recommended_verdict"] = "request_changes"
        _write_json(tr / "audit_report.json", data)
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 14 (request_changes)", 14, rc, so, se):
            failures += 1

        # ----- exit 15: computed_verdict=reject (1 blocker finding) -----
        case = base_tmp / "case15"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        data = json.loads((tr / "audit_report.json").read_text())
        data["findings"] = [{
            "id": "AF1",
            "category": "out_of_scope_edit",
            "severity": "blocker",
            "surface": "impl",
            "description": "blocker-severity test finding",
            "evidence": "synthetic",
        }]
        data["recommended_verdict"] = "reject"
        _write_json(tr / "audit_report.json", data)
        rc, so, se = _run_validate(tr, env)
        if not _expect("exit 15 (reject)", 15, rc, so, se):
            failures += 1

        # ----- bonus: disagreement log -----
        # findings empty + recommended=reject -> computed=ack (exit 0) + DISAGREEMENT
        case = base_tmp / "case_dis"
        case.mkdir()
        tr, _pl, _or, env = _stage_baseline(case)
        data = json.loads((tr / "audit_report.json").read_text())
        data["recommended_verdict"] = "reject"
        _write_json(tr / "audit_report.json", data)
        rc, so, se = _run_validate(tr, env)
        if not _expect("bonus: disagreement -> exit 0", 0, rc, so, se):
            failures += 1
        if "DISAGREEMENT: recommended=reject, computed=ack" not in so:
            print("[FAIL] disagreement log line missing from stdout")
            print(f"        stdout head: {so.splitlines()[:3]}")
            failures += 1
        else:
            print("[PASS] disagreement log line present")

        # ----- split-mirror: extra_writable_dir houses the branch -----
        # Stage a baseline, then "move" the orchestrator branch from
        # path_local (where _stage_baseline put it) into a fresh sibling
        # dir simulating extra_writable_dir. Make path_local inert (drop
        # its .git) so Gate A would FAIL on path_local; it must succeed
        # via report.extra_writable_dir.
        case = base_tmp / "case_split"
        case.mkdir()
        tr, pl, _or, env = _stage_baseline(case)

        # Capture the branch sha + replicate the branch into a new repo.
        rc, sha_out, _ = _git(["rev-parse", f"refs/heads/{_BRANCH}"], pl)
        assert rc == 0, sha_out
        branch_sha = sha_out.strip()

        # Create a parallel real git repo at <case>/git_target_dir.
        git_target = case / "git_target_dir"
        _init_git_repo(git_target)
        _git(["checkout", "-q", "-b", _BRANCH], git_target)
        (git_target / "deliverable.txt").write_text("body", encoding="utf-8")
        _git(["add", "deliverable.txt"], git_target)
        _git(["commit", "-q", "-m", f"orch {_TASK_ID} initial"], git_target)
        rc, new_sha_out, _ = _git(["rev-parse", f"refs/heads/{_BRANCH}"], git_target)
        assert rc == 0, new_sha_out
        new_branch_sha = new_sha_out.strip()

        # Break path_local as a git repo: rename .git so any git op fails.
        # Confirms Gate A truly switched to git_target_dir.
        if (pl / ".git").exists():
            shutil.move(str(pl / ".git"), str(pl / ".git_broken"))

        # Patch the audit_report to point to the new git_target_dir +
        # the new branch sha (since we re-built the commit in the new
        # repo with a different author/timestamp -> different sha).
        data = json.loads((tr / "audit_report.json").read_text())
        data["extra_writable_dir"] = str(git_target).replace("\\", "/")
        data["branch_sha_audited"] = new_branch_sha
        _write_json(tr / "audit_report.json", data)
        rc, so, se = _run_validate(tr, env)
        if not _expect("split-mirror: extra_writable_dir resolves Gate A -> exit 0", 0, rc, so, se):
            failures += 1

    finally:
        shutil.rmtree(base_tmp, ignore_errors=True)

    if failures:
        print(f"\n{failures} check(s) failed.")
        return 1
    print("\nAll validate_audit checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
