# SDD -- Orchestrator, Phase 4: auditor chain

**task_id:** `orch-phase4-auditor-2026-05-22`
**task_size:** L (new L3 runtime -- codex instead of claude; new MCP-gate parser; new severity-to-verdict deterministic compute; modifies Stage 8 operator_signoff format established in Phase 3)
**author:** Claude (L2 in this Orchestrator session, parent of Phase 4 chain)
**date:** 2026-05-22
**status:** draft for operator review

---

## 1. Context and goal

Phase 1 (analyst) shipped 2026-05-22 at `eccd95c`; Phase 2 (sdd_writer) shipped 2026-05-22 at `ed090ef`; Phase 3 (implementer) shipped 2026-05-22 at `9d24d51` (+ IOQ1+IOQ2 at `0307fed`, FF8+baseline at `37cb56a`). Together they produce, per task: `tasks/<task_id>/analysis_report.json`, `tasks/<task_id>/sdd.md` + `tasks/<task_id>/sdd_metadata.json`, branch `orchestrator/<task_id>` in `<path_local>` + `tasks/<task_id>/impl_metadata.json`. Phase 4 builds the next link: an L3 **auditor** that consumes that whole bundle and produces an independent second-opinion verdict before Stage 8 operator signoff.

**Goal of Phase 4:** auditor only. After it lands, Phase 5 (rotation) opens.

**Out of scope for Phase 4:**
- Rotation / Remote toggle (Phase 5)
- L1 orchestration (always the user)
- Editing Phase 1+2+3 artifacts unless a contract change is forced (see §10 -- only `operator_signoff.txt` format extension is forced)
- Live database mutation (forbidden by Phase 3 carry-forward; auditor is read-only beyond that)
- Auto-merge of `orchestrator/<task_id>` to master/main (operator-only, carry-forward)
- Auditor re-spawning the writer or implementer (auditor produces verdict, does not re-do)
- Cross-task / release-branch sweep (auditor sees one task at a time)
- New MCP servers beyond codemetadata (read-only structural facts about `<path_local>`)
- claude-skills (1c-skills family). Codex runtime does NOT support claude-skills; auditor independence is established via direct codemetadata MCP reads, not via re-running validate skills. [VERIFIED via `~/.claude/projects/.../memory/feedback_phase4_spawn_model.md` + RLM Phase 4 design session.]

**Carry-forwards from Phases 1+2+3:**
- Spawn-per-task in a fresh `wt` tab, file-only L2<->L3 protocol
- Per-task CWD = `tasks/<task_id>/`, rendered `CLAUDE.md` + MCP config per task (auditor-specific variants)
- `--add-dir <path_local>` + `--add-dir <orchestrator_root>` (codex form: `--cd <task_root> --add-dir ...`)
- Pre-trust patterns (not directly applicable to codex -- see §2 table)
- PowerShell 5.1 only, ASCII-only `.ps1` files [VERIFIED via `memory/feedback_powershell_5_1_gotchas.md`]
- path_local INVARIANT (0c): `projects.yaml.path_local` mirrors codemetadata XML index. spawn-auditor.ps1 fail-fasts identically to Phases 1+2+3.
- FF1-FF8 forcing functions per `docs/writer-forcing-functions.md` apply to every artifact produced this phase.
- Operational quality gate: every prior session.jsonl + the auditor's own codex rollout must show >=1 MCP `tool_use`. validate_audit extends the triple-fan from validate_impl into a quad-fan (analyst exit 6, writer exit 7, implementer exit 8, auditor exit 9-style code per §5).

---

## 2. Constraints and decisions

