---
name: v3-naparnik-usage
description: 1c-naparnik is the 1С ITS docs MCP wrapper; tool names are unstable, source comes from `naparnik_tools.json` at runtime — NEVER hardcode tool names here.
---

`1c-naparnik` wraps 1С ITS docs queries. **Tool names evolve
independently of this skill.** The only legitimate source is
`naparnik_tools.json` written under the task root by the manifest-build
step (`<prior-iteration>/v3/analyst_manifest.py:build_analyst_server_refs`).

## Discovery, not memory

Before invoking any naparnik tool:

1. Read `naparnik_tools.json` from the task root.
2. If the file is missing or `tools: []` — naparnik is unavailable for
   this run. Skip it. Declare `tool_evidence["1c-naparnik"]` ONLY if
   `manifest.mcp.server_refs` includes `"1c-naparnik"`.
3. If the file lists tools — invoke them. The names in that file are
   the ground truth.

## Anti-pattern

Naming a naparnik tool from memory — even one that worked last week —
is forbidden. The build that this analyst run targets may have a
different tool surface. The rule applies to every authored artefact
(`analysis_report.json`, `templates/v3/analyst.j2`, this skill, any
project skill). The skill body deliberately contains no tool names.

## Citations

Each naparnik call → `Citation(source="mcp", ref="1c-naparnik/round<N>/q<i>")`
plus a raw-artefact citation pointing at
`analysis_raw/1c-naparnik/r<N>-q<i>-<sha12>.json`. Dump every response
verbatim. Naparnik is read-only by nature; the raw record is the
canonical evidence.

## When naparnik is NOT in `server_refs`

Item 4d gates the 1С MCP block on `project.type == "1c"`. For non-1c
projects (e.g. <prior-iteration> itself, `type="tool"`) naparnik is excluded
entirely. The analyst still works — `rlm-toolkit` and the L3 terminal's
local Read/Glob/Grep cover the gap.

Sources:
- https://github.com/comol/ai_rules_1c/blob/main/AGENTS.md (naparnik wrapper context — tool surface itself is runtime-discovered)
- https://github.com/comol/ai_rules_1c/blob/main/content/rules/tooling-playbooks.md
- https://github.com/comol/ai_rules_1c/blob/main/content/rules/anti-patterns.md
- https://www.anthropic.com/engineering/code-execution-with-mcp
- <prior-iteration>/v3/analyst_manifest.py (probe + on-disk write of `naparnik_tools.json`)
