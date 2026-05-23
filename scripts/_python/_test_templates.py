"""Stage 3 verification: substitute placeholders in templates and validate.

Runs from Orchestrator root: `python scripts/_python/_test_templates.py`.
Exits non-zero on any failure.
"""

from __future__ import annotations

import json
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PLACEHOLDERS = {
    "PROJECT_ID": "example-erp",
    "PROJECT_PATH": "<workspace>/1c-exchange/example-erp",
    "TASK_ID": "2026-05-22-example-erp-01",
    "TASK_TEXT": "Add INN attribute to Counterparties",
    "ORCHESTRATOR_ROOT": "<orchestrator-root>",
    "TASK_ROOT_ABS": "<orchestrator-root>/tasks/2026-05-22-example-erp-01",
    "CODEMETADATA_URL": "http://<codemeta-host>:7620/mcp",
    "ANALYSIS_REPORT_REL": "analysis_report.json",
    # Phase 3 implementer placeholders
    "SDD_REF": "sdd.md",
    "SDD_METADATA_REF": "sdd_metadata.json",
    "GITEA_REMOTE_URL": "http://<gitea-host>:3000/admin/example-erp-src.git",
    "BRANCH_NAME": "orchestrator/2026-05-22-example-erp-01",
    # Phase 4 auditor placeholders
    "IMPL_METADATA_REF": "impl_metadata.json",
    "ANALYSIS_REF": "analysis_report.json",
    "BRANCH_AUDITED": "orchestrator/2026-05-22-example-erp-01",
    "BRANCH_SHA_AT_AUDIT_START": "0ec0e934abc1234567890fedcba9876543210000",
}


def render(template_text: str) -> str:
    out = template_text
    for key, value in PLACEHOLDERS.items():
        out = out.replace("{" + key + "}", value)
    return out


def check(name: str, cond: bool, detail: str = "") -> bool:
    status = "PASS" if cond else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return cond


