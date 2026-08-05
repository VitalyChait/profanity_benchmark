# YouthEscalateBench Execution Plan

Structured subtasks derived from [`plan.md`](plan.md). Status key: `[ ]` pending, `[~]` in progress, `[x]` done, `[-]` blocked.

---

## Phase 0 — Repository Foundation

| ID | Subtask | Owner | Depends | Gate |
|----|---------|-------|---------|------|
| 0.1 | `[x]` Python project scaffold (`pyproject.toml`, `src/youth_escalate_bench/`) | eng | — | `pip install -e .` succeeds |
| 0.2 | `[x]` Pydantic contracts: inference input, model output, turn, label taxonomy | eng | 0.1 | schema tests pass |
| 0.3 | `[x]` Pipeline stage CLI stubs with versioned YAML configs | eng | 0.1 | `yeb run --stage source_audit` runs |
| 0.4 | `[x]` Manifest utilities (SHA-256 row counts, reproducibility) | eng | 0.3 | manifest round-trip test |
| 0.5 | `[x]` pytest suite: schema, topology, causal-prefix, no-future-turn | eng | 0.2 | CI green |
| 0.6 | `[x]` `TASKS.md` (this file) + updated `README.md` | eng | — | — |
| 0.7 | `[x]` CI workflow (Python 3.12 matrix, pytest + ruff) | eng | 0.1 | GitHub Actions green |
| 0.8 | `[x]` DVC miniature E2E pipeline (`dvc.yaml`) | eng | 0.3 | stages wired |

---

## Phase 1 — Weeks 1–4: Governance & Source Audit

| ID | Subtask | Owner | Depends | Gate |
|----|---------|-------|---------|------|
| 1.1 | `[x]` Source registry schema + registry YAML | eng | 0.1 | 100% source coverage field defined |
| 1.2 | `[x]` IRB/ethics submission package draft | PI | — | ethics determination filed |
| 1.3 | `[x]` Threat model document | eng | — | reviewed by T&S |
| 1.4 | `[x]` Taxonomy draft as machine-readable enums | eng | 0.2 | panel review scheduled |
| 1.5 | `[x]` License audit worksheet template | legal | 1.1 | each source has allow/deny row |
| 1.6 | `[ ]` ConvoTox written redistribution review | legal | 1.5 | written approval or fallback quota |
| 1.7 | `[ ]` GameTox access request | legal | 1.5 | access or taxonomy-only fallback |
| 1.8 | `[ ]` Youth advisory IRB protocol (13–17 co-design) | ethics | 1.2 | approved or 18–24 fallback |
| **GATE** | **No source enters ingest without documented legal status** | | 1.6–1.7 | |

---

## Phase 2 — Weeks 5–8: Pilot (500 conversations)

| ID | Subtask | Owner | Depends | Gate |
|----|---------|-------|---------|------|
| 2.1 | `[x]` Annotation guideline v0.1 draft | annot | 1.4 | panel sign-off |
| 2.2 | `[x]` Annotation packet export format + tooling | eng | 0.3, 2.1 | pilot packets generated |
| 2.3 | `[ ]` Recruit 12–20 adult annotators + wellness protocol | annot | 1.2 | training complete |
| 2.4 | `[ ]` Build 500 pilot conversations (mixed sources) | data | GATE 1 | 500 convs in Parquet |
| 2.5 | `[ ]` Triple annotation on all pilot turns | annot | 2.2–2.4 | labels imported |
| 2.6 | `[ ]` Disagreement analysis → guideline v1.0 | annot | 2.5 | revision documented |
| 2.7 | `[x]` PII detector setup + redact stage | eng | 0.3 | two-pass PII pipeline |
| 2.8 | `[ ]` Quality gates: Krippendorff α ≥ 0.80 severity; 90% actionable agreement | annot | 2.5 | gates pass or re-annotate |
| **GATE** | **Agreement and privacy thresholds met** | | 2.7–2.8 | |

---

## Phase 3 — Weeks 9–16: Full Data Construction

