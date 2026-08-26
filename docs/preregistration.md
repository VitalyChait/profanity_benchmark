# OSF Preregistration Draft — YouthEscalateBench

**Study title:** YouthEscalateBench: Causal Multi-Turn Moderation Evaluation  
**Status:** Draft — freeze before viewing hidden labels

## Hypotheses (from plan.md)

- **H1:** Full causal history improves AUPRC on context-dependent examples but may not improve aggregate performance.
- **H2:** Semantic-preserving evasion reduces detection; composed transformations cause larger losses.
- **H3:** Context-aware systems improve onset detection but may increase false alarms during benign banter.
- **H4:** Lower performance on expressions first observed after model training cutoff.
- **H5:** Specialized moderation models better calibrated; general LLMs better on implicit/context-dependent harm.

## Primary comparisons (BH-FDR 0.05)

1. Full prefix vs current-turn-only AUPRC (paired bootstrap)
2. Transformed vs clean AUPRC (robustness retention)
3. Specialized safeguard vs instruction LLM on context-dependent slice
4. Onset detection recall at lag 0 vs lag 2

## Model panel (pinned at freeze)

| Tier | Models | Notes |
|------|--------|-------|
| Lexical | `lexicon_raw`, `lexicon_normalized`, `char_ngram_tfidf`, `lexicon_full_context` | Bundled deterministic baselines |
| Rule Safeguard | `rule_safeguard_expert` | Threshold 0.65, context window 3 turns |
| LLM Judge | `prompted_llm_judge` | OpenRouter / local LLM, zero-shot structured JSON |
| Ensemble | `ensemble_moderator` | 40% lexical + 60% rule safeguard |
| Frontier LLMs | Gemma 4 (31B/26B), Nemotron 3.5 Content Safety, Dots 3, Liquid LFM 2.5 | Temperature 0.0, seed 42 |

## Evaluation conditions

- Current turn only, prev+current, full prefix
- Raw and oracle-normalized (diagnostic)
- Zero-shot and 5-shot (public dev examples only)

## Exclusions

- Hidden labels not used for model selection
- Exploratory analyses labeled explicitly in paper

## Power

Pilot simulation target: 90% power for Δ AUPRC = 0.03 (paired).

## Data

YouthEscalateBench v1.0.0 representative + diagnostic private tracks.
