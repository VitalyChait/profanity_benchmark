Plan
YouthEscalateBench: Dynamic Multi-Turn Youth-Safeguarding Benchmark
1. Research Objective and Contributions
Objective
Build a causally evaluated benchmark for determining whether moderation systems can detect harmful peer-to-peer interactions as they emerge across multi-turn, youth-oriented conversations—especially when profanity, slang, emojis, code-switching, and algospeak obscure the harm.

The benchmark evaluates moderation detection, not chatbot refusal or response generation. Every prediction must use only the conversation prefix available at that moment; future turns are never exposed.

Intended contributions
A multi-turn benchmark distinguishing isolated profanity from contextual cyberbullying, harassment, threats, identity attacks, sexualized harassment, and encouragement of self-harm.
A causal early-detection protocol measuring when a system first recognizes an escalating interaction.
Paired context-free and context-aware evaluation showing when history amplifies, mitigates, or reverses a moderation decision. Prior work found that context can reverse toxicity judgments, motivating explicit context-dependent labels rather than simply prepending earlier messages (Pavlopoulos et al., 2020).
A controlled algospeak and evasion suite containing semantic-preserving transformations, benign controls, compositional attacks, and new transformation families held out from development.
A dynamic quarterly evaluation protocol for measuring performance decay as youth language evolves, following the model-in-the-loop motivation of Dynabench while preserving a stable anchor set.
An ethically governed, versioned, machine-readable benchmark, evaluator, model registry, and private test server suitable for a NeurIPS Evaluations & Datasets submission.
Primary research questions
RQ1: How much does causal conversation context improve detection of actionable harm relative to classifying the current turn alone?
RQ2: How many turns after the gold harm onset do moderation systems require before raising an alert?
RQ3: Can systems forecast escalation within the next two turns without producing excessive false alarms?
RQ4: How robust are systems to algospeak and multimethod obfuscation when meaning is preserved?
RQ5: Do models confuse benign profanity, quotations, reclaimed expressions, identity mentions, and friendly banter with abuse?
RQ6: How quickly does performance decay on newly emerging coded language?
RQ7: Which failures arise from language understanding, context use, calibration, or policy-taxonomy mismatch?
Preregistered hypotheses
H1: Full causal history will significantly improve AUPRC on context-dependent examples but may not improve aggregate performance.
H2: Semantic-preserving evasion will reduce detection performance, with larger losses for composed transformations than single transformations.
H3: Context-aware systems will improve onset detection but may increase false alarms during benign banter.
H4: Performance will be lower on expressions first observed after each model’s documented training cutoff.
H5: Specialized moderation models will be better calibrated than general instruction LLMs, while general LLMs may perform better on implicit and context-dependent harm.
Null and negative findings remain valid outcomes; publication claims must not depend on finding large model failures.

2. Benchmark Contract
Evaluation tracks
Implement four independently scored tracks:

Current-turn moderation

Input: either the current turn alone or the complete causal prefix.
Output: harm probabilities, harm categories, severity, target type, and supporting turn identifiers.
Purpose: isolate the value of context.
Conversation onset detection

Run the model after every turn.
Detect the first turn at which severity becomes actionable.
Measure missed events and delay after the gold onset.
Two-turn escalation forecasting

At prefix $1..t$, predict whether actionable harm will emerge during turns $t+1$ or $t+2$.
Keep this separate from current-harm detection to prevent claims of “early detection” when the model merely recognizes already-explicit abuse.
Robustness and temporal drift

Evaluate clean/perturbed pairs, unseen transformation families, new slang snapshots, and code-switch examples.
Report robustness separately from ordinary predictive performance.
Input schema
Each inference request contains:

benchmark_version
conversation_id
current_turn_id
platform_style: gaming chat, group chat, direct messaging, or forum thread
language_mode: English or English-led code-switch
turns: ordered records containing turn_id, pseudonymous speaker_id, role, text, and coarse relative time
task: current harm, onset detection, or two-turn forecast
Do not expose source, gold labels, transformation metadata, exact timestamps, demographic assumptions, or future turns.

