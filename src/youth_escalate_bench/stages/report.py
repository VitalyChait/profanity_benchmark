"""Report generation: tables, LaTeX snippets, error analysis, benchmark card data."""

from pathlib import Path
from typing import Any

import yaml

from youth_escalate_bench.metrics.agreement import actionable_agreement, severity_alpha
from youth_escalate_bench.stages.adjudicate import _load_annotations


def _generate_latex_table(results: list[dict]) -> str:
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\small",
        r"\begin{tabular}{llccc}",
        r"\toprule",
        r"\textbf{Model / Scorer} & \textbf{Condition} & \textbf{AUPRC} $\uparrow$ & \textbf{AUROC} $\uparrow$ & \textbf{N} \\",
        r"\midrule",
    ]
    for row in results:
        scorer = row.get("scorer", "").replace("_", r"\_")
        condition = row.get("condition", "").replace("_", r"\_")
        auprc = f"{row.get('auprc', 0.0):.3f}"
        auroc = f"{row.get('auroc', 0.0):.3f}" if row.get("auroc") is not None else "---"
        n = row.get("n_samples", 0)
        lines.append(f"{scorer} & {condition} & {auprc} & {auroc} & {n} \\\\")
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\caption{YouthEscalateBench Causal Moderation Performance across Context Conditions.}",
            r"\label{tab:main_results}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines)


def run_report(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    eval_path = input_dir / "evaluation_results.yaml"
    if not eval_path.exists():
        default_eval = "data/processed/evaluate/evaluation_results.yaml"
        eval_path = Path(config.get("evaluation_results", default_eval))

    results: list[dict] = []
    if eval_path.exists():
        with eval_path.open(encoding="utf-8") as f:
            results = yaml.safe_load(f) or []

    # Onset metrics if available
    onset_path = input_dir / "onset_metrics.yaml"
    if not onset_path.exists():
        onset_path = Path(config.get("onset_metrics", "data/processed/evaluate/onset_metrics.yaml"))
    onset_data: dict[str, Any] = {}
    if onset_path.exists():
        with onset_path.open(encoding="utf-8") as f:
            onset_data = yaml.safe_load(f) or {}

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
        f"**Benchmark version:** `{config.get('benchmark_version', '0.1.0')}`",
        "",
        "## 1. Primary Moderation Performance",
        "",
        "| Scorer | Condition | AUPRC | AUROC | N |",
        "|--------|-----------|-------|-------|---|",
    ]
    for row in results:
        auroc = row.get("auroc")
        auroc_str = f"{auroc:.3f}" if auroc is not None else "—"
        lines.append(
            f"| `{row.get('scorer')}` | `{row.get('condition')}` | "
            f"**{row.get('auprc', 0):.3f}** | {auroc_str} | {row.get('n_samples', 0)} |"
        )

    if onset_data:
        lines.extend(
            [
                "",
                "## 2. Conversation Onset Detection Dynamics",
                "",
                f"- **Mean Onset Lag:** {onset_data.get('mean_onset_lag', '—')} turns",
                f"- **Median Onset Lag:** {onset_data.get('median_onset_lag', '—')} turns",
                f"- **Recall @ Lag 0 (Immediate):** {onset_data.get('recall_lag_0', '—')}",
                f"- **Recall @ Lag 1 (+1 turn):** {onset_data.get('recall_lag_1', '—')}",
                f"- **Recall @ Lag 2 (+2 turns):** {onset_data.get('recall_lag_2', '—')}",
            ]
        )

    if quality:
        lines.extend(
            [
                "",
                "## 3. Annotation Quality & Agreement",
                "",
                f"- **Severity Krippendorff $\\alpha$:** `{quality.get('severity_alpha')}`",
                f"- **Actionable Agreement %:** `{quality.get('actionable_agreement')}`",
                f"- **Evaluated Annotation Packets:** `{quality.get('annotation_count')}`",
            ]
        )

    report_md = output_dir / "evaluation_report.md"
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Export LaTeX table for paper inclusion
    latex_path = output_dir / "table_main_results.tex"
    latex_path.write_text(_generate_latex_table(results) + "\n", encoding="utf-8")

    summary_path = output_dir / "report_summary.yaml"
    summary = {"results": results, "onset_dynamics": onset_data, "annotation_quality": quality}
    with summary_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(summary, f)

    # Error analysis bundle
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
            "table_main_results.tex",
            "report_summary.yaml",
            "error_analysis_bundle.yaml",
        ],
        "metadata": {"result_rows": len(results), "onset_metrics_present": bool(onset_data)},
    }