def main() -> int:
    failures = 0

    mcp_tpl = (ROOT / "templates/analyst-mcp.json.tpl").read_text(encoding="utf-8")
    mcp_rendered = render(mcp_tpl)
    if not check(
        "templates/analyst-mcp.json.tpl: contains {CODEMETADATA_URL} placeholder",
        "{CODEMETADATA_URL}" in mcp_tpl,
    ):
        failures += 1
    if not check(
        "templates/analyst-mcp.json.tpl: no leftover placeholders after render",
        "{" not in mcp_rendered or all(
            ph not in mcp_rendered for ph in (
                "{PROJECT_ID}", "{PROJECT_PATH}", "{TASK_ID}",
                "{TASK_TEXT}", "{ORCHESTRATOR_ROOT}", "{TASK_ROOT_ABS}",
                "{CODEMETADATA_URL}"
            )
        ),
    ):
        failures += 1
    try:
        parsed = json.loads(mcp_rendered)
        url = parsed["mcpServers"]["1c-codemetadata"]["url"]
        ok = url == PLACEHOLDERS["CODEMETADATA_URL"]
    except Exception as exc:  # noqa: BLE001
        ok = False
        url = f"<error: {exc}>"
    if not check(
        "templates/analyst-mcp.json.tpl: rendered is valid JSON with expected url",
        ok,
        f"url={url}",
    ):
        failures += 1
    # Regression guard for D1 (Stage 6 e2e finding, 2026-05-22): 1c-cloud-mcp
    # is Streamable HTTP, not pure SSE. type=sse causes Claude Code 2.1.119 to
    # silently fail to bind mcp__1c-codemetadata__* tools, forcing analysts to
    # fall back to direct curl. type MUST stay "http".
    try:
        parsed = json.loads(mcp_rendered)
        transport = parsed["mcpServers"]["1c-codemetadata"]["type"]
        ok = transport == "http"
    except Exception as exc:  # noqa: BLE001
        ok = False
        transport = f"<error: {exc}>"
    if not check(
        "templates/analyst-mcp.json.tpl: 1c-codemetadata transport type == 'http' (D1 regression guard)",
        ok,
        f"type={transport}",
    ):
        failures += 1

    claude_tpl = (ROOT / "templates/analyst-CLAUDE.md.tpl").read_text(encoding="utf-8")
    required_placeholders = [
        "{PROJECT_ID}", "{PROJECT_PATH}", "{TASK_ID}",
        "{TASK_TEXT}", "{ORCHESTRATOR_ROOT}", "{TASK_ROOT_ABS}",
    ]
    for ph in required_placeholders:
        if not check(
            f"templates/analyst-CLAUDE.md.tpl: contains {ph}",
            ph in claude_tpl,
        ):
            failures += 1

    claude_rendered = render(claude_tpl)
    if not check(
        "templates/analyst-CLAUDE.md.tpl: no leftover placeholders after render",
        all(ph not in claude_rendered for ph in required_placeholders + ["{CODEMETADATA_URL}"]),
    ):
        failures += 1
    if not check(
        "templates/analyst-CLAUDE.md.tpl: rendered uses absolute paths only "
        "(no '..\\' or '../' refs that would escape task_root)",
        ".." not in claude_rendered.replace("...", "")
        .replace(":/Users/" + os.environ.get("USERNAME", ""), ""),  # ignore any windows path normalization
    ):
        failures += 1

    bad_refs = [
        line for line in claude_rendered.splitlines()
        if "{ORCHESTRATOR_ROOT}/prompts/" in line or "{ORCHESTRATOR_ROOT}/skills/" in line
    ]
    if not check(
        "templates/analyst-CLAUDE.md.tpl: no unrendered ORCHESTRATOR_ROOT refs in output",
        len(bad_refs) == 0,
        f"leftover lines: {bad_refs[:2]}" if bad_refs else "",
    ):
        failures += 1

    # ----- Phase 2 sdd-writer templates -----
    sdd_mcp_tpl = (ROOT / "templates/sdd-writer-mcp.json.tpl").read_text(encoding="utf-8")
    sdd_mcp_rendered = render(sdd_mcp_tpl)
    if not check(
        "templates/sdd-writer-mcp.json.tpl: contains {CODEMETADATA_URL}",
        "{CODEMETADATA_URL}" in sdd_mcp_tpl,
    ):
        failures += 1
    try:
        parsed = json.loads(sdd_mcp_rendered)
        url = parsed["mcpServers"]["1c-codemetadata"]["url"]
        transport = parsed["mcpServers"]["1c-codemetadata"]["type"]
        ok = url == PLACEHOLDERS["CODEMETADATA_URL"] and transport == "http"
    except Exception as exc:  # noqa: BLE001
        ok = False
        url = f"<error: {exc}>"
        transport = "<error>"
    if not check(
        "templates/sdd-writer-mcp.json.tpl: rendered JSON has expected url + type=http (D1 regression guard)",
        ok,
        f"url={url} type={transport}",
    ):
        failures += 1

    sdd_claude_tpl = (ROOT / "templates/sdd-writer-CLAUDE.md.tpl").read_text(encoding="utf-8")
    sdd_required_placeholders = [
        "{PROJECT_ID}", "{PROJECT_PATH}", "{TASK_ID}",
        "{TASK_TEXT}", "{ORCHESTRATOR_ROOT}", "{TASK_ROOT_ABS}",
        "{ANALYSIS_REPORT_REL}",
    ]
    for ph in sdd_required_placeholders:
        if not check(
            f"templates/sdd-writer-CLAUDE.md.tpl: contains {ph}",
            ph in sdd_claude_tpl,
        ):
            failures += 1

    sdd_claude_rendered = render(sdd_claude_tpl)
    if not check(
        "templates/sdd-writer-CLAUDE.md.tpl: no leftover placeholders after render",
        all(ph not in sdd_claude_rendered for ph in sdd_required_placeholders + ["{CODEMETADATA_URL}"]),
    ):
        failures += 1
    sdd_bad_refs = [
        line for line in sdd_claude_rendered.splitlines()
        if "{ORCHESTRATOR_ROOT}/prompts/" in line
        or "{ORCHESTRATOR_ROOT}/skills/" in line
        or "{ORCHESTRATOR_ROOT}/docs/" in line
        or "{ORCHESTRATOR_ROOT}/schemas/" in line
    ]
    if not check(
        "templates/sdd-writer-CLAUDE.md.tpl: no unrendered ORCHESTRATOR_ROOT refs",
        len(sdd_bad_refs) == 0,
        f"leftover lines: {sdd_bad_refs[:2]}" if sdd_bad_refs else "",
    ):
        failures += 1
    # sdd-writer-CLAUDE.md references absolute path to prompts/sdd-writer.md
    if not check(
        "templates/sdd-writer-CLAUDE.md.tpl: rendered references absolute prompts/sdd-writer.md path",
        f"{PLACEHOLDERS['ORCHESTRATOR_ROOT']}/prompts/sdd-writer.md" in sdd_claude_rendered,
    ):
        failures += 1

    # ----- Phase 3 implementer templates -----
    impl_mcp_tpl = (ROOT / "templates/implementer-mcp.json.tpl").read_text(encoding="utf-8")
    impl_mcp_rendered = render(impl_mcp_tpl)
    if not check(
        "templates/implementer-mcp.json.tpl: contains {CODEMETADATA_URL}",
        "{CODEMETADATA_URL}" in impl_mcp_tpl,
    ):
        failures += 1
    try:
        parsed = json.loads(impl_mcp_rendered)
        url = parsed["mcpServers"]["1c-codemetadata"]["url"]
        transport = parsed["mcpServers"]["1c-codemetadata"]["type"]
        ok = url == PLACEHOLDERS["CODEMETADATA_URL"] and transport == "http"
    except Exception as exc:  # noqa: BLE001
        ok = False
        url = f"<error: {exc}>"
        transport = "<error>"
    if not check(
        "templates/implementer-mcp.json.tpl: rendered JSON has expected url + type=http (D1 regression guard)",
        ok,
        f"url={url} type={transport}",
    ):
        failures += 1

    impl_claude_tpl = (ROOT / "templates/implementer-CLAUDE.md.tpl").read_text(encoding="utf-8")
    impl_required_placeholders = [
        "{PROJECT_ID}", "{PROJECT_PATH}", "{TASK_ID}",
        "{TASK_TEXT}", "{ORCHESTRATOR_ROOT}", "{TASK_ROOT_ABS}",
        "{SDD_REF}", "{SDD_METADATA_REF}",
        "{GITEA_REMOTE_URL}", "{BRANCH_NAME}",
    ]
    for ph in impl_required_placeholders:
        if not check(
            f"templates/implementer-CLAUDE.md.tpl: contains {ph}",
            ph in impl_claude_tpl,
        ):
            failures += 1

    impl_claude_rendered = render(impl_claude_tpl)
    if not check(
        "templates/implementer-CLAUDE.md.tpl: no leftover placeholders after render",
        all(ph not in impl_claude_rendered for ph in impl_required_placeholders + ["{CODEMETADATA_URL}"]),
    ):
        failures += 1
    impl_bad_refs = [
        line for line in impl_claude_rendered.splitlines()
        if "{ORCHESTRATOR_ROOT}/prompts/" in line
        or "{ORCHESTRATOR_ROOT}/skills/" in line
        or "{ORCHESTRATOR_ROOT}/docs/" in line
        or "{ORCHESTRATOR_ROOT}/schemas/" in line
    ]
    if not check(
        "templates/implementer-CLAUDE.md.tpl: no unrendered ORCHESTRATOR_ROOT refs",
        len(impl_bad_refs) == 0,
        f"leftover lines: {impl_bad_refs[:2]}" if impl_bad_refs else "",
    ):
        failures += 1
    # implementer-CLAUDE.md references absolute path to prompts/implementer.md
    if not check(
        "templates/implementer-CLAUDE.md.tpl: rendered references absolute prompts/implementer.md path",
        f"{PLACEHOLDERS['ORCHESTRATOR_ROOT']}/prompts/implementer.md" in impl_claude_rendered,
    ):
        failures += 1
    # branch convention substituted (orchestrator/<task_id> with task_id rendered)
    expected_branch = f"orchestrator/{PLACEHOLDERS['TASK_ID']}"
    if not check(
        "templates/implementer-CLAUDE.md.tpl: rendered includes literal branch name "
        f"'{expected_branch}'",
        expected_branch in impl_claude_rendered,
    ):
        failures += 1
    # the `orch <task_id>` commit-substring convention appears in the rendered template
    if not check(
        "templates/implementer-CLAUDE.md.tpl: rendered includes literal 'orch <task_id>' "
        "commit convention substring",
        f"orch {PLACEHOLDERS['TASK_ID']}" in impl_claude_rendered,
    ):
        failures += 1

    # ----- Phase 4 auditor templates -----
    aud_toml_tpl = (ROOT / "templates/auditor-codex.toml.tpl").read_text(encoding="utf-8")
    aud_toml_rendered = render(aud_toml_tpl)
    if not check(
        "templates/auditor-codex.toml.tpl: contains {CODEMETADATA_URL}",
        "{CODEMETADATA_URL}" in aud_toml_tpl,
    ):
        failures += 1
    if not check(
        "templates/auditor-codex.toml.tpl: no leftover placeholders after render",
        "{CODEMETADATA_URL}" not in aud_toml_rendered
        and "{TASK_ROOT_ABS}" not in aud_toml_rendered.replace(
            "{TASK_ROOT_ABS}\\.codex_home", ""
        ),
    ):
        failures += 1
    try:
        parsed_toml = tomllib.loads(aud_toml_rendered)
        cm = parsed_toml.get("mcp_servers", {}).get("codemetadata", {})
        toml_url = cm.get("url")
        toml_ok = toml_url == PLACEHOLDERS["CODEMETADATA_URL"]
    except Exception as exc:  # noqa: BLE001
        toml_ok = False
        toml_url = f"<error: {exc}>"
    if not check(
        "templates/auditor-codex.toml.tpl: rendered parses as TOML with "
        "[mcp_servers.codemetadata].url == fixture url",
        toml_ok,
        f"url={toml_url}",
    ):
        failures += 1

    aud_claude_tpl = (ROOT / "templates/auditor-CLAUDE.md.tpl").read_text(encoding="utf-8")
    aud_required_placeholders = [
        "{PROJECT_ID}", "{PROJECT_PATH}", "{TASK_ID}",
        "{TASK_TEXT}", "{ORCHESTRATOR_ROOT}", "{TASK_ROOT_ABS}",
        "{SDD_REF}", "{SDD_METADATA_REF}",
        "{IMPL_METADATA_REF}", "{ANALYSIS_REF}",
        "{BRANCH_AUDITED}", "{BRANCH_SHA_AT_AUDIT_START}",
    ]
    for ph in aud_required_placeholders:
        if not check(
            f"templates/auditor-CLAUDE.md.tpl: contains {ph}",
            ph in aud_claude_tpl,
        ):
            failures += 1

    aud_claude_rendered = render(aud_claude_tpl)
    if not check(
        "templates/auditor-CLAUDE.md.tpl: no leftover placeholders after render",
        all(ph not in aud_claude_rendered for ph in aud_required_placeholders + ["{CODEMETADATA_URL}"]),
    ):
        failures += 1
    aud_bad_refs = [
        line for line in aud_claude_rendered.splitlines()
        if "{ORCHESTRATOR_ROOT}/prompts/" in line
        or "{ORCHESTRATOR_ROOT}/skills/" in line
        or "{ORCHESTRATOR_ROOT}/docs/" in line
        or "{ORCHESTRATOR_ROOT}/schemas/" in line
    ]
    if not check(
        "templates/auditor-CLAUDE.md.tpl: no unrendered ORCHESTRATOR_ROOT refs",
        len(aud_bad_refs) == 0,
        f"leftover lines: {aud_bad_refs[:2]}" if aud_bad_refs else "",
    ):
        failures += 1
    # auditor-CLAUDE.md references absolute path to prompts/auditor.md
    if not check(
        "templates/auditor-CLAUDE.md.tpl: rendered references absolute prompts/auditor.md path",
        f"{PLACEHOLDERS['ORCHESTRATOR_ROOT']}/prompts/auditor.md" in aud_claude_rendered,
    ):
        failures += 1
    # branch convention substituted (orchestrator/<task_id> with task_id rendered)
    expected_branch = f"orchestrator/{PLACEHOLDERS['TASK_ID']}"
    if not check(
        "templates/auditor-CLAUDE.md.tpl: rendered includes literal branch "
        f"'{expected_branch}'",
        expected_branch in aud_claude_rendered,
    ):
        failures += 1
    # read-only contract MUST be stated explicitly (SDD §5 Stage 3 verification)
    if not check(
        "templates/auditor-CLAUDE.md.tpl: rendered states read-only contract explicitly",
        "read-only" in aud_claude_rendered.lower(),
    ):
        failures += 1
    # CODEX_HOME mechanism described (Stage 0 finding: no --config flag in codex 0.130.0)
    if not check(
        "templates/auditor-CLAUDE.md.tpl: rendered mentions CODEX_HOME redirect mechanism",
        "CODEX_HOME" in aud_claude_rendered,
    ):
        failures += 1
    # codex-runtime note (1c-skills not available)
    if not check(
        "templates/auditor-CLAUDE.md.tpl: rendered notes codex runtime / 1c-skills unavailability",
        "codex" in aud_claude_rendered.lower()
        and "1c-skills" in aud_claude_rendered.lower(),
    ):
        failures += 1
    # AUDIT READY single terminator (no NEEDS_REVISION / BLOCKED states)
    if not check(
        "templates/auditor-CLAUDE.md.tpl: rendered contains AUDIT READY exit signal",
        "AUDIT READY" in aud_claude_rendered,
    ):
        failures += 1
    if not check(
        "templates/auditor-CLAUDE.md.tpl: rendered does NOT mention "
        "AUDIT NEEDS_REVISION or AUDIT BLOCKED as separate terminators "
        "(verdict-split contract; severities drive verdict, not the auditor)",
        "AUDIT NEEDS_REVISION" not in aud_claude_rendered.replace("`AUDIT NEEDS_REVISION`", "")
        or aud_claude_rendered.count("AUDIT NEEDS_REVISION") <= 1,
    ):
        failures += 1
    # SHA placeholder substituted (40-hex string preserved)
    if not check(
        "templates/auditor-CLAUDE.md.tpl: rendered includes fixture branch sha",
        PLACEHOLDERS["BRANCH_SHA_AT_AUDIT_START"] in aud_claude_rendered,
    ):
        failures += 1

    if failures:
        print(f"\n{failures} check(s) failed.")
        return 1
    print("\nAll template checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
