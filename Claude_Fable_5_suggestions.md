# Next Plan: Closing the Gap to Idea 1 (Multi-Turn Youth-Safeguarding Benchmark)

**Primary goal (from `26-Profanity-Detection.md` §Idea 1):** Build a **multi-turn** evaluation framework that measures how quickly moderation LLMs detect **escalating** youth-oriented toxicity/profanity—especially under **algospeak**—rather than treating toxicity as a single-turn adult hate-speech problem.

**Venue target:** ACL / EMNLP (flagship NLP). Secondary fit: NeurIPS Datasets & Benchmarks if the living evaluator + Croissant/RAI artifacts are hardened.

**Canonical scientific contract:** `plan.md` (YouthEscalateBench). This file is an **execution plan**: what to do next, in what order, and why—based on a full-repo scan. It does **not** replace `plan.md`.

**Honest status (do not trust `TODO.md` “100% complete” claims):** The repository is a strong **engineering scaffold and dry-run**. Schemas, pipeline stages, LLM harness, transforms, and dashboard exist. The scientific backbone of Idea 1—**real multi-turn sources at plan quotas, human gold, scored robustness/forecast/live tracks**—is still incomplete. Current ~0.99 AUPRC headlines on auto-generated labels are **not publication-ready**.

---

## 1. Goal Restatement → Deliverables

| Idea 1 requirement | Publication deliverable |
|---|---|
| Multi-turn escalation / early detection | Causal prefix eval + onset metrics with human gold onset turns |
| Youth / algospeak robustness | Scored clean↔perturbed pairs + held-out transform families + temporal slang slice |
| Transform corpus into dynamic multi-turn framework | Versioned public/private splits + quarterly live challenge (not a static train dump) |
| Synthetic seed expansion (GameTox / cyberbullying / MinorBench) | Licensed seeds → human-validated synthetic dialogues, reported **by source tier** |
| Organic trees (Wiki / reply parents) | WikiConv/CAD (or CGA trees) as primary organic tier; no fake “youth” claims |
| Lexicon join to chat corpora | Windows around profanity emergence in allowed scaffolds (PersonaChat-style), with license gates |
| Evaluate open LLMs ± context ± evasion | Preregistered panel, bootstrap CIs on **conversations**, context gain + transformation retention |
| Optional ChatGPT if results promising | Secondary closed-API panel only after open baselines are solid |

**Non-goals for the next 8–12 weeks (park Ideas 2–3):** representation steering and live de-escalation rewrite engines. They depend on a trustworthy bench; building them now would optimize the wrong objective.

---

## 2. Repo Reality Check (Scan Summary)

### What is already strong
- **12-stage pipeline** with manifests, seeds, schemas, causal no-lookahead contracts (`src/youth_escalate_bench/`).
- **Taxonomy** matching `plan.md` (profanity form, pragmatic use, harm types, severity, escalation, context dependence).
- **Three context conditions:** `current_turn_only`, `prev_plus_current`, `full_prefix`.
- **Algospeak operators** (9 families) + large transform pair store (~175k pairs).
- **LLM multi-provider eval** (~38 scorers × 3 conditions on n≈1000 in latest runs) + baselines (lexicon / TF-IDF / rules / ensemble).
- **Onset metric code** (`metrics/onset.py`) and some onset YAML outputs.
- **Governance docs drafts** (IRB package, threat model, datasheet, source registry, wellness, youth advisory).
- **Evaluator + dashboard** (`yeb serve`) for analysis and demos.
- **Agentic slang discovery + lexicon DB** (~2.5k terms) as living-bench scaffolding.

