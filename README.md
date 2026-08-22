# YouthEscalateBench

Dynamic multi-turn youth-safeguarding benchmark for causal moderation detection.

## Quick start

```bash
pip install -e ".[dev]"
yeb llm-status                       # Inspect detected LLM API keys (.env)
yeb e2e                              # Miniature fixture pipeline (50 tests)
yeb export-schemas                   # JSON Schema contracts
yeb audit-sources                    # Phase 1 gate
yeb serve --port 8080                # /predict evaluator
pytest tests -v
```

## LLM API Keys & Auto-Detection

The benchmark auto-detects configured LLM providers and uses them for live evaluation, synthetic generation, and automated multi-model consensus judging:

1. Copy the key template to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Set your keys in `.env` (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, or `OLLAMA_BASE_URL`).
3. Verify detected keys:
   ```bash
   yeb llm-status
   ```

## Pipeline

`source_audit → ingest → redact → thread → sample → stage_generate → transform →
annotate_export → adjudicate → split → evaluate → report`

```bash
yeb run --stage stage_generate --config configs/stages/stage_generate.yaml
yeb run --stage transform --config configs/stages/transform.yaml
yeb run --stage evaluate --config configs/stages/evaluate.yaml
yeb run --stage report --config configs/stages/report.yaml
```

## Baseline Moderation Scorers

| Scorer | Description |
|--------|-------------|
| `lexicon_raw` | Raw profanity lexicon matcher |
| `lexicon_normalized` | Normalized text lexicon |
| `char_ngram_tfidf` | Char n-gram weighted scorer |
| `lexicon_full_context` | Lexicon over full causal prefix |
| `rule_based_safeguard` | Multi-pattern escalation & banter tracker |
| `prompted_llm_judge` | Frontier LLM judge (auto-routes via `.env` keys) |
| `ensemble_moderator` | Calibrated multi-feature weighted blend |

## Evaluator container

```bash
docker build -f docker/evaluator/Dockerfile -t yeb-evaluator .
docker run --network none -p 8080:8080 yeb-evaluator
# POST http://localhost:8080/predict with InferenceRequest JSON
```

## Documentation

| Doc | Purpose |
|-----|---------|
| [`.env.example`](.env.example) | Designated LLM API keys template |
| [`TASKS.md`](TASKS.md) | Phase tracker |
| [`TODO.md`](TODO.md) | Pre-release and re-audit checklist |
| [`docs/benchmark_card.md`](docs/benchmark_card.md) | NeurIPS E&D summary |
| [`docs/datasheet.md`](docs/datasheet.md) | Datasheet |
| [`docs/preregistration.md`](docs/preregistration.md) | OSF prereg draft |
| [`metadata/croissant.json`](metadata/croissant.json) | Croissant metadata |

## Status

Engineering scaffold & autonomous pipeline **complete** (50 tests passing).

## License

Code: MIT. Data: per-source restrictions in `configs/source_registry.yaml`.
