# Opus 4.6 Suggestions — YouthEscalateBench Deep Review

> **Reviewer:** Claude Opus 4.6 (Thinking)
> **Date:** 2026-08-28
> **Scope:** Full repository scan with focus on the multi-turn youth safeguarding benchmark mission.

---

## Executive Assessment

You have built an impressively comprehensive **infrastructure** — 12-stage pipeline, 21 subpackages, 146+ passing tests, 14 data sources, 9 algospeak transform families, agentic discovery, RAG, caching, Docker evaluator, and interactive dashboards. The engineering scaffolding is genuinely excellent for a research project at this stage.

However, there is a critical gap between the infrastructure and the **actual benchmark**. The repository is currently a well-built machine that has not yet produced its primary deliverable: a stress-tested multi-turn evaluation dataset with results that would be compelling for ACL/EMNLP reviewers. Below, I organize suggestions from highest to lowest impact for getting to that paper.

---

## 🔴 CRITICAL: The Multi-Turn Dataset Gap

### Problem

The current evaluation report (`reports/evaluation_report.md`) shows results on **N=20 samples** with a single "Rule Based Lexicon" scorer showing 0.000 AUPRC and an empty LLM leaderboard. The extended README shows N=20 across all models. This is orders of magnitude below what's needed for a credible benchmark paper.

The synthetic generator (`src/youth_escalate_bench/generation/generator.py`) produces dialogues from ~10 hard-coded dialogue act pools using template-based composition. While this is useful for testing the pipeline, these conversations are **not realistic enough** to serve as a publishable multi-turn benchmark. ACL/EMNLP reviewers will immediately flag:

1. Turns are sampled independently from static pools — there is no **coherent narrative arc** within a conversation.
2. The "multi-turn" property is structural (turns are ordered) but not **semantically cumulative** — turn N doesn't reference or build upon turns N-1 or N-2.
3. Escalation trajectories are **deterministic by pattern** (e.g., "gradual_escalation" always follows: banter → trash talk → targeted insult), not emergent from interaction dynamics.

### Suggestion 1: LLM-Powered Recursive Conversation Synthesis

This is the single highest-impact improvement. Replace template-composed dialogues with LLM-generated multi-turn conversations:

```
Seed Behavior (from GameTox/Cyberbullying/MinorBench)
        │
        ▼
┌─────────────────────────────────────┐
│  Frontier LLM Conversation Engine   │
│                                     │
│  System Prompt:                     │
│  "You are simulating a [Discord/    │
│  Roblox/group chat] between teens.  │
│  Generate a realistic conversation  │
│  where [scenario plan] unfolds      │
│  gradually over 6-10 turns.         │
│  Maintain speaker voice, slang,     │
│  and platform conventions."         │
│                                     │
│  Input: Scenario plan with roles,   │
│  escalation arc, onset turn, harm   │
│  type, platform style               │
│                                     │
│  Output: Multi-turn dialogue +      │
│  per-turn severity annotations      │
└─────────────────────────────────────┘
        │
        ▼
Human Validation → Quality Gate → Benchmark
```

**Concrete implementation steps:**

1. Create a new module `src/youth_escalate_bench/synthesis/llm_conversation_engine.py` that:
   - Takes a `ScenarioPlan` (you already have this schema!) and sends it to a frontier LLM (GPT-4o, Claude, Gemini) as a structured generation request.
   - Uses a two-stage prompt: first generate the scenario plan (participants, platform, escalation trajectory, onset turn), then generate the actual dialogue conditioned on that plan.
   - Enforces the balanced transition matrix constraint from `plan.md` — not every conversation should escalate.
   - Tags each generated turn with provisional severity annotations.

2. Use your existing `ScenarioPlan` dataclass and `scenario_templates.yaml` as seed inputs, but expand the template library to cover all 11 `transition_pattern` types more diversely.

3. Run the generation at scale: aim for **3,000–5,000 synthetic conversations** using at least 3 different generator LLMs (as `plan.md` requires).

4. Route all outputs through your existing pipeline (redact → thread → dedup → annotate_export → adjudicate).

**Important:** The existing `SyntheticDialogueGenerator` should be preserved as a **fast, deterministic fallback** for CI tests and pipeline validation. The LLM-powered engine is for the actual benchmark dataset.

---

### Suggestion 2: Extract Real Multi-Turn Escalation Trees from Existing Corpora

You already have two gold-standard multi-turn corpora downloaded:

