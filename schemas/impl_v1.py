"""implementer output sidecar contract -- v1 schema, standalone.

Mirrors sdd_v1.py hygiene: no <prior-iteration> imports, no schemas.sdd_v1 imports
(Citation + FFOutcome shapes are DUPLICATED, not imported, per FF2 --
keeps v1/v1/v2 schemas independent so they evolve separately).

Consumed by scripts/_python/validate_impl.py (Stage 5) and produced by
the implementer L3 phase (Stage 4 spawn).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_FF_KEYS = ("FF1", "FF2", "FF3", "FF4", "FF5", "FF6", "FF7", "FF8")
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_BRANCH_RE = re.compile(r"^orchestrator/[A-Za-z0-9._/-]+$")


def _non_empty(value: str, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value.strip()


class ArtifactModel(BaseModel):
    """Base for all sidecar models. Strict: extra fields rejected."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Citation(ArtifactModel):
    """Evidence pointer inside an impl claim.

    Phase 3 adds "sdd_metadata" + "sdd" to the source enum compared to
    sdd_v1.Citation: implementer carries forward findings from
    sdd_metadata.json and sdd.md, and must cite section/key paths into
    them (e.g. "sdd_metadata.json#stages.2", "sdd.md#5.4-stage-4").
    """

    source: Literal[
        "mcp", "code", "rlm", "raw_artefact", "analysis_report", "sdd_metadata", "sdd"
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
        return self


class FFOutcome(ArtifactModel):
    """Result of one FF1-FF8 self-audit row. Duplicated from sdd_v1."""

    status: Literal["pass", "na", "fail"]
    note: str

    @field_validator("note")
    @classmethod
    def _note_non_empty(cls, value: str) -> str:
        return _non_empty(value, "FFOutcome.note")


class ImplCommit(ArtifactModel):
    """One commit on the orchestrator/<task_id> branch."""

    sha: str
    subject: str
    files: list[str] = Field(min_length=1)
    stage_ref: str

    @field_validator("sha")
    @classmethod
    def _sha_shape(cls, value: str) -> str:
        if not _SHA40_RE.match(value):
            raise ValueError(
                f"ImplCommit.sha must match {_SHA40_RE.pattern!r} (got: {value!r})"
            )
        return value

    @field_validator("subject", "stage_ref")
    @classmethod
    def _str_non_empty(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))

    @field_validator("files")
    @classmethod
    def _files_non_empty(cls, value: list[str]) -> list[str]:
        return [_non_empty(item, "ImplCommit.files[*]") for item in value]


class MirrorCheck(ArtifactModel):
    """Mirror byte-identity record with CRLF/LF normalization.

    Phase 5 Group A. When a ValidationAttempt is a mirror compare
    (e.g. "cmp docs/orchestrator/<task_id>/<file>.md vs operator-local
    artefact"), the L3 agent populates this sub-model with BOTH raw and
    normalized SHA256 for each side, plus derived match booleans.

    Equality decision uses `normalized_match`. `raw_match` is kept for
    diagnostic so the operator can distinguish a real semantic mismatch
    (raw_match=false + normalized_match=false) from a pure autocrlf
    artefact (raw_match=false + normalized_match=true). The helper that
    fills these fields lives at `scripts/_python/_hash_normalized.py`.
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
        # Raw equality implies normalized equality (raw bytes equal ->
        # normalize_eol output is also equal). Catch corrupt fixtures.
        if raw_eq and not norm_eq:
            raise ValueError(
                "MirrorCheck: raw_match=true but normalized_match=false "
                "(impossible -- raw equality implies normalized equality)"
            )
        return self


class ValidationAttempt(ArtifactModel):
    """Best-effort verification step result.

    `mirror_check` is OPTIONAL (Phase 5 additive field). Populate it when
    the attempt is a mirror byte-identity compare; otherwise leave None.
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


class ImplOpenQuestion(ArtifactModel):
    id: str
    severity: Literal["info", "decision", "blocker"]
    question: str
    surface: str

    @field_validator("id", "question", "surface")
    @classmethod
    def _str_non_empty(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))


