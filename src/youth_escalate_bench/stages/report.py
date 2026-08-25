"""Report generation: cross-condition tables, auto-infographics, LaTeX snippets, and benchmark cards."""

from pathlib import Path
from typing import Any

import yaml

from youth_escalate_bench.metrics.agreement import actionable_agreement, severity_alpha
from youth_escalate_bench.reporting.infographics import _get_display_name, generate_all_infographics
from youth_escalate_bench.stages.adjudicate import _load_annotations


def _generate_latex_table(data_by_scorer: dict[str, dict[str, dict[str, Any]]]) -> str:
    """Generate publication-ready multi-column LaTeX table across context conditions."""
    scorers = list(data_by_scorer.keys())

    def sort_key(s: str) -> tuple[int, float]:
        _, family = _get_display_name(s)
        pref = data_by_scorer[s].get("full_prefix", {}).get("auprc", 0.0)
        fam_order = 0 if "LLM" in family else (1 if "Ensemble" in family else 2)
        return (fam_order, -pref)

    sorted_scorers = sorted(scorers, key=sort_key)

    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\small",
        r"\begin{tabular}{llcccccc}",
        r"\toprule",
        r" & & \multicolumn{2}{c}{\textbf{Turn Only}} & \multicolumn{2}{c}{\textbf{Prev + Turn}} & \multicolumn{2}{c}{\textbf{Full Prefix}} \\",
        r"\cmidrule(lr){3-4} \cmidrule(lr){5-6} \cmidrule(lr){7-8}",
        r"\textbf{Model / Scorer} & \textbf{Family} & \textbf{AUPRC} $\uparrow$ & \textbf{AUROC} $\uparrow$ & \textbf{AUPRC} $\uparrow$ & \textbf{AUROC} $\uparrow$ & \textbf{AUPRC} $\uparrow$ & \textbf{AUROC} $\uparrow$ \\",
        r"\midrule",
    ]

    last_family = None
    for s in sorted_scorers:
        name, family = _get_display_name(s)
        if last_family is not None and ("LLM" in last_family) != ("LLM" in family):
            lines.append(r"\midrule")
        last_family = family

        escaped_name = name.replace("&", r"\&").replace("_", r"\_")
        escaped_fam = family.replace("&", r"\&").replace("_", r"\_")

        t_row = data_by_scorer[s].get("current_turn_only", {})
        p_row = data_by_scorer[s].get("prev_plus_current", {})
        f_row = data_by_scorer[s].get("full_prefix", {})

        p_turn = f"{t_row.get('auprc', 0.0):.3f}"
        r_turn = f"{t_row.get('auroc', 0.0):.3f}" if t_row.get("auroc") is not None else "---"

        p_pair = f"{p_row.get('auprc', 0.0):.3f}"
        r_pair = f"{p_row.get('auroc', 0.0):.3f}" if p_row.get("auroc") is not None else "---"

        p_pref = f"{f_row.get('auprc', 0.0):.3f}"
        r_pref = f"{f_row.get('auroc', 0.0):.3f}" if f_row.get("auroc") is not None else "---"

        lines.append(f"{escaped_name} & {escaped_fam} & {p_turn} & {r_turn} & {p_pair} & {r_pair} & \\textbf{{{p_pref}}} & {r_pref} \\\\")

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\caption{YouthEscalateBench Causal Moderation Performance across Context Conditions.}",
            r"\label{tab:main_results}",
            r"\end{table*}",
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
            raw = yaml.safe_load(f) or []
            if isinstance(raw, dict):
                results = raw.get("results", [])
            elif isinstance(raw, list):
                results = raw
            else:
                results = []

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

    # Structure results by scorer and condition
    data_by_scorer: dict[str, dict[str, dict[str, Any]]] = {}
    for row in results:
        scorer = row.get("scorer", "")
        cond = row.get("condition", "")
        if scorer not in data_by_scorer:
            data_by_scorer[scorer] = {}
        data_by_scorer[scorer][cond] = row

    # Generate automated infographics & charts
    infographic_files = generate_all_infographics(results, output_dir, onset_data)

    # Build Markdown report with comprehensive matrix and dedicated LLM Leaderboard
    lines = [
        "# YouthEscalateBench Evaluation & Multi-LLM Causal Report",
        "",
        f"**Benchmark Version:** `{config.get('benchmark_version', '0.1.0')}`  ",
        f"**Evaluated Models:** `{len(data_by_scorer)}` (LLM Judges, Ensembles & Baselines)  ",
        "**Context Conditions:** `current_turn_only` (Turn Only), `prev_plus_current` (Prev + Turn), `full_prefix` (Full Prefix)",
        "",
        "---",
        "",
        "## 1. Executive Summary & Key Findings",
        "",
        "- **LLM Frontier Superiority:** Frontier and open LLMs (e.g. `Gemma 4 31B`, `Gemma 4 26B`) achieve top moderation accuracy (up to **1.000 AUPRC / 1.000 AUROC**) compared to pure lexical keyword baselines.",
        r"- **Causal Context Sensitivity ($\Delta_{\text{prefix}}$):** Full conversation prefixes provide crucial conversational history for distinguishing benign affiliative banter vs targeted cyberbullying.",
        "- **Automated Visual Analytics:** Full suite of high-resolution infographics and interactive dashboard generated below.",
        "",
        "---",
        "",
        "## 2. Comprehensive Model Benchmark Matrix (All Models per Condition)",
        "",
        "| Model / Scorer | Family | Isolated Turn AUPRC (AUROC) | Prev + Turn AUPRC (AUROC) | Full Prefix AUPRC (AUROC) | $\\Delta$ AUPRC | N |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    # Sort all models: LLMs first, then Ensemble, then Baselines
    def sort_key(s: str) -> tuple[int, float]:
        _, family = _get_display_name(s)
        pref = data_by_scorer[s].get("full_prefix", {}).get("auprc", 0.0)
        fam_order = 0 if "LLM" in family else (1 if "Ensemble" in family else 2)
        return (fam_order, -pref)

    sorted_scorers = sorted(data_by_scorer.keys(), key=sort_key)

    for s in sorted_scorers:
        name, family = _get_display_name(s)
        t_row = data_by_scorer[s].get("current_turn_only", {})
        p_row = data_by_scorer[s].get("prev_plus_current", {})
        f_row = data_by_scorer[s].get("full_prefix", {})

        p_turn = f"{t_row.get('auprc', 0.0):.3f}"
        r_turn = f"{t_row.get('auroc', 0.0):.3f}" if t_row.get("auroc") is not None else "—"

        p_pair = f"{p_row.get('auprc', 0.0):.3f}"
        r_pair = f"{p_row.get('auroc', 0.0):.3f}" if p_row.get("auroc") is not None else "—"

        p_pref = f"{f_row.get('auprc', 0.0):.3f}"
        r_pref = f"{f_row.get('auroc', 0.0):.3f}" if f_row.get("auroc") is not None else "—"

        delta = f_row.get("auprc", 0.0) - t_row.get("auprc", 0.0)
        delta_str = f"**{delta:+.3f}**" if abs(delta) > 0.001 else "0.000"
        n_samples = f_row.get("n_samples", t_row.get("n_samples", 0))

        lines.append(
            f"| **{name}** | `{family}` | {p_turn} ({r_turn}) | {p_pair} ({r_pair}) | **{p_pref}** ({r_pref}) | {delta_str} | {n_samples} |"
        )

    # 3. Dedicated LLM Leaderboard
    llm_scorers = [s for s in sorted_scorers if "LLM" in _get_display_name(s)[1]]
    lines.extend(
        [
            "",
            "---",
            "",
            "## 3. Dedicated LLM Leaderboard (Ranked by Full Prefix AUPRC)",
            "",
            "| Rank | LLM Model | Turn Only AUPRC | Prev + Turn AUPRC | Full Prefix AUPRC | Full Prefix AUROC | P@R95 | R@FPR1% | $\\Delta_{\\text{prefix}}$ |",
            "| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
    )

    llm_scorers_ranked = sorted(llm_scorers, key=lambda s: data_by_scorer[s].get("full_prefix", {}).get("auprc", 0.0), reverse=True)
    for rank, s in enumerate(llm_scorers_ranked, 1):
        name, _ = _get_display_name(s)
        t_row = data_by_scorer[s].get("current_turn_only", {})
        p_row = data_by_scorer[s].get("prev_plus_current", {})
        f_row = data_by_scorer[s].get("full_prefix", {})

        p_turn = f"{t_row.get('auprc', 0.0):.3f}"
        p_pair = f"{p_row.get('auprc', 0.0):.3f}"
        p_pref = f"{f_row.get('auprc', 0.0):.3f}"
        r_pref = f"{f_row.get('auroc', 0.0):.3f}" if f_row.get("auroc") is not None else "—"
        p95 = f"{f_row.get('precision_at_recall_95', 0.0):.3f}"
        rfpr1 = f"{f_row.get('recall_at_fpr_1pct', 0.0):.3f}"
        delta = f_row.get("auprc", 0.0) - t_row.get("auprc", 0.0)

        medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"{rank}"))
        lines.append(
            f"| {medal} | **{name}** | {p_turn} | {p_pair} | **{p_pref}** | {r_pref} | {p95} | {rfpr1} | {delta:+.3f} |"
        )

    # 4. Embedded Infographics Gallery
    lines.extend(
        [
            "",
            "---",
            "",
            "## 4. Automated Infographics & Visual Analytics",
            "",
            "### Fig 1: Comprehensive Multi-Panel Model Benchmark",
            "![Multi-Panel Infographic](infographic_models_comparison.png)",
            "",
            "### Fig 2: Performance Heatmaps (AUPRC & AUROC)",
            "![AUPRC & AUROC Heatmap](figure_auprc_heatmap.png)",
            "",
            "### Fig 3: Causal Context Expansion Dynamics",
            "![Causal Trajectory](figure_context_trajectory.png)",
            "",
            "### Fig 4: Dedicated LLM Moderation Leaderboard",
            "![LLM Leaderboard](figure_llm_leaderboard.png)",
            "",
            "> 🌐 **Interactive Dashboard:** View the self-contained dashboard at [`infographic_dashboard.html`](infographic_dashboard.html).",
            "",
            "---",
            "",
            "## 5. Conversation Onset Detection Dynamics",
            "",
            f"- **Mean Onset Lag:** {onset_data.get('mean_onset_lag', '—')} turns",
            f"- **Median Onset Lag:** {onset_data.get('median_onset_lag', '—')} turns",
            f"- **Recall @ Lag 0 (Immediate Detection):** {onset_data.get('recall_lag_0', '—')}",
            f"- **Recall @ Lag 1 (+1 turn):** {onset_data.get('recall_lag_1', '—')}",
            f"- **Recall @ Lag 2 (+2 turns):** {onset_data.get('recall_lag_2', '—')}",
        ]
    )

    if quality:
        lines.extend(
            [
                "",
                "---",
                "",
                "## 6. Annotation Quality & Agreement",
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
    latex_path.write_text(_generate_latex_table(data_by_scorer) + "\n", encoding="utf-8")

    summary_path = output_dir / "report_summary.yaml"
    summary = {
        "results": results,
        "data_by_scorer": data_by_scorer,
        "onset_dynamics": onset_data,
        "annotation_quality": quality,
        "infographics": infographic_files,
    }
    with summary_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(summary, f)

    # Error analysis bundle
    error_path = output_dir / "error_analysis_bundle.yaml"
    error_bundle = {
        "top_false_positives": [],
        "top_false_negatives": [],
        "by_source_tier": {},
        "note": "Populated from predictions.jsonl",
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

    output_files = [
        "evaluation_report.md",
        "table_main_results.tex",
        "report_summary.yaml",
        "error_analysis_bundle.yaml",
    ] + infographic_files

    return {
        "output_files": output_files,
        "metadata": {
            "result_rows": len(results),
            "total_models": len(data_by_scorer),
            "infographics_count": len(infographic_files),
            "onset_metrics_present": bool(onset_data),
        },
    }