| Corpus | What's There | Multi-Turn Structure |
|--------|-------------|---------------------|
| **Conversations Gone Awry (Wikipedia)** | 6,964 conversation pairs | Full reply-tree topology with personal attack annotations |
| **Conversations Gone Awry (CMV)** | 6,842 conversation pairs | Reddit tree structure with toxicity onset labels |

These are **exactly** the organic escalation trajectories your plan calls for. But the current adapter registry maps these through `GenericConversationAdapter`, which doesn't exploit their tree structure.

**Concrete implementation:**

1. Create `src/youth_escalate_bench/adapters/convokit.py` — a dedicated ConvoKit adapter that:
   - Parses the ConvoKit JSON format (speakers, utterances, conversations).
   - Reconstructs full reply trees preserving `parent_turn_id` relationships.
   - Extracts the `conversation_has_personal_attack` / `comment_has_personal_attack` labels and maps them to your severity taxonomy.
   - Identifies the **onset turn** — the first turn where toxicity emerges — which is critical for your RQ2 (onset detection delay).

2. Similarly, for Davidson and WikiConv, extract any parent-chain metadata (`in_reply_to`, `parent_id`) that currently exists in the raw data but is being discarded by flat adapters.

3. The ConvoKit corpora alone should give you ~4,000 real multi-turn conversations with organic escalation trajectories. Combined with synthetic, this gets you near the 12,000-conversation target in `plan.md`.

---

### Suggestion 3: Profanity Lexicon → Conversational Corpora Semantic Join

Your third proposed strategy — filtering massive conversation corpora (Persona-Chat, WildChat, LMSYS-Chat) for emergence of profane unigrams and extracting multi-turn windows — is very doable with your existing infrastructure:

1. The `FlatToMultiTurnJoiner` (`src/youth_escalate_bench/adapters/joiner.py`) already has the skeleton for this, but it currently creates **synthetic scaffolds** around flat seeds rather than **extracting real windows**.

2. **Modify the joiner** to operate in "window extraction" mode:
   - Load a large dialog corpus (WildChat, LMSYS-Chat) as a flat stream of multi-turn conversations.
   - For each conversation, scan for the emergence of any term from your 2,508-term `profanity_database.json`.
   - When a term appears at turn `t`, extract the window `[t-k, t+k]` (e.g., k=3) as a standalone conversation.
   - This preserves the **organic conversational context** around the profanity emergence.

3. The lexicon matching should be fuzzy — use your existing algospeak transforms in reverse as a normalization layer to catch obfuscated variants.

**Tip:** LMSYS-Chat-1M has a license restriction against dataset transfer, but your `source_registry.yaml` already has it marked as "approved" for "personal non-commercial research." Verify this carefully — you may need to only publish derived labels + loader scripts, not the text itself.

---

## 🟠 HIGH PRIORITY: Evaluation Framework Gaps

### Suggestion 4: The N=20 Problem — Scale Up Evaluation Immediately

The most visible credibility gap is the N=20 sample size in all reported results. Even for a development run:

- **Minimum for development:** N=500 with `--mode medium --seed 42`
- **Minimum for paper draft:** N=2,000+ with `--mode large`
- **Full benchmark run:** N=5,000+ with `--mode extra-large` or custom `--max-samples`

The pipeline is already built to handle this. The bottleneck appears to be:
1. API tokens (the free OpenRouter models have rate limits).
2. The evaluation results currently showing in `README_extended.md` appear to be from a single small test run.

**Immediate action:** Run `python main.py --all --mode large --seed 42 --extended-report` with your configured API keys and update the reports.

---

### Suggestion 5: Add the Missing Evaluation Tracks

`plan.md` specifies **four independently scored tracks**, but only one is implemented:

| Track | Status | Implementation Gap |
|-------|--------|-------------------|
| ✅ Current-turn moderation | Implemented | Working via `ContextCondition` |
| ❌ Conversation onset detection | **Not implemented** | Need to run model after every turn and measure first detection |
| ❌ Two-turn escalation forecasting | **Not implemented** | Need forecast mode at prefix `1..t` for turns `t+1, t+2` |
| ⚠️ Robustness / temporal drift | Partially implemented | Algospeak transforms exist but not systematically evaluated as clean/perturbed pairs |

