"""Pipeline stage implementations."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from youth_escalate_bench.adapters import get_adapter
from youth_escalate_bench.dedup.minhash import find_near_duplicates, normalized_text_hash
from youth_escalate_bench.io.parquet import read_conversations, write_conversations
from youth_escalate_bench.metrics.detection import compute_binary_metrics
from youth_escalate_bench.pii.detector import redact_text
from youth_escalate_bench.schemas.conversation import ConversationRecord, StoredTurn
from youth_escalate_bench.schemas.labels import AnnotationRecord, Severity
from youth_escalate_bench.source_registry import audit_gate_passes, load_registry, save_registry
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

    strict = config.get("strict", False)
    if strict and not passed:
        raise RuntimeError(f"Source audit gate failed: {failures}")

    return {
        "output_files": ["audit_report.yaml", "source_registry_signed.yaml"],
        "metadata": report,
    }


def run_ingest(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    registry_path = Path(config.get("source_registry_path", "configs/source_registry.yaml"))
    registry = load_registry(registry_path)
    approved = {s.source_id for s in registry.approved_sources()}

    # Fixture sources for dev/e2e bypass when explicitly allowed
    allow_fixture = config.get("allow_fixture_sources", False)
    if allow_fixture:
        approved.update({"fixture", "fixture_wikiconv", "fixture_cad"})

    if config.get("enforce_gate", True) and not approved:
        raise RuntimeError("No approved sources; complete license audit before ingest")

    sources_cfg = config.get("sources", [])
    all_conversations: list[ConversationRecord] = []

    for src in sources_cfg:
        source_id = src["source_id"]
        input_path = Path(src.get("input_path", input_dir / f"{source_id}.jsonl"))
        if not input_path.exists():
            raise FileNotFoundError(f"Missing ingest input: {input_path}")

        adapter = get_adapter(source_id)
        if config.get("enforce_gate", True):
            adapter.validate_source_approved(approved)

        conversations = adapter.load(input_path)
        all_conversations.extend(conversations)

    out_path = output_dir / "conversations.parquet"
    n = write_conversations(out_path, all_conversations)
    turn_count = sum(len(c.turns) for c in all_conversations)

    return {
        "output_files": ["conversations.parquet"],
        "row_counts": {"conversations.parquet": turn_count},
        "metadata": {"conversations": n, "turns": turn_count},
    }


def run_redact(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    in_path = _find_parquet(input_dir, "conversations.parquet")
    conversations = read_conversations(in_path)
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

    out_path = output_dir / "conversations_redacted.parquet"
    write_conversations(out_path, redacted)

    report_path = output_dir / "pii_report.yaml"
    report = {"total_pii_hits": total_hits, "conversations": len(redacted)}
    with report_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(report, f)

    return {
        "output_files": ["conversations_redacted.parquet", "pii_report.yaml"],
        "row_counts": {"conversations_redacted.parquet": sum(len(c.turns) for c in redacted)},
        "metadata": report,
    }


def run_thread(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    in_path = _find_parquet(input_dir, "conversations_redacted.parquet", "conversations.parquet")
    conversations = read_conversations(in_path)
    issues = validate_all(conversations)

    report_path = output_dir / "topology_report.yaml"
    report = {
        "issue_count": len(issues),
        "issues": [
            {"conversation_id": i.conversation_id, "turn_id": i.turn_id, "issue": i.issue}
            for i in issues
        ],
    }
    with report_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(report, f)

    if config.get("fail_on_issues", False) and issues:
        raise RuntimeError(f"Topology validation failed with {len(issues)} issues")

    out_path = output_dir / "conversations_threaded.parquet"
    write_conversations(out_path, conversations)

    return {
        "output_files": ["conversations_threaded.parquet", "topology_report.yaml"],
        "row_counts": {"conversations_threaded.parquet": sum(len(c.turns) for c in conversations)},
        "metadata": {"issues": len(issues)},
    }


def run_transform(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    in_path = _find_parquet(input_dir, "conversations_threaded.parquet")
    conversations = read_conversations(in_path)

    families = [
        TransformFamily(f) for f in config.get("families", [TransformFamily.LEETSPEAK.value])
    ]
    depth = config.get("composition_depth", 1)
    selected = families[:depth]

    transformed_rows: list[ConversationRecord] = []
    for conv in conversations:
        for turn in conv.turns:
            clean = turn.text
            perturbed = transform_text(clean, selected)
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
                            text=clean,
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

    out_path = output_dir / "transform_pairs.parquet"
    write_conversations(out_path, transformed_rows)

    return {
        "output_files": ["transform_pairs.parquet"],
        "row_counts": {"transform_pairs.parquet": sum(len(c.turns) for c in transformed_rows)},
        "metadata": {
            "pairs": len(transformed_rows),
            "transform_version": transform_version_hash(),
        },
    }


def run_split(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    in_path = _find_parquet(input_dir, "conversations_threaded.parquet")
    conversations = read_conversations(in_path)

    seed = config.get("random_seed", 42)
    ratios = config.get(
        "ratios",
        {"train": 0.5, "dev": 0.25, "test": 0.25},
    )

    import random

    rng = random.Random(seed)
    ids = conversations.copy()
    rng.shuffle(ids)

    n = len(ids)
    train_end = int(n * ratios.get("train", 0.5))
    dev_end = train_end + int(n * ratios.get("dev", 0.25))

    splits = {
        "train": ids[:train_end],
        "dev": ids[train_end:dev_end],
        "test": ids[dev_end:],
    }

    output_files: list[str] = []
    row_counts: dict[str, int] = {}
    for name, split_convs in splits.items():
        path = output_dir / f"split_{name}.parquet"
        write_conversations(path, split_convs)
        output_files.append(f"split_{name}.parquet")
        row_counts[f"split_{name}.parquet"] = sum(len(c.turns) for c in split_convs)

    manifest_path = output_dir / "split_manifest.yaml"
    manifest = {
        "seed": seed,
        "counts": {k: len(v) for k, v in splits.items()},
        "conversation_ids": {k: [c.conversation_id for c in v] for k, v in splits.items()},
    }
    with manifest_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f)

    output_files.append("split_manifest.yaml")
    return {
        "output_files": output_files,
        "row_counts": row_counts,
        "metadata": manifest["counts"],
    }


def run_evaluate(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Evaluate using fixture labels or supplied predictions."""
    labels_path = Path(config.get("labels_path", input_dir / "labels.jsonl"))
    split_path = _find_parquet(input_dir, "split_test.parquet", "conversations_threaded.parquet")
    conversations = read_conversations(split_path)

    labels: dict[tuple[str, str], bool] = {}
    if labels_path.exists():
        import json

        with labels_path.open(encoding="utf-8") as f:
            for line in f:
                raw = json.loads(line)
                ann = AnnotationRecord.model_validate(raw)
                labels[(ann.conversation_id, ann.turn_id)] = ann.severity in (
                    Severity.ACTIONABLE,
                    Severity.URGENT,
                )

    y_true: list[bool] = []
    y_score: list[float] = []

    for conv in conversations:
        for turn in conv.turns:
            key = (conv.conversation_id, turn.turn_id)
            if key in labels:
                y_true.append(labels[key])
                # Placeholder scorer: length-normalized hash as pseudo-score
                y_score.append((len(turn.text) % 100) / 100.0)

    metrics = compute_binary_metrics(y_true, y_score)
    result = {
        "auprc": metrics.auprc,
        "auroc": metrics.auroc,
        "precision_at_recall_95": metrics.precision_at_recall_95,
        "recall_at_fpr_1pct": metrics.recall_at_fpr_1pct,
        "n_samples": len(y_true),
    }

    out_path = output_dir / "metrics.yaml"
    with out_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(result, f)

    return {
        "output_files": ["metrics.yaml"],
        "metadata": result,
    }


