# Phase 5 kickoff -- hardening and wrapper consolidation

You are starting Phase 5 of the Orchestrator project. Phases 1+2+3+4 shipped 2026-05-22:

* Phase 1 (analyst) @ `eccd95c` -- read-only L3, produces `analysis_report.json` (schema v2).
* Phase 2 (sdd_writer) @ `ed090ef` -- read-only L3, produces `sdd.md` + `sdd_metadata.json` (schema v1).
* Phase 3 (implementer) @ `9d24d51` (+ IOQ @ `0307fed`, FF8+baseline @ `37cb56a`) -- read+write L3, produces `orchestrator/<task_id>` branch in `path_local` + `impl_metadata.json` (schema v1).
* Phase 4 (auditor) @ `5213edc` -- read-only L3 on codex runtime, produces `audit_report.json` (schema v1) + operator_signoff convention `audit=<verdict>`.

NOTE: Phase 4 SDD §10 sketched "Phase 5 = rotation". That is REDEFERRED to a later phase. Phase 5 as scoped in this brief = two Phase 4 follow-ups (mirror hardening + wrapper consolidation). Rotation work stays a separate future phase.

## What Phase 5 does

Two orthogonal groups, both flagged by Phase 4 close-out (`project_phase4_done.md` "Phase 5 follow-ups" list):

### Group A -- mirror CRLF/LF hardening

Phase 4 Stage 6 e2e on `2026-05-22-example-erp-02` caught a true contract violation that turned out to be a Windows/Git artefact, not a semantic defect:

* implementer-local `attributes_summary.md`: 5851 bytes, LF, SHA256 `33CA25E2...`
* committed mirror in example-erp-src (after autocrlf=true rewrite): 5881 bytes, CRLF, SHA256 `2E5F2B8F...`

The implementer's `validations_attempted[6]` claimed `cmp identical`, but a fresh sha256 hash post-checkout falsified it. The auditor correctly flagged it as a blocker (severity=blocker, FF7=fail), driving `computed_verdict=reject`. Operator overrode via Stage 8 convention with an explicit `audit=override:LF-vs-CRLF drift is a core.autocrlf artefact`.

Group A goal: make the mirror byte-identity post-condition immune to autocrlf so that future e2e runs do not produce false rejects on this axis.

### Group C -- phase-agnostic peek/kill wrappers

After Phase 4, the wrapper surface is 4 near-duplicate pairs:

* `peek-analyst.ps1` / `kill-analyst.ps1`
* `peek-sdd-writer.ps1` / `kill-sdd-writer.ps1`
* `peek-implementer.ps1` / `kill-implementer.ps1`
* `peek-auditor.ps1` / `kill-auditor.ps1`

Three of the four pairs share an identical body (claude jsonl discovery + tail), differing only in packet filename and wt title prefix. The fourth (auditor) routes to a different parser (codex rollout via `_codex_rollout.py`) but has the same packet/title pattern.

Group C goal: consolidate to `peek-task.ps1` + `kill-task.ps1` that auto-detect the active phase from packet presence (analyst -> writer -> implementer -> auditor) and dispatch to the correct parser. Old 8 wrappers deprecated to thin forwarding shims for one release; deletion deferred to a later phase if any operator workflow still calls them.

## Why both groups in Phase 5 (not separate phases)

* Both are pure cleanup of Phase 4 close-out follow-ups.
* They share no file overlap -- can be implemented and reviewed independently within the same chain.
* Each is too small to justify its own SDD; bundled they make one coherent "Phase 4 hardening" deliverable.
* Phase 4 SDD §10 OQ4-OQ10 closed all real Phase 4 OQs; "rotation" was a forward-looking phase-5 placeholder, not a Phase 4 follow-up.

## Out of scope for Phase 5

* Rotation / autonomous chain orchestration (Phase 4 SDD's original Phase 5 sketch). Deferred to a later phase.
* meta-auditor (auditor-of-auditor). Phase 4 close-out flagged as theoretical until severity under-grading observed in real e2e statistics; not adding without evidence.
* `validate-signoff.ps1` enforcer for `operator_signoff.txt` convention. Convention is documented (Phase 4 Stage 8) and operator currently disciplined; enforcer can wait until convention drift is observed.
* strict subset-check of audit `re_verifications` vs `impl_metadata.validations_attempted` (Phase 4 only checks coverage of mandatory entries). Deferred to whichever later phase has a real driver.
* Editing Phase 1+2+3 artifacts beyond what mirror hardening forces (implementer prompt + skill change; SDD section update if any post-condition wording changes).

## Carry-forwards from Phases 1+2+3+4

* PowerShell 5.1 only, ASCII-only `.ps1` files [VERIFIED via `memory/feedback_powershell_5_1_gotchas.md`].
* Per-task CWD = `tasks/<task_id>/`, rendered `CLAUDE.md` + MCP config per task.
* path_local INVARIANT (0c): `projects.yaml.path_local` mirrors codemetadata XML index.
* FF1-FF8 forcing functions per `docs/writer-forcing-functions.md` apply to every artifact Phase 5 produces.
* Operational quality gate: every L3 session.jsonl (claude) or codex rollout must show >=1 MCP `tool_use`. validate_impl / validate_audit gates unchanged.
* Stage 8 operator_signoff convention from Phase 4: `audit=<verdict>` suffix required.
