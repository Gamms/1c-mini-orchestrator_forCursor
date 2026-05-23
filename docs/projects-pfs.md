# Проект PFS в оркестраторе

Регистрация: `projects.yaml` → `pfs`  
Путь к коду: `C:/Tools/DevsProject/ai/PFS`

## Отличия от docker/codemetadata-сценария

PFS — репозиторий расширения 1С (не полный XML-дамп с `Configuration.xml` в корне). Поэтому:

- `skip_path_invariant: true` — spawn не требует `Catalogs/` в корне
- `mcp_config_file: config/pfs-mcp.json` — локальный стек MCP (порты 8000–8008), синхронизирован с `PFS/.cursor/mcp.json`
- `allow_missing_git_remote: true` — имплементатор может коммитить локально без `origin`/`gitea`

## Перед первым spawn

1. **Cursor API key**
   ```powershell
   $env:CURSOR_API_KEY = "cursor_..."
   ```

2. **Зависимости оркестратора**
   ```powershell
   cd C:\Tools\DevsProject\ai\hermes
   py -m pip install -e .
   ```

3. **MCP-серверы PFS** — должны быть запущены (как в обычной работе в Cursor):
   - `http://localhost:8000/mcp` — code-metadata
   - `http://localhost:8002/mcp` — syntax-checker
   - … см. `config/pfs-mcp.json`

   Если порты или URL изменились в `PFS/.cursor/mcp.json`, обновите `hermes/config/pfs-mcp.json`.

4. **Чистое git-дерево PFS** — перед фазой implementer:
   ```powershell
   git -C C:\Tools\DevsProject\ai\PFS status
   ```
   Закоммитьте или спрячьте незакоммиченные изменения.

5. **ИБ для 1c-data-mcp** — в `.dev.env` указано `INFOBASE_PUBLISH_URL=http://localhost/ARA_Demo/ru/`; публикация должна отвечать на `/hs/mcp` без пароля.

## Запуск задачи

```powershell
cd C:\Tools\DevsProject\ai\hermes

# Фаза 1 — аналитик
.\scripts\spawn-analyst.cmd -ProjectId pfs -TaskText "Описание задачи"
# если политика блокирует .ps1 напрямую — .cmd обходит ExecutionPolicy

# После REPORT READY + validate
.\scripts\validate-analysis.ps1 -TaskId <task_id>
.\scripts\spawn-sdd-writer.ps1 -TaskId <task_id>
# … далее implementer → auditor
```

## L2 в Cursor

Откройте `hermes` в Cursor и пишите оркестратору, например:

```
Проект pfs. Задача: добавить метод печати в PFS_Api
```

Оркестратор следует `AGENTS.md` и вызывает скрипты сам.

## Синхронизация MCP-конфига

При изменении `PFS/.cursor/mcp.json`:

```powershell
Copy-Item C:\Tools\DevsProject\ai\PFS\.cursor\mcp.json `
  C:\Tools\DevsProject\ai\hermes\config\pfs-mcp.json -Force
```

Убедитесь, что у каждого сервера есть `"type": "http"` (оркестратор добавляет при необходимости).
