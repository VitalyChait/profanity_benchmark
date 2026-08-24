"""Pipeline stage implementations — aggregated registry."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from youth_escalate_bench.adapters import get_adapter
from youth_escalate_bench.baselines.scorers import build_default_scorers
from youth_escalate_bench.evaluation.conditions import ContextCondition
from youth_escalate_bench.evaluation.runner import evaluate_from_parquet, write_evaluation_bundle
from youth_escalate_bench.io.parquet import read_conversations, write_conversations
from youth_escalate_bench.metrics.onset import compute_onset_metrics, detection_recall_at_lag
from youth_escalate_bench.pii.detector import redact_text
from youth_escalate_bench.schemas.conversation import ConversationRecord, StoredTurn
from youth_escalate_bench.schemas.labels import AnnotationRecord
from youth_escalate_bench.source_registry import audit_gate_passes, load_registry, save_registry
from youth_escalate_bench.split.leakage import (
    check_near_duplicates_across_splits,
    check_split_leakage,
)
from youth_escalate_bench.stages.adjudicate import run_adjudicate
from youth_escalate_bench.stages.common import find_parquet
from youth_escalate_bench.stages.report import run_report
from youth_escalate_bench.stages.sample import run_sample, run_stage_generate
from youth_escalate_bench.thread.validate import validate_all
from youth_escalate_bench.transforms.algospeak import (
    TransformFamily,
    transform_text,
    transform_version_hash,
)

StageFn = Callable[[dict[str, Any], Path, Path], dict[str, Any]]


def run_source_audit(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    registry_path = Path(config.get("source_registry_path", "configs/source_registry.yaml"))
    registry = load_registry(registry_path)
    passed, failures = audit_gate_passes(registry)

    report = {
        "gate_passed": passed,
        "coverage_pct": registry.coverage_pct(),
        "pending_count": len(registry.pending_sources()),
        "failures": failures,
        "approved_sources": [s.source_id for s in registry.approved_sources()],
    }
    report_path = output_dir / "audit_report.yaml"
    with report_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(report, f, sort_keys=False)

    signed_path = output_dir / "source_registry_signed.yaml"
    save_registry(registry, signed_path)

    if config.get("strict", False) and not passed:
        raise RuntimeError(f"Source audit gate failed: {failures}")

    return {
        "output_files": ["audit_report.yaml", "source_registry_signed.yaml"],
        "metadata": report,
    }


def run_ingest(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    registry_path = Path(config.get("source_registry_path", "configs/source_registry.yaml"))
    registry = load_registry(registry_path)
    approved = {s.source_id for s in registry.approved_sources()}

    if config.get("allow_fixture_sources", False):
        approved.update({"fixture", "fixture_wikiconv", "fixture_cad"})

    if config.get("enforce_gate", True) and not approved:
        raise RuntimeError("No approved sources; complete license audit before ingest")

    all_conversations: list[ConversationRecord] = []
    for src in config.get("sources", []):
        source_id = src["source_id"]
        input_path = Path(src.get("input_path", input_dir / f"{source_id}.jsonl"))
        if not input_path.exists():
            raise FileNotFoundError(f"Missing ingest input: {input_path}")

        adapter = get_adapter(source_id)
        if config.get("enforce_gate", True):
            adapter.validate_source_approved(approved)
        all_conversations.extend(adapter.load(input_path))

    out_path = output_dir / "conversations.parquet"
    n = write_conversations(out_path, all_conversations)
    turn_count = sum(len(c.turns) for c in all_conversations)

    return {
        "output_files": ["conversations.parquet"],
        "row_counts": {"conversations.parquet": turn_count},
        "metadata": {"conversations": n, "turns": turn_count},
    }


def run_redact(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    conversations = read_conversations(find_parquet(input_dir, "conversations.parquet"))
    total_hits = 0
    redacted: list[ConversationRecord] = []

    for conv in conversations:
        new_turns: list[StoredTurn] = []
        for turn in conv.turns:
            text, hits = redact_text(turn.text)
            total_hits += len(hits)
            new_turns.append(
                StoredTurn(
                    turn_id=turn.turn_id,
                    speaker_id=turn.speaker_id,
                    role=turn.role,
                    text=text,
                    relative_time=turn.relative_time,
                    parent_turn_id=turn.parent_turn_id,
                )
            )
        redacted.append(conv.model_copy(update={"turns": new_turns}))

    write_conversations(output_dir / "conversations_redacted.parquet", redacted)
    report = {"total_pii_hits": total_hits, "conversations": len(redacted)}
    with (output_dir / "pii_report.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(report, f)

    return {
        "output_files": ["conversations_redacted.parquet", "pii_report.yaml"],
        "row_counts": {"conversations_redacted.parquet": sum(len(c.turns) for c in redacted)},
        "metadata": report,
    }


def run_thread(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    conversations = read_conversations(
        find_parquet(input_dir, "conversations_redacted.parquet", "conversations.parquet")
    )
    issues = validate_all(conversations)
    report = {
        "issue_count": len(issues),
        "issues": [
            {"conversation_id": i.conversation_id, "turn_id": i.turn_id, "issue": i.issue}
            for i in issues
        ],
    }
    with (output_dir / "topology_report.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(report, f)

    if config.get("fail_on_issues", False) and issues:
        raise RuntimeError(f"Topology validation failed with {len(issues)} issues")

    write_conversations(output_dir / "conversations_threaded.parquet", conversations)
    return {
        "output_files": ["conversations_threaded.parquet", "topology_report.yaml"],
        "row_counts": {"conversations_threaded.parquet": sum(len(c.turns) for c in conversations)},
        "metadata": {"issues": len(issues)},
    }


def run_transform(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    conversations = read_conversations(find_parquet(input_dir, "conversations_threaded.parquet"))
    default_families = [TransformFamily.LEETSPEAK.value]
    families = [TransformFamily(f) for f in config.get("families", default_families)]
    selected = families[: config.get("composition_depth", 1)]

    transformed_rows: list[ConversationRecord] = []
    for conv in conversations:
        for turn in conv.turns:
            perturbed = transform_text(turn.text, selected)
            transformed_rows.append(
                ConversationRecord(
                    conversation_id=f"{conv.conversation_id}__{turn.turn_id}__xform",
                    source_id=conv.source_id,
                    source_tier=conv.source_tier,
                    platform_style=conv.platform_style,
                    language_mode=conv.language_mode,
                    benchmark_version=conv.benchmark_version,
                    turns=[
                        StoredTurn(
                            turn_id="clean",
                            speaker_id=turn.speaker_id,
                            role=turn.role,
                            text=turn.text,
                            relative_time=turn.relative_time,
                        ),
                        StoredTurn(
                            turn_id="transformed",
                            speaker_id=turn.speaker_id,
                            role=turn.role,
                            text=perturbed,
                            relative_time=turn.relative_time,
                        ),
                    ],
                    metadata={
                        "transform_families": [f.value for f in selected],
                        "transform_version": transform_version_hash(),
                        "origin_conversation_id": conv.conversation_id,
                        "origin_turn_id": turn.turn_id,
                    },
                )
            )

    write_conversations(output_dir / "transform_pairs.parquet", transformed_rows)
    return {
        "output_files": ["transform_pairs.parquet"],
        "row_counts": {"transform_pairs.parquet": sum(len(c.turns) for c in transformed_rows)},
        "metadata": {"pairs": len(transformed_rows), "transform_version": transform_version_hash()},
    }


def run_split(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    conversations = read_conversations(find_parquet(input_dir, "conversations_threaded.parquet"))
    seed = config.get("random_seed", 42)
    ratios = config.get("ratios", {"train": 0.5, "dev": 0.25, "test": 0.25})

    import random

    rng = random.Random(seed)
    pool = conversations.copy()
    rng.shuffle(pool)

    n = len(pool)
    train_end = int(n * ratios.get("train", 0.5))
    dev_end = train_end + int(n * ratios.get("dev", 0.25))

    splits = {
        "train": pool[:train_end],
        "dev": pool[train_end:dev_end],
        "test": pool[dev_end:],
    }

    output_files: list[str] = []
    row_counts: dict[str, int] = {}
    for name, split_convs in splits.items():
        path = output_dir / f"split_{name}.parquet"
        write_conversations(path, split_convs)
        output_files.append(f"split_{name}.parquet")
        row_counts[f"split_{name}.parquet"] = sum(len(c.turns) for c in split_convs)

    leakage = check_split_leakage(splits)
    near_dup = check_near_duplicates_across_splits(
        splits, threshold=config.get("leakage_threshold", 0.85)
    )

    manifest = {
        "seed": seed,
        "counts": {k: len(v) for k, v in splits.items()},
        "conversation_ids": {k: [c.conversation_id for c in v] for k, v in splits.items()},
        "leakage_findings": [{"kind": f.kind, "detail": f.detail} for f in leakage],
        "near_duplicate_findings": [{"kind": f.kind, "detail": f.detail} for f in near_dup],
        "leakage_clean": len(leakage) == 0,
    }
    with (output_dir / "split_manifest.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f)
    output_files.append("split_manifest.yaml")

    if config.get("fail_on_leakage", False) and leakage:
        raise RuntimeError(f"Split leakage detected: {leakage}")

    return {"output_files": output_files, "row_counts": row_counts, "metadata": manifest["counts"]}


def run_evaluate(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    configured_labels = Path(config.get("labels_path", "data/processed/adjudicate/gold_labels.jsonl"))
    if configured_labels.exists():
        labels_path = configured_labels
    elif (input_dir / "gold_labels.jsonl").exists():
        labels_path = input_dir / "gold_labels.jsonl"
    elif Path("data/processed/adjudicate/gold_labels.jsonl").exists():
        labels_path = Path("data/processed/adjudicate/gold_labels.jsonl")
    else:
        labels_path = Path("tests/fixtures/sample_labels.jsonl")

    split_name = config.get("split", "test")
    parquet_path = find_parquet(
        input_dir, f"split_{split_name}.parquet", "split_test.parquet", "conversations_threaded.parquet"
    )

    lexicon_path = Path(config.get("lexicon_path", "configs/profanity_lexicon.txt"))
    scorers = build_default_scorers(lexicon_path)

    condition_names = config.get(
        "conditions",
        [
            ContextCondition.CURRENT_TURN_ONLY.value,
            ContextCondition.PREV_PLUS_CURRENT.value,
            ContextCondition.FULL_PREFIX.value,
        ],
    )
    conditions = [ContextCondition(c) for c in condition_names]

    bundle = evaluate_from_parquet(
        parquet_path=parquet_path,
        labels_path=labels_path,
        scorers=scorers,
        conditions=conditions,
        seed=config.get("random_seed", 42),
    )

    meta = write_evaluation_bundle(bundle, output_dir)

    # Onset metrics for primary scorer + full context
    labels_list_path = labels_path
    import json

    label_records: list[AnnotationRecord] = []
    if labels_list_path.exists():
        with labels_list_path.open(encoding="utf-8") as f:
            for line in f:
                label_records.append(AnnotationRecord.model_validate(json.loads(line)))

    predictions = {
        (p.conversation_id, p.turn_id): p.harm_probability
        for p in bundle.predictions
        if p.scorer == "lexicon_full_context" and p.condition == ContextCondition.FULL_PREFIX.value
    }
    onset = compute_onset_metrics(label_records, predictions)
    lag_recalls = detection_recall_at_lag(label_records, predictions, max_lag=2)

    onset_report = {
        "detection_rate": onset.detection_rate,
        "median_delay": onset.median_delay,
        "missed": onset.missed,
        "recall_at_lag": lag_recalls,
    }
    with (output_dir / "onset_metrics.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(onset_report, f)

    meta["output_files"].append("onset_metrics.yaml")
    meta["metadata"]["onset"] = onset_report
    return meta


def run_annotate_export(
    config: dict[str, Any], input_dir: Path, output_dir: Path
) -> dict[str, Any]:
    conversations = read_conversations(
        find_parquet(input_dir, "conversations_threaded.parquet", "conversations.parquet")
    )
    import json

    packet_path = output_dir / "annotation_packets.jsonl"
    with packet_path.open("w", encoding="utf-8") as f:
        for conv in conversations:
            packet = {
                "conversation_id": conv.conversation_id,
                "source_id": conv.source_id,
                "source_tier": conv.source_tier.value,
                "platform_style": conv.platform_style,
                "turns": [t.model_dump() for t in conv.turns],
                "annotation_fields": AnnotationRecord.taxonomy_coverage(),
            }
            f.write(json.dumps(packet, ensure_ascii=False) + "\n")

    return {
        "output_files": ["annotation_packets.jsonl"],
        "row_counts": {"annotation_packets.jsonl": len(conversations)},
        "metadata": {"packets": len(conversations)},
    }


def _stub_stage(stage: str) -> StageFn:
    def runner(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
        marker = output_dir / f"{stage}_complete.marker"
        seed = config.get("random_seed", 42)
        marker.write_text(f"stage={stage}\nseed={seed}\n", encoding="utf-8")
        return {"output_files": [f"{stage}_complete.marker"], "metadata": {"stage": stage}}

    return runner


STAGE_IMPLEMENTATIONS: dict[str, StageFn] = {
    "source_audit": run_source_audit,
    "ingest": run_ingest,
    "redact": run_redact,
    "thread": run_thread,
    "transform": run_transform,
    "split": run_split,
    "evaluate": run_evaluate,
    "annotate_export": run_annotate_export,
    "sample": run_sample,
    "stage_generate": run_stage_generate,
    "adjudicate": run_adjudicate,
    "report": run_report,
}
