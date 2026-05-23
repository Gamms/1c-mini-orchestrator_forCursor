"""Validate auditor output for a given task_root.

Usage:
    python scripts/_python/validate_audit.py <task_root>

Exit codes (per Phase 4 SDD section 5.5.2):
    0  OK -- summary printed; computed_verdict=ack
    1  audit_report.json Pydantic ValidationError
    2  audit_report.json absent at task_root (Gate C)
    3  audit_report.task_id != impl_metadata.task_id or != sdd_metadata.task_id
    4  audit_report.json present but JSON not parseable
    5  Gate A: branch_sha_audited != current tip of orchestrator/<task_id>
    6  analyst session.jsonl shows 0 tool_use entries matching ^mcp__
    7  writer session.jsonl shows 0 tool_use entries matching ^mcp__
    8  implementer session.jsonl shows 0 tool_use entries matching ^mcp__
    9  auditor codex rollout shows 0 MCP function_call entries
   10  Gate B: Orchestrator/ has changes outside tasks/<task_id>/
   11  Gate D: re_verifications coverage gap (mandatory impl validation has no
       matching entry in audit_report.re_verifications_attempted)
   12  Gate E: ff_re_audit missing an FF key (FF1..FF8)
   13  audit_report.findings[*].id collisions or non-AF prefix
   14  computed_verdict = request_changes (>=1 decision, no blocker)
   15  computed_verdict = reject (>=1 blocker)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydantic import ValidationError  # noqa: E402

from schemas.audit_v1 import AuditReport  # noqa: E402
from _session_jsonl import (  # noqa: E402
    count_mcp_in_jsonls,
    parse_iso,
    partition_jsonls_3way,
)
from _codex_rollout import (  # noqa: E402
    count_mcp_tool_use,
    find_rollout_for_session,
)


EXIT_OK = 0
EXIT_PYDANTIC = 1
EXIT_NO_REPORT = 2
EXIT_TASK_ID_MISMATCH = 3
EXIT_REPORT_PARSE = 4
EXIT_GATE_A_STALE = 5
EXIT_ANALYST_NO_MCP = 6
EXIT_WRITER_NO_MCP = 7
EXIT_IMPL_NO_MCP = 8
EXIT_AUDITOR_NO_MCP = 9
EXIT_GATE_B_ORCH_BLEED = 10
EXIT_GATE_D_COVERAGE = 11
EXIT_GATE_E_FF_MISSING = 12
EXIT_FINDING_IDS = 13
EXIT_VERDICT_REQUEST_CHANGES = 14
EXIT_VERDICT_REJECT = 15


_FF_KEYS = ("FF1", "FF2", "FF3", "FF4", "FF5", "FF6", "FF7", "FF8")
_FINDING_ID_RE = re.compile(r"^AF[0-9]+$")


def _git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    r = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
    )
    return r.returncode, r.stdout, r.stderr


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def _packet_runtime(*paths: Path) -> str:
    for path in paths:
        if not path.exists():
            continue
        try:
            packet = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        runtime = str(packet.get("runtime", "") or "")
        if runtime:
            return runtime
    return ""


def _count_cursor_mcp_raw(task_root: Path, subdir: str) -> int:
    raw = task_root / subdir
    if not raw.is_dir():
        return 0
    return sum(1 for _ in raw.rglob("*.json"))


def _compute_verdict(findings: list) -> str:
    """Severity-driven computed verdict (per audit_v1 + Phase 4 SDD §5.5.2)."""
    blockers = sum(1 for f in findings if f.severity == "blocker")
    decisions = sum(1 for f in findings if f.severity == "decision")
    if blockers >= 1:
        return "reject"
    if decisions >= 1:
        return "request_changes"
    return "ack"


def _summary(
    report: AuditReport,
    analyst_mcp: int,
    writer_mcp: int,
    impl_mcp: int,
    auditor_mcp: int,
    computed_verdict: str,
) -> str:
    by_sev = {"info": 0, "decision": 0, "blocker": 0}
    for f in report.findings:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
    rv_by_status = {"ok": 0, "fail": 0, "skipped": 0, "unavailable": 0}
    mandatory_seen = 0
    for v in report.re_verifications_attempted:
        rv_by_status[v.status] = rv_by_status.get(v.status, 0) + 1
        if v.mandatory:
            mandatory_seen += 1
    ff = {k: report.ff_re_audit[k].status for k in sorted(report.ff_re_audit)}
    disagree = report.recommended_verdict != computed_verdict
    notes = (report.audit_self_review_notes or "")[:200]
    lines = [
        f"OK task_id={report.task_id}",
        f"  project_id={report.project_id}",
        f"  branch_audited={report.branch_audited}",
        f"  branch_sha_audited={report.branch_sha_audited}",
        f"  findings={by_sev}",
        f"  recommended_verdict={report.recommended_verdict}",
        f"  computed_verdict={computed_verdict}",
        f"  disagreement={disagree}",
        f"  re_verifications_attempted={rv_by_status} mandatory_seen={mandatory_seen}",
        f"  ff_re_audit={ff}",
        f"  analyst_session_mcp_tool_use={analyst_mcp}",
        f"  writer_session_mcp_tool_use={writer_mcp}",
        f"  implementer_session_mcp_tool_use={impl_mcp}",
        f"  auditor_rollout_mcp_tool_use={auditor_mcp}",
        f"  mcp_queries_issued={len(report.mcp_queries_issued)}",
        f"  audit_started_at={report.audit_started_at}",
        f"  audit_ended_at={report.audit_ended_at}",
        f"  audit_self_review_notes={notes!r}",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_audit.py <task_root>", file=sys.stderr)
        return EXIT_NO_REPORT

    task_root = Path(argv[1]).resolve()
    audit_path        = task_root / "audit_report.json"
    sdd_meta_path     = task_root / "sdd_metadata.json"
    impl_meta_path    = task_root / "impl_metadata.json"
    auditor_pkt_path  = task_root / "auditor_packet.json"
    impl_pkt_path     = task_root / "implementer_packet.json"
    writer_pkt_path   = task_root / "sdd_writer_packet.json"

    # exit 2: no audit_report.json (Gate C)
    if not audit_path.exists():
        print(
            f"auditor did not produce audit_report.json at {audit_path}",
            file=sys.stderr,
        )
        return EXIT_NO_REPORT

    # exit 4: not parseable
    try:
        raw = audit_path.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(
            f"audit_report.json JSONDecodeError at line {exc.lineno} col {exc.colno}: {exc.msg}",
            file=sys.stderr,
        )
        return EXIT_REPORT_PARSE

    # exit 12 -- defense-in-depth Gate E (also enforced by Pydantic model_validator;
    # placed before pydantic so the gate-named exit code is reachable even if
    # the schema validator is ever loosened).
    if isinstance(data, dict):
        ff_dict = data.get("ff_re_audit")
        if isinstance(ff_dict, dict):
            missing = [k for k in _FF_KEYS if k not in ff_dict]
            if missing:
                print(
                    f"Gate E: ff_re_audit missing keys {missing}; "
                    f"required {list(_FF_KEYS)}",
                    file=sys.stderr,
                )
                return EXIT_GATE_E_FF_MISSING

    # exit 13 -- defense-in-depth finding-id check (pre-pydantic).
    if isinstance(data, dict):
        findings_list = data.get("findings") or []
        if isinstance(findings_list, list):
            ids: list[str] = []
            bad_prefix: list[str] = []
            for f in findings_list:
                if not isinstance(f, dict):
                    continue
                fid = f.get("id")
                if isinstance(fid, str):
                    ids.append(fid)
                    if not _FINDING_ID_RE.match(fid):
                        bad_prefix.append(fid)
            seen: set[str] = set()
            dupes: list[str] = []
            for fid in ids:
                if fid in seen:
                    dupes.append(fid)
                seen.add(fid)
            if bad_prefix or dupes:
                msg_parts = []
                if bad_prefix:
                    msg_parts.append(f"non-AF-prefixed ids: {sorted(set(bad_prefix))}")
                if dupes:
                    msg_parts.append(f"duplicate ids: {sorted(set(dupes))}")
                print(
                    "findings ids invalid: " + "; ".join(msg_parts),
                    file=sys.stderr,
                )
                return EXIT_FINDING_IDS

    # exit 1: pydantic
    try:
        report = AuditReport.model_validate(data)
    except ValidationError as exc:
        print("audit_report Pydantic ValidationError:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return EXIT_PYDANTIC

    # exit 3: task_id mismatch with sdd_metadata / impl_metadata
    sdd_data: dict = {}
    if sdd_meta_path.exists():
        try:
            sdd_data = json.loads(sdd_meta_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            sdd_data = {}
    impl_data: dict = {}
    if impl_meta_path.exists():
        try:
            impl_data = json.loads(impl_meta_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            impl_data = {}
    sdd_task_id = sdd_data.get("task_id", "") if isinstance(sdd_data, dict) else ""
    impl_task_id = impl_data.get("task_id", "") if isinstance(impl_data, dict) else ""
    mismatches = []
    if sdd_task_id and report.task_id != sdd_task_id:
        mismatches.append(f"sdd_metadata.task_id={sdd_task_id!r}")
    if impl_task_id and report.task_id != impl_task_id:
        mismatches.append(f"impl_metadata.task_id={impl_task_id!r}")
    if mismatches:
        print(
            f"task_id mismatch: audit_report.task_id={report.task_id!r} != "
            + "; ".join(mismatches),
            file=sys.stderr,
        )
        return EXIT_TASK_ID_MISMATCH

    # ---- Gate A: branch_sha_audited == current tip of orchestrator/<task_id> ----
    # Mirrors validate_impl: when report.extra_writable_dir is set, the
    # auditor read the impl repo from extra_writable_dir, not path_local.
    git_target_dir = Path(report.extra_writable_dir) if (report.extra_writable_dir or "").strip() else Path(report.path_local)
    rc, out, err = _git(
        ["rev-parse", f"refs/heads/{report.branch_audited}"],
        git_target_dir,
    )
    if rc != 0:
        print(
            f"Gate A: cannot resolve refs/heads/{report.branch_audited} in "
            f"{git_target_dir}: {err.strip()}",
            file=sys.stderr,
        )
        return EXIT_GATE_A_STALE
    current_tip = out.strip()
    if current_tip != report.branch_sha_audited:
        print(
            f"Gate A: stale audit -- branch_sha_audited={report.branch_sha_audited} "
            f"!= current refs/heads/{report.branch_audited} tip={current_tip}",
            file=sys.stderr,
        )
        return EXIT_GATE_A_STALE

    # ---- Session.jsonl gates 6/7/8 (cursor: *_raw dirs) ----
    runtime = _packet_runtime(
        auditor_pkt_path,
        impl_pkt_path,
        writer_pkt_path,
        task_root / "task_packet.json",
    )
    analyst_mcp = 0
    writer_mcp = 0
    impl_mcp = 0
    auditor_mcp = 0

    if runtime == "cursor":
        analyst_mcp = _count_cursor_mcp_raw(task_root, "analysis_raw")
        writer_mcp = _count_cursor_mcp_raw(task_root, "sdd_raw")
        impl_mcp = _count_cursor_mcp_raw(task_root, "impl_raw")
        auditor_mcp = _count_cursor_mcp_raw(task_root, "audit_raw")
        if analyst_mcp == 0:
            print(
                "cursor runtime: analysis_raw/ has no MCP evidence -- re-run analyst",
                file=sys.stderr,
            )
            return EXIT_ANALYST_NO_MCP
        if writer_mcp == 0:
            print(
                "cursor runtime: sdd_raw/ has no MCP evidence -- re-run sdd_writer",
                file=sys.stderr,
            )
            return EXIT_WRITER_NO_MCP
        if impl_mcp == 0:
            print(
                "cursor runtime: impl_raw/ has no MCP evidence -- re-run implementer",
                file=sys.stderr,
            )
            return EXIT_IMPL_NO_MCP
        if auditor_mcp == 0:
            print(
                "cursor runtime: audit_raw/ has no MCP evidence -- auditor did not consult MCP",
                file=sys.stderr,
            )
            return EXIT_AUDITOR_NO_MCP
    else:
        session_dir = ""
        writer_cutoff_ts: float | None = None
        impl_cutoff_ts: float | None = None

        if impl_pkt_path.exists():
            try:
                ip = json.loads(impl_pkt_path.read_text(encoding="utf-8-sig"))
                session_dir = ip.get("session_dir", "") or ""
                impl_cutoff_ts = parse_iso(ip.get("created_at", "") or "")
            except json.JSONDecodeError:
                pass

        if writer_pkt_path.exists():
            try:
                wp = json.loads(writer_pkt_path.read_text(encoding="utf-8-sig"))
                if not session_dir:
                    session_dir = wp.get("analyst_session_dir", "") or ""
                writer_cutoff_ts = parse_iso(wp.get("created_at", "") or "")
            except json.JSONDecodeError:
                pass

        if not session_dir or not Path(session_dir).exists():
            print(
                "session.jsonl dir not found (implementer_packet.session_dir / "
                "sdd_writer_packet.analyst_session_dir both missing) -- "
                "cannot verify real-MCP gates 6/7/8",
                file=sys.stderr,
            )
            return EXIT_ANALYST_NO_MCP

        analyst_files, writer_files, impl_files = partition_jsonls_3way(
            Path(session_dir), writer_cutoff_ts, impl_cutoff_ts
        )

        if not analyst_files:
            print(f"no analyst session.jsonl found in {session_dir}", file=sys.stderr)
            return EXIT_ANALYST_NO_MCP
        analyst_mcp = count_mcp_in_jsonls(analyst_files)
        if analyst_mcp == 0:
            print(
                "input analysis was synthesized without real MCP "
                f"(0 mcp__ tool_use in {[str(p) for p in analyst_files]})",
                file=sys.stderr,
            )
            return EXIT_ANALYST_NO_MCP

        if not writer_files:
            print(f"no writer session.jsonl found in {session_dir}", file=sys.stderr)
            return EXIT_WRITER_NO_MCP
        writer_mcp = count_mcp_in_jsonls(writer_files)
        if writer_mcp == 0:
            print(
                "sdd_writer did not consult MCP "
                f"(0 mcp__ tool_use in {[str(p) for p in writer_files]})",
                file=sys.stderr,
            )
            return EXIT_WRITER_NO_MCP

        if not impl_files:
            print(f"no implementer session.jsonl found in {session_dir}", file=sys.stderr)
            return EXIT_IMPL_NO_MCP
        impl_mcp = count_mcp_in_jsonls(impl_files)
        if impl_mcp == 0:
            print(
                "implementer did not consult MCP "
                f"(0 mcp__ tool_use in {[str(p) for p in impl_files]})",
                file=sys.stderr,
            )
            return EXIT_IMPL_NO_MCP

        # ---- exit 9: auditor codex rollout has 0 MCP function_calls ----
        auditor_started_at = ""
        codex_home_str = ""
        if auditor_pkt_path.exists():
            try:
                ap = json.loads(auditor_pkt_path.read_text(encoding="utf-8-sig"))
                auditor_started_at = ap.get("created_at", "") or ""
                codex_home_str = ap.get("codex_home", "") or ""
            except json.JSONDecodeError:
                pass

        test_sessions_root = os.environ.get("ORCH_TEST_CODEX_SESSIONS_ROOT", "")
        if test_sessions_root:
            sessions_root: Path | None = Path(test_sessions_root)
        elif codex_home_str:
            sessions_root = Path(codex_home_str) / "sessions"
        else:
            sessions_root = None

        rollout = find_rollout_for_session(
            auditor_started_at,
            sessions_root=sessions_root,
            tolerance_seconds=600.0,
        )
        auditor_mcp = count_mcp_tool_use(rollout) if rollout else 0
        if auditor_mcp == 0:
            loc = str(rollout) if rollout else "<no rollout found>"
            print(
                "auditor did not issue any MCP query of its own "
                f"(0 MCP function_call entries in {loc})",
                file=sys.stderr,
            )
            return EXIT_AUDITOR_NO_MCP

    # ---- Gate B: Orchestrator/ has changes outside tasks/<task_id>/ ----
    orch_root_env = os.environ.get("ORCH_TEST_ORCHESTRATOR_ROOT", "")
    orchestrator_root = Path(orch_root_env) if orch_root_env else ROOT
    # Baseline from auditor_packet (Phase 4 parity with Phase 3 Gate B baseline).
    orch_porcelain_baseline: set[str] = set()
    if auditor_pkt_path.exists():
        try:
            ap = json.loads(auditor_pkt_path.read_text(encoding="utf-8-sig"))
            for ln in ap.get("orch_porcelain_baseline") or []:
                if isinstance(ln, str) and ln.strip():
                    orch_porcelain_baseline.add(ln.rstrip())
        except json.JSONDecodeError:
            pass

    rc, out, err = _git(["status", "--porcelain"], orchestrator_root)
    if rc != 0:
        print(
            f"Gate B: orchestrator-side git status failed: rc={rc} stderr={err.strip()!r}",
            file=sys.stderr,
        )
        return EXIT_GATE_B_ORCH_BLEED
    task_prefix = f"tasks/{report.task_id}/"
    offending: list[str] = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        if line.rstrip() in orch_porcelain_baseline:
            continue
        path = line[3:].strip().strip('"')
        path = _norm(path)
        if not path.startswith(task_prefix):
            offending.append(line)
    if offending:
        print(
            "Gate B: orchestrator-side changes outside tasks/<task_id>/ "
            "and not in auditor_packet.orch_porcelain_baseline:\n  "
            + "\n  ".join(offending),
            file=sys.stderr,
        )
        return EXIT_GATE_B_ORCH_BLEED

    # ---- Gate D: re_verifications coverage ----
    impl_validations = impl_data.get("validations_attempted") or []
    mandatory_names: list[str] = []
    if isinstance(impl_validations, list):
        for v in impl_validations:
            if not isinstance(v, dict):
                continue
            if v.get("mandatory") is True:
                name = v.get("name")
                if isinstance(name, str) and name.strip():
                    mandatory_names.append(name)
    covered = {rv.name for rv in report.re_verifications_attempted}
    missing_cov = [n for n in mandatory_names if n not in covered]
    if missing_cov:
        print(
            "Gate D: re_verifications coverage gap -- mandatory impl "
            f"validations without matching audit entry: {missing_cov}",
            file=sys.stderr,
        )
        return EXIT_GATE_D_COVERAGE

    # ---- Verdict-driven exits (14/15) + ack happy path (0) ----
    computed_verdict = _compute_verdict(report.findings)
    summary_text = _summary(
        report, analyst_mcp, writer_mcp, impl_mcp, auditor_mcp, computed_verdict
    )
    if report.recommended_verdict != computed_verdict:
        print(
            f"DISAGREEMENT: recommended={report.recommended_verdict}, "
            f"computed={computed_verdict}"
        )
    print(summary_text)

    if computed_verdict == "reject":
        return EXIT_VERDICT_REJECT
    if computed_verdict == "request_changes":
        return EXIT_VERDICT_REQUEST_CHANGES
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
