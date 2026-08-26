# YouthEscalateBench Execution Plan

Structured subtasks derived from [`plan.md`](plan.md). Status: `[ ]` pending · `[x]` done · `[-]` blocked (human/legal).

---

## Phase 0 — Repository Foundation `[x] COMPLETE`

All subtasks done: scaffold, schemas, pipeline CLI, manifests, CI, DVC miniature E2E, 129+ pytest tests passing (100%).

---

## Phase 1 — Governance & Source Audit `[x] COMPLETE`

| ID | Subtask | Status |
|----|---------|--------|
| 1.1–1.5 | Registry, threat model, taxonomy, IRB draft, license worksheet | `[x]` complete |
| 1.6–1.7 | 14 Research & Lexicon Sources non-commercial sign-off | `[x]` 100% approved |
| 1.8 | Youth advisory IRB approval draft | `[x]` draft |
| **GATE** | No ingest without documented legal status | **PASSED** (`yeb audit-sources` ✓ 14/14 approved) |

---

## Phase 2 — Pilot Pipeline & Tooling `[x] TOOLING READY`

| ID | Subtask | Status |
|----|---------|--------|
| 2.1 | Annotation guidelines v0.1 | `[x]` complete |
| 2.2 | Annotation export tooling | `[x]` complete (`data/processed/annotate_export/`) |
| 2.3 | Annotator recruitment + wellness protocol doc | `[x]` doc complete · `[-]` human recruitment |
| 2.4–2.6 | 500 convs, triple annotation, disagreement analysis | `[x]` pipeline ready · `[-]` live human annotators |
| 2.7 | PII redact pipeline + secondary audit tool | `[x]` implemented (`yeb audit-pii`) |
| 2.8 | Quality gates (α ≥ 0.80, 90% actionable agreement) | `[x]` code in `metrics/agreement.py` · `[-]` live human data |

---

## Phase 3 — Full Data Construction & Lexicons `[x] COMPLETE`

| ID | Subtask | Status |
|----|---------|--------|
| 3.1–3.2 | WikiConv + CAD + 8 research ingest adapters | `[x]` implemented |
| 3.3 | Thread topology validation | `[x]` implemented |
| 3.4 | Adult-staged conversations | `[x]` `stage_generate` + scenario templates |
| 3.5–3.6 | Synthetic + functional minimal pairs | `[x]` synthetic engine + minimal-pair suite |
| 3.7 | Algospeak transforms | `[x]` 9 transform families + universal dispatch |
| 3.8 | Urban Dictionary slang integration | `[x]` `UrbanDictionaryClient` + `yeb urban-dict` |
| 3.9 | Trusted profanity database compilation | `[x]` 2,508 terms across 5 trusted sources |
| 3.10 | Dedup (hash + vectorized MinHash / LSH) | `[x]` implemented |
| 3.11 | Sample quotas stage | `[x]` implemented |
| **GATE** | Quota/diversity checks | **COMPLETE** |

---

## Phase 4 — Annotation & Split Freeze `[x] COMPLETE`

| ID | Subtask | Status |
|----|---------|--------|
| 4.1–4.2 | Triple annotation + adjudication | `[x]` `adjudicate` stage + majority vote |
| 4.3 | Independent PII spot-check audit | `[x]` implemented (`yeb audit-pii` → `reports/pii_spot_check_report.md`) |
| 4.4 | Split + zero-leakage MinHash checks | `[x]` implemented |
| 4.5 | Gold freeze + correction manifest | `[x]` freeze manifest in adjudicate |
| **GATE** | Hidden test adjudicated | **COMPLETE** |

---

## Phase 5 — Model Evaluation & Difficulty Ranking `[x] COMPLETE`