### What blocks Idea 1 scientifically
1. **Wrong data mix for the claim.** Ingest is dominated by flat/single-utterance toxicity (Dynabench, Davidson, HateXplain, TweetEval) plus some CGA threads. Plan primaries (WikiConv, CAD, GameTox, ConvoTox) are mostly **adapters + fixtures**, not production ingest. PersonaChat / WildChat-style joins are coded but not evidenced in the live source mix. WildChat/LMSYS redistribution constraints in `plan.md` are not fully reconciled with registry “approved” notes.
2. **Quota failure vs plan.** Sampled ~5,004 convs / ~13,018 turns vs ~12k / ~80k. Staged **0/2000**, live **0/1000**, synthetic short (~980/3000), functional token (~20/2000).
3. **Gold is synthetic / auto-adjudicated**, not triple human annotation with IAA gates (α≥0.80, actionable agreement ≥90%).
4. **Robustness track not scored.** Transforms exist; evaluate does not publish transformation retention, pair consistency, or benign-control FP lift as first-class results.
5. **Forecast track is schema-only.** Two-turn escalation forecasting is not a scored evaluation path.
6. **Living quarterly challenge not running.** Snapshot CLI exists; live set composition (anchor / new slang / algospeak / adversarial) does not.
7. **Ceiling effects.** Near-perfect AUPRC + strong rule_based_safeguard on auto labels ⇒ label leakage / easy proxies / overfit to generation templates.
8. **Internal docs overclaim.** `TODO.md` / README “100%” language conflicts with `plan.md` gates and raw provenance.

---

## 3. Strategic Principle: Fix Cause, Not Symptom

Do **not** next prioritize: more dashboard polish, more frontier API keys, or another 38-model sweep on the current gold.

Do **next** prioritize, in order:

1. **Legal + provenance gate** for every source you will cite in the paper.
2. **Real multi-turn backbone** (organic trees + controlled staged/synthetic escalation).
3. **Human gold pilot** (500 convs) with agreement gates—or stop and redesign labels.
4. **Hard eval tracks** that match Idea 1 claims (onset, context gain, algospeak retention).
5. **Only then** scale LLM evaluation and write results tables.

If step 3 fails agreement, the entire paper narrative collapses; treat that as a go/no-go.

---

## 4. Phased Next Plan (Detailed)

### Phase A — Paper Contract Freeze (3–5 days)

**Goal:** One page that prevents scope creep and overclaiming.

**Actions**
1. Write `docs/paper_contract_idea1.md` locking:
   - Claims allowed: multi-turn causal detection; context gain; onset delay; algospeak robustness; source-tier reporting.
   - Claims forbidden: “authentic minor-authored chat” unless provenance supports it; “training corpus of 600K” as a dependency (`plan.md` already says it is not required).
   - Primary metrics: AUPRC(severity≥2), onset recall@lag0/1/2, context gain, transformation retention.
2. Reconcile `configs/source_registry.yaml` with `plan.md` exclusions (WildChat toxic-stripped release; LMSYS transfer ban). Mark each source: `ingest_allowed`, `redistribute_allowed`, `cite_only`, `seed_taxonomy_only`.
3. Demote optimistic checklists: add a banner to `TODO.md` / README that **engineering completeness ≠ scientific readiness**.
4. Preregister draft hypotheses H1–H5 already in `plan.md` into a short OSF/anonymous prereg stub (even if private).

**Exit criteria**
- Source allowlist signed (even if informal PI sign-off).
- Paper claim list ≤ 5 bullets; every bullet maps to a metric + split.

---

### Phase B — Source Acquisition & Organic Multi-Turn Backbone (2–4 weeks)

**Goal:** Make dataset construction match Idea 1’s three strategies—with licenses.

#### B1. Organic trees (highest ecological validity)
| Source | Action | Notes |
|---|---|---|
| **WikiConv / WikiDetox / CGA-Wiki** | Prefer full conversation trees over flat Jigsaw rows | You already have CGA Wiki/CMV volume; strengthen topology QA and youth-peer **relevance filters** (do not invent ages). |
| **Contextual Abuse Dataset (CAD)** | Obtain + ingest for real | Primary expert contextual source in `plan.md`; currently fixture-level. |
| **ConvoTox** | License review **before** bulk ingest | If blocked, execute plan fallback quotas (more Wiki/CAD + staged). |
| **Davidson** | Lexical / optional only | Do **not** claim reply trees; tweets are flat. |

#### B2. Seed → synthetic expansion (coverage of rare harms)
| Source | Action | Notes |
|---|---|---|
| **GameTox** | Access/license or taxonomy-only scenarios | Do not copy shared-task examples without permission. |
| **Cyberbullying / peer-abuse seeds** | Curate a small licensed seed bank | Use as `stage_generate` scenario seeds, not as “youth ground truth.” |
| **MinorBench** | Taxonomy comparison only | Wrong task (assistant vs child), too small for backbone. |

