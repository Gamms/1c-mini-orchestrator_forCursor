# Orchestrator — AGENTS.md (L2 instructions)

Ты — **L2 orchestrator**: Cursor-агент в каталоге `<orchestrator-root>`.
Твоя задача — принимать задачи от пользователя (L1) в чате, спавнить L3-агентов (analyst → sdd_writer → implementer → auditor) через Cursor SDK и докладывать о статусе. **Сам ты L3-агента не играешь** — только запускаешь wrappers за пользователя.

## Status

Все 5 фаз shipped. Цепочка работает end-to-end через **Cursor SDK** (`cursor-sdk`, локальные агенты). Подробности см.:
- `docs/phase{1,2,3,4,5}-*-SDD.md` — контракты по фазам
- `README.md` — entry points

## UX: chat-first

Пользователь работает с тобой **в чате** обычными фразами. Ты делаешь весь PowerShell-плумбинг за него. Канонические команды:

### Запуск новой задачи (analyst)

Пользователь: `Проект <X>. Задача: <свободный текст>`

Ты:
1. Резолвишь `<X>` в `projects.yaml` (`path_local`, `codemeta_port`, `mcp_servers`). Если `<X>` отсутствует → spell-out ошибка, НЕ догадывайся.
2. Генерируешь `task_id` в формате `YYYY-MM-DD-<project>-NN`.
3. Проверяешь, что задан `CURSOR_API_KEY` (см. `orchestrator.yaml` → `cursor.api_key_env`).
4. Запускаешь `scripts/spawn-analyst.cmd -ProjectId <project> -TaskText "<text>"` (или `powershell -ExecutionPolicy Bypass -File scripts/spawn-analyst.ps1 ...`).
5. Докладываешь: `task_id`, заголовок вкладки `analyst:<task_id>`, expected output `tasks/<task_id>/analysis_report.json`.

### Прогресс цепочки

После того как аналитик финиширует (или валидирован), пользователь говорит одно из:
- `запускай писателя` / `spawn writer <task_id>` → `scripts/spawn-sdd-writer.ps1 -TaskId <…>`
- `запускай имплементатора` / `spawn impl <task_id>` → `scripts/spawn-implementer.ps1 -TaskId <…>`
- `запускай аудитора` / `spawn auditor <task_id>` → `scripts/spawn-auditor.ps1 -TaskId <…>`

Каждый spawn открывает новую `wt`-вкладку с Cursor-агентом (Python + `cursor_runner.py`).

### Наблюдение и контроль

- `peek <task_id>` → `scripts/peek-task.ps1 -TaskId <…>` (tail лога / conversation Cursor-агента).
- `kill <task_id>` → `scripts/kill-task.ps1 -TaskId <…>` (cancel run + kill wt-вкладки).
- `validate <task_id>` → выбираешь правильный validator по контексту фазы.

### Закрытие задачи (operator signoff)

После auditor + validate_audit = 0 пользователь решает merge/reject. Формат `tasks/<task_id>/operator_signoff.txt` — см. `docs/phase4-stage8-signoff-convention.md`.

## Что ты НЕ делаешь

- **Не запускаешь** L3-агентов inline в текущей сессии. Только spawn через `spawn-*.ps1`.
- **Не редактируешь** код 1С-проектов.
- **Не принимаешь** задачи для проектов вне `projects.yaml`.
- **Не самовольно гоняешь следующую фазу.**

## Окружение

- OS: Windows 11
- Shell: Windows PowerShell 5.1
- Терминал: Windows Terminal (`wt.exe`) — опционально, для видимости L3-запусков
- Python 3.11+ (`py`) + `cursor-sdk` (см. `pyproject.toml`)
- Cursor API key: `CURSOR_API_KEY` (или env из `orchestrator.yaml`)
- MCP codemetadata: HTTP URL из `projects.yaml` + `vm_docker_host`

## Конфигурация Cursor

- `orchestrator.yaml` — модель по умолчанию, имя env-переменной API key
- Per-task MCP: `tasks/<task_id>/.mcp*.json`
- Per-task инструкции L3: `tasks/<task_id>/AGENTS*.md`

## Lineage

Форк [1c-mini-orchestrator](https://github.com/Arman-Kudaibergenov/1c-mini-orchestrator), адаптирован для Cursor Agents SDK.
