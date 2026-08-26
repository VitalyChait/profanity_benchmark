# YouthEscalateBench — Comprehensive Project Status & Master TODO

This document synthesizes the status of the entire project across all documentation files (`plan.md`, `TASKS.md`, `26-Profanity-Detection.md`, `docs/*`, `docker/*`, and `reports/*`), detailing **what has been completed** and **what remains to be done** for conference publication (NeurIPS / ACL / EMNLP) and benchmark deployment.

---

## 📊 Executive Project Status Overview

```
+-----------------------------------------------------------------------------------+
| Stage / Area                   | Implementation Status     | Validation Status     |
+-----------------------------------------------------------------------------------+
| Phase 0: System Architecture   | [x] 100% COMPLETE         | [x] 74/74 Pytest Pass |
| Phase 1: Governance & Audit    | [x] 100% COMPLETE         | [x] Gate Passed       |
| Phase 2: Pilot Pipeline        | [x] 100% Code Complete    | [ ] Live Annotators   |
| Phase 3: Data Construction     | [x] 100% COMPLETE (79k+)  | [x] 10 Sources Ingest |
| Phase 4: Adjudication & Split  | [x] 100% COMPLETE         | [x] Zero-Leakage Test |
| Phase 5: Multi-LLM Evaluation  | [x] 100% COMPLETE (12 Mod)| [x] 3 Conditions Run  |
| Phase 6: Reporting & Viz       | [x] 100% COMPLETE         | [x] Auto Infographics |
| Phase 7: Agentic Discovery Loop | [ ] Architecture Planned   | [ ] Autonomous Scout   |
| Pre-Release Compliance & Legal | [x] Documentation Ready   | [ ] IRB Sign-Off      |
| Extended Research Tracks (2&3) | [ ] Planned Post-Bench    | [ ] Research Roadmap  |
+-----------------------------------------------------------------------------------+
```

---

## ✅ 1. Completed Accomplishments (Done)

### 🏗️ Architecture & Core Infrastructure (`Phase 0`)
- [x] **Modular Benchmark Architecture**: Established `src/youth_escalate_bench` across 18 specialized subpackages.
- [x] **Strict Pydantic Schema Contracts**: Implemented `InferenceRequest`, `ModelOutput`, `ConversationRecord`, `TurnRecord`, and `AnnotationRecord` with zero lookahead validation.
- [x] **High-Performance IO Engine**: $O(N)$ dictionary-based conversation grouping and vectorized Parquet IO.
- [x] **Vectorized MinHash & LSH Banding**: Sublinear near-duplicate detection preventing conversational leakage.
- [x] **Robust Checkpoint Orchestrator**: `main.py` orchestrator supporting `--all`, `--resume`, `--step`, `--force`, `--status`, and `--extended-report`.
- [x] **100% Test Pass Rate**: 74 automated unit, integration, schema, causal, and e2e tests passing in CI.
- [x] **CI/CD Integration**: GitHub Actions workflow (`.github/workflows/ci.yml`) with automated linting and coverage checks.

### 🛡️ Governance, Ethics & Threat Modeling (`Phase 1`)
- [x] **Source Registry Gate**: Automated `source_audit` enforcing legal review across 10 datasets in [`configs/source_registry.yaml`](configs/source_registry.yaml).
- [x] **License Audit Worksheet**: Completed source license terms and non-commercial exemptions in [`docs/license_audit_worksheet.md`](docs/license_audit_worksheet.md).
- [x] **Adversarial Threat Model**: Defined 9 algospeak evasion classes and threat vectors in [`docs/threat_model.md`](docs/threat_model.md).
- [x] **IRB Ethics Protocol**: Drafted university human subjects package in [`docs/irb_ethics_package.md`](docs/irb_ethics_package.md).
- [x] **Annotator Wellness Protocol**: Established mental wellness, duty limits, and debriefing standards in [`docs/annotator_wellness_protocol.md`](docs/annotator_wellness_protocol.md).
- [x] **Youth Advisory Protocol**: Created co-design guidelines for adolescent safety feedback in [`docs/youth_advisory_protocol.md`](docs/youth_advisory_protocol.md).

