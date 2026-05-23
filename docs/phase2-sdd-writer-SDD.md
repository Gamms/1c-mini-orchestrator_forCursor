# SDD — Orchestrator, Phase 2: sdd_writer chain

**task_id:** `orch-phase2-sdd-writer`
**task_size:** M (mirrors Phase 1; same plumbing pattern, new contract)
**author:** Claude (L3 in a fresh wt tab spawned 2026-05-22 ~14:50, handed off from parent Orchestrator session)
**date:** 2026-05-22
**status:** draft for operator review

---

## 1. Context and goal

Phase 1 (analyst) shipped 2026-05-22 at commit `eccd95c` (master = main in Gitea, all 7 stages merged). It produces `tasks/<task_id>/analysis_report.json` (schema_v2). Phase 2 builds the next link: an L3 **sdd_writer** that consumes that analysis report and produces an SDD document for the original operator task.

**Goal of Phase 2:** sdd_writer only. After it lands, Phase 3 (implementer + auditor) opens.

**Out of scope for Phase 2:**
- Implementer, auditor, rotation, remote toggle (Phases 3-5)
- L1 orchestration (always the user)
- Editing Phase 1 artifacts unless a contract change is forced (see §10 — none forced as of this draft)
- New MCP servers (naparnik stays deferred; codemetadata only, same as Phase 1)
- Auto-feeding the SDD into the implementer (Phase 3 will pick `sdd.md` + `sdd_metadata.json` from `tasks/<task_id>/`, but designing that handoff is Phase 3 scope)

**Carry-forwards from Phase 1:**
- Spawn-per-task in a fresh `wt` tab, file-only L2↔L3 protocol
- Per-task CWD = `tasks/<task_id>/`, rendered `CLAUDE.md` + `.mcp.json` per task
- `--mcp-config <task>/.mcp.json --strict-mcp-config` + `--add-dir <path_local>` + `--add-dir <orchestrator_root>`
- Pre-trust both case variants of the encoded path
- `--dangerously-skip-permissions` accepted risk; read-only contract is honor-system in the prompt, sanity-checked at Stage 6 (FF6 tagged below)
- PowerShell 5.1 only, ASCII-only `.ps1` files [VERIFIED via `memory/feedback_powershell_5_1_gotchas.md`]
- path_local INVARIANT (D2 close-out): every `projects.yaml.path_local` mirrors the codemetadata XML-dump index. `spawn-sdd-writer.ps1` enforces fail-fast pre-check identical to Phase 1 `spawn-analyst.ps1` [VERIFIED via `scripts/spawn-analyst.ps1` lines 98-109]

---

## 2. Constraints and decisions

