"""Automated Infographics and Visualizations for YouthEscalateBench."""

import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import structlog

logger = structlog.get_logger()


def _format_model_from_spec(mdl: str) -> str:
    """Convert model spec (e.g. 'z-ai/glm-5.3-flash' or 'google/gemma-4-31b-it:free') into a clean human title."""
    org = mdl.split("/")[0] if "/" in mdl else ""
    base = mdl.split("/")[-1]
    is_free = False
    if base.endswith(":free") or base.endswith("_free"):
        is_free = True
        base = base[:-5]

    # Convert version number patterns like 5_3 or 2_5 (single digit subversion) into 5.3, 2.5
    base = re.sub(r"(^|[\s_/-])(\d+)_(\d)(?=[\s_/-]|$)", r"\1\2.\3", base)
    # Also handle decimal parameter counts like 2_6b or 1_5b into 2.6B, 1.5B
    base = re.sub(r"(^|[\s_/-])(\d+)_(\d)[bB](?=[\s_/-]|$)", r"\1\2.\3B", base)

    parts = base.replace("-", " ").replace("_", " ").split()
    out: list[str] = []
    if org.lower() == "liquid" and not any(p.lower() == "liquid" for p in parts):
        out.append("Liquid")

    for p in parts:
        pl = p.lower()
        if pl in ("glm", "gpt", "lfm", "llm", "it", "ai", "dpo", "rlhf"):
            token = p.upper()
        elif pl in ("qwen", "llama", "gemma", "mistral", "claude", "gemini", "deepseek"):
            token = p.title()
        elif pl.endswith("b") and pl[:-1].replace(".", "").isdigit():
            token = p.upper()
        elif pl == "dots":
            token = "Dots"
        elif pl == "nemotron":
            token = "Nemotron"
        elif pl in ("flash", "safety", "instruct", "preview", "note", "content"):
            token = p.capitalize()
        else:
            token = p.title()

        if not out or out[-1].lower() != token.lower():
            out.append(token)

    name = " ".join(out)
    if "Nemotron" in name and "Content Safety" in name:
        name = name.replace("Content Safety", "Safety")
    if is_free:
        name += " (Free)"
    return name


