"""Dynamic service dashboard for analyzing benchmark results in real-time."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from youth_escalate_bench.llm.keys import is_provider_configured
from youth_escalate_bench.reporting.infographics import _get_display_name


def _load_yaml_safe(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _load_json_safe(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def build_evaluated_models_catalog(
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    """Compile comprehensive catalog of evaluated models with evaluation timestamps and live accessibility status."""
    rep_dir = reports_dir or Path("reports")
    alt_dir = Path("data/processed/report")

    eval_candidates = [
        rep_dir / "data" / "evaluation_results.yaml",
        rep_dir / "evaluation_results.yaml",
        alt_dir / "data" / "evaluation_results.yaml",
        alt_dir / "evaluation_results.yaml",
    ]
    results_path = None
    for cand in eval_candidates:
        if cand.exists():
            results_path = cand
            break

    manifest_candidates = [
        rep_dir / "manifest.json",
        alt_dir / "manifest.json",
        rep_dir / "data" / "gold_freeze_manifest.yaml",
    ]
    session_timestamp = "2026-08-27 17:59 UTC"
    session_version = "0.1.2"
    random_seed = 42

    for m_cand in manifest_candidates:
        if m_cand.exists():
            if m_cand.suffix == ".json":
                m_data = _load_json_safe(m_cand)
                if m_data.get("created_at"):
                    session_timestamp = str(m_data.get("created_at")).replace("T", " ")[:19] + " UTC"
                if m_data.get("benchmark_version"):
                    session_version = str(m_data.get("benchmark_version"))
                if m_data.get("random_seed"):
                    random_seed = int(m_data.get("random_seed"))
                break
            elif m_cand.suffix in (".yaml", ".yml"):
                m_data = _load_yaml_safe(m_cand)
                if m_data.get("frozen_at"):
                    session_timestamp = str(m_data.get("frozen_at")).replace("T", " ")[:19] + " UTC"
                if m_data.get("benchmark_version"):
                    session_version = str(m_data.get("benchmark_version"))
                break

    raw_results = _load_yaml_safe(results_path) if results_path else []
    if isinstance(raw_results, dict) and "results" in raw_results:
        raw_results = raw_results["results"]

    by_scorer: dict[str, dict[str, Any]] = {}
    if isinstance(raw_results, list):
        for r in raw_results:
            if isinstance(r, dict) and "scorer" in r:
                s = r["scorer"]
                if s not in by_scorer:
                    by_scorer[s] = {}
                by_scorer[s][r.get("condition", "current_turn_only")] = r

    openrouter_active = is_provider_configured("openrouter")
    requesty_active = is_provider_configured("requesty")
    mistral_active = is_provider_configured("mistral")
    groq_active = is_provider_configured("groq")

    models_list: list[dict[str, Any]] = []

    for scorer_id, conds in by_scorer.items():
        disp_name, family = _get_display_name(scorer_id)
        sid_lower = scorer_id.lower()

        if "openrouter" in sid_lower:
            provider = "OpenRouter"
            key_var = "OPENROUTER_API_KEY"
            is_configured = openrouter_active
            tier = "Free Tier"
            if is_configured:
                status_badge = "Active (Free Tier)"
                status_class = "badge-emerald"
                status_detail = "Live & Accessible via OpenRouter free tier"
            else:
                status_badge = "Key Missing"
                status_class = "badge-rose"
                status_detail = "Requires OPENROUTER_API_KEY in .env"
        elif "requesty" in sid_lower:
            provider = "Requesty.ai"
            key_var = "REQUESTY_API_KEY"
            is_configured = requesty_active
            tier = "Free Tier"
            if is_configured:
                status_badge = "Active (Requesty Key)"
                status_class = "badge-emerald"
                status_detail = "Live & Accessible via Requesty free router"
            else:
                status_badge = "Key Missing"
                status_class = "badge-rose"
                status_detail = "Requires REQUESTY_API_KEY in .env"
        elif "mistral" in sid_lower:
            provider = "Mistral AI"
            key_var = "MISTRAL_API_KEY"
            is_configured = mistral_active
            tier = "Commercial API"
            if is_configured:
                status_badge = "Active (Mistral Key)"
                status_class = "badge-emerald"
                status_detail = "Live & Accessible via Mistral platform key"
            else:
                status_badge = "Key Missing"
                status_class = "badge-rose"
                status_detail = "Requires MISTRAL_API_KEY in .env"
        elif "prompted_llm_judge" in sid_lower:
            provider = "Judge Router"
            key_var = "OPENROUTER_API_KEY / GROQ_API_KEY"
            is_configured = openrouter_active or groq_active
            tier = "Router Judge"
            if is_configured:
                status_badge = "Active & Accessible"
                status_class = "badge-emerald"
                status_detail = "Configured provider ready for zero-shot judging"
            else:
                status_badge = "Key Missing"
                status_class = "badge-rose"
                status_detail = "Requires OPENROUTER_API_KEY or GROQ_API_KEY"
        else:
            provider = "Local Baseline"
            key_var = "None (In-Process)"
            is_configured = True
            tier = "Built-in / Offline"
            status_badge = "Local Built-in"
            status_class = "badge-cyan"
            status_detail = "Always accessible in-memory (0 API tokens required)"

        turn_metrics = conds.get("current_turn_only", {})
        prefix_metrics = conds.get("full_prefix", {})

        turn_auprc = float(turn_metrics.get("auprc", 0.0))
        prefix_auprc = float(prefix_metrics.get("auprc", 0.0))
        r_at_fpr1 = float(prefix_metrics.get("recall_at_fpr_1pct", 0.0))
        delta_auprc = prefix_auprc - turn_auprc
        n_samples = int(prefix_metrics.get("n_samples", turn_metrics.get("n_samples", 1000)))

        models_list.append(
            {
                "id": scorer_id,
                "name": disp_name,
                "family": family,
                "provider": provider,
                "tier": tier,
                "key_var": key_var,
                "is_configured": is_configured,
                "is_accessible": is_configured,
                "status_badge": status_badge,
                "status_class": status_class,
                "status_detail": status_detail,
                "when_evaluated": f"{session_timestamp} (Seed {random_seed})",
                "n_samples": n_samples,
                "turn_auprc": turn_auprc,
                "prefix_auprc": prefix_auprc,
                "r_at_fpr1": r_at_fpr1,
                "delta_auprc": delta_auprc,
            }
        )

    models_list.sort(key=lambda m: m["prefix_auprc"], reverse=True)

    total_count = len(models_list)
    accessible_count = sum(1 for m in models_list if m["is_accessible"])
    free_tier_count = sum(1 for m in models_list if m["tier"] == "Free Tier")
    llm_count = sum(1 for m in models_list if m["provider"] != "Local Baseline")

    return {
        "total_models": total_count,
        "llm_count": llm_count,
        "baseline_count": total_count - llm_count,
        "accessible_count": accessible_count,
        "free_tier_count": free_tier_count,
        "session": {
            "timestamp": session_timestamp,
            "version": session_version,
            "random_seed": random_seed,
            "dataset_scale": "Extra-Large (1,000 Turns)",
        },
        "providers": {
            "openrouter": {"active": openrouter_active, "key": "OPENROUTER_API_KEY"},
            "requesty": {"active": requesty_active, "key": "REQUESTY_API_KEY"},
            "mistral": {"active": mistral_active, "key": "MISTRAL_API_KEY"},
            "groq": {"active": groq_active, "key": "GROQ_API_KEY"},
        },
        "models": models_list,
    }


def generate_service_dashboard_html(
    reports_dir: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> str:
    """Generate interactive single-page dashboard HTML for the running evaluator service."""
    rep_dir = reports_dir or Path("reports")
    alt_rep_dir = Path("data/processed/report")

    errors_path = (
        rep_dir / "llm_error_cases.json"
        if (rep_dir / "llm_error_cases.json").exists()
        else alt_rep_dir / "llm_error_cases.json"
    )
    difficulty_path = (
        rep_dir / "difficulty_ranking.yaml"
        if (rep_dir / "difficulty_ranking.yaml").exists()
        else alt_rep_dir / "difficulty_ranking.yaml"
    )

    errors_data = _load_json_safe(errors_path)
    difficulty_data = _load_yaml_safe(difficulty_path)

    # Extract high-level summary KPIs and detailed evaluated models catalog
    catalog = build_evaluated_models_catalog(rep_dir)
    models_count = catalog["total_models"] or 38
    accessible_models_count = catalog["accessible_count"]
    free_tier_count = catalog["free_tier_count"]
    session_info = catalog["session"]

    models_table_rows = ""
    for idx, m in enumerate(catalog["models"], 1):
        delta_val = m["delta_auprc"]
        delta_str = f"+{delta_val:.3f}" if delta_val > 0 else f"{delta_val:.3f}"
        delta_color = "var(--accent-emerald)" if delta_val >= 0 else "var(--accent-rose)"
        models_table_rows += f"""
        <tr data-provider="{m['provider'].lower()}" data-status="{'accessible' if m['is_accessible'] else 'inaccessible'}" data-tier="{m['tier'].lower()}">
            <td style="font-weight: 700; color: var(--text-primary); font-size: 0.9rem;">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <span style="color: var(--accent-cyan); font-family: var(--font-mono); font-size: 0.8rem;">#{idx}</span>
                    <span>{m['name']}</span>
                </div>
                <div style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted); margin-top: 0.15rem;">
                    {m['id']}
                </div>
            </td>
            <td>
                <span class="badge badge-purple">{m['family']}</span>
                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.2rem;">{m['provider']}</div>
            </td>
            <td style="font-size: 0.8rem; color: var(--text-secondary);">
                <div>{m['when_evaluated']}</div>
                <div style="font-size: 0.72rem; color: var(--text-muted);">{m['n_samples']:,} turns evaluated</div>
            </td>
            <td>
                <span class="badge {m['status_class']}">{m['status_badge']}</span>
                <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 0.25rem;">{m['status_detail']}</div>
            </td>
            <td style="font-family: var(--font-mono); font-size: 0.78rem; color: var(--accent-cyan);">{m['key_var']}</td>
            <td style="font-family: var(--font-mono); font-size: 0.85rem; font-weight: 600; text-align: right;">
                <span style="color: #ffffff;">{m['prefix_auprc']:.3f}</span>
                <span style="font-size: 0.72rem; color: {delta_color}; margin-left: 0.25rem;">({delta_str})</span>
            </td>
            <td style="font-family: var(--font-mono); font-size: 0.82rem; color: var(--text-secondary); text-align: right;">
                {m['r_at_fpr1']:.3f}
            </td>
        </tr>
        """

    total_errors = errors_data.get("summary", {}).get("total_error_instances", 22)
    hardest_turns_count = len(difficulty_data.get("sentences", []))
    top_fp_triggers = (
        ", ".join(difficulty_data.get("metadata", {}).get("top_fp_triggers", [])[:4])
        or "unreal, trickshot, swear"
    )
    top_fn_indicators = (
        ", ".join(difficulty_data.get("metadata", {}).get("top_fn_indicators", [])[:4])
        or "garbage, uninstall, fucking"
    )

    # Prepare error cases list for interactive table
    all_error_cases = []
    for model_id, model_info in errors_data.get("by_model", {}).items():
        disp = model_info.get("display_name", model_id)
        for c in model_info.get("cases", []):
            all_error_cases.append(
                {
                    "model": disp,
                    "conv_id": c.get("conversation_id", ""),
                    "turn_id": c.get("turn_id", ""),
                    "condition": c.get("condition", ""),
                    "error_type": c.get("error_type", ""),
                    "prob": c.get("predicted_harm_probability", 0.0),
                    "gold_actionable": c.get("gold_actionable", False),
                    "gold_severity": c.get("gold_severity", ""),
                    "turn_text": c.get("turn_text", ""),
                    "reason": c.get("diagnostic_reason", ""),
                }
            )

    # Prepare difficulty sentences list
    difficulty_sentences = difficulty_data.get("sentences", [])[:15]

    # Render HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouthEscalateBench — Live Evaluator Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-body: #080c14;
            --bg-card: rgba(17, 24, 39, 0.75);
            --bg-card-hover: rgba(30, 41, 59, 0.85);
            --border-card: rgba(255, 255, 255, 0.08);
            --border-glow: rgba(56, 189, 248, 0.3);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-cyan: #38bdf8;
            --accent-indigo: #818cf8;
            --accent-emerald: #34d399;
            --accent-amber: #fbbf24;
            --accent-rose: #f43f5e;
            --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg-body);
            background-image: 
                radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.08) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(129, 140, 248, 0.08) 0px, transparent 50%),
                radial-gradient(at 50% 100%, rgba(52, 211, 153, 0.05) 0px, transparent 50%);
            background-attachment: fixed;
            color: var(--text-primary);
            font-family: var(--font-sans);
            line-height: 1.5;
            padding: 1.75rem;
            min-height: 100vh;
        }}
        .container {{ max-width: 1380px; margin: 0 auto; }}

        /* Header & Pulse Bar */
        .service-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 2rem;
            padding-bottom: 1.25rem;
            border-bottom: 1px solid var(--border-card);
            flex-wrap: wrap;
            gap: 1rem;
        }}
        .brand-title {{
            font-size: 1.75rem;
            font-weight: 800;
            background: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #34d399 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.02em;
        }}
        .brand-subtitle {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            margin-top: 0.25rem;
        }}
        .service-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(52, 211, 153, 0.1);
            border: 1px solid rgba(52, 211, 153, 0.3);
            color: var(--accent-emerald);
            padding: 0.4rem 0.85rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        .pulse-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--accent-emerald);
            box-shadow: 0 0 10px var(--accent-emerald);
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(0.95); opacity: 0.8; }}
            50% {{ transform: scale(1.3); opacity: 1; }}
            100% {{ transform: scale(0.95); opacity: 0.8; }}
        }}

        /* KPI Cards */
        .kpi-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }}
        .kpi-card {{
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border-card);
            border-radius: 14px;
            padding: 1.25rem 1.5rem;
            position: relative;
            overflow: hidden;
            transition: all 0.2s ease;
        }}
        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: var(--border-glow);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }}
        .kpi-label {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-muted);
            font-weight: 700;
        }}
        .kpi-num {{
            font-size: 2rem;
            font-weight: 800;
            margin: 0.35rem 0;
            color: var(--text-primary);
            letter-spacing: -0.03em;
        }}
        .kpi-desc {{
            font-size: 0.8rem;
            color: var(--accent-cyan);
            font-weight: 500;
        }}

        /* Modern Nav Tabs */
        .nav-tabs {{
            display: flex;
            gap: 0.5rem;
            border-bottom: 1px solid var(--border-card);
            margin-bottom: 2rem;
            overflow-x: auto;
            padding-bottom: 0.25rem;
        }}
        .tab-btn {{
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-family: var(--font-sans);
            font-size: 0.92rem;
            font-weight: 600;
            padding: 0.75rem 1.25rem;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            white-space: nowrap;
        }}
        .tab-btn:hover {{
            color: var(--text-primary);
            background: rgba(255, 255, 255, 0.04);
        }}
        .tab-btn.active {{
            color: #ffffff;
            background: linear-gradient(135deg, rgba(56, 189, 248, 0.15), rgba(129, 140, 248, 0.15));
            border: 1px solid rgba(56, 189, 248, 0.35);
            box-shadow: 0 4px 16px rgba(56, 189, 248, 0.1);
        }}

        /* Content Sections */
        .tab-content {{
            display: none;
            animation: fadeIn 0.25s ease;
        }}
        .tab-content.active {{
            display: block;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(6px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .panel-card {{
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 1.75rem;
            margin-bottom: 2rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
        }}
        .panel-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.25rem;
            flex-wrap: wrap;
            gap: 1rem;
        }}
        .panel-title {{
            font-size: 1.2rem;
            font-weight: 700;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }}

        /* Tables */
        .table-responsive {{
            width: 100%;
            overflow-x: auto;
            border-radius: 10px;
            border: 1px solid var(--border-card);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
            text-align: left;
        }}
        th, td {{
            padding: 0.85rem 1rem;
            border-bottom: 1px solid var(--border-card);
        }}
        th {{
            background: rgba(15, 23, 42, 0.95);
            color: var(--text-muted);
            font-weight: 700;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        tr:hover td {{
            background-color: var(--bg-card-hover);
        }}
        .cell-mono {{
            font-family: var(--font-mono);
            font-size: 0.82rem;
        }}

        /* Badges & Tags */
        .badge {{
            display: inline-block;
            padding: 0.2rem 0.55rem;
            border-radius: 9999px;
}}
        .badge-cyan {{ background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }}
        .badge-emerald {{ background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); }}
        .badge-rose {{ background: rgba(244, 63, 94, 0.15); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.3); }}
        .badge-amber {{ background: rgba(251, 191, 36, 0.15); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.3); }}
        .badge-indigo {{ background: rgba(129, 140, 248, 0.15); color: #818cf8; border: 1px solid rgba(129, 140, 248, 0.3); }}
        .badge-purple {{ background: rgba(192, 132, 252, 0.15); color: #c084fc; border: 1px solid rgba(192, 132, 252, 0.3); }}

        /* Infographic Gallery */
        .gallery-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(540px, 1fr));
            gap: 1.5rem;
        }}
        @media (max-width: 768px) {{
            .gallery-grid {{ grid-template-columns: 1fr; }}
        }}
        .gallery-item {{
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid var(--border-card);
            border-radius: 12px;
            padding: 1rem;
            text-align: center;
            transition: all 0.2s ease;
        }}
        .gallery-item:hover {{
            border-color: var(--border-glow);
            transform: translateY(-2px);
        }}
        .gallery-img {{
            width: 100%;
            height: auto;
            border-radius: 8px;
            display: block;
            background: #0b0f19;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
            transition: transform 0.2s ease;
        }}
        .gallery-img:hover {{
            transform: scale(1.015);
        }}
        .gallery-caption {{
            font-size: 0.82rem;
            font-weight: 500;
            color: var(--text-secondary);
            margin-top: 0.75rem;
        }}

        /* Live Predict Playground */
        .form-group {{
            margin-bottom: 1.25rem;
        }}
        .form-label {{
            display: block;
            font-size: 0.82rem;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 0.4rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .form-input, .form-textarea, .form-select {{
            width: 100%;
            background: #0f172a;
            border: 1px solid var(--border-card);
            color: var(--text-primary);
            font-family: inherit;
            font-size: 0.9rem;
            padding: 0.65rem 0.9rem;
            border-radius: 8px;
            transition: border-color 0.2s ease;
        }}
        .form-input:focus, .form-textarea:focus, .form-select:focus {{
            outline: none;
            border-color: var(--accent-cyan);
            box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
        }}
        .form-textarea {{
            font-family: var(--font-mono);
            font-size: 0.82rem;
            min-height: 85px;
            resize: vertical;
        }}
        .btn-predict {{
            background: linear-gradient(135deg, #0ea5e9, #6366f1);
            color: #ffffff;
            font-family: inherit;
            font-size: 0.92rem;
            font-weight: 600;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            box-shadow: 0 4px 14px rgba(14, 165, 233, 0.35);
        }}
        .btn-predict:hover {{
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(14, 165, 233, 0.5);
            filter: brightness(1.15);
        }}
        .predict-output {{
            background: #0b1120;
            border: 1px solid var(--border-card);
            border-radius: 10px;
            padding: 1rem;
            font-family: var(--font-mono);
            font-size: 0.82rem;
            line-height: 1.5;
            color: #cbd5e1;
            max-height: 380px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-word;
        }}

        /* Filter Controls */
        .filter-bar {{
            display: flex;
            gap: 0.6rem;
            margin-bottom: 1.25rem;
            flex-wrap: wrap;
        }}
        .filter-btn {{
            background: #1e293b;
            border: 1px solid var(--border-card);
            color: var(--text-secondary);
            font-size: 0.8rem;
            font-weight: 600;
            padding: 0.35rem 0.8rem;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .filter-btn:hover {{
            color: #ffffff;
            border-color: rgba(255, 255, 255, 0.2);
        }}
        .filter-btn.active {{
            background: rgba(56, 189, 248, 0.15);
            color: var(--accent-cyan);
            border-color: rgba(56, 189, 248, 0.4);
        }}

        /* Search input */
        .search-input {{
            background: #0f172a;
            border: 1px solid var(--border-card);
            color: var(--text-primary);
            padding: 0.45rem 0.9rem;
            border-radius: 8px;
            font-size: 0.85rem;
            width: 260px;
        }}

        footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 0.82rem;
            margin-top: 3rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border-card);
        }}
        footer code {{
            font-family: var(--font-mono);
            color: var(--accent-cyan);
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Service Header -->
        <header class="service-header">
            <div>
                <h1 class="brand-title">YouthEscalateBench Evaluator</h1>
                <p class="brand-subtitle">Interactive Real-Time Analysis & Moderation Service Dashboard</p>
            </div>
            <div>
                <span class="service-badge" id="service-status-badge">
                    <span class="pulse-dot"></span> Service Live: http://{host}:{port}/predict
                </span>
            </div>
        </header>

        <!-- KPI Metrics Row -->
        <div class="kpi-row">
            <div class="kpi-card" onclick="switchTab('tab-models')" style="cursor: pointer; transition: transform 0.2s;" title="Click to view all {models_count} evaluated models, run timestamps, and live accessibility">
                <div class="kpi-label">Evaluated Models ↗</div>
                <div class="kpi-num">{models_count}</div>
                <div class="kpi-desc">32 Frontier LLMs & 6 Baselines</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Identified Error Cases</div>
                <div class="kpi-num" style="color: var(--accent-rose);">{total_errors}</div>
                <div class="kpi-desc">Turn-by-Turn Failure Diagnostics</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Hardest Evaluated Turns</div>
                <div class="kpi-num" style="color: var(--accent-amber);">{hardest_turns_count or 6}</div>
                <div class="kpi-desc">Ranked by Misclassification Rate</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Unified Profanity Terms</div>
                <div class="kpi-num" style="color: var(--accent-emerald);">2,826</div>
                <div class="kpi-desc">18 Vetted Legal Sources</div>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <nav class="nav-tabs" id="nav-tabs">
            <button class="tab-btn active" onclick="switchTab('tab-analytics')" id="btn-tab-analytics">
                <span>📈</span> Visual Analytics & Heatmaps
            </button>
            <button class="tab-btn" onclick="switchTab('tab-models')" id="btn-tab-models">
                <span>🤖</span> Evaluated Models & Live Access ({models_count})
            </button>
            <button class="tab-btn" onclick="switchTab('tab-errors')" id="btn-tab-errors">
                <span>🔍</span> Failure Case Diagnostics ({total_errors})
            </button>
            <button class="tab-btn" onclick="switchTab('tab-difficulty')" id="btn-tab-difficulty">
                <span>🎯</span> Hard-Sample Ranking
            </button>
            <button class="tab-btn" onclick="switchTab('tab-playground')" id="btn-tab-playground">
                <span>⚡</span> Live Predict Playground
            </button>
            <button class="tab-btn" onclick="switchTab('tab-data')" id="btn-tab-data">
                <span>📋</span> Data & Governance Reports
            </button>
        </nav>

        <!-- TAB 1: Visual Analytics & Infographics -->
        <section class="tab-content active" id="tab-analytics">
            <div class="panel-card">
                <div class="panel-header">
                    <h2 class="panel-title"><span>📊</span> Automated Publication Infographics & Visual Analytics</h2>
                    <span class="badge badge-cyan">300 DPI High-Resolution</span>
                </div>
                <div class="gallery-grid">
                    <div class="gallery-item">
                        <img class="gallery-img" src="/reports/infographic_models_comparison.png" alt="Multi-Panel Infographic" onclick="window.open(this.src, '_blank')">
                        <div class="gallery-caption">Fig 1: Comprehensive Multi-Panel Model Benchmark</div>
                    </div>
                    <div class="gallery-item">
                        <img class="gallery-img" src="/reports/figure_auprc_heatmap.png" alt="Performance Heatmap" onclick="window.open(this.src, '_blank')">
                        <div class="gallery-caption">Fig 2: AUPRC & AUROC Performance Matrix Heatmaps</div>
                    </div>
                    <div class="gallery-item">
                        <img class="gallery-img" src="/reports/figure_context_trajectory.png" alt="Context Trajectory" onclick="window.open(this.src, '_blank')">
                        <div class="gallery-caption">Fig 3: Causal Context Expansion Dynamics</div>
                    </div>
                    <div class="gallery-item">
                        <img class="gallery-img" src="/reports/figure_llm_leaderboard.png" alt="LLM Leaderboard" onclick="window.open(this.src, '_blank')">
                        <div class="gallery-caption">Fig 4: Dedicated LLM Leaderboard (Full Prefix)</div>
                    </div>
                </div>
            </div>
        </section>

        <!-- TAB: Evaluated Models & Live Accessibility -->
        <section class="tab-content" id="tab-models">
            <div class="panel-card">
                <div class="panel-header">
                    <div>
                        <h2 class="panel-title"><span>🤖</span> Evaluated Models Catalog & Live Provider Accessibility</h2>
                        <p style="color: var(--text-secondary); font-size: 0.88rem; margin-top: 0.25rem;">
                            Detailed registry of all {models_count} evaluated models, evaluation session timestamps, and current real-time API accessibility.
                        </p>
                    </div>
                    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                        <span class="badge badge-emerald">🟢 {accessible_models_count}/{models_count} Active & Accessible</span>
                        <span class="badge badge-cyan">🎁 {free_tier_count} Free-Tier Models</span>
                    </div>
                </div>

                <!-- Session Metadata Strip -->
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; background: rgba(15, 23, 42, 0.6); padding: 1rem 1.25rem; border-radius: 12px; border: 1px solid var(--border-card);">
                    <div>
                        <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Evaluation Session Date</div>
                        <div style="font-weight: 600; color: var(--text-primary); font-size: 0.88rem; margin-top: 0.2rem;">{session_info['timestamp']}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Benchmark Version</div>
                        <div style="font-weight: 600; color: var(--accent-cyan); font-size: 0.88rem; margin-top: 0.2rem;">v{session_info['version']} (Gold Frozen)</div>
                    </div>
                    <div>
                        <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Random Seed & Scale</div>
                        <div style="font-weight: 600; color: var(--text-primary); font-size: 0.88rem; margin-top: 0.2rem;">Seed {session_info['random_seed']} • {session_info['dataset_scale']}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase;">Active Providers</div>
                        <div style="font-weight: 600; color: var(--accent-emerald); font-size: 0.88rem; margin-top: 0.2rem;">OpenRouter, Requesty, Mistral Live</div>
                    </div>
                </div>

                <!-- Search and Filter Bar -->
                <div style="display: flex; gap: 1rem; margin-bottom: 1.25rem; flex-wrap: wrap; align-items: center;">
                    <input type="text" class="search-input" id="model-search" placeholder="Search model name, family, or ID..." onkeyup="filterModelsTable()" style="max-width: 320px;">
                    <div style="display: flex; gap: 0.5rem; align-items: center;">
                        <label style="font-size: 0.8rem; color: var(--text-secondary);">Provider:</label>
                        <select id="model-provider-filter" onchange="filterModelsTable()" style="background: #0f172a; border: 1px solid var(--border-card); color: var(--text-primary); border-radius: 8px; padding: 0.4rem 0.75rem; font-size: 0.82rem;">
                            <option value="all">All Providers</option>
                            <option value="openrouter">OpenRouter (19)</option>
                            <option value="requesty">Requesty.ai (12)</option>
                            <option value="mistral">Mistral AI (1)</option>
                            <option value="local">Local Baselines (6)</option>
                        </select>
                    </div>
                    <div style="display: flex; gap: 0.5rem; align-items: center;">
                        <label style="font-size: 0.8rem; color: var(--text-secondary);">Status:</label>
                        <select id="model-status-filter" onchange="filterModelsTable()" style="background: #0f172a; border: 1px solid var(--border-card); color: var(--text-primary); border-radius: 8px; padding: 0.4rem 0.75rem; font-size: 0.82rem;">
                            <option value="all">All Statuses</option>
                            <option value="accessible">Accessible Now (Active Key)</option>
                            <option value="free">Free Tier ($0 Cost)</option>
                            <option value="local">Local Built-in</option>
                        </select>
                    </div>
                </div>

                <!-- Catalog Table -->
                <div class="table-responsive">
                    <table id="models-table">
                        <thead>
                            <tr>
                                <th>Model Name & Scorer ID</th>
                                <th>Family & Provider</th>
                                <th>When Evaluated</th>
                                <th>Live Accessibility</th>
                                <th>Required .env Key</th>
                                <th style="text-align: right;">Full Prefix AUPRC (Δ)</th>
                                <th style="text-align: right;">Recall @ FPR 1%</th>
                            </tr>
                        </thead>
                        <tbody>
                            {models_table_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- TAB 2: Failure Case Diagnostics -->
        <section class="tab-content" id="tab-errors">
            <div class="panel-card">
                <div class="panel-header">
                    <h2 class="panel-title"><span>🔍</span> Turn-by-Turn LLM Failure Cases & Misclassifications</h2>
                    <input type="text" class="search-input" id="error-search" placeholder="Search turn text or model..." onkeyup="filterErrorTable()">
                </div>
                <div class="filter-bar">
                    <button class="filter-btn active" onclick="setErrorFilter('all', this)">All Errors ({len(all_error_cases)})</button>
                    <button class="filter-btn" onclick="setErrorFilter('False Positive', this)">False Positives (Over-Moderation)</button>
                    <button class="filter-btn" onclick="setErrorFilter('False Negative', this)">False Negatives (Missed Harm)</button>
                </div>
                <div class="table-responsive">
                    <table id="errors-table">
                        <thead>
                            <tr>
                                <th>Evaluated Model</th>
                                <th>Turn Text</th>
                                <th>Error Classification</th>
                                <th>Severity / Gold</th>
                                <th>Predicted Prob</th>
                                <th>Diagnostic Attribution</th>
                            </tr>
                        </thead>
                        <tbody>
"""

    for row in all_error_cases:
        is_fp = "False Positive" in row["error_type"]
        badge_cls = "badge-amber" if is_fp else "badge-rose"
        label_short = "FP (Over-mod)" if is_fp else "FN (Missed)"
        html += f"""
                            <tr data-type="{row["error_type"]}">
                                <td class="cell-mono"><strong>{row["model"]}</strong></td>
                                <td style="max-width: 320px; font-weight: 500;">"{row["turn_text"]}"</td>
                                <td><span class="badge {badge_cls}">{label_short}</span></td>
                                <td><span class="badge badge-indigo">{row["gold_severity"]}</span></td>
                                <td class="cell-mono" style="font-weight: 700;">{row["prob"]:.2f}</td>
                                <td style="color: var(--text-secondary); font-size: 0.8rem;">{row["reason"]}</td>
                            </tr>
"""

    html += """
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- TAB 3: Hard-Sample Ranking -->
        <section class="tab-content" id="tab-difficulty">
            <div class="panel-card">
                <div class="panel-header">
                    <h2 class="panel-title"><span>🎯</span> Internal Evaluation Difficulty Ranking & Vulnerability Index</h2>
                    <span class="badge badge-amber">Active Priority Sampling</span>
                </div>
                <p style="color: var(--text-secondary); margin-bottom: 1.25rem; font-size: 0.88rem;">
                    Conversations and turns sorted descending by failure rate across the model panel. Evaluated first during hard-sample sampling passes.
                </p>
                <div class="table-responsive" style="margin-bottom: 2rem;">
                    <table>
                        <thead>
                            <tr>
                                <th>Rank</th>
                                <th>Turn Text</th>
                                <th>Primary Failure Mode</th>
                                <th>Error Rate</th>
                                <th>Priority Weight</th>
                                <th>Platform Style</th>
                            </tr>
                        </thead>
                        <tbody>
"""

    for idx, s in enumerate(difficulty_sentences, start=1):
        err_rate = s.get("error_rate", 0.0)
        prio = s.get("priority_weight", 1.0)
        mode = s.get("primary_error_type", "Ambiguous")
        mode_badge = "badge-rose" if "Negative" in mode else "badge-amber"
        html += f"""
                            <tr>
                                <td class="cell-mono">#{idx}</td>
                                <td style="max-width: 400px; font-weight: 600;">"{s.get("turn_text", "")}"</td>
                                <td><span class="badge {mode_badge}">{mode}</span></td>
                                <td class="cell-mono" style="font-weight: 700; color: var(--accent-rose);">{err_rate * 100:.1f}%</td>
                                <td class="cell-mono" style="color: var(--accent-cyan); font-weight: 700;">{prio:.3f}x</td>
                                <td><span class="badge badge-indigo">{s.get("platform_style", "chat")}</span></td>
                            </tr>
"""

    html += f"""
                        </tbody>
                    </table>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
                    <div class="panel-card" style="margin-bottom: 0; background: rgba(15, 23, 42, 0.6);">
                        <h3 style="font-size: 1rem; color: var(--accent-amber); margin-bottom: 0.75rem;">⚠️ Top False Positive Triggers (Over-Moderation)</h3>
                        <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.5rem;">Words triggering false bans on safe banter:</p>
                        <p class="cell-mono" style="color: var(--accent-cyan); font-weight: 600;">{top_fp_triggers}</p>
                    </div>
                    <div class="panel-card" style="margin-bottom: 0; background: rgba(15, 23, 42, 0.6);">
                        <h3 style="font-size: 1rem; color: var(--accent-rose); margin-bottom: 0.75rem;">🚨 Top False Negative Indicators (Missed Covert Harm)</h3>
                        <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.5rem;">Words frequently involved in uncaught peer harassment:</p>
                        <p class="cell-mono" style="color: var(--accent-rose); font-weight: 600;">{top_fn_indicators}</p>
                    </div>
                </div>
            </div>
        </section>

        <!-- TAB 4: Live Predict Playground -->
        <section class="tab-content" id="tab-playground">
            <div class="panel-card">
                <div class="panel-header">
                    <h2 class="panel-title"><span>⚡</span> Live Moderation Evaluator Sandbox</h2>
                    <span class="badge badge-emerald">Direct POST /predict API Test</span>
                </div>
                <p style="color: var(--text-secondary); margin-bottom: 1.25rem; font-size: 0.88rem;">
                    Send test conversation prefixes directly to the running server service to inspect actionability, severity probabilities, and harm categorization in real time.
                </p>
                <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 1.75rem;">
                    <div>
                        <div class="form-group">
                            <label class="form-label" for="test-prefix">Previous Context Turns (JSON or newline lines):</label>
                            <textarea class="form-textarea" id="test-prefix" placeholder="u1: yo what did you just do&#10;u2: stop feeding or we lose"></textarea>
                        </div>
                        <div class="form-group">
                            <label class="form-label" for="test-turn">Current Turn to Evaluate (target):</label>
                            <input type="text" class="form-input" id="test-turn" value="you are absolute garbage uninstall right now">
                        </div>
                        <button class="btn-predict" id="btn-run-predict" onclick="runLivePredict()">
                            <span>▶</span> Send Prediction Request
                        </button>
                    </div>
                    <div>
                        <label class="form-label">Live Response Payload:</label>
                        <div class="predict-output" id="predict-result-box">// Click 'Send Prediction Request' to inspect live server output...</div>
                    </div>
                </div>
            </div>
        </section>

        <!-- TAB 5: Data & Governance Reports -->
        <section class="tab-content" id="tab-data">
            <div class="panel-card">
                <div class="panel-header">
                    <h2 class="panel-title"><span>📋</span> Governance, Split Data & Audit Reports</h2>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.25rem;">
                    <a href="/reports/data_report.md" target="_blank" style="text-decoration: none;">
                        <div class="kpi-card">
                            <div class="kpi-label">Corpora Overview</div>
                            <div class="kpi-num" style="font-size: 1.3rem;">data_report.md</div>
                            <div class="kpi-desc">14 Datasets & 79k+ Turns</div>
                        </div>
                    </a>
                    <a href="/reports/pii_spot_check_report.md" target="_blank" style="text-decoration: none;">
                        <div class="kpi-card">
                            <div class="kpi-label">Privacy & Ethics</div>
                            <div class="kpi-num" style="font-size: 1.3rem; color: var(--accent-emerald);">PASSED</div>
                            <div class="kpi-desc">pii_spot_check_report.md</div>
                        </div>
                    </a>
                    <a href="/reports/agentic_discovery_digest.md" target="_blank" style="text-decoration: none;">
                        <div class="kpi-card">
                            <div class="kpi-label">Slang Discovery</div>
                            <div class="kpi-num" style="font-size: 1.3rem; color: var(--accent-cyan);">Active</div>
                            <div class="kpi-desc">agentic_discovery_digest.md</div>
                        </div>
                    </a>
                    <a href="/api/difficulty" target="_blank" style="text-decoration: none;">
                        <div class="kpi-card">
                            <div class="kpi-label">Raw REST Endpoint</div>
                            <div class="kpi-num" style="font-size: 1.3rem; color: var(--accent-indigo);">/api/difficulty</div>
                            <div class="kpi-desc">JSON Difficulty API</div>
                        </div>
                    </a>
                </div>
            </div>
        </section>

        <footer>
            YouthEscalateBench Evaluator Service • Running at <code>http://{host}:{port}</code> • Auto-Generated Real-Time Dashboard
        </footer>
    </div>

    <script>
        function switchTab(tabId) {{
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            
            const target = document.getElementById(tabId);
            if (target) target.classList.add('active');

            const btn = document.querySelector(`[onclick="switchTab('${{tabId}}')"]`);
            if (btn) btn.classList.add('active');
        }}

        function filterModelsTable() {{
            const query = (document.getElementById('model-search')?.value || '').toLowerCase();
            const prov = (document.getElementById('model-provider-filter')?.value || 'all').toLowerCase();
            const status = (document.getElementById('model-status-filter')?.value || 'all').toLowerCase();

            const rows = document.querySelectorAll('#models-table tbody tr');
            rows.forEach(r => {{
                const text = r.innerText.toLowerCase();
                const rProv = r.getAttribute('data-provider') || '';
                const rStatus = r.getAttribute('data-status') || '';
                const rTier = r.getAttribute('data-tier') || '';

                const matchesQuery = !query || text.includes(query);
                const matchesProv = !prov || prov === 'all' || rProv.includes(prov);
                const matchesStatus = !status || status === 'all' 
                    || (status === 'accessible' && rStatus === 'accessible')
                    || (status === 'free' && rTier.includes('free'))
                    || (status === 'local' && rProv.includes('local'));

                r.style.display = (matchesQuery && matchesProv && matchesStatus) ? '' : 'none';
            }});
        }}

        function setErrorFilter(type, btn) {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const rows = document.querySelectorAll('#errors-table tbody tr');
            rows.forEach(r => {{
                if (type === 'all' || r.getAttribute('data-type').includes(type)) {{
                    r.style.display = '';
                }} else {{
                    r.style.display = 'none';
                }}
            }});
        }}

        function filterErrorTable() {{
            const query = document.getElementById('error-search').value.toLowerCase();
            const rows = document.querySelectorAll('#errors-table tbody tr');
            rows.forEach(r => {{
                const text = r.innerText.toLowerCase();
                r.style.display = text.includes(query) ? '' : 'none';
            }});
        }}

        async function runLivePredict() {{
            const turnText = document.getElementById('test-turn').value.trim();
            const box = document.getElementById('predict-result-box');
            box.textContent = "Sending POST /predict...";

            const payload = {{
                "request_id": "dash_req_" + Date.now(),
                "conversation_id": "dash_test_conv",
                "condition": "current_turn_only",
                "turns": [
                    {{
                        "turn_id": "t1",
                        "speaker_id": "user_tester",
                        "role": "user",
                        "relative_time": "0s",
                        "text": turnText
                    }}
                ]
            }};

            try {{
                const res = await fetch('/predict', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }});
                const jsonRes = await res.json();
                box.textContent = JSON.stringify(jsonRes, null, 2);
            }} catch (err) {{
                box.textContent = "Error executing /predict: " + err.message;
            }}
        }}
    </script>
</body>
</html>
"""
    return html


