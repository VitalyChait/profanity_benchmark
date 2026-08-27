# Annotation Guidelines v0.1

**YouthEscalateBench** — draft for taxonomy panel review  
**Version:** 0.1.1 | **Date:** 2026-08-05

## 1. Purpose

Label each turn and conversation for moderation **detection** research. Do not infer
offline age, identity, intent, power imbalance, or threat credibility unless explicitly
observable in the text.

## 2. Unit of annotation

- **Turn-level:** every visible turn receives independent dimension labels.
- **Conversation-level:** first actionable turn, peak severity, repeated-target pattern,
  de-escalation (adjudication tier).

## 3. Severity (required)

| Level | Label | Definition |
|-------|-------|------------|
| 0 | `benign` | No moderation concern |
| 1 | `coarse_monitor` | Rude/profane but not actionable alone |
| 2 | `actionable` | Warrants intervention (insult, harassment turn, etc.) |
| 3 | `urgent` | High-risk (credible threat, self-harm encouragement) |

**Actionable harm** = severity ≥ 2.

## 4. Harm types (multi-label, optional empty)

`targeted_insult`, `repeated_harassment`, `identity_attack`, `threat_intimidation`,
`sexualized_harassment`, `self_harm_encouragement`, `exclusion_coercion`,
`humiliation_rumor`, `dogpiling_mobilization`.

**Note:** `repeated_harassment` requires repeated or conversation-level targeting.

## 5. Profanity form (required)

`none`, `literal`, `orthographically_obfuscated`, `phonetic`, `euphemistic_algo_coded`,
`acronym`, `emoji_rebus`, `code_switched`.

## 6. Pragmatic use (required)

`absent`, `affiliative_banter`, `emotional_emphasis`, `quotation_reporting`,
`reclaimed_self_reference`, `targeted_abuse`, `ambiguous`.

## 7. Target type (required)

`none`, `self`, `individual_peer`, `non_protected_group`, `protected_group`,
`indeterminate`.

## 8. Context dependence (required when full thread visible)

`invariant`, `amplified`, `mitigated`, `label_flipped`, `insufficient_context`.

Use `label_flipped` when the current turn alone would receive a different severity
than with full causal prefix.

## 9. Escalation transition (required)

`de_escalating`, `stable`, `escalating`, `not_applicable` (first turn).

## 10. Evidence (required for severity ≥ 2)

- Character spans in current turn.
- Prior `turn_id` values needed to justify the label.

## 11. Edge cases

| Case | Guidance |
|------|----------|
| Quoted abuse | `quotation_reporting` if condemning; else harm labels |
| Friendly profanity | `affiliative_banter`, severity 0–1 |
| Reclaimed language | `reclaimed_self_reference` vs `identity_attack` by target |
| Code-switch | Note language shift; do not penalize non-English |
| Ambiguous | Use `ambiguous` / `insufficient_context` — do not force |

## 12. Quality expectations

- Pilot gate: Krippendorff α ≥ 0.80 on severity after guideline stabilization.
- ≥ 90% agreement on actionable vs non-actionable.
- Disagreements trigger guideline revision, not model comparison.

## 13. Panel sign-off (pending)

| Role | Name | Date | Status |
|------|------|------|--------|
| Cyberbullying researcher | | | pending |
| Trust & safety practitioner | | | pending |
| Youth-safety / developmental expert | | | pending |
| Linguist | | | pending |
| Annotation lead | | | pending |
