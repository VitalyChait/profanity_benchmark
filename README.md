# YouthEscalateBench

Dynamic multi-turn youth-safeguarding benchmark for causal moderation detection.

## Quick start

```bash
pip install -e ".[dev]"
yeb stages
yeb e2e                              # miniature fixture pipeline
yeb export-schemas                   # JSON Schema contracts
yeb audit-sources                    # Phase 1 gate (fails until licenses approved)
pytest tests -v
```

## Project structure

```
configs/                 Versioned YAML configs and source registry
docs/                    Threat model, IRB draft, annotation guidelines
src/youth_escalate_bench/  Schemas, pipeline stages, adapters, metrics
tests/                   28 pytest tests including E2E
TASKS.md                 Structured execution plan with phase gates
plan.md                  Canonical benchmark specification
```

## Pipeline

`source_audit → ingest → redact → thread → transform → annotate_export → split → evaluate`

Each stage emits `manifest.json` with SHA-256 hashes.

## Current status

| Phase | Status |
|-------|--------|
| 0 Repository foundation | complete |
| 1 Governance | docs + tooling ready; **license/IRB sign-off pending** |
| 2 Pilot | annotation tooling ready; data collection blocked on Phase 1 |
| 3–6 | core stages scaffolded; production scale blocked on data + annotation |

See [`TASKS.md`](TASKS.md) for full subtask tracker.

## License

Code: MIT (see LICENSE). Data loaders enforce per-source restrictions in `configs/source_registry.yaml`.
