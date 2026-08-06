# YouthEscalateBench Datasheet

## Motivation

Standard toxicity benchmarks miss youth-specific algospeak and multi-turn escalation.
YouthEscalateBench evaluates causal moderation detection on peer-to-peer text.

## Composition

| Source tier | Target conversations | Role |
|-------------|---------------------|------|
| Organic | 4,000 | Ecological validity |
| Adult-staged | 2,000 | Controlled escalation |
| Synthetic | 3,000 | Rare harm coverage |
| Functional | 2,000 | Diagnostic minimal pairs |
| Live quarterly | 1,000 | Temporal drift |

## Collection

- Public licensed sources (WikiConv, CAD) with provenance registry
- Adults 18–24 enact staged scenarios (not minors authoring harm)
- Optional youth 13–17 advisors for sanitized co-design only
- No scraping private youth platforms

## Preprocessing

1. License audit gate
2. PII redaction (two-pass + human review for release)
3. Topology validation
4. Deterministic algospeak transforms (paired safe/unsafe)
5. Group-aware split with leakage checks

## Labels

- Triple adult annotation per turn
- Expert adjudication for hidden test, severity-3, context-flips
- Independent dimensions: profanity form, pragmatic use, harm type, severity, target, context dependence

## Uses

**Intended:** Research on moderation detection, robustness, early warning.  
**Not intended:** Automated punishment, surveillance of minors, training on hidden labels.

## Distribution

- Public train/dev with license compliance
- Private test via sandboxed evaluator (network disabled)
- Aggregate metrics only for private slices

## Maintenance

- Semantic versioning (1.0.0, 1.1.0, …)
- Quarterly live snapshots with anchor set
- Correction manifests for label fixes (never silent edits)

## Known limitations

- Text-only v1 (no images/audio)
- English-primary with code-switch slice
- Staged/synthetic tiers explicitly labeled — not equivalent to organic performance
