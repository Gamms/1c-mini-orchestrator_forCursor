# SDD -- Orchestrator, Phase 5: hardening and wrapper consolidation

**task_id:** `orch-phase5-hardening-2026-05-23`
**task_size:** S (no new L3 runtime, no new schemas top-level; one new helper module, two new wrappers, prompt + schema field updates)
**author:** Claude (L2 in this Orchestrator session, parent of Phase 5 chain)
**date:** 2026-05-23
**status:** draft for operator review

---

## 1. Context and goal

Phase 4 (auditor) shipped 2026-05-22 at `5213edc`. The Stage 6 e2e on `2026-05-22-example-erp-02` produced `computed_verdict=reject` driven by a single blocker finding AF1: mirror byte-mismatch between implementer-local file (LF, 5851 bytes) and committed example-erp-src copy (CRLF, 5881 bytes after `core.autocrlf` rewrite on checkout). Operator overrode via `audit=override:...` convention because the drift was a known Git artefact, not semantic defect. Phase 4 closed with the override documented and the underlying autocrlf issue queued as a Phase 5 hardening item.

**Goal of Phase 5:**

1. Make the mirror byte-identity post-condition immune to autocrlf-driven LF<->CRLF rewrite (Group A).
2. Consolidate the 4 near-duplicate peek/kill wrapper pairs into one phase-agnostic pair (Group C).

After Phase 5 lands, Phase 4's chain (analyst -> writer -> implementer -> auditor -> operator signoff) re-runs against future tasks without recurrent CRLF false-rejects, and the operator's `peek-task.ps1` / `kill-task.ps1` work regardless of which phase is currently active in a task directory.

**Out of scope for Phase 5:**

* Rotation / autonomous chain (originally sketched as Phase 5 in Phase 4 SDD §10 -- redeferred).
* meta-auditor (no evidence-driven need).
* `validate-signoff.ps1` (convention not yet drifted).
* strict subset-check audit re_verifications vs impl_metadata.validations_attempted (Phase 5 OQ closure left for later).
* Editing 1C `path_local` repos (Phase 5 is pure Orchestrator-side: prompts, schemas, helpers, wrappers).
* Adding `.gitattributes` to per-project repos (would require write access + per-project decision; mitigation is hash-normalization at compare time, which is Phase 5 scope).

**Carry-forwards from Phases 1+2+3+4:**

* Spawn-per-task wt-tab model unchanged.
* Per-task CWD + rendered `CLAUDE.md` + MCP config unchanged.
* PowerShell 5.1 + ASCII-only `.ps1` [VERIFIED via `memory/feedback_powershell_5_1_gotchas.md`].
* FF1-FF8 forcing functions per `docs/writer-forcing-functions.md`.
* validate_impl + validate_audit exit codes UNCHANGED (Phase 5 adds no new exit codes; new mirror_check fields are additive on the schema, default-optional, so old fixtures keep passing).
* Stage 8 operator_signoff convention `audit=<verdict>` unchanged.

---

## 2. Constraints and decisions

