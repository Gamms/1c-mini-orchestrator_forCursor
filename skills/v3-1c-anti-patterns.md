---
name: v3-1c-anti-patterns
description: Explicit FORBIDDEN analyst moves — assumption without lookup, summarising instead of dumping, naming tools without runtime verification, sub-2-rounds laziness.
---

The analyst is read-only. Every claim must trace back to a logged MCP /
code / RLM lookup. The rules below codify what NOT to do.

## Forbidden phrases (no citation = no claim)

- "I already know <prior-iteration> uses X for this."
- "It's obvious that Y."
- "naparnik probably has a tool for Z."
- "Round 1 is enough — I've seen this pattern before."

Each requires a `Citation` against a current MCP / code / RLM lookup OR
must be omitted. Pydantic's `min_length=1` on `Finding.citations` /
`RelevantFile.citations` enforces this at the schema layer; this skill
captures the *spirit* the validator only approximates.

## Cycle-discipline anti-patterns

- "Round 1 is enough" → no, **≥2 distinct rounds per server**.
- "I'll keep going past Round 4 to be thorough" → no, **≤4 rounds**.
  Past Round 4, raise an `OpenQuestion` instead.
- "I summarised the MCP response, no need to dump the raw JSON" → no,
  every response → `analysis_raw/<server>/r<round>-q<idx>-<sha12>.json`,
  verbatim.
- "I'll skip 1c-naparnik, the other servers cover it" → no, **every**
  server in `manifest.mcp.server_refs` must appear in `tool_evidence`
  keys (orchestrator's `v3.analysis.tool_exhaustion` validator rejects
  the artefact otherwise).

## 1C-specific anti-patterns (read-only)

These are adapted from comol's anti-patterns guide. Translated into
analyst-side rules:

- **Assuming a query result has columns X, Y, Z** without checking
  `Выполнить().Колонки` — verify the structure via `1c-codemetadata` or
  `get_object_dossier` (*verify via the server's `tools/list` at runtime*).
- **"There's surely a БСП helper for this"** — run `ssl_search` (*verify
  via the server's `tools/list` at runtime*) before claiming a helper
  exists.
- **"This loop is O(N²)"** as a finding without tracing the actual
  iteration. Cite the file:line range AND the metadata that backs the
  performance claim.
- **Citing project-wide rules** ("this codebase forbids …") without
  reading the project's local dev-standards file. Quote the rule's
  source.
- **"It looks like a write op"** — analyst is read-only. If the operator's
  goal implies writes, raise an `OpenQuestion` with `severity="decision"`
  rather than producing a write recommendation.

## Tool-name discipline

- **Naparnik tool names**: source ONLY from `naparnik_tools.json` at
  runtime. Never from memory or this skill.
- **Comol tool names** (codemetadata, graph-metadata, ssl, templates,
  docs): may be named in this skill set WITH the runtime-discovery
  disclaimer, but never relied on as canonical. Re-verify before each
  invocation.

Sources:
- https://github.com/comol/ai_rules_1c/blob/main/content/rules/anti-patterns.md
- https://github.com/comol/ai_rules_1c/blob/main/AGENTS.md
- https://github.com/comol/ai_rules_1c/blob/main/content/rules/tooling-playbooks.md
- https://www.anthropic.com/engineering/code-execution-with-mcp
