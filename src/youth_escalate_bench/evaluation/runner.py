"""Causal evaluation runner for moderation scorers."""

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
) -> EvaluationBundle:
    bundle = EvaluationBundle()

    for condition in conditions:
        for scorer_name, scorer in scorers.items():
            y_true: list[bool] = []
            y_score: list[float] = []

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
                    if key not in labels:
                        continue
                    out = scorer.predict(req)
                    y_true.append(labels[key])
                    y_score.append(out.harm_probability)
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
) -> EvaluationBundle:
    conversations = read_conversations(parquet_path)
    labels = load_labels(labels_path)
    return run_evaluation(conversations, scorers, labels, conditions, seed=seed)


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