### ⚙️ Pipeline Data Processing & Synthesis (`Phases 2 & 3`)
- [x] **Ingestion of 10 Real-World Datasets**: Adapters for WikiConv, CAD, ConvoTox, GameTox, Davidson, Waseem, etc. (79,000+ turns).
- [x] **PII Redaction Pipeline**: Automated detection and sanitization of emails, IPs, usernames, phone numbers, and URLs.
- [x] **Thread Topology Reconstructor**: Tree-depth validation, branching factor checks, and chronological sorting.
- [x] **Algospeak Obfuscation Suite**: 9 deterministic transformation operators (leetspeak, zero-width spaces, homoglyphs, emojis, phonetic respelling, acronyms, euphemisms).
- [x] **Synthetic Scenario Simulator**: Automated minimal pairs and multi-turn escalation simulations in `stage_generate`.
- [x] **Sampling & Quota Balancing**: Platform and demographic quota allocation in `sample`.

### ⚖️ Adjudication & Leakage-Free Splitting (`Phase 4`)
- [x] **Consensus Adjudicator**: Majority-vote aggregation with tie-breaking and frozen gold manifest export.
- [x] **Zero-Leakage Train/Dev/Test Splitter**: MinHash near-duplicate and exact-match leakage verification.
- [x] **Annotation Packet Exporter**: Standardized export for human annotators and automated judge pipelines.

### 🤖 Multi-LLM Causal Evaluation & Baseline Engine (`Phase 5`)
- [x] **Multi-Provider LLM Router**: Integration with 14 providers (OpenRouter, Mistral, OpenAI, Anthropic, Gemini, Groq, DeepSeek, Together, Ollama, etc.).
- [x] **Top Free OpenRouter Frontier Models**: Evaluated Gemma 4 31B, Gemma 4 26B, Nemotron 3.5 Content Safety, Dots 3 Note Preview, and Liquid LFM 2.5.
- [x] **7 Baseline Scorers**: Evaluated Raw Lexicon, Normalized Lexicon, TF-IDF Char N-Grams, Full-Context Lexicon, Rule Safeguard Expert, Prompted LLM Judge, Ensemble Moderator.
- [x] **3 Causal Context Conditions**: Evaluated `current_turn_only`, `prev_plus_current`, and `full_prefix`.
- [x] **Early Onset Detection Dynamics**: Calculated mean onset delay and detection recall @ lag 0, 1, 2.

### 📈 Visualization, Reporting & Deployment (`Phase 6`)
- [x] **Cross-Condition Performance Matrix**: Comparative markdown tables in [`data/processed/report/evaluation_report.md`](data/processed/report/evaluation_report.md).
- [x] **Automated Infographics Engine**: 300 DPI figures generated in `data/processed/report/`:
  - `infographic_models_comparison.png` (4-panel overview)
  - `figure_auprc_heatmap.png` (AUPRC & AUROC condition heatmaps)
  - `figure_context_trajectory.png` (Causal expansion trajectory curves)
  - `figure_llm_leaderboard.png` (Dedicated LLM ranking chart)
  - `infographic_dashboard.html` (Standalone interactive dark-mode dashboard)
- [x] **Extended Failure Diagnostics (`--extended-report`)**: Turn-by-turn error logs with exact turn text, dialogue context, and diagnostic rationales.
- [x] **Evaluator Microservice Container**: Production-ready Docker container and manual in [`docker/evaluator/`](docker/evaluator/README.md).
- [x] **Publication-Ready Documentation**: Completed [`docs/benchmark_card.md`](docs/benchmark_card.md) and [`docs/datasheet.md`](docs/datasheet.md).

---

## ⏳ 2. What's Left to Do (Actionable Roadmap)

### 🔴 Priority 1: Human Annotations & Live Pilot Verification
- [ ] **Annotator Recruitment & Onboarding**:
  - Recruit 3–5 human annotators using the guidelines in [`docs/annotation_guidelines_v0.1.md`](docs/annotation_guidelines_v0.1.md).
  - Enforce the wellness and break protocols in [`docs/annotator_wellness_protocol.md`](docs/annotator_wellness_protocol.md).
- [ ] **500-Conversation Pilot Annotation**:
  - Distribute annotation packets from `data/processed/annotate_export/annotation_packets.jsonl`.
  - Validate inter-annotator agreement meets benchmark quality targets:
    - Severity Krippendorff $\alpha \ge 0.80$
    - Actionable agreement $\ge 90\%$
  - Analyze disagreements between human raters and LLM judge predictions.
- [ ] **Independent PII Audit**:
  - Conduct human spot-check on 200 random conversations to verify complete redaction of real-world names, handles, and locations.

---

