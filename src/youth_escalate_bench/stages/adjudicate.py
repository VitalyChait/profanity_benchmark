"""Adjudication and gold label freeze."""

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from youth_escalate_bench.schemas.labels import AnnotationRecord, Severity


def _load_annotations(path: Path) -> list[AnnotationRecord]:
    records: list[AnnotationRecord] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(AnnotationRecord.model_validate(json.loads(line)))
    return records


def _majority_severity(votes: list[Severity]) -> Severity:
    counts: dict[Severity, int] = defaultdict(int)
    for v in votes:
        counts[v] += 1
    return max(counts, key=lambda s: counts[s])


def adjudicate_annotations(
    annotations: list[AnnotationRecord],
    require_adjudication: bool = False,
) -> list[AnnotationRecord]:
    """Majority vote per turn; prefer adjudicated label when present."""
    by_turn: dict[tuple[str, str], list[AnnotationRecord]] = defaultdict(list)
    for ann in annotations:
        by_turn[(ann.conversation_id, ann.turn_id)].append(ann)

    gold: list[AnnotationRecord] = []
    for key, votes in by_turn.items():
        adjudicated = [v for v in votes if v.adjudicated]
        if adjudicated:
            gold.append(adjudicated[0].model_copy(update={"adjudicated": True}))
        elif require_adjudication:
            continue
        else:
            severity = _majority_severity([v.severity for v in votes])
            template = votes[0]
            gold.append(
                AnnotationRecord(
                    conversation_id=template.conversation_id,
                    turn_id=template.turn_id,
                    profanity_form=template.profanity_form,
                    pragmatic_use=template.pragmatic_use,
                    harm_types=template.harm_types,
                    target_type=template.target_type,
                    severity=severity,
                    escalation_transition=template.escalation_transition,
                    context_dependence=template.context_dependence,
                    evidence_spans=template.evidence_spans,
                    evidence_turn_ids=template.evidence_turn_ids,
                    adjudicated=False,
                )
            )
    return gold


def _find_annotations_file(input_dir: Path, config_path: str | None = None) -> Path:
    if config_path:
        p = Path(config_path)
        if p.exists():
            return p
        if (input_dir / config_path).exists():
            return input_dir / config_path
    for candidate in ["annotations.jsonl", "generated_annotations.jsonl", "annotation_packets.jsonl"]:
        if (input_dir / candidate).exists():
            return input_dir / candidate
    jsonl_files = [f for f in input_dir.glob("*.jsonl") if not f.name.endswith("plans.jsonl") and not f.name.endswith("specs.jsonl")]
    if jsonl_files:
        return jsonl_files[0]
    return input_dir / "annotations.jsonl"


def run_adjudicate(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    annotations_path = _find_annotations_file(input_dir, config.get("annotations_path"))
    if not annotations_path.exists():
        raise FileNotFoundError(f"Missing annotations: {annotations_path}")

    annotations = _load_annotations(annotations_path)
    gold = adjudicate_annotations(
        annotations,
        require_adjudication=config.get("require_adjudication", False),
    )

    gold_path = output_dir / "gold_labels.jsonl"
    with gold_path.open("w", encoding="utf-8") as f:
        for ann in gold:
            f.write(json.dumps(ann.model_dump(mode="json")) + "\n")

    manifest = {
        "frozen_at": datetime.now(UTC).isoformat(),
        "benchmark_version": config.get("benchmark_version", "0.1.0"),
        "input_annotations": len(annotations),
        "gold_labels": len(gold),
        "correction_policy": "issue_correction_manifest_for_label_changes",
    }
    freeze_path = output_dir / "gold_freeze_manifest.yaml"
    with freeze_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f)

    return {
        "output_files": ["gold_labels.jsonl", "gold_freeze_manifest.yaml"],
        "row_counts": {"gold_labels.jsonl": len(gold)},
        "metadata": manifest,
    }


def run_import_annotations(
    config: dict[str, Any], input_dir: Path, output_dir: Path
) -> dict[str, Any]:
    """Import annotator submission JSONL into unified annotations file."""
    import_dir = Path(config.get("import_dir", input_dir))
    sources = list(import_dir.glob("*.jsonl"))
    merged: list[AnnotationRecord] = []
    for src in sources:
        merged.extend(_load_annotations(src))

    out_path = output_dir / "annotations.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ann in merged:
            f.write(json.dumps(ann.model_dump(mode="json")) + "\n")

    return {
        "output_files": ["annotations.jsonl"],
        "row_counts": {"annotations.jsonl": len(merged)},
        "metadata": {"imported": len(merged), "sources": len(sources)},
    }