class DiffBaseline(ArtifactModel):
    """Before/after snapshots for Gate B sanity (no-write-to-Orchestrator)."""

    before_sha: str
    after_branch_sha: str
    orchestrator_before: str
    orchestrator_after: str

    @field_validator("before_sha", "after_branch_sha")
    @classmethod
    def _sha_shape(cls, value: str, info: Any) -> str:
        if not _SHA40_RE.match(value):
            raise ValueError(
                f"{info.field_name} must match {_SHA40_RE.pattern!r} (got: {value!r})"
            )
        return value


class ImplementationResult(ArtifactModel):
    """implementer terminal output sidecar. Consumed by validate_impl.py."""

    schema_version: Literal["v1"]
    task_id: str
    sdd_metadata_ref: Literal["sdd_metadata.json"]
    sdd_ref: Literal["sdd.md"]
    project_id: str
    path_local: str
    extra_writable_dir: str = ""
    gitea_remote_url: str
    branch_name: str
    commits: list[ImplCommit] = Field(min_length=1)
    files_changed: list[str] = Field(min_length=1)
    validations_attempted: list[ValidationAttempt] = Field(default_factory=list)
    open_questions: list[ImplOpenQuestion] = Field(default_factory=list)
    refusals: list[str] = Field(default_factory=list)
    diff_baseline: DiffBaseline
    ff_self_audit: dict[str, FFOutcome]
    citations_used: list[Citation] = Field(min_length=1)
    status: Literal["ready", "needs_revision", "blocked"]
    failures: list[str] = Field(default_factory=list)
    audit_inputs: list[str] = Field(default_factory=list)
    self_review_notes: str

    @field_validator(
        "task_id",
        "project_id",
        "path_local",
        "gitea_remote_url",
        "self_review_notes",
    )
    @classmethod
    def _str_non_empty(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))

    @field_validator("branch_name")
    @classmethod
    def _branch_shape(cls, value: str) -> str:
        if not _BRANCH_RE.match(value):
            raise ValueError(
                f"branch_name must match {_BRANCH_RE.pattern!r} (got: {value!r})"
            )
        return value

    @field_validator("files_changed")
    @classmethod
    def _files_non_empty(cls, value: list[str]) -> list[str]:
        return [_non_empty(item, "files_changed[*]") for item in value]

    @field_validator("refusals")
    @classmethod
    def _refusal_items_non_empty(cls, value: list[str]) -> list[str]:
        return [_non_empty(item, "refusals[*]") for item in value]

    @field_validator("failures", "audit_inputs")
    @classmethod
    def _opt_list_items_non_empty(cls, value: list[str], info: Any) -> list[str]:
        return [_non_empty(item, str(info.field_name) + "[*]") for item in value]

    @model_validator(mode="after")
    def _ff_audit_complete(self) -> "ImplementationResult":
        expected = set(_FF_KEYS)
        got = set(self.ff_self_audit.keys())
        missing = expected - got
        extra = got - expected
        if missing:
            raise ValueError(
                f"ff_self_audit missing keys: {sorted(missing)}; "
                f"required: {sorted(expected)}"
            )
        if extra:
            raise ValueError(
                f"ff_self_audit has unknown keys: {sorted(extra)}; "
                f"only {sorted(expected)} allowed"
            )
        return self

    @model_validator(mode="after")
    def _status_failures_consistent(self) -> "ImplementationResult":
        if self.status == "ready":
            if self.failures:
                raise ValueError(
                    "status='ready' requires failures=[] (got "
                    f"{len(self.failures)} entries)"
                )
            for v in self.validations_attempted:
                if v.mandatory and v.status != "ok":
                    raise ValueError(
                        "status='ready' requires every mandatory validation to "
                        f"have status='ok'; '{v.name}' has status='{v.status}'"
                    )
        else:
            if not self.failures:
                raise ValueError(
                    f"status='{self.status}' requires failures non-empty"
                )
        return self


def read_impl_metadata(artifact_dir: Path) -> ImplementationResult | None:
    """Load impl_metadata.json. Returns None if absent. Raises on malformed."""
    path = Path(artifact_dir) / "impl_metadata.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return ImplementationResult.model_validate(data)


__all__ = [
    "Citation",
    "FFOutcome",
    "ImplCommit",
    "MirrorCheck",
    "ValidationAttempt",
    "ImplOpenQuestion",
    "DiffBaseline",
    "ImplementationResult",
    "read_impl_metadata",
]
