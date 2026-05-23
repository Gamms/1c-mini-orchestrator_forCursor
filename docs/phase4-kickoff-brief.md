# Phase 4 kickoff — auditor

You are starting Phase 4 of the Orchestrator project. Phases 1+2+3 shipped 2026-05-22:
- Phase 1 (analyst) @ `eccd95c` — read-only L3, produces `analysis_report.json` (schema v2).
- Phase 2 (sdd_writer) @ `ed090ef` — read-only L3, produces `sdd.md` + `sdd_metadata.json` (schema v1).
- Phase 3 (implementer) @ `9d24d51` (+ IOQ1+IOQ2 @ `0307fed`, FF8+baseline @ `37cb56a`) — read+write L3, produces `orchestrator/<task_id>` branch in `path_local` + `impl_metadata.json` (schema v1).

Your job is to **DESIGN** Phase 4 (auditor) — produce `docs/phase4-auditor-SDD.md`. The operator wants to discuss the design first; do NOT start implementation in this session unless the operator explicitly says so.

## What Phase 4 does (the working definition)

The auditor is an independent L3 agent that runs AFTER the implementer completes and BEFORE Stage 8 operator signoff. Its job is to apply auditor-mode optic (depth, defect-search, cold-context, low-trust toward writer/implementer patterns — per `docs/writer-forcing-functions.md` "How the auditor catches what the writer missed" table) to the implementer's output:

- Read `tasks/<task_id>/sdd.md` + `sdd_metadata.json` + `impl_metadata.json` + `impl_metadata.audit_inputs[]`.
- Inspect the branch diff in `path_local` (the actual file edits) against `sdd_metadata.stages[*].deliverables`.
- Re-verify writer/implementer claims via fresh MCP (codemetadata for 1C structural facts, possibly other read-only MCPs).
- Emit an audit verdict.

Phases 1-3 do their own FF1-FF8 self-audit. Phase 4 is the *second opinion* the writer-forcing-functions doc designed `FF1-FF8` against — operational closure of the writer-auditor gap.

## Step 0 — load context (run in parallel before any output)

Authoritative inputs:

1. `docs/phase1-analyst-SDD.md` — original §1-§10 contract format (still the structural template every phase mirrors).
2. `docs/phase2-sdd-writer-SDD.md` — Phase 2 SDD; closest sibling for Phase 4 in structure.
3. `docs/phase3-implementer-SDD.md` — Phase 3 SDD; closest sibling in "we operate on path_local" semantics.
4. `docs/phase2-kickoff-brief.md` + `docs/phase3-kickoff-brief.md` — model the Phase 4 kickoff on these.
5. `docs/writer-forcing-functions.md` — FF1-FF8 + the writer-vs-auditor optic table. This doc is the *charter* for Phase 4: the gap it names is what Phase 4 closes operationally.
6. `schemas/analysis_v2.py` + `schemas/sdd_v1.py` + `schemas/impl_v1.py` — three input contracts already in scope; `audit_v1.py` is the new output schema you will propose.
7. `prompts/analyst.md` + `prompts/sdd-writer.md` + `prompts/implementer.md` — model `prompts/auditor.md` on these.
8. `templates/{analyst,sdd-writer,implementer}-CLAUDE.md.tpl` + `templates/{analyst,sdd-writer,implementer}-mcp.json.tpl` — model `templates/auditor-*` on these.
9. `scripts/spawn-{analyst,sdd-writer,implementer}.ps1` + `scripts/_run-*.ps1` + `scripts/peek-*.ps1` + `scripts/kill-*.ps1` + `scripts/_python/validate.py` + `validate_sdd.py` + `validate_impl.py` — model the L4 wrappers on these.
10. `~/.claude/projects/<orchestrator-claude-projects-dir>/memory/MEMORY.md` — read every entry, especially `project_phase3_done.md` (full Phase 3 surface + example-erp-02 closure) and `project_utp02_phase3_e2e.md` (the e2e that exercised the chain end-to-end).
11. RLM facts under `domain=retrospective module=Orchestrator` via `mcp__rlm-toolkit__rlm_get_facts_by_domain` — at minimum `b4ec12c2` (example-erp-02 e2e PASS + harness findings + master merge), `68812487` (FF8 causal decision), `fceec770` (harness findings closed + main promoted), plus the Phase 1-3 ship facts.
12. `CLAUDE.md` (project root) — L2 orchestrator instructions; auditor is L3 same as analyst / writer / implementer.
13. `~/.claude/1c-development-rules.md` — 1C validation skill surface; the auditor consumes the same surface read-only.
14. `projects.yaml` — `path_local` is what the auditor inspects (read-only). INVARIANT 0c carries forward.