Required model output
Use strict JSON:

harm_probability: float in [0,1]
harm_types: probability map over the benchmark taxonomy
severity_probabilities: four probabilities summing to one
target_type: probability map
escalation_state: probability map
forecast_next_two_turns: float in [0,1]
evidence_turn_ids: zero or more visible turn identifiers
abstain: boolean
Free-form chain-of-thought must neither be requested nor scored. Invalid JSON counts as abstention and is included in reliability reporting.

Annotation taxonomy
Annotate independent dimensions rather than collapsing profanity and harm:

Profanity form: none, literal, orthographically obfuscated, phonetic, euphemistic/algo-coded, acronym, emoji/rebus, or code-switched.
Pragmatic use: absent, affiliative banter, emotional emphasis, quotation/reporting, reclaimed/self-reference, targeted abuse, or ambiguous.
Harm type, multi-label: targeted insult, repeated harassment, identity attack, threat/intimidation, sexualized harassment, self-harm encouragement, exclusion/coercion, humiliation/rumor, and dogpiling/mobilization.
Target: none, self, individual peer, non-protected group, protected group, or indeterminate.
Severity: 0 benign; 1 coarse/monitor; 2 actionable intervention; 3 urgent/high-risk intervention.
Escalation transition: de-escalating, stable, escalating, or not applicable.
Context dependence: invariant, amplified, mitigated, label-flipped, or insufficient context.
Evidence: offending spans and earlier turn identifiers needed to justify the label.
Conversation-level event: first actionable turn, peak severity, repeated-target pattern, and whether de-escalation occurs.
“Harassment” requires repeated or conversation-level targeting; a single coarse statement may instead be an insult. Offline age, identity, intent, power imbalance, and threat credibility must not be inferred unless explicitly observable.

3. Data Construction
Target scale and composition
Build approximately 12,000 conversations and 80,000 usable turns:

Partition	Conversations	Intended role
Organic contextual conversations	4,000	Ecological validity
Adult-staged peer conversations	2,000	Controlled escalation and de-escalation
Human-validated synthetic conversations	3,000	Rare harms and systematic coverage
Functional/counterfactual conversations	2,000	Diagnostic and fairness tests
Quarterly live challenge	1,000	Temporal drift and contamination resistance
Report all results by source tier. Never present synthetic performance as equivalent to real-world performance.

Source policy
Create a source registry before downloading data. For every source, record its owner, version, URL, license, terms, consent basis, redistribution rights, deletion process, age evidence, PII risk, intended use, and allowed released artifacts.

Use the following hierarchy:

WikiConv/WikiDetox: primary organic conversation source because it reconstructs Wikipedia discussion structure rather than relying on flat Jigsaw rows (WikiDetox repository).
Contextual Abuse Dataset: primary expert-annotated contextual source because it includes conversation context, rationales, and group adjudication (CAD paper).
ConvoTox: conditional Reddit tree source; ingest only after written license and redistribution review. Its public description reports more than one million responses in tree structure (ConvoTox record).
GameTox: use only as a flat gaming-language seed source after explicit access and license approval. Its full dataset is currently tied to a shared task, so it must not be assumed available (GameTox repository).
MinorBench: use for taxonomy comparison only; it evaluates child-facing assistant safety rather than peer cyberbullying and is too small to provide the conversation backbone (dataset card).
Davidson: use only as an optional lexical source. Its released records are flat labeled tweets and do not provide reconstructable parent chains (repository).
WildChat: exclude from the core because the current public release removed conversations flagged as toxic (dataset card).
LMSYS-Chat-1M: exclude from redistributable benchmark data because its agreement prohibits transfer of the dataset (license and dataset card).
PersonaChat: permit only as a safe dialogue scaffold; never describe it as authentic youth or cyberbullying data.
If ConvoTox fails review, replace its 1,000-conversation quota with 500 additional WikiConv/CAD conversations and 500 adult-staged conversations. If GameTox permission is unavailable, generate scenarios from its published taxonomy rather than reproducing its examples.

