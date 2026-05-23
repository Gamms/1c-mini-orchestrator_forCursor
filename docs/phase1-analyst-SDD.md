# SDD — Orchestrator, Phase 1: цепочка аналитика

**task_id:** `orch-phase1-analyst`
**task_size:** M
**автор:** Claude (L2 в текущей сессии Orchestrator)
**дата:** 2026-05-22
**статус:** черновик на согласование

---

## 1. Контекст и цель

Строим консолидацию <prior-iteration-v2> + v3 в виде лёгкого локального оркестратора, который запускается на ноутбуке (Windows 11) в обычном Claude Code. Пользователь сам играет роль L1 (открывает терминалы под задачи). L2 — это Claude в каталоге `Orchestrator/`. L3 — отдельные процессы `claude` в новых вкладках Windows Terminal под конкретные фазы.

**Цель Phase 1:** только аналитик. После согласования — берёмся за SDD-писателя (Phase 2).

**Что НЕ делаем в Phase 1:**
- SDD-писателя, аудиторов, имплементацию (Phase 2-4)
- Ротацию и Remote-toggle (Phase 5)
- L1-оркестратор (никогда — это пользователь)
- DB, локи, dispatch-state-machine (из v2 — выкинуто, не нужно для локального)
- HTTP-сервер с signal-done URL (из v2 — не нужно: ждём файла `analysis_report.json`, а не HTTP callback)
- Capabilities / preflight / rails (из v2/v3 — не нужно для read-only аналитика)

---

## 2. Ограничения и решения

| Ограничение | Решение |
|---|---|
| Windows 11, нет tmux | Windows Terminal (`wt.exe`) — нативные вкладки |
| Скорость доступа к 1С-исходникам | Локальные копии через Syncthing (уже работает) |
| Claude Code читает `CLAUDE.md` + `.mcp.json` из CWD | CWD аналитика = `tasks/<task_id>/`, CLAUDE.md и .mcp.json генерим туда |
| Аналитику нужен доступ к 1С-проекту вне CWD | Флаг `claude --add-dir <project_path>` |
| Trust-prompt при первом запуске | Pre-deploy `~/.claude/projects/<encoded>/settings.json {"trusted":true}`. **Кодировка пути [VERIFIED via `ls ~/.claude/projects/`]:** `path.replace(":","-").replace("\\","-").replace("/","-").TrimStart("-")`. Регистр диска нестабилен (`C--` и `c--` оба встречаются) — pre-trust пишем оба варианта. |
| Shell-escape промпта в `powershell -Command` | Промпт `$(cat …)` — это **bash**, в powershell не работает. Решение: spawn через `wt -w 0 nt --title <…> powershell.exe -NoExit -ExecutionPolicy Bypass -File scripts/_run-analyst.ps1 -TaskRoot <…> -ProjectPath <…>`. Wrapper читает `Get-Content prompt.md -Raw` и вызывает `& claude … -- $prompt`. Никаких `"$(…)"` в командной строке wt. |
| PowerShell edition | **Windows PowerShell 5.1** (`powershell.exe`) — гарантированно есть на любой Win10/11. `pwsh` (PowerShell 7) на ноутбуке НЕ установлен (verified Stage 0 smoke 2026-05-22). Ограничения 5.1: нет `&&`/`||`, нет `?:`/`??`/`?.`. Default file-encoding = UTF-16 LE с BOM — поэтому при `Out-File`/`Set-Content` всегда передавать `-Encoding utf8`. Чтение чужих UTF-8 файлов — `Get-Content -Raw -Encoding UTF8`. Native exe-вызовы: следить за quoting; для аргументов с `-`/`@`/спец-символами при необходимости использовать `--%` stop-parsing token. |
| `wt.exe` использует `;` как разделитель команд | Используем `-File` (без `-Command`), это полностью убирает проблему. |
| Полный FS-доступ при `--dangerously-skip-permissions` | **РИСК ПРИНЯТ для Phase 1.** `--add-dir` только расширяет, не ограничивает. Аналитик технически может писать куда угодно. Митигация только инструкцией в `prompts/analyst.md` («read-only»). Stage 6 sanity-check: после прогона аналитика — `git status` в воркспейсе показывает изменения только в `Orchestrator/tasks/<id>/`. Альтернатива (Phase 3+): `--permission-mode acceptEdits --allowedTools "Read,Glob,Grep,Write,Bash(git status,git diff,git log:*)"`. |
| MCP в `.mcp.json` (CWD) требует interactive trust при первом запуске | **Не полагаемся на CWD-autoload.** Передаём явно: `--mcp-config tasks/<id>/.mcp.json --strict-mcp-config` [VERIFIED via `claude --help`]. `--strict-mcp-config` запрещает любые другие источники MCP — глобальные rlm/linear не утекут к аналитику. |
| Аналитик не выдумывает факты | Жёсткое чтение `prompts/analyst.md` + 5 скиллов; tool-exhaustion на выходе + `os.path.exists(raw_result_ref)` для каждого ToolQuery в `validate.py`. |
| Аналитик может забыть `Write` финального отчёта | `prompts/analyst.md` требует пост-Write `Read` + объявление `REPORT READY` в чат. Валидатор имеет exit-code 4 «no file» с явной диагностикой. Retry-flow описан в Stage 6. |
| Зависший / упёртый аналитик | `scripts/peek-analyst.ps1` показывает «secs since last event» (mtime последнего jsonl-события). `scripts/kill-analyst.ps1 -TaskId X` находит вкладку по `--title` и шлёт `Stop-Process` на дочерний `claude.exe`. |
| L2 (я в этой сессии) хочет видеть, что делает аналитик | Stage 7: discovery через `Get-ChildItem $HOME/.claude/projects/ -Filter "*Orchestrator*tasks*<task_id_substr>*"`, не построение пути руками. |