### 🟡 Priority 2: Institutional & Pre-Release Compliance
- [ ] **Formal Institutional Ethics (IRB) Filing**:
  - Submit [`docs/irb_ethics_package.md`](docs/irb_ethics_package.md) to the university/institutional review board.
- [ ] **External Source License Re-Verification**:
  - Prior to public dataset redistribution on HuggingFace / GitHub:
    - Verify CC-BY-SA attribution for WikiConv.
    - Confirm ConvoTox / GameTox terms for derived benchmark redistribution.
    - Sign off legal reviewer section in [`docs/license_audit_worksheet.md`](docs/license_audit_worksheet.md).
- [ ] **OSF Preregistration Freeze**:
  - Pin the exact model versions, prompt templates, decoding seeds, and metric definitions in [`docs/preregistration.md`](docs/preregistration.md) *prior* to evaluating hidden test splits.

---

### 🟢 Priority 3: Expanded Model Evaluation & SOTA Benchmarks
- [ ] **Open Safeguard / Moderation Models**:
  - Evaluate `meta-llama/Llama-Guard-3-8B` and `Llama-Guard-3-1B`.
  - Evaluate `allenai/wildguard`.
  - Evaluate `google/shieldgemma-9b`.
- [ ] **Proprietary Frontier LLMs (Once API keys are configured in `.env`)**:
  - Evaluate OpenAI `gpt-4o` / `gpt-4o-mini`.
  - Evaluate Anthropic `claude-3-5-sonnet-20241022`.
  - Evaluate Google `gemini-2.0-flash`.
- [ ] **Commercial Moderation API Baselines**:
  - Evaluate Perspective API (Google Jigsaw).
  - Evaluate Azure AI Content Safety API.
  - Evaluate OpenAI `/v1/moderations` endpoint.

---

### 🚀 Priority 4: Paper Submission & Public Release (ACL / EMNLP / NeurIPS)
- [ ] **Full 12,000-Conversation Benchmark Run**:
  - Execute full production run: `python main.py --all --extended-report`.
- [ ] **LaTeX Paper Integration**:
  - Incorporate [`data/processed/report/table_main_results.tex`](data/processed/report/table_main_results.tex) and generated figures into paper draft.
- [ ] **Public Benchmark Release Package**:
  - Upload sanitized datasets to Hugging Face Hub (with Croissant metadata).
  - Publish evaluator container image to Docker Hub / GitHub Container Registry (GHCR).

---

### 🔬 Priority 5: Post-Benchmark Research Tracks (from `26-Profanity-Detection.md`)
- [ ] **Track 2: Representation Engineering & Activation Steering**:
  - Extract activation steering vectors from contrastive youth escalation pairs.
  - Test training-free mitigation of moderation false positives (banter vs abuse) without model fine-tuning.
  - Measure steering sensitivity across sequence length.
- [ ] **Track 3: Real-Time Dialogue De-Escalation Engine**:
  - Build an on-the-fly conversational intervention model that rephrases hostile escalation into constructive communication while preserving user intent.
  - Evaluate de-escalation success rates in multi-turn gaming and chat threads.

---

### 🤖 Priority 6: Autonomous Agentic Framework for Continuous Profanity & Slang Discovery
An autonomous, self-evolving agentic loop that continuously scouts, filters, stress-tests, and incorporates emerging youth slang, toxic neologisms, and evasion tactics into YouthEscalateBench.

- [ ] **Phase 6.1: Multi-Source Slang & Neologism Scouts (Web Crawler Subsystem)**:
  - Implement continuous Urban Dictionary scout utilizing `UrbanDictionaryClient` (`/api/random`, daily top definitions, and targeted youth slang tag exploration).
  - Implement Reddit / Social Forum scout (streaming linguistic anomalies from gaming and youth subreddits: r/teenagers, r/gaming, Twitch chat logs).
  - Implement Wiktionary & KnowYourMeme glossary monitor for newly added internet slang, memes, and covert derogatory terms.
  - Implement lexical anomaly detector (identifying high-velocity Out-of-Vocabulary (OOV) tokens with low standard dictionary frequency).

- [ ] **Phase 6.2: Autonomous Linguistic Verification & Multi-Judge Triangulation**:
  - Implement an LLM Multi-Judge verification agent (using OpenRouter frontier models + local models) to evaluate discovered terms:
    - Distinguish innocent adolescent jargon (e.g. *skibidi, rizz, fanum tax, gyatt*) from malicious bypasses, coded slurs, or harassment terms.
    - Classify semantic categories (`derogatory_insult`, `slur_hate_speech`, `offensive_sexual`, `gaming_toxic`, `benign_youth_slang`).
    - Estimate severity rating (Level 1–4) and extract context-dependent usage rules.
  - Implement human-in-the-loop (HITL) review queue for high-stakes terms (severity $\ge 3$ or potential protected-class slurs).

