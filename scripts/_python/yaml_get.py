"""Read projects.yaml and print a project's fields as KEY=VALUE pairs.

Used by spawn-*.ps1 to avoid requiring the PowerShell-Yaml module.
Python is already a Phase-1 dependency (validate.py, schemas).

Usage:
    python scripts/_python/yaml_get.py <project_id>

Output (stdout, one per line):
    path_local=...
    codemeta_port=...
    mcp_servers=codemetadata,...
    vm_docker_host=...
    extra_writable_dir=...      (empty string if absent)
    mcp_config_file=...         (empty if absent — use template MCP)
    skip_path_invariant=true|false
    allow_missing_git_remote=true|false

Exit codes:
    0  success
    1  unknown project_id
    2  projects.yaml missing or malformed
    3  required field missing for the project
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECTS_YAML = ROOT / "projects.yaml"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: yaml_get.py <project_id>", file=sys.stderr)
        return 2
    project_id = argv[1]

    try:
        import yaml
    except ImportError:
        print("pyyaml not installed; pip install pyyaml", file=sys.stderr)
        return 2

    if not PROJECTS_YAML.exists():
        print(f"projects.yaml not found at {PROJECTS_YAML}", file=sys.stderr)
        return 2

    try:
        data = yaml.safe_load(PROJECTS_YAML.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"projects.yaml parse error: {exc}", file=sys.stderr)
        return 2

    if not isinstance(data, dict) or "projects" not in data:
        print("projects.yaml missing top-level 'projects' key", file=sys.stderr)
        return 2

    projects = data["projects"]
    if project_id not in projects:
        print(
            f"project '{project_id}' not in registry; "
            f"known: {sorted(projects.keys())}",
            file=sys.stderr,
        )
        return 1

    entry = projects[project_id]
    mcp_config_file = entry.get("mcp_config_file", "") or ""
    skip_path_invariant = bool(entry.get("skip_path_invariant", False))
    allow_missing_git_remote = bool(entry.get("allow_missing_git_remote", False))

    required = ["path_local", "mcp_servers"]
    if not mcp_config_file:
        required.extend(["codemeta_port"])
    for field in required:
        if field not in entry:
            print(
                f"project '{project_id}' missing required field '{field}'",
                file=sys.stderr,
            )
            return 3

    vm_host = data.get("vm_docker_host", "")
    extra_writable_dir = entry.get("extra_writable_dir", "")
    codemeta_port = entry.get("codemeta_port", "")

    print(f"path_local={entry['path_local']}")
    print(f"codemeta_port={codemeta_port}")
    servers = entry["mcp_servers"]
    if isinstance(servers, str):
        servers_list = [servers]
    else:
        servers_list = list(servers)
    print(f"mcp_servers={','.join(servers_list)}")
    print(f"vm_docker_host={vm_host}")
    print(f"extra_writable_dir={extra_writable_dir}")
    print(f"mcp_config_file={mcp_config_file}")
    print(f"skip_path_invariant={'true' if skip_path_invariant else 'false'}")
    print(f"allow_missing_git_remote={'true' if allow_missing_git_remote else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
