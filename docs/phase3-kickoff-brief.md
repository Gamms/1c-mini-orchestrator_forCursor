# Phase 3 kickoff — implementer

You are starting Phase 3 of the Orchestrator project. Phase 1 (analyst) shipped 2026-05-22 at `eccd95c`; Phase 2 (sdd_writer) shipped 2026-05-22 at `ed090ef`. Your job is to design AND implement Phase 3 (implementer) using Phases 1+2 as a structural template.

## What Phase 3 does

The implementer is an L3 agent that consumes Phase 2 output (`tasks/<task_id>/sdd.md` + `tasks/<task_id>/sdd_metadata.json`) and produces actual code changes in the **target 1C project** (not in `Orchestrator/`). Output: one branch in the 1C project repo, pushed to Gitea, with all stage commits per the SDD. Plus a sidecar artifact `tasks/<task_id>/impl_metadata.json` (Pydantic `ImplementationResult` v1) describing what was changed and how it was verified.

This is the first phase that **writes outside `Orchestrator/`**. Phases 1+2 were read-only (analyst) and write-to-task-root-only (sdd_writer). Phase 3 makes real edits in `path_local` of the target project. That fact drives most of the new constraints below.

## Step 0 — load context

Run these reads/queries in parallel before anything else. They are the authoritative inputs:

1. `docs/phase1-analyst-SDD.md` — original contract format (§1-§10 layout, FF1-FF8, stage gates, DoD checklist).
2. `docs/phase2-kickoff-brief.md` — Phase 2 brief; this brief mirrors its shape exactly.
3. `docs/phase2-sdd-writer-SDD.md` — Phase 2 SDD; this is the closest available template for the Phase 3 SDD.
4. `schemas/analysis_v2.py` + `schemas/sdd_v1.py` — input contracts already in scope; `impl_v1.py` will join them.
5. `prompts/analyst.md` + `prompts/sdd-writer.md` — model `prompts/implementer.md` on these.
6. `templates/analyst-CLAUDE.md.tpl`, `templates/analyst-mcp.json.tpl`, `templates/sdd-writer-CLAUDE.md.tpl`, `templates/sdd-writer-mcp.json.tpl` — model `templates/implementer-*` on these.
7. `scripts/spawn-analyst.ps1` + `scripts/spawn-sdd-writer.ps1` + `scripts/_run-*.ps1` + `scripts/peek-*.ps1` + `scripts/kill-*.ps1` + `scripts/_python/validate.py` + `scripts/_python/validate_sdd.py` — model the L4 wrappers on these.
8. `~/.claude/projects/<orchestrator-claude-projects-dir>/memory/MEMORY.md` — read all referenced files, especially `project_phase1_done.md` and `project_phase2_done.md`.
9. RLM facts under `domain=tasks module=Orchestrator` via `mcp__rlm-toolkit__rlm_get_facts_by_domain` — at minimum `fe55a607` (Phase 2 DONE invariants) and `7da04374` (Phase 2 error patterns retrospective).
10. `CLAUDE.md` (project root) — L2 orchestrator instructions; implementer is L3, same as analyst and sdd_writer.
11. `docs/writer-forcing-functions.md` — FF1-FF8 still apply.
12. `~/.claude/1c-development-rules.md` — 1C-specific rules (skills surface, validation tools, commit conventions). Phase 3 is the first phase to touch this; absorb the rules verbatim.
13. `projects.yaml` — `path_local` is the implementer's working tree; INVARIANT 0c (path_local mirrors codemetadata XML index) carries forward.

## Step 1 — design (no code yet)

Produce `docs/phase3-implementer-SDD.md` mirroring `phase2-sdd-writer-SDD.md` §1-§11. Must answer:

