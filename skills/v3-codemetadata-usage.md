---
name: v3-codemetadata-usage
description: When-and-how to query 1c-codemetadata; entry points, drill patterns, and the rule "verify tool names via tools/list at runtime".
---

Applies when `1c-codemetadata` is in `manifest.mcp.server_refs`.

## Entry points

**Tool surface evolves — verify each name via the server's `tools/list` at runtime before relying on it.** Names below match `1c-cloud-mcp v3.1.1` (Stage 6 e2e probe 2026-05-22).

Structural (SQLite-backed, instant):
- `metadatasearch` — FTS5 search over 1С metadata XML. First call to find candidate objects. **Gotcha**: silently drops short Cyrillic tokens (e.g. `ИНН`) and most pure-English queries; use longer Cyrillic forms or English-via-synonym. *Verify via `tools/list` at runtime.*
- `get_object_details` — full structure (attributes with types, tabular parts, register movements) of a known object. **Arg is `full_name`** (e.g. `Справочник.Контрагенты`), NOT `object_name`. *Verify via `tools/list` at runtime.*
- `search_function` — find BSL procedures / functions by name across all modules. *Verify via `tools/list` at runtime.*
- `get_module_functions` — list functions in a specific module file. *Verify via `tools/list` at runtime.*
- `get_function_context` — call graph for a function (calls + called by). *Verify via `tools/list` at runtime.*

Semantic (ChromaDB vector search):
- `codesearch` — hybrid search in BSL modules; pair with `get_object_details` to bridge metadata→code. *Verify via `tools/list` at runtime.*
- `search_code_filtered` — semantic code search with structural filters. *Verify via `tools/list` at runtime.*
- `helpsearch` — search 1C documentation. *Verify via `tools/list` at runtime.*

Utility:
- `stats` — indexer statistics. *Verify via `tools/list` at runtime.*
- `reindex` — rebuild indexes (do not call from analyst; mutates server state). *Verify via `tools/list` at runtime.*

Form-inspection tools (`search_forms`, `inspect_form_layout`) and `get_metadata_details` from older comol AGENTS.md are NOT present in 1c-cloud-mcp v3.1.1 — do not call them.

## Drill pattern (Round 1 → Round 2)

1. Round 1: broad metadata query with the server's primary metadata
   search entry, against the operator's goal.
2. Round 2: pick the top 2-3 hits, get full structure per object;
   cross-reference with the BSL code-search entry for modules that touch them.
3. If impact analysis matters (e.g. "what breaks if we change X"), pair
   with `1c-graph-metadata` (see `v3-1c-mcp-tools-guide` for that server's
   entry points; verify each name via `tools/list` at runtime).

## Fall back to grep ONLY when both metadata servers are tried

`1c-codemetadata` + `1c-graph-metadata` are the truth. Repo-side grep
misses generated files, XML manifest details, and call-graph context.
Only resort to `Grep` after both metadata servers were queried and
neither surfaced the answer.

## Citation shape

Cite each call as `Citation(source="mcp", ref="1c-codemetadata/round<N>/q<i>")`
and additionally write the raw response to
`analysis_raw/1c-codemetadata/r<N>-q<i>-<sha12>.json`. Both refs end up
in `RelevantFile.citations` / `Finding.citations` where applicable.

Sources:
- https://github.com/comol/ai_rules_1c/blob/main/AGENTS.md
- https://github.com/comol/ai_rules_1c/blob/main/content/rules/tooling-playbooks.md
- https://github.com/comol/ai_rules_1c/blob/main/content/rules/anti-patterns.md
- https://www.anthropic.com/engineering/code-execution-with-mcp
