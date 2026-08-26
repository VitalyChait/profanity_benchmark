# YouthEscalateBench — Comprehensive Project Status & Master TODO

This document synthesizes the status of the entire project across all documentation files (`plan.md`, `TASKS.md`, `26-Profanity-Detection.md`, `docs/*`, `docker/*`, and `reports/*`), detailing **what has been completed** and **what remains to be done** for conference publication (NeurIPS / ACL / EMNLP) and benchmark deployment.

---

## 📊 Executive Project Status Overview

```
+-----------------------------------------------------------------------------------+
| Stage / Area                   | Implementation Status     | Validation Status     |
+-----------------------------------------------------------------------------------+
| Phase 0: System Architecture   | [x] 100% COMPLETE         | [x] 105/105 Pytest Pass|
| Phase 1: Governance & Audit    | [x] 100% COMPLETE         | [x] Gate Passed (14/14)|
| Phase 2: Pilot Pipeline        | [x] 100% Code Complete    | [ ] Live Annotators   |
| Phase 3: Data Construction     | [x] 100% COMPLETE (79k+)  | [x] 14 Sources Ingest |
| Phase 4: Adjudication & Split  | [x] 100% COMPLETE         | [x] Zero-Leakage Test |
| Phase 5: Multi-LLM Evaluation  | [x] 100% COMPLETE (12 Mod)| [x] Priority Sampling |
| Phase 6: Reporting & Viz       | [x] 100% COMPLETE         | [x] Auto Infographics |
| Phase 7: Agentic Discovery Loop| [x] 100% Code Complete    | [x] Autonomous Scout  |
| Pre-Release Compliance & Legal | [x] Documentation Ready   | [ ] IRB Sign-Off      |
| Extended Research Tracks (2&3) | [ ] Planned Post-Bench    | [ ] Research Roadmap  |
+-----------------------------------------------------------------------------------+
```

---

## ✅ 1. Completed Accomplishments (Done)

### 🏗️ Architecture & Core Infrastructure (`Phase 0`)
- [x] **Modular Benchmark Architecture**: Established `src/youth_escalate_bench` across 21 specialized subpackages.
- [x] **Strict Pydantic Schema Contracts**: Implemented `InferenceRequest`, `ModelOutput`, `ConversationRecord`, `TurnRecord`, and `AnnotationRecord` with zero lookahead validation.
- [x] **High-Performance IO Engine**: $O(N)$ dictionary-based conversation grouping and vectorized Parquet IO.
- [x] **Vectorized MinHash & LSH Banding**: Sublinear near-duplicate detection preventing conversational leakage.
- [x] **Robust Checkpoint Orchestrator**: `main.py` orchestrator supporting `--all`, `--resume`, `--step`, `--force`, `--status`, and `--extended-report`.
- [x] **100% Test Pass Rate**: 105+ automated unit, integration, schema, causal, agentic, and e2e tests passing in CI.
- [x] **CI/CD Integration**: GitHub Actions workflows (`.github/workflows/ci.yml` and `.github/workflows/agentic_discovery.yml`).

### 🛡️ Governance, Ethics & Threat Modeling (`Phase 1`)
- [x] **Source Registry Gate**: Automated `source_audit` enforcing legal review across 14 research datasets and lexicons in [`configs/source_registry.yaml`](configs/source_registry.yaml).
- [x] **License Audit Worksheet**: Completed source license terms and non-commercial exemptions for all 14 sources in [`docs/license_audit_worksheet.md`](docs/license_audit_worksheet.md).
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
- [x] **Quarterly Live Snapshot Tooling (`yeb create-snapshot`)**: Bundles versioned release archives with Croissant metadata and SHA256 verification.
- [x] **Independent PII Audit Spot-Check Tooling (`yeb audit-pii`)**: Automated high-recall heuristic scanner with formal verification report (`reports/pii_spot_check_report.md`).
- [x] **Unified Profanity & Slur Database (`yeb profanity-check`, `yeb lexicon-stats`)**: 2,508 terms with severity ratings (1–4) and categories from 5 trusted sources.
- [x] **Internal Evaluation Difficulty & Misclassification Ranking (`yeb difficulty-ranking`)**: Hard-sample priority queue and word vulnerability index.
- [x] **Autonomous Agentic Discovery Framework (`Phase 7`)**: Implemented `ScoutAgent`, `VerifierAgent`, `GeneratorAgent`, `DiscoveryLoop`, and weekly GitHub Actions cron (`.github/workflows/agentic_discovery.yml`).
- [x] **Publication-Ready Documentation**: Completed [`docs/benchmark_card.md`](docs/benchmark_card.md), [`docs/datasheet.md`](docs/datasheet.md), and [`docs/license_audit_worksheet.md`](docs/license_audit_worksheet.md).

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

- [x] **Phase 6.1: Multi-Source Slang & Neologism Scouts (Web Crawler Subsystem)**:
  - Implemented continuous Urban Dictionary scout utilizing `UrbanDictionaryClient` (`/api/random`, daily top definitions, and targeted youth slang tag exploration).
  - Designed Reddit / Social Forum scout architecture for streaming linguistic anomalies.
  - Implemented lexical candidate extractor in `ScoutAgent`.

- [x] **Phase 6.2: Autonomous Linguistic Verification & Multi-Judge Triangulation**:
  - Implemented `VerifierAgent` classifying candidates into semantic categories (`derogatory_insult`, `slur_hate_speech`, `offensive_sexual`, `gaming_toxic`, `benign_youth_slang`).
  - Implemented severity rating engine (Level 1–4) with diagnostic rationale generation.
  - Integrated human-in-the-loop (HITL) review queue logging in discovery digest.

- [x] **Phase 6.3: Adversarial Mutation & Contrastive Minimal-Pair Generator**:
  - Implemented `GeneratorAgent` creating paired conversational contexts (benign banter vs hostile escalation).
  - Applied the 9 algospeak transformation operators (leetspeak, zero-width spaces, phonetic respellings, emojis) to synthesize evasion variants.

- [x] **Phase 6.4: Closed-Loop LLM Regression Testing & Vulnerability Re-indexing**:
  - Implemented priority hard-sample queue in `runner.py` using the **Internal Difficulty & Misclassification Ranking Index** (`difficulty.py`).
  - Automatically identifies whether new slang causes False Positive over-moderation or False Negative model blind spots.

- [x] **Phase 6.5: Automated Database Maintenance, Governance, & CI/CD Cron**:
  - Implemented `DiscoveryLoop` updating [`configs/lexicons/profanity_database.json`](configs/lexicons/profanity_database.json) and [`configs/profanity_lexicon.txt`](configs/profanity_lexicon.txt).
  - Created GitHub Actions automated workflow (`.github/workflows/agentic_discovery.yml`) to run the discovery loop on a weekly cron.
  - Automated weekly markdown discovery digests in `reports/agentic_discovery_digest.md`.
  - Added CLI command: `yeb agent-discover`.

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
