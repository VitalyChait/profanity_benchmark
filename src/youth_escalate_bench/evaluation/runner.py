"""Causal evaluation runner for moderation scorers.

KEY LOCATION:
- Set LLM API keys in `.env` at repository root to evaluate frontier LLMs (OpenAI, Anthropic, Groq, Gemini).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from youth_escalate_bench.baselines.scorers import ModerationScorer
from youth_escalate_bench.evaluation.conditions import (
    ContextCondition,
    build_requests_for_conversation,
)
from youth_escalate_bench.evaluation.difficulty import (
    DifficultyIndex,
    compute_difficulty_index,
    score_request_difficulty,
)
from youth_escalate_bench.io.parquet import read_conversations
from youth_escalate_bench.metrics.detection import compute_binary_metrics
from youth_escalate_bench.schemas.conversation import ConversationRecord
from youth_escalate_bench.schemas.inference import (
    InferenceRequest,
    ModelOutput,
    PlatformStyle,
    TaskType,
    TurnRecord,
)
from youth_escalate_bench.schemas.labels import AnnotationRecord, Severity


@dataclass
class PredictionRow:
    conversation_id: str
    turn_id: str
    scorer: str
    condition: str
    harm_probability: float
    actionable: bool


@dataclass
class EvaluationResult:
    scorer: str
    condition: str
    metrics: dict
    n_samples: int


@dataclass
class EvaluationBundle:
    results: list[EvaluationResult] = field(default_factory=list)
    predictions: list[PredictionRow] = field(default_factory=list)
    difficulty_index: DifficultyIndex | None = None
    seed: int = 42
    sample_strategy: str = "auto"
    enable_rag: bool = False
    rag_compare: bool = False
    cache_stats: dict[str, Any] = field(default_factory=dict)


def select_evaluation_pairs(
    pairs: list[tuple[InferenceRequest, bool]],
    max_samples: int | None = None,
    seed: int = 42,
    difficulty_index: DifficultyIndex | None = None,
    prioritize_hard_samples: bool = True,
    sample_strategy: str = "auto",
) -> list[tuple[InferenceRequest, bool]]:
    """Deterministically select evaluation examples using a controllable seed and strategy.

    Strategies:
    - 'random': Pure seeded pseudo-random subsample. Different seeds select different examples.
    - 'stratified': Balanced sampling across actionable and benign labels using the seed.
    - 'difficulty': Prioritize hardest/misclassified examples, breaking ties deterministically via seed.
    - 'auto': Uses 'difficulty' if difficulty_index is provided and prioritize_hard_samples is True,
              otherwise falls back to seeded 'random' subsampling.
    """
    if not max_samples or len(pairs) <= max_samples:
        return pairs

    import random

    rng = random.Random(seed)

    # Strategy: pure seeded random selection
    if sample_strategy == "random" or (not prioritize_hard_samples and sample_strategy == "auto"):
        shuffled = list(pairs)
        rng.shuffle(shuffled)
        return shuffled[:max_samples]

    # Strategy: stratified (balanced actionable vs non-actionable labels)
    if sample_strategy == "stratified":
        pos = [p for p in pairs if p[1]]
        neg = [p for p in pairs if not p[1]]
        rng.shuffle(pos)
        rng.shuffle(neg)
        half = max_samples // 2
        n_pos = min(len(pos), half)
        n_neg = min(len(neg), max_samples - n_pos)
        if n_pos + n_neg < max_samples:
            if len(pos) > n_pos:
                n_pos = min(len(pos), max_samples - n_neg)
            elif len(neg) > n_neg:
                n_neg = min(len(neg), max_samples - n_pos)
        selected = pos[:n_pos] + neg[:n_neg]
        rng.shuffle(selected)
        return selected

    # Strategy: difficulty (prioritize hardest, break ties & sub-sample using controllable seed)
    if difficulty_index and prioritize_hard_samples:
        # Deterministically shuffle before stable sort so that equal-difficulty ties
        # are broken according to the controllable seed
        shuffled = list(pairs)
        rng.shuffle(shuffled)
        shuffled.sort(
            key=lambda p: score_request_difficulty(
                difficulty_index,
                p[0].conversation_id,
                p[0].current_turn_id,
                p[0].turns[-1].text if p[0].turns else "",
            ),
            reverse=True,
        )
        return shuffled[:max_samples]

    # Fallback to seeded random sample
    shuffled = list(pairs)
    rng.shuffle(shuffled)
    return shuffled[:max_samples]


def load_labels(path: Path) -> dict[tuple[str, str], bool]:
    import json

    labels: dict[tuple[str, str], bool] = {}
    if not path.exists():
        return labels
    with path.open(encoding="utf-8") as f:
        for line in f:
            raw = json.loads(line)
            ann = AnnotationRecord.model_validate(raw)
            labels[(ann.conversation_id, ann.turn_id)] = ann.severity in (
                Severity.ACTIONABLE,
                Severity.URGENT,
            )
    return labels


def run_evaluation(
    conversations: list[ConversationRecord],
    scorers: dict[str, ModerationScorer],
    labels: dict[tuple[str, str], bool],
    conditions: list[ContextCondition],
    task: TaskType = TaskType.CURRENT_HARM,
    seed: int = 42,
    threshold: float = 0.5,
    max_samples: int | None = None,
    difficulty_index: DifficultyIndex | None = None,
    prioritize_hard_samples: bool = True,
    sample_strategy: str = "auto",
    enable_rag: bool = False,
    rag_compare: bool = False,
) -> EvaluationBundle:
    from concurrent.futures import ThreadPoolExecutor

    import structlog

    eval_logger = structlog.get_logger()
    bundle = EvaluationBundle(
        seed=seed,
        sample_strategy=sample_strategy,
        enable_rag=enable_rag,
        rag_compare=rag_compare,
    )

    # Pre-collect labeled inference requests per condition with controllable seed selection
    target_requests: dict[ContextCondition, list[tuple[InferenceRequest, bool]]] = {}
    for condition in conditions:
        pairs: list[tuple[InferenceRequest, bool]] = []
        for conv in conversations:
            turn_records = [
                TurnRecord(
                    turn_id=t.turn_id,
                    speaker_id=t.speaker_id,
                    role=t.role,
                    text=t.text,
                    relative_time=t.relative_time,
                )
                for t in conv.turns
            ]
            requests = build_requests_for_conversation(
                conversation_id=conv.conversation_id,
                turns=turn_records,
                benchmark_version=conv.benchmark_version,
                platform_style=PlatformStyle(conv.platform_style),
                language_mode=conv.language_mode,
                task=task,
                condition=condition,
                seed=seed,
            )
            for req in requests:
                key = (req.conversation_id, req.current_turn_id)
                if key in labels:
                    pairs.append((req, labels[key]))

        total_candidates = len(pairs)
        selected_pairs = select_evaluation_pairs(
            pairs=pairs,
            max_samples=max_samples,
            seed=seed,
            difficulty_index=difficulty_index,
            prioritize_hard_samples=prioritize_hard_samples,
            sample_strategy=sample_strategy,
        )

        eval_logger.info(
            "evaluation_examples_selected",
            condition=condition.value,
            total_candidates=total_candidates,
            selected_count=len(selected_pairs),
            seed=seed,
            sample_strategy=sample_strategy,
            prioritize_hard_samples=prioritize_hard_samples,
        )

        target_requests[condition] = selected_pairs

    # Run predictions concurrently per scorer
    import structlog

    eval_logger = structlog.get_logger()

    from youth_escalate_bench.baselines.scorers import deduplicate_scorers

    # Deduplicate scorers targeting identical LLM models before starting evaluation
    scorers, removed_duplicates = deduplicate_scorers(scorers)
    if removed_duplicates:
        print("\n" + "=" * 72)
        print("🔍 [LLM PRE-FLIGHT DEDUPLICATION GATE] Verifying Model Targets")
        print(
            f"⚠️  Detected and removed {len(removed_duplicates)} duplicate model entries to save tokens and inference time:"
        )
        for rem in removed_duplicates:
            print(
                f"   • REMOVED : '{rem['removed_scorer']}' (targets {rem['provider']}:{rem['model']})"
            )
            print(f"     RETAINED: '{rem['retained_scorer']}'")
            print(f"     REASON  : {rem['reason']}")
            eval_logger.warning(
                "duplicate_llm_model_removed",
                removed=rem["removed_scorer"],
                retained=rem["retained_scorer"],
                provider=rem["provider"],
                model=rem["model"],
                reason=rem["reason"],
            )
        print("✅ Clean deduplicated panel ready. Proceeding to evaluation.\n" + "=" * 72 + "\n")

    for condition in conditions:
        pairs = target_requests.get(condition, [])
        if not pairs:
            continue

        eval_logger.info(
            "evaluation_sample_intake",
            condition=condition.value,
            sample_count=len(pairs),
            max_samples=max_samples,
        )

        for scorer_name, scorer in scorers.items():

            def _score_one(
                pair: tuple[InferenceRequest, bool],
            ) -> tuple[InferenceRequest, bool, ModelOutput]:
                req, label = pair
                out = scorer.predict(req)
                return req, label, out

            with ThreadPoolExecutor(max_workers=8) as pool:
                scored = list(pool.map(_score_one, pairs))

            y_true = [s[1] for s in scored]
            y_score = [s[2].harm_probability for s in scored]

            for req, _, out in scored:
                bundle.predictions.append(
                    PredictionRow(
                        conversation_id=req.conversation_id,
                        turn_id=req.current_turn_id,
                        scorer=scorer_name,
                        condition=condition.value,
                        harm_probability=out.harm_probability,
                        actionable=out.harm_probability >= threshold,
                    )
                )

            if not y_true:
                continue

            metrics = compute_binary_metrics(y_true, y_score)
            bundle.results.append(
                EvaluationResult(
                    scorer=scorer_name,
                    condition=condition.value,
                    metrics={
                        "auprc": metrics.auprc,
                        "auroc": metrics.auroc,
                        "precision_at_recall_95": metrics.precision_at_recall_95,
                        "recall_at_fpr_1pct": metrics.recall_at_fpr_1pct,
                    },
                    n_samples=len(y_true),
                )
            )

    if bundle.predictions:
        bundle.difficulty_index = compute_difficulty_index(
            predictions=bundle.predictions,
            labels=labels,
            conversations=conversations,
        )

    from youth_escalate_bench.cache import get_default_llm_cache

    bundle.cache_stats = get_default_llm_cache().stats()

    return bundle


def evaluate_from_parquet(
    parquet_path: Path,
    labels_path: Path,
    scorers: dict[str, ModerationScorer],
    conditions: list[ContextCondition],
    seed: int = 42,
    max_samples: int | None = None,
    difficulty_index: DifficultyIndex | None = None,
    prioritize_hard_samples: bool = True,
    sample_strategy: str = "auto",
    enable_rag: bool = False,
    rag_compare: bool = False,
) -> EvaluationBundle:
    conversations = read_conversations(parquet_path)
    labels = load_labels(labels_path)
    return run_evaluation(
        conversations,
        scorers,
        labels,
        conditions,
        seed=seed,
        max_samples=max_samples,
        difficulty_index=difficulty_index,
        prioritize_hard_samples=prioritize_hard_samples,
        sample_strategy=sample_strategy,
        enable_rag=enable_rag,
        rag_compare=rag_compare,
    )


def write_evaluation_bundle(bundle: EvaluationBundle, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    results_data = [
        {
            "scorer": r.scorer,
            "condition": r.condition,
            "n_samples": r.n_samples,
            **r.metrics,
        }
        for r in bundle.results
    ]
    results_path = output_dir / "evaluation_results.yaml"
    with results_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(results_data, f)

    # Export cache stats if present
    cache_path = output_dir / "cache_stats.yaml"
    with cache_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(bundle.cache_stats, f)

    import json

    preds_path = output_dir / "predictions.jsonl"
    with preds_path.open("w", encoding="utf-8") as f:
        for p in bundle.predictions:
            f.write(
                json.dumps(
                    {
                        "conversation_id": p.conversation_id,
                        "turn_id": p.turn_id,
                        "scorer": p.scorer,
                        "condition": p.condition,
                        "harm_probability": p.harm_probability,
                        "actionable": p.actionable,
                    }
                )
                + "\n"
            )

    return {
        "output_files": ["evaluation_results.yaml", "predictions.jsonl", "cache_stats.yaml"],
        "metadata": {
            "result_count": len(bundle.results),
            "predictions": len(bundle.predictions),
            "random_seed": bundle.seed,
            "sample_strategy": bundle.sample_strategy,
            "enable_rag": bundle.enable_rag,
            "rag_compare": bundle.rag_compare,
            "cache_stats": bundle.cache_stats,
        },
    }
