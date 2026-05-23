"""Analyst output contract — v2 schema, standalone.

Inlined minimal subset of <prior-iteration-v3> schemas (audit C4): no <prior-iteration> imports,
no ARTIFACT_MODELS global, no SDDArtifact/SDDStage/TaskPacket.
AIProducedArtifact (extra="ignore") collapsed into ArtifactModel
(extra="forbid") — strict by default; we want garbage to fail loud.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_RAW_REF_RE = re.compile(
    r"^analysis_raw/[A-Za-z0-9._-]+/r\d+-q\d+-[a-f0-9]{12}\.json$"
)

_LINE_RANGE_RE = re.compile(r"^L:\d+(-\d+)?$")


def _non_empty(value: str, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value.strip()


class ArtifactModel(BaseModel):
    """Base for all artifact models. Strict: extra fields rejected."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Citation(ArtifactModel):
    """A single evidence pointer.

    Every Finding, every RelevantFile carries >=1 (Pydantic min_length=1).
    OpenQuestion.citations may be empty when the question is meta
    (e.g. "is the goal worth pursuing?").
    """

    source: Literal["mcp", "code", "rlm", "raw_artefact"]
    ref: str
    excerpt: str | None = None

    @field_validator("ref")
    @classmethod
    def _ref_non_empty(cls, value: str) -> str:
        return _non_empty(value, "Citation.ref")


class ToolQuery(ArtifactModel):
    """One MCP tool call. raw_result_ref is repo-relative under task_root."""

    round: int = Field(ge=1, le=10)
    tool: str
    query: str
    raw_result_ref: str
    summary: str
    leads_to: list[str] = Field(default_factory=list)

    @field_validator("tool", "query", "summary")
    @classmethod
    def _str_non_empty(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))

    @field_validator("raw_result_ref")
    @classmethod
    def _validate_raw_ref(cls, value: str) -> str:
        stripped = value.strip()
        if not _RAW_REF_RE.match(stripped):
            raise ValueError(
                "raw_result_ref must match "
                "'analysis_raw/<server>/r<round>-q<idx>-<sha12>.json' "
                f"(got: {value!r})."
            )
        return stripped


class ToolEvidence(ArtifactModel):
    """Per-server evidence pack. Distinct round count enforced 2 <= N <= 4."""

    server: str
    queries: list[ToolQuery] = Field(min_length=1)

    @field_validator("server")
    @classmethod
    def _server_non_empty(cls, value: str) -> str:
        return _non_empty(value, "ToolEvidence.server")

    @model_validator(mode="after")
    def _validate_rounds(self) -> "ToolEvidence":
        distinct_rounds = {q.round for q in self.queries}
        if not 2 <= len(distinct_rounds) <= 4:
            raise ValueError(
                f"ToolEvidence.queries must span 2-4 distinct rounds "
                f"(server={self.server!r}, got rounds={sorted(distinct_rounds)})"
            )
        prefix = f"analysis_raw/{self.server}/"
        seen: set[str] = set()
        for q in self.queries:
            if not q.raw_result_ref.startswith(prefix):
                raise ValueError(
                    f"ToolQuery.raw_result_ref must live under {prefix!r}: "
                    f"{q.raw_result_ref!r}"
                )
            filename = q.raw_result_ref[len(prefix):]
            if not filename.startswith(f"r{q.round}-"):
                raise ValueError(
                    f"raw_result_ref filename round prefix must match "
                    f"ToolQuery.round={q.round}: {q.raw_result_ref!r}"
                )
            if q.raw_result_ref in seen:
                raise ValueError(
                    f"raw_result_ref duplicated within server={self.server!r}: "
                    f"{q.raw_result_ref!r}"
                )
            seen.add(q.raw_result_ref)
        return self


class RelevantFile(ArtifactModel):
    path: str
    line_range: str | None = None
    why_relevant: str
    citations: list[Citation] = Field(min_length=1)

    @field_validator("line_range")
    @classmethod
    def _validate_line_range(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _LINE_RANGE_RE.match(value):
            raise ValueError(
                f"line_range must be 'L:N' or 'L:N-M' (got: {value!r})"
            )
        return value

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("RelevantFile.path must not be empty")
        if (
            stripped.startswith("/")
            or stripped.startswith("\\")
            or Path(stripped).is_absolute()
            or (len(stripped) >= 2 and stripped[1] == ":")
        ):
            raise ValueError(f"RelevantFile.path must be repo-relative: {value}")
        if any(part == ".." for part in Path(stripped).parts):
            raise ValueError(f"RelevantFile.path must stay within repo: {value}")
        return stripped

    @field_validator("why_relevant")
    @classmethod
    def _why_non_empty(cls, value: str) -> str:
        return _non_empty(value, "RelevantFile.why_relevant")


class Finding(ArtifactModel):
    kind: Literal["pattern", "pitfall", "constraint", "opportunity"]
    summary: str
    citations: list[Citation] = Field(min_length=1)

    @field_validator("summary")
    @classmethod
    def _summary_non_empty(cls, value: str) -> str:
        return _non_empty(value, "Finding.summary")


class OpenQuestion(ArtifactModel):
    """Escalation package for the operator."""

    severity: Literal["info", "decision", "blocker"]
    question: str
    what_i_found_so_far: str
    what_i_need_from_operator: str
    citations: list[Citation] = Field(default_factory=list)

    @field_validator("question", "what_i_found_so_far", "what_i_need_from_operator")
    @classmethod
    def _non_empty_field(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))


class AnalysisReport(ArtifactModel):
    """Analyst terminal output. Consumed by sdd_writer in Phase 2."""

    schema_version: Literal["v2"]
    task_id: str
    goal_understanding: str
    tool_evidence: dict[str, ToolEvidence]
    relevant_files: list[RelevantFile]
    existing_patterns: list[Finding] = Field(default_factory=list)
    pitfalls_found: list[Finding] = Field(default_factory=list)
    constraints_discovered: list[Finding] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    self_review_notes: str

    @field_validator("task_id", "goal_understanding", "self_review_notes")
    @classmethod
    def _non_empty_field(cls, value: str, info: Any) -> str:
        return _non_empty(value, str(info.field_name))

    @model_validator(mode="after")
    def _evidence_keys_match_server(self) -> "AnalysisReport":
        for key, ev in self.tool_evidence.items():
            if ev.server != key:
                raise ValueError(
                    f"tool_evidence key {key!r} must equal ToolEvidence.server "
                    f"{ev.server!r}"
                )
        return self


def read_analysis_report(artifact_dir: Path) -> AnalysisReport | None:
    """Load analysis_report.json. Returns None if absent. Raises on malformed."""
    path = Path(artifact_dir) / "analysis_report.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return AnalysisReport.model_validate(data)


__all__ = [
    "Citation",
    "ToolQuery",
    "ToolEvidence",
    "RelevantFile",
    "Finding",
    "OpenQuestion",
    "AnalysisReport",
    "read_analysis_report",
]
