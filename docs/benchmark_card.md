# YouthEscalateBench Benchmark Card

**Version:** 0.1.2  
**Task:** Multi-turn youth-oriented peer moderation detection  
**Languages:** English + English-led code-switch slice  
**Unit:** Turn within causal conversation prefix  

## Tracks (independently scored)

| Track | Description |
|-------|-------------|
| Current-turn moderation | Harm probability at each turn with context ablations |
| Onset detection | First actionable turn after gold harm onset |
| Two-turn forecast | Predict harm in t+1 or t+2 |
| Robustness / drift | Clean vs transformed pairs, temporal snapshots |

## Splits (target scale)

| Split | Conversations | Access |
|-------|---------------|--------|
| Public train | 5,000 | Redistributable (license-dependent) |
| Public dev | 2,000 | Redistributable |
| Private representative test | 2,000 | Evaluator only |
| Private diagnostic test | 2,000 | Evaluator only |
| Quarterly live | 1,000 | Versioned snapshots |

## Metrics (primary)

- AUPRC actionable harm (severity ≥ 2)
- Macro-AUPRC across harm types
- Recall at 95% precision / recall at 1% FPR
- Detection recall at lag 0, 1, 2 after onset
- Context gain (full prefix vs turn-only)

## Baselines (bundled)

- 7 Classical & Specialized Baselines: `lexicon_raw`, `lexicon_normalized`, `char_ngram_tfidf`, `lexicon_full_context`, `rule_safeguard_expert`, `prompted_llm_judge`, `ensemble_moderator`
- Frontier Multi-LLM Router: 14 providers (OpenRouter, Groq, Mistral, OpenAI, Anthropic, Gemini, Ollama, etc.)
- Active Difficulty Queue: Prioritizes historically misclassified turns and vulnerable slang via `SentenceRanking` & `WordRanking`

## Submission

OCI container implementing `POST /predict` with `InferenceRequest` JSON → `ModelOutput` JSON.

```bash
docker build -f docker/evaluator/Dockerfile -t yeb-evaluator .
docker run --network none -p 8080:8080 yeb-evaluator
```

## License

Code: MIT. Data: per-source restrictions in `configs/source_registry.yaml`.

## Citation

YouthEscalateBench (2026). Dynamic Multi-Turn Youth-Safeguarding Benchmark.