| ID | Subtask | Owner | Depends | Gate |
|----|---------|-------|---------|------|
| 3.1 | `[x]` `ingest` adapters: WikiConv/WikiDetox (scaffold) | data | GATE 1 | organic quota on track |
| 3.2 | `[x]` `ingest` adapter: CAD (scaffold) | data | GATE 1 | CAD integrated |
| 3.3 | `[x]` `thread` topology reconstruction + validation | eng | 3.1 | topology tests pass |
| 3.4 | `[ ]` Adult-staged conversations (2,000 target) | data | 1.8 | scenario state machines |
| 3.5 | `[ ]` Synthetic generation (3 families, hold-out 1) | data | 2.1 | ≤25% hidden test synthetic |
| 3.6 | `[ ]` Functional/counterfactual minimal pairs (2,000 convs) | data | 1.4 | pair groups intact |
| 3.7 | `[x]` Algospeak transformation operators (deterministic, versioned) | eng | 0.3 | determinism tests pass |
| 3.8 | `[ ]` Semantic-equivalence review (3 annotators, unanimous filter) | annot | 3.7 | robustness set frozen |
| 3.9 | `[x]` Deduplication: hash + MinHash utilities | eng | 3.3 | near-duplicate report |
| 3.10 | `[ ]` `sample` quotas per source tier (12k conv / 80k turns) | data | 3.1–3.6 | quota dashboard |
| **GATE** | **Quota, topology, semantic-equivalence, source-diversity checks** | | 3.9–3.10 | |

---

## Phase 4 — Weeks 17–22: Production Annotation & Split Freeze

| ID | Subtask | Owner | Depends | Gate |
|----|---------|-------|---------|------|
| 4.1 | `[ ]` Triple annotation on full corpus | annot | GATE 3 | all turns labeled |
| 4.2 | `[ ]` Expert adjudication (hidden test, severity-3, flips, code-switch) | annot | 4.1 | 100% hidden adjudicated |
| 4.3 | `[ ]` Independent PII audit | privacy | 2.7 | zero critical findings |
| 4.4 | `[x]` `split`: group-aware split stage (seeded) | eng | 4.2 | zero cross-split leakage |
| 4.5 | `[ ]` Freeze gold labels + correction manifest process | eng | 4.4 | immutable release tag |
| **GATE** | **Hidden test adjudicated; critical PII clear** | | 4.2–4.3 | |

---

## Phase 5 — Weeks 23–27: Model Evaluation

| ID | Subtask | Owner | Depends | Gate |
|----|---------|-------|---------|------|
| 5.1 | `[ ]` Preregister model panel + hypotheses (OSF) | PI | GATE 4 | prereg frozen |
| 5.2 | `[ ]` Baseline implementations (lexicon, TF-IDF, encoders, safeguards) | eng | 0.3 | baselines runnable |
| 5.3 | `[x]` `evaluate`: metrics scaffold + JSON validation | eng | 5.2 | no future-turn exposure |
| 5.4 | `[ ]` Context ablations (turn-only, prev+current, full prefix) | eng | 5.3 | all conditions logged |
| 5.5 | `[x]` Metrics + bootstrap CI utilities | eng | 5.3 | metric fixture tests pass |
| 5.6 | `[ ]` Error analysis bundles by source tier / harm type | eval | 5.5 | bundles published |
| **GATE** | **Deterministic reruns within tolerance** | | 5.3 | |

---

## Phase 6 — Weeks 28–32: Dynamic Evaluator & Publication

| ID | Subtask | Owner | Depends | Gate |
|----|---------|-------|---------|------|
| 6.1 | `[ ]` Private evaluator server (`/predict` OCI, network off) | eng | 5.3 | container isolation tests |
| 6.2 | `[ ]` First quarterly live snapshot (1,000 conv quota) | data | 6.1 | version 1.1.0 tagged |
| 6.3 | `[ ]` Benchmark card, datasheet, Croissant metadata | docs | 5.5 | NeurIPS E&D checklist |
| 6.4 | `[ ]` Paper tables + Responsible-AI fields | PI | 5.5–6.3 | submission ready |
| **GATE** | **Executable benchmark + metadata at submission** | | 6.1–6.4 | |

---

## Cross-Cutting Engineering Stages

```
source_audit → ingest → redact → thread → sample → stage_generate → transform
  → annotate_export → adjudicate → split → evaluate → report
```

| Stage | Status |
|-------|--------|
| `source_audit` | implemented |
| `ingest` | implemented (gate-enforced) |
| `redact` | implemented |
| `thread` | implemented |
| `sample` | dedup report implemented |
| `stage_generate` | stub |
| `transform` | implemented |
| `annotate_export` | implemented |
| `adjudicate` | stub |
| `split` | implemented |
| `evaluate` | scaffold |
| `report` | stub |

**E2E:** `yeb e2e` runs fixture pipeline (28 tests passing).

**Schemas:** `yeb export-schemas` → `schemas/json/`

---

## Human / Legal Blockers (cannot automate)

1. License audits sign-off (ConvoTox, GameTox, WikiConv, CAD)
2. IRB filing and youth advisory approval
3. Annotator recruitment and pilot labeling
4. Production data collection at scale
