# Phase 2 kickoff — sdd_writer

You are starting Phase 2 of the Orchestrator project. Phase 1 (analyst) shipped 2026-05-22 at `eccd95c`. Your job is to design AND implement Phase 2 (sdd_writer) using Phase 1 as a structural template.

## Step 0 — load context

Run these reads/queries in parallel before anything else. They are the authoritative inputs:

1. `docs/phase1-analyst-SDD.md` — the contract format Phase 2 must follow (sections §1-§10, FF1-FF8 writer-forcing-functions, stage gates, DoD checklist). Phase 2 must produce its own analogous `docs/phase2-sdd-writer-SDD.md`.
2. `schemas/analysis_v2.py` — the input contract: `AnalysisReport` is what sdd_writer consumes.
3. `prompts/analyst.md` — model the Phase 2 analog `prompts/sdd-writer.md` on this shape.
4. `templates/analyst-CLAUDE.md.tpl` + `templates/analyst-mcp.json.tpl` — model `templates/sdd-writer-CLAUDE.md.tpl` + `templates/sdd-writer-mcp.json.tpl` on these.
5. `scripts/spawn-analyst.ps1` + `scripts/_run-analyst.ps1` + `scripts/peek-analyst.ps1` + `scripts/kill-analyst.ps1` — model the L4 wrappers on these.
6. `~/.claude/projects/<orchestrator-claude-projects-dir>/memory/MEMORY.md` — read all referenced files, especially `project_phase1_done.md`.
7. RLM facts under `domain=tasks module=Orchestrator` via `mcp__rlm-toolkit__rlm_get_facts_by_domain` — at minimum facts `486bd6e3`, `0d131b79`, `fc696e57`.
8. `CLAUDE.md` (project root) — L2 orchestrator instructions; sdd_writer is L3 same as analyst.

## Step 1 — design (no code yet)

Produce `docs/phase2-sdd-writer-SDD.md` mirroring `phase1-analyst-SDD.md`. Must answer:

- **§1 Цель:** sdd_writer consumes `tasks/<task_id>/analysis_report.json` (schema v2) and produces an SDD document for the original task. Output format and storage location are open questions for this design pass.
- **§2 Contract IO:** input shape (AnalysisReport), output shape (some Pydantic model — propose schema_sdd_v1.py?), where it lives on disk.
- **§3 Workflow:** how operator triggers sdd_writer. Spawn-per-task analogous to analyst? OR is sdd_writer non-spawned (runs inline in L2)?
- **§5 Stages:** mirror Phase 1's 0-7 staging — Stage 0 smoke, Stage 1 contracts, Stage 2 schema+prompts, Stage 3 templates, Stage 4 spawn-script, Stage 5 validate-script, Stage 6 e2e, Stage 7 wrappers.
- **§6 Quality gates (MANDATORY for Phase 2 — operational lesson from D1/Stage 6):** sdd_writer's validate.py must check ToolEvidence.queries in the input analysis_report.json reference real MCP tool_use entries in the analyst's session.jsonl, not Bash+curl-synthesized data. Specifically: walk `tasks/<task_id>/<jsonl>`, count `tool_use.name` entries that start with `mcp__`; if 0, exit non-zero with diagnostic. See `project_phase1_done.md` §3 for full rationale.
- **§7 Risks:** carry forward from Phase 1 §7; add anything new.
- **§8 DoD:** mirror Phase 1 DoD shape. Pre-condition 0c (path_local INVARIANT from D2) applies to sdd_writer too — it reads source files via Read tool, must resolve under path_local.
- **§10 Open questions + resolutions:** be aggressive about flushing OQ1-OQN before any Stage 1 work — use FF1-FF8 forcing functions from `docs/writer-forcing-functions.md` (see memory `feedback_writer_discipline.md`).

## Step 2 — implement stages

Same chain pattern as Phase 1: one Stage = one commit on `master`, push to gitea, merge to `main` at Phase 2 DONE. Each stage closes with `## DONE` on its own line; autonomous-chain hooks pick up next stage.

## Hard rules carried over from Phase 1

- AI-to-AI docs (SDD, prompts, skills, memory, RLM) — English, plain text, no emojis unless user requests.
- User-facing chat — Russian, terse, no auto-summaries.
- PS 5.1 only, ASCII-only .ps1 files (`memory/feedback_powershell_5_1_gotchas.md`).
- Apply FF1-FF8 forcing functions in all SDD writing (`memory/feedback_writer_discipline.md`).
- Definition of Done = merged to main + RLM completion fact + memory update. No "implementation done but not merged".
- Gitea remote = `http://<gitea-host>:3000/admin/Orchestrator`. Token already configured in remote URL.
- Operator mode = ROTATE (autonomous chain enabled). Emit `## DONE` after a stage closes; emit `## CHAIN COMPLETE` only when Phase 2 fully shipped.

## What you do NOT do this session

- Do NOT edit Phase 1 artifacts unless Phase 2 design directly forces a contract change (rare). If you find a Phase 1 bug, raise it as an Open Question first.
- Do NOT skip Step 0 — that context load is the difference between sdd_writer that integrates and sdd_writer that drifts.
- Do NOT make up new MCP servers or tools — verify everything via tools/list at runtime (`v3-codemetadata-usage.md` carries the forcing function).

Begin with Step 0 in parallel reads. Report back when you have the SDD draft ready for operator review.