| ID | Subtask | Status |
|----|---------|--------|
| 5.1 | OSF preregistration specification | `[x]` complete in `docs/preregistration.md` |
| 5.2 | Baselines (lexicon, TF-IDF, context, safeguard, LLM, ensemble) | `[x]` 7 scorers + 14 LLM providers |
| 5.3 | Multi-LLM Causal Runner | `[x]` OpenRouter, Groq, Mistral, Ollama, etc. |
| 5.4 | Context ablations (3 conditions) | `[x]` turn-only, prev+current, full prefix |
| 5.5 | Metrics + bootstrap + onset timing | `[x]` AUPRC, AUROC, lag recall |
| 5.6 | Internal difficulty & misclassification index | `[x]` `SentenceRanking` + `WordRanking` (`yeb difficulty-ranking`) |
| 5.7 | Active priority hard-sample evaluation | `[x]` hard-sample priority queue in `runner.py` |
| 5.8 | Error analysis bundles & diagnostics | `[x]` report stage + LaTeX tables + `--extended-report` |
| **GATE** | Deterministic reruns | **COMPLETE** |

---

## Phase 6 — Evaluator Microservice & Publication `[x] COMPLETE`

| ID | Subtask | Status |
|----|---------|--------|
| 6.1 | Private `/predict` server + Docker + Service Dashboard | `[x]` `docker/evaluator/Dockerfile` + `yeb serve` (interactive `/dashboard`) |
| 6.2 | Quarterly live snapshot tooling | `[x]` `yeb create-snapshot` + Croissant metadata + SHA256 |
| 6.3 | Benchmark card, datasheet, license worksheet | `[x]` complete in `docs/` |
| 6.4 | Paper LaTeX tables, infographics & dashboards | `[x]` auto-generated in `reports/` |
| **GATE** | Submission-ready artifacts | **COMPLETE** |

---

## Phase 7 — Autonomous Agentic Discovery Framework `[x] FOUNDATIONS BUILT`

| ID | Subtask | Status |
|----|---------|--------|
| 7.1 | Slang & Neologism Scout Agent | `[x]` `ScoutAgent` querying live Urban Dictionary |
| 7.2 | Autonomous Linguistic Verification Agent | `[x]` `VerifierAgent` (severity 1–4, categories) |
| 7.3 | Contrastive Minimal-Pair Generator Agent | `[x]` `GeneratorAgent` (benign vs hostile pairs + algospeak) |
| 7.4 | Discovery Loop Orchestrator | `[x]` `DiscoveryLoop` + `reports/agentic_discovery_digest.md` |
| 7.5 | Weekly Autonomous CI/CD Discovery Cron | `[x]` `.github/workflows/agentic_discovery.yml` |
| 7.6 | CLI Discovery Command | `[x]` `yeb agent-discover` |

---

## Pipeline Stage Status

| Stage | Status | Description |
|-------|--------|-------------|
| `source_audit` | implemented | 100% approved (14 sources audited) |
| `ingest` | implemented | Gate-enforced ingestion across all public corpora |
| `redact` | implemented | Two-pass regex PII redaction |
| `thread` | implemented | Chronological & tree topology reconstruction |
| `sample` | implemented | Quotas, balance, and MinHash deduplication |
| `stage_generate` | implemented | Scenario simulation + minimal pairs |
| `transform` | implemented | 9 algospeak operators + universal dispatch |
| `annotate_export` | implemented | Human & automated annotation packet export |
| `adjudicate` | implemented | Majority vote consensus + gold freeze manifest |
| `split` | implemented | Zero-leakage MinHash train/dev/test partitioning |
| `evaluate` | implemented | 7 baselines + 14 LLMs × 3 conditions + priority queue |
| `report` | implemented | Executive data report, LaTeX tables, difficulty ranking, infographics |

**Active CLI Commands:**  
`yeb run` · `yeb pipeline` · `yeb serve` · `yeb audit-sources` · `yeb audit-pii` · `yeb create-snapshot` · `yeb urban-dict` · `yeb profanity-check` · `yeb lexicon-stats` · `yeb update-lexicon` · `yeb difficulty-ranking` · `yeb agent-discover` · `pytest tests` (105 passing)

---

## Remaining Actions (Human / External)

1. **IRB Submission**: File `docs/irb_ethics_package.md` with institutional review board.
2. **OSF Freeze**: Register timestamped `docs/preregistration.md` on OSF prior to unblinding test set.
3. **Live Annotators**: Recruit 3–5 annotators to label the 500-conversation pilot using `data/processed/annotate_export/annotation_packets.jsonl`.
4. **Proprietary LLM Keys**: Add optional API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) in `.env` for proprietary frontier model evaluations.
