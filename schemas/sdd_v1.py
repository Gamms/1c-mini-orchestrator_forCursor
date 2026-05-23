"""sdd_writer output sidecar contract -- v1 schema, standalone.

Mirrors analysis_v2.py hygiene: no <prior-iteration> imports, extra="forbid",
strict by default. Citation shape is duplicated (not imported) from
analysis_v2 because the source enum here adds "analysis_report" — keep
the schemas independent so v2/v1 can evolve separately.

Consumed by scripts/_python/validate_sdd.py (Stage 5) and produced by
the sdd_writer L3 phase (Stage 4 spawn).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_FF_KEYS = ("FF1", "FF2", "FF3", "FF4", "FF5", "FF6", "FF7", "FF8")


def _non_empty(value: str, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value.strip()


class ArtifactModel(BaseModel):
    """Base for all sidecar models. Strict: extra fields rejected."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Citation(ArtifactModel):
    """Evidence pointer inside an SDD claim.

    Phase 2 adds "analysis_report" to the source enum compared to v2:
    sdd_writer carries forward findings from analysis_report.json and
    must cite section/key paths into it (e.g. "analysis_report.json#tool_evidence").
    """

    source: Literal["mcp", "code", "rlm", "raw_artefact", "analysis_report"]
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
        return self


class FFOutcome(ArtifactModel):
    """Result of one FF1-FF8 self-audit row."""

    status: Literal["pass", "na", "fail"]
    note: str

    @field_validator("note")
    @classmethod
    def _note_non_empty(cls, value: str) -> str:
        return _non_empty(value, "FFOutcome.note")


class Deliverable(ArtifactModel):
    """One stage deliverable: bare file path + optional human description.

    Tightened in 2026-05-22 per Phase 3 IOQ2 resolution: prior shape was
    `list[str]` with descriptive English suffixes baked into the string
    (e.g. "tasks/<id>/x.md exists; markdown table with N rows"). That
    broke validate_impl Gate D, which compares branch-changed paths
    literally against deliverable strings. Splitting path from
    description restores Gate D correctness without losing human prose.
    """

    path: str
    description: str | None = None

    @field_validator("path")
    @classmethod
    def _path_non_empty(cls, value: str) -> str:
        cleaned = _non_empty(value, "Deliverable.path")
        if "\n" in cleaned or "\r" in cleaned:
            raise ValueError("Deliverable.path must not contain line breaks")
        return cleaned

    @field_validator("description")
    @classmethod
    def _desc_strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped


class SDDStage(ArtifactModel):
    id: str
    title: str
    deliverables: list[Deliverable] = Field(min_length=1)
    verifications: list[str] = Field(min_length=1)
    failure_modes: list[str] = Field(min_length=1)

    @field_validator("id", "title")
    @classmethod
    def _str_non_empty(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))

    @field_validator("verifications", "failure_modes")
    @classmethod
    def _items_non_empty(cls, value: list[str], info: Any) -> list[str]:
        cleaned = [_non_empty(item, str(info.field_name)) for item in value]
        return cleaned


class SDDOpenQuestion(ArtifactModel):
    id: str
    severity: Literal["info", "decision", "blocker"]
    question: str
    recommendation: str

    @field_validator("id", "question", "recommendation")
    @classmethod
    def _str_non_empty(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))


class SDDRisk(ArtifactModel):
    summary: str
    mitigation: str

    @field_validator("summary", "mitigation")
    @classmethod
    def _str_non_empty(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))


class SDDMetadata(ArtifactModel):
    """sdd_writer terminal output sidecar. Consumed by validate_sdd.py."""

    schema_version: Literal["v1"]
    task_id: str
    analysis_report_ref: Literal["analysis_report.json"]
    sdd_path: Literal["sdd.md"]
    task_size: Literal["XS", "S", "M", "L", "XL"]
    stages: list[SDDStage] = Field(default_factory=list)
    open_questions: list[SDDOpenQuestion] = Field(default_factory=list)
    risks: list[SDDRisk] = Field(default_factory=list)
    refusals: list[str] = Field(default_factory=list)
    dod_pre: list[str] = Field(min_length=1)
    dod_post: list[str] = Field(min_length=1)
    ff_self_audit: dict[str, FFOutcome]
    citations_used: list[Citation] = Field(min_length=1)
    self_review_notes: str

    @field_validator("task_id", "self_review_notes")
    @classmethod
    def _str_non_empty(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))

    @field_validator("refusals")
    @classmethod
    def _refusal_items_non_empty(cls, value: list[str]) -> list[str]:
        return [_non_empty(item, "refusals[*]") for item in value]

    @field_validator("dod_pre", "dod_post")
    @classmethod
    def _dod_items_non_empty(cls, value: list[str], info: Any) -> list[str]:
        return [_non_empty(item, str(info.field_name)) for item in value]

    @model_validator(mode="after")
    def _ff_audit_complete(self) -> "SDDMetadata":
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


def read_sdd_metadata(artifact_dir: Path) -> SDDMetadata | None:
    """Load sdd_metadata.json. Returns None if absent. Raises on malformed."""
    path = Path(artifact_dir) / "sdd_metadata.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return SDDMetadata.model_validate(data)


__all__ = [
    "Citation",
    "Deliverable",
    "FFOutcome",
    "SDDStage",
    "SDDOpenQuestion",
    "SDDRisk",
    "SDDMetadata",
    "read_sdd_metadata",
]
