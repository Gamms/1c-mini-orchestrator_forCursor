"""Read/update orchestrator task packet JSON files."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PHASE_PACKET_FILES: dict[str, str] = {
    "analyst": "task_packet.json",
    "sdd-writer": "sdd_writer_packet.json",
    "implementer": "implementer_packet.json",
    "auditor": "auditor_packet.json",
}


def packet_path(task_root: Path, phase: str) -> Path:
    rel = PHASE_PACKET_FILES.get(phase)
    if not rel:
        raise ValueError(f"unknown phase: {phase}")
    return task_root / rel


def load_packet(task_root: Path, phase: str) -> dict[str, Any]:
    path = packet_path(task_root, phase)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_packet(task_root: Path, phase: str, packet: dict[str, Any]) -> None:
    path = packet_path(task_root, phase)
    path.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_packet(task_root: Path, phase: str, **fields: Any) -> dict[str, Any]:
    packet = load_packet(task_root, phase)
    packet.update(fields)
    save_packet(task_root, phase, packet)
    return packet


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
