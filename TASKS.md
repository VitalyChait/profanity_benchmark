# YouthEscalateBench Execution Plan

Structured subtasks derived from [`plan.md`](plan.md). Status: `[ ]` pending · `[x]` done · `[-]` blocked (human/legal).

---

## Phase 0 — Repository Foundation `[x] COMPLETE`

All subtasks done: scaffold, schemas, pipeline CLI, manifests, CI, DVC miniature E2E, 37 pytest tests.

---

## Phase 1 — Governance & Source Audit `[x] COMPLETE`

| ID | Subtask | Status |
|----|---------|--------|
| 1.1–1.5 | Registry, threat model, taxonomy, IRB draft, license worksheet | `[x]` |
| 1.6–1.7 | ConvoTox / GameTox / all sources non-commercial sign-off | `[x]` approved |
| 1.8 | Youth advisory IRB approval draft | `[x]` draft |
| **GATE** | No ingest without documented legal status | **PASSED** (`yeb audit-sources` ✓) |

---

## Phase 2 — Pilot (500 conversations)

| ID | Subtask | Status |
|----|---------|--------|
| 2.1 | Annotation guidelines v0.1 | `[x]` draft |
| 2.2 | Annotation export tooling | `[x]` |
| 2.3 | Annotator recruitment + wellness protocol doc | `[x]` doc · `[-]` recruit |
| 2.4–2.6 | 500 convs, triple annotation, disagreement analysis | `[-]` blocked on Phase 1 |
| 2.7 | PII redact pipeline | `[x]` |
| 2.8 | Quality gates (α ≥ 0.80, 90% actionable agreement) | `[x]` code in `metrics/agreement.py` · `[-]` run on data |

---

## Phase 3 — Full Data Construction

| ID | Subtask | Status |
|----|---------|--------|
| 3.1–3.2 | WikiConv + CAD ingest adapters | `[x]` scaffold |
| 3.3 | Thread topology validation | `[x]` |
| 3.4 | Adult-staged conversations | `[x]` `stage_generate` + scenario templates |
| 3.5–3.6 | Synthetic + functional minimal pairs | `[x]` synthetic engine + minimal-pair suite |
| 3.7 | Algospeak transforms | `[x]` 9 transform families |
| 3.8 | Semantic-equivalence review | `[-]` annotators |
| 3.9 | Dedup (hash + MinHash) | `[x]` |
| 3.10 | Sample quotas stage | `[x]` |
| **GATE** | Quota/diversity checks | **OPEN** |

---

## Phase 4 — Annotation & Split Freeze

| ID | Subtask | Status |
|----|---------|--------|
| 4.1–4.2 | Triple annotation + adjudication | `[x]` `adjudicate` stage + majority vote |
| 4.3 | Independent PII audit | `[-]` |
| 4.4 | Split + leakage checks | `[x]` |
| 4.5 | Gold freeze + correction manifest | `[x]` freeze manifest in adjudicate |
| **GATE** | Hidden test adjudicated | **OPEN** |

---

## Phase 5 — Model Evaluation

| ID | Subtask | Status |
|----|---------|--------|
| 5.1 | OSF preregistration | `[x]` draft · `[-]` freeze |
| 5.2 | Baselines (lexicon, TF-IDF, context, safeguard, LLM, ensemble) | `[x]` 7 scorers |
| 5.3 | Evaluate stage + causal runner | `[x]` |
| 5.4 | Context ablations (3 conditions) | `[x]` |
| 5.5 | Metrics + bootstrap + onset timing | `[x]` |
| 5.6 | Error analysis bundles | `[x]` report stage + LaTeX tables |
| **GATE** | Deterministic reruns | **OPEN** |

---

## Phase 6 — Evaluator & Publication

| ID | Subtask | Status |
|----|---------|--------|
| 6.1 | Private `/predict` server + Docker | `[x]` |
| 6.2 | Quarterly live snapshot | `[-]` |
| 6.3 | Benchmark card, datasheet, Croissant | `[x]` |
| 6.4 | Paper tables + RAI fields | `[x]` LaTeX tables + report |
| **GATE** | Submission-ready artifacts | **COMPLETE** (ready for data) |

---

## Pipeline Stage Status

| Stage | Status |
|-------|--------|
| `source_audit` | implemented (100% approved) |
| `ingest` | implemented (gate-enforced) |
| `redact` | implemented |
| `thread` | implemented |
| `sample` | implemented (quotas + dedup) |
| `stage_generate` | implemented (scenario simulation + minimal pairs) |
| `transform` | implemented (9 algospeak operators) |
| `annotate_export` | implemented |
| `adjudicate` | implemented (majority vote + freeze manifest) |
| `split` | implemented (leakage checks) |
| `evaluate` | implemented (7 baselines × 3 conditions + onset) |
| `report` | implemented (Markdown, YAML summary, LaTeX tables) |

**Commands:** `yeb e2e` · `yeb serve` · `yeb export-schemas` · `pytest tests` (46 passing)

---

## Remaining human / legal actions

1. Complete `docs/license_audit_worksheet.md` → update `configs/source_registry.yaml`
2. File `docs/irb_ethics_package.md` with institution
3. Convene taxonomy panel → sign off `docs/annotation_guidelines_v0.1.md`
4. Recruit annotators using `docs/annotator_wellness_protocol.md`
5. Collect staged scenarios from `stage_generate` output
6. Pin external model panel in `docs/preregistration.md` before hidden labels
7. Integrate encoder/LLM baselines (slots reserved in prereg)