| Constraint | Decision |
|---|---|
| Normalization scope | **LF/CRLF only.** Replace all `\r\n` with `\n` before hashing both sides of a mirror comparison. Do NOT strip BOM, trailing whitespace, or trailing newline -- those CAN be semantic in 1C XML or markdown. The only artefact we are immunizing against is autocrlf-driven line ending rewrite. [Closes OQ1.] |
| Normalization location | **Python helper, single source of truth: `scripts/_python/_hash_normalized.py`.** Mirrors `_codex_rollout.py` pattern: standalone module, ASCII source, no external deps beyond stdlib (hashlib + pathlib). PowerShell wrappers shell out to `python` if they need it. Rationale: easier to unit-test, single place to fix bugs, parallel to existing `_codex_rollout.py` / `_session_jsonl.py` parser modules. [Closes OQ2.] |
| Where the normalized hash gets recorded | `impl_metadata.validations_attempted[i].mirror_check` (new optional sub-field group) records BOTH `raw_sha256` (filesystem bytes) AND `normalized_sha256` (post-CRLF->LF). Same on auditor side: `audit_report.re_verifications_attempted[i].mirror_check`. Equality test the auditor cares about is `normalized_sha256` equality. `raw_sha256` is kept for diagnostics (operator can see whether the drift is real or just autocrlf). |
| schema_v1 backward compatibility | `mirror_check` is a new OPTIONAL sub-model on `ValidationAttempt`. All existing fixtures (impl + audit) pass unchanged because absence of the field is valid. New fixtures added explicitly to cover mirror_check present + matching, present + raw-diff-only, present + true-mismatch. |
| Implementer prompt update | `prompts/implementer.md` mirror post-condition section UPDATED: when `validations_attempted` includes a mirror compare, the implementer MUST populate `mirror_check.raw_sha256` and `mirror_check.normalized_sha256` for both sides. The `cmp identical` shorthand is replaced by a Python one-liner shelling out to `_hash_normalized.py` (or inline equivalent) that prints both hashes. |
| Auditor prompt update | `prompts/auditor.md` FF7 re-audit section UPDATED: when comparing mirror bytes, auditor MUST use `_hash_normalized.py` for the equality decision, NOT raw filesystem hash. Raw hash is captured for diagnostics. `FF7=pass` when normalized hashes match; `FF7=fail` only when normalized hashes ALSO differ (real semantic drift). |
| Wrapper consolidation strategy | **Single `peek-task.ps1` + single `kill-task.ps1` with auto-detect.** Phase detection rule: scan `tasks/<TaskId>/` for known packet files in priority order [auditor, implementer, sdd_writer, analyst]; highest-priority existing packet wins (later phases supersede earlier ones in the chain). Each packet's `created_at` is ALSO checked: if multiple packets exist, the one with latest `created_at` wins to defend against stale-packet edge cases. [Closes OQ3.] |
| Runtime dispatch in peek-task | Once phase detected: analyst/writer/implementer -> claude jsonl parser (`_session_jsonl.py`). auditor -> codex rollout parser (`_codex_rollout.py`). The packet's `codex_home` field is treated as the codex-runtime marker; if present, use codex parser. [Closes OQ4.] |
| Title prefix for kill-task | Derived from detected phase name: `analyst:` / `writer:` / `implementer:` / `auditor:`. wt title-match logic identical to existing kill-* scripts. |
| Old 8 wrappers fate | **Forwarding shims, one release.** Each old `peek-<phase>.ps1` and `kill-<phase>.ps1` rewritten to a 5-line shim that writes `DEPRECATED: use peek-task.ps1 / kill-task.ps1` to stderr and forwards to the new wrapper with the same TaskId. Shims kept for 1 release for muscle-memory continuity; deletion deferred. [Closes OQ3 continuation.] |
| Optional Stage E re-run | After A+C land, an OPTIONAL Stage E re-runs the Phase 4 Stage 6 e2e on example-erp-02 to verify the new mirror_check gates produce `ack` (the LF/CRLF artefact no longer drives reject). Stage E is operator-triggered, not part of the auto-merge condition for Phase 5; documented in §5 stage map but skippable if operator declines the rerun cost. |
| Phase 5 commit chain pattern | Mirror Phase 4: one commit per Stage; conventional commit prefix `feat`/`fix`/`docs`/`refactor`(phase5 stage<N>): pushed to gitea master after each stage. No merge to main (parity with Phase 3 + Phase 4 closure). |

---

## 3. Repo layout after Phase 5

