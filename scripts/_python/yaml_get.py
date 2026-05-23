"""Read projects.yaml and print a project's fields as KEY=VALUE pairs.

Used by spawn-analyst.ps1 to avoid requiring the PowerShell-Yaml module.
Python is already a Phase-1 dependency (validate.py, schemas).

Usage:
    python scripts/_python/yaml_get.py <project_id>

Output (stdout, one per line):
    path_local=...
    codemeta_port=...
    mcp_servers=codemetadata,...
    vm_docker_host=...
    extra_writable_dir=...      (empty string if absent in projects.yaml)

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
    required = ["path_local", "codemeta_port", "mcp_servers"]
    for field in required:
        if field not in entry:
            print(
                f"project '{project_id}' missing required field '{field}'",
                file=sys.stderr,
            )
            return 3

    vm_host = data.get("vm_docker_host", "")
    extra_writable_dir = entry.get("extra_writable_dir", "")
    print(f"path_local={entry['path_local']}")
    print(f"codemeta_port={entry['codemeta_port']}")
    print(f"mcp_servers={','.join(entry['mcp_servers'])}")
    print(f"vm_docker_host={vm_host}")
    print(f"extra_writable_dir={extra_writable_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
