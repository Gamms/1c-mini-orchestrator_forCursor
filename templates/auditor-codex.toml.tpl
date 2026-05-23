# Per-task codex config for the L3 auditor.
#
# spawn-auditor.ps1 renders this template into
#   {TASK_ROOT_ABS}/.codex_home/config.toml
# and starts codex with
#   $env:CODEX_HOME = "{TASK_ROOT_ABS}\.codex_home"
# before invoking `codex exec ...`. Stage 0 verification (docs/phase4-
# auditor-SDD.md §5 Stage 0) confirmed codex 0.130.0 has no
# `--config <path>` flag, so the per-task config is delivered via
# CODEX_HOME redirect rather than a CLI flag.
#
# Per-task isolation matters for the same reason it did in Phases 1-3:
# multiple auditor tabs may run concurrently, each pinned to a different
# project's codemetadata URL. A global ~/.codex/config.toml could not
# disambiguate.
#
# The exact MCP TOML key surface for codex 0.130.0 is locked at Stage 6
# e2e (Phase 4 SDD §5 Stage 6). If codex renames the section, the fix
# is one line here -- no spawn-auditor.ps1 change required.

[mcp_servers.codemetadata]
url = "{CODEMETADATA_URL}"