---

## 3. Структура каталога после Phase 1

```
Orchestrator/
├── CLAUDE.md                          # инструкции мне (L2): как принимать "Проект X. Задача: Y"
├── README.md                          # для будущего меня и пользователя
├── projects.yaml                      # реестр: example-erp, example-trade, example-mfg (+ заглушки на расширение)
├── .gitignore                         # tasks/, *.pyc, __pycache__, .venv
├── pyproject.toml                     # минимальный, только для pydantic + pyyaml
├── docs/
│   ├── phase1-analyst-SDD.md          # этот документ
│   └── audit-phase1.md                # отчёт независимого аудитора (приложу после)
├── prompts/
│   └── analyst.md                     # фаза-промпт (адаптация v3/claude/phases/analyst.md)
├── skills/                            # копии 5 файлов из v3/config/skills
│   ├── v3-analysis-protocol.md
│   ├── v3-1c-anti-patterns.md
│   ├── v3-codemetadata-usage.md
│   ├── v3-naparnik-usage.md
│   └── v3-1c-mcp-tools-guide.md
├── schemas/
│   ├── __init__.py
│   └── analysis_v2.py                 # standalone Pydantic (inline базовые классы из v3)
├── templates/
│   ├── analyst-CLAUDE.md.tpl          # шаблон task-CLAUDE.md с плейсхолдерами
│   └── analyst-mcp.json.tpl           # шаблон .mcp.json
├── scripts/
│   ├── spawn-analyst.ps1              # главный entry-point: создаёт task_root + открывает wt
│   ├── validate-analysis.ps1          # PowerShell-обёртка вокруг python-валидатора
│   ├── peek-analyst.ps1               # читает session.jsonl, summary последних действий
│   └── _python/
│       └── validate.py                # Pydantic-валидация + tool-exhaustion check
└── tasks/                             # gitignored, рабочие каталоги задач
    └── .gitkeep
```

**Объём:** ~10 файлов кода (5 PS + 1 PY + 2 шаблона + 1 yaml + 1 CLAUDE.md) + 5 скилов + 1 промпт + 1 схема. Не Python-пакет.

---

## 4. Поток задачи (end-to-end)

```
[Пользователь в этой сессии Orchestrator]
    ↓ "Проект example-erp. Задача: добавить реквизит ИНН в справочник Контрагенты"
[Claude = L2]
    1. Резолвлю "example-erp" в projects.yaml → path_local, mcp_servers
    2. Генерю task_id: 2026-05-22-example-erp-01
    3. Запускаю scripts/spawn-analyst.ps1 -ProjectId example-erp -TaskText "..."
        ├── создаёт tasks/<task_id>/
        ├── рендерит CLAUDE.md (шаблон + контекст проекта)
        ├── рендерит .mcp.json (выбранные MCP-серверы из projects.yaml)
        ├── пишет task_packet.json (вся метадата)
        ├── пишет prompt.md (первое сообщение для claude)
        ├── pre-trust task_root + project_path
        ├── открывает новую вкладку wt с claude --add-dir <project>
        └── возвращает task_id
[Аналитик в отдельной вкладке]
    - Читает CLAUDE.md (свою роль), task_packet.json (что делать), prompt.md
    - Многоэтапное обследование через MCP (codemetadata и др.)
    - Пишет analysis_raw/<server>/r<N>-q<i>-<sha12>.json под каждый MCP-вызов
    - Финальный артефакт: analysis_report.json
[Пользователь] "готов" или "глянь, что он там делает"
[Claude = L2]
    - "готов" → scripts/validate-analysis.ps1 -TaskId X
        ├── Pydantic-валидация analysis_report.json по схеме v2
        ├── Tool-exhaustion: tool_evidence.keys() ⊇ manifest.server_refs
        └── показывает summary + пасс/фейл
    - "глянь" → scripts/peek-analyst.ps1 -TaskId X
        └── tail последних tool-вызовов из ~/.claude/projects/.../<uuid>.jsonl
```

---

## 5. Стадии реализации

### Stage 0 — Smoke-проверка цепочки `wt → powershell.exe → claude` (ОБЯЗАТЕЛЬНО первым)

Без этого нельзя начинать Stage 1. Цель: убедиться, что spawning механизм физически работает на этой машине ДО того, как мы написали хоть строчку логики.

**Шаги:**
1. Создать `Orchestrator/scripts/_run-smoke.ps1` с содержимым (script пишет marker-файл `tasks/.smoke-marker.txt` для автоматической верификации):
   ```powershell
   param([string]$Note = "smoke")
   $ErrorActionPreference = "Continue"
   Write-Host "smoke from powershell: $Note"
   $ver = (& claude --version) | Out-String
   Write-Host $ver
   $markerDir = Join-Path $PSScriptRoot "..\tasks"
   if (-not (Test-Path $markerDir)) { New-Item -ItemType Directory -Path $markerDir -Force | Out-Null }
   $marker = Join-Path $markerDir ".smoke-marker.txt"
   $payload = "smoke OK | note=$Note | claude=$($ver.Trim()) | host=$env:COMPUTERNAME | ts=$(Get-Date -Format o)"
   $payload | Out-File -Encoding utf8 -FilePath $marker
   Write-Host "marker written: $marker"
   Write-Host "smoke done. Press Enter to close."
   $null = Read-Host
   ```
