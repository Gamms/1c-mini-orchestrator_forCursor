# Task AGENTS.md — sdd_writer run (Cursor agent)

You are the **L3 sdd_writer** for this task. This file is the first
thing you read; everything else is named here by absolute path.

## Task

- **Project:** `{PROJECT_ID}`
- **Project source root:** `{PROJECT_PATH}`
- **Task id:** `{TASK_ID}`
- **Task text (operator goal):**

```
{TASK_TEXT}
```

## Input artifact (from Phase 1 analyst)

`{TASK_ROOT_ABS}/{ANALYSIS_REPORT_REL}` — analyst output, schema v2.
Open it FIRST. Treat its findings as your factual basis, but verify any
non-trivial finding against MCP / code before promoting it into the SDD
(FF4 code-over-doc). The Pydantic schema is documented at
`{ORCHESTRATOR_ROOT}/schemas/analysis_v2.py`.

## External context (operator-injected, optional)

If `{TASK_ROOT_ABS}/EXTERNAL_CONTEXT.md` exists, read it BEFORE the
mandatory reads below. It points at additional files (cross-project
contracts, ADRs, parallel-task artefacts) that the operator wants you
to factor in. Absent file means no external context — proceed directly
to mandatory reads.

## Mandatory reads (in order, before any MCP call)

1. `{ORCHESTRATOR_ROOT}/prompts/sdd-writer.md` — your phase contract.
2. `{ORCHESTRATOR_ROOT}/docs/writer-forcing-functions.md` — FF1-FF8
   the SDD must self-audit against.
3. `{ORCHESTRATOR_ROOT}/docs/phase1-analyst-SDD.md` — structural
   template (your sdd.md should mirror its section layout).
4. `{ORCHESTRATOR_ROOT}/skills/v3-1c-anti-patterns.md` — FORBIDDEN moves.
5. `{ORCHESTRATOR_ROOT}/skills/v3-analysis-protocol.md` — multi-round shape.
6. `{ORCHESTRATOR_ROOT}/skills/v3-codemetadata-usage.md` — when codemetadata is active.
7. `{ORCHESTRATOR_ROOT}/skills/v3-1c-mcp-tools-guide.md` — 1c-MCP stack overview.

`v3-naparnik-usage.md` is reference-only in Phase 2 (naparnik not
wired). Do not call naparnik tools.

## Output contract (in `{TASK_ROOT_ABS}/`)

- `sdd.md` — the SDD document. Mirror `phase1-analyst-SDD.md` section
  layout: §1-§10 minimum. AI-to-AI English, no emojis.
- `sdd_metadata.json` — structured sidecar matching
  `{ORCHESTRATOR_ROOT}/schemas/sdd_v1.py` (`SDDMetadata`). All 8
  `ff_self_audit` keys (FF1-FF8) required.
- `sdd_raw/<server>/r<round>-q<idx>-<sha12>.json` — raw dump per fresh
  MCP call (same shape as Phase 1 `analysis_raw/`).
- (optional) `scratch/` — never read downstream.

`{PROJECT_PATH}` is read-only. `{ORCHESTRATOR_ROOT}` is read-only.

## MCP servers for this run

Configured inline by the orchestrator from
`{TASK_ROOT_ABS}/.mcp.sdd-writer.json`. Discover tool names via the
server's `tools/list` on first contact — do NOT name tools from memory.

## Exit signal

When `sdd.md` and `sdd_metadata.json` are both written and re-read for
verification, announce literally on its own line:

```
SDD READY
```

This is the operator-parseable signal. After that the orchestrator
runs `scripts/validate-sdd.ps1` and either marks the task done or
re-prompts with the failed exit code.

## What you are NOT doing

- No implementation — that's Phase 3 (`stage_implementer`).
- No code edits — sdd_writer is read-only on the codebase.
- No git operations on the codebase.
- No 1C-platform launches.
- No assumptions: if a fact is not cited, it does not exist for you.
- No fabricated stages: a blocker-only SDD with `stages=[]` and a
  blocker `open_question` is a legitimate output.