Human-staged conversations
Recruit adults aged 18–24 to enact peer-chat scenario cards; do not ask minors to author harmful dialogue.
Cover gaming, class group chats, direct messages, fandom/community spaces, and forum replies.
Scenario state machines must include gradual escalation, immediate abuse, persistent low-grade harassment, de-escalation, oscillation, false alarms, friendly profanity, and bystander intervention.
Randomly assign roles and desired transition patterns. Do not prescribe exact abusive wording.
Retain source-tier metadata so staged data can be analyzed separately.
Synthetic generation
Use at least three unrelated generator families and store model/version/prompt metadata privately.

Generation proceeds in two stages:

Generate a structured scenario plan: participants, relationship, topic, harm type, intended onset, peak, de-escalation path, code-switch pattern, and platform constraints.
Generate dialogue from that plan with 4–12 turns.
Requirements:

No generator output supplies its own gold label.
Prevent artificial always-increasing toxicity by enforcing a balanced transition matrix.
Cap synthetic material at 25% of the representative hidden test.
Human reviewers must approve realism, label clarity, speaker consistency, and absence of accidental PII.
Detect near-duplicates against seeds and all splits.
Hold out one generator family from public data to measure generator-style overfitting.
Publish generation prompts and software, but not active private-test seeds.
Functional and counterfactual suite
Following the diagnostic philosophy of HateCheck, build matched pairs for:

Targeted versus non-targeted profanity.
Friendly banter versus bullying.
Quotation/condemnation versus endorsement.
Reclaimed identity language versus identity attack.
Negation and counter-speech.
Threatening idiom versus credible threat.
Identity mention without abuse.
Context that amplifies, mitigates, or flips the target-turn label.
Same surface utterance addressed to different targets.
Safe and unsafe code-switch examples.
Bystander agreement, resistance, and dogpiling.
Each pair should vary one controlled factor. Store a machine-readable minimal_pair_group_id; split entire groups together.

Algospeak and evasion transformations
Build deterministic, versioned transformation operators:

Character substitution, leetspeak, homoglyphs, spacing, punctuation insertion, repeated characters, casing, and zero-width characters.
Phonetic respelling and syllable splitting.
Acronyms, clipped forms, euphemisms, coded nouns, emoji substitution, and rebuses.
Code-switch substitution and transliteration.
Contextual substitution where a benign word becomes harmful only through shared conversational meaning.
Composition depths of one, two, and three transformations.
Apply transformations to matched safe and unsafe examples. Otherwise models can learn that any obfuscation implies harm.

Every transformed item requires semantic-equivalence review:

Three adult annotators independently compare clean and transformed meaning.
Retain only items with unanimous harm-label preservation for the robustness set.
Put meaning-changing transformations into a separate control set.
Hold out at least two transformation families and all newly harvested terms from public development data.
4. Annotation, Ethics, and Quality Control
Youth participation default
Assume IRB-approved co-design with 8–12 consented participants aged 13–17:

Obtain guardian consent and youth assent.
Youth advisors review sanitized platform scenarios, naturalness, and contemporary language interpretations.
They must not produce explicit abuse, inspect severe sexual content, or assign moderation labels.
All harmful-content annotation is performed by trained adults.
If IRB approval is unavailable, replace the youth panel with 18–24-year-old advisors and narrow claims from “authentic youth speech” to “youth-oriented communication settings.”
The benchmark must be distinguished from YouthSafe, which studies youth–AI interaction risks; this work concerns causal moderation of peer-to-peer escalation (YouthSafe paper).