- **§1 Goal:** implementer consumes `sdd.md` + `sdd_metadata.json` and applies the SDD's `stages[*].deliverables` as real file edits in the target 1C project. Output: branch + commits + `impl_metadata.json`. Reads from `path_local`, writes there, commits there, pushes to project's own remote (Gitea, in most cases).
- **§2 Contract IO:** input shape (`SDDMetadata` v1 + `sdd.md`), output shape (`ImplementationResult` v1, new schema), where it lives on disk (`tasks/<task_id>/impl_metadata.json` + the branch in the 1C project's git history).
- **§3 Workflow:** spawn-per-task, mirroring sdd_writer. wt tab title `implementer:<task_id>`. CWD = `tasks/<task_id>/` (Orchestrator side); but implementer's actual edits land in `path_local` via `--add-dir`.
- **§5 Stages:** mirror Phase 2's 0-7 staging plus a NEW Stage 8 if operator-review gate is in scope (see OQ6 below). Stages 0-7 structure: Stage 0 wrapper smoke, Stage 1 schema, Stage 2 prompt, Stage 3 templates, Stage 4 spawn-script, Stage 5 validate-script, Stage 6 e2e on `tasks/2026-05-22-example-erp-02` (which already has a valid `sdd.md` + `sdd_metadata.json`), Stage 7 peek/kill wrappers.
- **§6 Quality gates (MANDATORY for Phase 3):** carry forward the operational MCP-real-usage gate (validate_impl exits 6 if input analyst had 0 `mcp__` calls; exit 7 if input sdd_writer had 0 `mcp__` calls; exit 8 if implementer itself had 0 `mcp__` calls). NEW gates specific to Phase 3:
  - **Gate A — branch hygiene:** validate_impl must verify the implementer pushed exactly one new branch in `path_local`'s git, named per the convention chosen in OQ2 (proposal: `orchestrator/<task_id>`). If no branch was created or HEAD is on master/main, fail.
  - **Gate B — no-write-to-Orchestrator:** validate_impl must check `git status` in `Orchestrator/` is clean for files outside `tasks/<task_id>/` (implementer is allowed to write only in its task root + in `path_local`). If files outside both scopes changed, fail.
  - **Gate C — orchestrator-side artifact present:** `impl_metadata.json` exists at `tasks/<task_id>/` and validates against `schemas/impl_v1.py`.
  - **Gate D — diff scope match:** every file changed in the implementer's branch must appear in `sdd_metadata.stages[*].deliverables` (string match against committed paths). Out-of-scope edits = fail OR surface as an `OpenQuestion[severity=blocker]` in `impl_metadata`; design choice in §10 OQ7.
- **§7 Risks:** carry forward Phase 2 §7; add new rows for **destructive writes in 1C project** (mitigated by per-task branch + push-only-to-branch, never to master/main of the 1C project), **mid-run pip/npm install via dangerously-skip-permissions** (same RISK ACCEPTED as Phase 1+2), **schema drift in `1c-skills` MCP servers between runs** (mitigated by validate_impl recording tool versions), **failure of cf-validate / cfe-validate / db-update at the implementer step** (OQ3 below — best-effort vs mandatory).
- **§8 DoD:** mirror Phase 2 DoD shape. Pre-conditions: OQ1-OQ7 closed in §10. Post-conditions: 8 stages green + Stage 6 e2e produces a branch in `example-erp-src` (since example-erp-02 is the e2e fixture) with passing `validate_impl.py`, that branch is pushed to gitea, `impl_metadata.json` validates, Orchestrator side is clean of out-of-scope edits, RLM completion fact written, `MEMORY.md` index + `project_phase3_done.md` memory file added.
- **§10 Open questions (NEW for Phase 3 — resolve all before Stage 1):**
  - **OQ1 — MCP surface for implementer:** codemetadata (read) + `1c-skills` family (write — cfe-init, cfe-borrow, cfe-patch-method, meta-edit, meta-compile, form-compile, form-edit, etc.)? Or only `1c-skills`? Proposal: BOTH. Codemetadata for re-verifying analyst+writer claims at write-time (FF4 carries forward); 1c-skills for actually making the edits. Closes via <vm-docker-host> MCP common skills, same dispatch as `~/.claude/1c-development-rules.md`.
  - **OQ2 — Branch naming convention:** `orchestrator/<task_id>` vs `dispatch/<task_id>` vs `claude/<task_id>`. Proposal: `orchestrator/<task_id>` for operator clarity ("this branch came from the orchestrator"). Distinct from dispatched-agent branches in other workflows. Single source of truth: encoded in `prompts/implementer.md` + enforced by validate_impl Gate A.
  - **OQ3 — Validation steps mandatory or best-effort:** the 1C-skills family includes `cfe-validate`, `cf-validate`, `meta-validate`, `form-validate`, `db-update`, etc. Proposal: implementer ATTEMPTS the validation steps that match SDD's `stages[*].verifications`, but records each result in `impl_metadata.validations_attempted[]` with `status: ok|fail|skipped|unavailable` + diagnostic. Hard failure of `cf-validate` blocks DoD only if SDD explicitly listed it as a verification; otherwise it surfaces as `OpenQuestion[severity=decision]`. **No db-update by default** — the implementer is not authorized to mutate live databases in Phase 3; that is operator's call post-merge.
  - **OQ4 — Test DB availability:** none of the three current projects (`example-erp`, `example-trade`, `example-mfg`) have a documented test DB in `projects.yaml`. Proposal: Phase 3 does NOT require test DB; verifications stop at structural validation (cf-validate, cfe-validate) + visual diff. Adding test DB hookup is a future phase. If operator wants live db-update, they run it manually post-Phase-3-DONE.
  - **OQ5 — Rollback policy if validate_impl fails:** implementer wrote a branch + commits; validate_impl exit != 0. Proposal: branch stays; implementer surfaces failure as `impl_metadata.status = "needs_revision"` + `impl_metadata.failures[]`; operator decides — either nudge implementer with retry prompt (max 2 retries, same as Phase 1+2), OR delete branch + redo from analyst, OR accept partial work. validate_impl does NOT delete the branch.
  - **OQ6 — Operator-review gate as a discrete Stage 8?** Phase 3 lifecycle is `IMPLEMENT READY` → validate_impl → ... → operator manually reviews diff → operator merges branch in 1C project → Phase 3 DONE for this task. Should this manual step be encoded as a Stage 8 with its own DoD checklist (e.g. branch URL printed, operator signs off in `tasks/<task_id>/operator_signoff.txt`), or kept implicit (Phase 4 = auditor would formalize it)? Proposal: encode as a thin Stage 8 in Phase 3 with optional signoff file; deeper review tooling is Phase 4 scope.
  - **OQ7 — Out-of-scope edits handling:** SDD lists `stages[*].deliverables` as file paths. Implementer edits a file NOT in any deliverable. Proposal: validate_impl Gate D fails (exit 9) with explicit diff of out-of-scope files. No auto-revert. Operator amends SDD or rejects the work.
  - **OQ8 — Phase 4 (auditor) preview:** does Phase 3 leave hooks for Phase 4? Proposal: `impl_metadata.audit_inputs[]` lists artifacts an auditor would inspect (branch ref, diff stats, validations_attempted). No Phase 4 work in Phase 3; just preserve the surface.

## Step 2 — implement stages

Same chain pattern as Phases 1+2: one Stage = one commit on `master`, push to gitea, merge to `main` at Phase 3 DONE. Each stage closes with `## DONE` on its own line; autonomous-chain hooks pick up next stage.

## Hard rules carried over from Phases 1+2

- AI-to-AI docs (SDD, prompts, skills, memory, RLM) — English, plain text, no emojis unless user requests.
- User-facing chat — Russian, terse, no auto-summaries.
- PS 5.1 only, ASCII-only `.ps1` files (`memory/feedback_powershell_5_1_gotchas.md`).
- Apply FF1-FF8 forcing functions in all SDD writing (`memory/feedback_writer_discipline.md`).
- Definition of Done = merged to main + RLM completion fact + memory update. No "implementation done but not merged".
- Gitea remote = `http://<gitea-host>:3000/admin/Orchestrator`. Token already configured in remote URL.
- Operator mode = ROTATE (autonomous chain enabled). Emit `## DONE` after a stage closes; emit `## CHAIN COMPLETE` only when Phase 3 fully shipped.
- path_local INVARIANT 0c carries forward: `projects.yaml.path_local` mirrors the codemetadata XML index. Implementer SCRIPTS re-enforce this at spawn time.

## NEW hard rules for Phase 3

- **Implementer NEVER pushes to master/main of the 1C project.** Push target is always `orchestrator/<task_id>` (or whatever OQ2 closes to). Operator merges in Gitea UI or via `git merge` in their own session.
- **Implementer NEVER touches `Orchestrator/` files outside `tasks/<task_id>/`.** Validate_impl Gate B enforces.
- **Implementer NEVER runs `db-update` against any 1C base by default.** OQ3 closes this — operator-only post-Phase-3-DONE.
- **Implementer MAY install pip/npm packages in its session.** Same RISK ACCEPTED as Phases 1+2 (`--dangerously-skip-permissions`). Sanity-checked at Stage 6 by diffing pip freeze before/after if operator opts in.
- **Every commit in the implementer's branch must reference task_id in its message.** Convention: `feat(orch <task_id>): <subject>` or `fix(orch <task_id>): <subject>`. Validate_impl checks all commits on the branch for the `orch <task_id>` substring.

## What you do NOT do this session

- Do NOT edit Phase 1+2 artifacts unless Phase 3 design directly forces a contract change. If you find a Phase 1+2 bug, raise it as an Open Question first.
- Do NOT skip Step 0 — that context load is the difference between an implementer that integrates and one that drifts.
- Do NOT make up new MCP servers or tools — verify everything via `tools/list` at runtime. The `1c-skills` family is real (see `~/.claude/1c-development-rules.md`) but their exact surface must be confirmed via <vm-docker-host> MCP `tools/list` before relying on a specific tool name in the prompt or schema.
- Do NOT design Phase 4 (auditor) in this SDD — only preserve the handoff surface per OQ8.

Begin with Step 0 in parallel reads. Report back when you have the SDD draft ready for operator review.
