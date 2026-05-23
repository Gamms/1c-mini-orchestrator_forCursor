# Credits & Attribution

## Author

This project is developed by **Arman Kudaibergenov** ([@Arman-Kudaibergenov](https://github.com/Arman-Kudaibergenov)).

GitHub: https://github.com/Arman-Kudaibergenov/1c-mini-orchestrator

## Related public projects (same author)

- **rlm-workflow** (Apache-2.0) — https://github.com/Arman-Kudaibergenov/rlm-workflow
  Claude Code workflow on top of RLM-Toolkit (memory across sessions, pre-compact hooks).
- **bsl-atlas** — https://github.com/Arman-Kudaibergenov/bsl-atlas
  Companion tooling for 1C BSL navigation.

## Optional integrations

The orchestrator can plug into the following external MCP servers. None of
them is vendored or required at runtime; the chain works without any of
them, you just lose the corresponding capability.

### codemetadata (1C XML-dump indexer)

The analyst / writer / implementer phases call a `codemetadata` MCP server
to read the project's 1C metadata (catalogs, documents, registers, code).
Set the host + per-project port in `projects.yaml`; the URL is assembled
as `http://<vm_docker_host>:<codemeta_port>/mcp`.

This repo does NOT ship the codemetadata server itself.

### RLM-Toolkit (institutional memory)

Optional MCP server used as the long-term memory of phase closures.

- Author: **Dmitry Labintcev** ([@DmitrL-dev](https://github.com/DmitrL-dev))
- Original project: https://github.com/DmitrL-dev/AISecurity/tree/main/rlm-toolkit
- PyPI: `pip install rlm-toolkit`
- License: Apache-2.0

The orchestrator calls the standard RLM MCP tools
(`rlm_add_hierarchical_fact`, `rlm_route_context`, etc.) over HTTP. There is
no RLM source code in this repository.

### Articles by the RLM-Toolkit author (Habr / Хабр)

| Article | URL |
|---------|-----|
| Полное руководство по обработке 10M+ токенов | https://habr.com/ru/articles/986280/ |
| Почему ваш LLM-агент забывает цель | https://habr.com/ru/articles/986836/ |
| RLM-Toolkit v1.2.1: Теоретические основы и оригинальные разработки | https://habr.com/ru/articles/986702/ |
| RLM-Toolkit: Полная замена LangChain? FAQ часть 2 | https://habr.com/ru/articles/987250/ |

### Codex CLI (auditor runtime)

Phase 4 auditor runs on top of OpenAI's `codex` CLI. The orchestrator
spawns `codex exec` in a separate `wt`-tab with a per-task `CODEX_HOME`
overlay; no Codex source is vendored.

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE) for the
full terms and the attribution requirements.