Annotation process
Convene a taxonomy panel consisting of a cyberbullying researcher, trust-and-safety practitioner, developmental/youth-safety expert, linguist, and annotation lead.
Annotate a 500-conversation pilot.
Revise guidelines through disagreement analysis, not model performance.
Triple-annotate every turn and conversation.
Expert-adjudicate:
All hidden-test data.
All severity-3 cases.
All disagreements involving severity 0 versus 2/3.
All context-flip examples.
All code-switch and novel-algospeak examples.
Allow explicit “insufficient context” and “ambiguous” decisions rather than forcing false certainty.
Preserve individual labels privately so disagreement can be modeled rather than discarded.
Quality gates
Krippendorff’s alpha at least 0.80 for four-level severity after guideline stabilization.
Alpha at least 0.67 for each harm type with prevalence above 2%; also report positive and negative agreement for rare labels.
At least 90% agreement on actionable versus non-actionable harm.
At least 90% of synthetic examples rated plausible and internally consistent.
Any failed gate triggers guideline revision and full reannotation of the affected batch.
Gold attention checks must measure guideline comprehension, not agreement with a model.
Model-assisted labeling may prioritize examples but may never determine final gold labels.
Safety and privacy
Obtain IRB/ethics determination before recruitment or new data collection.
Do not scrape private Discord, Roblox, school, or minor-only spaces.
Never infer that a public account belongs to a minor.
Exclude CSAM, explicit sexual depictions involving minors, credible ongoing emergencies, doxxing, and recoverable private identifiers.
Run two independent PII detectors followed by human review; remove usernames, links, locations, contacts, and exact timestamps.
If any critical PII appears in the independent release audit, stop release and rerun redaction over the complete corpus.
Give annotators informed warnings, paid breaks, exposure limits, opt-out rights, wellness resources, and no-penalty reassignment.
Provide takedown and deletion procedures; propagate source deletions into the next release through tombstone records.
Release text only when redistribution is permitted. Otherwise release source identifiers plus reproducible loaders or derived labels, subject to source terms.
5. Splitting, Leakage Control, and Dynamic Evolution
Fixed release split
For the initial 11,000 non-live conversations:

5,000 public authoring/train examples.
2,000 public development examples.
2,000 private representative-test examples.
2,000 private diagnostic-test examples.
The additional 1,000 conversations form the quarterly live challenge.

Group-split by original thread, author pseudonym where permitted, seed record, semantic cluster, minimal-pair group, scenario template, and synthetic generation lineage. Apply chronological splitting wherever source timestamps exist.

Leakage checks:

Exact normalized-text hashes.
Character and token MinHash.
Embedding-neighbor review.
Template and transformation-lineage matching.
Search for public benchmark phrases in generated outputs.
Zero shared source threads or counterfactual groups across splits.
Representative versus diagnostic scoring
Preserve naturally observed class prevalence in the representative test.
Use sampling weights when rare examples are oversampled for annotation.
Balance the diagnostic test across behaviors, context dependence, and transformation types.
Never combine both tracks into an opaque single leaderboard score.
Quarterly dynamic cycle
Each live version contains:

250 unchanged private anchor conversations.
375 newly validated natural or staged conversations.
250 newly observed algospeak/evasion examples.
125 adversarial examples created against the previous leaderboard’s strongest systems.
Monthly candidate discovery may use licensed public sources, expert nominations, youth-advisory sanitized submissions, character-level novelty, embedding drift, and rapid frequency growth. All candidates receive human semantic validation.

Versioning rules:

Use semantic dataset versions such as 1.0.0, 1.1.0, and 2.0.0.
Never silently edit released labels; issue a correction manifest.
Report current-version scores and anchor-equated longitudinal scores.
Retire live examples after two cycles or 12 months, whichever is later.
Release retired examples and labels when licensing and safety permit.
Recalculate model rankings per version; do not treat scores from different unanchored versions as directly comparable.
6. Models and Experimental Matrix
Baselines
Evaluate:

Raw profanity lexicon matcher.
Normalized lexicon matcher.
Character n-gram TF-IDF logistic regression.
Fine-tuned encoder classifier trained only on public training data.
One widely used toxicity classifier.
At least three open specialized safeguard models.
Six open instruction LLMs spanning:
At least three model families.
Two models at or below 10B parameters.
Three models between 20B and 40B or equivalent active parameters.
One model at or above 70B or equivalent.
One closed moderation API and one frontier closed LLM only if funding and zero-retention terms are available.
At experimental freeze, select the newest eligible model releases, pin exact revisions and licenses, and preregister the panel before viewing hidden labels. Main claims must remain valid without proprietary systems.

Evaluation conditions
Run every eligible model under:

