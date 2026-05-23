# Phase 4 Stage 8 -- operator_signoff convention (extension)

**Date:** 2026-05-22
**Scope:** convention-only; no validator script in Phase 4 (Phase 5
candidate is `validate-signoff.ps1`).

## Format

Operator signoff first line MUST match exactly one of:

```
^(approved [0-9a-f]{7,40} audit=(ack|override:.+)|rejected: .+ audit=(ack|request_changes|reject|override:.+))$
```

In plain language:

| Path                      | First line                                              |
|---------------------------|---------------------------------------------------------|
| audit clean, ship         | `approved <commit> audit=ack`                           |
| audit non-ack, ship anyway| `approved <commit> audit=override:<reason>`             |
| audit clean, reject anyway| `rejected: <reason> audit=ack`                          |
| audit non-ack, also reject| `rejected: <reason> audit=<verdict>` (verdict from audit_report.computed_verdict) |

The `audit=` suffix records the verdict that was active when the
operator signed off; an `override:<reason>` MUST give a one-line
reason (no machine validation; future Phase 5 `validate-signoff.ps1`
may enforce non-empty reason length and presence of an audit_report
matching the commit).

After the first line, the file is free-form prose. The convention
applies to the FIRST LINE only.

## Grandfather clause

Pre-Phase-4 operator signoffs that do not have the `audit=` suffix
remain valid for their tasks. The convention applies to:

* new tasks audited under Phase 4
* tasks where the operator chooses to re-sign after a Phase 4 audit
  (e.g. `tasks/2026-05-22-example-erp-02/operator_signoff.txt` rewritten
  with the Phase 4 audit addendum)

## Demonstration -- `tasks/2026-05-22-example-erp-02/operator_signoff.txt`

After Phase 4 Stage 6 produced `computed_verdict = reject` driven
by AF1 (LF/CRLF mirror byte-mismatch), the operator chose the
override path. The new signoff first line is:

```
approved 0ec0e934de8da99a3ea8e648d43faa6dd4b4362e audit=override:LF-vs-CRLF drift is a core.autocrlf artifact (no semantic difference); docs mirror purpose intact and already shipped to example-erp-src master; retroactive normalize would be churn
```

The body of the file now includes a "Phase 4 audit addendum" section
that records the audit_report fields (findings, FF re-audit, MCP
calls, audit_raw refs), the override rationale, and a Phase 5
follow-up note for hardening the mirror post-condition.

Regex check: PASS.

## Why convention-only in Phase 4

SDD section 5 Stage 8 closure: "no new script; convention-only change.
Future Phase 5 may add a validate-signoff.ps1; out of Phase 4 scope."
This avoids two costs:

1. A new validator with its own gate semantics (matching
   `audit_report.computed_verdict` against the `audit=` suffix,
   resolving stale audit reports, handling pre-Phase-4 grandfather)
   would be a stage of its own with its own e2e exposure.
2. Operator signoff is human-written prose; over-machine-enforcing the
   format pushes the operator to game it.

Phase 5 may revisit once there is a second operator (e.g. CI
gatekeeper) reading these files programmatically.
