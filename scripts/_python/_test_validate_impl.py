"""Stage 5 verification: 14 fixture cases for validate_impl.py exit codes 0..13.

Runs from Orchestrator root: `python scripts/_python/_test_validate_impl.py`.

Each case builds a throwaway task_root + fake path_local (real git repo)
+ fake gitea bare + fake session.jsonl dir + fake orchestrator_root
under a tempdir, runs validate_impl.py against it, asserts exit code.
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
VALIDATE_PY = ROOT / "scripts/_python/validate_impl.py"

TASK_ID = "2026-05-22-test-99"
PROJECT_ID = "fixture"
DELIV_PATH = "src/Catalogs/Counterparties/Ext/Module.bsl"


def _run_git(args: list[str], cwd: Path, env: dict | None = None) -> tuple[int, str]:
    e = dict(os.environ)
    e.setdefault("GIT_AUTHOR_NAME", "Fixture")
    e.setdefault("GIT_AUTHOR_EMAIL", "fixture@local")
    e.setdefault("GIT_COMMITTER_NAME", "Fixture")
    e.setdefault("GIT_COMMITTER_EMAIL", "fixture@local")
    if env:
        e.update(env)
    r = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        env=e,
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _setup_path_local(base: Path, *, push: bool = True, extra_file: str | None = None,
                      commit_subject: str | None = None,
                      bare_setup: bool = True) -> tuple[Path, Path, str, str]:
    """Build a fake path_local with .git, an initial master commit (before_sha),
    a branch orchestrator/<TASK_ID> with one extra commit, and a gitea remote
    pointing at a bare repo. Returns (path_local, gitea_bare, before_sha, after_sha).

    push=False keeps the branch local-only (Gate A exit 5 case).
    extra_file: when set, the branch commit also touches this off-deliverable path.
    commit_subject: override the branch commit subject (omit "orch <id>" to trigger Gate E).
    """
    path_local = base / "path_local_fake"
    path_local.mkdir()
    _run_git(["init", "-q", "-b", "master"], path_local)
    _run_git(["config", "user.name", "Fixture"], path_local)
    _run_git(["config", "user.email", "fixture@local"], path_local)
    (path_local / DELIV_PATH).parent.mkdir(parents=True, exist_ok=True)
    (path_local / DELIV_PATH).write_text("// initial\n", encoding="utf-8")
    _run_git(["add", "-A"], path_local)
    _run_git(["commit", "-q", "-m", "chore: initial"], path_local)
    rc, sha_out = _run_git(["rev-parse", "HEAD"], path_local)
    before_sha = sha_out.strip()

    gitea_bare = base / "gitea_bare.git"
    if bare_setup:
        _run_git(["init", "-q", "--bare", str(gitea_bare)], base)
        # On Windows file:// URLs use forward-slash paths.
        gitea_url = "file:///" + str(gitea_bare).replace("\\", "/").lstrip("/")
        _run_git(["remote", "add", "gitea", gitea_url], path_local)
        _run_git(["push", "-q", "gitea", "master"], path_local)

    branch = f"orchestrator/{TASK_ID}"
    _run_git(["checkout", "-q", "-b", branch], path_local)
    (path_local / DELIV_PATH).write_text("// implementer edit\n", encoding="utf-8")
    if extra_file:
        out_path = path_local / extra_file
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("// out-of-scope edit\n", encoding="utf-8")
    _run_git(["add", "-A"], path_local)
    subj = commit_subject if commit_subject is not None else f"feat(orch {TASK_ID}): apply stage 1"
    _run_git(["commit", "-q", "-m", subj], path_local)
    rc, sha_out = _run_git(["rev-parse", "HEAD"], path_local)
    after_sha = sha_out.strip()

    if push and bare_setup:
        _run_git(["push", "-q", "gitea", branch], path_local)

    return path_local, gitea_bare, before_sha, after_sha


def _setup_orchestrator_root(base: Path, *, bleed: bool = False) -> Path:
    """Build a fake orchestrator_root with `.git` and a tasks/<id>/ subdir.

    bleed=True adds an untracked file OUTSIDE tasks/<id>/ to trigger Gate B.
    """
    orch = base / "orchestrator_root_fake"
    orch.mkdir()
    _run_git(["init", "-q", "-b", "master"], orch)
    _run_git(["config", "user.name", "Fixture"], orch)
    _run_git(["config", "user.email", "fixture@local"], orch)
    (orch / "tasks" / TASK_ID).mkdir(parents=True)
    (orch / "tasks" / TASK_ID / ".keep").write_text("", encoding="utf-8")
    (orch / "README.md").write_text("# fixture\n", encoding="utf-8")
    _run_git(["add", "-A"], orch)
    _run_git(["commit", "-q", "-m", "init"], orch)
    if bleed:
        (orch / "docs").mkdir(exist_ok=True)
        (orch / "docs" / "out-of-scope.md").write_text("oops\n", encoding="utf-8")
    return orch


def _setup_session_dir(base: Path, *, analyst_mcp: int = 2, writer_mcp: int = 2,
                       impl_mcp: int = 2) -> tuple[Path, float, float]:
    """Create fake session_dir with 3 jsonls (analyst/writer/impl) by mtime.
    Returns (session_dir, writer_cutoff_ts, impl_cutoff_ts).
    """
    session_dir = base / "fake_session"
    session_dir.mkdir()
    analyst = session_dir / "analyst-uuid.jsonl"
    writer = session_dir / "writer-uuid.jsonl"
    impl = session_dir / "impl-uuid.jsonl"

    def line_mcp(name: str) -> str:
        return json.dumps(
            {"message": {"content": [{"type": "tool_use", "name": name, "input": {}}]}}
        )

    def line_bash() -> str:
        return json.dumps(
            {"message": {"content": [{"type": "tool_use", "name": "Bash", "input": {}}]}}
        )

    def write(p: Path, count: int) -> None:
        if count > 0:
            lines = [line_mcp(f"mcp__server__t_{i}") for i in range(count)]
        else:
            lines = [line_bash()]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    write(analyst, analyst_mcp)
    write(writer, writer_mcp)
    write(impl, impl_mcp)

    now = time.time()
    a_t = now - 3000
    w_t = now - 2000
    i_t = now - 1000
    os.utime(analyst, (a_t, a_t))
    os.utime(writer, (w_t, w_t))
    os.utime(impl, (i_t, i_t))

    writer_cutoff = a_t + 500
    impl_cutoff = w_t + 500
    return session_dir, writer_cutoff, impl_cutoff


def _valid_sdd_metadata() -> dict:
    return {
        "schema_version": "v1",
        "task_id": TASK_ID,
        "analysis_report_ref": "analysis_report.json",
        "sdd_path": "sdd.md",
        "task_size": "M",
        "stages": [
            {
                "id": "Stage 1",
                "title": "Modify Counterparties",
                "deliverables": [{"path": DELIV_PATH, "description": "single in-scope file"}],
                "verifications": ["cf-validate"],
                "failure_modes": ["mcp timeout"],
            }
        ],
        "open_questions": [],
        "risks": [],
        "refusals": [],
        "dod_pre": ["pre-cond"],
        "dod_post": ["post-cond"],
        "ff_self_audit": {
            "FF1": {"status": "pass", "note": "tagged"},
            "FF2": {"status": "na", "note": "n/a"},
            "FF3": {"status": "pass", "note": "covered"},
            "FF4": {"status": "pass", "note": "MCP queried"},
            "FF5": {"status": "pass", "note": "dangerous documented"},
            "FF6": {"status": "pass", "note": "honor flagged"},
            "FF7": {"status": "pass", "note": "DoD split"},
            "FF8": {"status": "na", "note": "no grep in fixture dod_post"},
        },
        "citations_used": [
            {"source": "code", "ref": "src/x.bsl:L1"}
        ],
        "self_review_notes": "fixture",
    }


def _valid_impl_metadata(before_sha: str, after_sha: str, path_local: Path) -> dict:
    return {
        "schema_version": "v1",
        "task_id": TASK_ID,
        "sdd_metadata_ref": "sdd_metadata.json",
        "sdd_ref": "sdd.md",
        "project_id": PROJECT_ID,
        "path_local": str(path_local).replace("\\", "/"),
        "gitea_remote_url": "http://<gitea-host>:3000/admin/fixture.git",
        "branch_name": f"orchestrator/{TASK_ID}",
        "commits": [
            {
                "sha": after_sha,
                "subject": f"feat(orch {TASK_ID}): apply stage 1",
                "files": [DELIV_PATH],
                "stage_ref": "Stage 1",
            }
        ],
        "files_changed": [DELIV_PATH],
        "validations_attempted": [
            {"name": "cf-validate", "status": "ok", "diagnostic": "ok", "mandatory": True}
        ],
        "open_questions": [],
        "refusals": [],
        "diff_baseline": {
            "before_sha": before_sha,
            "after_branch_sha": after_sha,
            "orchestrator_before": "",
            "orchestrator_after": "",
        },
        "ff_self_audit": {
            "FF1": {"status": "pass", "note": "tagged"},
            "FF2": {"status": "na", "note": "n/a"},
            "FF3": {"status": "pass", "note": "covered"},
            "FF4": {"status": "pass", "note": "MCP queried at write-time"},
            "FF5": {"status": "pass", "note": "branch isolation"},
            "FF6": {"status": "pass", "note": "honor flagged"},
            "FF7": {"status": "pass", "note": "DoD"},
            "FF8": {"status": "na", "note": "no grep in fixture dod_post"},
        },
        "citations_used": [
            {"source": "sdd_metadata", "ref": "sdd_metadata.json#stages.0"}
        ],
        "status": "ready",
        "failures": [],
        "audit_inputs": [f"orchestrator/{TASK_ID}@{after_sha[:12]}"],
        "self_review_notes": "fixture",
    }


def _write_packets(task_root: Path, session_dir: Path,
                   writer_cutoff: float, impl_cutoff: float,
                   orch_porcelain_baseline: list[str] | None = None) -> None:
    task_root.mkdir(exist_ok=True)
    w_iso = _dt.datetime.fromtimestamp(writer_cutoff, tz=_dt.timezone.utc).isoformat()
    i_iso = _dt.datetime.fromtimestamp(impl_cutoff, tz=_dt.timezone.utc).isoformat()
    (task_root / "sdd_writer_packet.json").write_text(
        json.dumps({
            "task_id": TASK_ID,
            "analyst_session_dir": str(session_dir),
            "created_at": w_iso,
        }),
        encoding="utf-8",
    )
    (task_root / "implementer_packet.json").write_text(
        json.dumps({
            "task_id": TASK_ID,
            "session_dir": str(session_dir),
            "created_at": i_iso,
            "orch_porcelain_baseline": list(orch_porcelain_baseline or []),
        }),
        encoding="utf-8",
    )


def _setup_happy(tmp: Path,
                 *,
                 push: bool = True,
                 analyst_mcp: int = 2,
                 writer_mcp: int = 2,
                 impl_mcp: int = 2,
                 extra_file: str | None = None,
                 commit_subject: str | None = None,
                 orch_bleed: bool = False,
                 orch_porcelain_baseline: list[str] | None = None,
                 mutate_impl_metadata=None,
                 omit_impl_metadata: bool = False,
                 write_bad_impl_metadata: str | None = None,
                 mutate_sdd_metadata=None):
    """Build a full happy-path fixture. Optional mutations override specific
    parts to trigger non-zero exits.
    """
    path_local, gitea, before_sha, after_sha = _setup_path_local(
        tmp, push=push, extra_file=extra_file, commit_subject=commit_subject
    )
    orch_root = _setup_orchestrator_root(tmp, bleed=orch_bleed)
    session_dir, w_cut, i_cut = _setup_session_dir(
        tmp,
        analyst_mcp=analyst_mcp,
        writer_mcp=writer_mcp,
        impl_mcp=impl_mcp,
    )

    task_root = tmp / "task"
    task_root.mkdir()
    sdd = _valid_sdd_metadata()
    if mutate_sdd_metadata:
        mutate_sdd_metadata(sdd)
    (task_root / "sdd_metadata.json").write_text(
        json.dumps(sdd), encoding="utf-8"
    )

    if not omit_impl_metadata:
        if write_bad_impl_metadata is not None:
            (task_root / "impl_metadata.json").write_text(
                write_bad_impl_metadata, encoding="utf-8"
            )
        else:
            impl = _valid_impl_metadata(before_sha, after_sha, path_local)
            if mutate_impl_metadata:
                mutate_impl_metadata(impl)
            (task_root / "impl_metadata.json").write_text(
                json.dumps(impl), encoding="utf-8"
            )

    _write_packets(task_root, session_dir, w_cut, i_cut, orch_porcelain_baseline)
    return task_root, orch_root


def _run(task_root: Path, orch_root: Path) -> int:
    env = dict(os.environ)
    env["ORCH_TEST_ORCHESTRATOR_ROOT"] = str(orch_root)
    r = subprocess.run(
        [sys.executable, str(VALIDATE_PY), str(task_root)],
        capture_output=True,
        text=True,
        env=env,
    )
    return r.returncode


# ---- Case constructors ----

def case_a(tmp):
    return _setup_happy(tmp)


def case_b_pydantic(tmp):
    return _setup_happy(
        tmp, mutate_impl_metadata=lambda m: m.__delitem__("self_review_notes")
    )


def case_c_no_metadata(tmp):
    return _setup_happy(tmp, omit_impl_metadata=True)


def case_d_task_id_mismatch(tmp):
    return _setup_happy(
        tmp,
        mutate_impl_metadata=lambda m: m.update({"task_id": "other-task-id-2099"}),
    )


def case_e_unparseable(tmp):
    return _setup_happy(tmp, write_bad_impl_metadata="not json{")


def case_f_branch_not_pushed(tmp):
    return _setup_happy(tmp, push=False)


def case_g_analyst_zero_mcp(tmp):
    return _setup_happy(tmp, analyst_mcp=0)


def case_h_writer_zero_mcp(tmp):
    return _setup_happy(tmp, writer_mcp=0)


def case_i_impl_zero_mcp(tmp):
    return _setup_happy(tmp, impl_mcp=0)


def case_j_out_of_scope_file(tmp):
    return _setup_happy(tmp, extra_file="src/OOPS/out_of_scope.bsl")


def case_k_orch_bleed(tmp):
    return _setup_happy(tmp, orch_bleed=True)


def case_l_commit_no_orch(tmp):
    return _setup_happy(tmp, commit_subject="feat: missing orch tag")


def case_m_ff_fail(tmp):
    def mut(m):
        m["ff_self_audit"]["FF4"] = {
            "status": "fail",
            "note": "writer issued 0 MCP queries",
        }
    return _setup_happy(tmp, mutate_impl_metadata=mut)


def case_n_status_needs_revision(tmp):
    def mut(m):
        m["status"] = "needs_revision"
        m["failures"] = ["cf-validate failed"]
    return _setup_happy(tmp, mutate_impl_metadata=mut)


def case_o_baseline_absorbs_bleed(tmp):
    # Same setup as case_k (orch_bleed=True creates an untracked file
    # outside tasks/<id>/) BUT implementer_packet.orch_porcelain_baseline
    # already lists that exact porcelain line, so Gate B should absorb it
    # and return 0 instead of 10. git status --porcelain renders the
    # untracked nested dir as `?? docs/` (not the inner file path).
    return _setup_happy(
        tmp,
        orch_bleed=True,
        orch_porcelain_baseline=["?? docs/"],
    )


def _setup_split_target(tmp: Path, *, push: bool = True, push_remote: str = "origin"):
    """Build a split-mirror fixture: path_local is an inert dir (NOT a git
    repo), extra_writable_dir is the real git repo with `push_remote` remote.

    Mirrors the example-erp / example-trade convention where path_local points at the
    read-only XML mirror used by codemetadata MCP and extra_writable_dir
    points at the hand-maintained source with its own Gitea remote.
    push=False keeps the branch local-only (Gate A exit 5).
    push_remote="origin" exercises the gitea -> origin fallback in
    validate_impl Gate A.
    """
    path_local = tmp / "path_local_inert"
    path_local.mkdir()
    (path_local / ".keep").write_text("inert XML mirror\n", encoding="utf-8")

    git_target = tmp / "extra_writable_dir_real"
    git_target.mkdir()
    _run_git(["init", "-q", "-b", "master"], git_target)
    _run_git(["config", "user.name", "Fixture"], git_target)
    _run_git(["config", "user.email", "fixture@local"], git_target)
    (git_target / DELIV_PATH).parent.mkdir(parents=True, exist_ok=True)
    (git_target / DELIV_PATH).write_text("// initial\n", encoding="utf-8")
    _run_git(["add", "-A"], git_target)
    _run_git(["commit", "-q", "-m", "chore: initial"], git_target)
    rc, sha_out = _run_git(["rev-parse", "HEAD"], git_target)
    before_sha = sha_out.strip()

    gitea_bare = tmp / "gitea_bare_split.git"
    _run_git(["init", "-q", "--bare", str(gitea_bare)], tmp)
    gitea_url = "file:///" + str(gitea_bare).replace("\\", "/").lstrip("/")
    _run_git(["remote", "add", push_remote, gitea_url], git_target)
    _run_git(["push", "-q", push_remote, "master"], git_target)

    branch = f"orchestrator/{TASK_ID}"
    _run_git(["checkout", "-q", "-b", branch], git_target)
    (git_target / DELIV_PATH).write_text("// implementer edit\n", encoding="utf-8")
    _run_git(["add", "-A"], git_target)
    _run_git(["commit", "-q", "-m", f"feat(orch {TASK_ID}): apply stage 1"], git_target)
    rc, sha_out = _run_git(["rev-parse", "HEAD"], git_target)
    after_sha = sha_out.strip()
    if push:
        _run_git(["push", "-q", push_remote, branch], git_target)

    return path_local, git_target, before_sha, after_sha


def _setup_split_fixture(tmp: Path, *, push: bool = True, push_remote: str = "origin"):
    path_local, git_target, before_sha, after_sha = _setup_split_target(
        tmp, push=push, push_remote=push_remote
    )
    orch_root = _setup_orchestrator_root(tmp, bleed=False)
    session_dir, w_cut, i_cut = _setup_session_dir(tmp)
    task_root = tmp / "task"
    task_root.mkdir()
    (task_root / "sdd_metadata.json").write_text(
        json.dumps(_valid_sdd_metadata()), encoding="utf-8"
    )
    impl = _valid_impl_metadata(before_sha, after_sha, path_local)
    impl["extra_writable_dir"] = str(git_target).replace("\\", "/")
    (task_root / "impl_metadata.json").write_text(
        json.dumps(impl), encoding="utf-8"
    )
    _write_packets(task_root, session_dir, w_cut, i_cut)
    return task_root, orch_root


def case_p_split_origin_pushed(tmp):
    return _setup_split_fixture(tmp, push=True, push_remote="origin")


def case_q_split_origin_not_pushed(tmp):
    return _setup_split_fixture(tmp, push=False, push_remote="origin")


def case_r_split_gitea_named_remote(tmp):
    return _setup_split_fixture(tmp, push=True, push_remote="gitea")


CASES = [
    ("(a) full happy path -> 0", 0, case_a),
    ("(b) drop required field self_review_notes -> 1 (pydantic)", 1, case_b_pydantic),
    ("(c) impl_metadata.json absent -> 2", 2, case_c_no_metadata),
    ("(d) task_id != sdd_metadata.task_id -> 3", 3, case_d_task_id_mismatch),
    ("(e) impl_metadata.json unparseable -> 4", 4, case_e_unparseable),
    ("(f) branch local-only, not pushed -> 5 (Gate A)", 5, case_f_branch_not_pushed),
    ("(g) analyst session 0 mcp__ -> 6", 6, case_g_analyst_zero_mcp),
    ("(h) writer session 0 mcp__ -> 7", 7, case_h_writer_zero_mcp),
    ("(i) implementer session 0 mcp__ -> 8", 8, case_i_impl_zero_mcp),
    ("(j) file changed in branch not in deliverables -> 9 (Gate D)", 9, case_j_out_of_scope_file),
    ("(k) orchestrator-side change outside tasks/<id>/ -> 10 (Gate B)", 10, case_k_orch_bleed),
    ("(l) commit subject without 'orch <task_id>' -> 11 (Gate E)", 11, case_l_commit_no_orch),
    ("(m) ff_self_audit.FF4.status=fail -> 12", 12, case_m_ff_fail),
    ("(n) status=needs_revision -> 13", 13, case_n_status_needs_revision),
    ("(o) Gate B bleed absorbed by orch_porcelain_baseline -> 0", 0, case_o_baseline_absorbs_bleed),
    ("(p) split path_local + extra_writable_dir, pushed via 'origin' -> 0", 0, case_p_split_origin_pushed),
    ("(q) split, branch not pushed -> 5 (Gate A on git_target_dir)", 5, case_q_split_origin_not_pushed),
    ("(r) split, branch pushed via 'gitea'-named remote -> 0", 0, case_r_split_gitea_named_remote),
]


def _case(name: str, expected: int, setup_fn) -> bool:
    with tempfile.TemporaryDirectory() as tmpdir:
        task_root, orch_root = setup_fn(Path(tmpdir))
        actual = _run(task_root, orch_root)
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
