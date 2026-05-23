"""auditor output sidecar contract -- v1 schema, standalone.

Mirrors impl_v1.py + sdd_v1.py hygiene: no <prior-iteration> imports, no
schemas.sdd_v1 / schemas.impl_v1 imports (Citation + FFOutcome +
ValidationAttempt shapes are DUPLICATED, not imported, per FF2 --
keeps the v1 schemas independent so they evolve separately).

Consumed by scripts/_python/validate_audit.py (Stage 5) and produced by
the auditor L3 phase (Stage 4 spawn). The auditor runs under codex
runtime; the schema is consumed by python tooling on the Orchestrator
side regardless of runtime.

Severity-to-verdict computation is NOT in this schema -- it lives in
validate_audit.py. The schema stores the codex-set `recommended_verdict`
(advisory) alongside per-finding severities; the machine-computed
verdict supersedes recommendation downstream.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_FF_KEYS = ("FF1", "FF2", "FF3", "FF4", "FF5", "FF6", "FF7", "FF8")
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA12_RE = re.compile(r"^[0-9a-f]{12}$")
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_BRANCH_RE = re.compile(r"^orchestrator/[A-Za-z0-9._/-]+$")
_FINDING_ID_RE = re.compile(r"^AF[0-9]+$")


def _non_empty(value: str, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value.strip()


class ArtifactModel(BaseModel):
    """Base for all sidecar models. Strict: extra fields rejected."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Citation(ArtifactModel):
    """Evidence pointer inside an audit claim.

    Phase 4 extends the source enum compared to impl_v1.Citation:
    auditor cites into impl_metadata.json and into its own audit_raw/
    directory (the MCP-query dump tree). impl_metadata refs use
    'impl_metadata.json#...' anchors; audit_raw refs start with
    'audit_raw/'.
    """

    source: Literal[
        "mcp",
        "code",
        "rlm",
        "raw_artefact",
        "analysis_report",
        "sdd_metadata",
        "sdd",
        "impl_metadata",
        "audit_raw",
    ]
    ref: str
    excerpt: str | None = None

    @field_validator("ref")
    @classmethod
    def _ref_non_empty(cls, value: str) -> str:
        return _non_empty(value, "Citation.ref")

    @model_validator(mode="after")
    def _ref_shape(self) -> "Citation":
        if self.source == "analysis_report" and not self.ref.startswith(
            "analysis_report.json#"
        ):
            raise ValueError(
                "Citation(source='analysis_report').ref must start with "
                f"'analysis_report.json#' (got: {self.ref!r})"
            )
        if self.source == "sdd_metadata" and not self.ref.startswith(
            "sdd_metadata.json#"
        ):
            raise ValueError(
                "Citation(source='sdd_metadata').ref must start with "
                f"'sdd_metadata.json#' (got: {self.ref!r})"
            )
        if self.source == "sdd" and not self.ref.startswith("sdd.md#"):
            raise ValueError(
                "Citation(source='sdd').ref must start with "
                f"'sdd.md#' (got: {self.ref!r})"
            )
        if self.source == "impl_metadata" and not self.ref.startswith(
            "impl_metadata.json#"
        ):
            raise ValueError(
                "Citation(source='impl_metadata').ref must start with "
                f"'impl_metadata.json#' (got: {self.ref!r})"
            )
        if self.source == "audit_raw" and not self.ref.startswith("audit_raw/"):
            raise ValueError(
                "Citation(source='audit_raw').ref must start with "
                f"'audit_raw/' (got: {self.ref!r})"
            )
        return self


class FFOutcome(ArtifactModel):
    """Result of one FF1-FF8 re-audit row. Duplicated from impl_v1/sdd_v1."""

    status: Literal["pass", "na", "fail"]
    note: str

    @field_validator("note")
    @classmethod
    def _note_non_empty(cls, value: str) -> str:
        return _non_empty(value, "FFOutcome.note")


