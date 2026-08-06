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

## Model panel (to pin at freeze)

| Tier | Models | Notes |
|------|--------|-------|
| Lexical | lexicon_raw, lexicon_normalized, char_ngram_tfidf | Bundled baselines |
| Encoder | TBD fine-tuned on public train only | Pin checkpoint |
| Safeguard | TBD × 3 open models | Pin revisions |
| Instruction LLM | TBD × 6 spanning size tiers | Temperature 0 |

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
