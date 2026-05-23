"""Load orchestrator.yaml (Cursor runtime defaults)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

_DEFAULTS: dict[str, Any] = {
    "cursor": {
        "model": "composer-2.5",
        "api_key_env": "CURSOR_API_KEY",
        "setting_sources": [],
    }
}


def orchestrator_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_config() -> dict[str, Any]:
    cfg_path = orchestrator_root() / "orchestrator.yaml"
    if not cfg_path.exists() or yaml is None:
        return dict(_DEFAULTS)
    loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    cursor = dict(_DEFAULTS.get("cursor", {}))
    cursor.update(loaded.get("cursor") or {})
    return {"cursor": cursor}


def cursor_model(override: str | None = None) -> str:
    if override:
        return override
    return str(load_config()["cursor"].get("model") or "composer-2.5")


def cursor_api_key_env() -> str:
    return str(load_config()["cursor"].get("api_key_env") or "CURSOR_API_KEY")


def load_cursor_api_key() -> str | None:
    env_name = cursor_api_key_env()
    value = os.environ.get(env_name)
    if value and value.strip():
        return value.strip()

    root = orchestrator_root()
    candidates = [
        root / ".env",
        root / "config" / "cursor-api-key.local",
    ]
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("CURSOR_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    os.environ[env_name] = val
                    return val
            if line.startswith(("crsr_", "cursor_")):
                os.environ[env_name] = line
                return line
    return None