class MirrorCheck(ArtifactModel):
    """Mirror byte-identity record with CRLF/LF normalization. Duplicated from impl_v1.

    Phase 5 Group A. When a re-verification attempt is a mirror compare,
    the auditor populates this sub-model with BOTH raw and normalized
    SHA256 for each side, plus derived match booleans. Equality decision
    uses `normalized_match`; `raw_match` is diagnostic only.

    Mirrors `schemas.impl_v1.MirrorCheck` (DUPLICATED per FF2 -- the v1
    schemas stay independent and evolve separately).
    """

    local_path: str
    local_raw_sha256: str
    local_normalized_sha256: str
    local_raw_bytes: int = Field(ge=0)
    local_normalized_bytes: int = Field(ge=0)
    counterpart_path: str
    counterpart_raw_sha256: str
    counterpart_normalized_sha256: str
    counterpart_raw_bytes: int = Field(ge=0)
    counterpart_normalized_bytes: int = Field(ge=0)
    raw_match: bool
    normalized_match: bool

    @field_validator("local_path", "counterpart_path")
    @classmethod
    def _path_non_empty(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))

    @field_validator(
        "local_raw_sha256",
        "local_normalized_sha256",
        "counterpart_raw_sha256",
        "counterpart_normalized_sha256",
    )
    @classmethod
    def _sha256_shape(cls, value: str, info: Any) -> str:
        if not _SHA256_HEX_RE.match(value):
            raise ValueError(
                f"{info.field_name} must match {_SHA256_HEX_RE.pattern!r} "
                f"(got: {value!r})"
            )
        return value

    @model_validator(mode="after")
    def _derived_consistent(self) -> "MirrorCheck":
        raw_eq = self.local_raw_sha256 == self.counterpart_raw_sha256
        norm_eq = (
            self.local_normalized_sha256 == self.counterpart_normalized_sha256
        )
        if raw_eq != self.raw_match:
            raise ValueError(
                "MirrorCheck.raw_match must equal the raw_sha256 equality "
                f"(raw_match={self.raw_match}, raw_sha256 equality={raw_eq})"
            )
        if norm_eq != self.normalized_match:
            raise ValueError(
                "MirrorCheck.normalized_match must equal the "
                "normalized_sha256 equality "
                f"(normalized_match={self.normalized_match}, "
                f"normalized_sha256 equality={norm_eq})"
            )
        if raw_eq and not norm_eq:
            raise ValueError(
                "MirrorCheck: raw_match=true but normalized_match=false "
                "(impossible -- raw equality implies normalized equality)"
            )
        return self


class ValidationAttempt(ArtifactModel):
    """Re-verification step result. Duplicated from impl_v1.

    Auditor records one entry per impl_metadata.validations_attempted[v]
    where v.mandatory==true (validate_audit Gate D enforces coverage).

    `mirror_check` is OPTIONAL (Phase 5 additive field). Populate it when
    the re-verification is a mirror byte-identity compare; otherwise None.
    """

    name: str
    status: Literal["ok", "fail", "skipped", "unavailable"]
    diagnostic: str
    mandatory: bool
    mirror_check: MirrorCheck | None = None

    @field_validator("name", "diagnostic")
    @classmethod
    def _str_non_empty(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))


class AuditFinding(ArtifactModel):
    """One auditor finding. Severity drives validate_audit's computed verdict."""

    id: str
    category: Literal[
        "ff_audit_disagreement",
        "dod_post_regex_mismatch",
        "out_of_scope_edit",
        "refuse_violation",
        "missing_verification",
        "scope_mismatch",
        "other",
    ]
    severity: Literal["info", "decision", "blocker"]
    surface: Literal["sdd", "impl", "both", "process"]
    description: str
    evidence: str
    cross_reference: str | None = None

    @field_validator("id")
    @classmethod
    def _id_shape(cls, value: str) -> str:
        if not _FINDING_ID_RE.match(value):
            raise ValueError(
                f"AuditFinding.id must match {_FINDING_ID_RE.pattern!r} "
                f"(got: {value!r})"
            )
        return value

    @field_validator("description", "evidence")
    @classmethod
    def _str_non_empty(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))