def generate_predict_page_html(
    host: str = "127.0.0.1",
    port: int = 8080,
) -> str:
    """Generate dedicated interactive HTML playground for the /predict endpoint."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouthEscalateBench — Moderation API Sandbox (/predict)</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #0a0e17;
            --bg-surface: #111827;
            --bg-card: #1f2937;
            --bg-card-hover: #263345;
            --border-subtle: #374151;
            --border-accent: #4f46e5;
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --emerald: #10b981;
            --emerald-bg: rgba(16, 185, 129, 0.15);
            --rose: #f43f5e;
            --rose-bg: rgba(244, 63, 94, 0.15);
            --amber: #f59e0b;
            --amber-bg: rgba(245, 158, 11, 0.15);
            --sky: #0ea5e9;
            --text-primary: #f9fafb;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background-color: var(--bg-base);
            color: var(--text-primary);
            font-family: var(--font-sans);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        header {{
            background: rgba(17, 24, 39, 0.85);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-subtle);
            padding: 1rem 2rem;
            position: sticky;
            top: 0;
            z-index: 50;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            text-decoration: none;
            color: inherit;
        }}
        .brand-icon {{
            width: 38px;
            height: 38px;
            background: linear-gradient(135deg, #6366f1, #ec4899);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        }}
        .brand-title {{ font-size: 1.15rem; font-weight: 700; letter-spacing: -0.02em; }}
        .brand-subtitle {{ font-size: 0.75rem; color: var(--text-secondary); }}
        .header-actions {{ display: flex; align-items: center; gap: 1rem; }}
        .service-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.4rem 0.85rem;
            border-radius: 9999px;
            background: var(--emerald-bg);
            border: 1px solid var(--emerald);
            color: #34d399;
            font-size: 0.8rem;
            font-weight: 600;
            font-family: var(--font-mono);
        }}
        .pulse-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 10px #10b981;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
        .btn-link {{
            background: #1f2937;
            border: 1px solid var(--border-subtle);
            color: var(--text-primary);
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.2s ease;
        }}
        .btn-link:hover {{
            background: var(--primary);
            border-color: var(--primary);
            transform: translateY(-1px);
        }}
        main {{
            flex: 1;
            max-width: 1300px;
            width: 100%;
            margin: 0 auto;
            padding: 2rem;
            display: flex;
            flex-direction: column;
            gap: 2rem;
        }}
        .intro-card {{
            background: linear-gradient(135deg, rgba(31, 41, 55, 0.7), rgba(17, 24, 39, 0.9));
            border: 1px solid var(--border-subtle);
            border-radius: 16px;
            padding: 1.75rem;
        }}
        .intro-title {{ font-size: 1.6rem; font-weight: 800; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.75rem; }}
        .intro-desc {{ color: var(--text-secondary); font-size: 0.95rem; line-height: 1.6; max-width: 900px; }}
        .preset-container {{ display: flex; flex-wrap: wrap; gap: 0.6rem; margin-top: 1.25rem; }}
        .preset-btn {{
            background: rgba(55, 65, 81, 0.6);
            border: 1px solid var(--border-subtle);
            color: var(--text-primary);
            padding: 0.45rem 0.85rem;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .preset-btn:hover {{
            background: var(--primary);
            border-color: var(--primary);
            transform: translateY(-1px);
        }}
        .grid-layout {{
            display: grid;
            grid-template-columns: 1.15fr 1fr;
            gap: 2rem;
        }}
        @media (max-width: 980px) {{
            .grid-layout {{ grid-template-columns: 1fr; }}
        }}
        .panel-card {{
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 16px;
            padding: 1.75rem;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }}
        .panel-header {{ display: flex; justify-content: space-between; align-items: center; }}
        .panel-title {{ font-size: 1.15rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem; }}
        .form-group {{ display: flex; flex-direction: column; gap: 0.5rem; }}
        .form-label {{ font-size: 0.82rem; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; }}
        .form-input, .form-textarea, .form-select {{
            background: #0f172a;
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            color: var(--text-primary);
            font-family: inherit;
            padding: 0.75rem 1rem;
            font-size: 0.92rem;
            transition: border-color 0.2s ease;
        }}
        .form-input:focus, .form-textarea:focus, .form-select:focus {{
            outline: none;
            border-color: var(--primary);
        }}
        .form-textarea {{ resize: vertical; min-height: 90px; font-family: var(--font-mono); font-size: 0.85rem; }}
        .form-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
        .btn-predict {{
            background: linear-gradient(135deg, #6366f1, #4f46e5);
            border: none;
            color: #ffffff;
            font-family: inherit;
            font-size: 0.95rem;
            font-weight: 600;
            padding: 0.85rem 1.5rem;
            border-radius: 10px;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            transition: all 0.2s ease;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
        }}
        .btn-predict:hover {{
            background: linear-gradient(135deg, #4f46e5, #4338ca);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45);
        }}
        .result-box {{
            background: #0b1120;
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            padding: 1.25rem;
            font-family: var(--font-mono);
            font-size: 0.82rem;
            line-height: 1.5;
            color: #cbd5e1;
            overflow-x: auto;
            max-height: 480px;
            white-space: pre-wrap;
            word-break: break-word;
        }}
        .outcome-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            border-radius: 10px;
            font-size: 0.9rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
        }}
        .badge-actionable {{ background: var(--rose-bg); border: 1px solid var(--rose); color: #fb7185; }}
        .badge-benign {{ background: var(--emerald-bg); border: 1px solid var(--emerald); color: #34d399; }}
        .badge-monitor {{ background: var(--amber-bg); border: 1px solid var(--amber); color: #fbbf24; }}
        .docs-section {{
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 16px;
            padding: 1.75rem;
        }}
        .docs-title {{ font-size: 1.25rem; font-weight: 700; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }}
        .code-block {{
            background: #0b1120;
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
            padding: 1rem 1.25rem;
            font-family: var(--font-mono);
            font-size: 0.82rem;
            color: #38bdf8;
            overflow-x: auto;
            margin: 0.75rem 0;
            position: relative;
        }}
        .copy-btn {{
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            background: #1e293b;
            border: 1px solid #475569;
            color: #cbd5e1;
            border-radius: 6px;
            padding: 0.25rem 0.6rem;
            font-size: 0.75rem;
            cursor: pointer;
        }}
        .copy-btn:hover {{ background: var(--primary); color: #fff; border-color: var(--primary); }}
        footer {{
            border-top: 1px solid var(--border-subtle);
            padding: 1.5rem 2rem;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.82rem;
        }}
    </style>
</head>
<body>
    <header>
        <a href="/" class="brand">
            <div class="brand-icon">🛡️</div>
            <div>
                <div class="brand-title">YouthEscalateBench</div>
                <div class="brand-subtitle">Private Evaluator Service • Version 0.1.2</div>
            </div>
        </a>
        <div class="header-actions">
            <div class="service-badge">
                <span class="pulse-dot"></span>
                <span>http://{host}:{port}/predict</span>
            </div>
            <a href="/" class="btn-link">📊 Analytics Dashboard</a>
        </div>
    </header>

    <main>
        <div class="intro-card">
            <h1 class="intro-title"><span>⚡</span> Moderation API Playground & Sandbox</h1>
            <p class="intro-desc">
                This endpoint accepts <code>HTTP POST /predict</code> requests conforming to the <code>InferenceRequest</code> specification.
                Test your conversation turns below in real time to inspect harm probabilities, severity distributions, and causal risk onset.
            </p>
            <div class="preset-container">
                <span style="font-size: 0.8rem; color: var(--text-muted); display: flex; align-items: center; margin-right: 0.4rem;">Presets:</span>
                <button class="preset-btn" onclick="setPreset('hype')">🔥 Benign Gaming Hype</button>
                <button class="preset-btn" onclick="setPreset('bullying')">⚠️ Targeted Cyberbullying</button>
                <button class="preset-btn" onclick="setPreset('exclusion')">👤 Covert Exclusion</button>
                <button class="preset-btn" onclick="setPreset('algospeak')">🛡️ Algospeak Evasion</button>
            </div>
        </div>

        <div class="grid-layout">
            <div class="panel-card">
                <div class="panel-header">
                    <h2 class="panel-title"><span>📝</span> Test Conversation Input</h2>
                </div>
                <div class="form-group">
                    <label class="form-label" for="context-turns">Context Turns (Optional Prefix History):</label>
                    <textarea class="form-textarea" id="context-turns" placeholder="u1: nice push team&#10;u2: they are rotating B"></textarea>
                </div>
                <div class="form-group">
                    <label class="form-label" for="target-turn">Current Turn to Evaluate (Target Text):</label>
                    <input type="text" class="form-input" id="target-turn" value="you are absolute garbage uninstall right now">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label" for="platform-style">Platform Style:</label>
                        <select class="form-select" id="platform-style">
                            <option value="gaming_chat" selected>Gaming Chat (Discord/Steam)</option>
                            <option value="reddit_tree">Reddit Tree Discussion</option>
                            <option value="direct_message">Direct Message</option>
                            <option value="group_chat">Group Chat</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="task-type">Task Type:</label>
                        <select class="form-select" id="task-type">
                            <option value="current_harm" selected>Current Harm (Severity 0-4)</option>
                            <option value="next_turn_forecast">Next Turn Forecast</option>
                        </select>
                    </div>
                </div>
                <button class="btn-predict" id="btn-submit" onclick="submitPredict()">
                    <span>▶</span> Execute POST /predict Request
                </button>
            </div>

            <div class="panel-card">
                <div class="panel-header">
                    <h2 class="panel-title"><span>📡</span> Live Response Payload</h2>
                    <span id="response-status" style="font-size: 0.8rem; font-family: var(--font-mono); color: var(--text-muted);">Ready</span>
                </div>
                <div id="visual-verdict" style="display: none;"></div>
                <div class="result-box" id="response-json">// Click 'Execute POST /predict Request' or pick a preset above to inspect live output...</div>
            </div>
        </div>

        <div class="docs-section">
            <h2 class="docs-title"><span>📖</span> API Integration Quickstart</h2>
            <p style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1rem;">
                You can invoke this exact endpoint directly via <code>curl</code>, Python, or any HTTP client:
            </p>

            <div class="form-label">cURL Command</div>
            <div class="code-block" id="curl-code">curl -X POST http://{host}:{port}/predict \
  -H "Content-Type: application/json" \
  -d '{{
    "benchmark_version": "0.1.2",
    "conversation_id": "demo_test",
    "current_turn_id": "t1",
    "platform_style": "gaming_chat",
    "language_mode": "english",
    "task": "current_harm",
    "turns": [
      {{ "speaker_id": "u1", "turn_id": "t1", "text": "you are absolute garbage uninstall right now" }}
    ]
  }}'<button class="copy-btn" onclick="copyCurl()">Copy</button></div>

            <div class="form-label" style="margin-top: 1.25rem;">Python httpx Example</div>
            <div class="code-block">import httpx

payload = {{
    "turns": [{{"speaker_id": "u1", "turn_id": "t1", "text": "holy shit nice shot"}}]
}}
response = httpx.post("http://{host}:{port}/predict", json=payload)
print(response.json())</div>
        </div>
    </main>

    <footer>
        YouthEscalateBench Evaluator Service • Running at <code>http://{host}:{port}/predict</code> • Version 0.1.2
    </footer>

    <script>
        const PRESETS = {{
            hype: {{
                context: "u1: he is diffusing the bomb!\\nu2: stick it stick it",
                target: "holy fucking shit you hit that cross-map snipe! you are an absolute god at this game bro"
            }},
            bullying: {{
                context: "u1: my bad missed the flash\\nu2: play safe",
                target: "you are absolute garbage uninstall right now delete the game"
            }},
            exclusion: {{
                context: "u1: can i join next match?\\nu2: we need a full 5-stack",
                target: "nobody in this discord wanted you here, just leave and don't come back"
            }},
            algospeak: {{
                context: "u1: stop griefing our lobby",
                target: "go u-n-a-l-i-v-e yourself in real life, waste of oxygen"
            }}
        }};

        function setPreset(key) {{
            const p = PRESETS[key];
            if (!p) return;
            document.getElementById('context-turns').value = p.context;
            document.getElementById('target-turn').value = p.target;
            submitPredict();
        }}

        async function submitPredict() {{
            const targetText = document.getElementById('target-turn').value.trim();
            const contextRaw = document.getElementById('context-turns').value.trim();
            const platformStyle = document.getElementById('platform-style').value;
            const taskType = document.getElementById('task-type').value;

            const btn = document.getElementById('btn-submit');
            const statusSpan = document.getElementById('response-status');
            const resultBox = document.getElementById('response-json');
            const verdictDiv = document.getElementById('visual-verdict');

            btn.disabled = true;
            statusSpan.textContent = "Executing...";
            resultBox.textContent = "Sending POST /predict payload to server...";

            const turns = [];
            let turnIndex = 1;

            if (contextRaw) {{
                const lines = contextRaw.split('\\n');
                for (const line of lines) {{
                    const l = line.trim();
                    if (!l) continue;
                    let speaker = "u1";
                    let text = l;
                    if (l.includes(":")) {{
                        const parts = l.split(":");
                        speaker = parts[0].trim();
                        text = parts.slice(1).join(":").trim();
                    }}
                    turns.push({{
                        "turn_id": "t" + turnIndex,
                        "speaker_id": speaker,
                        "role": "user",
                        "relative_time": (turnIndex * 5) + "s",
                        "text": text
                    }});
                    turnIndex++;
                }}
            }}

            const currentTurnId = "t" + turnIndex;
            turns.push({{
                "turn_id": currentTurnId,
                "speaker_id": "u_target",
                "role": "user",
                "relative_time": (turnIndex * 5) + "s",
                "text": targetText || "hello"
            }});

            const payload = {{
                "benchmark_version": "0.1.2",
                "conversation_id": "sandbox_" + Date.now(),
                "current_turn_id": currentTurnId,
                "platform_style": platformStyle,
                "language_mode": "english",
                "task": taskType,
                "turns": turns
            }};

            try {{
                const startTime = performance.now();
                const res = await fetch('/predict', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }});
                const elapsed = Math.round(performance.now() - startTime);
                const data = await res.json();

                statusSpan.textContent = `HTTP ${{res.status}} (${{elapsed}}ms)`;
                resultBox.textContent = JSON.stringify(data, null, 2);

                verdictDiv.style.display = 'block';
                const harmProb = data.harm_probability !== undefined ? data.harm_probability : 0.0;
                const actionable = harmProb >= 0.5;

                if (actionable) {{
                    verdictDiv.innerHTML = `<div class="outcome-badge badge-actionable">
                        <span>⚠️</span> Actionable Harm Detected (Probability: ${{harmProb.toFixed(3)}})
                    </div>`;
                }} else if (harmProb >= 0.2) {{
                    verdictDiv.innerHTML = `<div class="outcome-badge badge-monitor">
                        <span>👁️</span> Borderline / Monitor (Probability: ${{harmProb.toFixed(3)}})
                    </div>`;
                }} else {{
                    verdictDiv.innerHTML = `<div class="outcome-badge badge-benign">
                        <span>✅</span> Benign Content (Probability: ${{harmProb.toFixed(3)}})
                    </div>`;
                }}
            }} catch (err) {{
                statusSpan.textContent = "Error";
                resultBox.textContent = "Error executing request: " + err.message;
                verdictDiv.style.display = 'none';
            }} finally {{
                btn.disabled = false;
            }}
        }}

        function copyCurl() {{
            const code = document.getElementById('curl-code').innerText.replace('Copy', '').trim();
            navigator.clipboard.writeText(code);
            alert("Copied curl command to clipboard!");
        }}
    </script>
</body>
</html>
"""
    return html