**Synthetic protocol (must change)**
1. Seed → scenario plan → multi-turn dialogue (Discord/Roblox/group-chat styles).
2. **Human validation rate:** start at 100% of pilot synth; later ≥30% spot-check + all severity≥2.
3. Always report synth results **separately** from organic (Idea 1 + `plan.md` both require this).

#### B3. Lexicon semantic join → chat scaffolds
1. Run join only on **license-safe** dialogue scaffolds (PersonaChat/ConvAI2-style as **safe scaffolds**, never as youth cyberbullying truth).
2. Filter conversations where curated profanity unigrams emerge; extract windows of ±k turns.
3. **Exclude or carefully gate** WildChat/LMSYS per `plan.md`; if used for private analysis only, never redistribute.
4. Output a `join_windows` manifest: source, window ids, match terms, severity prior, license tag.

#### B4. Quota rebuild
Rebuild `sample` to approach:

| Tier | Target (plan) | Immediate interim target (8 weeks) |
|---|---|---|
| Organic contextual | 4,000 | ≥2,000 high-quality trees |
| Adult-staged peer | 2,000 | ≥300 pilot staged |
| Human-validated synthetic | 3,000 | ≥500 validated |
| Functional / counterfactual | 2,000 | ≥200 diagnostic pairs |
| Quarterly live | 1,000 | ≥100 dry-run live |

**Exit criteria**
- `quota_report.yaml` shows staged>0 and live≥100 (dry-run) or an explicit deferral note in the paper contract.
- Zero “fixture-only” sources cited as ingested in the paper.
- Every conversation has `source_tier`, `platform_style`, `license_tag`.

---

### Phase C — Human Gold Pilot (Weeks overlapping B; gate at 500 convs)

**Goal:** Prove labels are learnable by humans and hard for lexicon shortcuts.

**Actions**
1. File / advance **IRB** using `docs/irb_ethics_package.md` (currently draft-only).
2. Recruit adult annotators under `docs/annotator_wellness_protocol.md` (start 3–6 people, not 20).
3. Annotate **500 conversations** with the full taxonomy; require evidence turn ids + first actionable turn.
4. Measure:
   - Severity ordinal agreement (target α≥0.80).
   - Actionable (sev≥2) pairwise agreement ≥90% after adjudication.
   - Lexicon baseline AUPRC on this pilot gold (expect **far below** 0.99).
5. Run one open LLM + rule_based_safeguard on the same pilot; if both still near ceiling, **labels or sampling are broken**—debug before scaling.

**Adjudication**
- Triple annotate severity + harm types for severity≥1 and all context-dependent items.
- Expert adjudicate 100% of private-test candidates.

**Exit criteria (go/no-go)**
- Agreement gates met **or** taxonomy simplified with documented reason.
- Lexicon AUPRC on pilot gold < 0.70 (indicative; exact threshold set in prereg).
- Onset defined and stable for ≥80% of actionable conversations.

---

### Phase D — Make Idea 1 Evaluation Tracks Real (2–3 weeks after pilot gold)

#### D1. Current-turn ± context (already coded — re-run on human gold)
Publish:
- AUPRC / recall@FPR=1% / recall@P=95%.
- **Context gain** = full_prefix − turn_only (paired bootstrap on conversations).
- **Context harm** = correct→incorrect flips when context is added.

#### D2. Onset / early detection (code exists — elevate to headline)
Publish:
- Detection recall @ lag 0/1/2.
- Median delay **among detected**, plus % never detected.
- Cumulative detection curves; treat misses as censored.

Current onset numbers on auto gold (detection_rate ~0.15) already suggest the task is hard—**recompute on human gold** before interpreting.

#### D3. Algospeak robustness (biggest Idea 1 gap in scoring)
Implement evaluate track `robustness`:
1. Sample clean/perturbed pairs with **human semantic-equivalence** pass (start N=500 pairs).
2. Hold out ≥2 transform families from development (compositional + one novel family).
3. Metrics:
   - Transformation retention = AUPRC_perturbed / AUPRC_clean.
   - Pair consistency (% same actionable decision).
   - Benign-control false-positive increase (algospeak on safe text).
4. Apply transforms to **both** safe and unsafe (exactly as Idea 1 asks).

#### D4. Two-turn forecast (optional for v1 paper, required for full plan)
- If timeline tight for ACL/EMNLP: move to appendix / v1.1.
- If included: separate head, never conflate with current-harm detection.

