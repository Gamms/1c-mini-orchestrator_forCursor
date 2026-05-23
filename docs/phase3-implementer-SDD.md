# SDD -- Orchestrator, Phase 3: implementer chain

**task_id:** `orch-phase3-implementer-2026-05-22`
**task_size:** L (broader risk surface than Phase 1+2; writes outside `Orchestrator/`; new MCP family; new Stage 8 operator-review gate)
**author:** Claude (L2 in this Orchestrator session, parent of Phase 3 chain)
**date:** 2026-05-22
**status:** draft for operator review

---

## 1. Context and goal

Phase 1 (analyst) shipped 2026-05-22 at `eccd95c`; Phase 2 (sdd_writer) shipped 2026-05-22 at `ed090ef`. Together they produce `tasks/<task_id>/sdd.md` + `tasks/<task_id>/sdd_metadata.json` (schema_sdd_v1). Phase 3 builds the next link: an L3 **implementer** that consumes that SDD and applies it as real edits in the target 1C project under a per-task branch.

**Goal of Phase 3:** implementer only. After it lands, Phase 4 (auditor) opens.

**Out of scope for Phase 3:**
- Auditor pass on the produced branch (Phase 4)
- Rotation / Remote toggle (Phase 5)
- L1 orchestration (always the user)
- Editing Phase 1+2 artifacts unless a contract change is forced (see §10 -- none forced as of this draft)
- New MCP servers beyond codemetadata + the <vm-docker-host> MCP common family (help/ssl/syntax/forms). `1c-skills` family of slash-skills (cfe-*, meta-*, form-*, etc.) are **Skills**, not MCP servers -- they are available to any Claude Code session by default; no .mcp.json wiring needed for them. [VERIFIED via system-reminder skill list in this session + `~/.claude/1c-development-rules.md` §"codemetadata MCP".]
- Live database updates (`db-update` against any 1C base) -- operator-only post-Phase-3-DONE
- Auto-merge of the implementer's branch to master/main of the 1C project -- operator-only via Gitea UI or own session

**Carry-forwards from Phases 1+2:**
- Spawn-per-task in a fresh `wt` tab, file-only L2<->L3 protocol
- Per-task CWD = `tasks/<task_id>/`, rendered `CLAUDE.md` + `.mcp.json` per task (implementer-specific variants)
- `--mcp-config <task>/.mcp.implementer.json --strict-mcp-config` + `--add-dir <path_local>` + `--add-dir <orchestrator_root>`
- Pre-trust both case variants of the encoded path
- `--dangerously-skip-permissions` accepted risk; constrained write contract enforced via prompts + validate_impl Gates A-D, NOT honor-system
- PowerShell 5.1 only, ASCII-only `.ps1` files [VERIFIED via `memory/feedback_powershell_5_1_gotchas.md`]
- path_local INVARIANT (0c): `projects.yaml.path_local` mirrors codemetadata XML index. spawn-implementer.ps1 fail-fasts identically to Phase 1+2 [VERIFIED via `scripts/spawn-sdd-writer.ps1`].
- FF1-FF8 forcing functions per `docs/writer-forcing-functions.md` apply to every artifact produced this phase.

---

## 2. Constraints and decisions

