# YouthEscalateBench Threat Model (Phase 1)

Version 0.1.2 — derived from plan.md Sections 2–4.

## 1. Scope

YouthEscalateBench evaluates **moderation detection** on multi-turn peer-to-peer
text. It does not evaluate chatbot refusal, automated punishment, or intervention
policy execution.

## 2. Assets

| Asset | Sensitivity | Protection goal |
|-------|-------------|-----------------|
| Private test conversations + gold labels | Critical | No public leakage |
| Annotator identities + disagreement labels | High | Access-controlled storage |
| Source registry + license audits | High | Integrity before ingest |
| Model submission containers | Medium | Sandboxed execution |
| Public train/dev splits | Medium | Integrity + license compliance |
| Youth advisor submissions (sanitized) | High | Minimal retention |

## 3. Adversaries and Threats

### 3.1 Benchmark extraction (models memorizing hidden test)

- **Threat:** Submitters overfit or extract hidden texts via repeated queries.
- **Mitigations:** Private evaluator with network disabled; rate limits; canary/
  duplicate submissions; aggregate-only private metrics; immutable manifests.

### 3.2 Adversarial evasion (algospeak, code-switch, composition)

- **Threat:** Semantic-preserving obfuscation bypasses lexical matchers.
- **Mitigations:** Paired clean/transformed evaluation; benign transformation
  controls; held-out transformation families; semantic-equivalence review.

### 3.3 Context manipulation

- **Threat:** Systems ignore history or are misled by benign banter preceding abuse.
- **Mitigations:** Causal-prefix protocol; context-flip minimal pairs; separate
  context gain/harm metrics; label-flip adjudication.

### 3.4 Data misuse

- **Threat:** Benchmark used to train on hidden labels or harass individuals.
- **Mitigations:** License tiers; PII redaction; no exact timestamps; tombstone
  deletion; Responsible-AI documentation; access tiers for sensitive slices.

### 3.5 Annotator harm

- **Threat:** Exposure to severe content without support.
- **Mitigations:** Wellness protocol, exposure limits, paid breaks, opt-out,
  no-penalty reassignment; youth advisors do not annotate harm.

### 3.6 License violation

- **Threat:** Redistributing data contrary to source terms.
- **Mitigations:** Source registry gate; per-source loaders; independent license
  review before release.

## 4. Trust Boundaries

```
[Public internet sources] → ingest (license gate) → redact → internal ETL
[Internal ETL] → annotate (adults only) → adjudicate → split freeze
[Split freeze] → public release (redacted) | private evaluator (network off)
[Model container] → /predict (read-only hidden data, quotas) → aggregate scores
```

## 5. Out of Scope (v1)

- Images, audio, video, platform-network metadata
- Scraping private Discord/Roblox/school spaces
- Inferring that public accounts belong to minors
- CSAM, explicit sexual depictions involving minors, ongoing emergencies

## 6. Residual Risks

- Emergent slang after benchmark freeze will reduce temporal scores (by design).
- Synthetic data may not transfer to organic peer speech.
- Closed API evaluations depend on vendor zero-retention terms.

## 7. Review Schedule

- Revisit threat model at Phase 1 gate, split freeze, and first live snapshot.