Current turn only.
Previous turn plus current turn.
Full causal prefix.
Full prefix truncated to the model’s context window.
Raw input.
Oracle-normalized input as a diagnostic upper-bound.
Zero-shot fixed policy prompt.
Five-shot prompt using public development examples only.
Use temperature zero and deterministic decoding where supported. Repeat nondeterministic API configurations three times. Record tokenizer, prompt, quantization, hardware, seed, latency, token counts, cost, invalid-output rate, and model release/training-cutoff information.

Ablations
Remove speaker identifiers.
Shuffle preceding turns while retaining the current turn.
Remove profanity tokens.
Remove non-profane contextual cues.
Vary context window length.
Compare clean and transformed items.
Compare natural, staged, synthetic, and functional sources.
Exclude each harm category in turn from examples shown in prompts.
Compare systems with and without explicit youth-oriented moderation policy wording.
7. Metrics and Statistical Analysis
Primary metrics
AUPRC for actionable harm (severity >= 2) on the representative track.
Macro-AUPRC across harm types.
Recall at 95% precision and recall at 1% false-positive rate.
Detection recall at 0, 1, and 2 turns after gold onset.
False escalation alerts per 1,000 safe prefixes.
Secondary metrics
Macro/micro F1 using thresholds locked on public development data.
AUROC, precision, recall, and confusion matrices.
Ordinal severity weighted kappa.
Brier score and expected calibration error.
Selective risk versus coverage when abstention is allowed.
Evidence-turn precision/recall.
Invalid-output rate, latency, throughput, and monetary cost.
Context and robustness metrics
Context gain: paired difference between full-prefix and current-turn-only AUPRC.
Context harm: rate at which context changes a correct isolated decision into an incorrect contextual decision.
Transformation retention: transformed AUPRC divided by clean AUPRC.
Pair consistency: percentage of clean/transformed pairs receiving the same actionable-harm decision.
Benign transformation false-positive increase.
Temporal decay: anchor-adjusted score slope versus expression age and benchmark version.
Event timing
For each harmful conversation, define onset as the first adjudicated severity-2/3 turn.

Time-to-detection is the first threshold-crossing turn at or after onset minus onset.
Report median delay only alongside the percentage of conversations ever detected.
Treat misses as censored failures and plot cumulative detection curves.
Forecast lead time is reported only when a correct alert occurs before onset.
Report false forecasts on conversations that never reach actionable harm.
Statistical protocol
Use the conversation, not the turn, as the resampling unit.
Report 95% confidence intervals using 10,000 stratified bootstrap samples.
Use paired bootstrap tests for model and context comparisons.
Control planned comparison false discovery rate with Benjamini–Hochberg at 0.05.
Run a pilot-based simulation to verify at least 90% power for detecting a 0.03 paired AUPRC difference; increase relevant hidden-test strata if necessary without inspecting system results.
Publish all preregistered comparisons and label exploratory analyses explicitly.
Report results by source tier, harm type, severity, platform style, context dependence, transformation depth, code-switch status, and temporal bucket.
8. Engineering and Execution
Repository architecture
Use Python 3.12 with uv, Parquet storage, Pydantic/JSON Schema contracts, Polars/DuckDB ETL, DVC pipeline versioning, pytest, containerized inference, and immutable content hashes.

Implement these stages:

source_audit: produce signed source and license registry.
ingest: import each source through an isolated adapter.
redact: remove PII and prohibited content.
thread: reconstruct and validate conversation topology.
sample: apply quotas and source-aware selection.
stage_generate: create staged/synthetic scenario material.
transform: generate paired algospeak and adversarial variants.
annotate_export: create annotation packets and import judgments.
adjudicate: resolve required cases and freeze gold labels.
split: group-aware, chronological, contamination-checked splitting.
evaluate: causal prefix inference, validation, scoring, and bootstrap analysis.
report: create paper tables, benchmark cards, datasheets, and error-analysis bundles.
Every stage must accept a versioned YAML configuration, fixed random seed, input manifest, and output manifest containing row counts and SHA-256 hashes. A clean checkout must reproduce all redistributable artifacts with one documented command.

