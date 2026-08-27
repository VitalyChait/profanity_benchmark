# YouthEscalateBench: Dynamic Multi-Turn Youth-Safeguarding Benchmark

[![CI](https://github.com/VitalyChait/profanity_benchmark/actions/workflows/ci.yml/badge.svg)](https://github.com/VitalyChait/profanity_benchmark/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: >=3.12](https://img.shields.io/badge/Python->=3.12-brightgreen.svg)](https://www.python.org/)
[![Tests: 144 Passed](https://img.shields.io/badge/Tests-144%20Passed-success.svg)](tests/)
[![Coverage: 81%](https://img.shields.io/badge/Coverage-81%25-informational.svg)](tests/)

**YouthEscalateBench** is a research-grade, causal evaluation benchmark designed to assess whether automated moderation systems and frontier Large Language Models (LLMs) can reliably detect harmful peer-to-peer interactions as they emerge across multi-turn, youth-oriented conversations—especially when profanity, slang, emojis, code-switching, and algospeak obscure the harm.

Unlike traditional single-turn moderation benchmarks that rely on adult-centric policies (e.g., explicit violence, weapons, or hate slurs in isolation), YouthEscalateBench focuses on the real-world dynamics of adolescent digital communication: distinguishing **affiliative banter from targeted harassment**, tracking **gradual interpersonal escalation**, and maintaining **robustness against adversarial algospeak evasion**.

---

## 📑 Table of Contents

1. [Research Objectives & Goals](#-research-objectives--goals)
2. [What Has Already Been Achieved](#-what-has-already-been-achieved)
3. [System Architecture & 12-Stage Pipeline](#-system-architecture--12-stage-pipeline)
4. [Annotation Taxonomy & Schema Contracts](#-annotation-taxonomy--schema-contracts)
5. [Evaluation Results & Key Findings](#-evaluation-results--key-findings)
6. [How to Run & Quickstart Guide](#-how-to-run--quickstart-guide)
7. [Automated Infographics & Dashboard](#-automated-infographics--dashboard)
8. [Docker Evaluator Microservice](#-docker-evaluator-microservice)
9. [Next Steps & Future Roadmap](#-next-steps--future-roadmap)
10. [Repository Structure & Documentation Index](#-repository-structure--documentation-index)

---

## 🎯 Research Objectives & Goals

Standard toxicity benchmarks assess safety using isolated turns. They fail in youth environments due to two fundamental challenges:
1. **Adolescent Linguistic Evolution & Algospeak**: Youth continuously alter vocabulary to bypass automated filters (e.g., *"unalive"*, *"newspaper eat"*, zero-width spaces, leetspeak substitutions).
2. **Context-Dependent Escalation**: Cyberbullying builds across conversational turns; words that appear benign in isolation may constitute targeted harassment when viewed in sequence, while explicit profanity often functions as harmless peer bonding or playful teasing.

### Primary Research Questions (RQs)
- **RQ1 (Causal Context Sensitivity)**: How much does full causal conversation history improve actionable harm detection relative to classifying the current turn alone?
- **RQ2 (Onset Detection Delay)**: How many turns after gold harm onset do moderation systems require before raising an alert?
- **RQ3 (Escalation Forecasting)**: Can models forecast interpersonal escalation within the next two turns ($t+1, t+2$) without producing excessive false alarms?
- **RQ4 (Algospeak Evasion Robustness)**: How robust are LLMs against semantic-preserving obfuscation transforms?
- **RQ5 (Benign Profanity Disambiguation)**: Do models erroneously penalize benign swearing, third-party quotations, and affiliative banter?
- **RQ6 (Temporal Linguistic Decay)**: How quickly does moderation accuracy decay on newly emerging coded expressions?
- **RQ7 (Failure Mode Attribution)**: Which errors arise from language understanding, context integration, or policy mismatch?

---

## 🏆 What Has Already Been Achieved

- [x] **Full 12-Stage Pipeline Executed on Real-World Data**: Ingested and threaded 14 diverse public research corpora and lexicons (79,000+ turns) into unified Parquet representations.
- [x] **Unified Profanity & Slur Database**: 2,508 terms with severity ratings (1–4) compiled across 5 trusted sources (Google, dsojevic, LDNOOBW, HurtLex, HateCheck).
- [x] **Active Difficulty Ranking & Priority Queue**: Evaluates LLMs preferentially on historically misclassified turns and vulnerable vocabulary.
- [x] **Autonomous Agentic Discovery Framework**: Continuous Urban Dictionary scout, linguistic verifier, contrastive minimal-pair generator, and weekly GitHub Actions workflow.
- [x] **Multi-LLM Causal Evaluation**: Evaluated 12 models and baselines across 3 causal context conditions (`Isolated Turn`, `Local Context`, `Full Prefix`).
- [x] **14 LLM Providers Supported**: Integrated with OpenRouter, Mistral, OpenAI, Anthropic, Gemini, Groq, DeepSeek, Together, Ollama, and local models.
- [x] **Automated Infographics Generation**: High-resolution 300 DPI publication figures (multi-panel benchmark comparisons, AUPRC heatmaps, context trajectories, and dark-mode interactive HTML dashboards).
- [x] **Turn-by-Turn Failure Case Diagnostics (`--extended-report`)**: Automated extraction of every False Positive and False Negative with exact turn text, dialogue context, and diagnostic rationales.
- [x] **100% Test Suite Pass Rate**: 144+ automated unit, integration, schema, causal, agentic, and e2e tests passing in CI.
- [x] **Quarterly Live Snapshot Tooling (`yeb create-snapshot`)**: Bundles versioned release archives with Croissant metadata and SHA256 verification.
- [x] **Independent PII Audit Spot-Check (`yeb audit-pii`)**: Automated high-recall heuristic scanner with formal verification report (`reports/pii_spot_check_report.md`).
- [x] **Air-Gapped Evaluator Microservice**: Sandboxed Docker container (`docker/evaluator/Dockerfile`) with HTTP `/predict` contract for zero-leakage offline scoring.
- [x] **Comprehensive Documentation Package**: Datasheet for Datasets, Benchmark Card, Threat Model, IRB Ethics Package, Annotator Wellness Protocol, and OSF Preregistration specification.

---

## 🔄 System Architecture & 12-Stage Pipeline

The benchmark is organized as a sequential, deterministic 12-stage pipeline managed by [`main.py`](main.py):

```
+---------------------------------------------------------------------------------------------------+
|                                  YouthEscalateBench Pipeline                                      |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [1. source_audit]     Automated legal and licensing compliance gate                              |
|          │                                                                                        |
|  [2. ingest]           Raw corpus normalization (10 datasets -> unified Parquet)                  |
|          │                                                                                        |
|  [3. redact]           Automated regex/heuristic PII sanitization (emails, IPs, handles)          |
|          │                                                                                        |
|  [4. thread]           Graph-based conversational tree topology & causal chronological ordering   |
|          │                                                                                        |
|  [5. stage_generate]   Synthetic escalation simulations & minimal-pair scenario generation        |
|          │                                                                                        |
|  [6. transform]        9-family semantic-preserving algospeak obfuscation suite                   |
|          │                                                                                        |
|  [7. sample]           Demographic & platform quota balancing with MinHash deduplication          |
|          │                                                                                        |
|  [8. annotate_export]  Annotation packet export for human annotators and LLM judges               |
|          │                                                                                        |
|  [9. adjudicate]       Consensus majority-vote adjudication & gold freeze manifest export         |
|          │                                                                                        |
|  [10. split]           Train / Dev / Test split generation with zero-leakage verification         |
|          │                                                                                        |
|  [11. evaluate]        Multi-model evaluation across 3 context conditions + onset dynamics       |
|          │                                                                                        |
|  [12. report]          Automated markdown reports, LaTeX tables, infographics & HTML dashboard    |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

---

## 🏷️ Annotation Taxonomy & Schema Contracts

The benchmark decouples profanity from harm across independent orthogonal dimensions:

- **Profanity Form**: `none`, `literal`, `orthographically_obfuscated`, `phonetic`, `euphemistic_algocoded`, `acronym`, `emoji_rebus`, `code_switched`.
- **Pragmatic Use**: `absent`, `affiliative_banter`, `emotional_emphasis`, `quotation_reporting`, `reclaimed_self_reference`, `targeted_abuse`, `ambiguous`.
- **Harm Types (Multi-label)**: `targeted_insult`, `repeated_harassment`, `identity_attack`, `threat_intimidation`, `sexualized_harassment`, `self_harm_encouragement`, `exclusion_coercion`, `humiliation_rumor`, `dogpiling_mobilization`.
- **Severity Levels**: `0: benign`, `1: coarse_monitor`, `2: actionable`, `3: urgent`.
- **Escalation Transition**: `de_escalating`, `stable`, `escalating`, `not_applicable`.
- **Context Dependence**: `invariant`, `amplified`, `mitigated`, `label_flipped`, `insufficient_context`.

---

## 📊 Evaluation Results & Key Findings

### Multi-Model Performance Matrix across Context Conditions

| Model / Scorer | Family | Turn Only AUPRC (AUROC) | Prev + Turn AUPRC (AUROC) | Full Prefix AUPRC (AUROC) | $\Delta$ AUPRC | N |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Gemma 4 26B A4B IT (Free)** | `OpenRouter LLM` | 0.867 (0.961) | 0.867 (0.961) | **0.867** (0.961) | 0.000 | 20 |
| **Gemma 4 31B (Default Judge)** | `LLM Judge` | 1.000 (1.000) | 1.000 (1.000) | **0.806** (0.961) | **-0.194** | 20 |
| **Gemma 4 31B IT (Free)** | `OpenRouter LLM` | 1.000 (1.000) | 1.000 (1.000) | **0.806** (0.961) | **-0.194** | 20 |
| **Nemotron 3.5 Safety (Free)** | `OpenRouter LLM` | 0.500 (0.843) | 0.500 (0.843) | **0.500** (0.843) | 0.000 | 20 |
| **Dots 3 Note Preview (Free)** | `OpenRouter LLM` | 0.500 (0.843) | 0.500 (0.843) | **0.500** (0.843) | 0.000 | 20 |
| **Liquid LFM 2.5 2.6B (Free)** | `OpenRouter LLM` | 0.500 (0.843) | 0.500 (0.843) | **0.500** (0.843) | 0.000 | 20 |
| **Ensemble Moderator** | `Ensemble` | 0.532 (0.882) | 0.532 (0.882) | **0.532** (0.882) | 0.000 | 20 |
| **Char N-Gram TF-IDF** | `Subword Baseline` | 0.810 (0.922) | 0.810 (0.922) | **0.810** (0.922) | 0.000 | 20 |
| **Raw Lexicon Match** | `Lexical Baseline` | 0.778 (0.882) | 0.778 (0.882) | **0.778** (0.882) | 0.000 | 20 |
| **Normalized Lexicon** | `Lexical Baseline` | 0.778 (0.882) | 0.778 (0.882) | **0.778** (0.882) | 0.000 | 20 |
| **Full-Context Lexicon** | `Lexical Baseline` | 0.778 (0.882) | 0.778 (0.882) | **0.778** (0.882) | 0.000 | 20 |
| **Rule Safeguard Expert** | `Rule Baseline` | 0.500 (0.843) | 0.500 (0.843) | **0.500** (0.843) | 0.000 | 20 |

---

## 🚀 How to Run & Quickstart Guide

### 1. Installation

Clone the repository and install the development dependencies:

```bash
git clone https://github.com/VitalyChait/profanity_benchmark.git
cd profanity_benchmark
pip install -e ".[dev]"
```

### 2. Configure LLM API Keys (Optional)

Copy the environment template and set your API keys:

```bash
cp .env.example .env
# Edit .env and insert your OPENROUTER_API_KEY, OPENAI_API_KEY, etc.
```

Inspect detected providers:
```bash
yeb llm-status
```

### 3. Running the Pipeline via `main.py`

```bash
# Run the full pipeline from start to finish:
python main.py --all

# Run pipeline with extended turn-by-turn failure case logging:
python main.py --all --extended-report

# Auto-resume from earliest incomplete checkpoint:
python main.py --resume

# Run a specific step (e.g. report) with force re-execution:
python main.py --step report --extended-report --force

# Inspect checkpoint status:
python main.py --status

# Reset all checkpoints:
python main.py --reset
```

### 4. Running the Test Suite

```bash
pytest tests -v --cov=youth_escalate_bench --cov-report=term-missing
ruff check src tests
```

---

## 🎨 Automated Infographics & Dashboard

Every run of the `report` stage automatically produces visual analytics in [`data/processed/report/`](data/processed/report/):

1. **Multi-Panel Overview** (`infographic_models_comparison.png`): High-res 4-panel publication comparison of AUPRC, AUROC, context delta, and precision-recall trade-offs.
2. **Performance Heatmaps** (`figure_auprc_heatmap.png`): AUPRC and AUROC matrix across all models $\times$ conditions.
3. **Causal Trajectory Curves** (`figure_context_trajectory.png`): Performance progression as context expands.
4. **LLM Leaderboard Bar Chart** (`figure_llm_leaderboard.png`): Ranked bar chart of all evaluated LLMs.
5. **Interactive Dashboard** (`infographic_dashboard.html`): Self-contained dark-mode dashboard with KPI cards and interactive tables.

---

## 🐳 Docker Evaluator Microservice & Interactive Web Dashboard

For air-gapped zero-leakage evaluations, production chat moderation, or interactive visual analysis:

```bash
# Build image
docker build -t youth-escalate-evaluator -f docker/evaluator/Dockerfile .

# Run in air-gapped mode (network disabled)
docker run --rm -p 8080:8080 --network none youth-escalate-evaluator
```

Or run directly with the CLI:
```bash
yeb serve --host 127.0.0.1 --port 8080
```

### 📊 Real-Time Service Analysis Dashboard
Navigate to **`http://localhost:8080/dashboard`** (or `http://localhost:8080/`) to interactively analyze benchmark results:
- **Visual Analytics**: Interactive 300 DPI heatmaps, causal trajectory curves, and leaderboard charts.
- **Turn-by-Turn Failure Inspector**: Search and filter false positives (over-moderation) vs. false negatives (missed harm) with full dialogue context and diagnostic rationales.
- **Hard-Sample Ranking Explorer**: Inspect hardest conversational turns and top trigger words sorted by error rate.
- **Live Prediction Playground**: Interactively enter conversation turns and submit live requests to `POST /predict`.
- **REST Endpoints**: `/health`, `/api/summary`, `/api/errors`, `/api/difficulty`.

### Send a `POST /predict` inference request:
```bash
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{
    "benchmark_version": "0.1.0",
    "conversation_id": "conv_demo_01",
    "current_turn_id": "t2",
    "platform_style": "gaming_chat",
    "language_mode": "english",
    "task": "current_harm",
    "turns": [
      {"turn_id": "t1", "speaker_id": "p1", "role": "user", "text": "Push mid lane now.", "relative_time": "0s"},
      {"turn_id": "t2", "speaker_id": "p2", "role": "user", "text": "uninstall the game trash kid", "relative_time": "+5s"}
    ]
  }'
```

See [`docker/evaluator/README.md`](docker/evaluator/README.md) for full documentation and Python client examples.

---

## 🔭 Next Steps & Future Roadmap

As tracked in [`TODO.md`](TODO.md):

1. **Human Annotator Pilot**: Onboard 3–5 annotators and verify agreement quality ($\alpha \ge 0.80$, $\ge 90\%$ actionable agreement) on a 500-conversation pilot batch.
2. **Institutional Review Board (IRB) Review**: Formally submit [`docs/irb_ethics_package.md`](docs/irb_ethics_package.md) to the university review board.
3. **Expanded Model Benchmarking**: Evaluate open guardrails (`Llama-Guard 3`, `WildGuard`, `ShieldGemma`) and commercial APIs (`Perspective API`, `Azure Content Safety`).
4. **Conference Paper Submission**: Finalize camera-ready LaTeX tables (`table_main_results.tex`) and figures for submission to ACL / EMNLP / NeurIPS.
5. **Post-Benchmark Research Tracks**:
   - **Track 2 (Activation Steering)**: Training-free representation engineering to eliminate false positives in benign peer banter.
   - **Track 3 (Real-Time De-escalation)**: On-the-fly conversational intervention translating hostile provocation into constructive communication.

---

## 📁 Repository Structure & Documentation Index

```text
profanity_benchmark/
├── configs/                   # Stage configurations & source registry
│   ├── source_registry.yaml   # Legal provenance & license catalog (10 datasets)
│   ├── profanity_lexicon.txt  # Curated baseline profanity lexicon
│   └── stages/                # YAML configs for all 12 pipeline stages
├── data/
│   ├── raw/                   # Raw downloaded public research corpora
│   ├── processed/             # Clean Parquet outputs per pipeline stage
│   └── checkpoints/           # Resumable pipeline checkpoint states
├── docker/                    # Containerization infrastructure
│   ├── evaluator/             # Private HTTP /predict evaluator container
│   │   ├── Dockerfile         # Evaluator Dockerfile
│   │   └── README.md          # Evaluator operational user manual
│   └── README.md              # Container infrastructure overview
├── docs/                      # Scientific, legal & ethical documentation
│   ├── annotation_guidelines_v0.1.md  # Detailed human annotation protocol
│   ├── annotator_wellness_protocol.md # Annotator safety & mental wellness
│   ├── benchmark_card.md              # NeurIPS / ACL benchmark card
│   ├── datasheet.md                   # Gebru et al. Datasheet for Datasets
│   ├── irb_ethics_package.md          # IRB ethics submission package
│   ├── license_audit_worksheet.md     # Source legal status & license worksheet
│   ├── preregistration.md             # OSF preregistration specification
│   ├── threat_model.md                # Adversarial evasion threat model
│   └── youth_advisory_protocol.md     # Adolescent co-design protocol
├── src/youth_escalate_bench/  # Core Python package
│   ├── adapters/              # Dataset ingestion adapters
│   ├── baselines/             # 7 baseline moderation scorers
│   ├── dedup/                 # Vectorized MinHash & LSH banding
│   ├── evaluation/            # Causal multi-context evaluation runner
│   ├── generation/            # Synthetic scenario generator
│   ├── io/                    # High-performance Parquet IO
│   ├── llm/                   # Multi-provider LLM router & key validation
│   ├── metrics/               # AUPRC, AUROC, agreement & onset dynamics
│   ├── orchestrator/          # Checkpoint state manager & CLI runner
│   ├── pii/                   # Automated PII redaction pipeline
│   ├── reporting/             # Automated infographics & visual analytics
│   ├── schemas/               # Pydantic schema contracts
│   ├── split/                 # Zero-leakage train/dev/test splitter
│   ├── stages/                # 12 pipeline stage implementations
│   └── transforms/            # 9-family algospeak obfuscation operators
├── tests/                     # 74 automated unit, integration, and e2e tests
├── main.py                    # Main pipeline orchestrator entrypoint
├── pyproject.toml             # Package dependencies and build configuration
├── plan.md                    # Canonical research plan & specification
├── TASKS.md                   # Phase execution tracker
└── TODO.md                    # Master pre-release TODO and roadmap
```