2. Удалить предыдущий marker (если есть) и запустить spawn из этой сессии:
   ```bash
   rm -f tasks/.smoke-marker.txt
   wt.exe -w 0 nt --title "smoke" powershell.exe -NoExit -ExecutionPolicy Bypass -File "<orchestrator-root>\scripts\_run-smoke.ps1" -Note "phase0"
   ```
3. **Verification (auto):**
   - Через ≤10 сек файл `tasks/.smoke-marker.txt` появился и содержит подстроку `smoke OK | note=phase0 | claude=<version>`
   - `tasks/.smoke-marker.txt` парсится: `claude=` поле — непустое; `ts=` — валидная ISO-8601
4. **Verification (visual, опц.):**
   - В новой вкладке Windows Terminal с заголовком `smoke` видны строки `smoke from powershell: phase0`, версия Claude Code, `marker written: ...`

Если шаг 3 упал — Phase 1 не имеет смысла начинать. Чиним spawn-цепочку (разрешение на запуск unsigned `.ps1` через `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, или `wt.exe` не в PATH, или PowerShell edition).

### Stage 1 — Скелет + projects.yaml + CLAUDE.md

**Создать:**
- `Orchestrator/CLAUDE.md` — инструкции мне как L2 (как парсить "Проект X. Задача: Y", куда смотреть, где скрипты, что Phase 1 = только аналитик)
- `Orchestrator/projects.yaml` — реестр с записями: `example-erp`, `example-trade`, `example-mfg` (минимум: id, name, path_local, mcp_servers)
- `Orchestrator/README.md` — короткий обзор: как запустить, что есть
- `Orchestrator/.gitignore` — `tasks/`, `*.pyc`, `__pycache__`, `.venv`, `.env*`
- `Orchestrator/pyproject.toml` — только `pydantic>=2`, `pyyaml`

**Verification:**
- `ls Orchestrator/` показывает все 5 файлов
- `python -c "import yaml; print(yaml.safe_load(open('projects.yaml')))"` парсит без ошибок и содержит 4 ключа проектов
- `Orchestrator/CLAUDE.md` содержит маркеры: "L2 orchestrator", "spawn-analyst", "Phase 1"

### Stage 2 — Скилы + промпт + Pydantic-схема

**Скопировать как есть:**
- `<prior-iteration-v3>/config/skills/v3-analysis-protocol.md` → `Orchestrator/skills/`
- `<prior-iteration-v3>/config/skills/v3-1c-anti-patterns.md` → `Orchestrator/skills/`
- `<prior-iteration-v3>/config/skills/v3-codemetadata-usage.md` → `Orchestrator/skills/`
- `<prior-iteration-v3>/config/skills/v3-naparnik-usage.md` → `Orchestrator/skills/`
- `<prior-iteration-v3>/config/skills/v3-1c-mcp-tools-guide.md` → `Orchestrator/skills/`

**Адаптировать:**
- `<prior-iteration-v3>/claude/phases/analyst.md` → `Orchestrator/prompts/analyst.md` — выкинуть L2-эскалацию, `manifest_resolver`, `PhaseResult`; оставить суть: read-only, схема v2 на выходе, citation-discipline, tool-exhaustion, anti-assumption.

**Переписать standalone (закрывает audit C4):**
- `Orchestrator/schemas/analysis_v2.py` — НЕ копировать `<prior-iteration>/v3/schemas.py` целиком: он строкой 15 делает `from <prior-iteration>.engine.planner import _is_binary_criterion` [VERIFIED grep], что притянет полпрограммы. Инлайним **только то, что реально нужно** для AnalysisReport:
  - `Citation`, `ToolQuery`, `ToolEvidence` (с ВСЕМИ `@model_validator` — 2-4 round'а, raw_result_ref префикс), `RelevantFile` (с path-валидатором), `Finding`, `OpenQuestion`, `AnalysisReport`
  - базовые: `ArtifactModel(BaseModel)` с `model_config = ConfigDict(extra="forbid")` (не `ignore` — ловим мусор), helper `_non_empty(value, field_name)`
  - **НЕ копируем:** `SDDArtifact`, `SDDStage`, `_is_binary_criterion`, `TaskPacket`, `ARTIFACT_MODELS` глобал, `AIProducedArtifact` базовый класс (схлопываем в `ArtifactModel`)
- Перед началом Stage 2 — `grep -rE "^from <prior-iteration>" <prior-iteration-v3>/<prior-iteration>/v3/schemas.py <prior-iteration-v3>/<prior-iteration>/v3/analysis_schemas.py` и каждый импорт явно заменён или удалён.

**Verification (закрывает audit C4, C5, M7):**
- `ls Orchestrator/skills/` — 5 файлов
- `grep -L "PhaseResult\|manifest_resolver\|L2 escalat" Orchestrator/prompts/analyst.md` — пусто
- `grep -E "^from <prior-iteration>|^import <prior-iteration>" Orchestrator/schemas/analysis_v2.py` — **пусто**
- `cd Orchestrator && python -c "from schemas.analysis_v2 import AnalysisReport; print(sorted(AnalysisReport.model_fields.keys()))"` — печатает 10 полей без ImportError
- Fixture-тест: `python scripts/_python/_test_schema.py` (создаётся в Stage 2) с тремя кейсами:
  - (a) валидный отчёт → OK
  - (b) `extra_field: "garbage"` → `ValidationError` (потому что `extra="forbid"`)
  - (c) `ToolEvidence` с 1 round → `ValidationError` («must span 2-4 distinct rounds»)
  - (d) `RelevantFile.path = "/absolute/path"` → `ValidationError`

### Stage 3 — Шаблоны per-task CLAUDE.md и .mcp.json

**Создать:**
- `templates/analyst-CLAUDE.md.tpl` — короткий стартовый промпт для аналитика. Содержит плейсхолдеры: `{PROJECT_ID}`, `{PROJECT_PATH}`, `{TASK_ID}`, `{TASK_TEXT}`, `{ORCHESTRATOR_ROOT}`, `{TASK_ROOT_ABS}`. Все ссылки на `prompts/analyst.md` и `skills/*.md` — **абсолютные** пути (`{ORCHESTRATOR_ROOT}/prompts/analyst.md`), а не относительные. Это закрывает audit m5: из CWD `tasks/<id>/` относительный путь `../../prompts/...` выйдет за read-доступ если orchestrator-root не передан в `--add-dir`.
- `templates/analyst-mcp.json.tpl` — `.mcp.json` с MCP-серверами для аналитика: codemetadata (URL из projects.yaml). Плейсхолдер: `{CODEMETADATA_URL}`. (Naparnik вынесен в OQ2 → Phase 2.)

**Verification:**
- Оба файла существуют, содержат ожидаемые плейсхолдеры
- Подстановка тестовых значений (через `python` хелпер) даёт валидный JSON и Markdown с абсолютными путями

### Stage 4 — `spawn-analyst.ps1` + `_run-analyst.ps1` (главный entry-point)

**Закрывает audit C1, C2, M2, M3, m5, m6, m7.**

#### 4.1 `scripts/spawn-analyst.ps1` (родительский — из этой сессии)

**Параметры:** `-ProjectId <string>` (обяз.), `-TaskText <string>` (обяз.), `-TaskId <string>` (опц., автоген если нет).

**Делает (только подготовка, без quoting hell):**
1. Загружает `projects.yaml` через python-хелпер `python scripts/_python/yaml_get.py projects.yaml <projectId>` (надёжнее powershell-yaml + не требует Install-Module). Падает с понятной ошибкой, если проект не найден.
2. Генерит `TaskId = YYYY-MM-DD-<projectId>-NN`, где NN = next-free номер для дня (`Get-ChildItem tasks/ -Filter "$today-$projectId-*"`).
3. Создаёт `tasks/<task_id>/` и `tasks/<task_id>/analysis_raw/`.
4. Подставляет плейсхолдеры в шаблоны → пишет:
   - `tasks/<task_id>/CLAUDE.md` (из шаблона `analyst-CLAUDE.md.tpl`)
   - `tasks/<task_id>/.mcp.json` (из шаблона `analyst-mcp.json.tpl`)
   - `tasks/<task_id>/task_packet.json` (см. ниже)
   - `tasks/<task_id>/prompt.md` (короткое первое сообщение: «Прочитай CLAUDE.md этого каталога, далее следуй `prompts/analyst.md` по абсолютному пути.»)
5. **Pre-trust (audit M3):** для CWD аналитика и для `$orchestrator_root` — создаёт `~/.claude/projects/<encoded>/settings.json` с `{"trusted":true}`. Кодировка пути: `path.replace(":","-").replace("\\","-").replace("/","-").TrimStart("-")`. Записываем **в обе версии регистра диска** (`C--…` и `c--…`) — на случай M1.
6. `task_packet.json` содержит: `task_id`, `project_id`, `project_path` (абсолютный), `task_text`, `mcp_servers` (список из projects.yaml), `orchestrator_root` (абсолютный), `task_root` (абсолютный), `created_at` (ISO-8601 UTC), `expected_session_dir_hint` (см. m4 — это hint, не контракт), `wt_window_title`.
7. Запускает `wt.exe` через `-File`-wrapper (нет quoting):
   ```powershell
   wt.exe -w 0 nt `
     --title "analyst:$TaskId" `
     powershell.exe -NoExit -ExecutionPolicy Bypass `
          -File "$PSScriptRoot\_run-analyst.ps1" `
          -TaskRoot "$TaskRoot" `
          -ProjectPath "$ProjectPath" `
          -OrchestratorRoot "$OrchestratorRoot"
   ```
8. Возвращает в stdout JSON: `{task_id, task_root, project_path, wt_window_title, expected_session_dir_hint}`.

#### 4.2 `scripts/_run-analyst.ps1` (дочерний — внутри новой вкладки)

```powershell
param(
    [Parameter(Mandatory)][string]$TaskRoot,
    [Parameter(Mandatory)][string]$ProjectPath,
    [Parameter(Mandatory)][string]$OrchestratorRoot
)
$ErrorActionPreference = "Stop"
Set-Location $TaskRoot
$prompt = Get-Content -Path "$TaskRoot\prompt.md" -Raw -Encoding UTF8
& claude `
    --dangerously-skip-permissions `
    --add-dir $ProjectPath `
    --add-dir $OrchestratorRoot `
    --mcp-config "$TaskRoot\.mcp.json" `
    --strict-mcp-config `
    -- $prompt
```

Ключевые моменты:
- `Get-Content -Raw` — одна строка, не массив (audit C1).
- `-- $prompt` — `--` отделяет позиционный аргумент от флагов.
- `--add-dir` дублирован для project + orchestrator-root (audit m5/m6).
- `--mcp-config + --strict-mcp-config` (audit M2) — никакого CWD-autoload и interactive trust-prompt.
- `--dangerously-skip-permissions` оставлен — РИСК ПРИНЯТ, документирован в §2 и §7.

#### Verification (Stage 4)

- `powershell.exe -ExecutionPolicy Bypass -File scripts/spawn-analyst.ps1 -ProjectId example-erp -TaskText "smoke test"` создаёт `tasks/<id>/` с 4 файлами + `analysis_raw/`
- Появляется новая вкладка Windows Terminal с заголовком `analyst:<task_id>`
- Внутри вкладки запускается claude без ошибок quoting/escape (видно prompt-box)
- В `~/.claude/projects/<encoded>/settings.json` есть `{"trusted":true}` (для обеих case-вариантов)
- `task_packet.json` содержит **все** ожидаемые ключи (см. список выше)
- **Negative-тест:** `powershell.exe -ExecutionPolicy Bypass -File spawn-analyst.ps1 -ProjectId notexist -TaskText "x"` — exit 1 с сообщением `project 'notexist' not in registry`
- **Negative-тест:** wt.exe не найден → exit 2 с сообщением и подсказкой fallback (запустить `_run-analyst.ps1` в текущем терминале)

### Stage 5 — `validate-analysis.ps1` + `_python/validate.py` + `kill-analyst.ps1`

**Закрывает audit C3, C5, M4.**

#### 5.1 `_python/validate.py`

Принимает `<task_root>` как аргумент. Coded exit-коды:

| exit | смысл | сообщение |
|---|---|---|
| 0 | OK | summary (см. ниже) |
| 1 | Pydantic-ошибка | full `ValidationError` |
| 2 | Tool-exhaustion: keys не покрывают server_refs | `missing servers: [...]; required: [...]` |
| 3 | `raw_result_ref` указывает на несуществующий файл (новое — audit C5) | `analysis_raw/<server>/<ref> not found on disk` |
| 4 | `analysis_report.json` файла нет вообще (audit M4) | `analyst did not produce analysis_report.json — check session log or restart` |
| 5 | JSON битый (не parseable) | `JSONDecodeError at line N` |

Summary при exit=0: `task_id`, кол-во `relevant_files`, `existing_patterns`, `pitfalls_found`, `constraints_discovered`, `open_questions` (с разбивкой по severity), список серверов в `tool_evidence` с распределением round'ов и кол-вом ToolQuery каждый.

#### 5.2 `validate-analysis.ps1`

- Принимает `-TaskId <string>`
- Резолвит `tasks/<task_id>/`, вызывает `python scripts/_python/validate.py tasks/<task_id>/`
- Прокидывает exit-code, печатает summary

#### 5.3 `kill-analyst.ps1` (новое — audit C3)

- Принимает `-TaskId <string>`
- Находит вкладку wt по `wt_window_title` из task_packet.json
- Графически: `wt.exe focus-tab --title "analyst:<TaskId>"`, затем посылает Ctrl+C через `SendKeys`
- Грубо: `Get-Process -Name "claude" | Where-Object { $_.MainWindowTitle -like "*analyst:<TaskId>*" } | Stop-Process -Force`
- Дописывает в `task_packet.json` поле `killed_at`

#### Verification (Stage 5)

- Fixture-набор в `scripts/_python/_test_validate.py`:
  - (a) валидный отчёт + все raw-файлы на месте → exit 0, summary правильный
  - (b) пропущено `task_id` → exit 1 + ValidationError
  - (c) `tool_evidence = {}` → exit 2 + список missing servers
  - (d) `raw_result_ref` указывает на `analysis_raw/codemetadata/r1-q1-NOTEXIST.json` → exit 3
  - (e) `analysis_report.json` отсутствует в task_root → exit 4
  - (f) `analysis_report.json` = `not json{`  → exit 5
- `kill-analyst.ps1` на живом аналитике: вкладка закрывается, claude-процесс умирает, `task_packet.json` помечен `killed_at`

### Stage 6 — Smoke-test end-to-end на реальной задаче

**Сценарий:** проект `example-erp`, задача: "Перечисли все реквизиты справочника `Контрагенты` с их типами и кратким описанием для чего они используются (5-10 ключевых)."

**Шаги:**
1. Я (Claude = L2) запускаю `scripts/spawn-analyst.ps1 -ProjectId example-erp -TaskText "..."`.
2. Вижу task_id, ссылку на task_root, hint на session-dir.
3. Пользователь наблюдает в новой вкладке как аналитик работает.
4. **Пред-валидация workspace:** до запуска делаю `git status` в `example-erp-example-trade-exchange/` (или `Get-ChildItem -Path <project> -File -Recurse | Measure-Object`-снэпшот mtime) — фиксирую baseline.
5. По завершении (пользователь говорит "готов") → `scripts/validate-analysis.ps1 -TaskId X`.
6. Если validate упал — see «Retry-flow» ниже.
7. Sanity-чек качества: см. ниже.

**Retry-flow (audit M4):**
- exit 4 (нет файла): открываю `peek-analyst.ps1 -TaskId X`, смотрю последние 30 событий. Если аналитик закончил без Write — прошу пользователя сказать в той вкладке: «Прочитай свой отчёт, исправь, перезапиши `analysis_report.json`».
- exit 1 (Pydantic): копирую ValidationError → передаю в ту же вкладку аналитика как followup-сообщение через буфер обмена (Phase 1 — вручную).
- exit 2 (tool-exhaustion): «Сервер X не покрыт, добавь evidence».
- exit 3 (raw файла нет): «У ToolQuery `ref X` нет файла, либо допиши raw-dump, либо удали ToolQuery».
- Не делаем автоматический respawn — Phase 1, человек в петле.

**Sanity-чек (закрывает audit C2 + M7):**
- `analysis_report.json` существует в `tasks/<id>/`
- Pydantic-валидация — passed
- Tool-exhaustion — passed
- **CWD-isolation:** `git status` в `example-erp-example-trade-exchange/` после прогона — НИЧЕГО не изменилось вне tasks/. Если изменилось — аналитик нарушил read-only контракт, помечаем как баг и пишем в RLM pitfall.
- **Random-file existence (audit M7):** беру 3 случайных `RelevantFile.path` из отчёта → `Test-Path "$ProjectPath\$rel"` → все три = `True`. Если хоть один False — аналитик галлюцинирует, regression.
- В отчёте нет фразы "по моим знаниям" / "обычно в УТП" — только цитаты (мягкий grep)

### Stage 7 — Видимость для L2 (`peek-analyst.ps1`)

**Цель:** я (Claude = L2) могу заглянуть, что делает аналитик, не блокируясь.

**Механика:** Claude Code пишет полный лог сессии в `~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl`. Каждая строка — JSON-событие. **Закрывает audit M1:** не строим путь руками — discover'им:
```powershell
Get-ChildItem -Path "$HOME\.claude\projects" -Directory `
  | Where-Object { $_.Name -like "*Orchestrator*tasks*$TaskId*" } `
  | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```
Берёт самый свежий каталог (закрывает и нестабильность регистра `C--` vs `c--`, и любые будущие изменения схемы encoding).

**`peek-analyst.ps1`:**
- Принимает `-TaskId <string>`, опц. `-Tail <int>` (умолчание 30)
- Discovery (см. выше), затем последний `*.jsonl` по mtime в этом каталоге
- Парсит последние N событий, выдаёт компактную сводку:
  - tool_use: имя инструмента + первые 100 chars аргументов
  - assistant text: первые 200 chars
  - tool_result: статус (ok/error) + длина
- **Health-индикатор (audit C3):** в конце печатает строку `LAST_EVENT_AGO=<N>s` — время с последнего события (mtime файла). Если > 300s — добавляет предупреждение `WARNING: analyst may be stuck`.
- Если jsonl ещё не появился — печатает `STATUS: not_started_yet` (не падает)

**Verification:**
- После старта аналитика + пары tool-вызовов: `peek-analyst.ps1 -TaskId X` возвращает непустой список + `LAST_EVENT_AGO=<N>s`
- `peek-analyst.ps1 -TaskId X -Tail 100` возвращает до 100 событий
- На свежезапущенной задаче (jsonl ещё нет) — `STATUS: not_started_yet`
- Discovery работает корректно: создаём dummy-каталог `c--Users-<user>-workspace-Orchestrator-tasks-fake-01` и проверяем, что peek для `fake-01` его находит
- Имитация зависания: stop dummy claude, ждём 6 минут (или подделываем mtime через `(Get-Item file).LastWriteTime = (Get-Date).AddMinutes(-6)`) → peek печатает `WARNING: analyst may be stuck`

---

## 6. Open Questions (нужно решение пользователя ДО Stage 4)

### OQ1 — URL-ы MCP-серверов
v3 использует `${CODEMETADATA_UTP_URL:http://codemetadata:7620/mcp}` и т.д. — это hostname внутри докер-сети сервера. На ноутбуке этого DNS нет.

**Варианты:**
- **(a)** Прописать в `projects.yaml` реальные IP/hostname <vm-docker-host>: `http://<codemeta-host>:7620/mcp` и т.д.
- **(b)** Сделать SSH-туннели на ноутбуке (как RLM): `localhost:7620 → <vm-docker-host>:7620`
- **(c)** Прописать `<vm-docker-host>.local` в hosts ноутбука, использовать как DNS

**Рекомендация:** (a) — самое простое, работает out-of-box. Можно потом завернуть в туннели.

**Нужно от тебя:** список URL/портов codemetadata для example-erp, example-trade, example-mfg. Или: подтвердить, что (a) с реальными IP — OK, и дать актуальный IP <vm-docker-host> (по global rule: `<vm-docker-host>`).

### OQ2 — Naparnik
v3 описывает `naparnik` MCP с runtime tool discovery через `naparnik_tools.json`. Подключаем сейчас или Phase 1 только codemetadata?

**Рекомендация:** Phase 1 — **только codemetadata**. Naparnik добавим, когда увидим, что codemetadata-flow стабилен.

### OQ3 — Какой путь брать для каждого проекта (корень vs `1c/`)

Проекты в воркспейсе разложены неоднородно:

| Проект | В корне | В `1c/` |
|---|---|---|
| example-erp | `workspace/example-erp-example-trade-exchange/example-erp/` | — |
| example-trade  | `workspace/example-erp-example-trade-exchange/example-trade/`  | — |
| example-mfg | `workspace/example-mfg/` (с `CLAUDE.md`, `src/`, `ext/`) | `workspace/1c/example-mfg/` |

**Вопросы:**
- **OQ3a — example-mfg**: какой путь канонический для аналитика? Я бы взял `workspace/example-mfg/` (с CLAUDE.md = более вылеженный) и проигнорировал `1c/example-mfg/`. Подтверди.
- **OQ3c — общее правило**: на будущее ввести в `projects.yaml` поле `path_local` (полный путь) — без догадок. Для каждого нового проекта пишем явно.

**Рекомендация:** projects.yaml на старте:
```yaml
projects:
  example-erp:   { path_local: "<workspace>/1c-exchange/example-erp", mcp_servers: ["codemetadata"] }
  example-trade:    { path_local: "<workspace>/1c-exchange/example-trade",  mcp_servers: ["codemetadata"] }
  example-mfg: { path_local: "<workspace>/example-mfg",               mcp_servers: ["codemetadata"] }
```

### OQ4 — Git и Gitea-remote для Orchestrator
По global rule: каждый проект → remote в Gitea. Сейчас `Orchestrator/` не git-репо вообще.

**Рекомендация:** да, инициализировать git + добавить Gitea-remote. Делаем в Stage 1 (или сразу после согласования SDD, до Stage 1).

### OQ5 — Какая модель у аналитика?
v3 запускал аналитика отдельным `claude --print --model X`. У нас — interactive (`claude` без `--print`), модель = дефолт (Opus, скорее всего, что и так стоит у пользователя).

**Рекомендация:** Phase 1 — дефолтная модель, не указываем флаг. Если аналитик слишком тяжёлый — даунгрейдим в Sonnet (`--model claude-sonnet-4-6`).

---

## 7. Риски и митигации

| Риск | Митигация |
|---|---|
| `wt.exe` отсутствует (не Windows Terminal) | Stage 0 + Stage 4 проверяют `Get-Command wt.exe`; fallback — пользователю печатается команда `powershell.exe -ExecutionPolicy Bypass -File _run-analyst.ps1 ...` для ручного запуска |
| `claude --add-dir` flag переименован | [VERIFIED via `claude --help`] флаг существует. Если переименуют — Stage 0 smoke упадёт и сразу видно. |
| Кодировка пути session.jsonl нестабильна (audit M1) | Stage 7 — discovery через `Get-ChildItem -Filter "*Orchestrator*tasks*<task_id>*"`, не построение |
| Аналитик не пишет `analysis_report.json` (audit M4) | (a) `prompts/analyst.md` требует post-Write `Read` + объявление `REPORT READY`; (b) validate exit=4 с явной диагностикой; (c) Stage 6 retry-flow явный |
| Pre-trust не срабатывает (audit M3 + M1) | Pre-trust пишется в **обе** case-варианты (`C--…` и `c--…`) + полная нормализация `:` → `-`. Если всё равно prompt — `--dangerously-skip-permissions` его подавляет. |
| MCP-сервер недоступен (сеть, выкл. контейнер) | Аналитик упирается в OpenQuestion с severity=blocker, в отчёте видно. Не падаем тихо. |
| Powershell-yaml модуль не установлен | Закрыто: используем `python scripts/_python/yaml_get.py` (python и так в зависимостях) |
| Аналитик зависает (audit C3) | peek печатает `LAST_EVENT_AGO=Ns`; > 300s → WARNING. `kill-analyst.ps1` прибивает вкладку. |
| Аналитик пишет за пределы task_root (audit C2) | **РИСК ПРИНЯТ для Phase 1.** Sanity-check в Stage 6: `git status` в воркспейсе должен показать изменения только в `Orchestrator/tasks/<id>/`. Перенос на `--permission-mode acceptEdits --allowedTools` — Phase 3. |
| Inline-копия схемы тянет лишнее (audit C4) | Stage 2 verification: `grep -E "^from <prior-iteration>" schemas/analysis_v2.py` должен быть пуст |
| `raw_result_ref` врёт про существование файла (audit C5) | validate exit=3 для каждого несуществующего ref |
| `wt.exe` интерпретирует `;` как разделитель (audit C1) | Используем `-File`, никакого `-Command "...; ..."` |

---

## 8. Что делает SDD Phase 1 "готовым" (Definition of Done)

**Pre-conditions (audit M6 — БЕЗ этого Stage 1 не начинаем):**
- 0a. Все OQ1-OQ5 закрыты письменно в §10 Resolutions
- 0b. Stage 0 smoke `wt → powershell.exe → claude --version` прошёл
- 0c. **path_local INVARIANT** (added 2026-05-22 after Stage 6 D2 finding): для каждого проекта в `projects.yaml`, `path_local` — это корень XML-выгрузки конфигурации 1С, которую индексирует codemetadata-контейнер этого проекта. Прямые потомки `path_local` должны включать `Configuration.xml` + `Catalogs/` + `Documents/` etc. Для `example-erp`/`example-trade` дамп живёт в Gitea (`admin/example-erp-src`, `admin/example-trade-src`), автосинк с <vm-docker-host> `/opt/mcp-xml/<p>/src` через systemd-timer `sync-xml-to-gitea.timer` (30 мин). `spawn-analyst.ps1` enforces инвариант fail-fast перед спавном.

**Post-conditions (Phase 1 = DONE когда):**
1. Все 7 стадий (0-7) пройдены, verification каждой — pass
2. Stage 6 smoke на `example-erp` дал валидный `analysis_report.json` с реальными ссылками
3. Stage 6 sanity-check: 3 случайных RelevantFile.path резолвятся через `Test-Path` под `path_local` (precondition 0c обеспечивает FS-резолвимость); git status в воркспейсе чист вне `Orchestrator/tasks/`
4. `peek-analyst.ps1` показывает события + `LAST_EVENT_AGO`
5. `kill-analyst.ps1` тестово прибивает dummy-аналитика
6. Каталог `Orchestrator/` запушен в Gitea
7. RLM-факт записан: «Phase 1 done, точка входа = spawn-analyst.ps1»

После этого — **STOP**, ждём решения пользователя про Phase 2 (SDD-писатель).

---

## 9. Отказы (REFUSE)

Стадии, от которых я отказался бы:
- **Realtime streaming аналитика в L2-чат** — отказ, оставляю как pull через `peek-analyst.ps1`. Push потребует watcher/демон, это overkill для Phase 1.
- **Multi-tab session-continuation** — отказ, Phase 5. Сейчас каждая задача = свежий task_root.
- **Авто-определение типа задачи и выбор skills** — отказ. Аналитик получает все 5 скилов всегда. Контекстуальный выбор (как в v3 yaml) — Phase 3+.
- **Технический sandbox аналитика** — отказ для Phase 1, риск зафиксирован в §2/§7. Полноценная изоляция через `--permission-mode acceptEdits --allowedTools` — Phase 3.

---

## 10. Resolutions (закрытие Open Questions)

**OQ1 — URL-ы MCP-серверов:** ЗАКРЫТО (2026-05-22, эмпирически проверено с ноутбука).
- URL: `http://<vm-docker-host>:{port}/mcp` напрямую, без туннеля.
- Порты (verified `docker ps` on `<vm-docker-host>`): example-erp 7620, example-trade 7630, example-mfg 7610, <other-project> <port>, <other-project> <port>, <other-project> <port>, <other-project> <port>, <other-project> <port>, <other-project> <port>. Все Up healthy.
- Связность: `ping <vm-docker-host>` → 2/2 ответа RTT 88-176ms; `curl http://<codemeta-host>:7610/mcp` → HTTP 406 (MCP отвечает, 406 = SSE без Accept-хедера = норма для curl). Идентично для :7620 и для :8250 (rlm).
- Маршрут: предполагается прямая LAN-доступность до `<vm-docker-host>` / `<rlm-host>` (например через VPN). Конкретные адреса зависят от твоего сетевого setup.
- Implication для projects.yaml: `mcp_servers: ["codemetadata"]` → шаблон `analyst-mcp.json.tpl` подставляет `http://<vm-docker-host>:{codemeta_port}/mcp` по `project.codemeta_port`.

**OQ2 — Naparnik:** ЗАКРЫТО — отложено в Phase 2+. В Phase 1 только codemetadata.

**OQ3a — example-mfg path:** ЗАКРЫТО (2026-05-22, эмпирически через `git log`).
- Канонический: `<workspace>/example-mfg`.
- Обоснование: `workspace/example-mfg/` имеет HEAD `5a0a9b8b` (`fix(фл_ДФЛ HTTP): ОбменДФЛ_post оборачивает результат`) и `ad53c655` — **2 коммита впереди** `workspace/1c/example-mfg/` (HEAD `a266ffc8`). Свежий .env май 20. `1c/example-mfg/` устарел; держит 2.7 GB `.dt` файл и `dist/` (артефакты сборки), который для аналитика не нужен.
- Действие: использовать `workspace/example-mfg` в projects.yaml. `1c/example-mfg` для аналитика не упоминать (пользователь сам потом решит, удалить ли его).

**OQ3c — общее правило `path_local`:** ЗАКРЫТО — каждая запись в projects.yaml обязана иметь явный `path_local`.

**OQ4 — Git + Gitea remote:** ЗАКРЫТО — да, инициализируем в Stage 1 (`git init` + `git remote add gitea http://<gitea-host>:3000/admin/Orchestrator.git`). Репо в Gitea создаём через API заранее (вне SDD-стадии).

**OQ5 — Модель аналитика:** ЗАКРЫТО — дефолтная (Opus, как у пользователя). Без флага `--model`. Если потребуется даунгрейд — `--model sonnet` (audit n5 — корректный alias).

**OQ6 — PowerShell edition:** ЗАКРЫТО (2026-05-22, Stage 0 smoke discovery).
- На ноутбуке установлен **только Windows PowerShell 5.1** (`powershell.exe` в `C:\Windows\System32\WindowsPowerShell\v1.0\`). PowerShell 7 (`pwsh`) НЕ установлен (verified: `where.exe pwsh` → not found; `C:\Program Files\PowerShell\` не существует).
- Решение: SDD везде использует `powershell.exe -ExecutionPolicy Bypass -File ...`. Все скрипты Phase 1 пишем 5.1-совместимо (нет `&&`/`||`, нет `?:`/`??`/`?.`).
- File I/O правило: writes — `Out-File -Encoding utf8` / `Set-Content -Encoding utf8` (default 5.1 = UTF-16 LE с BOM ломает чужих читателей); reads чужих utf-8 — `Get-Content -Raw -Encoding UTF8`.
- Implication для Stage 4 wrapper: вызов `claude.cmd` с многострочным `$prompt` — следить за quoting; при необходимости использовать `--%` stop-parsing token.