**For onset detection**, the infrastructure is nearly there:
- `build_requests_for_conversation()` already generates one `InferenceRequest` per turn.
- You need a new method `evaluate_onset_detection()` that:
  1. Runs the model incrementally at each turn.
  2. Records the first turn where `harm_probability >= threshold`.
  3. Computes delay = `first_detection_turn - gold_onset_turn`.
  4. Reports the metrics already defined in your plan: median delay, % ever detected, cumulative detection curves.

**For two-turn forecasting:**
- Create a new `TaskType.ESCALATION_FORECAST` in your schema.
- At each prefix `1..t`, the model predicts whether severity ≥ 2 will emerge at `t+1` or `t+2`.
- This is separate from current-harm detection to prevent conflation.

The evaluation report (`reports/evaluation_report.md`) already has Section 5 "Conversation Onset Detection Dynamics" with placeholder dashes — the reporting infrastructure is waiting for the data.

---

### Suggestion 6: Adversarial Algospeak Evaluation as Clean/Perturbed Pairs

Your `plan.md` specifies that robustness should be measured by comparing model performance on **paired clean and transformed versions** of the same text. But currently:

- The `transform` stage applies algospeak mutations to text but doesn't maintain the pairing in the evaluation.
- There's no metric for **transformation retention** (transformed AUPRC / clean AUPRC) or **pair consistency** (% of pairs receiving the same decision).

**Implementation:**

1. In the evaluate stage, for each evaluation example, also generate its transformed counterpart(s) using the 9 algospeak families.
2. Score both versions with every scorer.
3. Compute and report:
   - `transformation_retention = AUPRC(transformed) / AUPRC(clean)`
   - `pair_consistency = count(both_correct_or_both_wrong) / total_pairs`
   - `benign_transform_fp_increase = FP_rate(transformed_benign) - FP_rate(clean_benign)`

This is one of the most novel aspects of your benchmark and would strongly distinguish it from ToxiGen, HateCheck, and similar single-turn benchmarks.

---

## 🟡 IMPORTANT: LLM Evaluation Expansion

### Suggestion 7: Prioritize Safety-Specialized Models

The current evaluation includes general-purpose LLMs via OpenRouter free tier. For a compelling benchmark paper, you need to include the **models that people actually use for moderation**:

**Tier 1 — Must Have (open, free to run locally):**
- `meta-llama/Llama-Guard-3-8B` — Meta's dedicated safety classifier
- `meta-llama/Llama-Guard-3-1B` — Lightweight variant
- `allenai/wildguard` — Allen AI's safety model
- `google/shieldgemma-9b` — Google's safety model

These can be run locally via Ollama (you already have Ollama integration in your LLM router). They don't require API keys or tokens.

**Tier 2 — Should Have (commercial APIs, need budget):**
- `Perspective API` (Google Jigsaw) — The industry standard for toxicity scoring. Free API with rate limits.
- `OpenAI /v1/moderations` — Free moderation endpoint, no billing required.
- `Azure AI Content Safety` — Microsoft's moderation API.

**Tier 3 — Nice to Have (if funding is available):**
- `gpt-4o` / `gpt-4o-mini` via OpenAI
- `claude-3-5-sonnet` via Anthropic
- `gemini-2.0-flash` via Google

**Tip:** Perspective API and OpenAI Moderations are both **free** and would immediately add two industry-standard baselines to your results. Creating adapters for these should be high priority.

### Suggestion 8: Create a Perspective API Adapter

```python
# src/youth_escalate_bench/baselines/perspective.py

class PerspectiveAPIScorer(ModerationScorer):
    """Google Jigsaw Perspective API baseline scorer."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.endpoint = "https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze"
    
    def predict(self, request: InferenceRequest) -> ModelOutput:
        text = request.turns[-1].text  # current turn
        # Perspective API call with TOXICITY, SEVERE_TOXICITY, 
        # IDENTITY_ATTACK, INSULT, PROFANITY, THREAT attributes
        ...
```

This would give you the single most important industry baseline — the one that every reviewer will expect to see.

---

## 🟢 CODE QUALITY & ARCHITECTURE IMPROVEMENTS

### Suggestion 9: Fix the Hardcoded Profanity Detection in Generator

In `src/youth_escalate_bench/generation/generator.py`, profanity form is determined by a naive substring check:

```python
profanity_form=ProfanityForm.LITERAL
if any(w in text.lower() for w in ["shit", "fuck", "bitch", "ass"])
else ProfanityForm.NONE,
```