## Step 1 — design (no code yet)

Produce `docs/phase4-auditor-SDD.md` mirroring `phase3-implementer-SDD.md` §1-§11. The operator will sign off on the SDD before any code is written.

The design MUST resolve these open questions in §10 before Stage 1:

- **OQ1 — Spawn model.** wt-tab-per-task (mirroring all 3 prior phases) vs. in-process inside L2 (faster, no terminal) vs. Agent tool subagent (single Claude session, isolated context). Each has tradeoffs: separate tab gives clean session.jsonl partition for MCP-real-usage gates carried forward from Phases 1-3 (currently `validate_impl` exits 6/7/8 check analyst/writer/impl session MCP usage; auditor would add exit X for itself); in-process is trivially fast but shares session.jsonl with L2 and breaks the partitioning model; Agent subagent has its own session.jsonl tree but the auditor's "cold context, low trust" optic depends on being a fresh process, which Agent gives.
- **OQ2 — Pass/fail criteria.** What makes an audit "rejected"? Candidates: (a) any FF1-FF8 row marked `fail` by auditor; (b) any sdd_metadata.dod_post regex that doesn't actually match the committed deliverable (the FF8 check, but executed by auditor instead of trusting writer's self-audit); (c) any out-of-scope edit not surfaced as an implementer OpenQuestion; (d) any commit that violates the REFUSE list in `prompts/implementer.md` (e.g. db-update, git filter-branch); (e) operator-defined severity threshold.
- **OQ3 — Output schema.** Propose `schemas/audit_v1.AuditReport`. Fields likely needed: `task_id`, `verdict ∈ {ack, request_changes, reject}`, `findings: list[AuditFinding]` (each with `severity ∈ {info, decision, blocker}`, `surface ∈ {sdd, impl, both}`, `description`, `evidence`), `ff_re_audit: dict[FF1..FF8, FFOutcome]` (auditor re-runs the writer's self-audit), `re_verifications_attempted: list[ValidationAttempt]` (auditor re-issues at least the mandatory verifications from `sdd_metadata.stages[*].verifications`), `audit_self_review_notes`. Verify against the patterns in `schemas/{sdd,impl}_v1.py`.
- **OQ4 — Re-prompt vs. operator escalation.** If audit_verdict = `request_changes`, does L2 automatically re-prompt the implementer (max 2 retries like validate_impl) or always escalate to operator? The Phase 3 retry table currently re-prompts on validate_impl exits 1-13; auditor verdicts are subtler than schema/Gate failures, lean operator-decision.
- **OQ5 — MCP surface.** codemetadata (read 1C structural facts) almost certainly yes. `1c-skills` family (write-side: cfe-init, meta-edit, etc.) — auditor is read-only, so likely NO. But validation skills (cf-validate, cfe-validate, meta-validate, form-validate, role-validate, mxl-validate, skd-validate) are read-only checks the auditor SHOULD re-run independently of `impl_metadata.validations_attempted`. Decide: full validation skill surface, or codemetadata-only?
- **OQ6 — Relationship to validate_impl.** Phase 3 ships 14 validate_impl exit codes (0=OK + 1-13 various Gate / schema / MCP / status failures). Phase 4 auditor: (a) runs AFTER validate_impl returns 0 (cheap stuff first, auditor is the expensive depth pass); (b) runs INSTEAD of validate_impl for hard-to-automate checks; (c) supersedes — auditor verdict is final, validate_impl becomes pre-flight. Recommend (a).
- **OQ7 — Stage 8 operator signoff integration.** Currently Stage 8 = operator writes `tasks/<task_id>/operator_signoff.txt` after manually reviewing diff. Phase 4 changes this to: operator reads `audit_report.json` first, then writes signoff (and can override audit_verdict). Encode this in Phase 4 SDD §8 DoD.
- **OQ8 — Audit artifact storage.** Mirror prior phases: `tasks/<task_id>/audit_report.json` + `audit_raw/<server>/r<round>-q<idx>-<sha12>.json` for each fresh MCP call.
- **OQ9 — Model selection.** Phases 1-3 are model-agnostic at the prompt level but in practice user is on Opus 4.7. Auditor's optic (low-trust, depth, cold-context) maps onto Opus capability; but a stronger argument: auditor should be a DIFFERENT model class from writer/implementer to reduce the "same blind spots" risk. Decide.
- **OQ10 — Out-of-scope for Phase 4.** Likely deferred: (a) auto-merge of `orchestrator/<task_id>` into master/main of the 1C project (always operator scope), (b) cross-task audit (auditor sees only one task at a time, not a release-branch sweep), (c) live 1C base mutation (forbidden, same as Phase 3), (d) writer/implementer re-spawn (auditor's job is to verdict, not to re-do).

## Step 2 — implement stages (deferred until SDD is signed off)

Stage map proposal (operator will adjust during design discussion):
- Stage 0: smoke wrappers
- Stage 1: `schemas/audit_v1.py` + N fixtures
- Stage 2: `prompts/auditor.md`
- Stage 3: templates
- Stage 4: `spawn-auditor.ps1` + `_run-auditor.ps1`
- Stage 5: `scripts/_python/validate_audit.py` + N fixtures
- Stage 6: e2e on a known-good task (likely re-run `tasks/2026-05-22-example-erp-02` or a new task) — auditor independently confirms what validate_impl exit-0 said
- Stage 7: `peek-auditor.ps1` + `kill-auditor.ps1`
- Stage 8 update: extend operator-signoff format to include `audit_verdict_at_signoff` field

## Hard rules carried over from Phases 1-3

- AI-to-AI docs (SDD, prompts, skills, memory, RLM, kickoff briefs) — English, plain text, no emojis unless user requests.
- User-facing chat — Russian, terse, no auto-summaries.
- PS 5.1 only, ASCII-only `.ps1` (`memory/feedback_powershell_5_1_gotchas.md`).
- Apply FF1-FF8 forcing functions in all SDD writing.
- Definition of Done = merged to main + RLM completion fact + memory update. No "done but not merged".
- Gitea remote = `http://<gitea-host>:3000/admin/Orchestrator`. Token already configured.
- Operator mode = check `~/.claude/.autonomous-off` marker; respect NORMAL until operator flips to ROTATE.
- path_local INVARIANT 0c carries forward — auditor reads `path_local` but never writes there (and never to master/main of the 1C project).

## NEW hard rules introduced by Phase 4

- **Auditor is fully read-only.** No edits to `path_local`, no edits to `Orchestrator/` outside `tasks/<task_id>/audit_report.json` + `audit_raw/`. Carries forward Phase 1's read-only stance, NOT Phase 3's read+write stance. Encode this in REFUSE section of `prompts/auditor.md` mirroring Phase 1.
- **Independence requirement.** The auditor MUST issue at least one fresh MCP query against codemetadata or a validation skill that the implementer's session.jsonl shows the implementer did NOT issue. "Independence" means the auditor doesn't trust the implementer's MCP record; it goes back to the source. Operational gate candidate: `validate_audit` exit X if auditor's MCP queries are a subset of implementer's (the auditor added zero new evidence).
- **No re-prompt loop with implementer.** Phase 3 retries via validate_impl exits 1-13 happen BEFORE auditor runs. Auditor either acks, requests_changes (operator escalates), or rejects (terminal verdict). No machine loop between auditor and implementer.

## What this session does NOT do

- Do NOT skip Step 0 — context load is the difference between an auditor that integrates and one that drifts.
- Do NOT make up MCP servers/tools — verify via `tools/list` at runtime.
- Do NOT start Stage 1 code until operator signs off on `docs/phase4-auditor-SDD.md`.
- Do NOT change Phase 1/2/3 prompts or schemas unless Phase 4 forces a contract change; if you find a Phase 1-3 bug, raise it as an OQ first.
