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
) -> EvaluationBundle:
    from concurrent.futures import ThreadPoolExecutor

    bundle = EvaluationBundle()

    # Pre-collect labeled inference requests per condition
    target_requests: dict[ContextCondition, list[tuple[InferenceRequest, bool]]] = {}
    for condition in conditions:
        pairs: list[tuple[InferenceRequest, bool]] = []
        for conv in conversations:
            if max_samples and len(pairs) >= max_samples:
                break
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
                if max_samples and len(pairs) >= max_samples:
                    break
                key = (req.conversation_id, req.current_turn_id)
                if key in labels:
                    pairs.append((req, labels[key]))
        target_requests[condition] = pairs

    # Run predictions concurrently per scorer
    for condition in conditions:
        pairs = target_requests.get(condition, [])
        if not pairs:
            continue

        for scorer_name, scorer in scorers.items():
            def _score_one(pair: tuple[InferenceRequest, bool]) -> tuple[InferenceRequest, bool, ModelOutput]:
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

    return bundle


def evaluate_from_parquet(
    parquet_path: Path,
    labels_path: Path,
    scorers: dict[str, ModerationScorer],
    conditions: list[ContextCondition],
    seed: int = 42,
    max_samples: int | None = None,
) -> EvaluationBundle:
    conversations = read_conversations(parquet_path)
    labels = load_labels(labels_path)
    return run_evaluation(
        conversations, scorers, labels, conditions, seed=seed, max_samples=max_samples
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
        "output_files": ["evaluation_results.yaml", "predictions.jsonl"],
        "metadata": {"result_count": len(bundle.results), "predictions": len(bundle.predictions)},
    }