This appears in **6 separate locations** across the file. Problems:
1. Only checks 4 words against a 2,508-term database.
2. `"ass"` matches "class", "assert", "passage", etc.
3. Doesn't use the `ProfanityDatabase` you've already built.

**Fix:** Extract a utility function that uses your existing database:

```python
from youth_escalate_bench.external.profanity_sources import ProfanityDatabase

_db = ProfanityDatabase.load_json(Path("configs/lexicons/profanity_database.json"))

def detect_profanity_form(text: str) -> ProfanityForm:
    """Check text against the full profanity database with word-boundary matching."""
    words = set(re.findall(r'\b\w+\b', text.lower()))
    if words & _db.term_set:
        return ProfanityForm.LITERAL
    return ProfanityForm.NONE
```

---

### Suggestion 10: The `print()` vs `structlog` Inconsistency

The evaluation runner (`src/youth_escalate_bench/evaluation/runner.py`) mixes `print()` statements (lines 254–273) with `structlog` logging. The print statements are for the deduplication gate output. This should be consistent — use `structlog` or `click.echo()` throughout, especially since this code runs within a CLI tool.

---

### Suggestion 11: Redundant `import structlog` in Evaluation Runner

In `src/youth_escalate_bench/evaluation/runner.py`, `structlog` is imported twice:
- Line 179: `import structlog`
- Line 245: `import structlog` (again, inside the same function)

Remove the duplicate.

---

### Suggestion 12: Thread-Safety Issue in Evaluation Scoring

In the `run_evaluation()` function, the `ThreadPoolExecutor` closure captures `scorer` by reference:

```python
for scorer_name, scorer in scorers.items():
    def _score_one(pair):
        req, label = pair
        out = scorer.predict(req)  # captures 'scorer' from outer loop
        return req, label, out
    
    with ThreadPoolExecutor(max_workers=8) as pool:
        scored = list(pool.map(_score_one, pairs))
```

The `scorer` variable in the closure will capture the **last value** of `scorer` if the ThreadPoolExecutor outlives the loop iteration. In this case it's likely fine because `pool.map()` is called within the same iteration, but it's fragile. Fix with a default argument:

```python
def _score_one(pair, _scorer=scorer):
    req, label = pair
    out = _scorer.predict(req)
    return req, label, out
```

---

### Suggestion 13: Missing `__all__` Exports in Key Modules

Several public-facing modules lack `__all__` declarations. This matters for:
- IDE autocompletion for users of your library
- Clean namespace when doing `from youth_escalate_bench.evaluation import *`
- Documentation generators

Priority modules: `evaluation/`, `transforms/`, `baselines/`, `schemas/`.

---

### Suggestion 14: Harden the PII Redaction Pipeline

The current PII redaction uses regex-based heuristics. For a benchmark that will be publicly released, consider:

1. Adding a second-pass NER detector (spaCy `en_core_web_sm` or Presidio) as `plan.md` requires ("two independent PII detectors").
2. Adding detection for Discord-style usernames (`username#1234`), Roblox usernames, and platform-specific identifiers.
3. The `audit-pii` command already exists — make it a **mandatory pipeline gate** rather than an optional audit.

---

## 🔵 DATASET & CONTENT IMPROVEMENTS

### Suggestion 15: Expand Algospeak Coverage with Generation-Year Terminology

Your `EUPHEMISM_MAP` in `src/youth_escalate_bench/transforms/algospeak.py` is a good start but is missing many current (2024–2026) youth platform evasion terms. Consider adding:

| Surface Form | Meaning | Platform |
|-------------|---------|----------|
| `accountant` | sex worker | TikTok |
| `camping` | hate crime | TikTok |
| `le dollar bean` | lesbian | TikTok |
| `mascara` | SA/assault | TikTok |
| `b00ks` / `books` | offensive slur | Roblox |
| `leg ends` | slur | Roblox |
| `ice cream` | drugs | Discord |
| `pdf file` | predator | Cross-platform |
| `devious lick` | theft/vandalism | TikTok/School |
| `glazing` | excessive praise (sarcastic bullying) | Gaming/Discord |
| `cooked` | ruined/destroyed | Gaming |
| `rizz` (negative) | creepy behavior | Gen Z cross-platform |

Your `agentic_discovery` pipeline should be periodically mining these, but having a curated seed set from known platforms is essential for the paper's algospeak section.

---

### Suggestion 16: Add Platform-Specific Conversation Templates

Your `scenario_templates.yaml` covers gaming chat, group chat, DMs, and forums. But for a youth-specific benchmark, you should add scenarios modeled after:

