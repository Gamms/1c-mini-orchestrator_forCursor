# Task AGENTS.md — implementer run (Cursor agent)

You are the **L3 implementer** for this task. This file is the first
thing you read; everything else is named here by absolute path.

## Task

- **Project:** `{PROJECT_ID}`
- **Project source root (path_local):** `{PROJECT_PATH}`
  - codemetadata MCP target. Read-only from the implementer's POV.
- **Git target dir:** `{GIT_TARGET_DIR}`
  - this is the repo you edit, commit, and push. For most projects
    it equals path_local. For split-mirror projects (example-erp / example-trade) it
    equals the project's `extra_writable_dir` from `projects.yaml` —
    the hand-maintained source with its own Gitea remote, separate
    from the XML mirror that path_local points at.
- **Task id:** `{TASK_ID}`
- **Task text (operator goal):**

```
{TASK_TEXT}
```

## Branch contract (HARD)

- Working tree: `{GIT_TARGET_DIR}` (this is the git repo you edit).
- Branch you create: `{BRANCH_NAME}` (must equal `orchestrator/{TASK_ID}`).
- Gitea remote: `{GITEA_REMOTE_URL}` (push target for the branch;
  resolved to the named remote `{GITEA_REMOTE_NAME}` inside
  `{GIT_TARGET_DIR}`).
- Every commit subject must contain the literal substring
  `orch {TASK_ID}`. validate_impl Gate E (exit 11) refuses any commit
  on the branch without it.
- Forbidden: push to master/main, force-push, branch delete, rebase
  pushed commits, git config, filter-branch, merge to release
  branches. See `{ORCHESTRATOR_ROOT}/prompts/implementer.md` REFUSE
  section for the full list and the FF6 self-audit obligation.

## Input artifacts (from Phases 1+2)

`{TASK_ROOT_ABS}/{SDD_REF}` — the SDD document.
`{TASK_ROOT_ABS}/{SDD_METADATA_REF}` — the Pydantic-validated sidecar
(`SDDMetadata` v1). Schema at `{ORCHESTRATOR_ROOT}/schemas/sdd_v1.py`.

Open BOTH first. Treat `[d.path for d in sdd_metadata.stages[*].deliverables]`
as the file-path scope you are allowed to edit — each `Deliverable`
is `{path, description}` per `schemas/sdd_v1.Deliverable`. Out-of-scope
edits = validate_impl exit 9 (Gate D).

The Phase 1 analyst report
(`{TASK_ROOT_ABS}/analysis_report.json`) is also present; read it for
background but cite via `sdd_metadata.json#...` or `sdd.md#...` in
preference (FF4 — the SDD is your contract, the analysis is the
SDD's basis).

## Mandatory reads (in order, before any MCP call)

1. `{ORCHESTRATOR_ROOT}/prompts/implementer.md` — your phase contract.
2. `{ORCHESTRATOR_ROOT}/docs/writer-forcing-functions.md` — FF1-FF8
   you self-audit against.
3. `{ORCHESTRATOR_ROOT}/docs/phase3-implementer-SDD.md` — the Phase 3
   SDD. Read sections 1, 2, 5, 7, 8, 9.
4. `{ORCHESTRATOR_ROOT}/skills/v3-1c-anti-patterns.md` — FORBIDDEN
   moves for 1C edits.
5. `{ORCHESTRATOR_ROOT}/skills/v3-codemetadata-usage.md` — for FF4
   re-verification of writer claims at write time.
6. `{ORCHESTRATOR_ROOT}/skills/v3-1c-mcp-tools-guide.md` — 1c-MCP
   stack overview.

`v3-naparnik-usage.md` is reference-only in Phase 3 (naparnik not
wired). Do not call naparnik tools.

## Output contract (in `{TASK_ROOT_ABS}/` + branch in `{GIT_TARGET_DIR}`)

- `impl_metadata.json` — structured sidecar matching
  `{ORCHESTRATOR_ROOT}/schemas/impl_v1.py` (`ImplementationResult`).
  All 8 `ff_self_audit` keys (FF1-FF8) required. `branch_name` must
  equal `{BRANCH_NAME}`. Populate `extra_writable_dir` with the
  exact value from `implementer_packet.json` (may be empty string).
- `impl_raw/<server>/r<round>-q<idx>-<sha12>.json` — raw dump per
  fresh MCP call (mirrors `analysis_raw/` and `sdd_raw/`).
- (optional) `scratch/` — never read downstream.
- Branch `{BRANCH_NAME}` in `{GIT_TARGET_DIR}` with one commit per
  implemented stage, pushed to `{GITEA_REMOTE_URL}` via remote name
  `{GITEA_REMOTE_NAME}`.

`{GIT_TARGET_DIR}` is writable (git working tree); edits must stay
within `{d.path for d in sdd_metadata.stages[*].deliverables}`.
`{PROJECT_PATH}` is read-only (codemetadata XML-dump root when it
differs from `{GIT_TARGET_DIR}`).
`{ORCHESTRATOR_ROOT}` is read-only except for `{TASK_ROOT_ABS}/`.

## MCP servers for this run

Configured inline by the orchestrator from
`{TASK_ROOT_ABS}/.mcp.implementer.json`. Discover tool names via the
server's `tools/list` on first contact — do NOT name tools from memory.

## Exit signal

When all in-scope SDD stages are committed AND the branch is pushed
AND `impl_metadata.json` is written and re-read for verification,
announce literally on its own line one of:

```
IMPLEMENT READY
```

```
IMPLEMENT NEEDS_REVISION
```

```
IMPLEMENT BLOCKED
```

After the signal, the orchestrator runs
`scripts/validate-impl.ps1 -TaskId {TASK_ID}`.

## What you are NOT doing

- No live database mutation — operator scope.
- No force-push, branch delete, master/main push, rebase pushed
  commits, git config, filter-branch.
- No auto-merge of `{BRANCH_NAME}` into master/main — operator only.
- No edits outside `sdd_metadata.stages[*].deliverables` — Gate D.
- No edits in `{ORCHESTRATOR_ROOT}` outside `{TASK_ROOT_ABS}/` — Gate B.
- No assumptions: if a fact is not cited, it does not exist for you.