def _get_display_name(scorer_id: str) -> tuple[str, str]:
    """Return clean human-readable name and model family."""
    mapping = {
        "prompted_llm_judge": ("Gemma 4 31B (Default Judge)", "LLM Judge"),
        "ensemble_moderator": ("Ensemble Moderator", "Ensemble"),
        "char_ngram_tfidf": ("Char N-Gram TF-IDF", "Subword Baseline"),
        "lexicon_raw": ("Raw Lexicon Match", "Lexical Baseline"),
        "lexicon_normalized": ("Normalized Lexicon", "Lexical Baseline"),
        "lexicon_full_context": ("Full-Context Lexicon", "Lexical Baseline"),
        "rule_based_safeguard": ("Rule Safeguard Expert", "Rule Baseline"),
    }
    if scorer_id in mapping:
        return mapping[scorer_id]

    # Dynamic lookup from all models defined in .env for OpenRouter
    try:
        from youth_escalate_bench.llm import get_openrouter_models

        for mdl in get_openrouter_models():
            clean_id = mdl.split("/")[-1].replace(":", "_").replace("-", "_").replace(".", "_")
            key = f"llm_openrouter_{clean_id}"
            if scorer_id in (key, mdl, f"openrouter/{mdl}"):
                return (_format_model_from_spec(mdl), "OpenRouter LLM")
    except Exception:
        pass

    # Pattern-based provider matching for OpenRouter and LLM providers
    if scorer_id.startswith("llm_openrouter_"):
        slug = scorer_id[len("llm_openrouter_") :]
        return (_format_model_from_spec(slug), "OpenRouter LLM")
    if scorer_id.startswith("openrouter_"):
        slug = scorer_id[len("openrouter_") :]
        return (_format_model_from_spec(slug), "OpenRouter LLM")
    if scorer_id.startswith("llm_groq_"):
        slug = scorer_id[len("llm_groq_") :]
        return (_format_model_from_spec(slug), "Groq LLM")
    if scorer_id.startswith("llm_mistral_"):
        slug = scorer_id[len("llm_mistral_") :]
        return (_format_model_from_spec(slug), "Mistral LLM")
    if scorer_id.startswith("llm_gemini_"):
        slug = scorer_id[len("llm_gemini_") :]
        return (_format_model_from_spec(slug), "Gemini LLM")
    if scorer_id.startswith("llm_openai_"):
        slug = scorer_id[len("llm_openai_") :]
        return (_format_model_from_spec(slug), "OpenAI LLM")
    if scorer_id.startswith("llm_anthropic_"):
        slug = scorer_id[len("llm_anthropic_") :]
        return (_format_model_from_spec(slug), "Anthropic LLM")
    if scorer_id.startswith("llm_together_"):
        slug = scorer_id[len("llm_together_") :]
        return (_format_model_from_spec(slug), "Together LLM")
    if scorer_id.startswith("llm_cohere_"):
        slug = scorer_id[len("llm_cohere_") :]
        return (_format_model_from_spec(slug), "Cohere LLM")
    if scorer_id.startswith("llm_deepseek_"):
        slug = scorer_id[len("llm_deepseek_") :]
        return (_format_model_from_spec(slug), "DeepSeek LLM")
    if scorer_id.startswith("llm_qwen_"):
        slug = scorer_id[len("llm_qwen_") :]
        return (_format_model_from_spec(slug), "Qwen LLM")
    if scorer_id.startswith("llm_glm_"):
        slug = scorer_id[len("llm_glm_") :]
        return (_format_model_from_spec(slug), "GLM LLM")
    if scorer_id.startswith("llm_ollama_"):
        slug = scorer_id[len("llm_ollama_") :]
        return (_format_model_from_spec(slug), "Ollama Local LLM")
    if scorer_id.startswith("llm_huggingface_"):
        slug = scorer_id[len("llm_huggingface_") :]
        return (_format_model_from_spec(slug), "HuggingFace LLM")
    if scorer_id.startswith("llm_"):
        slug = scorer_id[len("llm_") :]
        return (_format_model_from_spec(slug), "LLM Model")

    return (scorer_id.replace("_", " ").title(), "Custom")


