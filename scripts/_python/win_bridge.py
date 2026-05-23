"""Windows-safe bootstrap for cursor-sdk local bridge.

cursor-sdk 0.1.5 uses selectors.select() on a subprocess pipe when
discovering the bridge. On Windows that raises WinError 10038. We start
the bundled bridge with Node, read the discovery line from stderr, and
export CURSOR_SDK_BRIDGE_URL / CURSOR_SDK_BRIDGE_TOKEN before Agent.create().
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

_BRIDGE_PROC: subprocess.Popen[str] | None = None
_BRIDGE_LOCK = threading.Lock()


def _find_node() -> str:
    for candidate in (
        shutil.which("node"),
        r"C:\Program Files\nodejs\node.exe",
        os.path.expandvars(
            r"%LOCALAPPDATA%\Programs\cursor\resources\app\resources\helpers\node.exe"
        ),
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("node.exe not found; install Node.js or Cursor helpers")


def _bridge_js_path() -> Path:
    import cursor_sdk

    path = (
        Path(cursor_sdk.__file__).resolve().parent
        / "_vendor"
        / "bridge"
        / "dist"
        / "bin"
        / "cursor-sdk-bridge.js"
    )
    if not path.is_file():
        raise RuntimeError(f"cursor-sdk bridge not found at {path}")
    return path


def _parse_ready_line(line: str) -> dict[str, Any]:
    prefix = "cursor-sdk-bridge ready "
    if prefix not in line:
        raise RuntimeError(f"unexpected bridge output: {line[:200]}")
    payload = line.split(prefix, 1)[1].strip()
    data = json.loads(payload)
    url = str(data.get("url") or "")
    token = str(data.get("authToken") or "")
    token_file = data.get("authTokenFile")
    if not token and token_file:
        token = Path(str(token_file)).read_text(encoding="utf-8").strip()
    if not url or not token:
        raise RuntimeError("bridge discovery payload missing url/token")
    return {"url": url, "token": token}


def _terminate_bridge() -> None:
    global _BRIDGE_PROC
    proc = _BRIDGE_PROC
    _BRIDGE_PROC = None
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def ensure_cursor_bridge(workspace: str | os.PathLike[str]) -> None:
    if os.environ.get("CURSOR_SDK_BRIDGE_URL") and os.environ.get("CURSOR_SDK_BRIDGE_TOKEN"):
        return
    if sys.platform != "win32":
        return

    global _BRIDGE_PROC
    with _BRIDGE_LOCK:
        if os.environ.get("CURSOR_SDK_BRIDGE_URL") and os.environ.get("CURSOR_SDK_BRIDGE_TOKEN"):
            return
        if _BRIDGE_PROC is not None and _BRIDGE_PROC.poll() is None:
            return

        node = _find_node()
        bridge_js = _bridge_js_path()
        cwd = str(Path(workspace).resolve())
        proc = subprocess.Popen(
            [node, str(bridge_js), "--workspace", cwd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
        )
        assert proc.stderr is not None
        deadline = time.monotonic() + 30
        discovery: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            line = proc.stderr.readline()
            if line:
                if "cursor-sdk-bridge ready " in line:
                    discovery = _parse_ready_line(line)
                    break
            elif proc.poll() is not None:
                rest = proc.stderr.read() or ""
                raise RuntimeError(f"bridge exited early (code={proc.returncode}): {rest[:300]}")
            time.sleep(0.05)
        if discovery is None:
            proc.terminate()
            raise RuntimeError("timed out waiting for cursor-sdk-bridge ready line")

        os.environ["CURSOR_SDK_BRIDGE_URL"] = discovery["url"]
        os.environ["CURSOR_SDK_BRIDGE_TOKEN"] = discovery["token"]
        _BRIDGE_PROC = proc
        atexit.register(_terminate_bridge)


atexit.register(_terminate_bridge)