class McpQuery(ArtifactModel):
    """Audit trail entry: one MCP call the auditor issued.

    raw_path points at the audit_raw/<server>/r<round>-q<idx>-<sha12>.json
    file (relative to task_root). args_sha12 / response_sha12 are 12-hex
    fingerprints; full payloads live in the raw_path file.
    """

    server: str
    tool: str
    args_sha12: str
    response_sha12: str
    raw_path: str

    @field_validator("server", "tool", "raw_path")
    @classmethod
    def _str_non_empty(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))

    @field_validator("args_sha12", "response_sha12")
    @classmethod
    def _sha12_shape(cls, value: str, info: Any) -> str:
        if not _SHA12_RE.match(value):
            raise ValueError(
                f"{info.field_name} must match {_SHA12_RE.pattern!r} "
                f"(got: {value!r})"
            )
        return value


class AuditReport(ArtifactModel):
    """auditor terminal output sidecar. Consumed by validate_audit.py."""

    schema_version: Literal["v1"]
    task_id: str
    sdd_metadata_ref: Literal["sdd_metadata.json"]
    sdd_ref: Literal["sdd.md"]
    impl_metadata_ref: Literal["impl_metadata.json"]
    analysis_ref: Literal["analysis_report.json"]
    project_id: str
    path_local: str
    extra_writable_dir: str = ""
    branch_audited: str
    branch_sha_audited: str
    findings: list[AuditFinding] = Field(default_factory=list)
    ff_re_audit: dict[str, FFOutcome]
    re_verifications_attempted: list[ValidationAttempt] = Field(default_factory=list)
    mcp_queries_issued: list[McpQuery] = Field(default_factory=list)
    recommended_verdict: Literal["ack", "request_changes", "reject"]
    citations: list[Citation] = Field(min_length=1)
    audit_started_at: str
    audit_ended_at: str
    audit_self_review_notes: str

    @field_validator(
        "task_id",
        "project_id",
        "path_local",
        "audit_started_at",
        "audit_ended_at",
        "audit_self_review_notes",
    )
    @classmethod
    def _str_non_empty(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))

    @field_validator("branch_audited")
    @classmethod
    def _branch_shape(cls, value: str) -> str:
        if not _BRANCH_RE.match(value):
            raise ValueError(
                f"branch_audited must match {_BRANCH_RE.pattern!r} (got: {value!r})"
            )
        return value

    @field_validator("branch_sha_audited")
    @classmethod
    def _sha_shape(cls, value: str) -> str:
        if not _SHA40_RE.match(value):
            raise ValueError(
                f"branch_sha_audited must match {_SHA40_RE.pattern!r} "
                f"(got: {value!r})"
            )
        return value

    @model_validator(mode="after")
    def _ff_re_audit_complete(self) -> "AuditReport":
        expected = set(_FF_KEYS)
        got = set(self.ff_re_audit.keys())
        missing = expected - got
        extra = got - expected
        if missing:
            raise ValueError(
                f"ff_re_audit missing keys: {sorted(missing)}; "
                f"required: {sorted(expected)}"
            )
        if extra:
            raise ValueError(
                f"ff_re_audit has unknown keys: {sorted(extra)}; "
                f"only {sorted(expected)} allowed"
            )
        return self

    @model_validator(mode="after")
    def _finding_ids_unique(self) -> "AuditReport":
        ids = [f.id for f in self.findings]
        if len(ids) != len(set(ids)):
            seen: set[str] = set()
            dupes: list[str] = []
            for fid in ids:
                if fid in seen:
                    dupes.append(fid)
                seen.add(fid)
            raise ValueError(
                f"AuditReport.findings has duplicate ids: {sorted(set(dupes))}"
            )
        return self


def read_audit_report(artifact_dir: Path) -> AuditReport | None:
    """Load audit_report.json. Returns None if absent. Raises on malformed."""
    path = Path(artifact_dir) / "audit_report.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return AuditReport.model_validate(data)


__all__ = [
    "Citation",
    "FFOutcome",
    "MirrorCheck",
    "ValidationAttempt",
    "AuditFinding",
    "McpQuery",
    "AuditReport",
    "read_audit_report",
]