def _get_float(d: dict[str, Any] | None, key: str, default: float = 0.0) -> float:
    """Safely extract float from metric dict handling None, missing keys, and invalid types."""
    if not isinstance(d, dict):
        return default
    val = d.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def generate_all_infographics(
    results: list[dict[str, Any]],
    output_dir: Path,
    onset_data: dict[str, Any] | None = None,
) -> list[str]:
    """Generate all publication-ready infographics, charts, and standalone HTML dashboard."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_files: list[str] = []

    # Organize data into structured dict: data[scorer][condition] -> dict of metrics
    data_by_scorer: dict[str, dict[str, dict[str, Any]]] = {}
    for row in results:
        scorer = row.get("scorer", "")
        cond = row.get("condition", "")
        if scorer not in data_by_scorer:
            data_by_scorer[scorer] = {}
        data_by_scorer[scorer][cond] = row

    if not data_by_scorer:
        return generated_files

    # Try generating figures with matplotlib
    try:
        f1 = _generate_multipanel_infographic(
            data_by_scorer, output_dir / "infographic_models_comparison.png"
        )
        if f1:
            generated_files.append(f1)
        f2 = _generate_heatmap_infographic(data_by_scorer, output_dir / "figure_auprc_heatmap.png")
        if f2:
            generated_files.append(f2)
        f3 = _generate_context_trajectory(
            data_by_scorer, output_dir / "figure_context_trajectory.png"
        )
        if f3:
            generated_files.append(f3)
        f4 = _generate_llm_leaderboard(data_by_scorer, output_dir / "figure_llm_leaderboard.png")
        if f4:
            generated_files.append(f4)
    except Exception as e:
        logger.warning("infographics_matplotlib_error", error=str(e))

    # Generate interactive standalone HTML dashboard
    try:
        f_html = _generate_html_dashboard(
            data_by_scorer, onset_data, output_dir / "infographic_dashboard.html"
        )
        if f_html:
            generated_files.append(f_html)
    except Exception as e:
        logger.warning("infographics_html_dashboard_error", error=str(e))

    return generated_files


def _generate_multipanel_infographic(
    data: dict[str, dict[str, dict[str, Any]]],
    out_path: Path,
) -> str:
    """Generate high-resolution 4-panel infographic comparison figure."""
    plt.style.use(
        "seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default"
    )
    fig, axes = plt.subplots(2, 2, figsize=(16, 12), dpi=300)
    fig.patch.set_facecolor("#0b0f19")

    # Colors
    c_turn = "#38bdf8"  # Sky blue
    c_pair = "#818cf8"  # Indigo
    c_prefix = "#34d399"  # Emerald

    # Text & Grid styles
    for ax in axes.flat:
        ax.set_facecolor("#111827")
        ax.tick_params(colors="#94a3b8", labelsize=9)
        ax.grid(color="#1e293b", linestyle="--", linewidth=0.7, alpha=0.7)
        for spine in ax.spines.values():
            spine.set_color("#334155")

    # Order models: LLMs first, then Ensemble, then Baselines
    scorers = list(data.keys())

    def sort_key(s: str) -> tuple[int, float]:
        name, family = _get_display_name(s)
        pref = _get_float(data[s].get("full_prefix"), "auprc", 0.0)
        fam_order = 0 if "LLM" in family else (1 if "Ensemble" in family else 2)
        return (fam_order, -pref)

    sorted_scorers = sorted(scorers, key=sort_key)
    names = [_get_display_name(s)[0] for s in sorted_scorers]

    # --- Panel 1: AUPRC across Conditions ---
    ax1 = axes[0, 0]
    y = np.arange(len(sorted_scorers))
    height = 0.26

    auprc_turn = [
        _get_float(data[s].get("current_turn_only"), "auprc", 0.0) for s in sorted_scorers
    ]
    auprc_pair = [
        _get_float(data[s].get("prev_plus_current"), "auprc", 0.0) for s in sorted_scorers
    ]
    auprc_pref = [_get_float(data[s].get("full_prefix"), "auprc", 0.0) for s in sorted_scorers]

    ax1.barh(
        y + height,
        auprc_turn,
        height,
        label="Turn Only",
        color=c_turn,
        alpha=0.9,
        edgecolor="#0284c7",
    )
    ax1.barh(
        y, auprc_pair, height, label="Prev + Turn", color=c_pair, alpha=0.9, edgecolor="#6366f1"
    )
    ax1.barh(
        y - height,
        auprc_pref,
        height,
        label="Full Prefix",
        color=c_prefix,
        alpha=0.9,
        edgecolor="#059669",
    )

    ax1.set_yticks(y)
    ax1.set_yticklabels(names, fontsize=9, color="#f1f5f9", fontweight="medium")
    ax1.set_xlim(0, 1.05)
    ax1.set_xlabel(
        "AUPRC (Area Under Precision-Recall Curve)", color="#cbd5e1", fontsize=10, fontweight="bold"
    )
    ax1.set_title(
        "A. Moderation Performance (AUPRC) across Context Conditions",
        color="#f8fafc",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    ax1.legend(
        loc="lower right",
        facecolor="#1e293b",
        edgecolor="#475569",
        labelcolor="#f8fafc",
        fontsize=9,
    )
    ax1.invert_yaxis()

    # --- Panel 2: AUROC across Conditions ---
    ax2 = axes[0, 1]
    auroc_turn = [
        _get_float(data[s].get("current_turn_only"), "auroc", 0.0) for s in sorted_scorers
    ]
    auroc_pair = [
        _get_float(data[s].get("prev_plus_current"), "auroc", 0.0) for s in sorted_scorers
    ]
    auroc_pref = [_get_float(data[s].get("full_prefix"), "auroc", 0.0) for s in sorted_scorers]

    ax2.barh(
        y + height,
        auroc_turn,
        height,
        label="Turn Only",
        color=c_turn,
        alpha=0.9,
        edgecolor="#0284c7",
    )
    ax2.barh(
        y, auroc_pair, height, label="Prev + Turn", color=c_pair, alpha=0.9, edgecolor="#6366f1"
    )
    ax2.barh(
        y - height,
        auroc_pref,
        height,
        label="Full Prefix",
        color=c_prefix,
        alpha=0.9,
        edgecolor="#059669",
    )

    ax2.set_yticks(y)
    ax2.set_yticklabels([])
    ax2.set_xlim(0.4, 1.05)
    ax2.set_xlabel("AUROC (Area Under ROC Curve)", color="#cbd5e1", fontsize=10, fontweight="bold")
    ax2.set_title(
        "B. Discrimination Power (AUROC) across Context Conditions",
        color="#f8fafc",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    ax2.legend(
        loc="lower right",
        facecolor="#1e293b",
        edgecolor="#475569",
        labelcolor="#f8fafc",
        fontsize=9,
    )
    ax2.invert_yaxis()

    # --- Panel 3: Context Sensitivity Delta (Full Prefix - Turn Only) ---
    ax3 = axes[1, 0]
    delta_auprc = [p - t for p, t in zip(auprc_pref, auprc_turn, strict=True)]
    delta_colors = ["#10b981" if d >= 0 else "#ef4444" for d in delta_auprc]

    bars = ax3.barh(
        y, delta_auprc, height=0.55, color=delta_colors, alpha=0.85, edgecolor="#334155"
    )
    ax3.axvline(0, color="#64748b", linewidth=1.2, linestyle="--")
    ax3.set_yticks(y)
    ax3.set_yticklabels(names, fontsize=9, color="#f1f5f9", fontweight="medium")
    ax3.set_xlabel(
        r"$\Delta$ AUPRC ($\text{Full Prefix} - \text{Turn Only}$)",
        color="#cbd5e1",
        fontsize=10,
        fontweight="bold",
    )
    ax3.set_title(
        "C. Causal Context Sensitivity Gain / Shift",
        color="#f8fafc",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    ax3.invert_yaxis()

    # Add text labels on bars
    for bar, d in zip(bars, delta_auprc, strict=True):
        offset = 0.01 if d >= 0 else -0.01
        ha = "left" if d >= 0 else "right"
        ax3.text(
            d + offset,
            bar.get_y() + bar.get_height() / 2,
            f"{d:+.3f}",
            va="center",
            ha=ha,
            fontsize=8,
            color="#e2e8f0",
            fontweight="bold",
        )

    # --- Panel 4: LLM Frontier vs Baselines Comparison ---
    ax4 = axes[1, 1]
    # Filter LLMs
    llm_scorers = [s for s in sorted_scorers if "LLM" in _get_display_name(s)[1]]
    llm_names = [_get_display_name(s)[0] for s in llm_scorers]
    llm_y = np.arange(len(llm_scorers))

    p95 = [
        _get_float(data[s].get("full_prefix"), "precision_at_recall_95", 0.0) for s in llm_scorers
    ]
    rfpr1 = [_get_float(data[s].get("full_prefix"), "recall_at_fpr_1pct", 0.0) for s in llm_scorers]

    w = 0.35
    if len(llm_scorers) > 0:
        ax4.barh(
            llm_y + w / 2,
            p95,
            w,
            label="Precision @ Recall 95%",
            color="#f59e0b",
            alpha=0.9,
            edgecolor="#d97706",
        )
        ax4.barh(
            llm_y - w / 2,
            rfpr1,
            w,
            label="Recall @ FPR 1%",
            color="#ec4899",
            alpha=0.9,
            edgecolor="#db2777",
        )
        ax4.set_yticks(llm_y)
        ax4.set_yticklabels(llm_names, fontsize=9, color="#f1f5f9", fontweight="medium")
        ax4.legend(
            loc="lower right",
            facecolor="#1e293b",
            edgecolor="#475569",
            labelcolor="#f8fafc",
            fontsize=9,
        )
    ax4.set_xlim(0, 1.05)
    ax4.set_xlabel(
        "High-Precision / Low-FPR Operating Points", color="#cbd5e1", fontsize=10, fontweight="bold"
    )
    ax4.set_title(
        "D. LLM Safety Regimes (Full Prefix Operating Points)",
        color="#f8fafc",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    ax4.invert_yaxis()

    # Supertitle and Metadata
    plt.suptitle(
        "YouthEscalateBench — Automated Multi-Model Causal Moderation Benchmark",
        fontsize=16,
        fontweight="bold",
        color="#ffffff",
        y=0.99,
    )
    plt.tight_layout(rect=[0, 0.02, 1, 0.97])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return out_path.name


def _generate_heatmap_infographic(
    data: dict[str, dict[str, dict[str, Any]]],
    out_path: Path,
) -> str:
    """Generate high-contrast color heatmap of AUPRC and AUROC matrix."""
    scorers = list(data.keys())

    def sort_key(s: str) -> tuple[int, float]:
        name, family = _get_display_name(s)
        pref = _get_float(data[s].get("full_prefix"), "auprc", 0.0)
        fam_order = 0 if "LLM" in family else (1 if "Ensemble" in family else 2)
        return (fam_order, -pref)

    sorted_scorers = sorted(scorers, key=sort_key)
    names = [_get_display_name(s)[0] for s in sorted_scorers]
    conditions = ["current_turn_only", "prev_plus_current", "full_prefix"]
    cond_labels = ["Turn Only (Isolated)", "Prev + Turn (Local)", "Full Prefix (Causal)"]

    matrix_auprc = np.zeros((len(sorted_scorers), len(conditions)))
    matrix_auroc = np.zeros((len(sorted_scorers), len(conditions)))

    for i, s in enumerate(sorted_scorers):
        for j, c in enumerate(conditions):
            matrix_auprc[i, j] = _get_float(data[s].get(c), "auprc", 0.0)
            matrix_auroc[i, j] = _get_float(data[s].get(c), "auroc", 0.0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 8), dpi=300)
    fig.patch.set_facecolor("#0b0f19")

    for ax in (ax1, ax2):
        ax.set_facecolor("#111827")
        ax.tick_params(colors="#94a3b8", labelsize=9)

    # AUPRC Heatmap
    ax1.imshow(matrix_auprc, cmap="viridis", vmin=0.45, vmax=1.0, aspect="auto")
    ax1.set_xticks(range(len(conditions)))
    ax1.set_xticklabels(cond_labels, color="#f8fafc", fontsize=10, fontweight="bold")
    ax1.set_yticks(range(len(sorted_scorers)))
    ax1.set_yticklabels(names, color="#f8fafc", fontsize=9, fontweight="medium")
    ax1.set_title(
        "AUPRC Across Context Conditions", color="#f8fafc", fontsize=12, fontweight="bold", pad=12
    )

    for i in range(len(sorted_scorers)):
        for j in range(len(conditions)):
            val = matrix_auprc[i, j]
            text_color = "black" if val > 0.85 else "white"
            ax1.text(
                j,
                i,
                f"{val:.3f}",
                ha="center",
                va="center",
                color=text_color,
                fontweight="bold",
                fontsize=9,
            )

    # AUROC Heatmap
    ax2.imshow(matrix_auroc, cmap="plasma", vmin=0.8, vmax=1.0, aspect="auto")
    ax2.set_xticks(range(len(conditions)))
    ax2.set_xticklabels(cond_labels, color="#f8fafc", fontsize=10, fontweight="bold")
    ax2.set_yticks(range(len(sorted_scorers)))
    ax2.set_yticklabels([])
    ax2.set_title(
        "AUROC Across Context Conditions", color="#f8fafc", fontsize=12, fontweight="bold", pad=12
    )

    for i in range(len(sorted_scorers)):
        for j in range(len(conditions)):
            val = matrix_auroc[i, j]
            text_color = "black" if val > 0.95 else "white"
            ax2.text(
                j,
                i,
                f"{val:.3f}",
                ha="center",
                va="center",
                color=text_color,
                fontweight="bold",
                fontsize=9,
            )

    plt.suptitle(
        "YouthEscalateBench — Performance Heatmaps by Model & Context Condition",
        color="#ffffff",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    plt.tight_layout(rect=[0, 0.02, 1, 0.95])

    plt.savefig(out_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return out_path.name


def _generate_context_trajectory(
    data: dict[str, dict[str, dict[str, Any]]],
    out_path: Path,
) -> str:
    """Generate trajectory lines showing how each model evolves across the 3 context windows."""
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    fig.patch.set_facecolor("#0b0f19")
    ax.set_facecolor("#111827")
    ax.tick_params(colors="#94a3b8", labelsize=10)
    ax.grid(color="#1e293b", linestyle="--", linewidth=0.7, alpha=0.7)
    for spine in ax.spines.values():
        spine.set_color("#334155")

    conditions = ["current_turn_only", "prev_plus_current", "full_prefix"]
    cond_labels = ["1. Isolated Turn", "2. Prev + Current", "3. Full Prefix"]
    x = [1, 2, 3]

    colors = [
        "#38bdf8",
        "#34d399",
        "#f59e0b",
        "#ec4899",
        "#818cf8",
        "#a78bfa",
        "#f43f5e",
        "#10b981",
        "#64748b",
        "#cbd5e1",
    ]
    scorers = list(data.keys())

    for idx, s in enumerate(scorers):
        y_vals = [_get_float(data[s].get(c), "auprc", 0.0) for c in conditions]
        name, family = _get_display_name(s)
        color = colors[idx % len(colors)]
        style = "-" if "LLM" in family else ("--" if "Ensemble" in family else ":")
        linewidth = 2.5 if "LLM" in family else 1.5
        marker = "o" if "LLM" in family else "s"

        ax.plot(
            x,
            y_vals,
            style,
            color=color,
            linewidth=linewidth,
            marker=marker,
            markersize=6,
            label=f"{name}",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(cond_labels, color="#f8fafc", fontsize=11, fontweight="bold")
    ax.set_ylabel("AUPRC Score", color="#f8fafc", fontsize=11, fontweight="bold")
    ax.set_ylim(0.4, 1.05)
    ax.set_title(
        "Causal Context Trajectory: Model Performance Dynamics as Context Expands",
        color="#f8fafc",
        fontsize=13,
        fontweight="bold",
        pad=15,
    )
    ax.legend(
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        facecolor="#1e293b",
        edgecolor="#475569",
        labelcolor="#f8fafc",
        fontsize=8.5,
    )

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return out_path.name


def _generate_llm_leaderboard(
    data: dict[str, dict[str, dict[str, Any]]],
    out_path: Path,
) -> str:
    """Generate dedicated LLM Leaderboard horizontal ranking chart."""
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    fig.patch.set_facecolor("#0b0f19")
    ax.set_facecolor("#111827")
    ax.tick_params(colors="#94a3b8", labelsize=10)
    ax.grid(color="#1e293b", linestyle="--", linewidth=0.7, alpha=0.7)
    for spine in ax.spines.values():
        spine.set_color("#334155")

    llm_scorers = [s for s in data.keys() if "LLM" in _get_display_name(s)[1]]
    llm_scorers.sort(
        key=lambda s: _get_float(data[s].get("full_prefix"), "auprc", 0.0), reverse=True
    )

    names = [_get_display_name(s)[0] for s in llm_scorers]
    scores = [_get_float(data[s].get("full_prefix"), "auprc", 0.0) for s in llm_scorers]
    y = np.arange(len(llm_scorers))

    palette = ["#38bdf8", "#34d399", "#818cf8", "#f59e0b", "#ec4899", "#a78bfa"]
    bar_colors = [palette[i % len(palette)] for i in range(len(llm_scorers))]
    bars = ax.barh(
        y, scores, height=0.55, color=bar_colors, alpha=0.9, edgecolor="#334155"
    )

    ax.set_yticks(y)
    ax.set_yticklabels(names, color="#f8fafc", fontsize=10, fontweight="bold")
    ax.set_xlim(0, 1.1)
    ax.set_xlabel("Full Prefix AUPRC", color="#f8fafc", fontsize=11, fontweight="bold")
    ax.set_title(
        "LLM Moderation Leaderboard (Full Conversation Context)",
        color="#f8fafc",
        fontsize=13,
        fontweight="bold",
        pad=15,
    )
    ax.invert_yaxis()

    for bar, val in zip(bars, scores, strict=True):
        ax.text(
            val + 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.3f}",
            va="center",
            ha="left",
            fontsize=10,
            color="#ffffff",
            fontweight="bold",
        )

    plt.tight_layout()
    plt.savefig(out_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return out_path.name


def _generate_html_dashboard(
    data: dict[str, dict[str, dict[str, Any]]],
    onset_data: dict[str, Any] | None,
    out_path: Path,
) -> str:
    """Generate self-contained interactive dark-mode HTML infographic dashboard."""
    scorers = list(data.keys())

    rows_html = []
    for s in scorers:
        name, family = _get_display_name(s)
        c_turn = data[s].get("current_turn_only", {})
        c_pair = data[s].get("prev_plus_current", {})
        c_pref = data[s].get("full_prefix", {})

        p_turn = f"{_get_float(c_turn, 'auprc', 0.0):.3f}"
        r_turn = (
            f"{_get_float(c_turn, 'auroc', 0.0):.3f}" if c_turn.get("auroc") is not None else "—"
        )
        p_pair = f"{_get_float(c_pair, 'auprc', 0.0):.3f}"
        r_pair = (
            f"{_get_float(c_pair, 'auroc', 0.0):.3f}" if c_pair.get("auroc") is not None else "—"
        )
        p_pref = f"{_get_float(c_pref, 'auprc', 0.0):.3f}"
        r_pref = (
            f"{_get_float(c_pref, 'auroc', 0.0):.3f}" if c_pref.get("auroc") is not None else "—"
        )

        delta = _get_float(c_pref, "auprc", 0.0) - _get_float(c_turn, "auprc", 0.0)
        delta_badge = f"<span class='badge {'badge-green' if delta >= 0 else 'badge-red'}'>{delta:+.3f}</span>"
        fam_badge = (
            f"<span class='badge badge-purple'>{family}</span>"
            if "LLM" in family
            else (
                f"<span class='badge badge-blue'>{family}</span>"
                if "Ensemble" in family
                else f"<span class='badge badge-gray'>{family}</span>"
            )
        )

        rows_html.append(f"""
        <tr>
            <td class="model-name"><strong>{name}</strong></td>
            <td>{fam_badge}</td>
            <td><span class="score-pill">{p_turn}</span> <span class="sub-score">({r_turn})</span></td>
            <td><span class="score-pill">{p_pair}</span> <span class="sub-score">({r_pair})</span></td>
            <td><span class="score-pill score-highlight">{p_pref}</span> <span class="sub-score">({r_pref})</span></td>
            <td>{delta_badge}</td>
        </tr>
        """)

    table_rows = "\n".join(rows_html)

    # Top stats
    best_llm_score = max(
        (
            _get_float(data[s].get("full_prefix"), "auprc", 0.0)
            for s in scorers
            if "LLM" in _get_display_name(s)[1]
        ),
        default=0.0,
    )
    best_baseline_score = max(
        (
            _get_float(data[s].get("full_prefix"), "auprc", 0.0)
            for s in scorers
            if "Baseline" in _get_display_name(s)[1]
        ),
        default=0.0,
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouthEscalateBench — Causal Moderation Infographic Dashboard</title>
    <style>
        :root {{
            --bg-main: #0b0f19;
            --bg-card: #111827;
            --bg-card-hover: #1f2937;
            --border-color: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-cyan: #38bdf8;
            --accent-emerald: #34d399;
            --accent-purple: #a855f7;
            --accent-amber: #f59e0b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-main);
            color: var(--text-main);
            line-height: 1.6;
            padding: 2rem 1.5rem;
        }}
        .container {{ max-width: 1300px; margin: 0 auto; }}
        .header {{
            text-align: center;
            margin-bottom: 2.5rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}
        .header h1 {{
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #38bdf8, #818cf8, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}
        .header p {{ color: var(--text-muted); font-size: 1.05rem; }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }}
        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        .kpi-title {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); }}
        .kpi-value {{ font-size: 1.8rem; font-weight: 700; color: var(--accent-cyan); margin: 0.3rem 0; }}
        .kpi-sub {{ font-size: 0.8rem; color: var(--accent-emerald); }}
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        .card-title {{
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: #f1f5f9;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.92rem;
        }}
        th, td {{
            padding: 0.85rem 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            background: #0f172a;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }}
        tr:hover {{ background-color: var(--bg-card-hover); }}
        .model-name {{ color: #ffffff; font-weight: 600; }}
        .badge {{
            display: inline-block;
            padding: 0.2rem 0.55rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-purple {{ background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }}
        .badge-blue {{ background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }}
        .badge-gray {{ background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3); }}
        .badge-green {{ background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); }}
        .badge-red {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}
        .score-pill {{ font-weight: 700; color: #f8fafc; }}
        .score-highlight {{ color: #34d399; font-weight: 800; }}
        .sub-score {{ color: var(--text-muted); font-size: 0.8rem; margin-left: 0.25rem; }}
        .gallery-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
            gap: 1.5rem;
        }}
        .gallery-item {{
            background: #0f172a;
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 0.75rem;
            text-align: center;
        }}
        .gallery-item img {{
            width: 100%;
            height: auto;
            border-radius: 6px;
            display: block;
        }}
        .gallery-caption {{
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-muted);
            margin-top: 0.6rem;
        }}
        footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 0.85rem;
            margin-top: 3rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border-color);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>YouthEscalateBench Causal Infographics</h1>
            <p>Automated Benchmark Dashboard & Multi-LLM Context Sensitivity Analysis</p>
        </header>

        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-title">Total Evaluated Models</div>
                <div class="kpi-value">{len(scorers)}</div>
                <div class="kpi-sub">6 LLMs & 6 Baselines</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Top Frontier LLM (AUPRC)</div>
                <div class="kpi-value">{best_llm_score:.3f}</div>
                <div class="kpi-sub">Gemma 4 31B Judge</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Top Baseline (AUPRC)</div>
                <div class="kpi-value">{best_baseline_score:.3f}</div>
                <div class="kpi-sub">Char N-Gram TF-IDF</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Causal Conditions</div>
                <div class="kpi-value">3</div>
                <div class="kpi-sub">Turn / Prev+Turn / Prefix</div>
            </div>
        </div>

        <section class="card">
            <h2 class="card-title">📊 Multi-Model Performance Matrix across Context Conditions</h2>
            <table>
                <thead>
                    <tr>
                        <th>Model / Scorer</th>
                        <th>Type</th>
                        <th>Turn Only AUPRC (AUROC)</th>
                        <th>Prev + Turn AUPRC (AUROC)</th>
                        <th>Full Prefix AUPRC (AUROC)</th>
                        <th>Δ Prefix Gain</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </section>

        <section class="card">
            <h2 class="card-title">📈 Automated Infographics & Visual Analytics</h2>
            <div class="gallery-grid">
                <div class="gallery-item">
                    <img src="infographic_models_comparison.png" alt="Multi-Panel Infographic">
                    <div class="gallery-caption">Fig 1: Comprehensive Multi-Panel Model Benchmark</div>
                </div>
                <div class="gallery-item">
                    <img src="figure_auprc_heatmap.png" alt="Performance Heatmap">
                    <div class="gallery-caption">Fig 2: AUPRC & AUROC Performance Matrix Heatmaps</div>
                </div>
                <div class="gallery-item">
                    <img src="figure_context_trajectory.png" alt="Context Trajectory">
                    <div class="gallery-caption">Fig 3: Causal Context Expansion Trajectory</div>
                </div>
                <div class="gallery-item">
                    <img src="figure_llm_leaderboard.png" alt="LLM Leaderboard">
                    <div class="gallery-caption">Fig 4: Dedicated LLM Leaderboard (Full Prefix)</div>
                </div>
            </div>
        </section>

        <footer>
            YouthEscalateBench — Benchmark version 0.1.2 • Auto-generated by Reporting Pipeline
        </footer>
    </div>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")
    return out_path.name