1. **Roblox chat** — character limits, filtered words auto-replaced with `####`, very young demographics
2. **Discord server moderation evasion** — users referencing deleted messages, using nicknames to mock
3. **TikTok/Instagram comment threads** — parasocial dynamics, hate raids, coordinated dogpiling
4. **School group chats (WhatsApp/iMessage)** — private context, screenshot threats, exclusion dynamics
5. **Streaming chat (Twitch/YouTube Live)** — fast-moving, emoji spam, emote-based harassment

Each platform has distinctive conversational norms that affect how escalation unfolds.

---

### Suggestion 17: Add Sexualized Harassment and Self-Harm Encouragement Dialogue Pools

The current dialogue act pools in the generator cover targeted insults, threats, and exclusion well. But two critical harm types from your taxonomy are underrepresented:

1. **Sexualized harassment** (`HarmType.SEXUALIZED_HARASSMENT`) — no dedicated dialogue pool exists.
2. **Self-harm encouragement** (`HarmType.SELF_HARM_ENCOURAGEMENT`) — partially covered by "unalive" euphemisms but no realistic conversational scenarios.

These are exactly the categories where youth-specific benchmarks differ most from adult-centric ones, and where existing benchmarks have the biggest gaps. Adding carefully constructed (and ethically reviewed) scenario templates for these would strengthen the paper's novelty claim.

**Caution:** Self-harm encouragement content requires extra care — ensure it goes through your annotator wellness protocol and IRB review before inclusion. The content should be realistic enough for evaluation but should not serve as a how-to guide.

---

## 📐 EVALUATION METRICS & STATISTICAL RIGOR

### Suggestion 18: Add Bootstrap Confidence Intervals

Your `plan.md` specifies "95% confidence intervals using 10,000 stratified bootstrap samples" but the current `compute_binary_metrics()` returns point estimates only. For a credible paper submission:

1. Implement conversation-level (not turn-level) bootstrapping — conversations are the independent units.
2. Report CIs on AUPRC, AUROC, and all derived metrics.
3. Use paired bootstrap tests when comparing two models.

This is non-negotiable for ACL/EMNLP.

---

### Suggestion 19: Add Calibration Metrics

Your plan specifies "Brier score and expected calibration error" but these aren't implemented. Well-calibrated probabilities are especially important for moderation systems because:
- A moderator needs to trust that a 0.8 harm probability actually means ~80% chance of harm.
- Overconfident models (high accuracy, poor calibration) are dangerous in production.

Add to `metrics/detection.py`:
```python
def compute_calibration_metrics(y_true, y_score, n_bins=10):
    """Compute ECE and Brier score."""
    brier = mean((y_score - y_true) ** 2)
    # Bin predictions and compute |avg_predicted - avg_actual| per bin
    ece = sum(|bin_confidence - bin_accuracy| * bin_weight)
    return {"brier_score": brier, "ece": ece}
```

---

### Suggestion 20: Add Per-Harm-Type Disaggregated Results

The current evaluation computes metrics across all examples. But for the paper, you need breakdowns by:
- Harm type (9 categories)
- Severity level (4 levels)
- Platform style (4 types)
- Source tier (organic vs. synthetic vs. functional)
- Context dependence (invariant vs. amplified vs. flipped)

This is where the most interesting findings will come from — e.g., "LLMs detect explicit insults at 0.95 AUPRC but miss covert exclusion at 0.42 AUPRC."

---

## 📝 PUBLICATION READINESS

### Suggestion 21: The README Metrics Don't Match Reality

The `README_extended.md` reports "12 models and baselines" in the evaluation, but the actual evaluation report shows only 1 model with 0.000 AUPRC. The README should reflect current state, not aspirational state. This matters for reproducibility — anyone who clones and runs will see the discrepancy.

**Fix:** Either clearly label the README results as "preliminary development results" or re-run the full evaluation and update.

---

### Suggestion 22: Create a LaTeX Paper Skeleton

You have `reports/table_main_results.tex` but no paper skeleton. For ACL/EMNLP submission, create a `paper/` directory with:
- `paper/main.tex` — ACL 2025 format paper skeleton
- `paper/figures/` — symlinked to `reports/` generated figures
- `paper/tables/` — auto-generated from evaluation results
- `paper/references.bib` — BibTeX with all cited works

Having the paper structure early forces you to identify what results you actually need.

---