def run_annotate_export(
    config: dict[str, Any], input_dir: Path, output_dir: Path
) -> dict[str, Any]:
    in_path = _find_parquet(input_dir, "conversations_threaded.parquet", "conversations.parquet")
    conversations = read_conversations(in_path)

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


def run_dedup_report(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    in_path = _find_parquet(input_dir, "conversations_threaded.parquet")
    conversations = read_conversations(in_path)

    texts = []
    ids = []
    for conv in conversations:
        for turn in conv.turns:
            texts.append(turn.text)
            ids.append(f"{conv.conversation_id}:{turn.turn_id}")

    exact_hashes: dict[str, list[str]] = {}
    for id_, text in zip(ids, texts, strict=True):
        h = normalized_text_hash(text)
        exact_hashes.setdefault(h, []).append(id_)

    exact_dupes = {h: v for h, v in exact_hashes.items() if len(v) > 1}
    near = find_near_duplicates(texts, threshold=config.get("minhash_threshold", 0.8))

    report = {
        "exact_duplicate_groups": len(exact_dupes),
        "near_duplicate_pairs": len(near),
        "near_duplicate_sample": [
            {"a": ids[i], "b": ids[j], "similarity": sim} for i, j, sim in near[:20]
        ],
    }
    report_path = output_dir / "dedup_report.yaml"
    with report_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(report, f)

    return {
        "output_files": ["dedup_report.yaml"],
        "metadata": report,
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
    "sample": run_dedup_report,
    "stage_generate": _stub_stage("stage_generate"),
    "adjudicate": _stub_stage("adjudicate"),
    "report": _stub_stage("report"),
}


def _find_parquet(input_dir: Path, *names: str) -> Path:
    for name in names:
        direct = input_dir / name
        if direct.exists():
            return direct
        nested = list(input_dir.rglob(name))
        if nested:
            return nested[0]
    raise FileNotFoundError(f"None of {names} found under {input_dir}")