Private evaluator
Open-model submissions use OCI containers implementing a documented /predict interface.
Run submitted containers with networking disabled, read-only hidden data, CPU/GPU/time quotas, and output-size limits.
Closed-model evaluations are executed by maintainers through adapters under zero-retention/no-training API settings.
Rate-limit submissions by team and model revision.
Store immutable model, prompt, environment, benchmark-version, and result manifests.
Run canary and duplicate submissions to detect nondeterminism or benchmark extraction attempts.
Publish detailed public-development reports but only aggregate private-test slice metrics.
Keep private texts out of ordinary application logs and telemetry.
Timeline and gates
Weeks 1–4: governance and source audit

Ethics submission, source registry, threat model, taxonomy draft.
Gate: no source enters the pipeline without documented legal status.
Weeks 5–8: pilot

Build 500 conversations, validate schemas, run triple annotation.
Gate: agreement and privacy thresholds met.
Weeks 9–16: construction

Organic ingestion, staged collection, synthesis, transformations, deduplication.
Gate: quota, topology, semantic-equivalence, and source-diversity checks pass.
Weeks 17–22: production annotation

Triple annotation, adjudication, PII audit, split freeze.
Gate: all hidden-test examples adjudicated and all critical PII checks clear.
Weeks 23–27: model evaluation

Preregister model panel and hypotheses, execute inference, perform error analysis.
Gate: deterministic reruns reproduce scores within tolerance.
Weeks 28–32: dynamic evaluator and publication

Launch private server, complete first live snapshot, artifact review, paper and documentation.
Required personnel
Principal investigator.
NLP/evaluation lead.
Data engineer.
Annotation and wellness lead.
Youth-safety/developmental expert.
Trust-and-safety practitioner.
12–20 trained adult annotators.
8–12 youth advisors under approved safeguards.
Independent privacy/license reviewer before release.
9. Testing and Acceptance Criteria
Pipeline tests
Schema validation for every conversation, turn, label, and prediction.
Conversation topology, role ordering, and causal-prefix tests.
No future-turn exposure during inference.
Transformation determinism and Unicode normalization tests.
Split leakage and semantic-neighbor tests.
Source-license allowlist enforcement.
PII regression suite.
Invalid model-output and abstention handling.
Metric tests against hand-calculated fixtures.
Bootstrap reproducibility.
Container isolation, timeout, and network-denial tests.
Full miniature end-to-end pipeline in continuous integration.
Release acceptance
Approximately 12,000 conversations and at least 75,000 accepted turns.
Zero source-thread, seed-group, or minimal-pair leakage across splits.
One hundred percent source-registry coverage.
One hundred percent expert adjudication for private tests.
Agreement gates satisfied.
Zero critical PII findings in the independent audit.
Every headline result reproducible from immutable manifests.
All source-tier and synthetic-data limitations clearly reported.
Public code, executable evaluator, example data, data card, benchmark card, Croissant metadata, and Responsible-AI fields available at submission. These are particularly important because NeurIPS 2026 requires executable benchmark code and Croissant/RAI metadata for relevant submissions (official call).
Include a small inspectable sample if protected or large data cannot be directly distributed.
10. Assumptions and Defaults
Version 1 evaluates English plus a smaller naturally occurring English-led code-switch slice.
The missing 600K-record corpus is not a dependency. When available, it enters only through the same provenance, license, quality, deduplication, and split controls.
The default full design uses IRB-approved youth co-design, adult harmful-content annotators, roughly 12,000 conversations, and a hybrid public/private benchmark.
No claims are made that all examples were authored by minors; provenance tiers remain explicit.
Text-only communication is in scope for version 1. Images, audio, video, and platform-network metadata are deferred.
The benchmark evaluates detection and forecasting, not automated punishment or intervention policy.
Closed APIs are optional secondary comparisons; open and reproducible baselines carry the primary scientific conclusions.
Dataset text retains source-specific licensing. Code should use a permissive license, while data loaders and manifests enforce the restrictions of each underlying source.