### Suggestion 23: Missing Comparison to Existing Benchmarks

For a benchmark paper, you need a **Related Work table** comparing YouthEscalateBench to:

| Benchmark | Multi-Turn | Youth-Specific | Algospeak | Causal Eval | Context-Aware Labels | # Conversations |
|-----------|-----------|---------------|-----------|-------------|---------------------|----------------|
| ToxiGen | ❌ | ❌ | ❌ | ❌ | ❌ | 0 |
| HateCheck | ❌ | ❌ | Partial | ❌ | ❌ | 0 |
| RealToxicityPrompts | ❌ | ❌ | ❌ | ❌ | ❌ | 0 |
| SimpleSafetyTests | ❌ | ❌ | ❌ | ❌ | ❌ | 0 |
| Dynabench Hate | ❌ | ❌ | ❌ | ❌ | ❌ | 0 |
| Conv. Gone Awry | ✅ | ❌ | ❌ | Partial | ❌ | 6,842 |
| **YouthEscalateBench** | ✅ | ✅ | ✅ | ✅ | ✅ | 12,000 (target) |

This table should appear in Section 2 of your paper.

---

## 🔧 INFRASTRUCTURE & DEVOPS

### Suggestion 24: Add a Makefile or Task Runner

The project has many entry points (`python main.py`, `yeb pipeline`, `yeb serve`, `pytest`, `scripts/download_datasets.py`). A `Makefile` would consolidate common workflows:

```makefile
.PHONY: download evaluate report test lint serve

download:
	python scripts/download_datasets.py --all

evaluate:
	python main.py --all --mode medium --seed 42 --extended-report

report:
	python main.py --step report --extended-report --force

test:
	pytest tests -v --cov=youth_escalate_bench

lint:
	ruff check src tests

serve:
	yeb serve --host 127.0.0.1 --port 8080
```

---

### Suggestion 25: Pin Dependency Versions for Reproducibility

`pyproject.toml` uses minimum version pins (`pydantic>=2.7`, `polars>=1.0`). For reproducible benchmark results, create a `requirements.lock` or use `uv lock` to pin exact versions. This is especially important because:
- `polars` has breaking API changes between minor versions.
- `numpy` 2.0 changed default dtypes.
- `matplotlib` rendering can differ between versions (your figures should be pixel-reproducible).

---

### Suggestion 26: Add Data Version Control (DVC) Pipeline Execution

You have a `dvc.yaml` file but it's not clear if it's being used. Wire up the DVC pipeline to track:
- Raw data downloads (inputs)
- Processed parquet files (outputs per stage)
- Evaluation results and reports

This gives you full data lineage tracking, which is important for the "every headline result reproducible from immutable manifests" requirement in `plan.md`.

---

## 📋 PRIORITIZED ACTION PLAN

If I were to rank the top 10 actions by impact-to-effort ratio for getting to an ACL/EMNLP paper:

| Priority | Suggestion | Impact | Effort |
|----------|-----------|--------|--------|
| 1 | **#2: Extract real multi-turn trees from Conversations Gone Awry** | 🔴 Critical | Medium (new adapter) |
| 2 | **#4: Scale evaluation to N≥500 immediately** | 🔴 Critical | Low (just run it) |
| 3 | **#1: LLM-powered conversation synthesis** | 🔴 Critical | High (new module + API costs) |
| 4 | **#7+8: Add Perspective API + OpenAI Moderations baselines** | 🟠 High | Low (API adapter) |
| 5 | **#5: Implement onset detection track** | 🟠 High | Medium (new eval mode) |
| 6 | **#6: Paired clean/transformed robustness evaluation** | 🟠 High | Medium (new metrics) |
| 7 | **#18: Bootstrap confidence intervals** | 🟡 Important | Low (statistical code) |
| 8 | **#3: Lexicon→corpus semantic join for window extraction** | 🟡 Important | Medium (modify joiner) |
| 9 | **#20: Per-harm-type disaggregated results** | 🟡 Important | Low (groupby in reporting) |
| 10 | **#22: LaTeX paper skeleton** | 🟡 Important | Low (template + wiring) |

---

> **Note:** The repository is in an excellent architectural state. The primary gap is not engineering — it's **data at scale** and **evaluation breadth**. The infrastructure can support 100x the current evaluation volume; the bottleneck is executing the data construction strategies outlined in `26-Profanity-Detection.md` and running evaluations with enough models and samples to produce publishable results.
