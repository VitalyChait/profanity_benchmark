"""Tests for source registry and Phase 1 audit gate."""

from pathlib import Path

from youth_escalate_bench.source_registry import (
    SourceRecord,
    SourceRegistry,
    SourceStatus,
    audit_gate_passes,
    load_registry,
)


def test_load_default_registry():
    registry_path = Path("configs/source_registry.yaml")
    registry = load_registry(registry_path)
    assert len(registry.sources) >= 5


def test_audit_gate_fails_with_pending_sources():
    registry = SourceRegistry(
        sources=[
            SourceRecord(
                source_id="test",
                name="Test",
                owner="owner",
                license="MIT",
                redistribution_rights="allowed",
                status=SourceStatus.PENDING_REVIEW,
            )
        ]
    )
    passed, failures = audit_gate_passes(registry)
    assert not passed
    assert any("pending_review" in f for f in failures)


def test_audit_gate_passes_approved_source():
    registry = SourceRegistry(
        sources=[
            SourceRecord(
                source_id="test",
                name="Test",
                owner="owner",
                license="MIT",
                redistribution_rights="allowed",
                status=SourceStatus.APPROVED,
            )
        ]
    )
    passed, failures = audit_gate_passes(registry)
    assert passed
    assert failures == []


def test_cli_audit_sources_passes_on_default_registry():
    """Default registry has approved sources — gate must pass."""
    registry = load_registry(Path("configs/source_registry.yaml"))
    passed, failures = audit_gate_passes(registry)
    assert passed
    assert failures == []
