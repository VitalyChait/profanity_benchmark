"""Report generation: tables, error analysis, benchmark card data."""

from pathlib import Path
from typing import Any

import yaml

from youth_escalate_bench.metrics.agreement import actionable_agreement, severity_alpha
from youth_escalate_bench.stages.adjudicate import _load_annotations


def run_report(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    eval_path = input_dir / "evaluation_results.yaml"
    if not eval_path.exists():
        default_eval = "data/processed/evaluate/evaluation_results.yaml"
        eval_path = Path(config.get("evaluation_results", default_eval))

    results: list[dict] = []
    if eval_path.exists():
        with eval_path.open(encoding="utf-8") as f:
            results = yaml.safe_load(f) or []

    # Agreement quality if annotations available
    ann_path = Path(config.get("annotations_path", input_dir / "annotations.jsonl"))
    quality: dict[str, Any] = {}
    if ann_path.exists():
        anns = _load_annotations(ann_path)
        quality = {
            "severity_alpha": severity_alpha(anns),
            "actionable_agreement": actionable_agreement(anns),
            "annotation_count": len(anns),
        }

    # Markdown report
    lines = [
        "# YouthEscalateBench Evaluation Report",
        "",
        f"Benchmark version: {config.get('benchmark_version', '0.1.0')}",
        "",
        "## Primary Results",
        "",
        "| Scorer | Condition | AUPRC | AUROC | N |",
        "|--------|-----------|-------|-------|---|",
    ]
    for row in results:
        auroc = row.get("auroc")
        auroc_str = f"{auroc:.3f}" if auroc is not None else "—"
        lines.append(
            f"| {row.get('scorer')} | {row.get('condition')} | "
            f"{row.get('auprc', 0):.3f} | {auroc_str} | {row.get('n_samples', 0)} |"
        )

    if quality:
        lines.extend(
            [
                "",
                "## Annotation Quality",
                "",
                f"- Severity Krippendorff α: {quality.get('severity_alpha')}",
                f"- Actionable agreement: {quality.get('actionable_agreement')}",
            ]
        )

    report_md = output_dir / "evaluation_report.md"
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary_path = output_dir / "report_summary.yaml"
    summary = {"results": results, "annotation_quality": quality}
    with summary_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(summary, f)

    # Error analysis bundle stub
    error_path = output_dir / "error_analysis_bundle.yaml"
    error_bundle = {
        "top_false_positives": [],
        "top_false_negatives": [],
        "by_source_tier": {},
        "note": "Populate from predictions.jsonl during full evaluation",
    }
    preds_path = input_dir / "predictions.jsonl"
    if preds_path.exists():
        import json

        fps: list[dict] = []
        fns: list[dict] = []
        with preds_path.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                # Without labels in predictions, just sample high-confidence preds
                if row.get("harm_probability", 0) > 0.8:
                    fps.append(row)
                if row.get("harm_probability", 0) < 0.2 and row.get("actionable"):
                    fns.append(row)
        error_bundle["top_false_positives"] = fps[:10]
        error_bundle["top_false_negatives"] = fns[:10]

    with error_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(error_bundle, f)

    return {
        "output_files": [
            "evaluation_report.md",
            "report_summary.yaml",
            "error_analysis_bundle.yaml",
        ],
        "metadata": {"result_rows": len(results)},
    }