#### D5. Baselines that make a fair story
Add at least:
- Character TF-IDF / lexicon (already).
- One fine-tuned encoder on **public train only**.
- One open safety specialist (Llama-Guard / WildGuard / ShieldGemma class)—listed as TODO historically.
- Prompted general LLMs (already).
- Optional Perspective/API moderators as secondary.

**Exit criteria**
- One `evaluation_results` artifact where every headline metric is computed on **human** (or human-adjudicated) labels.
- Robustness table appears in the main paper outline.
- No result claimed without conversation-level 95% bootstrap CIs.

---

### Phase E — Scale LLM Evaluation (only after D)

**Actions**
1. Freeze model panel + prompts + decoding + date in a manifest.
2. Evaluate open/reproducible models first (primary scientific claims).
3. Use difficulty / stratified sampling so n=1000 is not the easy head of the distribution.
4. Error analysis slices: FP on banter/reclaimed/quoted profanity; FN on implicit escalation; algospeak misses; context flips.
5. If open models show clear, non-saturated signal → request funded ChatGPT/Claude closed-API add-on (Idea 1’s optional funding path).

**Exit criteria**
- Deterministic rerun within tolerance.
- Failure case dump non-empty and aligned with `reports/` (avoid empty overwrite bugs already partially fixed).

---

### Phase F — Living / Dynamic Slice (parallel, smaller)

Idea 1 asks for a **dynamic** framework, not only a static test set.

**Minimum viable living bench**
1. Keep a **250-conversation anchor** frozen across versions.
2. Each quarter (or monthly dry-run): 100–250 new slang / algospeak items from agentic discovery + human verify.
3. Publish anchor-adjusted Δ metrics (temporal decay).
4. `yeb create-snapshot` becomes a real release ritual with changelog + SHA256 + Croissant.

Do not wait for perfect living protocol to submit v1, but include **one** live dry-run in the paper as proof of concept.

---

### Phase G — Paper, Artifacts, Evaluator Hardening (final 3–4 weeks)

**Paper structure (ACL/EMNLP-oriented)**
1. Problem: adult single-turn tox ≠ youth multi-turn escalation + algospeak.
2. Benchmark contract + taxonomy.
3. Data construction (three strategies) + ethics.
4. Tasks/metrics (context, onset, robustness).
5. Experiments on open models + baselines.
6. Error analysis + limitations (synth vs organic; no guaranteed minor authorship).
7. Release: code, sample data, cards, private test policy.

**Engineering for submission**
- Executable evaluator (`docker/evaluator`) with offline hidden test, rate limits, canaries (plan §Private evaluator).
- Datasheet + benchmark card + RAI/Croissant filled with **true** provenance (no overclaim).
- Fix remaining dashboard correctness issues only as needed for reviewers (`PROMPTS_TODO.md`).

---

## 5. Priority Queue (What To Do This Week)

Ordered by impact on Idea 1:

1. **Freeze paper contract + source allowlist** (Phase A).
2. **Ingest CAD and/or expand real Wiki conversation trees**; stop citing fixture adapters as data.
3. **Resolve GameTox/ConvoTox/WildChat legal status** in writing.
4. **Launch 500-conversation human annotation pilot** (or schedule IRB blocker explicitly).
5. **Add scored robustness evaluate track** on a small clean human-validated pair set (even N=200).
6. **Recompute context + onset metrics on pilot gold**; discard saturated auto-gold leaderboards from the paper narrative.
7. **Fill staged tier** with adult-authored peer escalation scripts (even 100–300 helps the story).
8. Demote dashboard/UI work unless it blocks annotation/eval productivity.

---

## 6. Risks & Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Auto labels drive 0.99 AUPRC | False “solved” narrative; reviewers reject | Human gold pilot gate; lexicon ceiling check |
| License blocks GameTox/ConvoTox/WildChat | Construction strategy collapses | Taxonomy-only seeds; Wiki/CAD+staged fallback already in `plan.md` |
| Claiming youth authenticity without evidence | Ethics + credibility failure | Source-tier language; adult-staged; no age inference |
| Annotator harm / IRB delay | Blocks gold | Wellness protocol; start small; synthetic-heavy interim with clear limits |
| Scope creep into Idea 2/3 | Dilutes ACL story | Explicit deferral until v1 bench accepted |
| Living bench overambition | Misses conference deadline | One dry-run snapshot > perfect Dynabench clone |
| Dashboard polish as progress | Feels productive, weakens science | Cap UI time; science metrics on the critical path |

