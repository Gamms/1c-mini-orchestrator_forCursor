# Writer Forcing Functions

> Болванка для `prompts/sdd_writer.md` (Phase 2) и для любого ИИ-писателя
> SDD внутри Orchestrator. Извлечена из ретроспективы первого SDD
> (`phase1-analyst-SDD.md`) и его аудита (`audit-phase1.md`, 2026-05-22).
>
> Назначение: закрыть систематический разрыв между писателем и аудитором.
> Писатель оптимизирует на coverage и narrative, аудитор — на depth и
> defect-search. Чтобы аудитор не находил одно и то же на каждом цикле,
> писатель должен ПРИНУДИТЕЛЬНО проходить чек-лист, который мимикрирует
> аудиторскую оптику.
>
> Документ в AI-to-AI стиле, английский ок (мы внутри prompts/).

---

## The nine failure modes (root causes observed)

1. **Pattern reuse without semantic translation.** Lifted v2 (Linux+tmux)
   pattern, swapped surface labels (`tmux`→`wt`), forgot the substrate
   (bash subshell `$(cat …)`, shell-escape rules, path-encoding casing,
   tmux send-keys vs wt argument parsing). Surface refactor ≠ port.

2. **Shallow dependency walk.** Said "inline base classes from
   `<prior-iteration>.v3.schemas`", stopped at first-level imports, didn't grep the
   next layer. Result: schemas.py:15 transitively pulls
   `<prior-iteration>.engine.planner._is_binary_criterion` — copy-as-is would
   ImportError.

3. **Happy-path bias.** Designed success flow (analyst writes → validate →
   done). Dropped v2's `signal-done` HTTP callback as "not needed" without
   designing a replacement for: hang, OOM, MCP timeout, partial write.

4. **Read-the-doc, not-the-code.** Schema constraints existed in BOTH the
   v3 prompt (description) and in v3 Pydantic validators (enforcement).
   Writer read the prompt. Auditor read the validators (the truth) and
   found the proposed validation was weaker (`keys ⊇ refs` instead of
   `2-4 distinct rounds + raw_result_ref exists on disk`).

5. **Empirical laziness.** Assumed path encoding `C--Users-…` without
   running `ls ~/.claude/projects/`. One command (1 sec) would have
   revealed `c--` lowercase variant + correct algorithm (`:` → `-`).
   Writer guessed where verification was free.

6. **Insufficient threat modeling.** Treated `--dangerously-skip-permissions`
   as UX-bypass (trust dialog), not as security boundary. Conflated with
   `--add-dir` (which extends, not restricts). Did not enumerate blast
   radius: "if this flag is on, what can the analyst do that violates the
   read-only contract?"

7. **Prompt-engineering as substitute for engineering.** Where reliability
   needed a forcing function, wrote "жирная инструкция в `prompts/…`" —
   admission of honor-system. Forcing functions are post-conditions
   validated by code, not promises in markdown.

8. **DoD without pre-conditions.** Structured DoD around deliverable
   stages, omitted "what inputs/decisions must exist before Stage 1".
   Resulted in OQ1-OQ4 being "questions" with no enforcement that they
   block work.

9. **Regex-vs-literal-block drift inside one SDD.** Writer emitted a
   `dod_post` / `verifications` grep regex AND a §5 literal example
   block the implementer is told to copy verbatim. The two diverged
   (e.g. regex `^\| ([0-9]|10)\|` vs §5 row `| 1 | ...` with a space
   before the second pipe). Implementer either fails its own dod_post
   or deviates from §5 to make the regex match — both defeat FF6's
   "no recreation from memory" invariant. Observed on
   `tasks/2026-05-22-example-erp-02` (Phase 3 e2e, 2026-05-22).

---

## The eight forcing functions (mandatory for the writer)

### FF1. Verification mandate on external claims

Every assertion about an external system (CLI flag behavior, file format,
network protocol, path encoding, shell quoting) must be tagged in the SDD:

- `[VERIFIED via <command>]` — when actually executed and observed
- `[VERIFIED via <doc>:<section>]` — when cross-checked against authoritative docs
- `[ASSUMED]` — when the writer is guessing

`[ASSUMED]` tags are red flags for the auditor. SDD must minimize them.
Before sign-off, every `[ASSUMED]` must either become `[VERIFIED]` or
move to a documented Open Question.

**Trigger:** any sentence containing a flag name, CLI command, encoded
path, environment variable, or external file format.

### FF2. Recursive dependency walk

When the SDD says "copy/inline/extract X from Y", the writer must:

1. Run `grep -rE "^(from|import) " <Y>` for ALL files transitively
   referenced (depth ≥2).
2. Enumerate every external symbol Y depends on.
3. Decide explicitly per symbol: inline, replace, drop.
4. Verification step: `grep -E "^(from|import) <pkg>" <inlined>` must be
   empty.