| Constraint | Decision |
|---|---|
| Implementer must read `sdd.md` + `sdd_metadata.json` from prior task root | Pre-check in spawn-implementer.ps1: both files exist AND validate-sdd.ps1 exits 0. Refuse to spawn (exit 5) otherwise [VERIFIED via Phase 2 spawn-sdd-writer.ps1 lines reading analysis_report.json + validate.py output] |
| Implementer must write in `path_local` of the target 1C project | `--add-dir <path_local>` (same pattern as analyst). Crucially, implementer is **expected** to write here (vs analyst's read-only contract) -- the write contract is enforced by Gate B (no writes to `Orchestrator/` outside `tasks/<task_id>/`) and Gate D (every changed file appears in `sdd_metadata.stages[*].deliverables`) -- both code-level, not honor-system |
| Implementer's git operations target the 1C project's repo, not Orchestrator's | All `git` commands in `prompts/implementer.md` and `templates/implementer-CLAUDE.md.tpl` explicitly cd to `<path_local>`. Branch name = `orchestrator/<task_id>` (OQ2). Push target = the `gitea` remote of the 1C project (the spawn script resolves it via `git -C <path_local> remote get-url gitea`, fail-fasts if absent). |
| MCP surface | codemetadata (read, re-verify analyst+writer claims at write time -- FF4 carries forward) + <vm-docker-host> MCP common (help/ssl/syntax/forms -- optional, used only if implementer's prompt detects a relevant subtask). NO `1c-skills` MCP wiring -- those are Skills, available by default to any Claude session. [VERIFIED via system-reminder available-skills list this session] |
| Operational quality gate carry-forward | validate_impl walks ALL THREE session.jsonls (analyst, writer, implementer) and asserts each has >=1 `tool_use.name ~ ^mcp__`. Exit 6 if analyst, exit 7 if writer, exit 8 if implementer. Catches D1-style Bash+curl synthesis at every link in the chain [VERIFIED via RLM fact 0d131b79 finding #5 + Phase 2 SDD §5.1 exit-code table] |
| Output format on Orchestrator side | One file: `tasks/<task_id>/impl_metadata.json` (Pydantic-validated sidecar, schema_impl_v1). No `impl.md` deliverable -- the "writing" output is the branch in the 1C project's git history (diff is the deliverable; readable via `git log` / Gitea web UI). |
| Schema for sidecar | New `schemas/impl_v1.py` -- standalone Pydantic v2, no <prior-iteration> imports, extra="forbid". Mirrors sdd_v1 hygiene. FF2 applies: no inlining from sdd_v1; if Citation shape is reused, it is DUPLICATED, not imported. |
| Where the branch lives long-term | In the 1C project's Gitea repo as a branch `orchestrator/<task_id>`. Operator merges to master/main in Gitea UI (or via own `git` session) after review. Branch is never auto-deleted by Phase 3 tooling. |
| Spawn model: spawn or inline in L2? | **Spawn.** Mirrors Phase 2 decision. Implementer pass is >100k tokens typically (reads sdd.md, drills into each stage, runs MCP queries, makes edits). Would pollute L2 context catastrophically if inline. [DECIDED -- operator may override; see OQ1 below if reconsidering] |
| Wrappers `peek-implementer.ps1` / `kill-implementer.ps1` | Phase-specific copies of Phase 1+2 wrappers. wt window title = `implementer:<task_id>`. Code duplication acknowledged; merging into phase-agnostic `peek-task.ps1`/`kill-task.ps1` is Phase 5 tech-debt cleanup, NOT this phase (FF8: don't refactor beyond what task requires) |
| `--dangerously-skip-permissions` blast radius | Larger than Phases 1+2: implementer is expected to write in `path_local`, so a misbehaving session could mangle the project's source tree. Mitigations: (a) per-task branch in 1C project's git -- nothing lands on master/main without operator merge; (b) Gate B and Gate D in validate_impl catch out-of-scope writes; (c) Stage 6 e2e includes `git status` baseline diff before/after run, recorded in `impl_metadata.diff_baseline`. |
| Retry budget on validate failure | Max 2 retries (same as Phases 1+2). Operator's call to nudge implementer with followup prompt, OR delete branch + redo from analyst, OR accept partial work with `impl_metadata.status = "needs_revision"` |
| Model | Default (Opus, what operator runs). Downgrade to `--model sonnet` only if implementer pass routinely exceeds session budget. Phase 3 tasks may run longer than Phase 2 (more files, more verifications) -- watch budget at Stage 6. |
| Validation steps (cf-validate, cfe-validate, meta-validate, form-validate) | Best-effort. Implementer attempts the validation steps that match SDD's `stages[*].verifications`. Each attempt recorded in `impl_metadata.validations_attempted[]` with `status: ok|fail|skipped|unavailable` + diagnostic. Hard failure of a SDD-listed verification blocks `impl_metadata.status = "ready"` (forces "needs_revision"). |
| Live db-update | REFUSED in Phase 3. `prompts/implementer.md` explicitly forbids running `db-update`, `1c-manage.sh config-partial-load`, or any other live-DB mutation. validate_impl does NOT check for this (out-of-scope file system signal), but the prompt's FF6 self-audit row requires implementer to certify it did not run such commands. |
| Commit message convention | Every commit in `orchestrator/<task_id>` branch must include `orch <task_id>` substring. Convention: `feat(orch <task_id>): <subject>` / `fix(orch <task_id>): <subject>` / `docs(orch <task_id>): <subject>`. Enforced by validate_impl Gate E (NEW). |

---

## 3. Repo layout after Phase 3

```
Orchestrator/
|-- CLAUDE.md                                 # (unchanged) L2 router contract
|-- README.md                                 # (updated) Phase 3 entry points added
|-- projects.yaml                             # (unchanged)
|-- pyproject.toml                            # (unchanged -- pydantic + pyyaml already cover Phase 3)
|-- docs/
|   |-- phase1-analyst-SDD.md                 # (unchanged)
|   |-- audit-phase1.md                       # (unchanged)
|   |-- writer-forcing-functions.md           # (unchanged -- referenced from prompts/implementer.md)
|   |-- phase2-kickoff-brief.md               # (unchanged)
|   |-- phase2-sdd-writer-SDD.md              # (unchanged)
|   |-- phase3-kickoff-brief.md               # (unchanged -- input to this SDD)
|   |-- phase3-implementer-SDD.md             # this document
|   `-- audit-phase3.md                       # NEW (operator-triggered post-Stage-6 if used)
|-- prompts/
|   |-- analyst.md                            # (unchanged)
|   |-- sdd-writer.md                         # (unchanged)
|   `-- implementer.md                        # NEW
|-- skills/                                   # (unchanged -- same 5 skills, implementer reads them too)
|-- schemas/
|   |-- analysis_v2.py                        # (unchanged)
|   |-- sdd_v1.py                             # (unchanged)
|   `-- impl_v1.py                            # NEW -- sidecar contract
|-- templates/
|   |-- analyst-CLAUDE.md.tpl                 # (unchanged)
|   |-- analyst-mcp.json.tpl                  # (unchanged)
|   |-- sdd-writer-CLAUDE.md.tpl              # (unchanged)
|   |-- sdd-writer-mcp.json.tpl               # (unchanged)
|   |-- implementer-CLAUDE.md.tpl             # NEW
|   `-- implementer-mcp.json.tpl              # NEW
|-- scripts/
|   |-- spawn-analyst.ps1                     # (unchanged)
|   |-- _run-analyst.ps1                      # (unchanged)
|   |-- peek-analyst.ps1                      # (unchanged)
|   |-- kill-analyst.ps1                      # (unchanged)
|   |-- validate-analysis.ps1                 # (unchanged)
|   |-- spawn-sdd-writer.ps1                  # (unchanged)
|   |-- _run-sdd-writer.ps1                   # (unchanged)
|   |-- peek-sdd-writer.ps1                   # (unchanged)
|   |-- kill-sdd-writer.ps1                   # (unchanged)
|   |-- validate-sdd.ps1                      # (unchanged)
|   |-- spawn-implementer.ps1                 # NEW
|   |-- _run-implementer.ps1                  # NEW
|   |-- peek-implementer.ps1                  # NEW
|   |-- kill-implementer.ps1                  # NEW
|   |-- validate-impl.ps1                     # NEW
|   |-- _run-smoke.ps1                        # (unchanged)
|   `-- _python/
|       |-- yaml_get.py                       # (unchanged)
|       |-- validate.py                       # (unchanged)
|       |-- validate_sdd.py                   # (unchanged)
|       |-- validate_impl.py                  # NEW -- impl + cross-checks analyst+writer+implementer session.jsonls
|       |-- _test_schema.py                   # (unchanged)
|       |-- _test_templates.py                # (extended -- adds implementer template fixtures)
|       |-- _test_validate.py                 # (unchanged)
|       |-- _test_sdd_schema.py               # (unchanged)
|       |-- _test_validate_sdd.py             # (unchanged)
|       |-- _test_impl_schema.py              # NEW -- impl_v1 fixtures
|       `-- _test_validate_impl.py            # NEW -- exit-code fixtures (10 cases for exits 0-9)
`-- tasks/                                    # (gitignored, unchanged shape)
```

Net NEW files: 11 (2 templates, 1 prompt, 1 schema, 5 ps1, 2 python tests + 1 python validator). Net edits: 2 files (`scripts/_python/_test_templates.py` extends; `README.md` lists new entry points).

**Out-of-Orchestrator-tree net new artifacts (per implementer run):**
- Branch `orchestrator/<task_id>` in the 1C project's Gitea repo, with N commits per SDD stages.
- No file changes anywhere else.

---

## 3.x Docs-only mirror convention (IOQ1=b, 2026-05-22)

Some SDDs target operator-local `tasks/<task_id>/` deliverables only --
e.g. a markdown summary of MCP scan results -- and explicitly forbid
edits in `<path_local>` (the 1C project source tree). The Phase 3
implementer contract nevertheless requires:

- `schemas/impl_v1.py`: `ImplementationResult.commits` `min_length=1`,
  `ImplCommit.files` `min_length=1`, `ImplementationResult.files_changed`
  `min_length=1`.
- `validate_impl.py` Gate A: branch `orchestrator/<task_id>` pushed to
  `<path_local>`'s `gitea` remote.

Two contracts in tension. Resolution (IOQ1=b, operator decision
2026-05-22): the sdd_writer MUST include a sanctioned mirror
deliverable for each operator-local file:

```json
{
  "path": "docs/orchestrator/<task_id>/<basename>",
  "description": "mirror of tasks/<task_id>/<basename> per docs-only convention (Phase 3 SDD §3.x)"
}
```

The implementer then creates ONE mirror commit at
`<path_local>/docs/orchestrator/<task_id>/<basename>` with subject
`docs(orch <task_id>): mirror <basename> per docs-only convention`.

**Rules:**
1. Mirror paths live under `<path_local>/docs/orchestrator/<task_id>/`
   only -- never under `Tasks/` (NTFS case-insensitive collision risk
   with 1C metadata directory `Tasks/<Cyrillic>`) and never under any
   1C-metadata-shaped directory (`src/`, `cf/`, `cfe/`, `ConfigDumpInfo/`).
2. The mirror file content is a byte-for-byte copy of the operator-local
   source. No transformation. No metadata header. The branch reviewer
   compares trivially.
3. The sdd_writer adds the mirror requirement to `dod_post` as well
   (e.g. `"docs/orchestrator/<task_id>/<basename> committed on
   orchestrator/<task_id> branch with subject 'docs(orch <task_id>):
   mirror <basename> per docs-only convention'"`).
4. validate_impl Gate D passes because the mirror path is in
   `deliverables_union` (union of all `Deliverable.path` across
   `stages[*].deliverables`).
5. The convention applies ONLY when SDD has zero deliverables in
   `<path_local>`. SDDs with both operator-local AND path_local
   deliverables do not auto-mirror.

**Why not loosen the schema instead?** Considered and rejected
(IOQ1=c): allowing zero-commit branches would defeat the Phase 3
"branch is the deliverable" model. Gate A (branch pushed to gitea) is
the single piece of objective evidence that the implementer reached
the act stage; making it optional removes the gate.

**Failure modes:**
- sdd_writer forgets the mirror deliverable -> validate_impl Gate D
  fail (exit 9) when implementer commits the mirror anyway.
- implementer mirrors to wrong path (e.g. `Tasks/` capitalised) ->
  Gate D fail (exit 9) on case-sensitive Gitea.
- Mirror file content drifts from source -> no validator catches this;
  operator reviews diff at sign-off.

**Carrying example-erp-02:** the 2026-05-22 example-erp-02 fixture was rejected at
Stage 8 because its sdd_metadata predates this convention. Re-running
example-erp-02 against an updated SDD that adds the mirror deliverable would
produce an exit-0 e2e (Phase 4 follow-up).

---

## 4. End-to-end flow

```
[Operator in this Orchestrator L2 session]
    -> "Реализуй SDD таска 2026-05-22-example-erp-02"
[Claude = L2]
    1. Resolve task_id -> tasks/<task_id>/ on disk
    2. Pre-check: sdd.md AND sdd_metadata.json AND analysis_report.json all exist
       AND validate-sdd.ps1 -TaskId <id> exits 0
       (implementer refuses to start on a non-validated SDD)
    3. Spawn scripts/spawn-implementer.ps1 -TaskId 2026-05-22-example-erp-02
        |-- reads tasks/<task_id>/task_packet.json -> project_id, project_path, etc.
        |-- reads tasks/<task_id>/sdd_writer_packet.json (writer-side metadata) for traceability
        |-- resolves <path_local> via projects.yaml
        |-- resolves gitea remote of <path_local> via `git -C <path_local> remote get-url gitea` (fail-fast if absent)
        |-- pre-check: <path_local> git status clean (no uncommitted changes); fail-fast exit 6 otherwise
        |-- pre-check: <path_local> not currently on orchestrator/<task_id> branch (would mean prior run; require -Force to overwrite)
        |-- renders templates/implementer-CLAUDE.md.tpl -> tasks/<task_id>/CLAUDE.implementer.md
        |-- renders templates/implementer-mcp.json.tpl -> tasks/<task_id>/.mcp.implementer.json
        |-- writes tasks/<task_id>/implementer_packet.json (implementer-side metadata: created_at, wt_window_title, path_local, gitea_remote_url, branch_name)
        |-- writes tasks/<task_id>/prompt.implementer.md
        |-- writes tasks/<task_id>/impl_raw/ directory (analogue of sdd_raw/)
        |-- pre-trusts task_root + orchestrator_root + path_local (all three; idempotent)
        `-- wt.exe -w 0 nt --title "implementer:<task_id>" powershell.exe -File _run-implementer.ps1 ...
[implementer in new wt tab]
    - reads CLAUDE.implementer.md (role + context + branch convention)
    - reads prompts/implementer.md (phase contract; includes FF1-FF8 self-audit + commit conventions)
    - reads tasks/<task_id>/sdd.md (primary input -- design)
    - reads tasks/<task_id>/sdd_metadata.json (secondary input -- machine-readable surface)
    - cd <path_local>
    - git checkout -b orchestrator/<task_id>  (or -B if -Force was passed to spawn)
    - For each SDD stage:
        - Verifies relevant findings via MCP at write-time (codemetadata; FF4 carries forward; dumps to impl_raw/)
        - Makes edits per stage.deliverables (BSL/XML files, possibly via Skill calls like 1c-skills:cfe-borrow)
        - Runs stage.verifications best-effort; records each in impl_metadata.validations_attempted[]
        - Commits: `feat(orch <task_id>): stage <id> -- <title>` (or fix/docs as fits)
    - git push gitea orchestrator/<task_id>
    - writes tasks/<task_id>/impl_metadata.json
    - post-Write Read on impl_metadata.json
    - announces "IMPLEMENT READY" (or "IMPLEMENT NEEDS_REVISION" if a SDD-mandatory verification failed)
[Operator] "готов" or "глянь, что он делает"
[Claude = L2]
    - "готов" -> scripts/validate-impl.ps1 -TaskId X
        |-- Pydantic-validate impl_metadata.json (schema_impl_v1)
        |-- Gate A: branch orchestrator/<task_id> exists in <path_local> git AND pushed to gitea remote
        |-- Gate B: git status in Orchestrator/ clean for files outside tasks/<task_id>/
        |-- Gate C: impl_metadata.json present at task_root
        |-- Gate D: every file changed in branch appears in sdd_metadata.stages[*].deliverables (string match against committed paths)
        |-- Gate E: every commit in branch contains `orch <task_id>` substring in message
        |-- analyst-session real-MCP check (exit 6)
        |-- writer-session real-MCP check (exit 7)
        |-- implementer-session real-MCP check (exit 8)
        `-- if all pass -- exit 0 with summary (counts, gates, validations_attempted breakdown)
    - "глянь" -> scripts/peek-implementer.ps1 -TaskId X
        `-- tail last N events from implementer's session.jsonl + LAST_EVENT_AGO
[Stage 8 -- operator review]
    - Operator opens branch URL in Gitea, reviews diff
    - Optionally writes tasks/<task_id>/operator_signoff.txt with one-line "approved <commit>" or "rejected: <reason>"
    - On approve: operator merges branch in Gitea UI / own git session
    - Phase 3 chain emits `## DONE` (this task is closed); orchestrator next phase begins or chain ends
```

---

## 5. Stages

### Stage 0 -- Spawn-mechanism smoke (mirror Phase 2 Stage 0, scoped to implementer wrapper)

**Goal:** prove that `wt -> powershell -> _run-implementer.ps1 -> claude` works with the planned argument shape BEFORE we author task-specific templates.

**What breaks (FF3):** the implementer wrapper takes a new param set (`-PathLocal`, `-GiteaRemoteUrl` in addition to `-TaskRoot` / `-OrchestratorRoot`). Parameter typo silently breaks Stage 4.

**Steps:**
1. Write `scripts/_run-implementer.ps1` stub that just echoes its four params + path-resolves `sdd.md` and `sdd_metadata.json` and confirms both exist.
2. From this session: run the stub with PowerShell directly (no `wt`) against the existing `tasks/2026-05-22-example-erp-02/` task, confirm it resolves and exits 0.
3. Wrap it in `wt.exe -w 0 nt --title "implementer-smoke" powershell.exe -File scripts/_run-implementer.ps1 -TaskRoot ...` -- confirm new tab opens and stub prints expected output.

**Verification (auto, binary):**
- `wt` opens new tab titled `implementer-smoke`
- Stub stdout contains `sdd.md EXISTS: true` AND `sdd_metadata.json EXISTS: true`
- Stub exit code = 0

**No marker file needed** -- Phase 1+2 Stage 0 already proved the `wt -> powershell -> claude` end-to-end binding; this stage tightens to the new wrapper only.

### Stage 1 -- schemas/impl_v1.py (Pydantic sidecar contract)

**Deliverables:**
- `schemas/impl_v1.py` -- standalone Pydantic v2, zero `from <prior-iteration>` imports, zero `from schemas.sdd_v1` imports (Citation is DUPLICATED). [FF2: recursive import walk N/A -- designed from scratch.]

**Schema sketch (binding for Stage 2 prompt):**
```python
class ImplementationResult(ArtifactModel):
    schema_version: Literal["v1"]
    task_id: str                                  # matches input sdd_metadata.task_id
    sdd_metadata_ref: Literal["sdd_metadata.json"]
    sdd_ref: Literal["sdd.md"]
    project_id: str                               # from projects.yaml
    path_local: str                               # absolute path used at runtime
    gitea_remote_url: str                         # the project's gitea remote, sans creds
    branch_name: str                              # orchestrator/<task_id>
    commits: list[ImplCommit]                     # >=1; each commit on the branch
    files_changed: list[str]                      # union of all files touched across commits; relative to <path_local>
    validations_attempted: list[ValidationAttempt]   # may be empty if SDD listed none
    open_questions: list[ImplOpenQuestion]        # may be empty
    refusals: list[str]                           # what implementer refused to implement and why
    diff_baseline: DiffBaseline                   # before/after status snapshots for Gate B sanity
    ff_self_audit: dict[Literal["FF1","FF2","FF3","FF4","FF5","FF6","FF7","FF8"], FFOutcome]
    citations_used: list[Citation]                # >=1; cross-reference into sdd_metadata or new MCP
    status: Literal["ready", "needs_revision", "blocked"]
    failures: list[str]                           # required non-empty if status != "ready"
    audit_inputs: list[str]                       # paths/refs an auditor (Phase 4) would inspect
    self_review_notes: str

class ImplCommit(ArtifactModel):
    sha: str                                      # 40 hex chars (git full sha)
    subject: str                                  # first line of message
    files: list[str] = Field(min_length=1)        # relative to <path_local>
    stage_ref: str                                # SDD stage id this commit implements, e.g. "Stage 1"

class ValidationAttempt(ArtifactModel):
    name: str                                     # e.g. "cf-validate", "cfe-validate", "meta-validate:Catalog.Counterparties"
    status: Literal["ok", "fail", "skipped", "unavailable"]
    diagnostic: str                               # required non-empty
    mandatory: bool                               # true if SDD listed it in stage.verifications

class ImplOpenQuestion(ArtifactModel):
    id: str                                       # e.g. "IOQ1"
    severity: Literal["info", "decision", "blocker"]
    question: str
    surface: str                                  # where in the implementation it surfaced (file, line, stage)

class DiffBaseline(ArtifactModel):
    before_sha: str                               # path_local HEAD sha just before implementer started
    after_branch_sha: str                         # tip of orchestrator/<task_id> after implementer finished
    orchestrator_before: str                      # `git -C <orchestrator_root> status --porcelain` snapshot before
    orchestrator_after: str                       # same after; Gate B compares for files outside tasks/<task_id>/

class FFOutcome(ArtifactModel):                   # duplicated from sdd_v1.py
    status: Literal["pass", "na", "fail"]
    note: str

class Citation(ArtifactModel):                    # duplicated; source enum adds "sdd_metadata" + "sdd"
    source: Literal["mcp", "code", "rlm", "raw_artefact", "analysis_report", "sdd_metadata", "sdd"]
    ref: str
    excerpt: str | None = None
```

**Validators (binding for validate_impl.py exit codes):**
- `task_id` matches the input `sdd_metadata.task_id` -- enforced cross-file in validate_impl, not in pydantic
- `ff_self_audit` must have all 7 keys present (model_validator)
- `status = "ready"` requires `failures = []` AND every `ValidationAttempt.mandatory=true` has `status="ok"` (model_validator)
- `status != "ready"` requires `failures` non-empty (model_validator)
- `ImplCommit.sha` matches `^[0-9a-f]{40}$` (field_validator)
- `branch_name` matches `^orchestrator/[A-Za-z0-9._/-]+$` (field_validator) -- enforces convention
- `Citation.source = "sdd_metadata"` requires `ref` to start with `sdd_metadata.json#` (field_validator)
- `Citation.source = "sdd"` requires `ref` to start with `sdd.md#` (field_validator)

**Verification (FF3 binary list):**
- `python -c "from schemas.impl_v1 import ImplementationResult; print(sorted(ImplementationResult.model_fields.keys()))"` exits 0, lists 20 fields
- `grep -E "^(from|import) <prior-iteration>" schemas/impl_v1.py` -- empty
- `grep -E "^from schemas.sdd_v1" schemas/impl_v1.py` -- empty (Citation duplicated, not imported)
- `scripts/_python/_test_impl_schema.py` fixtures pass:
  - (a) valid full result, status="ready", all validations ok -> OK
  - (b) status="ready" with a failed mandatory validation -> ValidationError
  - (c) status="needs_revision" with failures=[] -> ValidationError
  - (d) branch_name="dispatch/foo" -> ValidationError
  - (e) ImplCommit.sha="abc" (too short) -> ValidationError
  - (f) Citation(source="sdd_metadata", ref="something_else") -> ValidationError
  - (g) Citation(source="sdd", ref="sdd.md#stage1") -> OK
  - (h) ff_self_audit missing FF5 -> ValidationError

### Stage 2 -- prompts/implementer.md

**Deliverables:**
- `prompts/implementer.md` -- phase contract. Embeds FF1-FF8 (referenced by absolute path under `{ORCHESTRATOR_ROOT}/docs/writer-forcing-functions.md`).

**Required prompt content (FF6 forcing functions, not honor-system):**
- Anti-assumption rule (mirror analyst.md and sdd-writer.md)
- Multi-round verification: implementer must issue >=1 MCP query for any non-trivial finding it carries forward from sdd_metadata (FF4 -- code over doc; do not trust the writer's narrative)
- Citation discipline: every commit message body (after the subject) cites either `sdd_metadata.json#<section>`, `sdd.md#<heading>`, or a new MCP/code/rlm ref
- Branch convention: implementer creates and pushes `orchestrator/<task_id>` ONLY. Forbidden: pushing to master/main; force-pushing; deleting other branches; merging into master/main; running git config; running git filter-branch / rebase across already-pushed commits.
- Commit convention: `feat(orch <task_id>): <subject>` / `fix(orch <task_id>): <subject>` / `docs(orch <task_id>): <subject>` / `test(orch <task_id>): <subject>` / `chore(orch <task_id>): <subject>` -- the `orch <task_id>` substring is MANDATORY (Gate E).
- DB mutation prohibition: implementer is FORBIDDEN from running `db-update`, `1c-manage.sh config-partial-load`, any direct `psql`/`pg_*` command, any `ibcmd config apply`. The prompt lists these by name in a "REFUSE" section. Implementer must self-certify in FF6 self-audit row that it did not run any of them.
- Validation steps best-effort: for each `stage.verifications` entry that maps to a 1c-skills validate skill (cf-validate, cfe-validate, meta-validate, form-validate, role-validate, etc.), implementer attempts it via Skill invocation. Record outcome in `validations_attempted[]`. Hard failure of a SDD-listed verification -> status="needs_revision".
- Output contract: write impl_metadata.json, post-Write Read it, announce literally `IMPLEMENT READY` or `IMPLEMENT NEEDS_REVISION` or `IMPLEMENT BLOCKED` on its own line.
- FF1-FF8 self-audit checklist: must populate `impl_metadata.ff_self_audit` with all 7 keys, each pass/na/fail + note. `fail` blocks status="ready".
- Refusal contract: implementer may REFUSE to implement specific stages and must list them in `metadata.refusals` with reasons.
- Retry-on-validate-exit-code flow (exit codes listed in Stage 5).

**Verification (FF3 binary list):**
- `grep -E "FF[1-7]" prompts/implementer.md` produces >=14 matches
- `grep "IMPLEMENT READY" prompts/implementer.md` produces >=1 match
- `grep "IMPLEMENT NEEDS_REVISION" prompts/implementer.md` produces >=1 match
- `grep "orch <task_id>" prompts/implementer.md` produces >=2 matches
- `grep -E "(db-update|1c-manage\.sh|psql|ibcmd config apply)" prompts/implementer.md` produces >=4 matches (in the REFUSE section)
- File contains no Cyrillic
- File header references `docs/writer-forcing-functions.md` by absolute path

### Stage 3 -- templates (implementer-CLAUDE.md.tpl + implementer-mcp.json.tpl)

**Deliverables:**
- `templates/implementer-CLAUDE.md.tpl` -- first-thing-implementer-reads. Placeholders:
  - `{PROJECT_ID}`, `{PROJECT_PATH}`, `{TASK_ID}`, `{TASK_TEXT}`, `{ORCHESTRATOR_ROOT}`, `{TASK_ROOT_ABS}`
  - NEW for Phase 3: `{SDD_REF}` = `"sdd.md"`, `{SDD_METADATA_REF}` = `"sdd_metadata.json"`, `{GITEA_REMOTE_URL}`, `{BRANCH_NAME}` = `"orchestrator/{TASK_ID}"`
- `templates/implementer-mcp.json.tpl` -- `.mcp.json` for codemetadata, same shape as sdd-writer. Placeholder `{CODEMETADATA_URL}`.

**Why a distinct MCP file (analyst-, sdd-writer-, implementer-) instead of sharing?** Same reason as Phase 2: per-task render goes into a distinct file (`.mcp.implementer.json`) so a concurrent peek/kill of analyst or writer does not collide. Three files, slightly redundant content, full concurrent observability.

**Verification (FF3 binary):**
- Both files exist
- `python scripts/_python/_test_templates.py` (extended) renders both templates with fixture values and asserts:
  - No `{...}` placeholder remains in output
  - mcp.json output parses as JSON and has `type: "http"` (FF4: D1 regression -- Streamable HTTP, not SSE) [VERIFIED via RLM fact 486bd6e3 D1 close-out + commits 1f1df73 + fe54656]
  - CLAUDE.md output mentions absolute path `{ORCHESTRATOR_ROOT}/prompts/implementer.md` (resolved)
  - CLAUDE.md output includes the literal branch convention string `orchestrator/<task_id>` with task_id substituted

### Stage 4 -- spawn-implementer.ps1 + _run-implementer.ps1

**4.1 `scripts/spawn-implementer.ps1`**

**Params:**
- `-TaskId <string>` (required) -- must reference an existing `tasks/<task_id>/` with passing `sdd.md` + `sdd_metadata.json`
- `-PrepareOnly` (switch) -- generate files but skip `wt` spawn (for tests)
- `-Force` (switch) -- allow re-running on a task that already has `impl_metadata.json` or where `orchestrator/<task_id>` branch already exists

**Steps:**
1. Resolve `tasks/<TaskId>/`. If absent, exit 1.
2. Read `tasks/<TaskId>/task_packet.json`, `tasks/<TaskId>/sdd_writer_packet.json` (for traceability). Extract `project_id`, `project_path`, `orchestrator_root`, `codemetadata_url`.
3. **Gating pre-check 1:** `tasks/<TaskId>/sdd.md` AND `tasks/<TaskId>/sdd_metadata.json` exist; `scripts/validate-sdd.ps1 -TaskId <TaskId>` exits 0. If not, exit 5 with diagnostic "SDD not validated; run validate-sdd.ps1 first".
4. **Gating pre-check 2:** path_local INVARIANT (carried from Phase 1+2) -- fail-fast if `Configuration.xml` or `Catalogs/` not under `project_path`.
5. **Gating pre-check 3:** `<path_local>` git is clean (`git -C <path_local> status --porcelain` empty). If dirty, exit 6 with diagnostic. Operator must commit/stash/discard before implementer runs.
6. **Gating pre-check 4:** `<path_local>` has a `gitea` remote (`git -C <path_local> remote get-url gitea`). If absent, exit 7 with diagnostic.
7. **Gating pre-check 5:** If `<path_local>` already has a branch `orchestrator/<TaskId>` AND `-Force` not passed, exit 8 with diagnostic ("branch already exists; rerun with -Force to overwrite").
8. **Gating pre-check 6:** If `tasks/<TaskId>/impl_metadata.json` exists AND `-Force` not passed, exit 9 ("impl already exists; rerun with -Force to overwrite").
9. Render templates with placeholder dict. Write:
   - `tasks/<TaskId>/CLAUDE.implementer.md`
   - `tasks/<TaskId>/.mcp.implementer.json`
   - `tasks/<TaskId>/implementer_packet.json` (writer-side metadata: `created_at`, `wt_window_title`, `path_local`, `gitea_remote_url` with creds stripped, `branch_name`, `before_sha` = `git -C <path_local> rev-parse HEAD`)
   - `tasks/<TaskId>/prompt.implementer.md` (one-liner pointing at `./CLAUDE.implementer.md`)
   - `tasks/<TaskId>/impl_raw/` directory
10. Pre-trust (idempotent): `~/.claude/projects/<encoded>/settings.json {trusted:true}` for both case variants of task_root, orchestrator_root, AND path_local.
11. Spawn `wt.exe`:
    ```
    wt.exe -w 0 nt --title "implementer:$TaskId" powershell.exe -NoExit -ExecutionPolicy Bypass `
      -File "$PSScriptRoot\_run-implementer.ps1" `
      -TaskRoot "$TaskRoot" `
      -ProjectPath "$ProjectPath" `
      -OrchestratorRoot "$OrchestratorRoot" `
      -PathLocal "$PathLocal" `
      -GiteaRemoteUrl "$GiteaRemoteUrlSanitized"
    ```
12. Print JSON to stdout with `{task_id, task_root, wt_window_title, path_local, branch_name, before_sha}`.

**4.2 `scripts/_run-implementer.ps1`** -- same shape as `_run-sdd-writer.ps1`, but reads `prompt.implementer.md` and `.mcp.implementer.json`, and passes additional env-vars `ORCH_PATH_LOCAL` and `ORCH_BRANCH_NAME` for prompt template substitution. ASCII-only.

**What breaks (FF3 -- failure modes):**
- analyst hasn't run / sdd_writer hasn't run -> exit 1, clear message
- sdd present but invalid -> exit 5 (above)
- path_local dirty -> exit 6
- path_local no gitea remote -> exit 7
- branch already exists -> exit 8 unless -Force
- impl_metadata already exists -> exit 9 unless -Force
- `task_packet.json` schema drift -> spawn fails reading; covered by Stage 4 fixture test
- `wt.exe` absent -> exit 2 with manual-run fallback

**Verification (FF3 binary):**
- `spawn-implementer.ps1 -TaskId 2026-05-22-example-erp-02 -PrepareOnly` exits 0, creates 5 files + `impl_raw/`
- Negative: `spawn-implementer.ps1 -TaskId nonexistent -PrepareOnly` exits 1
- Negative: stage a fake task with broken sdd_metadata.json -> exit 5
- Negative: stage a fake task with dirty path_local -> exit 6
- Negative: stage a fake task with no gitea remote -> exit 7
- Negative: stage a fake task with pre-existing branch -> exit 8 (and exit 0 with `-Force`)
- Concurrent: re-running spawn with pre-existing impl_metadata -> exit 9 (and exit 0 with `-Force`)

### Stage 5 -- validate_impl.py + validate-impl.ps1

**5.1 `scripts/_python/validate_impl.py`**

**Input:** `<task_root>` (positional). Discovers `analyst_session.jsonl` + `writer_session.jsonl` + `implementer_session.jsonl` via `~/.claude/projects/*Orchestrator*tasks*<task_id>*/` glob.

**Exit codes:**

| exit | meaning | message |
|---|---|---|
| 0 | OK | summary (gates A-E, validations breakdown, MCP-usage tallies for three sessions) |
| 1 | impl_metadata.json Pydantic ValidationError | full ValidationError |
| 2 | impl_metadata.json absent at task_root (**Gate C**) | "implementer did not produce impl_metadata.json" |
| 3 | `impl_metadata.task_id` != input `sdd_metadata.task_id` | both values shown |
| 4 | impl_metadata.json not parseable | JSONDecodeError line/col |
| 5 | **Gate A: branch `orchestrator/<task_id>` not present in path_local OR not pushed to gitea** | `git ls-remote gitea orchestrator/<task_id>` empty OR local branch absent |
| 6 | analyst session.jsonl shows 0 `tool_use.name ~ ^mcp__` (OPERATIONAL QUALITY GATE -- Phase 2 carry-forward) | "input analysis was synthesized without real MCP" |
| 7 | writer session.jsonl shows 0 `tool_use.name ~ ^mcp__` (FF4 forcing function for writer) | "sdd_writer did not consult MCP" |
| 8 | implementer session.jsonl shows 0 `tool_use.name ~ ^mcp__` (FF4 for implementer itself) | "implementer did not consult MCP" |
| 9 | **Gate D: file changed in branch is NOT in sdd_metadata.stages[*].deliverables** | diff of out-of-scope files |
| 10 | **Gate B: Orchestrator/ has changes outside tasks/<task_id>/** | porcelain output of out-of-scope diff |
| 11 | **Gate E: commit in branch missing `orch <task_id>` substring** | sha + offending message |
| 12 | `ff_self_audit.<FFi>.status == "fail"` for any FFi | which FFs failed + notes |
| 13 | `impl_metadata.status` != "ready" (status="needs_revision" or "blocked") | failures list + open_questions[blocker] |

**Summary at exit=0:** task_id, project_id, branch_name, gitea remote ref + sha, files_changed count, commits count, validations_attempted breakdown (ok/fail/skipped/unavailable counts, mandatory-pass count), FF audit (7 booleans), analyst/writer/implementer MCP-tool-use counts, open_questions by severity, refusals count, audit_inputs list.

**Session.jsonl walker:** reuse the helper from `validate_sdd.py` (`count_mcp_tool_use(jsonl_path)`). DO NOT import -- duplicate the helper into `validate_impl.py` if Phase 3 design wants standalone (FF2 anti-coupling) OR factor both into `scripts/_python/_session_jsonl.py` shared helper. **Decision:** factor into shared helper `scripts/_python/_session_jsonl.py` -- single source of truth for the parser is more important than schema-style standalone-ness here (parsing the Claude Code session.jsonl format is a system contract, not a per-phase contract). Validate_sdd.py is updated to import from the helper in the same Stage 5 commit. [This is an intentional Phase 2 contract touch -- raised as OQ in §10; resolved CLOSED.]

**Gate implementations:**
- **Gate A:** `git -C <path_local> rev-parse refs/heads/orchestrator/<task_id>` succeeds AND `git -C <path_local> ls-remote gitea refs/heads/orchestrator/<task_id>` returns non-empty.
- **Gate B:** Capture orchestrator-side porcelain status. Filter lines: any path NOT under `tasks/<task_id>/` (after normalizing slashes) -> Gate B fail with the offending lines.
- **Gate D:** `git -C <path_local> diff --name-only orchestrator/<task_id> ^<diff_baseline.before_sha>` -> set X. Set Y = union of `sdd_metadata.stages[*].deliverables[*].path` (forward-slash normalised). If X - Y non-empty -> Gate D fail. (Updated 2026-05-22 per IOQ2: deliverables are now `Deliverable{path, description}` dicts, not bare strings.)
- **Gate E:** `git -C <path_local> log <diff_baseline.before_sha>..orchestrator/<task_id> --format=%H%n%s` -> for each commit, assert subject contains `orch <task_id>` substring.

**5.2 `scripts/validate-impl.ps1`** -- thin wrapper, `-TaskId X`, passes through python exit code. Same Write-Error gotcha mitigations as validate-sdd.ps1.

**Verification (FF3 binary, via `_test_validate_impl.py`):**
- 14 fixtures, one per exit code 0-13. Each fixture stages a fake task_root + sdd_metadata.json + impl_metadata.json + mocked session.jsonls under a temp dir; for git-touching gates (A, B, D, E) the fixture initializes a temp git repo (`tmp_path/path_local_fake/.git`) and runs `git init` + a few commits.

### Stage 6 -- e2e against `tasks/2026-05-22-example-erp-02`

**Why this task:** Phase 2 Stage 6 produced a real validated `sdd.md` + `sdd_metadata.json` at `tasks/2026-05-22-example-erp-02/` (example-erp-02 = example-erp project, ИНН attribute in Контрагенты). Reusing it exercises the full Phase 3 chain without first running another sdd_writer.

**Steps:**
1. Baselines (FF1 -- record before running):
   - `git -C <orchestrator_root> status --porcelain` (must be clean except in-progress `docs/phase3-*.md` if any)
   - `git -C <path_local> status --porcelain` (must be clean)
   - `git -C <path_local> rev-parse HEAD` (save as `before_sha`)
2. `scripts/spawn-implementer.ps1 -TaskId 2026-05-22-example-erp-02` -- opens `implementer:2026-05-22-example-erp-02` tab.
3. Observe via `scripts/peek-implementer.ps1 -TaskId 2026-05-22-example-erp-02 -Tail 30`. Wait for `IMPLEMENT READY` (or `IMPLEMENT NEEDS_REVISION` / `IMPLEMENT BLOCKED`).
4. `scripts/validate-impl.ps1 -TaskId 2026-05-22-example-erp-02` -- must exit 0 (or operator decides retry per Stage 6 retry-flow).
5. Sanity-checks (FF1):
   - `tasks/<task_id>/impl_metadata.json` exists, Pydantic-valid
   - `git -C <path_local> branch --list orchestrator/2026-05-22-example-erp-02` non-empty
   - `git -C <path_local> ls-remote gitea refs/heads/orchestrator/2026-05-22-example-erp-02` non-empty
   - `git -C <orchestrator_root> status --porcelain | grep -v 'tasks/'` empty (Gate B)
   - For each `impl_metadata.files_changed[*]`, the file exists under `<path_local>` at the branch tip
   - Every `impl_metadata.files_changed[*]` appears in `sdd_metadata.stages[*].deliverables` (Gate D pre-validate sanity)
   - `impl_metadata.validations_attempted[]` contains at least one entry (example-erp-02 SDD has stages with verifications; if it has zero, refusal must be in `impl_metadata.refusals`)
6. **Retry flow:** identical pattern to Phase 2 §5 Stage 6 retry-flow -- operator sees validate exit code, pastes guidance into the implementer's tab as followup, max 2 retries.

**What breaks (FF3):**
- Hang / no progress: peek prints `LAST_EVENT_AGO > 300s WARNING`; operator runs `kill-implementer.ps1`
- Partial write: post-Write Read in prompt + validate exit 2
- MCP timeout mid-edit: implementer records `OpenQuestion` of severity blocker; visible in metadata; status="blocked"
- Validation fails (cf-validate / cfe-validate): if mandatory per SDD -> status="needs_revision", validate exit 13
- Out-of-scope edit: Gate D catches (exit 9)
- Commit without `orch <task_id>`: Gate E catches (exit 11)

### Stage 7 -- peek-implementer.ps1 + kill-implementer.ps1

**peek-implementer.ps1:**
- Params: `-TaskId X`, `-Tail N` (default 30)
- Discovery: `Get-ChildItem ~/.claude/projects -Directory | Where Name -like "*Orchestrator*tasks*<TaskId>*"` then pick newest by `LastWriteTime` -- but Phase 3 may have THREE candidate session dirs (analyst, writer, implementer). Disambiguate as in Phase 2 (newest = current phase). Operator using `peek-analyst.ps1` / `peek-sdd-writer.ps1` instead, if they want older session.
- Same event-formatting as Phase 2. Same `LAST_EVENT_AGO` health line.
- ASCII-only.

**kill-implementer.ps1:**
- Title pattern: `*implementer:<TaskId>*`
- Stamps `implementer_packet.killed_at`
- Identical body otherwise.

**Verification (FF3 binary):**
- After Stage 6 run, `peek-implementer.ps1 -TaskId 2026-05-22-example-erp-02` returns >0 events + `LAST_EVENT_AGO=<s>`
- Mocked-stuck case: artificially set `LastWriteTime` to 6 minutes ago -> WARNING printed
- `kill-implementer.ps1 -TaskId <dummy>` -- kills dummy wt tab whose title contains `implementer:<dummy>`, stamps `killed_at`

### Stage 8 -- operator-review gate (thin)

**Goal:** record the manual review step in the chain explicitly, so Phase 3 has a defined closure point.

**Deliverables:**
- After Stage 7 closes and validate-impl exits 0 for the Stage 6 task, this stage's only deliverable is: `tasks/2026-05-22-example-erp-02/operator_signoff.txt` with content `approved <commit>` or `rejected: <reason>`.
- No new script. L2 (current session) writes the file on operator's verbal/text approval in chat. No automation.

**Verification (FF3 binary):**
- `tasks/2026-05-22-example-erp-02/operator_signoff.txt` exists at Phase 3 DONE
- File content matches regex `^(approved [0-9a-f]{7,40}|rejected: .+)$`

**Why this is a Stage and not just operator's call:** it is a Stage to (a) make the Phase 3 DoD checklist verify it, (b) make future phases (4 auditor, 5 rotation) able to find a signal of "this task was operator-approved" without inferring. The signoff file is part of the per-task artifact bundle, not a project-level state machine.

**What breaks (FF3):**
- Operator never signs off -> Phase 3 chain stuck on Stage 8; autonomous-chain re-prompts continue until operator emits `## CHAIN COMPLETE` or `## BLOCKED:`. Not a script-level failure; a UX one.

---

## 6. Open Questions

### OQ1 -- Spawn vs inline (operator confirmation needed)

Spawn is proposed (§2 table). Open question only if operator prefers inline (would block L2 for ~100k tokens during implementation; sacrifices observability; deletes peek/kill from Phase 3 deliverables).

**Recommendation:** spawn. Mirrors Phases 1+2; full L4 visibility.

### OQ2 -- Branch naming convention

`orchestrator/<task_id>` vs `dispatch/<task_id>` vs `claude/<task_id>`.

**Recommendation:** `orchestrator/<task_id>`. Operator clarity ("this branch came from the orchestrator"). Distinct from `dispatch/*` branches used in other workflows. Single source of truth: encoded in `prompts/implementer.md`, `templates/implementer-CLAUDE.md.tpl`, `schemas/impl_v1.py` (`branch_name` regex `^orchestrator/[A-Za-z0-9._/-]+$`), and `validate_impl.py` Gate A.

### OQ3 -- Validation steps mandatory or best-effort

The 1c-skills family includes `cf-validate`, `cfe-validate`, `meta-validate`, `form-validate`, `role-validate`, etc.

**Recommendation:** **best-effort**. Implementer attempts the validation steps that match SDD's `stages[*].verifications` -- records each in `impl_metadata.validations_attempted[]`. Hard failure of a SDD-listed verification (mandatory=true) -> status="needs_revision" -- blocking. Failure of an attempted-but-not-SDD-listed verification (mandatory=false) is informational only.

### OQ4 -- Test DB availability

None of the three current projects (`example-erp`, `example-trade`, `example-mfg`) have a documented test DB in `projects.yaml`.

**Recommendation:** Phase 3 does NOT require test DB. Verifications stop at structural validation (cf-validate, cfe-validate, meta-validate, form-validate) and source-level diff. **No db-update by default** (decision already locked in §2 table). Adding test DB hookup is a future phase. If operator wants live db-update, they run it manually post-Phase-3-DONE.

### OQ5 -- Rollback policy if validate_impl fails

Implementer wrote a branch + commits; validate_impl exit != 0.

**Recommendation:** branch stays. Implementer surfaces failure as `impl_metadata.status = "needs_revision"` + `impl_metadata.failures[]`. Operator decides -- either nudge implementer with retry prompt (max 2 retries), OR delete branch + redo from analyst, OR accept partial work with status="needs_revision". validate_impl does NOT delete the branch.

### OQ6 -- Operator-review gate as a discrete Stage 8?

**Recommendation:** **encode as Stage 8** with the thin signoff file (decided in §5 Stage 8 above). Reasons: (a) makes Phase 3 DoD verify it; (b) gives future Phase 4 (auditor) a discoverable signal; (c) low overhead -- one file, no script.

### OQ7 -- Out-of-scope edits handling

SDD lists `stages[*].deliverables` as file paths. Implementer edits a file NOT in any deliverable.

**Recommendation:** **validate_impl Gate D fails (exit 9)** with explicit diff of out-of-scope files. No auto-revert. Operator amends SDD or rejects the work. Same retry budget as other failures.

### OQ8 -- Phase 4 (auditor) preview

Does Phase 3 leave hooks for Phase 4?

**Recommendation:** YES, minimally. `impl_metadata.audit_inputs[]` lists artifacts an auditor would inspect (branch ref, diff stats, validations_attempted IDs, citations_used). No Phase 4 work in Phase 3; just preserve the surface.

### OQ9 -- Shared session.jsonl helper (`_session_jsonl.py`)

Stage 5 of Phase 3 refactors the session.jsonl walker out of `validate_sdd.py` into a shared `scripts/_python/_session_jsonl.py`, then imports from both `validate_sdd.py` and `validate_impl.py`.

**Recommendation:** **YES, refactor.** Parsing the Claude Code session.jsonl format is a system contract, not a per-phase contract. Single source of truth wins over schema-style standalone-ness. Phase 2 `validate_sdd.py` and its test fixtures are touched as part of Stage 5 -- raised as an Open Question because it is the FIRST Phase 2 contract touch in Phase 3. Stage 5 commit message acknowledges the cross-phase touch.

---

## 7. Risks and mitigations

| Risk | Mitigation | Tag |
|---|---|---|
| Implementer pushes to master/main of 1C project, corrupting stable code | Prompt forbids; Gate A enforces branch=`orchestrator/<task_id>` only; spawn-implementer.ps1 records `before_sha` so out-of-branch commits are detectable via DiffBaseline | FF6 (code-level) |
| Implementer writes files outside `tasks/<task_id>/` in `Orchestrator/` (e.g. modifies prompts/implementer.md mid-run) | Gate B fails (exit 10) with porcelain diff | FF6 |
| Implementer edits files not in SDD's deliverables | Gate D fails (exit 9) with diff of out-of-scope paths | FF6 |
| Implementer commits without `orch <task_id>` in message | Gate E fails (exit 11) with sha + message | FF6 |
| Implementer trusts SDD blindly, propagates Phase 2 errors | Gate H exit 8 enforces implementer ran real MCP queries; prompts/implementer.md FF4 instruction | FF4, FF6 |
| Analyst session synthesized via Bash+curl (D1-style) | exit 6 (carried from Phase 2 §5.1) | FF4 |
| Writer session synthesized | exit 7 (carried from Phase 2) | FF4 |
| Implementer runs `db-update` / `1c-manage.sh config-partial-load` / direct PG mutation | Prompt REFUSE section explicitly lists these; FF6 self-audit row requires implementer certification | FF6 honor-tagged BUT operator may verify post-hoc by checking `~/.claude/projects/<encoded>/session.jsonl` for `tool_use.name` matching `Bash` with these command substrings |
| Implementer hangs / loops | `peek-implementer.ps1 LAST_EVENT_AGO>300s WARNING` + `kill-implementer.ps1` | FF3 |
| `--dangerously-skip-permissions` blast radius -- can pip-install / modify arbitrary FS | RISK ACCEPTED (same as Phase 1+2). Mitigations: (a) per-task branch in 1C project's git; (b) Gate B; (c) Stage 6 e2e records pip-freeze before/after if operator opts in. No technical sandbox until Phase 5+ | FF5 |
| `impl_metadata.task_id` accidentally hardcoded by implementer (copy-paste from sdd_metadata) | validate_impl exit 3 cross-checks against sdd_metadata.task_id | FF6 |
| `task_packet.json` / `sdd_writer_packet.json` schema drift between Phases 1+2 and Phase 3 spawn | Stage 4 fixture test reads the real `tasks/2026-05-22-example-erp-02/` packets and asserts required keys present | FF1, FF2 |
| Two implementer-attempts on same task collide on branch | spawn-implementer.ps1 exit 8 if branch exists; exit 9 if impl_metadata exists; `-Force` opt-in deletes branch + metadata | FF3 |
| `peek-implementer.ps1` returns analyst's or writer's session instead of implementer's | Pick newest dir by `LastWriteTime`; operator can use phase-specific peek if needed. Documented in Stage 7. | FF3 (disambiguation) |
| Codemetadata indexer differs between sdd_writer run and implementer run | RISK ACCEPTED (same as Phase 2). Mitigation: implementer's prompt asks to re-verify only high-impact decisions; detection via tool_use count comparison | FF1 |
| `validate_impl.py` cannot find writer or analyst session dir | exit 6/7 with diagnostic "session.jsonl not found -- cannot verify gate". Operator re-runs upstream phase or overrides (no override switch in Phase 3) | FF3 |
| 1C-skill is REQUESTED in SDD but not available at runtime (Skill not registered for this session, or <vm-docker-host> MCP common unreachable) | `validations_attempted[].status = "unavailable"` + diagnostic. If the validation was mandatory per SDD, status="needs_revision" cascades. operator sees clear cause | FF3 |
| Implementer pushes branch to gitea but gitea push fails mid-stage (network) | implementer surfaces blocker OpenQuestion; status="blocked"; validate_impl exit 13 with `failures[]` containing push error | FF3 |
| Implementer's git operations corrupt local repo state (e.g. dangling refs) | RISK ACCEPTED. Mitigation: per-task branch is isolated; operator can `git reset --hard <before_sha>` to recover. validate_impl does NOT auto-recover. | FF5 |
| `orch <task_id>` substring causes false-positive Gate E pass if implementer copy-pastes the literal `<task_id>` instead of substituting | Gate E checks for the SUBSTITUTED form (e.g. `orch 2026-05-22-example-erp-02`), not the literal `<task_id>`. Encoded in regex `orch \S+` AND task_id must match the spawned task | FF6 |

---

## 8. Definition of Done

### Pre-conditions (FF7 -- BEFORE Stage 1 starts)

- **0a.** All OQ1-OQ9 closed in §10 with resolution text.
- **0b.** Stage 0 smoke (wrapper-stub spawning in `wt` tab) PASSES.
- **0c.** path_local INVARIANT remains intact (Phase 1+2 carry-forward).
- **0d.** Operator quality-gate semantics confirmed (carried from Phase 2 -- 0 mcp__ tool_use entries = fail). Phase 3 extends to a THIRD session (implementer's own); operator confirms same semantics apply.
- **0e.** Branch naming convention confirmed (OQ2 -- `orchestrator/<task_id>`).
- **0f.** Validation policy confirmed (OQ3 -- best-effort with mandatory escalation).

### Post-conditions (FF7 -- Phase 3 = DONE when)

1. All 9 stages (0-8 above) shipped, each verification list passes.
2. Stage 6 e2e on `2026-05-22-example-erp-02` produces a valid branch `orchestrator/2026-05-22-example-erp-02` in `<path_local>` (example-erp-src), pushed to gitea; `impl_metadata.json` validates; `validate-impl.ps1` exits 0.
3. Stage 6 sanity-checks: Orchestrator/ untouched outside tasks/<task_id>/ (Gate B); branch present at gitea (Gate A); every changed file in sdd_metadata deliverables (Gate D); every commit has `orch <task_id>` (Gate E); validations_attempted non-empty.
4. Stage 8 signoff: `tasks/2026-05-22-example-erp-02/operator_signoff.txt` exists with `approved <commit>`.
5. `peek-implementer.ps1` and `kill-implementer.ps1` verified on a dummy and on the Stage 6 task.
6. master pushed to Gitea Orchestrator repo, merged into main at the Phase 3 closeout commit.
7. RLM fact written: `Phase 3 implementer DONE @<commit>` with operational invariants list (gates A-E enforced, branch convention locked, helper refactored).
8. `MEMORY.md` updated with one-line entry pointing to new `project_phase3_done.md`.

---

## 9. Refusals (REFUSE)

Items deliberately NOT in Phase 3 scope:

- **Auditor for the produced branch.** Phase 4 scope.
- **Implementation engine of 1C runtime.** Phase 3 produces source edits only; running them against a live base is operator's call.
- **Live db-update / config-partial-load.** Refused by implementer prompt + project-wide rule (no live DB mutation by L3 in Phase 3).
- **Auto-merge of `orchestrator/<task_id>` to master/main.** Operator-only.
- **Branch deletion / force-push / rebase.** Implementer prompt forbids.
- **Editing Phase 1+2 artifacts** EXCEPT `validate_sdd.py` import line + `_test_validate_sdd.py` fixture path adjustments (per OQ9 refactor into `_session_jsonl.py`).
- **Schema versioning policy.** schema_impl_v1 only. v2 happens when Phase 4 demands it.
- **Phase-agnostic peek/kill scripts.** Phase 5 cleanup.
- **Inline-in-L2 mode.** Spawn-only (OQ1 decision).
- **Implementer self-merging to a release branch.** Out of scope; operator does merges.
- **Cross-project implementer runs in a single session.** One task = one path_local = one branch. No multi-project bundle.

---

## 10. Resolutions (closure of Open Questions)

Resolutions promoted from PROVISIONAL to CLOSED 2026-05-22 under brief authorization (autonomous chain enabled, ROTATE mode). Operator retains override prerogative: if any resolution should flip, raise it during Stage 6 e2e and the affected stages are reworked before merge to main.

**OQ1 -- Spawn vs inline:** CLOSED -- SPAWN. Rationale: parity with Phases 1+2, observability via peek/kill, no L2 context pollution during a ~100k-token implementation pass.

**OQ2 -- Branch naming:** CLOSED -- `orchestrator/<task_id>`. Encoded in 4 places (prompt, template, schema regex, validate_impl Gate A).

**OQ3 -- Validation policy:** CLOSED -- best-effort with SDD-mandatory escalation. validations_attempted[] records all attempts; mandatory failures cascade to status="needs_revision".

**OQ4 -- Test DB:** CLOSED -- not required. Verifications stop at structural + source-level. db-update is operator-only.

**OQ5 -- Rollback policy:** CLOSED -- branch stays on validate_impl fail. Status="needs_revision". Max 2 retries via operator nudge.

**OQ6 -- Stage 8 operator-review gate:** CLOSED -- ENCODE as thin Stage 8. Deliverable: `operator_signoff.txt`. No new script.

**OQ7 -- Out-of-scope edits:** CLOSED -- validate_impl Gate D exit 9. No auto-revert.

**OQ8 -- Phase 4 surface:** CLOSED -- preserve via `impl_metadata.audit_inputs[]` (branch ref, diff stats, validation IDs, citations). No Phase 4 work in this phase.

**OQ9 -- Shared session.jsonl helper:** CLOSED -- YES, refactor into `scripts/_python/_session_jsonl.py`. Update `validate_sdd.py` import in same Stage 5 commit. Stage 5 commit message acknowledges the cross-phase touch.

With OQ1-OQ9 CLOSED, DoD pre-conditions 0a + 0d + 0e + 0f are satisfied. 0b (Stage 0 smoke) is the first implementation gate. 0c (path_local INVARIANT) carries forward intact from Phase 1+2.

---

## 11. Writer FF1-FF8 self-audit (before submitting this SDD)

Per `docs/writer-forcing-functions.md` and `memory/feedback_writer_discipline.md` -- the SDD writer (me, in this session) must self-audit against FF1-FF8 BEFORE handing off for review. Each gets pass / na / fail + note.

| FF | Status | Note |
|---|---|---|
| FF1 | pass | External claims tagged inline: `[VERIFIED via <fact/file/command>]` for path_local invariant (carried from Phase 1+2 §1), D1 transport=http regression (Phase 2 §3 verification + RLM fact 486bd6e3), Phase 2 session.jsonl parser (validate_sdd.py / peek-sdd-writer.ps1), 1c-skills are Skills not MCP (system-reminder available-skills list this session + `~/.claude/1c-development-rules.md`), spawn-sdd-writer.ps1 pre-check structure mirrored as basis for spawn-implementer.ps1. One `[ASSUMED]`-equivalent uncovered: §7 "1C-skill unavailable at runtime" -- assumes Skill registration is per-session and can fail silently. Not tagged because it is fail-open in design (status="unavailable" surfaces explicitly, no silent path). |
| FF2 | pass | "Recursive dependency walk" N/A for schemas -- `schemas/impl_v1.py` is designed from scratch, NOT inlined from sdd_v1. Citation + FFOutcome shapes are DUPLICATED (not imported). One intentional cross-phase touch (validate_sdd.py import line) is enumerated explicitly in OQ9, not silently. Stage 1 verification reasserts `grep -E "^from schemas.sdd_v1" schemas/impl_v1.py` empty. |
| FF3 | pass | Each stage (0-8) has explicit failure-modes paragraph or "What breaks" enumeration. Risk table §7 covers cross-stage failures. validate_impl exit-code table §5.1 enumerates 14 distinct failure modes (exit 0-13). |
| FF4 | pass | Three code-over-doc checks: (a) D1 transport regression baked into Stage 3 verification + Stage 5 mcp.json type=http assertion; (b) operational quality gate triple-fanned (exits 6, 7, 8 -- one per upstream session) reads ACTUAL session.jsonl artifacts, not narrative claims; (c) Gate D (out-of-scope edit) reads ACTUAL git diff, not implementer's self-report. |
| FF5 | pass | Two dangerous primitives carry forward: `--dangerously-skip-permissions` (Phase 1+2 carry-forward, blast radius now LARGER -- writes outside Orchestrator/) and git operations in 1C project (new). Both explicit in §7 with RISK ACCEPTED + mitigations (per-task branch isolation, Gate A push verification, before_sha baseline for rollback). Alternative (`--permission-mode acceptEdits --allowedTools`) deferred to Phase 5+. |
| FF6 | pass | Honor-system items explicitly tagged: (a) implementer's REFUSE of db-update / 1c-manage.sh / direct PG -> HONOR_SYSTEM with operator-side post-hoc verification path (grep session.jsonl for Bash tool_use); (b) implementer's FF7 self-audit text quality -> HONOR_SYSTEM, mitigation deferred to operator review + Phase 4 audit. All RELIABILITY-CRITICAL steps replaced with code-level forcing functions (exit codes 1-13, Gates A-E). |
| FF7 | pass | DoD §8 has BOTH pre-conditions (0a-0f, with 0d/0e/0f new for Phase 3) and post-conditions (8 binary checks). Pre-condition 0e (branch naming) and 0f (validation policy) are NEW for Phase 3 -- without them, Stages 2+5 are blocked. |

If operator approves with all FFs passing as marked above, this section freezes and Stage 0 may begin. If operator finds an FF should be FAIL, the writer rewrites the affected sections before Stage 0.

---

## End of draft

Operator next step: read sections §1-§11. If approved as-is, signal "начинаем Stage 0" and Phase 3 implementation chain begins on `master` with per-stage commits + `## DONE` markers, mirroring Phase 2's autonomous-chain pattern.