| Constraint | Decision |
|---|---|
| sdd_writer needs read access to source files referenced in analysis_report.relevant_files | `--add-dir <path_local>` reuses analyst pattern; path_local INVARIANT (0c) makes paths FS-resolvable [VERIFIED via RLM fact fc696e57] |
| sdd_writer must NOT trust analyst evidence blindly (FF4 code-over-doc) | Prompt requires sdd_writer to re-issue >=1 MCP query per non-trivial finding; sdd_metadata records new MCP queries; validate_sdd checks writer's own session.jsonl has `tool_use.name ~ ^mcp__` count > 0 [FF6 replaced with code-level forcing function] |
| Operational quality gate (operator-mandated, brief §6) | validate_sdd walks the INPUT analyst session.jsonl, counts `tool_use.name ~ ^mcp__`. If 0 -> exit 6 ("synthesized via Bash+curl, not real MCP"). Catches the Phase 1 Stage-6 D1 failure mode where type=sse silently unbound MCP tools and the analyst worked around with raw curl [VERIFIED via RLM fact 0d131b79 finding #5] |
| Output format | Two files: `tasks/<task_id>/sdd.md` (markdown, AI-to-AI English, human-and-machine-readable) + `tasks/<task_id>/sdd_metadata.json` (Pydantic-validated sidecar, schema_sdd_v1). Rationale: markdown is the deliverable, sidecar enables binary validation and downstream consumption without MD parsing |
| Schema for sidecar | New `schemas/sdd_v1.py` — standalone Pydantic, same hygiene as analysis_v2 (no <prior-iteration> imports, extra="forbid"). FF2 applies: recursive import walk if any inlining is considered |
| Markdown SDD structure | sdd.md must mirror `phase1-analyst-SDD.md` section layout (§1-§10). Validator counts heading occurrences as a structural smoke check, not deep linting (markdown structure rigidity is honor-system — tagged HONOR_SYSTEM in §7) |
| Where the SDD lives long-term | In `tasks/<task_id>/sdd.md` only. Promotion to `docs/<task_id>-SDD.md` (project docs) is operator's call after review, not sdd_writer's job |
| Spawn model: spawn or inline in L2? | **Spawn.** Same isolation, same observability via peek/kill, same `wt` tab UX. Inline in L2 would pollute L2's context with the writing pass (typically >50k tokens for an SDD of this size) and would block L2 for the duration. [DECIDED — operator may override; see OQ1 below if reconsidering] |
| Wrappers `peek-sdd-writer.ps1` / `kill-sdd-writer.ps1` | Phase-specific copies of Phase 1 wrappers. wt window title = `sdd-writer:<task_id>`. Code duplication acknowledged; merging into phase-agnostic `peek-task.ps1`/`kill-task.ps1` is Phase 5 tech-debt cleanup, NOT this phase (FF8: don't refactor beyond what task requires) |
| `--dangerously-skip-permissions` blast radius | Same as Phase 1 §2: full FS write. Mitigations same — read-only contract in prompt + Stage 6 `git status` sanity check in workspace. Risk accepted, documented (FF5 tag) |
| Retry budget on validate failure | Max 2 retries (same as analyst, prompts/sdd-writer.md reproduces the Phase 1 retry-flow shape) |
| Model | Default (Opus, what operator runs). Downgrade to `--model sonnet` only if writing pass routinely exceeds session budget |

---

## 3. Repo layout after Phase 2

```
Orchestrator/
├── CLAUDE.md                                 # (unchanged) L2 router contract
├── README.md                                 # (updated) Phase 2 entry points added
├── projects.yaml                             # (unchanged)
├── pyproject.toml                            # (unchanged — pydantic + pyyaml already cover Phase 2)
├── docs/
│   ├── phase1-analyst-SDD.md                 # (unchanged)
│   ├── audit-phase1.md                       # (unchanged)
│   ├── writer-forcing-functions.md           # (unchanged — referenced from prompts/sdd-writer.md)
│   ├── phase2-kickoff-brief.md               # (unchanged — input to this SDD)
│   ├── phase2-sdd-writer-SDD.md              # this document
│   └── audit-phase2.md                       # NEW (operator-triggered post-Stage-6 if used)
├── prompts/
│   ├── analyst.md                            # (unchanged)
│   └── sdd-writer.md                         # NEW
├── skills/                                   # (unchanged — same 5 skills, sdd_writer reads them too)
├── schemas/
│   ├── analysis_v2.py                        # (unchanged — input contract)
│   └── sdd_v1.py                             # NEW — sidecar contract
├── templates/
│   ├── analyst-CLAUDE.md.tpl                 # (unchanged)
│   ├── analyst-mcp.json.tpl                  # (unchanged)
│   ├── sdd-writer-CLAUDE.md.tpl              # NEW
│   └── sdd-writer-mcp.json.tpl               # NEW
├── scripts/
│   ├── spawn-analyst.ps1                     # (unchanged)
│   ├── _run-analyst.ps1                      # (unchanged)
│   ├── peek-analyst.ps1                      # (unchanged)
│   ├── kill-analyst.ps1                      # (unchanged)
│   ├── validate-analysis.ps1                 # (unchanged)
│   ├── spawn-sdd-writer.ps1                  # NEW
│   ├── _run-sdd-writer.ps1                   # NEW
│   ├── peek-sdd-writer.ps1                   # NEW
│   ├── kill-sdd-writer.ps1                   # NEW
│   ├── validate-sdd.ps1                      # NEW
│   ├── _run-smoke.ps1                        # (unchanged — covers Stage 0 for any L3)
│   └── _python/
│       ├── yaml_get.py                       # (unchanged)
│       ├── validate.py                       # (unchanged — analyst)
│       ├── validate_sdd.py                   # NEW — sdd_writer + cross-checks analyst session.jsonl
│       ├── _test_schema.py                   # (unchanged)
│       ├── _test_templates.py                # (extended — adds sdd-writer template fixtures)
│       ├── _test_validate.py                 # (unchanged)
│       ├── _test_sdd_schema.py               # NEW — sdd_v1 fixtures
│       └── _test_validate_sdd.py             # NEW — exit-code fixtures
└── tasks/                                    # (gitignored, unchanged shape)
```

Net NEW files: 11 (2 templates, 1 prompt, 1 schema, 5 ps1, 2 python tests + 1 python validator). Net edits: 1 file (`scripts/_python/_test_templates.py` extends; `README.md` lists new entry points).

---

## 4. End-to-end flow

```
[Operator in this Orchestrator L2 session]
    -> "Напиши SDD по таску 2026-05-22-example-erp-01"
[Claude = L2]
    1. Resolve task_id -> tasks/<task_id>/ on disk
    2. Pre-check: analysis_report.json exists AND validate-analysis.ps1 passes (exit 0)
       (sdd_writer refuses to write SDD on a non-validated analysis)
    3. Spawn scripts/spawn-sdd-writer.ps1 -TaskId 2026-05-22-example-erp-01
        ├── reads tasks/<task_id>/task_packet.json -> project_id, project_path, etc.
        ├── renders templates/sdd-writer-CLAUDE.md.tpl -> tasks/<task_id>/CLAUDE.sdd-writer.md
        ├── renders templates/sdd-writer-mcp.json.tpl -> tasks/<task_id>/.mcp.sdd-writer.json
        ├── writes tasks/<task_id>/sdd_writer_packet.json (sidecar to task_packet.json)
        ├── writes tasks/<task_id>/prompt.sdd-writer.md
        ├── pre-trusts task_root + orchestrator_root (analyst already did this, idempotent)
        └── wt.exe -w 0 nt --title "sdd-writer:<task_id>" powershell.exe -File _run-sdd-writer.ps1 ...
[sdd_writer in new wt tab]
    - reads CLAUDE.sdd-writer.md (role + context)
    - reads prompts/sdd-writer.md (phase contract; includes FF1-FF8 self-audit checklist)
    - reads tasks/<task_id>/analysis_report.json (input)
    - verifies findings via MCP (codemetadata) — own queries dumped to sdd_raw/
    - writes tasks/<task_id>/sdd.md
    - writes tasks/<task_id>/sdd_metadata.json
    - post-Write Read on both files
    - announces "SDD READY"
[Operator] "готов" or "глянь, что он делает"
[Claude = L2]
    - "готов" -> scripts/validate-sdd.ps1 -TaskId X
        ├── Pydantic-validate sdd_metadata.json (schema_sdd_v1)
        ├── sdd.md heading-shape smoke check (must have §1-§10 headings)
        ├── analyst-session real-MCP check: walk analyst session.jsonl, count tool_use.name ~ ^mcp__
        ├── writer-session real-MCP check: walk sdd_writer session.jsonl, same count
        └── if all pass — exit 0 with summary
    - "глянь" -> scripts/peek-sdd-writer.ps1 -TaskId X
        └── tail last N events from writer's session.jsonl + LAST_EVENT_AGO
```

---

## 5. Stages

### Stage 0 — Spawn-mechanism smoke (mirror Phase 1 Stage 0, scoped to sdd-writer wrapper)

**Goal:** prove that `wt -> powershell -> _run-sdd-writer.ps1 -> claude` works with the planned argument shape BEFORE we author task-specific templates.

**What breaks (FF3):** mostly impossible at this point since the Phase 1 chain has already been smoked; but the sdd-writer wrapper takes different args (`-AnalysisTaskRoot` vs `-TaskRoot`), so a parameter typo would silently break Stage 4.

**Steps:**
1. Write `scripts/_run-sdd-writer.ps1` stub that just echoes its three params + path-resolves `analysis_report.json` and confirms it exists. No `claude` call yet.
2. From this session: run the stub with PowerShell directly (no `wt`) against the existing `tasks/2026-05-22-example-erp-01/` task, confirm it resolves and exits 0.
3. Wrap it in `wt.exe -w 0 nt --title "sdd-writer-smoke" powershell.exe -File scripts/_run-sdd-writer.ps1 -TaskRoot ...` — confirm new tab opens and stub prints expected output.

**Verification (auto, binary):**
- `wt` opens new tab titled `sdd-writer-smoke`
- Stub stdout contains `analysis_report.json EXISTS: true`
- Stub exit code = 0

**No marker file needed** — Phase 1 Stage 0 already proved the `wt -> powershell -> claude` end-to-end binding [VERIFIED via RLM fact 7e2d8d53]; this stage tightens to the new wrapper only.

### Stage 1 — schemas/sdd_v1.py (Pydantic sidecar contract)

**Deliverables:**
- `schemas/sdd_v1.py` — standalone Pydantic v2, zero `from <prior-iteration>` imports (mirror analysis_v2.py hygiene). [FF2: recursive import walk N/A — nothing to inline; designed from scratch.]

**Schema sketch (binding for Stage 2 prompt):**
```python
class SDDMetadata(ArtifactModel):
    schema_version: Literal["v1"]
    task_id: str                              # matches input analysis_report.task_id
    analysis_report_ref: Literal["analysis_report.json"]
    sdd_path: Literal["sdd.md"]
    task_size: Literal["XS","S","M","L","XL"]
    stages: list[SDDStage]                    # >=1
    open_questions: list[SDDOpenQuestion]     # may be empty
    risks: list[SDDRisk]                      # may be empty
    refusals: list[str]                       # what writer refused to design and why
    dod_pre: list[str]                        # binary pre-conditions before stage 1 starts
    dod_post: list[str]                       # binary post-conditions for "done"
    ff_self_audit: dict[Literal["FF1","FF2","FF3","FF4","FF5","FF6","FF7","FF8"], FFOutcome]
    citations_used: list[Citation]            # >=1; cross-reference into analysis_report or new MCP
    self_review_notes: str

class SDDStage(ArtifactModel):
    id: str                                   # e.g. "Stage 0", "Stage 1"
    title: str
    deliverables: list[Deliverable]           # >=1; tightened 2026-05-22 (Phase 3 IOQ2): structured, not bare str
    verifications: list[str]                  # >=1, each must be a binary check
    failure_modes: list[str]                  # FF3 enforcement: >=1 OR explicit "none beyond schema exits"

class Deliverable(ArtifactModel):
    path: str                                 # bare repo-relative file path (no English suffix)
    description: str | None                   # optional human prose

class SDDOpenQuestion(ArtifactModel):
    id: str                                   # e.g. "OQ1"
    severity: Literal["info","decision","blocker"]
    question: str
    recommendation: str                       # writer's proposed resolution; operator may override

class SDDRisk(ArtifactModel):
    summary: str
    mitigation: str                           # >=1 mitigation OR explicit "RISK ACCEPTED: <reason>"

class FFOutcome(ArtifactModel):
    status: Literal["pass","na","fail"]
    note: str                                 # required even on pass — quote evidence

class Citation(ArtifactModel):                # reuse analysis_v2 shape; do NOT import — inline
    source: Literal["mcp","code","rlm","raw_artefact","analysis_report"]
    ref: str
    excerpt: str | None = None
```

**Validators (binding for validate_sdd.py exit codes):**
- `task_id` matches the input `analysis_report.json.task_id` — enforced cross-file in validate_sdd, not in pydantic
- `ff_self_audit` must have all 7 keys present (model_validator)
- `dod_pre` and `dod_post` each >=1 entry (model_validator)
- Each `SDDStage.failure_modes` non-empty (already by Pydantic min_length=1)
- `Citation.source = "analysis_report"` requires `ref` to start with `analysis_report.json#` (field_validator)

**Verification (FF3 binary list):**
- `python -c "from schemas.sdd_v1 import SDDMetadata; print(sorted(SDDMetadata.model_fields.keys()))"` exits 0, lists 14 fields
- `grep -E "^(from|import) <prior-iteration>" schemas/sdd_v1.py` — empty
- `scripts/_python/_test_sdd_schema.py` fixtures pass:
  - (a) valid full metadata -> OK
  - (b) missing `ff_self_audit["FF4"]` -> ValidationError
  - (c) `task_size = "huge"` -> ValidationError
  - (d) `dod_pre = []` -> ValidationError
  - (e) `Citation(source="analysis_report", ref="something_else")` -> ValidationError

### Stage 2 — prompts/sdd-writer.md

**Deliverables:**
- `prompts/sdd-writer.md` — phase contract. Embeds FF1-FF8 (referenced from `docs/writer-forcing-functions.md` by absolute path under `{ORCHESTRATOR_ROOT}`).

**Required prompt content (FF6 forcing functions, not honor-system):**
- Anti-assumption rule (mirror analyst.md)
- Multi-round verification: sdd_writer must issue >=1 MCP query for any non-trivial finding it carries forward from analysis_report (FF4 — code over doc; do not trust the analyst's narrative)
- Citation discipline: every claim in sdd.md cites either `analysis_report.json#<section>` or a new MCP/code/rlm ref
- Output contract: write sdd.md + sdd_metadata.json, post-Write Read each, announce literally `SDD READY` on its own line
- FF1-FF8 self-audit checklist: must populate `sdd_metadata.ff_self_audit` with all 7 keys, each pass/na/fail + note. `fail` is allowed but blocks DoD post-condition; `na` requires explicit reason
- Refusal contract: writer may REFUSE to design specific stages and must list them in `metadata.refusals` with reasons (mirror Phase 1 §9)
- Retry-on-validate-exit-code flow (exit codes listed in Stage 5)

**Verification (FF3 binary list):**
- `grep -E "FF[1-7]" prompts/sdd-writer.md` produces >=14 matches (each FF mentioned >=2 times)
- `grep "SDD READY" prompts/sdd-writer.md` produces >=1 match
- File contains no Cyrillic [VERIFIED constraint via memory/feedback_powershell_5_1_gotchas.md — N/A, this is .md not .ps1, but English-only for sdd_writer-facing prompts is the brief's rule]
- File header references `docs/writer-forcing-functions.md` by `{ORCHESTRATOR_ROOT}/docs/writer-forcing-functions.md` absolute path

### Stage 3 — templates (CLAUDE.md.tpl + mcp.json.tpl for sdd_writer)

**Deliverables:**
- `templates/sdd-writer-CLAUDE.md.tpl` — first-thing-writer-reads. Placeholders:
  - `{PROJECT_ID}`, `{PROJECT_PATH}`, `{TASK_ID}`, `{TASK_TEXT}`, `{ORCHESTRATOR_ROOT}`, `{TASK_ROOT_ABS}`
  - NEW for Phase 2: `{ANALYSIS_REPORT_REL}` = literal `"analysis_report.json"` (allows future relocation without re-templating)
- `templates/sdd-writer-mcp.json.tpl` — `.mcp.json` for codemetadata, same shape as analyst. Placeholder `{CODEMETADATA_URL}`.

**Why two MCP files (analyst-mcp.json.tpl AND sdd-writer-mcp.json.tpl) instead of sharing?** The per-task render goes into a distinct file (`.mcp.sdd-writer.json` vs `.mcp.json`) so a sdd_writer spawn does not stomp the analyst's `.mcp.json` if the analyst tab is still around. Slightly redundant content but supports concurrent observability.

**Verification (FF3 binary):**
- Both files exist
- `python scripts/_python/_test_templates.py` (extended) renders both templates with fixture values and asserts:
  - No `{...}` placeholder remains in output
  - mcp.json output parses as JSON and has `type: "http"` (FF4: D1 regression — Streamable HTTP, not SSE) [VERIFIED via RLM fact 486bd6e3 D1 close-out + commits 1f1df73 + fe54656]
  - CLAUDE.md output mentions absolute path `{ORCHESTRATOR_ROOT}/prompts/sdd-writer.md` (resolved)

### Stage 4 — spawn-sdd-writer.ps1 + _run-sdd-writer.ps1

**4.1 `scripts/spawn-sdd-writer.ps1`**

**Params:**
- `-TaskId <string>` (required) — must reference an existing `tasks/<task_id>/` with passing `analysis_report.json`
- `-PrepareOnly` (switch) — generate files but skip `wt` spawn (for tests)

**Steps:**
1. Resolve `tasks/<TaskId>/`. If absent, exit 1 with diagnostic.
2. Read `tasks/<TaskId>/task_packet.json` (created by analyst spawn). Extract `project_id`, `project_path`, `orchestrator_root`, `codemetadata_url`. (FF1 [VERIFIED via spawn-analyst.ps1 line 165-178 — task_packet shape is stable Phase 1 contract.])
3. **Gating pre-check:** run `python scripts/_python/validate.py <task_root>`. If exit != 0, refuse to spawn (exit code 5 with message: "analysis_report.json not validated; run validate-analysis.ps1 first").
4. **path_local INVARIANT pre-check:** same fail-fast as `spawn-analyst.ps1` (check `Configuration.xml` + `Catalogs/` under `project_path`). [FF1 [VERIFIED via lines 98-109 of spawn-analyst.ps1.]]
5. Render templates with placeholder dict. Write:
   - `tasks/<TaskId>/CLAUDE.sdd-writer.md`
   - `tasks/<TaskId>/.mcp.sdd-writer.json`
   - `tasks/<TaskId>/sdd_writer_packet.json` (writer-side metadata: `created_at`, `wt_window_title`, `analyst_session_dir_hint` resolved at spawn time so validator can find it later)
   - `tasks/<TaskId>/prompt.sdd-writer.md` (one-liner that points at `./CLAUDE.sdd-writer.md`)
   - `tasks/<TaskId>/sdd_raw/` directory (analogue of `analysis_raw/`)
6. Pre-trust (idempotent — analyst already wrote these): `~/.claude/projects/<encoded>/settings.json {trusted:true}` for both case variants of task_root and orchestrator_root.
7. Spawn `wt.exe`:
   ```
   wt.exe -w 0 nt --title "sdd-writer:$TaskId" powershell.exe -NoExit -ExecutionPolicy Bypass `
     -File "$PSScriptRoot\_run-sdd-writer.ps1" `
     -TaskRoot "$TaskRoot" `
     -ProjectPath "$ProjectPath" `
     -OrchestratorRoot "$OrchestratorRoot"
   ```
8. Print JSON to stdout with `{task_id, task_root, wt_window_title, expected_session_dir_hint}`.

**4.2 `scripts/_run-sdd-writer.ps1`** — same shape as `_run-analyst.ps1`, but reads `prompt.sdd-writer.md` and `.mcp.sdd-writer.json`. ASCII-only [VERIFIED via memory/feedback_powershell_5_1_gotchas.md].

**What breaks (FF3 — failure modes):**
- analyst hasn't run yet or analysis_report.json missing -> exit 1, clear message
- analyst report present but invalid -> exit 5 (above)
- `task_packet.json` schema drift between Phase 1 and Phase 2 -> spawn fails reading; covered by Stage-4 verification fixture using the real `2026-05-22-example-erp-01` packet
- `wt.exe` absent -> exit 2 with manual-run fallback (same as analyst)
- Concurrent invocation (two sdd-writer spawns on same task_id) -> SDD content collision possible; mitigation: if `sdd_metadata.json` already exists at task_root, exit 6 ("sdd already exists; remove or use different task_id"). Operator override: `-Force` switch deletes existing sdd.md + sdd_metadata.json + sdd_raw/

**Verification (FF3 binary):**
- `spawn-sdd-writer.ps1 -TaskId 2026-05-22-example-erp-01 -PrepareOnly` exits 0, creates 4 files + `sdd_raw/`
- Negative: `spawn-sdd-writer.ps1 -TaskId nonexistent -PrepareOnly` exits 1
- Negative: stage a fake task with broken `analysis_report.json` -> exit 5
- Negative: stage a fake task with `Configuration.xml` missing -> exit 1 (path_local invariant)
- Concurrent: re-running spawn on a task that already has `sdd_metadata.json` -> exit 6 unless `-Force`

### Stage 5 — validate_sdd.py + validate-sdd.ps1

**5.1 `scripts/_python/validate_sdd.py`**

**Input:** `<task_root>` (positional). Discovers `analyst_session.jsonl` + `writer_session.jsonl` via `~/.claude/projects/*Orchestrator*tasks*<task_id>*/` glob.

**Exit codes:**

| exit | meaning | message |
|---|---|---|
| 0 | OK | summary (counts, FF audit results, MCP-usage tallies for both sessions) |
| 1 | sdd_metadata.json Pydantic ValidationError | full ValidationError |
| 2 | sdd.md missing OR has fewer than §1-§10 top-level headings | which headings missing |
| 3 | `sdd_metadata.task_id` != input `analysis_report.task_id` | both values shown |
| 4 | sdd_metadata.json absent at task_root | "sdd_writer did not produce sdd_metadata.json" |
| 5 | sdd_metadata.json not parseable | JSONDecodeError line/col |
| 6 | **analyst session.jsonl shows 0 `tool_use.name` matching `^mcp__`** (OPERATIONAL QUALITY GATE — Phase 2 brief §6) | "input analysis was synthesized without real MCP — re-run analyst before SDD" |
| 7 | **writer session.jsonl shows 0 `tool_use.name` matching `^mcp__`** (FF4 forcing function for the writer itself) | "sdd_writer did not consult MCP — refused" |
| 8 | `ff_self_audit.<FFi>.status == "fail"` for any FFi | which FFs failed + their notes |

**Summary at exit=0:** task_id, task_size, len(stages), open_questions by severity, risks count, refusals count, FF audit (7 booleans), analyst-session MCP-tool-use count, writer-session MCP-tool-use count.

**Session.jsonl walker (shared helper):**
```python
def count_mcp_tool_use(jsonl_path: Path) -> int:
    count = 0
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        try: ev = json.loads(line)
        except json.JSONDecodeError: continue
        msg = ev.get("message", {})
        for c in (msg.get("content") or []):
            if c.get("type") == "tool_use" and (c.get("name") or "").startswith("mcp__"):
                count += 1
    return count
```
[FF1 [VERIFIED via peek-analyst.ps1 lines 55-69 — event shape `message.content[].type == "tool_use"` with `name` field is the format Claude Code 2.1.119 writes; same parser used in Stage 7.]]

**5.2 `scripts/validate-sdd.ps1`** — thin wrapper, `-TaskId X`, passes through python exit code. Uses `[Console]::Error.WriteLine` + `exit N` + `ErrorActionPreference = Continue` [FF1 [VERIFIED via memory/feedback_powershell_5_1_gotchas.md Gotcha 2.]]

**Verification (FF3 binary, via `_test_validate_sdd.py`):**
- (a) Full valid task — exit 0, summary correct
- (b) Drop `ff_self_audit["FF1"]` — exit 1
- (c) sdd.md missing §5 heading — exit 2
- (d) sdd_metadata.task_id != analysis_report.task_id — exit 3
- (e) sdd_metadata.json absent — exit 4
- (f) sdd_metadata.json = `not json{` — exit 5
- (g) Mock analyst session.jsonl with zero `mcp__` tool_use entries — exit 6
- (h) Mock writer session.jsonl with zero `mcp__` tool_use entries — exit 7
- (i) `ff_self_audit["FF4"] = {status: "fail", note: "..."}` — exit 8

### Stage 6 — e2e smoke against `2026-05-22-example-erp-01`

**Why this task:** Phase 1 Stage 6 produced a real validated `analysis_report.json` at `tasks/2026-05-22-example-erp-01/` [VERIFIED via Bash ls]. Reusing it lets Stage 6 exercise the full Phase 2 chain without first running another analyst.

**Steps:**
1. `git status` baseline in `Orchestrator/` (must be clean except `docs/phase2-sdd-writer-SDD.md` if work-in-progress) AND in `<workspace>/1c-projects/example-erp/src` (must be clean — sdd_writer must not modify).
2. `scripts/spawn-sdd-writer.ps1 -TaskId 2026-05-22-example-erp-01` — opens `sdd-writer:2026-05-22-example-erp-01` tab.
3. Observe via `scripts/peek-sdd-writer.ps1 -TaskId 2026-05-22-example-erp-01 -Tail 30`. Wait for `SDD READY`.
4. `scripts/validate-sdd.ps1 -TaskId 2026-05-22-example-erp-01` — must exit 0.
5. Sanity-checks (FF1 [VERIFIED at runtime]):
   - `tasks/2026-05-22-example-erp-01/sdd.md` and `sdd_metadata.json` exist
   - `git status` in `example-erp-src` clean (no writer escape)
   - At least 3 distinct `Citation` entries in `sdd_metadata.citations_used` reference real lines in `analysis_report.json` (each ref starts with `analysis_report.json#`)
   - sdd.md mentions task_id at least once
   - Pick 3 random `analysis_report.relevant_files[*].path` and grep for them in `sdd.md` — at least 1 of 3 referenced (writer should drill into Findings, not skip files)
6. **Retry flow:** identical pattern to Phase 1 §5 Stage 6 retry-flow — operator sees validate exit code, pastes guidance into the writer's tab as followup, max 2 retries.

**What breaks (FF3):**
- Hang / no progress: peek prints `LAST_EVENT_AGO > 300s WARNING`; operator runs `kill-sdd-writer.ps1`
- Partial write: post-Write Read in prompt + validate exit 4
- MCP timeout: writer records `OpenQuestion` of severity blocker; visible in metadata
- Writer chases analyst's narrative without re-verifying: caught by exit 7 (zero MCP tool_use in writer session)

### Stage 7 — peek-sdd-writer.ps1 + kill-sdd-writer.ps1

**peek-sdd-writer.ps1:**
- Params: `-TaskId X`, `-Tail N` (default 30)
- Discovery: `Get-ChildItem ~/.claude/projects -Directory | Where Name -like "*Orchestrator*tasks*<TaskId>*"` then pick newest by `LastWriteTime` (mirror Phase 1 Stage 7 [FF1 [VERIFIED via peek-analyst.ps1 lines 22-30].])
- Disambiguation: `~/.claude/projects/` may have TWO matching dirs (one from analyst, one from writer) — same cwd-encoded path. Practically session dirs are unique per session-uuid not per cwd; the glob returns all matching session dirs. Sort by `LastWriteTime` descending and pick the newest -> writer's session (since writer ran later). If operator needs analyst's session events instead, they use the Phase 1 `peek-analyst.ps1`.
- Same event-formatting as `peek-analyst.ps1`. Same `LAST_EVENT_AGO` health line.

**kill-sdd-writer.ps1:**
- Title pattern: `*sdd-writer:<TaskId>*` (not `analyst:`)
- Stamps `sdd_writer_packet.killed_at`
- Identical body otherwise

**Verification (FF3 binary):**
- After Stage 6 run, `peek-sdd-writer.ps1 -TaskId 2026-05-22-example-erp-01` returns >0 events + `LAST_EVENT_AGO=<s>`
- Mocked-stuck case: artificially set `LastWriteTime` to 6 minutes ago -> WARNING printed
- `kill-sdd-writer.ps1 -TaskId <dummy>` — kills dummy wt tab whose title contains `sdd-writer:<dummy>`, stamps `killed_at`

---

## 6. Open Questions

### OQ1 — Spawn vs inline (operator confirmation needed)

Spawn is proposed (§2 table, Decision row). Open question only if operator prefers inline (would block L2 for ~50k tokens during writing; sacrifices observability; deletes peek/kill from Phase 2 deliverables — Stages 7 collapse).

**Recommendation:** spawn. Same UX as Phase 1, additive learning, full L4 visibility.

### OQ2 — Should sdd_writer be allowed to surface BLOCKER OQs (and refuse to write SDD)?

The analyst is allowed; sdd_writer should be too, with caveat: validate_sdd should NOT auto-fail when `open_questions` contains blockers. Producing a blocker-only SDD (with `stages = []`) is a legitimate output if the analysis_report's findings can't be designed against.

**Recommendation:** allow. Treat as a `task_size = "XS"` SDD with metadata.refusals listing what was refused and why. Operator decides next step (re-analyst, downgrade scope, accept blockers).

### OQ3 — Does sdd_writer get RLM MCP access?

The analyst doesn't (Phase 1 §6 OQ2 closed naparnik=deferred, codemetadata only). RLM is institutional memory across projects; sdd_writer might benefit from looking up "have we designed something like this before?".

**Recommendation:** **defer to Phase 3+.** Phase 2 stays with codemetadata only — same risk surface as analyst, less to debug. If sdd_writer's outputs feel shallow without project-history memory, revisit in Phase 3 design.

### OQ4 — Audit pass after Stage 6?

Phase 1 has `docs/audit-phase1.md` written by an independent Claude session. Phase 2 SDD itself was written under FF1-FF8 self-audit; an external audit pass is the operator's call, not a self-required step.

**Recommendation:** operator-triggered. If used, output -> `docs/audit-phase2.md`, listed as a Stage 6-deferred check, NOT a DoD blocker.

### OQ5 — Memory hook on Phase 2 DONE

After merge to main, what RLM fact + memory file does Phase 2 leave?

**Recommendation:**
- One RLM fact in `domain=tasks, module=Orchestrator`: "Phase 2 sdd_writer DONE @<commit>" with operational invariants (writer-session real-MCP check active, sdd_metadata.json contract live).
- One memory file `project_phase2_done.md` under `~/.claude/projects/.../memory/`, MEMORY.md index updated. Mirror `project_phase1_done.md` shape.

---

## 7. Risks and mitigations

| Risk | Mitigation | Tag |
|---|---|---|
| sdd_writer trusts analyst narrative blindly, propagates Phase 1 errors | validate_sdd exit 7 enforces writer ran real MCP queries; prompts/sdd-writer.md FF4 instruction | FF4, FF6 (code-level, not honor) |
| Analyst session was synthesized via Bash+curl (D1-style failure pattern) | validate_sdd exit 6 walks analyst session.jsonl for `mcp__` tool_use entries; refuses if 0 [VERIFIED via RLM fact 0d131b79 finding #5 — this is the brief's mandatory gate] | FF4 |
| Writer hangs or loops | `peek-sdd-writer.ps1 LAST_EVENT_AGO>300s WARNING` + `kill-sdd-writer.ps1` | FF3 |
| Writer writes outside task_root | RISK ACCEPTED for Phase 2 (same as Phase 1). Sanity-check at Stage 6: `git status` in `example-erp-src` + `Orchestrator/` shows no out-of-task writes | FF5 (blast radius: `--dangerously-skip-permissions` -> full FS write; no technical sandbox until Phase 3+) |
| sdd.md markdown structure is honor-system (validator only counts §1-§10 headings, not content quality) | HONOR_SYSTEM: structural-quality of sdd.md -- mitigation in Phase 3 via auditor + operator review on first 2-3 runs | FF6 honor-tagged |
| `sdd_metadata.task_id` accidentally hardcoded by writer (copy-paste from analysis_report) | validate_sdd exit 3 cross-checks against analysis_report.task_id | FF6 (code-level) |
| Writer uses `--dangerously-skip-permissions` to silently install pip packages mid-run | RISK ACCEPTED. Same blast-radius as Phase 1. Mitigation: Stage 6 `git status` plus `pip list --outdated` baseline diff (manual op, not validator-enforced) | FF5 |
| `wt.exe` not on PATH (e.g. Server Core image) | Same as Phase 1: spawn falls back to fallback-message + manual `_run-sdd-writer.ps1` invocation hint | FF1 [VERIFIED via spawn-analyst.ps1 lines 203-209] |
| `task_packet.json` schema drift between Phase 1 spawn and Phase 2 spawn | Stage 4 fixture test reads the real `tasks/2026-05-22-example-erp-01/task_packet.json` and asserts required keys present | FF1, FF2 |
| Two writer-attempts on same task collide on sdd.md | spawn-sdd-writer.ps1 exit 6 if metadata exists; `-Force` opt-in to delete | FF3 |
| `peek-sdd-writer.ps1` returns analyst's session instead of writer's | Pick newest dir by `LastWriteTime`; if operator wants the older session they use `peek-analyst.ps1`. Documented in Stage 7. | FF3 (disambiguation) |
| Codemetadata indexer differs between analyst run (Phase 1) and writer run (now) | RISK ACCEPTED. The 30-min Gitea sync means up to 30 min drift. Mitigation: prompts/sdd-writer.md asks writer to NOT re-verify schema-level facts already cited by analyst unless drift is suspected; only re-verify high-impact decisions. Detection: if writer's MCP tool_use count is >2x analyst's, writer is over-querying — operator notices | FF1 |
| Analyst session dir no longer exists when validate_sdd runs (operator cleared `~/.claude/projects/`) | validate_sdd exit 6 with diagnostic "analyst session.jsonl not found -- cannot verify real-MCP gate". Forces operator to either re-run analyst or override (no override switch in Phase 2; manual decision is to re-run) | FF3 |

---

## 8. Definition of Done

### Pre-conditions (FF7 — BEFORE Stage 1 starts)

- **0a.** All OQ1-OQ5 closed in §10 with resolution text.
- **0b.** Stage 0 smoke (wrapper-stub spawning in `wt` tab) PASSES.
- **0c.** path_local INVARIANT (carried from Phase 1) remains intact: `projects.yaml` unchanged, codemetadata containers still indexing the mirrored XML dumps. [FF1 [VERIFIED via RLM fact fc696e57; spawn-sdd-writer.ps1 re-enforces fail-fast.]]
- **0d.** **Operator quality-gate semantics signed off** (Phase 2 NEW pre-condition): operator confirms that `validate_sdd.py` rejecting on zero `mcp__` tool_use entries in analyst session.jsonl is the correct gate (vs e.g. count threshold >1, or per-server presence). Without this sign-off, Stage 5 implementation is paused at the gate logic. **Recommendation in this draft:** count == 0 fails; count >= 1 passes (same threshold as for the writer's own session).

### Post-conditions (FF7 — Phase 2 = DONE when)

1. All 8 stages (0-7 above) shipped, each verification list passes.
2. Stage 6 e2e on `2026-05-22-example-erp-01` produces a valid `sdd.md` + `sdd_metadata.json`; `validate-sdd.ps1` exits 0.
3. Stage 6 sanity-checks: `example-erp-src` untouched (`git status` clean); >=1 of 3 random `relevant_files` paths cross-referenced in sdd.md; sdd_metadata.citations_used has >=3 entries.
4. `peek-sdd-writer.ps1` and `kill-sdd-writer.ps1` verified on a dummy and on the Stage 6 task.
5. master pushed to Gitea, merged into main at the Phase 2 closeout commit.
6. RLM fact written: `Phase 2 sdd_writer DONE @<commit>` with operational invariants list.
7. `MEMORY.md` updated with one-line entry pointing to new `project_phase2_done.md`.

---

## 9. Refusals (REFUSE)

Items deliberately NOT in Phase 2 scope:

- **Auditor for the SDD output.** External audit is operator-triggered post-Stage-6, not a Phase 2 deliverable. Self-audit via FF1-FF8 is in scope.
- **Implementation engine.** Phase 3 reads `sdd_metadata.json` + `sdd.md`; designing that handoff happens in Phase 3 SDD.
- **SDD localization to Russian.** AI-to-AI docs stay English per project convention.
- **Markdown deep-linter for sdd.md.** Validator counts heading shape only. Quality of prose is operator-judgment + (optional) external audit.
- **Schema versioning policy.** schema_sdd_v1 only. v2 happens when Phase 3 demands it.
- **Phase-agnostic peek/kill scripts (`peek-task.ps1`).** Phase 5 cleanup; current duplication is intentional.
- **Inline-in-L2 mode.** Spawn-only (OQ1 decision).

---

## 10. Resolutions (closure of Open Questions)

Resolutions promoted from PROVISIONAL to CLOSED 2026-05-22 under brief authorization (autonomous chain enabled, ROTATE mode). Operator retains override prerogative: if any resolution should flip, raise it during Stage 6 e2e and the affected stages are reworked before merge to main.

**OQ1 — Spawn vs inline:** CLOSED — SPAWN. Rationale: parity with analyst, observability via peek/kill, no L2 context pollution during a ~50k-token writing pass.

**OQ2 — Allow BLOCKER-severity OQs in sdd_metadata:** CLOSED — YES. SDD with `stages=[]` and `open_questions=[blocker:...]` is a legitimate output. validate_sdd does NOT auto-fail on blockers (only on FF audit fails, schema, missing file, exit codes 1-8 per §5.1). Operator decides next step on a blocker-only SDD: re-run analyst with broader scope, downgrade task, or accept blockers as escalation.

**OQ3 — RLM MCP access for sdd_writer:** CLOSED — NO for Phase 2. Codemetadata only, mirror analyst. Reason: same risk surface, fewer moving parts to debug. Revisit in Phase 3 design if implementer needs cross-project pattern lookup.

**OQ4 — External audit pass for this SDD before implementing:** CLOSED — NO (FF1-FF8 self-audit in §11 is the in-scope discipline). Operator may still trigger an external audit any time; output -> `docs/audit-phase2.md`, NOT a DoD blocker.

**OQ5 — Memory + RLM hook on DONE:** CLOSED — YES, mirror Phase 1: one RLM fact in `domain=tasks, module=Orchestrator` ("Phase 2 sdd_writer DONE @<commit>") + `project_phase2_done.md` memory file + one-line entry in `MEMORY.md` index.

**OQ6 — Operational quality-gate semantics (pre-condition 0d):** CLOSED — count == 0 fails, count >= 1 passes. Same threshold for both analyst-session check (validate_sdd exit 6) and writer-session check (exit 7). Rationale: zero `mcp__` tool_use entries is the unambiguous Bash+curl-synthesis signature seen in Phase 1 D1 incident [VERIFIED via RLM fact 0d131b79 finding #5]. A stricter threshold (e.g. >=N per server) is over-fitting until we have more incident data.

With OQ1-OQ6 CLOSED, DoD pre-conditions 0a + 0d are satisfied. 0b (Stage 0 smoke) is the first implementation gate. 0c (path_local INVARIANT) carries forward intact from Phase 1.

---

## 11. Writer FF1-FF8 self-audit (before submitting this SDD)

Per `docs/writer-forcing-functions.md` and `memory/feedback_writer_discipline.md` — the SDD writer (me, in this session) must self-audit against FF1-FF8 BEFORE handing off for review. Each gets pass / na / fail + note.

| FF | Status | Note |
|---|---|---|
| FF1 | pass | External claims tagged inline: `[VERIFIED via <fact/file/command>]` for path_local invariant (RLM fc696e57), D1 transport=http regression (RLM 486bd6e3 + commits 1f1df73/fe54656), wt-fallback (spawn-analyst.ps1:203-209), peek event shape (peek-analyst.ps1:55-69), task_packet stability (spawn-analyst.ps1:165-178), PS 5.1 ASCII rule + Write-Error exit-code Gotcha (memory/feedback_powershell_5_1_gotchas.md). One `[ASSUMED]`-equivalent: §7 "codemetadata indexer drift up to 30 min" — accepted, surfaced as risk row, no `[ASSUMED]` tag since it's a stated invariant from D2 sync timer. |
| FF2 | pass | "Recursive dependency walk" N/A for schemas — `schemas/sdd_v1.py` is designed from scratch, not inlined; FF2 obligation triggers only on copy/inline. The base `ArtifactModel` + `Citation` shape will be DUPLICATED (not imported) from analysis_v2.py — same as analysis_v2 did from <prior-iteration>. Stage 1 verification reasserts `grep -E "^(from\|import) <prior-iteration>" schemas/sdd_v1.py` empty. |
| FF3 | pass | Each stage (0-7) has explicit failure-modes paragraph or "What breaks" enumeration. Risk table §7 covers cross-stage failures. |
| FF4 | pass | Two code-over-doc checks: (a) D1 transport regression baked into Stage 3 verification + Stage 5 mcp.json type=http assertion [VERIFIED commits 1f1df73, fe54656]; (b) operational quality gate (validate_sdd exit 6) reads ACTUAL session.jsonl artifact, not the analyst's narrative claim. |
| FF5 | pass | Single dangerous primitive (`--dangerously-skip-permissions`) carries forward from Phase 1 with explicit blast-radius paragraph in §7 (writer can write anywhere on FS, including pip-installing packages mid-run). Risk ACCEPTED with same mitigations (read-only prompt + Stage 6 `git status` sanity). Alternative (`--permission-mode acceptEdits --allowedTools`) deferred to Phase 3+. |
| FF6 | pass | Honor-system items explicitly tagged: (a) sdd.md content-quality not validated by code -> HONOR_SYSTEM, mitigation deferred to operator review + optional Phase 3 audit; (b) writer's read-only contract on codebase -> HONOR_SYSTEM matching Phase 1, sanity-checked via Stage 6 git-status. All RELIABILITY-CRITICAL steps (real MCP usage, task_id consistency, file presence) replaced with code-level forcing functions (exit codes 3, 4, 6, 7, 8). |
| FF7 | pass | DoD §8 has BOTH pre-conditions (0a-0d) and post-conditions (7 binary checks). Pre-condition 0d is NEW for Phase 2 (operator sign-off on the operational quality-gate semantics) -- without it, Stage 5 is blocked. |

If operator approves with all FFs passing as marked above, this section freezes and Stage 0 may begin. If operator finds an FF should be FAIL (e.g. FF5 should not accept the risk), the writer rewrites the affected sections before Stage 0.

---

## End of draft

Operator next step: read sections §1-§11. If approved as-is, write resolutions for OQ1-OQ5 in §10 (marking PROVISIONAL -> CLOSED with any overrides). Then signal "начинаем Stage 0" and Phase 2 implementation chain begins on `master` with per-stage commits + `## DONE` markers, mirroring Phase 1's autonomous-chain pattern.