```
Orchestrator/
|-- CLAUDE.md                                 # (unchanged)
|-- README.md                                 # (updated) Phase 5 entry points + peek-task / kill-task examples
|-- projects.yaml                             # (unchanged)
|-- pyproject.toml                            # (unchanged)
|-- docs/
|   |-- phase1-analyst-SDD.md                 # (unchanged)
|   |-- phase2-sdd-writer-SDD.md              # (unchanged)
|   |-- phase3-implementer-SDD.md             # (unchanged)
|   |-- phase4-auditor-SDD.md                 # (unchanged)
|   |-- writer-forcing-functions.md           # (unchanged)
|   |-- phase4-stage6-e2e-example-erp-02.md           # (unchanged -- input motivation for Group A)
|   |-- phase4-stage8-signoff-convention.md   # (unchanged)
|   |-- phase5-kickoff-brief.md               # NEW (created above)
|   `-- phase5-SDD.md                         # this document
|-- prompts/
|   |-- analyst.md                            # (unchanged)
|   |-- sdd-writer.md                         # (unchanged)
|   |-- implementer.md                        # (updated) mirror post-condition uses _hash_normalized
|   `-- auditor.md                            # (updated) FF7 re-audit uses _hash_normalized
|-- schemas/
|   |-- analysis_v2.py                        # (unchanged)
|   |-- sdd_v1.py                             # (unchanged)
|   |-- impl_v1.py                            # (updated) ValidationAttempt.mirror_check optional sub-model
|   `-- audit_v1.py                           # (updated) ValidationAttempt.mirror_check optional sub-model (DUPLICATED per FF2)
|-- templates/                                # (unchanged)
|-- scripts/
|   |-- spawn-{analyst,sdd-writer,implementer,auditor}.ps1   # (unchanged)
|   |-- _run-{analyst,sdd-writer,implementer,auditor}.ps1    # (unchanged)
|   |-- validate-{analysis,sdd,impl,audit}.ps1               # (unchanged)
|   |-- peek-{analyst,sdd-writer,implementer,auditor}.ps1    # (rewritten to forwarding shims)
|   |-- kill-{analyst,sdd-writer,implementer,auditor}.ps1    # (rewritten to forwarding shims)
|   |-- peek-task.ps1                                        # NEW (phase-agnostic)
|   |-- kill-task.ps1                                        # NEW (phase-agnostic)
|   `-- _python/
|       |-- _session_jsonl.py                                # (unchanged)
|       |-- _codex_rollout.py                                # (unchanged)
|       |-- _hash_normalized.py                              # NEW (LF/CRLF normalization + sha256)
|       |-- peek_codex_rollout.py                            # (unchanged)
|       |-- validate_impl.py                                 # (unchanged -- mirror_check is recorded by L3, not enforced by validator)
|       |-- validate_audit.py                                # (unchanged -- mirror_check usage is in auditor's FF7 logic, not in validator gates)
|       |-- _test_hash_normalized.py                         # NEW (Python unit tests for the helper)
|       |-- _test_validate_impl.py                           # (unchanged + new fixtures with mirror_check)
|       `-- _test_validate_audit.py                          # (unchanged + new fixtures with mirror_check)
`-- tasks/                                                   # (per-task artefacts; gitignored)
```

---

## 4. Open questions (resolved before Stage 1)

All four Phase 5 OQs are closed in §2 above. No OQs remain open going into implementation.

| OQ | Question | Decision (where) |
|---|---|---|
| OQ1 | Normalization scope: LF/CRLF only, or also BOM / trailing-whitespace? | LF/CRLF only (§2 row 1). |
| OQ2 | Helper location: Python or PowerShell? | Python `_hash_normalized.py` (§2 row 2). |
| OQ3 | Old 8 wrappers: shims or hard-delete? | Forwarding shims, 1 release (§2 row 9). |
| OQ4 | Runtime dispatch: by packet field or by phase name? | By packet `codex_home` presence (§2 row 7). |

---

## 5. Stage map