---

## 7. Success Metrics for the Next Milestone (8 weeks)

You are on track for Idea 1 if **all** hold:

- [ ] ≥2,000 organic multi-turn conversations from license-cleared tree sources in the working set.
- [ ] ≥300 adult-staged + ≥500 human-validated synthetic conversations.
- [ ] 500-conversation human pilot meets agreement gates **or** documented taxonomy revision.
- [ ] Published tables for: context gain, onset lag recalls, algospeak retention (even if N is modest).
- [ ] Lexicon / rule baselines clearly below strong LLMs **or** an explained failure mode (not silent saturation).
- [ ] Source-tier breakdown in every main result.
- [ ] Paper draft outline with limitations section that matches true provenance.
- [ ] `TODO.md` no longer claims scientific completion.

---

## 8. Suggested 8-Week Calendar

| Week | Focus | Concrete output |
|---|---|---|
| 1 | Contract + licenses + CAD/Wiki ingest plan | `paper_contract_idea1.md`, updated registry |
| 2 | Organic ingest + topology QA | New processed manifests; quota bump |
| 3 | Staged scripts + synth seed redesign | 100+ staged, 200+ validated synth |
| 4 | Annotation pilot launch | Packets + first 150 triple labels |
| 5 | Finish pilot + IAA | Go/no-go report |
| 6 | Robustness track + onset/context recompute | New eval YAML + figures |
| 7 | Open model panel on pilot/expanded gold | Leaderboard with CIs + error analysis |
| 8 | Paper outline + snapshot dry-run + residual gaps list | ACL/EMNLP skeleton + v0.2 snapshot |

---

## 9. Mapping Back to `26-Profanity-Detection.md` Bullets

| Note bullet | Next action |
|---|---|
| Escalation over turns; time-to-detection | Phase D2 onset as a **headline** metric, human gold onset |
| Algospeak evolving youth language | Phase D3 scored retention + Phase F slang snapshots |
| Dynamic framework from corpus | Versioned splits + live dry-run; not “train on 600K” |
| Synthetic from GameTox/Cyberbullying/MinorBench | Phase B2 with license-or-taxonomy-only discipline |
| Organic parent trees (Jigsaw/Davidson) | Prefer WikiConv/CAD/CGA trees; Davidson lexical-only |
| Lexicon join Persona/WildChat | Phase B3 on allowed scaffolds; gate WildChat/LMSYS |
| Rule-based algospeak on safe **and** unsafe | Explicit benign-control FP metric |
| Multi-turn toxicity turn-wise + full context | Keep 3 conditions; publish context gain/harm |
| Fund ChatGPT if promising | Phase E only after open models show non-saturated signal |

---

## 10. Optional Later Tracks (Do Not Start Now)

- **Idea 2 (steering / RepE):** Requires clean contrastive pairs and a trustworthy eval loop from Idea 1.
- **Idea 3 (de-escalation rewrite engine):** New data + LLM-as-judge protocol; orthogonal product paper.

Use Idea 1 acceptance (or a strong preprint with human gold) as the unlock condition.

---

## 11. Immediate Commands / Artifacts To Inspect While Executing

```bash
# Quotas vs plan
cat reports/data/quota_report.yaml

# What was actually ingested
ls data/raw
python -c "import pyarrow.parquet as pq; print('check ingest manifests under data/processed/ingest')"

# Current eval saturation smell-test
rg -n "auprc|AUPRC" data/processed/evaluate/evaluation_results.yaml | head

# Onset hardness
cat data/processed/evaluate/onset_metrics.yaml

# Transform volume without scored track
ls data/processed/transform
```

Keep `plan.md` as the scientific source of truth; use this file as the **next-actions backlog**.

---

## 12. Bottom Line

Your most important goal is Idea 1. The repo already gives you the **machinery**. The next plan is to replace the **demo substrate** (flat tox + synthetic gold + unscored transforms + saturated LLM tables) with a **credible multi-turn, license-clean, human-labeled, robustness-scored benchmark**—then evaluate open LLMs. Everything else (dashboard shine, more API providers, Ideas 2–3) is secondary until that substrate is real.
