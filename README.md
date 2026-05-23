# 1c-mini-orchestrator (Cursor edition)

Локальный оркестратор для запуска цепочки **аналитик → SDD-писатель → имплементатор → аудитор** над проектами 1С через **Cursor Agents SDK**. Аналитик, писатель, имплементатор и аудитор — локальные Cursor-агенты; MCP `codemetadata` подключается inline из task-пакета.

Форк [Arman-Kudaibergenov/1c-mini-orchestrator](https://github.com/Arman-Kudaibergenov/1c-mini-orchestrator), адаптированный под Cursor вместо Claude Code CLI + Codex CLI.

- **L1** = пользователь (открывает терминалы, пишет в чат L2 в Cursor)
- **L2** = Cursor-агент в корне репо (`AGENTS.md` — роутер, генератор task-пакетов)
- **L3** = analyst / sdd_writer / implementer / auditor через `cursor-sdk` (опционально во вкладке `wt`)

## Быстрый старт

```powershell
# 1. Python 3.11+ и зависимости
py -m pip install -e .

# 2. API key Cursor (Dashboard → Integrations)
$env:CURSOR_API_KEY = "cursor_..."

# 3. Настроить projects.yaml (path_local, codemeta_port, vm_docker_host)

# 4. Новая задача
.\scripts\spawn-analyst.ps1 -ProjectId example-mfg -TaskText "Добавить реквизит ИНН в справочник Контрагенты"

# 5. Цепочка (после validate каждой фазы)
.\scripts\spawn-sdd-writer.ps1 -TaskId 2026-05-23-example-mfg-01
.\scripts\spawn-implementer.ps1 -TaskId 2026-05-23-example-mfg-01
.\scripts\spawn-auditor.ps1 -TaskId 2026-05-23-example-mfg-01
```

Откройте этот репозиторий в Cursor и работайте с L2-оркестратором по инструкциям в [`AGENTS.md`](AGENTS.md).

## Status

| # | Фаза | Артефакт | Runtime |
|---|---|---|---|
| 1 | Аналитик | `analysis_report.json` | Cursor SDK |
| 2 | SDD-писатель | `sdd.md` + `sdd_metadata.json` | Cursor SDK |
| 3 | Имплементатор | ветка `orchestrator/<task_id>` + `impl_metadata.json` | Cursor SDK |
| 4 | Аудитор | `audit_report.json` + operator_signoff | Cursor SDK |
| 5 | Hardening | phase-agnostic peek/kill | Cursor SDK |

## Entry points

- `scripts/peek-task.ps1 -TaskId X [-Tail N]` — tail Cursor run (log + conversation)
- `scripts/kill-task.ps1 -TaskId X` — cancel Cursor run + kill wt-вкладки
- `scripts/spawn-{analyst,sdd-writer,implementer,auditor}.ps1` — подготовка task-пакета + spawn L3
- `scripts/validate-{analysis,sdd,impl,audit}.ps1 -TaskId X` — Pydantic-валидация

Ядро Cursor runtime:

- `scripts/_python/cursor_runner.py` — запуск L3 через `cursor-sdk`
- `scripts/_python/peek_cursor_run.py` — мониторинг
- `scripts/_python/cancel_cursor_run.py` — отмена

## Конфигурация

| Файл | Назначение |
|---|---|
| `orchestrator.yaml` | модель Cursor, env для API key |
| `projects.yaml` | реестр 1С-проектов и MCP-портов |
| `docs/projects-pfs.md` | настройка проекта **PFS** (`C:\Tools\DevsProject\ai\PFS`) |
| `tasks/<id>/AGENTS*.md` | контракт L3-агента |
| `tasks/<id>/.mcp*.json` | MCP для фазы |

## Docs

- `docs/phase{1,2,3,4,5}-*-SDD.md` — контракты по фазам
- `docs/writer-forcing-functions.md` — FF1-FF8
- `AGENTS.md` — инструкции L2 orchestrator для Cursor

## Отличия от upstream

| Upstream | Cursor edition |
|---|---|
| Claude Code CLI (`claude.cmd`) | `cursor-sdk` local agents |
| Codex CLI (auditor) | Cursor SDK (auditor) |
| `CLAUDE.md` per task | `AGENTS*.md` per task |
| `~/.claude/projects` session peek | `cursor_agent_id` / `cursor_run_id` в packet + log |
| Claude Code hooks | Cursor hooks (`.cursor/hooks.json`, opt-in) |

## Lineage & credits

См. [CREDITS.md](CREDITS.md) и [NOTICE](NOTICE). Лицензия — Apache License 2.0.
