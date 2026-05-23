---
name: v3-1c-mcp-tools-guide
description: Overview of the 1C MCP stack (router, code-metadata, graph-metadata, ssl, templates, naparnik) with one-line purpose per server and the runtime-discovery disclaimer.
---

**The 1C MCP tool surface evolves — verify every tool name via the server's `tools/list` at runtime before invocation. Names below were captured at SDD authoring.**

## Servers

- **`1c-mcp-router`** — the canonical routing entry — most 1C tools live behind this. Request routing in front of the stack; the analyst's `server_refs` lists it as a direct ref, and 3 of the 4 not-directly-exposed 1C servers (`1c-ssl`, `1c-templates`, `1c-docs`) are reached only through this router. See §"Routing pattern through `1c-mcp-router`" below for the invocation contract.

- **`1c-codemetadata`** — direct ref in `server_refs` (unchanged behaviour). Primary metadata + BSL code search. Tools (verify via `tools/list` at runtime): `metadatasearch`, `get_metadata_details`, `codesearch`, `search_function`, `get_module_structure`, `search_forms`, `inspect_form_layout`. See `v3-codemetadata-usage` for drill patterns.

- **`1c-graph-metadata`** — **NOT DEPLOYED as of 2026-05-15**; tools below are aspirational. Honest degraded path: full caller / impact analysis is unsupported until the container deploys; analyst MUST declare partial answers in `analysis_report.json` with explicit acknowledgement that graph-based traversal was unavailable. Codemetadata's `search_function` + `get_module_structure` (verify via `tools/list` at runtime) are NOT a substitute (per `config/skills/v3-codemetadata-usage.md:12-18, 26-35`: impact-analysis pairs with graph-metadata; codemetadata only provides structural primitives, not call-chain traversal). Neo4j-backed dependency / impact analysis. Tools (verify via `tools/list` at runtime when deployed): `get_object_dossier`, `trace_impact`, `trace_call_chain`, `find_objects_using_object`, `compare_base_and_extension`, `search_code`.

- **`1c-ssl`** — reached via `1c-mcp-router`'s `route` tool (see §"Routing pattern through `1c-mcp-router`" below); not a separate MCP namespace. Standard Subsystems Library search. Tool (verify via `tools/list` at runtime): `ssl_search`. Use before reinventing a helper that БСП already provides.

- **`1c-templates`** — reached via `1c-mcp-router`'s `route` tool (see §"Routing pattern through `1c-mcp-router`" below); not a separate MCP namespace. Project code-template library + project memory. Tools (verify via `tools/list` at runtime): `templatesearch`, `remember`, `recall`. Pre-coding: search templates for similar past implementations.

- **`1c-docs`** — reached via `1c-mcp-router`'s `route` tool (see §"Routing pattern through `1c-mcp-router`" below); not a separate MCP namespace. Platform documentation. Tools (verify via `tools/list` at runtime): `docsearch`, `docinfo`. Use to confirm an API name actually exists on the live platform version.

- **`1c-naparnik`** — see `v3-naparnik-usage`. Tool surface is dynamic;
  source comes from `naparnik_tools.json`, not from this skill.

- **`1c-code-check`** — write-side validators. Out of scope for analyst (read-only role).

- **`rlm-toolkit`** — project memory + institutional context. Always
  in `server_refs`. (Non-comol; tool surface stable, no runtime-discovery
  caveat needed.)

## Routing pattern through `1c-mcp-router`

For servers labelled "reached via `1c-mcp-router`" above (`1c-ssl`, `1c-templates`, `1c-docs`), the analyst invokes `mcp__1c-mcp-router__route` (verify exact tool name via `tools/list`) with arguments `{server: "<upstream-name>", tool: "<tool-name>", arguments: {...}}`. The router proxies to the upstream and returns the result verbatim.

The upstream-name DOES NOT always match the skill row label. Use this mapping (verified 2026-05-15 against `config/<prior-iteration>.yaml` + `config/v3-mcp-profiles.yaml`); tool names below MUST also be verified via `tools/list` at runtime before invocation (per the line-6 disclaimer):

| Skill row label | Router upstream `server=` value | Tools (verify via `tools/list`)        |
|-----------------|---------------------------------|----------------------------------------|
| `1c-ssl`        | `"1c-ssl"`                      | `ssl_search`                           |
| `1c-templates`  | `"1c-templates"`                | `templatesearch`, `remember`, `recall` |
| `1c-docs`       | `"1c-help"`                     | `docsearch`, `docinfo`                 |

Example (verify via `tools/list` at runtime before invoking):

```
mcp__1c-mcp-router__route(
  server="1c-help",
  tool="docsearch",
  arguments={"query": "СформироватьПечатнуюФорму"}
)
```

The arg shape is `server=..., tool=..., arguments=...` — NOT `upstream=..., args=...`. The router exposes `route` as the canonical proxy entry; per-upstream namespaces (e.g. `mcp__1c-ssl__*`) are NOT present in the analyst's dispatched workspace `.mcp.json`.

## When to invoke which server

| Analyst question | Server to hit first |
|---|---|
| "What does object X look like?" | 1c-codemetadata |
| "Who calls method Y?" | 1c-graph-metadata (graph-metadata unavailable — degraded path: declare partial answer in `analysis_report.json`) |
| "What breaks if we change Z?" | 1c-graph-metadata (graph-metadata unavailable — degraded path: declare partial answer in `analysis_report.json`) |
| "Is there a БСП helper for W?" | 1c-ssl (via 1c-mcp-router: `server="1c-ssl"`) |
| "Past project memory on this topic?" | rlm-toolkit |
| "1С ITS docs cover this?" | 1c-naparnik (consult `naparnik_tools.json` for the live tool name) |

Tool names per server are listed above with the runtime-discovery
disclaimer. **Never invoke a tool by name without first checking the
server's live `tools/list`.**

## Cross-links

- `v3-codemetadata-usage` — drill patterns for 1c-codemetadata.
- `v3-naparnik-usage` — 1c-naparnik runtime-discovery rule.
- `v3-1c-anti-patterns` — what NOT to do across the stack.

Sources:
- https://github.com/comol/ai_rules_1c/blob/main/AGENTS.md
- https://github.com/comol/ai_rules_1c/blob/main/content/rules/tooling-playbooks.md
- https://github.com/comol/ai_rules_1c/blob/main/content/rules/anti-patterns.md
- https://www.anthropic.com/engineering/code-execution-with-mcp
- `docs/next-session-prompts/comol-mcp-v2-analyst-manifest-extension.md` (LAN-probe retrospective 2026-05-15)
- RLM fact `07b1a0d2` (LAN-probe retrospective) — `mcp__rlm-toolkit__rlm_search_facts query="comol-mcp router proxy graph-metadata"`
