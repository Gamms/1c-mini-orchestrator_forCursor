"""Convert task-scoped .mcp*.json files into cursor-sdk MCP configs."""

from __future__ import annotations

import json
from pathlib import Path

from cursor_sdk.types import HttpMcpServerConfig, McpServerConfig

PHASE_MCP_FILES: dict[str, str] = {
    "analyst": ".mcp.json",
    "sdd-writer": ".mcp.sdd-writer.json",
    "implementer": ".mcp.implementer.json",
    "auditor": ".mcp.auditor.json",
}


def mcp_file_for_phase(task_root: Path, phase: str) -> Path:
    rel = PHASE_MCP_FILES.get(phase)
    if not rel:
        raise ValueError(f"unknown phase: {phase}")
    return task_root / rel


def load_mcp_servers(task_root: Path, phase: str) -> dict[str, McpServerConfig]:
    path = mcp_file_for_phase(task_root, phase)
    if not path.exists():
        raise FileNotFoundError(f"MCP config missing: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    servers = raw.get("mcpServers") or raw.get("mcp_servers") or {}
    out: dict[str, McpServerConfig] = {}
    for name, cfg in servers.items():
        url = cfg.get("url")
        if not url:
            raise ValueError(f"MCP server {name!r} in {path} has no url")
        transport = str(cfg.get("type") or "http").lower()
        headers = cfg.get("headers") or None
        out[name] = HttpMcpServerConfig(url=url, type=transport, headers=headers)
    return out
