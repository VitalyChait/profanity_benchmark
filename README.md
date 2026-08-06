# YouthEscalateBench

Dynamic multi-turn youth-safeguarding benchmark for causal moderation detection.

## Quick start

```bash
pip install -e ".[dev]"
yeb e2e                              # miniature fixture pipeline (37 tests)
yeb export-schemas                   # JSON Schema contracts
yeb audit-sources                    # Phase 1 gate (fails until licenses approved)
yeb serve --port 8080                # /predict evaluator (baseline default)
pytest tests -v
```

## Pipeline

`source_audit → ingest → redact → thread → sample → stage_generate → transform →
annotate_export → adjudicate → split → evaluate → report`

```bash
yeb run --stage evaluate --config configs/stages/evaluate.yaml
yeb run --stage stage_generate --config configs/stages/stage_generate.yaml
yeb run --stage adjudicate --config configs/stages/adjudicate.yaml --input-dir data/annotations
```

## Baselines (bundled)

| Scorer | Description |
|--------|-------------|
| `lexicon_raw` | Raw profanity lexicon matcher |
| `lexicon_normalized` | Normalized text lexicon |
| `char_ngram_tfidf` | Char n-gram weighted scorer |
| `lexicon_full_context` | Lexicon over full causal prefix |

## Evaluator container

```bash
docker build -f docker/evaluator/Dockerfile -t yeb-evaluator .
docker run --network none -p 8080:8080 yeb-evaluator
# POST http://localhost:8080/predict with InferenceRequest JSON
```

## Documentation

| Doc | Purpose |
|-----|---------|
| [`TASKS.md`](TASKS.md) | Phase tracker |
| [`docs/benchmark_card.md`](docs/benchmark_card.md) | NeurIPS E&D summary |
| [`docs/datasheet.md`](docs/datasheet.md) | Datasheet |
| [`docs/preregistration.md`](docs/preregistration.md) | OSF prereg draft |
| [`metadata/croissant.json`](metadata/croissant.json) | Croissant metadata |

## Status

Engineering scaffold **complete** (37 tests). Human/legal steps remain: license sign-off, IRB, annotation, production data.

See [`TASKS.md`](TASKS.md).

## License

Code: MIT. Data: per-source restrictions in `configs/source_registry.yaml`.
