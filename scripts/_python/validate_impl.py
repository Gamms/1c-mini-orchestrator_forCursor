"""Validate implementer output for a given task_root.

Usage:
    python scripts/_python/validate_impl.py <task_root>

Exit codes (per Phase 3 SDD section 5.5.1):
    0  OK; summary printed to stdout
    1  impl_metadata.json Pydantic schema validation failed
    2  impl_metadata.json absent at task_root (Gate C)
    3  impl_metadata.task_id != sdd_metadata.task_id
    4  impl_metadata.json present but JSON not parseable
    5  Gate A: branch orchestrator/<task_id> not present locally OR not pushed to gitea
    6  analyst session.jsonl shows 0 tool_use entries matching ^mcp__
    7  writer session.jsonl shows 0 tool_use entries matching ^mcp__
    8  implementer session.jsonl shows 0 tool_use entries matching ^mcp__
    9  Gate D: file changed in branch is NOT in sdd_metadata.stages[*].deliverables
   10  Gate B: Orchestrator/ has changes outside tasks/<task_id>/
   11  Gate E: commit in branch missing `orch <task_id>` substring
   12  ff_self_audit.<FFi>.status == "fail" for any FFi
   13  impl_metadata.status != "ready" (needs_revision / blocked)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydantic import ValidationError  # noqa: E402

from schemas.impl_v1 import ImplementationResult  # noqa: E402
from _session_jsonl import (  # noqa: E402
    count_mcp_in_jsonls,
    parse_iso,
    partition_jsonls_3way,
)


EXIT_OK = 0
EXIT_PYDANTIC = 1
EXIT_NO_METADATA = 2
EXIT_TASK_ID_MISMATCH = 3
EXIT_METADATA_PARSE = 4
EXIT_GATE_A_BRANCH = 5
EXIT_ANALYST_NO_MCP = 6
EXIT_WRITER_NO_MCP = 7
EXIT_IMPL_NO_MCP = 8
EXIT_GATE_D_OUT_OF_SCOPE = 9
EXIT_GATE_B_ORCH_BLEED = 10
EXIT_GATE_E_COMMIT_MSG = 11
EXIT_FF_FAIL = 12
EXIT_STATUS_NOT_READY = 13


def _git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    r = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
    )
    return r.returncode, r.stdout, r.stderr


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def _decode_git_path(path: str) -> str:
    """Normalize git --name-only lines (quoted paths, octal UTF-8 escapes on Windows)."""
    p = path.strip().strip('"')
    out = bytearray()
    i = 0
    while i < len(p):
        if (
            p[i] == "\\"
            and i + 3 < len(p)
            and all(c in "01234567" for c in p[i + 1 : i + 4])
        ):
            out.append(int(p[i + 1 : i + 4], 8))
            i += 4
        else:
            out.extend(p[i].encode("ascii"))
            i += 1
    return _norm(out.decode("utf-8"))


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


def _summary(
    meta: ImplementationResult,
    analyst_mcp: int,
    writer_mcp: int,
    impl_mcp: int,
) -> str:
    val_by_status = {"ok": 0, "fail": 0, "skipped": 0, "unavailable": 0}
    mandatory_ok = 0
    for v in meta.validations_attempted:
        val_by_status[v.status] = val_by_status.get(v.status, 0) + 1
        if v.mandatory and v.status == "ok":
            mandatory_ok += 1
    oq_by_sev = {"info": 0, "decision": 0, "blocker": 0}
    for q in meta.open_questions:
        oq_by_sev[q.severity] = oq_by_sev.get(q.severity, 0) + 1
    audit = {k: meta.ff_self_audit[k].status for k in sorted(meta.ff_self_audit)}
    lines = [
        f"OK task_id={meta.task_id}",
        f"  project_id={meta.project_id}",
        f"  branch_name={meta.branch_name}",
        f"  gitea_remote_url={meta.gitea_remote_url}",
        f"  before_sha={meta.diff_baseline.before_sha}",
        f"  after_branch_sha={meta.diff_baseline.after_branch_sha}",
        f"  commits={len(meta.commits)}",
        f"  files_changed={len(meta.files_changed)}",
        f"  validations_attempted={val_by_status} mandatory_ok={mandatory_ok}",
        f"  open_questions={oq_by_sev}",
        f"  refusals={len(meta.refusals)}",
        f"  audit_inputs={len(meta.audit_inputs)}",
        f"  citations_used={len(meta.citations_used)}",
        f"  ff_self_audit={audit}",
        f"  analyst_session_mcp_tool_use={analyst_mcp}",
        f"  writer_session_mcp_tool_use={writer_mcp}",
        f"  implementer_session_mcp_tool_use={impl_mcp}",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_impl.py <task_root>", file=sys.stderr)
        return EXIT_NO_METADATA

    task_root = Path(argv[1]).resolve()
    impl_meta_path = task_root / "impl_metadata.json"
    sdd_meta_path = task_root / "sdd_metadata.json"
    impl_packet_path = task_root / "implementer_packet.json"
    writer_packet_path = task_root / "sdd_writer_packet.json"

    # exit 2: no impl_metadata.json (Gate C)
    if not impl_meta_path.exists():
        print(
            f"implementer did not produce impl_metadata.json at {impl_meta_path}",
            file=sys.stderr,
        )
        return EXIT_NO_METADATA

    # exit 4: not parseable
    try:
        raw = impl_meta_path.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(
            f"impl_metadata.json JSONDecodeError at line {exc.lineno} col {exc.colno}: {exc.msg}",
            file=sys.stderr,
        )
        return EXIT_METADATA_PARSE

    # exit 1: pydantic
    try:
        meta = ImplementationResult.model_validate(data)
    except ValidationError as exc:
        print("impl_metadata Pydantic ValidationError:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return EXIT_PYDANTIC

    # exit 3: task_id mismatch with sdd_metadata
    sdd_meta_data: dict = {}
    if sdd_meta_path.exists():
        try:
            sdd_meta_data = json.loads(sdd_meta_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            sdd_meta_data = {}
    sdd_task_id = sdd_meta_data.get("task_id", "") if isinstance(sdd_meta_data, dict) else ""
    if sdd_task_id and meta.task_id != sdd_task_id:
        print(
            f"task_id mismatch: impl_metadata.task_id={meta.task_id!r} != "
            f"sdd_metadata.task_id={sdd_task_id!r}",
            file=sys.stderr,
        )
        return EXIT_TASK_ID_MISMATCH

    # exit 12: ff_self_audit fails
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

    # exit 13: status != "ready"
    if meta.status != "ready":
        print(
            f"impl_metadata.status={meta.status!r}; "
            f"failures={meta.failures}; "
            f"open_questions(blocker)="
            f"{[q.id for q in meta.open_questions if q.severity == 'blocker']}",
            file=sys.stderr,
        )
        return EXIT_STATUS_NOT_READY

    # ---- Git-touching gates operate on git_target_dir from implementer_packet ----
    # When meta.extra_writable_dir is set, the implementer git-pushes from
    # extra_writable_dir (real impl repo) while path_local stays the XML
    # mirror used by codemetadata MCP. Gates A/D/E therefore must operate
    # on the "git target": extra_writable_dir when non-empty, else path_local.
    git_target_dir = Path(meta.extra_writable_dir) if (meta.extra_writable_dir or "").strip() else Path(meta.path_local)
    branch = meta.branch_name
    before_sha = meta.diff_baseline.before_sha

    # exit 5: Gate A -- branch exists locally AND pushed to gitea
    rc, _, err = _git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], git_target_dir)
    if rc != 0:
        print(
            f"Gate A: local branch {branch!r} not present in {git_target_dir}: {err.strip()}",
            file=sys.stderr,
        )
        return EXIT_GATE_A_BRANCH
    # Remote name convention: `gitea` for projects without extra_writable_dir
    # (path_local IS the impl repo, has a named `gitea` remote per
    # spawn-implementer.ps1 pre-check 4). For extra_writable_dir-using
    # projects (example-erp / example-trade), the impl repo's only remote is `origin` -> Gitea.
    # Try `gitea` first, fall back to `origin`.
    rc, out, err = _git(["ls-remote", "gitea", f"refs/heads/{branch}"], git_target_dir)
    if rc != 0:
        rc, out, err = _git(["ls-remote", "origin", f"refs/heads/{branch}"], git_target_dir)
    if rc != 0 or not out.strip():
        print(
            f"Gate A: branch {branch!r} not pushed to gitea/origin "
            f"(ls-remote rc={rc}, stdout={out!r}, stderr={err.strip()!r})",
            file=sys.stderr,
        )
        return EXIT_GATE_A_BRANCH

    # ---- Session.jsonl gates 6/7/8 (cursor: impl_raw / analysis_raw / sdd_raw) ----
    runtime = _packet_runtime(
        impl_packet_path,
        writer_packet_path,
        task_root / "task_packet.json",
    )
    analyst_mcp = 0
    writer_mcp = 0
    impl_mcp = 0
    orch_porcelain_baseline: set[str] = set()
    if impl_packet_path.exists():
        try:
            ip = json.loads(impl_packet_path.read_text(encoding="utf-8-sig"))
            for ln in ip.get("orch_porcelain_baseline") or []:
                if isinstance(ln, str) and ln.strip():
                    orch_porcelain_baseline.add(ln.rstrip())
        except json.JSONDecodeError:
            pass

    if runtime == "cursor":
        analyst_mcp = _count_cursor_mcp_raw(task_root, "analysis_raw")
        writer_mcp = _count_cursor_mcp_raw(task_root, "sdd_raw")
        impl_mcp = _count_cursor_mcp_raw(task_root, "impl_raw")
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
                "cursor runtime: impl_raw/ has no MCP evidence -- implementer did not consult MCP",
                file=sys.stderr,
            )
            return EXIT_IMPL_NO_MCP
    else:
        session_dir = ""
        writer_cutoff_ts: float | None = None
        impl_cutoff_ts: float | None = None

        if impl_packet_path.exists():
            try:
                ip = json.loads(impl_packet_path.read_text(encoding="utf-8-sig"))
                session_dir = ip.get("session_dir", "") or ""
                impl_cutoff_ts = parse_iso(ip.get("created_at", "") or "")
            except json.JSONDecodeError:
                pass

        if writer_packet_path.exists():
            try:
                wp = json.loads(writer_packet_path.read_text(encoding="utf-8-sig"))
                if not session_dir:
                    session_dir = wp.get("analyst_session_dir", "") or ""
                writer_cutoff_ts = parse_iso(wp.get("created_at", "") or "")
            except json.JSONDecodeError:
                pass

        if not session_dir or not Path(session_dir).exists():
            print(
                "session.jsonl dir not found (implementer_packet.session_dir / "
                "sdd_writer_packet.analyst_session_dir both missing or cleared) -- "
                "cannot verify real-MCP gates 6/7/8",
                file=sys.stderr,
            )
            return EXIT_ANALYST_NO_MCP

        analyst_files, writer_files, impl_files = partition_jsonls_3way(
            Path(session_dir), writer_cutoff_ts, impl_cutoff_ts
        )

        if not analyst_files:
            print(
                f"no analyst session.jsonl found in {session_dir} "
                f"(writer_cutoff_ts={writer_cutoff_ts}, impl_cutoff_ts={impl_cutoff_ts})",
                file=sys.stderr,
            )
            return EXIT_ANALYST_NO_MCP
        analyst_mcp = count_mcp_in_jsonls(analyst_files)
        if analyst_mcp == 0:
            print(
                f"input analysis was synthesized without real MCP "
                f"(0 mcp__ tool_use entries in {[str(p) for p in analyst_files]})",
                file=sys.stderr,
            )
            return EXIT_ANALYST_NO_MCP

        if not writer_files:
            print(
                f"no writer session.jsonl found in {session_dir}",
                file=sys.stderr,
            )
            return EXIT_WRITER_NO_MCP
        writer_mcp = count_mcp_in_jsonls(writer_files)
        if writer_mcp == 0:
            print(
                f"sdd_writer did not consult MCP "
                f"(0 mcp__ tool_use entries in {[str(p) for p in writer_files]})",
                file=sys.stderr,
            )
            return EXIT_WRITER_NO_MCP

        if not impl_files:
            print(
                f"no implementer session.jsonl found in {session_dir}",
                file=sys.stderr,
            )
            return EXIT_IMPL_NO_MCP
        impl_mcp = count_mcp_in_jsonls(impl_files)
        if impl_mcp == 0:
            print(
                f"implementer did not consult MCP "
                f"(0 mcp__ tool_use entries in {[str(p) for p in impl_files]})",
                file=sys.stderr,
            )
            return EXIT_IMPL_NO_MCP

    # ---- Gate D: every file changed in branch must be in sdd_metadata.stages[*].deliverables ----
    rc, out, err = _git(
        ["diff", "--name-only", f"{before_sha}..refs/heads/{branch}"],
        git_target_dir,
    )
    if rc != 0:
        print(
            f"Gate D: git diff failed in {git_target_dir}: rc={rc} stderr={err.strip()!r}",
            file=sys.stderr,
        )
        return EXIT_GATE_D_OUT_OF_SCOPE
    branch_changed = {_decode_git_path(p) for p in out.splitlines() if p.strip()}

    deliverables_union: set[str] = set()
    stages = sdd_meta_data.get("stages") if isinstance(sdd_meta_data, dict) else None
    if isinstance(stages, list):
        for st in stages:
            if not isinstance(st, dict):
                continue
            for d in st.get("deliverables") or []:
                if isinstance(d, dict):
                    path = d.get("path")
                    if isinstance(path, str) and path.strip():
                        deliverables_union.add(_norm(path))
    out_of_scope = sorted(p for p in branch_changed if p not in deliverables_union)
    if out_of_scope:
        print(
            "Gate D: files changed in branch not in sdd_metadata.stages[*].deliverables:\n  "
            + "\n  ".join(out_of_scope),
            file=sys.stderr,
        )
        return EXIT_GATE_D_OUT_OF_SCOPE

    # ---- Gate B: Orchestrator/ has changes outside tasks/<task_id>/ ----
    # Test-time override: validate_impl normally inspects the real
    # Orchestrator working tree (ROOT). Tests set ORCH_TEST_ORCHESTRATOR_ROOT
    # to a throwaway repo so Gate B can be exercised in isolation.
    orch_root_env = os.environ.get("ORCH_TEST_ORCHESTRATOR_ROOT", "")
    orchestrator_root = Path(orch_root_env) if orch_root_env else ROOT
    rc, out, err = _git(["status", "--porcelain"], orchestrator_root)
    if rc != 0:
        print(
            f"Gate B: orchestrator-side git status failed: rc={rc} stderr={err.strip()!r}",
            file=sys.stderr,
        )
        return EXIT_GATE_B_ORCH_BLEED
    task_prefix = f"tasks/{meta.task_id}/"
    offending = []
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
            "and not in implementer_packet.orch_porcelain_baseline:\n  "
            + "\n  ".join(offending),
            file=sys.stderr,
        )
        return EXIT_GATE_B_ORCH_BLEED

    # ---- Gate E: every commit subject must contain `orch <task_id>` substring ----
    needle = f"orch {meta.task_id}"
    rc, out, err = _git(
        ["log", "--format=%H%n%s", f"{before_sha}..refs/heads/{branch}"],
        git_target_dir,
    )
    if rc != 0:
        print(
            f"Gate E: git log failed in {git_target_dir}: rc={rc} stderr={err.strip()!r}",
            file=sys.stderr,
        )
        return EXIT_GATE_E_COMMIT_MSG
    lines = [l for l in out.splitlines() if l.strip()]
    pairs = list(zip(lines[0::2], lines[1::2]))
    for sha, subj in pairs:
        if needle not in subj:
            print(
                f"Gate E: commit {sha[:12]} subject missing {needle!r}: {subj!r}",
                file=sys.stderr,
            )
            return EXIT_GATE_E_COMMIT_MSG

    print(_summary(meta, analyst_mcp, writer_mcp, impl_mcp))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