- [ ] **Phase 6.3: Adversarial Mutation & Contrastive Minimal-Pair Generator**:
  - Automatically generate paired conversational scenarios using the newly discovered terms:
    - *Benign scenario*: Slang used in positive/neutral gaming banter or humorous exaggeration.
    - *Escalated scenario*: Identical slang used in hostile, exclusionary, or threatening harassment.
  - Apply the 9 algospeak transformation operators (leetspeak, zero-width spaces, phonetic respellings, emojis) to synthesize evasion variants.

- [ ] **Phase 6.4: Closed-Loop LLM Regression Testing & Vulnerability Re-indexing**:
  - Trigger automated evaluation passes against the multi-LLM benchmark pool specifically targeting newly synthesized pairs.
  - Update the **Internal Difficulty & Misclassification Ranking Index** (`difficulty.py`):
    - Identify whether the new slang term triggers false positive over-moderation (safe banter falsely banned).
    - Identify whether models exhibit false negative blind spots (missed covert harassment).
  - Prioritize vulnerable terms in subsequent model evaluation queues.

- [ ] **Phase 6.5: Automated Database Maintenance, Governance, & CI/CD Cron**:
  - Automatically update and deduplicate [`configs/lexicons/profanity_database.json`](configs/lexicons/profanity_database.json) and [`configs/profanity_lexicon.txt`](configs/profanity_lexicon.txt).
  - Update [`configs/source_registry.yaml`](configs/source_registry.yaml) with timestamped discovery provenance.
  - Create GitHub Actions automated workflow (`.github/workflows/agentic_discovery.yml`) to run the discovery loop on a scheduled cron (e.g., daily / weekly).
  - Generate automated weekly markdown discovery digests in `reports/agentic_discovery_digest.md`.
  - Provide CLI entrypoint: `yeb agent run-once` and `yeb agent start --daemon --interval-hours 24`.

---

## 📌 Document Cross-Reference Map

| Document | Primary Role & Purpose | Current Status |
| :--- | :--- | :--- |
| [`plan.md`](plan.md) | Canonical benchmark specification (RQs, taxonomy, schemas, tracks) | 🟢 Complete & Aligned |
| [`TASKS.md`](TASKS.md) | Phase 0–6 execution checklist | 🟢 Phases 0–6 Implemented |
| [`26-Profanity-Detection.md`](26-Profanity-Detection.md) | Initial research vision (Benchmarking, Steering, De-escalation) | 🟢 Idea 1 Built; Ideas 2&3 Planned |
| [`docs/datasheet.md`](docs/datasheet.md) | Gebru et al. Datasheet for Datasets | 🟢 Complete |
| [`docs/benchmark_card.md`](docs/benchmark_card.md) | Standardized benchmark documentation | 🟢 Complete |
| [`docs/threat_model.md`](docs/threat_model.md) | Adversarial evasion & algospeak threat model | 🟢 Complete |
| [`docs/preregistration.md`](docs/preregistration.md) | OSF Preregistration plan | 🟡 Draft Ready for Freeze |
| [`docs/license_audit_worksheet.md`](docs/license_audit_worksheet.md) | Source licenses & legal sign-off table | 🟡 Pending Final Legal Review |
| [`docs/annotation_guidelines_v0.1.md`](docs/annotation_guidelines_v0.1.md) | Annotator guidelines & edge cases | 🟢 Complete |
| [`docs/annotator_wellness_protocol.md`](docs/annotator_wellness_protocol.md) | Mental health & duty limits for annotators | 🟢 Complete |
| [`docs/youth_advisory_protocol.md`](docs/youth_advisory_protocol.md) | Youth co-design & feedback protocol | 🟢 Complete |
| [`docs/irb_ethics_package.md`](docs/irb_ethics_package.md) | Institutional review board ethics proposal | 🟡 Ready for Institutional Submission |
| [`reports/llm_validation_report.md`](reports/llm_validation_report.md) | Multi-LLM provider live connectivity report | 🟢 Validated |
| [`docker/evaluator/README.md`](docker/evaluator/README.md) | Evaluator container manual & `/predict` API guide | 🟢 Complete |