Stopping at first-level imports is a defect.

### FF3. Failure-mode enumeration per stage

Each stage in the SDD must have a "what breaks" subsection enumerating:

- Hang / no progress
- Partial output (artefact half-written)
- External dependency unavailable (network, MCP, file system)
- Concurrent invocation (if applicable)
- User intervention mid-execution

If a stage has no failure modes worth listing, write "no failure modes
beyond Pydantic exit codes" explicitly — that statement is auditable.

### FF4. Code-over-doc rule

When a constraint exists in BOTH a prompt/spec AND in code (Pydantic
validators, regex, type signatures), the writer MUST:

1. Read both.
2. Quote both in the SDD section that depends on it.
3. If they differ — code wins, mark prompt as needing update.

Reading only the spec when the code is authoritative is a defect.

### FF5. Threat model per dangerous primitive

Every `--dangerous*` flag, `--skip-*` flag, permission override,
`sudo`-equivalent, or capability grant must have a "blast radius"
subsection:

- What can a misbehaving actor do under this flag?
- What's the worst-case (filesystem write to system files? credential
  exfiltration? lateral movement?)?
- What's the alternative without this flag, and why was it rejected?
- Is the risk accepted (with sign-off) or mitigated technically?

`--dangerously-skip-permissions` is not "disable annoying prompts"; it
is "disable all permission checks". Writer must articulate this in plain
language before deciding to use it.

### FF6. Honor-system marker

If reliability of a step depends on the executing agent's
self-discipline (e.g., "the analyst MUST write the file"), the SDD must
either:

(a) **Replace** with a forcing function: post-condition check by code,
exit code on absence, retry-flow on failure.

(b) **Explicitly tag** the step as `HONOR_SYSTEM: <risk> — mitigation in
Phase N` so the auditor sees the gap is acknowledged, not hidden.

Phrases like "жирная инструкция в промпте", "the prompt says clearly",
"the analyst should" are honor-system. Tag or replace.

### FF7. DoD = post + pre

The "Definition of Done" section must have two subsections:

- **Pre-conditions** — inputs, decisions, environment setup that must
  exist before the first stage. OQ resolutions live here. If any OQ is
  open at start of Stage 1, work stops.
- **Post-conditions** — deliverable verifications. Each must be a binary
  check (file exists / validator passes / test green).

A DoD without pre-conditions silently legitimizes starting work with
missing inputs.

### FF8. Self-grep dod_post regexes against §5 literal blocks

When a `dod_post` (or `stages[*].verifications`) entry contains a grep
expression (`grep`, `grep -c`, `grep -E`, `grep -F`, etc.) targeting an
operator-local deliverable that is ALSO rendered inside the SDD as a
literal example block (the "implementer copies §5 verbatim" pattern),
the writer MUST, before announcing `SDD READY`:

1. Extract every such regex from `dod_post` and `stages[*].verifications`.
2. Run each regex against the §5 literal block under this session
   (Bash `grep -cE`, Python `re`, or equivalent).
3. Confirm the observed match count agrees with whatever the dod_post
   line asserts (e.g. `=10`, `>=1`, `==0`).
4. If they disagree → revise either the regex or the §5 block until
   they agree. Do NOT submit while they drift.

N/A only if the SDD's dod_post / verifications contain no grep
expression, OR if no §5 literal example block exists (rare; usually a
sign the SDD is light on operator-checkable post-conditions).

`validate_sdd` does NOT enforce this — it schema-validates the
metadata but never reads file contents. FF8 is honor-system like FF6;
the cost of skipping is asymmetric (implementer either copies §5
verbatim and fails dod_post, or deviates from §5 and breaks FF6).

---

## How the auditor catches what the writer missed

The auditor and writer differ structurally:

| Dimension | Writer | Auditor |
|---|---|---|
| Optimization | Breadth (coverage of stages, OQs, risks) | Depth (stress-test each item) |
| Trust toward patterns | High ("v2 did this, port it") | Low ("v2 was Linux, this is Windows") |
| Reasoning direction | Forward (input → output) | Backward (what breaks → what's wrong upstream) |
| Context state | Dense, narrative-coherent | Cold, sees discontinuities |
| Incentive | Ship the document | Find defects |
| Time pressure | High (next stage waits) | Low (one job, well-bounded) |

Forcing functions FF1–FF8 attempt to inject auditor-mode discipline into
the writer's loop. They are not a substitute for the audit pass — the
auditor still runs — but they reduce the per-cycle audit-finding count
toward zero.

## Operational rule

Before any SDD is submitted for audit, the writer self-audits against
FF1–FF8 as a checklist. Each FF either passes (✅), is N/A (with
reason), or fails (writer fixes before submitting).

The audit pass thus becomes "second opinion", not "find what I missed".