| Stage | Title | Files touched | Acceptance |
|---|---|---|---|
| 0  | SDD + kickoff brief                              | `docs/phase5-kickoff-brief.md` + `docs/phase5-SDD.md`                                                                 | This commit. Operator has the design before any code. |
| A1 | `_hash_normalized.py` helper + unit tests        | `scripts/_python/_hash_normalized.py` + `scripts/_python/_test_hash_normalized.py`                                    | 6+ fixtures: pure-LF identical, pure-CRLF identical, mixed-LF-CRLF normalized-equal, true mismatch, empty file pair, missing file. `python -m unittest scripts/_python/_test_hash_normalized.py` -> green. |
| A2 | impl + audit schemas: optional `mirror_check`    | `schemas/impl_v1.py` + `schemas/audit_v1.py` + new fixtures in `_test_validate_impl.py` + `_test_validate_audit.py`   | Existing fixtures unchanged + pass. New fixtures cover mirror_check absent (default), present + match, present + raw-diff-only, present + true-mismatch. Both validators still emit unchanged exit codes for unchanged fixtures. |
| A3 | implementer + auditor prompt updates             | `prompts/implementer.md` + `prompts/auditor.md`                                                                       | Prompts reference `_hash_normalized.py` in their mirror sections. ASCII-only. No other prompt sections touched. |
| C1 | `peek-task.ps1` + `kill-task.ps1` phase-agnostic | `scripts/peek-task.ps1` + `scripts/kill-task.ps1`                                                                     | New wrappers. Manual smoke: each spawned-but-not-finished phase from example-erp-02 archive yields correct phase detection + correct parser dispatch (claude jsonl for first 3, codex rollout for auditor). |
| C2 | Deprecate 8 old wrappers to forwarding shims     | `scripts/{peek,kill}-{analyst,sdd-writer,implementer,auditor}.ps1`                                                    | Each old wrapper becomes <=15-line shim: prints `DEPRECATED: use {peek,kill}-task.ps1` to stderr, forwards to new wrapper, exits with forwarded exit code. Existing operator muscle-memory still works. |
| E  | OPTIONAL e2e re-run on example-erp-02                    | none (re-run only; tasks/ is gitignored)                                                                              | spawn-auditor against example-erp-02 task archive (if still valid) -> validate_audit -> verdict `ack`. Operator-triggered; not blocking Phase 5 close. |
| Z  | Close-out: README + memory + RLM                 | `README.md` + new `memory/project_phase5_done.md` + MEMORY.md edit + RLM fact                                         | README has new entry points. MEMORY.md indexed. RLM fact at master close-out sha. |

---

## 6. DoD (definition of done)

Phase 5 is DONE when:

1. All Stages 0 + A1 + A2 + A3 + C1 + C2 + Z committed and pushed to gitea master.
2. All Python unit tests green (`python -m unittest discover scripts/_python -p "_test_*.py"` -- existing 105+ fixtures PLUS the new mirror_check + hash_normalized fixtures).
3. `python -m unittest scripts/_python/_test_hash_normalized.py` green.
4. Manual smoke: `peek-task.ps1 -TaskId 2026-05-22-example-erp-02` returns the auditor codex rollout tail (last phase wins).
5. Manual smoke: each old wrapper still forwards correctly with DEPRECATED line on stderr.
6. `git status` clean.
7. `MEMORY.md` index updated; `project_phase5_done.md` written.
8. RLM fact `domain=tasks, module=Orchestrator, level=1, code_ref=<phase5 close sha>` recorded.

Stage E (e2e re-run) is OPTIONAL for DoD -- if operator declines re-run, Phase 5 still closes on the unit-test green + smoke evidence above.

---

## 7. Non-goals (re-stated for clarity)

* Phase 5 does NOT modify validate_impl.py or validate_audit.py exit code semantics. mirror_check is a metadata field the L3 agents populate; validators do not enforce it (that would be a Phase 6+ hardening if operator wants it).
* Phase 5 does NOT add `.gitattributes` to per-project repos. That is a per-project decision and would require write access to the target repo; the hash-normalization approach immunizes Orchestrator-side comparisons without touching downstream repos.
* Phase 5 does NOT introduce a new schema version. `impl_v1` and `audit_v1` get additive optional fields; consumers reading old fixtures keep working.
* Phase 5 does NOT alter the wt-tab spawn pattern. peek-task / kill-task discover phase from packet files written by existing spawn-* scripts; no spawn surface changes.
