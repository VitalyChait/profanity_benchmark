"""Source registry for license and provenance audit (plan.md Section 3)."""

from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field


class SourceStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    DENIED = "denied"
    EXCLUDED = "excluded"


class SourceRecord(BaseModel):
    source_id: str
    name: str
    owner: str
    version: str | None = None
    url: str | None = None
    license: str | None = None
    terms_url: str | None = None
    consent_basis: str | None = None
    redistribution_rights: str | None = None
    deletion_process: str | None = None
    age_evidence: str | None = None
    pii_risk: str | None = None
    intended_use: str | None = None
    allowed_artifacts: Annotated[list[str], Field(default_factory=list)]
    status: SourceStatus = SourceStatus.PENDING_REVIEW
    review_date: date | None = None
    reviewer: str | None = None
    notes: str | None = None
    conversation_quota: int | None = None
    fallback_if_denied: str | None = None


class SourceRegistry(BaseModel):
    registry_version: str = "1.0.0"
    last_updated: date | None = None
    sources: Annotated[list[SourceRecord], Field(default_factory=list)]

    def coverage_pct(self) -> float:
        if not self.sources:
            return 0.0
        documented = sum(
            1 for s in self.sources if s.license and s.status != SourceStatus.PENDING_REVIEW
        )
        return documented / len(self.sources) * 100

    def pending_sources(self) -> list[SourceRecord]:
        return [s for s in self.sources if s.status == SourceStatus.PENDING_REVIEW]

    def approved_sources(self) -> list[SourceRecord]:
        return [s for s in self.sources if s.status == SourceStatus.APPROVED]


def load_registry(path: Path) -> SourceRegistry:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return SourceRegistry.model_validate(data)


def save_registry(registry: SourceRegistry, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = registry.model_dump(mode="json")
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)


def audit_gate_passes(registry: SourceRegistry) -> tuple[bool, list[str]]:
    """Gate 1: no source enters ingest without documented legal status."""
    failures: list[str] = []
    for source in registry.sources:
        if source.status in (SourceStatus.PENDING_REVIEW, SourceStatus.DENIED):
            failures.append(f"{source.source_id}: status={source.status}")
        if not source.license:
            failures.append(f"{source.source_id}: missing license")
        if not source.redistribution_rights:
            failures.append(f"{source.source_id}: missing redistribution_rights")
    return len(failures) == 0, failures