| Constraint | Decision |
|---|---|
| Auditor runtime: claude vs codex | **Codex (`codex exec`).** Two reasons: (a) cold-context second-opinion optic benefits from a different model class than the one that produced the artifacts (writer+implementer ran on Opus 4.7); (b) Phase 4 closes the writer-auditor gap from `docs/writer-forcing-functions.md` -- different runtime = harder to inherit Opus's blind spots. Codex CLI 0.130.0 at `~/AppData/Roaming/npm/codex`. Default model from `~/.codex/config.toml`. [VERIFIED via `memory/feedback_phase4_spawn_model.md`] |
| Spawn model | **wt-tab-per-task, mirroring Phases 1-3.** NOT Agent subagent (`codex:codex-rescue`). Reasons: async observability via `peek-auditor.ps1`; parity with Phases 1-3 5-script pattern; Phase 5 rotation will restart L2 sessions and wt-process survives /clear; operational MCP-usage gate reads codex rollout file, not Agent subagent's in-conversation tool_use record. [VERIFIED via `memory/feedback_phase4_spawn_model.md`] |
| Auditor input set | reads `tasks/<task_id>/sdd.md` + `sdd_metadata.json` + `impl_metadata.json` + `analysis_report.json` + `impl_metadata.audit_inputs[]` references + git diff of branch `orchestrator/<task_id>` against `impl_metadata.diff_baseline.before_sha` in `<path_local>`. |
| Auditor write surface | **READ-ONLY beyond `tasks/<task_id>/audit_report.json` + `tasks/<task_id>/audit_raw/` + `tasks/<task_id>/audit.log` + `tasks/<task_id>/audit.status`.** No edits in `<path_local>` (not even git tags / notes). No edits in `Orchestrator/` outside the task root. Carries forward Phase 1 read-only stance (NOT Phase 3 read+write stance). Enforced via prompt REFUSE section + validate_audit Gate B. |
| MCP surface | **codemetadata-only.** Codex does not have claude-skills (1c-skills family is claude plugin); ssh-to-<vm-docker-host> for live 1C-validators (B-option in design discussion) was rejected (blast radius + stateful 1C-bases + zero independence gain). Auditor re-verifies SDD/impl claims by direct codemetadata reads (`get_object`, `list_attributes`, `get_form_layout`, etc.) instead of running validation skills. [VERIFIED via OQ5 closure 2026-05-22] |
| MCP independence gate (v1, weak) | validate_audit parses `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl` for the auditor's session; >=1 mcp tool_use entry required; zero -> exit code. Strict version (auditor's MCP queries must include at least one NOT in implementer's rollout) is deferred to Phase 5. [VERIFIED via `memory/feedback_phase4_independence_gates.md`] |
| Re-verification coverage gate | For each `impl_metadata.validations_attempted[v]` where `v.mandatory==true`, `audit_report.re_verifications_attempted[]` MUST contain a matching entry (by `name`). Missing coverage -> validate_audit gate fail (exit code) with "blocker: missing_verification: <name>" diagnostic. Empty case: if `impl_metadata.validations_attempted=[]`, auditor's `re_verifications_attempted=[]` is fine. [VERIFIED via `memory/feedback_phase4_independence_gates.md`] |
| Verdict split | **Two-layered.** Codex sets per-finding severity (info / decision / blocker) -- judgment. Codex also sets `recommended_verdict` (ack / request_changes / reject) -- advisory. validate_audit computes `computed_verdict` deterministically: >=1 blocker -> reject; >=1 decision (no blocker) -> request_changes; else -> ack. Computed wins; recommended is logged for operator visibility. [VERIFIED via `memory/feedback_phase4_verdict_split.md`] |
| No re-prompt loop with implementer | Auditor verdict `request_changes` or `reject` -> **operator escalation** (never auto re-prompt the implementer). Reasons: codex and claude are different runtimes with file-only protocol; auditor findings are subtler than validate_impl's deterministic exit codes; Phase 3 retry budget already runs BEFORE auditor (validate_impl must return 0 to permit auditor spawn). Auto re-prompt is Phase 5 territory. [VERIFIED via OQ4 closure] |
| validate_impl ordering | **validate_impl FIRST, auditor SECOND.** Auditor spawn is permitted only on tasks where `validate-impl.ps1 -TaskId <id>` returns 0. Reasons: cheap-first economics (auditor ~minutes + tokens vs validator ~seconds); auditor "depth-on-green" optic; Phase 3 retry loop isolated from Phase 4. spawn-auditor.ps1 pre-checks validate_impl pass before spawning. [VERIFIED via OQ6 closure] |
| Output format | One file: `tasks/<task_id>/audit_report.json` (Pydantic-validated, schema_audit_v1). Plus `tasks/<task_id>/audit_raw/<server>/r<round>-q<idx>-<sha12>.json` per MCP call (FF2 / independence audit trail). Plus `audit.log` + `audit.status` (peek/kill plumbing, mirroring Phase 3). |
| Schema for sidecar | New `schemas/audit_v1.py` -- standalone Pydantic v2, no <prior-iteration> imports, extra="forbid". Mirrors sdd_v1 + impl_v1 hygiene. FF2 applies: Citation + FFOutcome + ValidationAttempt shapes are DUPLICATED (not imported from sdd_v1 / impl_v1). |
| Stage 8 operator-signoff extension | `tasks/<task_id>/operator_signoff.txt` recommended format extends from `^(approved <commit>|rejected: <reason>)$` to `^(approved <commit> audit=<verdict>(?:[:]?<note>)?|rejected: <reason> audit=<verdict>)$` where `<verdict> in {ack, request_changes, reject, override}`. `override` means operator signed off despite computed_verdict != ack -- must include note. Convention-only (no enforcing validator in Phase 4; future Phase 5 may add). [VERIFIED via OQ7 closure] |
| --dangerously-bypass-approvals-and-sandbox | Codex flag analog of claude's --dangerously-skip-permissions. Same blast radius profile. Mitigations: Gate B (no writes to Orchestrator/ outside tasks/<task_id>/); auditor prompt REFUSE section explicitly enumerates write-side surfaces; codex session runs on operator's laptop, no live-DB / VPN access required by design. |
| Wrappers `peek-auditor.ps1` / `kill-auditor.ps1` | Phase-specific copies of Phase 1+2+3 wrappers. wt window title = `auditor:<task_id>`. Code duplication acknowledged; merging into phase-agnostic `peek-task.ps1` / `kill-task.ps1` is Phase 5 tech-debt cleanup, NOT this phase (FF8: don't refactor beyond what task requires). |
| Codex rollout file parser | New `scripts/_python/_codex_rollout.py` (sibling of `_session_jsonl.py`). Single source of truth for parsing `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`. Used by `validate_audit.py` for MCP-gate count and (future Phase 5) for strict subset-check. |
| Retry budget on validate failure | Same envelope as Phases 1-3: max 2 retries via operator nudge. If validate_audit exits with verdict != 0 due to coverage gap / Pydantic / Gate B, operator decides nudge vs delete-and-re-spawn vs accept partial. Verdict-driven exits (request_changes / reject from severities) are NOT retryable by L2 -- operator escalation only (no machine loop). |
| Model | Default codex model from `~/.codex/config.toml`. Operator may override via `-Model <name>` switch in spawn-auditor.ps1 (passed to `codex exec -m <model>`). |
| Auditor inspects branch at known sha | `audit_report.branch_sha_audited` captures the tip of `orchestrator/<task_id>` at audit-start time. validate_audit Gate A: this sha == current tip of `orchestrator/<task_id>` at validate-time (no commits added in between). If different, exit code (stale audit). Operator re-spawns auditor against fresh tip. |

---

## 3. Repo layout after Phase 4

```
Orchestrator/
|-- CLAUDE.md                                 # (unchanged) L2 router contract
|-- README.md                                 # (updated) Phase 4 entry points added
|-- projects.yaml                             # (unchanged)
|-- pyproject.toml                            # (unchanged -- pydantic already covers Phase 4)
|-- docs/
|   |-- phase1-analyst-SDD.md                 # (unchanged)
|   |-- phase2-sdd-writer-SDD.md              # (unchanged)
|   |-- phase3-implementer-SDD.md             # (unchanged)
|   |-- writer-forcing-functions.md           # (unchanged -- referenced from prompts/auditor.md)
|   |-- phase4-kickoff-brief.md               # (unchanged -- input to this SDD)
|   |-- phase4-auditor-SDD.md                 # this document
|   `-- audit-phase4.md                       # NEW (operator-triggered post-Stage-6)
|-- prompts/
|   |-- analyst.md                            # (unchanged)
|   |-- sdd-writer.md                         # (unchanged)
|   |-- implementer.md                        # (unchanged)
|   `-- auditor.md                            # NEW
|-- skills/                                   # (unchanged -- same 5 claude skills; auditor runs in codex so does not use them)
|-- schemas/
|   |-- analysis_v2.py                        # (unchanged)
|   |-- sdd_v1.py                             # (unchanged)
|   |-- impl_v1.py                            # (unchanged)
|   `-- audit_v1.py                           # NEW -- sidecar contract
|-- templates/
|   |-- analyst-CLAUDE.md.tpl                 # (unchanged)
|   |-- analyst-mcp.json.tpl                  # (unchanged)
|   |-- sdd-writer-CLAUDE.md.tpl              # (unchanged)
|   |-- sdd-writer-mcp.json.tpl               # (unchanged)
|   |-- implementer-CLAUDE.md.tpl             # (unchanged)
|   |-- implementer-mcp.json.tpl              # (unchanged)
|   |-- auditor-CLAUDE.md.tpl                 # NEW -- first-thing-auditor-reads
|   `-- auditor-codex.toml.tpl                # NEW -- codex MCP/profile snippet (TOML, NOT JSON; codex config syntax)
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
|   |-- spawn-implementer.ps1                 # (unchanged)
|   |-- _run-implementer.ps1                  # (unchanged)
|   |-- peek-implementer.ps1                  # (unchanged)
|   |-- kill-implementer.ps1                  # (unchanged)
|   |-- validate-impl.ps1                     # (unchanged)
|   |-- spawn-auditor.ps1                     # NEW
|   |-- _run-auditor.ps1                      # NEW
|   |-- peek-auditor.ps1                      # NEW
|   |-- kill-auditor.ps1                      # NEW
|   |-- validate-audit.ps1                    # NEW
|   |-- _run-smoke.ps1                        # (unchanged)
|   `-- _python/
|       |-- yaml_get.py                       # (unchanged)
|       |-- validate.py                       # (unchanged)
|       |-- validate_sdd.py                   # (unchanged)
|       |-- validate_impl.py                  # (unchanged)
|       |-- _session_jsonl.py                 # (unchanged -- claude session.jsonl parser)
|       |-- _codex_rollout.py                 # NEW -- codex rollout-file parser
|       |-- validate_audit.py                 # NEW -- audit + cross-checks four sessions (analyst/writer/impl claude.jsonl + auditor codex rollout)
|       |-- _test_schema.py                   # (unchanged)
|       |-- _test_templates.py                # (extended -- adds auditor template fixtures)
|       |-- _test_validate.py                 # (unchanged)
|       |-- _test_sdd_schema.py               # (unchanged)
|       |-- _test_validate_sdd.py             # (unchanged)
|       |-- _test_impl_schema.py              # (unchanged)
|       |-- _test_validate_impl.py            # (unchanged)
|       |-- _test_audit_schema.py             # NEW -- audit_v1 fixtures
|       |-- _test_validate_audit.py           # NEW -- exit-code fixtures
|       `-- _test_codex_rollout.py            # NEW -- rollout parser fixtures
`-- tasks/                                    # (gitignored, unchanged shape)
```

Net NEW files: 13 (2 templates, 1 prompt, 1 schema, 5 ps1, 4 python tests + 1 python validator + 1 python helper). Net edits: 2 files (`scripts/_python/_test_templates.py` extends; `README.md` lists new entry points).

**Per-auditor-run artifacts under `tasks/<task_id>/`:**
- `audit_report.json` -- the deliverable.
- `audit_raw/<server>/r<round>-q<idx>-<sha12>.json` -- one file per MCP query.
- `auditor_packet.json` -- spawn-side metadata (created_at, wt_window_title, codex_session_id, model, before_sha_at_audit_start).
- `CLAUDE.auditor.md` -- rendered template.
- `auditor.codex.toml` -- rendered codex profile (per-task isolation).
- `prompt.auditor.md` -- one-liner pointing at CLAUDE.auditor.md.
- `audit.log` + `audit.status` -- peek/kill plumbing.

**No artifacts in `<path_local>` -- auditor is fully read-only there.**

---

## 4. End-to-end flow

```
[Operator in this Orchestrator L2 session]
    -> "Auditor on 2026-05-22-example-erp-02" (or equivalent)
[Claude = L2]
    1. Resolve task_id -> tasks/<task_id>/ on disk
    2. Pre-check: sdd.md AND sdd_metadata.json AND impl_metadata.json AND analysis_report.json all exist
       AND validate-sdd.ps1 -TaskId <id> exits 0
       AND validate-impl.ps1 -TaskId <id> exits 0
       (auditor refuses to start without all four upstream artifacts and green machine gates on impl)
    3. Spawn scripts/spawn-auditor.ps1 -TaskId 2026-05-22-example-erp-02
        |-- reads tasks/<task_id>/task_packet.json + sdd_writer_packet.json + implementer_packet.json
        |-- resolves <path_local> via projects.yaml
        |-- captures current tip of orchestrator/<task_id> in <path_local> -> before_sha_at_audit_start
        |-- pre-check: validate-impl.ps1 -TaskId <id> exits 0 (FAIL -> exit code, no spawn)
        |-- pre-check: branch orchestrator/<task_id> exists in <path_local> and pushed to gitea
        |-- pre-check: <path_local> git status clean (matches impl_metadata.diff_baseline.orchestrator_after; if changed, exit code)
        |-- pre-check: tasks/<task_id>/audit_report.json absent OR -Force passed
        |-- renders templates/auditor-CLAUDE.md.tpl -> tasks/<task_id>/CLAUDE.auditor.md
        |-- renders templates/auditor-codex.toml.tpl -> tasks/<task_id>/auditor.codex.toml
        |-- writes tasks/<task_id>/auditor_packet.json (auditor-side metadata)
        |-- writes tasks/<task_id>/prompt.auditor.md
        |-- creates tasks/<task_id>/audit_raw/ directory
        `-- wt.exe -w 0 nt --title "auditor:<task_id>" powershell.exe -File _run-auditor.ps1 ...
[auditor in new wt tab]
    - reads CLAUDE.auditor.md (role + context + read-only contract + verdict-split rule)
    - reads prompts/auditor.md (phase contract; includes FF1-FF8 re-audit checklist + REFUSE + severity rubric)
    - reads sdd.md + sdd_metadata.json + impl_metadata.json + analysis_report.json (cold context)
    - cd <task_root>
    - For each impl_metadata.validations_attempted[v] where v.mandatory == true:
        - Re-runs the equivalent verification via codemetadata MCP (NOT 1c-skills -- codex has no skills)
        - Records outcome in audit_report.re_verifications_attempted[]
    - For each FF1-FF8 row in implementer's ff_self_audit (and sdd_metadata's writer FF self-audit):
        - Re-audits with cold-context optic
        - Records outcome in audit_report.ff_re_audit[]
    - For each sdd_metadata.dod_post regex:
        - Re-runs against the actual committed branch state (self-grep over <path_local>)
        - Mismatch -> finding with category=dod_post_regex_mismatch, severity >= decision
    - For each commit in branch orchestrator/<task_id>:
        - Inspects diff vs sdd_metadata.stages[*].deliverables[*].path
        - Flags out-of-scope edits (auditor's independent take on Gate D)
    - Iterates over impl_metadata.audit_inputs[] -- the implementer-curated list of artifacts auditor should inspect
    - Cross-checks impl_metadata.refusals[] against sdd_metadata.refusals[] for scope_mismatch findings
    - Assigns severity to each finding (info / decision / blocker)
    - Sets recommended_verdict (advisory)
    - writes tasks/<task_id>/audit_report.json
    - post-Write Read on audit_report.json
    - announces "AUDIT READY" (literally, one line)
[Operator] "audit готов" / "глянь, что аудитор делает"
[Claude = L2]
    - "audit готов" -> scripts/validate-audit.ps1 -TaskId X
        |-- Pydantic-validate audit_report.json (schema_audit_v1)
        |-- Gate A: branch_sha_audited == current tip of orchestrator/<task_id>
        |-- Gate B: Orchestrator/ has changes ONLY under tasks/<task_id>/ (no auditor-side scope leak)
        |-- Gate C: audit_report.json present at task_root
        |-- Gate D: re_verifications_attempted covers all impl_metadata.validations_attempted where mandatory==true
        |-- Gate E: ff_re_audit has all 8 keys (FF1-FF8)
        |-- analyst-session real-MCP check (exit 6, carry-forward from Phase 3)
        |-- writer-session real-MCP check (exit 7, carry-forward)
        |-- implementer-session real-MCP check (exit 8, carry-forward)
        |-- auditor codex-rollout real-MCP check (NEW; exit 9 if 0 mcp tool_use entries)
        |-- compute computed_verdict from findings severities (deterministic)
        |-- log recommended_verdict vs computed_verdict disagreement (informational, doesn't change exit)
        `-- if all gates pass AND computed_verdict=ack -> exit 0
            elif computed_verdict=request_changes -> exit 14
            elif computed_verdict=reject -> exit 15
    - "глянь" -> scripts/peek-auditor.ps1 -TaskId X
        `-- tail last N events from codex rollout file + LAST_EVENT_AGO
[Stage 8 -- operator review (extended)]
    - Operator reads tasks/<task_id>/audit_report.json (and validate-audit.ps1 stdout)
    - Decides:
        (a) computed_verdict=ack -> sign off normally: "approved <commit> audit=ack"
        (b) computed_verdict=request_changes -> operator decision: re-spawn implementer manually with audit_report as input, OR override-and-signoff ("approved <commit> audit=override:<reason>"), OR abandon task
        (c) computed_verdict=reject -> operator decision: abandon task (signoff "rejected: <reason> audit=reject"), OR override after risk acceptance ("approved <commit> audit=override:<reason>")
    - Writes tasks/<task_id>/operator_signoff.txt
    - Phase 4 chain emits `## DONE`; orchestrator next phase begins or chain ends
```

---

## 5. Stages

### Stage 0 -- Spawn-mechanism smoke (mirror Phase 3 Stage 0, scoped to auditor wrapper running codex)

**Goal:** prove that `wt -> powershell -> _run-auditor.ps1 -> codex exec` works with the planned argument shape BEFORE we author task-specific templates. The codex CLI invocation surface differs from claude CLI -- this is the highest-risk integration point of Phase 4.

**What breaks (FF3):** codex CLI flags differ from claude CLI (`--cd` instead of CWD argument; `--dangerously-bypass-approvals-and-sandbox` instead of `--dangerously-skip-permissions`; `-m <model>` instead of `--model <name>`; prompt passed via positional arg after `--`, not via stdin). One typo silently breaks Stage 4.

**Steps:**
1. Write `scripts/_run-auditor.ps1` stub that just echoes its five params + path-resolves `sdd.md` + `sdd_metadata.json` + `impl_metadata.json` and confirms all three exist.
2. From this session: run the stub with PowerShell directly (no `wt`) against the existing `tasks/2026-05-22-example-erp-02/` task, confirm it resolves and exits 0.
3. Wrap it in `wt.exe -w 0 nt --title "auditor-smoke" powershell.exe -File scripts/_run-auditor.ps1 -TaskRoot ...` -- confirm new tab opens and stub prints expected output.
4. Separately: run `codex exec --help` (no real spawn) and capture the available flags; confirm `--cd`, `--add-dir`, `--dangerously-bypass-approvals-and-sandbox`, `-m`, and positional prompt-after-`--` are all present. If any is renamed in codex 0.130.0, capture the actual flag name and update Stage 4 spec before proceeding.

**Verification (auto, binary):**
- `wt` opens new tab titled `auditor-smoke`
- Stub stdout contains `sdd.md EXISTS: true` AND `sdd_metadata.json EXISTS: true` AND `impl_metadata.json EXISTS: true`
- Stub exit code = 0
- `codex exec --help` output contains all five planned flags

**No marker file needed** -- Phase 1+2+3 Stage 0 already proved the `wt -> powershell -> child-process` end-to-end binding; this stage tightens to the codex-specific wrapper only.

### Stage 1 -- schemas/audit_v1.py (Pydantic sidecar contract)

**Deliverables:**
- `schemas/audit_v1.py` -- standalone Pydantic v2, zero `from <prior-iteration>` imports, zero `from schemas.sdd_v1` / `from schemas.impl_v1` imports (Citation / FFOutcome / ValidationAttempt are DUPLICATED). [FF2: recursive import walk N/A -- designed from scratch.]

**Schema sketch (binding for Stage 2 prompt):**
```python
class AuditReport(ArtifactModel):
    schema_version: Literal["v1"]
    task_id: str                                       # matches input impl_metadata.task_id
    sdd_metadata_ref: Literal["sdd_metadata.json"]
    sdd_ref: Literal["sdd.md"]
    impl_metadata_ref: Literal["impl_metadata.json"]
    analysis_ref: Literal["analysis_report.json"]
    project_id: str                                    # from projects.yaml
    path_local: str                                    # absolute path inspected, sans creds
    branch_audited: str                                # orchestrator/<task_id>
    branch_sha_audited: str                            # tip of branch at audit-start time
    findings: list[AuditFinding]                       # may be empty (clean ack)
    ff_re_audit: dict[Literal["FF1","FF2","FF3","FF4","FF5","FF6","FF7","FF8"], FFOutcome]
    re_verifications_attempted: list[ValidationAttempt]  # mirror of impl_v1 shape
    mcp_queries_issued: list[McpQuery]                 # for independence audit trail
    recommended_verdict: Literal["ack", "request_changes", "reject"]   # codex-set, advisory
    citations: list[Citation]                          # >=1 -- auditor must cite at least one MCP read or impl_metadata field
    audit_started_at: str                              # ISO-8601 UTC
    audit_ended_at: str                                # ISO-8601 UTC
    audit_self_review_notes: str                       # cold-context optic notes; required non-empty

class AuditFinding(ArtifactModel):
    id: str                                            # AF1, AF2, ...
    category: Literal[
        "ff_audit_disagreement",
        "dod_post_regex_mismatch",
        "out_of_scope_edit",
        "refuse_violation",
        "missing_verification",
        "scope_mismatch",
        "other"
    ]
    severity: Literal["info", "decision", "blocker"]
    surface: Literal["sdd", "impl", "both", "process"]   # process = harness/spawn finding
    description: str                                   # required non-empty
    evidence: str                                      # required non-empty (file:line, commit sha, MCP excerpt)
    cross_reference: str | None = None                 # optional secondary anchor

class McpQuery(ArtifactModel):
    server: str                                        # codemetadata
    tool: str                                          # e.g. get_object, list_attributes
    args_sha12: str                                    # 12 hex chars hash of args dict
    response_sha12: str                                # 12 hex chars hash of response
    raw_path: str                                      # tasks/<task_id>/audit_raw/<server>/r<round>-q<idx>-<sha12>.json

class ValidationAttempt(ArtifactModel):                # DUPLICATED from impl_v1
    name: str
    status: Literal["ok", "fail", "skipped", "unavailable"]
    diagnostic: str
    mandatory: bool

class FFOutcome(ArtifactModel):                        # DUPLICATED from sdd_v1 + impl_v1
    status: Literal["pass", "na", "fail"]
    note: str

class Citation(ArtifactModel):                         # DUPLICATED; source enum extended
    source: Literal[
        "mcp",
        "code",
        "rlm",
        "raw_artefact",
        "analysis_report",
        "sdd_metadata",
        "sdd",
        "impl_metadata",
        "audit_raw"
    ]
    ref: str
    excerpt: str | None = None
```

**Validators (binding for validate_audit.py exit codes):**
- `task_id` matches the input `impl_metadata.task_id` AND `sdd_metadata.task_id` -- enforced cross-file in validate_audit, not in pydantic
- `ff_re_audit` must have all 8 keys present (model_validator)
- `branch_audited` matches `^orchestrator/[A-Za-z0-9._/-]+$` (field_validator; carries Phase 3 convention)
- `branch_sha_audited` matches `^[0-9a-f]{40}$` (field_validator)
- `McpQuery.args_sha12` + `McpQuery.response_sha12` match `^[0-9a-f]{12}$` (field_validator)
- `Citation.source = "audit_raw"` requires `ref` to start with `audit_raw/` (field_validator)
- `Citation.source = "impl_metadata"` requires `ref` to start with `impl_metadata.json#` (field_validator)
- `recommended_verdict` is just a stored field; no constraint vs findings severities (decoupled by design -- machine compute is the gate, recommended is advisory)
- `findings` may be empty (clean ack); but if empty, `recommended_verdict` should be "ack" (soft-warn in validate_audit stdout, not a Pydantic error)

**Verification (FF3 binary list):**
- `python -c "from schemas.audit_v1 import AuditReport; print(sorted(AuditReport.model_fields.keys()))"` exits 0, lists 19 fields
- `grep -E "^(from|import) <prior-iteration>" schemas/audit_v1.py` -- empty
- `grep -E "^from schemas\.(sdd_v1|impl_v1)" schemas/audit_v1.py` -- empty (shapes duplicated, not imported)
- `scripts/_python/_test_audit_schema.py` fixtures pass:
  - (a) valid full report, no findings, recommended_verdict=ack -> OK
  - (b) ff_re_audit missing FF6 -> ValidationError
  - (c) branch_audited="dispatch/foo" -> ValidationError
  - (d) branch_sha_audited="abc" (too short) -> ValidationError
  - (e) McpQuery.args_sha12="0123abc" (too short) -> ValidationError
  - (f) Citation(source="impl_metadata", ref="something_else") -> ValidationError
  - (g) Citation(source="audit_raw", ref="audit_raw/codemetadata/r0-q0-abc.json") -> OK
  - (h) one blocker finding, recommended_verdict=ack -> OK at schema level (computed verdict diverges; not a schema error)
  - (i) empty findings, recommended_verdict=reject -> OK at schema level (validate_audit will soft-warn)

### Stage 2 -- prompts/auditor.md

**Deliverables:**
- `prompts/auditor.md` -- phase contract. Embeds FF1-FF8 re-audit checklist (referenced by absolute path under `{ORCHESTRATOR_ROOT}/docs/writer-forcing-functions.md`).

**Required prompt content (FF6 forcing functions, not honor-system):**
- Anti-assumption rule (mirror analyst.md / sdd-writer.md / implementer.md).
- Cold-context directive: "Do NOT trust the writer's or implementer's self-narrative. Treat their FF self-audit rows as claims to be re-verified, not as evidence."
- Re-verification mandate: for each `impl_metadata.validations_attempted[v]` with `v.mandatory == true`, the auditor MUST emit a corresponding entry in `audit_report.re_verifications_attempted[]` -- by name. If the auditor cannot re-verify (e.g. codemetadata MCP unavailable for the relevant query), the entry status is `"unavailable"` and a blocker finding with category=missing_verification is emitted.
- MCP-usage mandate: the auditor MUST issue at least one codemetadata MCP query of its own (FF4 carry-forward). Citing impl_metadata's MCP record without re-issuing = not independence.
- Severity rubric (codex-facing):
  - **info**: nothing actionable; observation logged for completeness.
  - **decision**: operator should review; not blocking. Examples: dod_post regex matches stricter than implementer's, but committed content satisfies a looser interpretation.
  - **blocker**: should not proceed without resolution. Examples: dod_post regex does NOT match committed file; out-of-scope edit confirmed; REFUSE list violation in commit log.
- recommended_verdict guidance: codex's view, advisory. "Do NOT try to bias severities to flip the machine-computed verdict; severities and recommended_verdict are independent dimensions."
- REFUSE list (auditor is read-only):
  - No writes to `<path_local>` (no edits, no git tags, no notes, no rebases, no force-pushes, no branch deletions).
  - No writes to `Orchestrator/` outside `tasks/<task_id>/`.
  - No db-update / 1c-manage.sh / direct PG / ibcmd config apply.
  - No re-running the writer or implementer (no auto-fix loop).
  - No editing sdd.md, impl_metadata.json, sdd_metadata.json, analysis_report.json (auditor produces audit_report.json ONLY).
- Output contract: write audit_report.json, post-Write Read it, announce literally `AUDIT READY` on its own line.
- ff_re_audit checklist: must populate `audit_report.ff_re_audit` with all 8 keys (FF1-FF8), each pass/na/fail + note. `fail` does NOT automatically cause a blocker finding -- the auditor must emit a separate `AuditFinding` with category=ff_audit_disagreement and chosen severity. (Decoupled to let the auditor distinguish minor FF gaps from blocking ones.)

**Verification (FF3 binary list):**
- `grep -E "FF[1-8]" prompts/auditor.md` produces >=16 matches
- `grep "AUDIT READY" prompts/auditor.md` produces >=1 match
- `grep -E "(info|decision|blocker)" prompts/auditor.md` produces >=6 matches (severity rubric)
- `grep -iE "(db-update|1c-manage\.sh|ibcmd|psql|pg_)" prompts/auditor.md` produces >=4 matches (REFUSE section)
- `grep "read-only" prompts/auditor.md` produces >=1 match
- File contains no Cyrillic
- File header references `docs/writer-forcing-functions.md` by absolute path

### Stage 3 -- templates (auditor-CLAUDE.md.tpl + auditor-codex.toml.tpl)

**Deliverables:**
- `templates/auditor-CLAUDE.md.tpl` -- first-thing-auditor-reads. Placeholders:
  - `{PROJECT_ID}`, `{PROJECT_PATH}`, `{TASK_ID}`, `{TASK_TEXT}`, `{ORCHESTRATOR_ROOT}`, `{TASK_ROOT_ABS}`
  - NEW for Phase 4: `{SDD_REF}`, `{SDD_METADATA_REF}`, `{IMPL_METADATA_REF}`, `{ANALYSIS_REF}`, `{BRANCH_AUDITED}`, `{BRANCH_SHA_AT_AUDIT_START}`
- `templates/auditor-codex.toml.tpl` -- codex config snippet (TOML syntax; codex uses `~/.codex/config.toml` format). Defines an MCP server entry for codemetadata pointing at `{CODEMETADATA_URL}`. spawn-auditor.ps1 will write this to `tasks/<task_id>/auditor.codex.toml` and pass it to `codex exec --config <path>` OR set `CODEX_HOME` env-var to a per-task dir containing this file. **Stage 3 verification step decides between `--config` flag and `CODEX_HOME` approach by reading `codex exec --help` -- whichever exists in codex 0.130.0 wins.**

**Why a distinct config file per task?** Same reason as Phases 1-3: per-task render avoids concurrent-spawn collisions. Per-task codex config also lets each auditor pin its own MCP URL (multi-project, multi-codemetadata).

**Verification (FF3 binary):**
- Both files exist
- `python scripts/_python/_test_templates.py` (extended) renders both templates with fixture values and asserts:
  - No `{...}` placeholder remains in output
  - auditor.codex.toml output parses as TOML and has an MCP entry pointing at the fixture codemetadata URL
  - CLAUDE.md output mentions absolute path `{ORCHESTRATOR_ROOT}/prompts/auditor.md` (resolved)
  - CLAUDE.md output includes the literal branch convention string `orchestrator/<task_id>` with task_id substituted
  - CLAUDE.md output explicitly states the read-only contract

### Stage 4 -- spawn-auditor.ps1 + _run-auditor.ps1

**4.1 `scripts/spawn-auditor.ps1`**

**Params:**
- `-TaskId <string>` (required) -- must reference an existing `tasks/<task_id>/` with passing sdd/impl/analysis validators
- `-Model <string>` (optional) -- override codex default model
- `-PrepareOnly` (switch) -- generate files but skip `wt` spawn (for tests)
- `-Force` (switch) -- allow re-running on a task that already has `audit_report.json`

**Steps:**
1. Resolve `tasks/<TaskId>/`. If absent, exit 1.
2. Read `tasks/<TaskId>/task_packet.json`, `sdd_writer_packet.json`, `implementer_packet.json`. Extract `project_id`, `project_path`, `orchestrator_root`, `codemetadata_url`.
3. **Gating pre-check 1:** `tasks/<TaskId>/sdd.md` AND `sdd_metadata.json` AND `impl_metadata.json` AND `analysis_report.json` exist; `scripts/validate-sdd.ps1 -TaskId <TaskId>` exits 0 AND `scripts/validate-impl.ps1 -TaskId <TaskId>` exits 0. If not, exit 5 with diagnostic "upstream artifact missing or validator non-zero; run validate-sdd / validate-impl first".
4. **Gating pre-check 2:** path_local INVARIANT (Phase 1+2+3 carry-forward) -- fail-fast if `Configuration.xml` or `Catalogs/` not under `project_path`.
5. **Gating pre-check 3:** `<path_local>` has branch `orchestrator/<TaskId>` AND its remote-tracking ref under `gitea/orchestrator/<TaskId>` exists. If not, exit 6.
6. **Gating pre-check 4:** `<path_local>` git status clean (matches `impl_metadata.diff_baseline.orchestrator_after`). If dirty since implementer finished, exit 7.
7. **Gating pre-check 5:** If `tasks/<TaskId>/audit_report.json` exists AND `-Force` not passed, exit 8.
8. **Gating pre-check 6:** `codex` executable resolvable on PATH. If absent, exit 2.
9. Capture `before_sha_at_audit_start = git -C <path_local> rev-parse refs/heads/orchestrator/<TaskId>`.
10. Render templates with placeholder dict. Write:
   - `tasks/<TaskId>/CLAUDE.auditor.md`
   - `tasks/<TaskId>/auditor.codex.toml`
   - `tasks/<TaskId>/auditor_packet.json` (auditor-side metadata: `created_at`, `wt_window_title`, `path_local`, `branch_audited`, `before_sha_at_audit_start`, `model`)
   - `tasks/<TaskId>/prompt.auditor.md` (one-liner pointing at `./CLAUDE.auditor.md`)
   - `tasks/<TaskId>/audit_raw/` directory
11. Spawn `wt.exe`:
    ```
    wt.exe -w 0 nt --title "auditor:$TaskId" powershell.exe -NoExit -ExecutionPolicy Bypass `
      -File "$PSScriptRoot\_run-auditor.ps1" `
      -TaskRoot "$TaskRoot" `
      -ProjectPath "$ProjectPath" `
      -OrchestratorRoot "$OrchestratorRoot" `
      -PathLocal "$PathLocal" `
      -Model "$Model"
    ```
12. Print JSON to stdout with `{task_id, task_root, wt_window_title, path_local, branch_audited, before_sha_at_audit_start, model}`.

**4.2 `scripts/_run-auditor.ps1`** -- same shape as `_run-implementer.ps1`, but the child command is:
```
codex exec `
  --cd "$TaskRoot" `
  --add-dir "$PathLocal" `
  --add-dir "$OrchestratorRoot" `
  --config "$TaskRoot\auditor.codex.toml" `
  --dangerously-bypass-approvals-and-sandbox `
  -m "$Model" `
  -- "$(Get-Content "$TaskRoot\prompt.auditor.md" -Raw)"
```
(Exact flag spelling locked at Stage 0 verification.) Pipes stdout/stderr to `tasks/<TaskId>/audit.log`. On exit, writes pid + exit code to `tasks/<TaskId>/audit.status`. ASCII-only.

**What breaks (FF3 -- failure modes):**
- upstream artifact absent or validator non-zero -> exit 5
- `<path_local>` branch missing or not pushed -> exit 6
- `<path_local>` dirty since impl finished -> exit 7
- audit_report already exists without -Force -> exit 8
- codex not on PATH -> exit 2
- codex flag rename in 0.130.0 -> Stage 0 catches before Stage 4 spec is locked
- wt.exe absent -> exit 2 with manual-run fallback

**Verification (FF3 binary):**
- `spawn-auditor.ps1 -TaskId 2026-05-22-example-erp-02 -PrepareOnly` exits 0, creates 5 files + `audit_raw/`
- Negative: `spawn-auditor.ps1 -TaskId nonexistent -PrepareOnly` exits 1
- Negative: stage a fake task with broken impl_metadata.json -> exit 5
- Negative: stage a fake task with no orchestrator/<id> branch -> exit 6
- Negative: stage a fake task with dirty path_local -> exit 7
- Concurrent: re-running spawn with pre-existing audit_report -> exit 8 (and exit 0 with `-Force`)

### Stage 5 -- _codex_rollout.py + validate_audit.py + validate-audit.ps1

**5.1 `scripts/_python/_codex_rollout.py`**

Helper module. Parses `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl`. Exposes:
- `find_rollout_for_session(session_id_or_starttime) -> Path`
- `count_mcp_tool_use(rollout_path) -> int` -- counts JSONL entries representing MCP tool calls. Exact entry shape (key names) TO BE CONFIRMED via Stage 5 fixture inspection -- the codex rollout schema is not in this SDD because it has not been parsed yet (see §10 OQ11 disposition).
- `iter_mcp_tool_uses(rollout_path) -> Iterable[dict]` -- yields server + tool name + args (for future Phase 5 strict subset-check).

Test fixtures (`_test_codex_rollout.py`):
- One real rollout file from `~/.codex/sessions/` -- copied as a fixture under `scripts/_python/fixtures/codex_rollout_*.jsonl`. Operator + writer inspect at Stage 5 kickoff to confirm field names; if names differ from initial guess, this helper's API is the single point of change.
- Synthetic rollout fixture with zero MCP entries -> count_mcp_tool_use == 0.
- Synthetic rollout fixture with N MCP entries -> count_mcp_tool_use == N.

**5.2 `scripts/_python/validate_audit.py`**

**Input:** `<task_root>` (positional). Discovers:
- `tasks/<task_id>/audit_report.json`
- analyst/writer/implementer session.jsonls via the same glob as `validate_impl.py`
- auditor codex rollout file via `_codex_rollout.find_rollout_for_session(auditor_packet.codex_session_id_or_starttime)`

**Exit codes:**

| exit | meaning | message |
|---|---|---|
| 0 | OK -- computed_verdict=ack | summary (gates A-E, findings counts, MCP-usage tallies for four sessions, computed_verdict, recommended_verdict, disagreement-flag) |
| 1 | audit_report.json Pydantic ValidationError | full ValidationError |
| 2 | audit_report.json absent at task_root (**Gate C**) | "auditor did not produce audit_report.json" |
| 3 | `audit_report.task_id` != input `impl_metadata.task_id` or != `sdd_metadata.task_id` | all values shown |
| 4 | audit_report.json not parseable | JSONDecodeError line/col |
| 5 | **Gate A: branch_sha_audited != current tip of orchestrator/<task_id>** (auditor audited stale state; commits added after audit started) | both shas shown |
| 6 | analyst session.jsonl shows 0 mcp tool_use (OPERATIONAL QUALITY GATE -- Phase 3 carry-forward) | "input analysis was synthesized without real MCP" |
| 7 | writer session.jsonl shows 0 mcp tool_use (Phase 3 carry-forward) | "sdd_writer did not consult MCP" |
| 8 | implementer session.jsonl shows 0 mcp tool_use (Phase 3 carry-forward) | "implementer did not consult MCP" |
| 9 | **auditor codex rollout shows 0 mcp tool_use** (NEW; weak independence gate v1) | "auditor did not issue any MCP query of its own" |
| 10 | **Gate B: Orchestrator/ has changes outside tasks/<task_id>/** | porcelain output of out-of-scope diff |
| 11 | **Gate D: re_verifications coverage gap** -- impl_metadata.validations_attempted[v] with v.mandatory==true has no matching entry in audit_report.re_verifications_attempted[] | list of missing names |
| 12 | **Gate E: ff_re_audit missing FF key** | which keys are missing |
| 13 | `audit_report.findings[*].id` collisions or non-AF prefix | offending ids |
| 14 | **computed_verdict = request_changes** (>=1 decision-severity finding, no blocker) | findings summary by severity + recommended_verdict for comparison |
| 15 | **computed_verdict = reject** (>=1 blocker-severity finding) | findings summary by severity + recommended_verdict for comparison |

**Summary at exit=0:** task_id, project_id, branch_audited, branch_sha_audited, findings count by severity (info/decision/blocker), recommended_verdict, computed_verdict, recommended-vs-computed disagreement-flag, re_verifications_attempted breakdown (ok/fail/skipped/unavailable counts, mandatory-coverage count), ff_re_audit (8 booleans pass/na/fail), analyst/writer/implementer/auditor MCP-tool-use counts, mcp_queries_issued count, audit_started_at, audit_ended_at, audit_self_review_notes (truncated to first 200 chars).

**Verdict-disagreement log:** when `recommended_verdict != computed_verdict`, validate_audit writes a "DISAGREEMENT" line to stdout. Does NOT change exit code. Operator sees both verdicts in the summary.

**Why exit 14/15 for verdict-driven failures (not just a binary 0/1)?** Operator needs to distinguish "auditor say ack" (exit 0, proceed to signoff) from "auditor says request_changes" (exit 14, operator decision: re-spawn implementer OR override) from "auditor says reject" (exit 15, operator decision: abandon OR override with risk acceptance). Three exit codes encode the three operator branches.

**5.3 `scripts/validate-audit.ps1`** -- thin wrapper, `-TaskId X`, passes through python exit code. Same Write-Error gotcha mitigations as validate-sdd.ps1 / validate-impl.ps1.

**Verification (FF3 binary, via `_test_validate_audit.py`):**
- 16 fixtures, one per exit code 0-15. Each fixture stages a fake task_root with sdd_metadata.json + impl_metadata.json + audit_report.json + mocked claude session.jsonls + a mocked codex rollout under temp dirs.
- Coverage-gap fixture (exit 11): impl_metadata.validations_attempted has one mandatory entry; audit_report.re_verifications_attempted is empty.
- Disagreement fixture (exit 0 with DISAGREEMENT log line): findings empty + recommended_verdict="reject" -> exit 0 (computed=ack) + stdout contains "DISAGREEMENT: recommended=reject, computed=ack".

### Stage 6 -- e2e against `tasks/2026-05-22-example-erp-02`

**Why this task:** Phase 3 e2e shipped a clean implementer run on `example-erp-02` (branch `orchestrator/2026-05-22-example-erp-02` in example-erp-src @ 0ec0e934). Re-using it exercises the full Phase 4 chain on a known-good baseline. Expected outcome: audit produces an `ack` verdict (zero blocker findings) OR a small number of decision-severity findings flagged for operator review (Phase 3 closed two example-erp-02 findings already; new auditor optic may find more).

**Steps:**
1. Baselines (FF1 -- record before running):
   - `git -C <orchestrator_root> status --porcelain` (must be clean except in-progress `docs/phase4-*.md` if any)
   - `git -C <path_local> status --porcelain` (must be clean; equal to `impl_metadata.diff_baseline.orchestrator_after`)
   - `git -C <path_local> rev-parse refs/heads/orchestrator/2026-05-22-example-erp-02` (save as `expected_branch_sha`)
2. `scripts/spawn-auditor.ps1 -TaskId 2026-05-22-example-erp-02` -- opens `auditor:2026-05-22-example-erp-02` tab.
3. Observe via `scripts/peek-auditor.ps1 -TaskId 2026-05-22-example-erp-02 -Tail 30`. Wait for `AUDIT READY`.
4. `scripts/validate-audit.ps1 -TaskId 2026-05-22-example-erp-02` -- must exit 0 (ack), 14 (request_changes -- operator decides), or 15 (reject -- operator decides).
5. Sanity-checks (FF1):
   - `tasks/<task_id>/audit_report.json` exists, Pydantic-valid
   - `audit_report.branch_sha_audited == expected_branch_sha` (Gate A pre-validate sanity)
   - `git -C <orchestrator_root> status --porcelain | grep -v 'tasks/'` empty (Gate B sanity)
   - `audit_report.re_verifications_attempted` covers every mandatory entry in `impl_metadata.validations_attempted` (Gate D sanity)
   - `audit_report.ff_re_audit` has all 8 keys (Gate E sanity)
   - `audit_report.mcp_queries_issued` count >= count(audit_raw/*/*.json files) (consistency)
   - codex rollout shows >=1 mcp tool_use (Gate "exit 9" sanity)
6. **Operator review (Stage 8 -- below):** operator reads `audit_report.json`, decides verdict path.

**What breaks (FF3):**
- Hang / no progress: peek prints `LAST_EVENT_AGO > 300s WARNING`; operator runs `kill-auditor.ps1`
- Codex CLI fails to start: exit code visible in `audit.status`; operator inspects log
- Codemetadata MCP unreachable: auditor records `unavailable` re-verifications + blocker finding; validate_audit exit 15
- audit_report.json malformed: exit 1 or 4
- Coverage gap: exit 11
- Stale audit (someone committed to branch during audit): exit 5

### Stage 7 -- peek-auditor.ps1 + kill-auditor.ps1

**peek-auditor.ps1:**
- Params: `-TaskId X`, `-Tail N` (default 30)
- Discovery: reads `auditor_packet.json` for codex session start-time, then resolves the latest rollout file under `~/.codex/sessions/YYYY/MM/DD/` whose mtime is >= that start-time AND has the auditor's task_id in its first event (cross-check). Fallback: newest rollout under today's date.
- Event-formatting: distinct from Phase 1-3 peek scripts because codex rollout schema differs from claude session.jsonl. Uses `_codex_rollout.iter_events()` -- a new helper sibling of `iter_mcp_tool_uses()`.
- `LAST_EVENT_AGO` health line: max(event-mtime - now) in seconds; > 300 prints `WARNING`.
- ASCII-only.

**kill-auditor.ps1:**
- Title pattern: `*auditor:<TaskId>*`
- Stamps `auditor_packet.killed_at`
- Identical body to Phase 3 kill-implementer.ps1 except the title prefix.

**Verification (FF3 binary):**
- After Stage 6 run, `peek-auditor.ps1 -TaskId 2026-05-22-example-erp-02` returns >0 events + `LAST_EVENT_AGO=<s>`
- Mocked-stuck case: artificially set rollout file mtime to 6 minutes ago -> WARNING printed
- `kill-auditor.ps1 -TaskId <dummy>` -- kills dummy wt tab whose title contains `auditor:<dummy>`, stamps `killed_at`

### Stage 8 -- operator-signoff extension

**Goal:** extend the Phase 3 operator_signoff.txt convention to record the audit verdict that was active at signoff. No new script; convention-only change. Future Phase 5 may add a validate-signoff.ps1; out of Phase 4 scope.

**Deliverables:**
- `tasks/2026-05-22-example-erp-02/operator_signoff.txt` rewritten (if Stage 6 produced a clean audit) with the new recommended format:
  - `approved <commit> audit=ack` (if computed_verdict was ack)
  - `approved <commit> audit=override:<reason>` (if operator signed off over a request_changes or reject -- reason must include why)
  - `rejected: <reason> audit=<verdict>` (if operator rejects)
- Documentation update in `prompts/auditor.md` and/or `docs/phase4-auditor-SDD.md` §2 table describing the new format (already covered above).

**Verification (FF3 binary):**
- After Stage 6 Stage 8, `tasks/2026-05-22-example-erp-02/operator_signoff.txt` matches regex `^(approved [0-9a-f]{7,40} audit=(ack|override:.+)|rejected: .+ audit=(ack|request_changes|reject|override:.+))$`.
- Old Phase 3 signoff format (`approved <commit>` without audit suffix) is grandfathered: convention applies to new signoffs, not to retroactive rewrites of pre-Phase-4 tasks.

**What breaks (FF3):**
- Operator writes signoff without audit suffix -> convention violation, no machine enforcement in Phase 4. Phase 5 may add enforcement.
- Operator overrides reject without writing `:<reason>` -> convention violation; reviewer (future auditor of auditor, or operator-of-operator) loses the rationale. Phase 4 documents the convention; enforcement deferred.

---

## 6. Open Questions

### OQ1 -- Spawn model (CLOSED -- B, wt-tab + codex exec)

Decided 2026-05-22. NOT Agent subagent. See `memory/feedback_phase4_spawn_model.md`.

### OQ2 -- Pass/fail criteria (CLOSED -- E, two-layered)

Codex sets per-finding severity (judgment); validate_audit computes verdict deterministically (machine gate). Codex's recommended_verdict is advisory and logged for operator visibility. See `memory/feedback_phase4_verdict_split.md`.

### OQ3 -- Output schema (CLOSED -- 5 design points)

Listed under "Closures (session 1)" in design memory. Surface enum includes `process`. Category enum has `"other"` safety valve. ff_re_audit is a separate 8-key dict (mirrors implementer's ff_self_audit shape), NOT just findings entries. re_verifications coverage gate is the missing-verification gate (Gate D / exit 11). MCP-usage gate is the weak v1 (auditor codex rollout >=1 mcp tool_use, exit 9). Strict subset-check deferred to Phase 5.

### OQ4 -- Re-prompt vs operator escalation (CLOSED -- always escalate operator)

No auto re-prompt loop between codex auditor and claude implementer. Different runtimes, file-only protocol. validate_audit verdict-driven exits (14, 15) are operator-decision; not L2 retry codes.

### OQ5 -- MCP surface (CLOSED -- C, codemetadata-only + auditor re-verifies via metadata reads)

Codex has no claude-skills (1c-skills family is claude plugin). Re-verifying SDD/impl claims is done by direct codemetadata reads (`get_object`, `list_attributes`, `get_form_layout`, etc.), not by running validate skills. SSH-to-<vm-docker-host> for live 1C-validators was rejected (blast radius + stateful 1C-bases + zero independence gain).

### OQ6 -- Auditor vs validate_impl ordering (CLOSED -- validate_impl FIRST, auditor SECOND)

Auditor spawn permitted only on tasks where validate-impl.ps1 returns 0. Cheap-first economics. Auditor "depth-on-green" optic. Phase 3 retry loop isolated.

### OQ7 -- Stage 8 operator-signoff integration (CLOSED -- extend signoff format)

`operator_signoff.txt` recommended format extends to include `audit=<verdict>` suffix; `audit=override:<reason>` when operator signs off over computed_verdict != ack. Convention-only in Phase 4; future Phase 5 may add validate-signoff.ps1.

### OQ8 -- Artifact storage (CLOSED -- mirror Phase 1-3)

`tasks/<task_id>/audit_report.json` + `audit_raw/<server>/r<round>-q<idx>-<sha12>.json` per MCP query + `auditor_packet.json` + `audit.log` + `audit.status`. Same pattern; no novelty.

### OQ9 -- Model (CLOSED -- codex default from ~/.codex/config.toml)

Decided by OQ1 closure (codex chosen over claude); model defaults from codex config. Operator may override via `-Model <name>` on spawn-auditor.ps1.

### OQ10 -- Out-of-scope for Phase 4 (CLOSED -- deferred list)

Out of scope: auto-merge orchestrator/<task_id> to master/main of 1C project (always operator); cross-task / release-branch sweep audit; live 1C-base mutation; writer/implementer re-spawn from auditor; auto-operator-ping (Telegram/email on request_changes -- Phase 5 territory).

### OQ11 -- Codex rollout schema (open, settled at Stage 5 fixture inspection)

**Status:** unconfirmed at SDD-time. Memory record explicitly flags this:

> Codex rollout format != claude session.jsonl format. Need a separate parser for the auditor MCP-gate. Worth checking the rollout schema before Stage 5 spec is finalized.

**Mitigation:** Stage 5.1 deliverable (`_codex_rollout.py`) gates on inspecting a real rollout file under `~/.codex/sessions/`. If field names differ from the initial guess in the parser stub, `_codex_rollout.py` is the single point of change -- `validate_audit.py` and `peek-auditor.ps1` import from this helper. SDD §5 exit-code table is unaffected by rollout schema specifics (only the count of mcp tool_use entries is consumed, not their inner structure).

**Why not block Stage 1 on this?** Schema design (audit_v1.py) does not depend on rollout shape; only the validator does. Decoupling is intentional.

---

## 7. Risks and mitigations

| Risk | Mitigation | Tag |
|---|---|---|
| Auditor writes to `<path_local>` (e.g. accidental git tag, note, branch) | Prompt REFUSE section forbids; CLAUDE.auditor.md states read-only contract; Gate B catches Orchestrator-side writes; codex `--add-dir <path_local>` is needed for read but `--dangerously-bypass-approvals-and-sandbox` does not constrain writes -- relying on prompt + post-hoc detection | FF5, FF6 |
| Auditor writes outside `tasks/<task_id>/` in `Orchestrator/` (e.g. modifies prompts/auditor.md mid-run) | Gate B fails (exit 10) with porcelain diff | FF6 |
| Auditor trusts impl_metadata's MCP record without re-issuing (no independence) | exit 9: codex rollout 0 mcp tool_use -> auditor did NOT consult MCP at all (weak version v1). Strict version (rollout queries must include >=1 not in impl session) deferred to Phase 5 | FF4 |
| Auditor produces verdict from narrative reasoning only (no fresh evidence) | exit 9 catches the absolute case (0 MCP calls). Coverage gate (exit 11) ensures every mandatory verification has a fresh entry. ff_re_audit (Gate E / exit 12) ensures every FF row was re-audited, even if pass/na | FF4 |
| Codex assigns blocker severity to a finding but recommends ack (negotiates with itself) | Machine compute supersedes recommended_verdict. validate_audit exit 15 fires on >=1 blocker regardless of recommendation. Disagreement is logged for operator visibility | FF6 |
| Codex assigns info severity to a true blocker (under-grades) | Mitigated by operator review at Stage 8; the audit_report is human-readable and operator can override. NOT machine-enforced -- this is the residual writer-auditor gap that Phase 4 cannot fully close in v1. Phase 5+ may add a meta-auditor (auditor of auditor) | FF6 honor-tagged |
| Auditor session.jsonl-equivalent (codex rollout) shape changes across codex versions | `_codex_rollout.py` is the single point of change. Stage 5 fixture inspection locks the parser for current codex 0.130.0. Phase 5+ keeps watch on codex CLI updates | FF1 |
| Auditor runs against stale branch tip (someone committed during audit) | Gate A exit 5 catches: branch_sha_audited != current tip. Operator re-spawns auditor against fresh tip | FF1 |
| Codex flag rename between codex 0.130.0 and a future operator-installed version | Stage 0 captures the actual flag set at session-start; spawn-auditor.ps1 reads codex version and warns on mismatch (deferred to a future hardening if codex CLI churns) | FF3 |
| --dangerously-bypass-approvals-and-sandbox blast radius -- can pip-install / modify arbitrary FS | RISK ACCEPTED (parity with Phase 1-3 --dangerously-skip-permissions). Mitigations: (a) Gate B for Orchestrator/; (b) auditor prompt REFUSE list; (c) codex session does not have ssh keys for <vm-docker-host> by default | FF5 |
| Codemetadata indexer differs between implementer run and auditor run | RISK ACCEPTED (same as Phase 2-3). Detection via MCP tool_use comparison (impl session vs codex rollout) -- not enforced in v1 (Phase 5 strict subset-check) | FF1 |
| Auditor hangs / loops | `peek-auditor.ps1 LAST_EVENT_AGO>300s WARNING` + `kill-auditor.ps1` | FF3 |
| `audit_report.task_id` accidentally hardcoded by auditor (copy-paste from sdd_metadata or impl_metadata) | validate_audit exit 3 cross-checks against both impl_metadata.task_id AND sdd_metadata.task_id | FF6 |
| `impl_metadata.audit_inputs[]` is empty or stale (implementer forgot to populate) | Auditor falls back to deriving its own input set from sdd_metadata.stages[*].deliverables + commit log of branch. audit_self_review_notes records the fallback. Not blocking; ergonomic only | FF3 |
| `peek-auditor.ps1` returns wrong codex rollout (multi-day, concurrent codex runs) | `auditor_packet.json` records codex session start-time; peek-auditor resolves rollout by mtime >= that start-time AND task_id match in first event. Documented in Stage 7 | FF3 |
| `validate_audit.py` cannot find codex rollout file (codex did not produce one, e.g. crashed early) | exit 9 (0 mcp tool_use, since no rollout = no calls). Operator inspects audit.log to diagnose | FF3 |
| Codex's recommended_verdict / severities suffer same blind spots as Opus (because trained on similar data) | RISK ACCEPTED as residual. Mitigation: codex is a different model class than Opus 4.7 (gpt-5.x family); operator may rotate model via -Model switch; Phase 5 may add multi-model ensemble | FF1, FF6 honor-tagged |
| Auditor citations point at non-existent refs (e.g. typo'd commit sha, file path) | Pydantic schema does not enforce ref existence (out of scope for pure type validation); operator review catches at Stage 8. Phase 5 may add validate-citations.ps1 | FF6 honor-tagged |
| Codex rollout file permissions block read by validate_audit (user mismatch) | `_codex_rollout.py` fails fast with clear "cannot read rollout" diagnostic; exit 9 fires (treated as 0 mcp tool_use, since unreadable=uncountable). Operator chmods or re-spawns | FF3 |
| Two auditor-attempts on same task collide on audit_report.json | spawn-auditor.ps1 exit 8 unless `-Force`; `-Force` overwrites both audit_report.json AND audit_raw/ | FF3 |

---

## 8. Definition of Done

### Pre-conditions (FF7 -- BEFORE Stage 1 starts)

- **0a.** All OQ1-OQ11 closed in §10 with resolution text (OQ11 closed = "schema inspection deferred to Stage 5, no SDD-level blocker").
- **0b.** Stage 0 smoke (wrapper-stub spawning in `wt` tab + codex CLI flag survey) PASSES.
- **0c.** path_local INVARIANT remains intact (Phase 1+2+3 carry-forward).
- **0d.** Operator quality-gate semantics confirmed (carried from Phase 3 -- 0 mcp__ tool_use entries = fail). Phase 4 extends to a FOURTH session (auditor's own codex rollout); operator confirms same semantics apply.
- **0e.** Verdict-split rule confirmed (OQ2 -- machine compute supersedes codex recommendation).
- **0f.** No-re-prompt-loop rule confirmed (OQ4 -- operator escalation always).
- **0g.** MCP-surface scope confirmed (OQ5 -- codemetadata-only).

### Post-conditions (FF7 -- Phase 4 = DONE when)

1. All 9 stages (0-8 above) shipped, each verification list passes.
2. Stage 6 e2e on `2026-05-22-example-erp-02` produces a valid `audit_report.json`; validate-audit.ps1 exits 0 (ack), 14 (request_changes -- operator decided), or 15 (reject -- operator decided). All three are acceptable Stage-6 outcomes; the operator decides Stage 8 path accordingly.
3. Stage 6 sanity-checks: Orchestrator/ untouched outside tasks/<task_id>/ (Gate B); branch_sha_audited matches current tip (Gate A); re_verifications covers all mandatory impl validations (Gate D); ff_re_audit has all 8 keys (Gate E); codex rollout shows >=1 mcp tool_use (exit 9 gate).
4. Stage 8 signoff: `tasks/2026-05-22-example-erp-02/operator_signoff.txt` rewritten in the new format (audit=<verdict> suffix). Convention test (regex) passes.
5. `peek-auditor.ps1` and `kill-auditor.ps1` verified on a dummy and on the Stage 6 task.
6. master pushed to Gitea Orchestrator repo, merged into main at the Phase 4 closeout commit.
7. RLM fact written: `Phase 4 auditor DONE @<commit>` with operational invariants list (gates A-E, MCP-gates extended to 4-fan, verdict-split locked, codex rollout parser shipped).
8. `MEMORY.md` updated with one-line entry pointing to new `project_phase4_done.md`.

---

## 9. Refusals (REFUSE)

Items deliberately NOT in Phase 4 scope:

- **Auto-merge of `orchestrator/<task_id>` to master/main of the 1C project.** Operator-only (Phase 3 carry-forward).
- **Live db-update / config-partial-load.** Phase 3 carry-forward; auditor never runs against a live base.
- **Branch deletion / force-push / rebase on any branch.** Auditor prompt forbids; auditor is read-only over `<path_local>`.
- **Editing Phase 1+2+3 artifacts** EXCEPT the operator_signoff.txt format convention extension (no script change, documentation only).
- **Schema versioning policy.** schema_audit_v1 only. v2 happens when Phase 5+ demands it.
- **Phase-agnostic peek/kill scripts.** Phase 5 cleanup.
- **Inline-in-L2 auditor.** Spawn-only (OQ1 decision).
- **Agent-subagent auditor (codex:codex-rescue).** OQ1 explicit closure.
- **Auto re-prompt loop between auditor and implementer.** OQ4 explicit closure.
- **Auditor running claude-skills (cf-validate, meta-validate, etc.).** Technical impossibility (codex has no skills); OQ5 explicit closure.
- **SSH-to-<vm-docker-host> for live 1C-validators from auditor.** Rejected during OQ5 design.
- **Strict subset-check on MCP queries (auditor's must include >=1 not in implementer's rollout).** Phase 5; v1 stays at weak gate.
- **Meta-auditor (auditor of auditor).** Phase 5+ if residual blind-spot risk warrants.
- **validate-signoff.ps1 enforcing the new operator_signoff.txt format.** Phase 5 cleanup; v1 keeps convention-only.
- **Auto-operator-ping (Telegram/email/Slack) on request_changes or reject.** Phase 5 rotation feature.
- **Cross-project / cross-task / release-branch sweep audit.** One task = one branch = one audit; no multi-task bundle.

---

## 10. Resolutions (closure of Open Questions)

Resolutions promoted from PROVISIONAL to CLOSED 2026-05-22 across the two-session Phase 4 design effort. Operator retains override prerogative: if any resolution should flip, raise it during Stage 6 e2e and the affected stages are reworked before merge to main.

**OQ1 -- Spawn model:** CLOSED -- B (wt-tab + codex exec). NOT Agent subagent. Rationale: async observability, parity with Phases 1-3 5-script pattern, Phase 5 rotation survivability, operational MCP-usage gate reads codex rollout.

**OQ2 -- Pass/fail criteria:** CLOSED -- E (two-layered). Codex severity per finding; validate_audit computes verdict deterministically.

**OQ3 -- Output schema:** CLOSED -- 5 design points (surface enum, category "other" safety valve, ff_re_audit dict shape, re_verifications coverage gate, weak MCP-usage gate).

**OQ4 -- Re-prompt vs operator escalation:** CLOSED -- always operator escalation. No machine loop between auditor and implementer.

**OQ5 -- MCP surface:** CLOSED -- C (codemetadata-only + auditor re-verifies via metadata reads). Codex has no claude-skills; ssh-to-<vm-docker-host> rejected (blast radius + zero independence gain).

**OQ6 -- Auditor vs validate_impl ordering:** CLOSED -- A (validate_impl FIRST). Auditor spawn permitted only on validate-impl exit 0.

**OQ7 -- Stage 8 operator-signoff integration:** CLOSED -- extend signoff format with `audit=<verdict>` suffix. Convention-only; no new validator in Phase 4.

**OQ8 -- Artifact storage:** CLOSED -- mirror Phase 1-3. `audit_report.json` + `audit_raw/<server>/r<round>-q<idx>-<sha12>.json` + `auditor_packet.json` + `audit.log` + `audit.status`.

**OQ9 -- Model:** CLOSED -- codex default from `~/.codex/config.toml`. -Model switch overrides.

**OQ10 -- Out-of-scope:** CLOSED -- deferred list (auto-merge, cross-task sweep, live 1C-base mutation, writer/implementer re-spawn, auto-operator-ping, strict MCP subset-check, meta-auditor).

**OQ11 -- Codex rollout schema:** CLOSED -- deferred to Stage 5.1 fixture inspection. Single point of change is `_codex_rollout.py`; schema design (audit_v1) decoupled.

With OQ1-OQ11 CLOSED, DoD pre-conditions 0a + 0d + 0e + 0f + 0g are satisfied. 0b (Stage 0 smoke + codex flag survey) is the first implementation gate. 0c (path_local INVARIANT) carries forward intact from Phase 1+2+3.

---

## 11. Writer FF1-FF8 self-audit (before submitting this SDD)

Per `docs/writer-forcing-functions.md` and `memory/feedback_writer_discipline.md` -- the SDD writer (me, in this session) must self-audit against FF1-FF8 BEFORE handing off for review. Each gets pass / na / fail + note.

| FF | Status | Note |
|---|---|---|
| FF1 | pass | External claims tagged inline: `[VERIFIED via <fact/file/command>]` for spawn-model decision (`memory/feedback_phase4_spawn_model.md`), verdict-split rule (`memory/feedback_phase4_verdict_split.md`), independence gates (`memory/feedback_phase4_independence_gates.md`), OQ5 closure 2026-05-22 (this session, prior turn). One `[ASSUMED]`-equivalent uncovered: §2 table claim "codex 0.130.0 supports `--cd / --add-dir / --dangerously-bypass-approvals-and-sandbox / -m`" -- not yet verified against actual codex CLI; Stage 0 Step 4 fixes this BEFORE Stage 4 spec is locked, so it is fail-open in design. |
| FF2 | pass | "Recursive dependency walk" N/A for schemas -- `schemas/audit_v1.py` is designed from scratch, NOT inlined from sdd_v1 / impl_v1. Citation + FFOutcome + ValidationAttempt shapes are DUPLICATED (not imported). One intentional cross-phase helper is `_session_jsonl.py` import (validate_audit reads three claude sessions via this helper) -- this is a Phase 3 contract touch that reuses, not modifies, the parser; enumerated in §3 layout and Stage 5 (no edit to _session_jsonl.py itself). |
| FF3 | pass | Each stage (0-8) has explicit failure-modes paragraph or "What breaks" enumeration. Risk table §7 covers cross-stage failures. validate_audit exit-code table §5.2 enumerates 16 distinct failure modes (exit 0-15). Stage 0 explicitly hedges on codex CLI flag uncertainty. |
| FF4 | pass | Three code-over-doc checks: (a) operational quality gate quad-fanned (exits 6, 7, 8, 9 -- one per upstream session + auditor itself) reads ACTUAL session.jsonl / rollout artifacts, not narrative claims; (b) Gate A reads ACTUAL git rev-parse output for branch tip; (c) Gate D reads ACTUAL audit_report.re_verifications_attempted vs impl_metadata.validations_attempted, not auditor's self-report of "I covered everything". (d) Coverage and severity computations are machine-driven, not codex-trust-driven. |
| FF5 | pass | Two dangerous primitives carry forward: `--dangerously-bypass-approvals-and-sandbox` (codex analog of claude's --dangerously-skip-permissions, blast radius profile identical) and codex CLI itself (new runtime; failure modes only emerge at Stage 0/4). Both explicit in §7 with RISK ACCEPTED + mitigations (Gate B for Orchestrator-side scope leak, prompt REFUSE list for path_local-side, codex session has no <vm-docker-host> ssh keys by default). Alternative (codex `--sandbox <mode>` finer-grained policy) deferred to Phase 5+. |
| FF6 | pass | Honor-system items explicitly tagged: (a) codex severity under-grading a true blocker -> HONOR_SYSTEM with operator-review-at-Stage-8 path + future meta-auditor in Phase 5; (b) auditor citations pointing at non-existent refs -> HONOR_SYSTEM, operator catches at Stage 8, Phase 5 may add validate-citations; (c) operator override-reason quality -> HONOR_SYSTEM, no machine check. All RELIABILITY-CRITICAL steps replaced with code-level forcing functions (exit codes 1-15, Gates A-E, MCP-quad-fan). |
| FF7 | pass | DoD §8 has BOTH pre-conditions (0a-0g, with 0e/0f/0g new for Phase 4) and post-conditions (8 binary checks). Pre-condition 0e (verdict-split rule), 0f (no-re-prompt-loop), 0g (MCP-surface scope) are NEW for Phase 4 -- without them, Stages 2+5+6 are blocked. |
| FF8 | pass | Self-grep over THIS SDD for dod_post-equivalent claims (`grep -nE "exit [0-9]+\|" docs/phase4-auditor-SDD.md` matches the §5.2 table consistently; `grep -E "FF[1-8]" docs/phase4-auditor-SDD.md` matches the §11 table). No "fix-on-write" comments. No unfinished sections (every §1-§11 closed). No "TODO" or "TBD" markers other than the explicit OQ11 deferred-to-Stage-5 disposition. |

If operator approves with all FFs passing as marked above, this section freezes and Stage 0 may begin. If operator finds an FF should be FAIL, the writer rewrites the affected sections before Stage 0.

---

## End of draft

Operator next step: read sections §1-§11. If approved as-is, signal "начинаем Stage 0" and Phase 4 implementation chain begins on `master` with per-stage commits + `## DONE` markers, mirroring Phase 3's autonomous-chain pattern.
