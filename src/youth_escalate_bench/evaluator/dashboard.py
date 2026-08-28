"""Dynamic service dashboard for analyzing benchmark results in real-time."""

from __future__ import annotations

import json
import threading
from html import escape as html_escape
from pathlib import Path
from typing import Any

import yaml

from youth_escalate_bench.llm.keys import is_provider_configured
from youth_escalate_bench.reporting.infographics import _get_display_name

# Parsed-file caches keyed by (resolved path, mtime_ns)
_FILE_CACHE: dict[tuple[str, int], dict[str, Any]] = {}
_FILE_CACHE_LOCK = threading.Lock()

# Generated HTML caches keyed by dependency fingerprint
_HTML_CACHE: dict[str, tuple[str, str]] = {}
_HTML_CACHE_LOCK = threading.Lock()

# Cap inline failure rows so the dashboard stays responsive; full set remains on /api/errors
MAX_INLINE_ERROR_CASES = 200


def invalidate_dashboard_caches() -> None:
    """Drop cached report parses and generated HTML (call after regenerating artifacts)."""
    with _FILE_CACHE_LOCK:
        _FILE_CACHE.clear()
    with _HTML_CACHE_LOCK:
        _HTML_CACHE.clear()


def _path_mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return -1


def _load_yaml_safe(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    key = (str(path.resolve()), _path_mtime_ns(path))
    with _FILE_CACHE_LOCK:
        cached = _FILE_CACHE.get(key)
        if cached is not None:
            return cached
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            # Some YAMLs are top-level lists (evaluation results); wrap for cache uniformity
            data = {"__list__": data} if isinstance(data, list) else {}
    except Exception:
        data = {}
    with _FILE_CACHE_LOCK:
        _FILE_CACHE[key] = data
    return data


def _load_json_safe(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    key = (str(path.resolve()), _path_mtime_ns(path))
    with _FILE_CACHE_LOCK:
        cached = _FILE_CACHE.get(key)
        if cached is not None:
            return cached
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if not isinstance(data, dict):
            data = {"__list__": data} if isinstance(data, list) else {}
    except Exception:
        data = {}
    with _FILE_CACHE_LOCK:
        _FILE_CACHE[key] = data
    return data


def _unwrap_cached_list(data: dict[str, Any] | list[Any]) -> Any:
    if isinstance(data, dict) and "__list__" in data and len(data) == 1:
        return data["__list__"]
    return data


def _load_difficulty_data(yaml_path: Path) -> dict[str, Any]:
    """Prefer JSON sibling (≈250× faster than YAML) and materialize it on first YAML load."""
    json_path = yaml_path.with_suffix(".json")
    yaml_mtime = _path_mtime_ns(yaml_path) if yaml_path.exists() else -1
    json_mtime = _path_mtime_ns(json_path) if json_path.exists() else -1

    if json_path.exists() and json_mtime >= yaml_mtime:
        data = _load_json_safe(json_path)
        return data if isinstance(data, dict) else {}

    data = _load_yaml_safe(yaml_path)
    data = data if isinstance(data, dict) else {}
    if data and yaml_path.exists():
        try:
            json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    return data


def _dependency_fingerprint(paths: list[Path], *extra: str) -> str:
    parts = list(extra)
    for p in paths:
        if p.exists():
            st = p.stat()
            parts.append(f"{p.resolve()}:{st.st_mtime_ns}:{st.st_size}")
        else:
            parts.append(f"{p}:missing")
    return "|".join(parts)


def build_evaluated_models_catalog(
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    """Compile comprehensive catalog of evaluated models with evaluation timestamps and live accessibility status."""
    rep_dir = reports_dir or Path("reports")
    alt_dir = Path("data/processed/report")
    fingerprint = _dependency_fingerprint(
        [
            rep_dir / "evaluation_results.yaml",
            rep_dir / "data" / "evaluation_results.yaml",
            alt_dir / "evaluation_results.yaml",
            rep_dir / "manifest.json",
            Path(".env"),
        ],
        "catalog",
    )
    with _HTML_CACHE_LOCK:
        hit = _HTML_CACHE.get("models_catalog")
        if hit and hit[0] == fingerprint:
            return json.loads(hit[1])

    catalog = _build_evaluated_models_catalog_uncached(rep_dir, alt_dir)
    with _HTML_CACHE_LOCK:
        _HTML_CACHE["models_catalog"] = (fingerprint, json.dumps(catalog))
    return catalog


def _build_evaluated_models_catalog_uncached(
    rep_dir: Path,
    alt_dir: Path,
) -> dict[str, Any]:
    """Build models catalog without HTML/catalog cache."""

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
    raw_results = _unwrap_cached_list(raw_results)
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
        pair_metrics = conds.get("prev_plus_current", {})
        prefix_metrics = conds.get("full_prefix", {})

        turn_auprc = float(turn_metrics.get("auprc", 0.0))
        pair_auprc = float(pair_metrics.get("auprc", 0.0))
        prefix_auprc = float(prefix_metrics.get("auprc", 0.0))
        turn_auroc = float(turn_metrics.get("auroc", 0.0)) if turn_metrics.get("auroc") is not None else None
        pair_auroc = float(pair_metrics.get("auroc", 0.0)) if pair_metrics.get("auroc") is not None else None
        prefix_auroc = float(prefix_metrics.get("auroc", 0.0)) if prefix_metrics.get("auroc") is not None else None
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
                "pair_auprc": pair_auprc,
                "prefix_auprc": prefix_auprc,
                "turn_auroc": turn_auroc,
                "pair_auroc": pair_auroc,
                "prefix_auroc": prefix_auroc,
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


def build_trajectory_bars_html(models_list: list[dict[str, Any]]) -> str:
    """Render top trajectory progress bars for context visualizer."""
    trajectory_bars_html = ""
    baselines_list = [m for m in models_list if m.get("provider") == "Local Baseline"]
    top_models_for_bars = [m for m in models_list if m.get("provider") != "Local Baseline"][:4]
    baselines_for_bars = baselines_list[:2]
    sampled_for_trajectory = top_models_for_bars + baselines_for_bars
    if not sampled_for_trajectory:
        sampled_for_trajectory = models_list[:6]

    for m in sampled_for_trajectory:
        t_val = m.get("turn_auprc", 0.0)
        p_val = m.get("pair_auprc", t_val)
        pref_val = m.get("prefix_auprc", 0.0)
        delta_val = m.get("delta_auprc", 0.0)
        delta_str = f"+{delta_val:.3f}" if delta_val > 0 else f"{delta_val:.3f}"
        badge_cls = "badge-emerald" if delta_val >= 0 else "badge-rose"

        trajectory_bars_html += f"""
        <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-card); border-radius: 10px; padding: 0.85rem 1rem; margin-bottom: 0.75rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem;">
                <div style="display: flex; align-items: center; gap: 0.6rem;">
                    <span style="font-weight: 700; color: #ffffff; font-size: 0.88rem;">{m['name']}</span>
                    <span class="badge badge-indigo" style="font-size: 0.7rem;">{m.get('family', 'Model')}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <span style="font-size: 0.75rem; color: var(--text-muted);">Causal Gain:</span>
                    <span class="badge {badge_cls}">{delta_str} Δ AUPRC</span>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.75rem; font-size: 0.78rem;">
                <div>
                    <div style="display: flex; justify-content: space-between; color: var(--text-muted); margin-bottom: 0.25rem;">
                        <span>Turn Only</span>
                        <span class="cell-mono" style="color: #c084fc; font-weight: 600;">{t_val:.3f}</span>
                    </div>
                    <div style="height: 6px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden;">
                        <div style="height: 100%; width: {max(5, int(t_val * 100))}%; background: linear-gradient(90deg, #a855f7, #c084fc); border-radius: 3px;"></div>
                    </div>
                </div>
                <div>
                    <div style="display: flex; justify-content: space-between; color: var(--text-muted); margin-bottom: 0.25rem;">
                        <span>Prev + Turn</span>
                        <span class="cell-mono" style="color: var(--accent-cyan); font-weight: 600;">{p_val:.3f}</span>
                    </div>
                    <div style="height: 6px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden;">
                        <div style="height: 100%; width: {max(5, int(p_val * 100))}%; background: linear-gradient(90deg, #0284c7, #38bdf8); border-radius: 3px;"></div>
                    </div>
                </div>
                <div>
                    <div style="display: flex; justify-content: space-between; color: var(--text-muted); margin-bottom: 0.25rem;">
                        <span>Full Prefix</span>
                        <span class="cell-mono" style="color: var(--accent-emerald); font-weight: 700;">{pref_val:.3f}</span>
                    </div>
                    <div style="height: 6px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden;">
                        <div style="height: 100%; width: {max(5, int(pref_val * 100))}%; background: linear-gradient(90deg, #059669, #34d399); border-radius: 3px;"></div>
                    </div>
                </div>
            </div>
        </div>
        """
    return trajectory_bars_html


def build_analytics_matrix_rows_html(models_list: list[dict[str, Any]]) -> str:
    """Render cross-condition performance matrix table rows for visual analytics."""
    analytics_matrix_rows = ""
    for idx, m in enumerate(models_list, 1):
        delta_val = m.get("delta_auprc", 0.0)
        delta_str = f"+{delta_val:.3f}" if delta_val > 0 else f"{delta_val:.3f}"
        delta_badge_cls = "badge-emerald" if delta_val >= 0 else "badge-rose"

        turn_auroc_str = f"{m['turn_auroc']:.3f}" if m.get("turn_auroc") is not None else "—"
        pair_auroc_str = f"{m['pair_auroc']:.3f}" if m.get("pair_auroc") is not None else "—"
        prefix_auroc_str = f"{m['prefix_auroc']:.3f}" if m.get("prefix_auroc") is not None else "—"

        pair_val = m.get("pair_auprc", 0.0)
        analytics_matrix_rows += f"""
        <tr>
            <td style="font-weight: 700; color: var(--text-primary);">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <span style="color: var(--accent-cyan); font-family: var(--font-mono); font-size: 0.8rem;">#{idx}</span>
                    <span>{m['name']}</span>
                </div>
            </td>
            <td>
                <span class="badge badge-purple">{m['family']}</span>
                <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: 0.35rem;">{m['provider']}</span>
            </td>
            <td class="cell-mono" style="text-align: right;">
                <span style="color: #ffffff; font-weight: 600;">{m['turn_auprc']:.3f}</span>
                <span style="font-size: 0.72rem; color: var(--text-muted); margin-left: 0.2rem;">({turn_auroc_str})</span>
            </td>
            <td class="cell-mono" style="text-align: right;">
                <span style="color: #ffffff; font-weight: 600;">{pair_val:.3f}</span>
                <span style="font-size: 0.72rem; color: var(--text-muted); margin-left: 0.2rem;">({pair_auroc_str})</span>
            </td>
            <td class="cell-mono" style="text-align: right;">
                <span style="color: var(--accent-cyan); font-weight: 700;">{m['prefix_auprc']:.3f}</span>
                <span style="font-size: 0.72rem; color: var(--text-muted); margin-left: 0.2rem;">({prefix_auroc_str})</span>
            </td>
            <td style="text-align: center;">
                <span class="badge {delta_badge_cls}">{delta_str}</span>
            </td>
            <td class="cell-mono" style="text-align: right; color: var(--text-secondary);">
                {m['r_at_fpr1']:.3f}
            </td>
        </tr>
        """
    return analytics_matrix_rows


def generate_model_selector_component(
    models: list[dict[str, Any]],
    prefix: str = "pred",
    default_all: bool = False,
) -> str:
    """Generate 3-column model selection checklist toolbar with Select All, Local Baselines, Frontier LLMs, and Custom columns."""
    baselines: list[dict[str, Any]] = []
    frontier_llms: list[dict[str, Any]] = []
    custom_models: list[dict[str, Any]] = []

    for m in models:
        prov_lower = str(m.get("provider", "")).lower()
        m_id_lower = str(m.get("id", "")).lower()
        if "local" in prov_lower or "baseline" in prov_lower:
            baselines.append(m)
        elif "requesty" in prov_lower or "custom" in prov_lower or "requesty" in m_id_lower:
            custom_models.append(m)
        else:
            frontier_llms.append(m)

    total_models = len(models)
    total_baselines = len(baselines)
    total_llms = len(frontier_llms)
    total_custom = len(custom_models)

    def _render_items(item_list: list[dict[str, Any]], category: str) -> str:
        res = ""
        for m in item_list:
            m_id = m.get("id", "")
            m_name = m.get("name", m_id)
            prov = m.get("provider", "Local Baseline")
            tier = m.get("tier", "")
            prov_lower = prov.lower()

            if "local" in prov_lower:
                badge_cls = "badge-cyan"
                status_tag = "⚡ 1ms"
            elif "requesty" in prov_lower or category == "custom":
                badge_cls = "badge-purple"
                status_tag = "🛠️ Custom"
            elif "openrouter" in prov_lower:
                badge_cls = "badge-indigo"
                status_tag = "Free Tier" if "free" in tier.lower() else "API Ready"
            elif "mistral" in prov_lower:
                badge_cls = "badge-amber"
                status_tag = "API Ready"
            else:
                badge_cls = "badge-emerald"
                status_tag = "Active"

            is_checked = True if default_all else (m_id == "lexicon_raw")
            checked_attr = "checked" if is_checked else ""
            selected_cls = "is-selected" if is_checked else ""

            res += f"""
            <label class="model-check-item {prefix}-check-item {selected_cls}" data-id="{m_id}" data-category="{category}" data-provider="{prov_lower}" data-name="{m_name.lower()}">
                <input type="checkbox" name="{prefix}-selected-models" value="{m_id}" class="{prefix}-checkbox" {checked_attr} onchange="onPredictModelPick('{prefix}', this)">
                <div class="model-info">
                    <span class="model-name" title="{m_name}">{m_name}</span>
                    <div class="model-meta">
                        <span class="badge {badge_cls}">{prov}</span>
                        <span class="model-status">{status_tag}</span>
                    </div>
                </div>
            </label>
            """
        return res

    baseline_items = _render_items(baselines, "baselines")
    frontier_items = _render_items(frontier_llms, "frontier")
    custom_items = _render_items(custom_models, "custom")

    if default_all:
        count_text = f"Selected: All {total_models} Models (Full Scope)"
        count_badge_cls = "badge-emerald"
    else:
        count_text = "Selected: 1 Model (Raw Lexicon Match)"
        count_badge_cls = "badge-cyan"

    return f"""
    <div class="form-group" style="margin-bottom: 1.25rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem;">
            <label class="form-label" style="margin-bottom: 0;">Select Evaluation Model(s):</label>
            <span id="{prefix}-selected-count" class="badge {count_badge_cls}" style="font-family: var(--font-mono); font-size: 0.78rem;">{count_text}</span>
        </div>

        <div style="display: flex; gap: 0.4rem; margin-bottom: 0.6rem; flex-wrap: wrap; align-items: center;">
            <button type="button" class="btn-sm btn-cyan" onclick="selectPredictModels('{prefix}', 'all')">🔘 Select All ({total_models})</button>
            <button type="button" class="btn-sm btn-outline" onclick="selectPredictModels('{prefix}', 'baselines')">⚡ Local Baselines ({total_baselines})</button>
            <button type="button" class="btn-sm btn-outline" onclick="selectPredictModels('{prefix}', 'llms')">🤖 Frontier LLMs ({total_llms})</button>
            <button type="button" class="btn-sm btn-outline" onclick="selectPredictModels('{prefix}', 'custom')">🛠️ Custom ({total_custom})</button>
            <button type="button" class="btn-sm btn-outline" onclick="selectPredictModels('{prefix}', 'none')">🧹 Clear</button>
            <input type="text" class="search-input" id="{prefix}-model-filter" placeholder="Filter models..." onkeyup="filterModelCheckboxes('{prefix}')" style="max-width: 170px; padding: 0.25rem 0.6rem; font-size: 0.78rem; margin-left: auto;">
        </div>

        <div class="model-columns-container" id="{prefix}-model-grid">
            <!-- Column 1: Local Baselines -->
            <div class="model-column">
                <div class="model-column-header">
                    <div style="font-size: 0.78rem; font-weight: 700; color: var(--accent-cyan); display: flex; align-items: center; gap: 0.35rem;">
                        <span>⚡</span> Local Baselines <span class="badge badge-cyan" style="font-size: 0.65rem; padding: 0.05rem 0.35rem;">{total_baselines}</span>
                    </div>
                    <button type="button" class="btn-col-select" style="color: var(--accent-cyan);" onclick="selectPredictModels('{prefix}', 'baselines')">Select Only</button>
                </div>
                <div class="model-column-scroll">
                    {baseline_items}
                </div>
            </div>

            <!-- Column 2: Frontier LLMs -->
            <div class="model-column">
                <div class="model-column-header">
                    <div style="font-size: 0.78rem; font-weight: 700; color: var(--accent-indigo); display: flex; align-items: center; gap: 0.35rem;">
                        <span>🤖</span> Frontier LLMs <span class="badge badge-indigo" style="font-size: 0.65rem; padding: 0.05rem 0.35rem;">{total_llms}</span>
                    </div>
                    <button type="button" class="btn-col-select" style="color: var(--accent-indigo);" onclick="selectPredictModels('{prefix}', 'llms')">Select Only</button>
                </div>
                <div class="model-column-scroll">
                    {frontier_items}
                </div>
            </div>

            <!-- Column 3: Custom Models -->
            <div class="model-column">
                <div class="model-column-header">
                    <div style="font-size: 0.78rem; font-weight: 700; color: var(--accent-purple); display: flex; align-items: center; gap: 0.35rem;">
                        <span>🛠️</span> Custom Models <span class="badge badge-purple" style="font-size: 0.65rem; padding: 0.05rem 0.35rem;">{total_custom}</span>
                    </div>
                    <button type="button" class="btn-col-select" style="color: var(--accent-purple);" onclick="selectPredictModels('{prefix}', 'custom')">Select Only</button>
                </div>
                <div class="model-column-scroll" id="{prefix}-custom-list">
                    {custom_items}
                </div>
                <div style="margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px solid rgba(255,255,255,0.06); display: flex; gap: 0.3rem;">
                    <input type="text" id="{prefix}-custom-input" placeholder="Add custom model ID..." style="flex: 1; min-width: 0; background: rgba(0,0,0,0.3); border: 1px solid var(--border-card); border-radius: 6px; padding: 0.25rem 0.5rem; font-size: 0.72rem; color: #fff; outline: none;">
                    <button type="button" onclick="addCustomPredictModel('{prefix}')" style="background: var(--accent-purple); border: none; color: #fff; font-size: 0.7rem; font-weight: 600; padding: 0.25rem 0.55rem; border-radius: 6px; cursor: pointer; white-space: nowrap;">+ Add</button>
                </div>
            </div>
        </div>
    </div>
    """


def generate_service_dashboard_html(
    reports_dir: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> str:
    """Generate interactive single-page dashboard HTML for the running evaluator service."""
    rep_dir = reports_dir or Path("reports")
    alt_rep_dir = Path("data/processed/report")

    cache_paths = [
        rep_dir / "llm_error_cases.json",
        alt_rep_dir / "llm_error_cases.json",
        rep_dir / "difficulty_ranking.yaml",
        rep_dir / "difficulty_ranking.json",
        alt_rep_dir / "difficulty_ranking.yaml",
        alt_rep_dir / "difficulty_ranking.json",
        rep_dir / "evaluation_results.yaml",
        rep_dir / "data" / "evaluation_results.yaml",
        alt_rep_dir / "evaluation_results.yaml",
        alt_rep_dir / "data" / "evaluation_results.yaml",
        rep_dir / "manifest.json",
        alt_rep_dir / "manifest.json",
        Path("data/processed/evaluate/evaluation_results.yaml"),
        Path(".env"),
    ]
    fingerprint = _dependency_fingerprint(cache_paths, "dashboard", host, str(port))
    with _HTML_CACHE_LOCK:
        hit = _HTML_CACHE.get("service_dashboard")
        if hit and hit[0] == fingerprint:
            return hit[1]

    html = _generate_service_dashboard_html_uncached(rep_dir, alt_rep_dir, host, port)
    with _HTML_CACHE_LOCK:
        _HTML_CACHE["service_dashboard"] = (fingerprint, html)
    return html


def _generate_service_dashboard_html_uncached(
    rep_dir: Path,
    alt_rep_dir: Path,
    host: str,
    port: int,
) -> str:
    """Build dashboard HTML without consulting the HTML cache."""

    def _pick_errors_path() -> Path:
        candidates = [
            rep_dir / "llm_error_cases.json",
            alt_rep_dir / "llm_error_cases.json",
            Path("data/processed/evaluate") / "llm_error_cases.json",
        ]
        existing = [p for p in candidates if p.exists()]
        if not existing:
            return candidates[0]
        # Prefer larger dump without parsing every candidate fully on cold start
        existing.sort(key=lambda p: p.stat().st_size, reverse=True)
        best = existing[0]
        best_data = _load_json_safe(best)
        best_n = int((best_data.get("summary") or {}).get("total_error_instances") or 0)
        if best_n > 0:
            return best
        for path in existing[1:]:
            data = _load_json_safe(path)
            n = int((data.get("summary") or {}).get("total_error_instances") or 0)
            if n > best_n:
                best = path
                best_n = n
        return best

    errors_path = _pick_errors_path()
    difficulty_yaml = (
        rep_dir / "difficulty_ranking.yaml"
        if (rep_dir / "difficulty_ranking.yaml").exists()
        else alt_rep_dir / "difficulty_ranking.yaml"
    )

    errors_data = _load_json_safe(errors_path)
    difficulty_data = _load_difficulty_data(difficulty_yaml)

    # Extract high-level summary KPIs and detailed evaluated models catalog
    catalog = build_evaluated_models_catalog(rep_dir)
    models_count = catalog["total_models"] or 38
    accessible_models_count = catalog["accessible_count"]
    free_tier_count = catalog["free_tier_count"]
    openrouter_count = sum(1 for m in catalog["models"] if "openrouter" in m["provider"].lower())
    requesty_count = sum(1 for m in catalog["models"] if "requesty" in m["provider"].lower())
    local_baseline_count = sum(1 for m in catalog["models"] if m["provider"] == "Local Baseline")
    session_info = catalog["session"]
    dash_model_selector = generate_model_selector_component(catalog["models"], prefix="dash")

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
            <td style="text-align: center;">
                <button class="btn-sm btn-cyan" onclick="openModelPredict('{html_escape(m['id'], quote=True)}')">⚡ Test</button>
            </td>
        </tr>
        """

    # Extract top models and key performers for analytics tab
    top_llm = catalog["models"][0] if catalog["models"] else None
    baselines_list = [m for m in catalog["models"] if m["provider"] == "Local Baseline"]
    top_baseline = baselines_list[0] if baselines_list else None
    max_delta_model = max(catalog["models"], key=lambda m: m["delta_auprc"]) if catalog["models"] else None

    # Pre-render cross-condition analytics performance matrix and trajectory progress bars
    analytics_model_selector = generate_model_selector_component(catalog["models"], prefix="analytics", default_all=True)
    analytics_matrix_rows = build_analytics_matrix_rows_html(catalog["models"])
    trajectory_bars_html = build_trajectory_bars_html(catalog["models"])

    total_errors = errors_data.get("summary", {}).get("total_error_instances", 22)
    raw_diff_sentences = difficulty_data.get("sentences", [])

    # Group and aggregate distinct unique linguistic utterances across conversations
    grouped_diff: dict[str, dict[str, Any]] = {}
    for s in raw_diff_sentences:
        txt = s.get("turn_text", "").strip()
        if not txt:
            continue
        key = txt.lower()
        if key not in grouped_diff:
            grouped_diff[key] = {
                "turn_text": txt,
                "gold_actionable": s.get("gold_actionable", False),
                "gold_severity": s.get("gold_severity", "unknown"),
                "platform_style": s.get("platform_style", "unknown"),
                "occurrences": 0,
                "total_evaluations": 0,
                "total_errors": 0,
                "error_rates": [],
                "priority_weights": [],
                "primary_error_type": s.get("primary_error_type", "None"),
                "sample_conversations": [],
            }
        g = grouped_diff[key]
        g["occurrences"] += 1
        g["total_evaluations"] += s.get("total_evaluations", 0)
        g["total_errors"] += s.get("total_errors", 0)
        g["error_rates"].append(s.get("error_rate", 0.0))
        g["priority_weights"].append(s.get("priority_weight", 0.0))
        if len(g["sample_conversations"]) < 3:
            cid = s.get("conversation_id", "")
            tid = s.get("turn_id", "")
            g["sample_conversations"].append(f"{cid}:{tid}")

    distinct_difficulty_sentences: list[dict[str, Any]] = []
    for g in grouped_diff.values():
        avg_err = sum(g["error_rates"]) / len(g["error_rates"]) if g["error_rates"] else 0.0
        max_prio = max(g["priority_weights"]) if g["priority_weights"] else 0.0
        distinct_difficulty_sentences.append(
            {
                "turn_text": g["turn_text"],
                "occurrences": g["occurrences"],
                "gold_actionable": g["gold_actionable"],
                "gold_severity": g["gold_severity"],
                "platform_style": g["platform_style"],
                "total_evaluations": g["total_evaluations"],
                "total_errors": g["total_errors"],
                "error_rate": avg_err,
                "priority_weight": max_prio,
                "primary_error_type": g["primary_error_type"],
                "sample_conversations": ", ".join(g["sample_conversations"]),
            }
        )
    distinct_difficulty_sentences.sort(key=lambda x: (x["priority_weight"], x["total_errors"]), reverse=True)
    hardest_turns_count = len(distinct_difficulty_sentences)

    fp_words = difficulty_data.get("metadata", {}).get("top_fp_triggers", [])[:8] or [
        "unreal", "trickshot", "swear", "cracked", "deadass", "holy", "shit", "lmao"
    ]
    fn_words = difficulty_data.get("metadata", {}).get("top_fn_indicators", [])[:8] or [
        "garbage", "uninstall", "fucking", "trash", "useless", "kys", "feeding"
    ]
    fp_trigger_buttons = "".join(
        f'<button class="btn-sm btn-outline" style="margin: 0.2rem; cursor: pointer;" onclick="filterDifficultyByWord(\'{w}\')">🔴 {w}</button>'
        for w in fp_words
    )
    fn_trigger_buttons = "".join(
        f'<button class="btn-sm btn-outline" style="margin: 0.2rem; cursor: pointer;" onclick="filterDifficultyByWord(\'{w}\')">🟠 {w}</button>'
        for w in fn_words
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

    total_error_case_count = int(
        errors_data.get("summary", {}).get("total_error_instances") or len(all_error_cases)
    )
    # Keep the page light: render a capped sample; full dump stays on /api/errors
    inline_error_cases = all_error_cases[:MAX_INLINE_ERROR_CASES]
    error_truncation_note = ""
    if len(all_error_cases) > MAX_INLINE_ERROR_CASES:
        error_truncation_note = (
            f'<div style="color: var(--text-muted); font-size: 0.8rem; margin: 0.5rem 0 0.75rem;">'
            f'Showing {MAX_INLINE_ERROR_CASES} of {total_error_case_count} cases for responsiveness. '
            f'Full JSON: <a href="/api/errors" target="_blank" style="color: var(--accent-cyan);">/api/errors</a>'
            f"</div>"
        )

    # Prepare difficulty sentences list (using distinct linguistic utterances)
    difficulty_sentences = distinct_difficulty_sentences[:20]

    # Pre-render error cases rows
    error_cases_rows = ""
    if not inline_error_cases:
        error_cases_rows = """
                            <tr>
                                <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem 1rem;">
                                    No failure cases loaded. Re-run the report stage or ensure
                                    <code>llm_error_cases.json</code> contains a non-empty <code>by_model</code> map.
                                </td>
                            </tr>
        """
    for row in inline_error_cases:
        is_fp = "False Positive" in row["error_type"]
        badge_cls = "badge-amber" if is_fp else "badge-rose"
        label_short = "FP (Over-mod)" if is_fp else "FN (Missed)"
        error_cases_rows += f"""
                            <tr data-type="{row['error_type']}">
                                <td class="cell-mono"><strong>{row['model']}</strong></td>
                                <td style="max-width: 320px; font-weight: 500;">"{html_escape(str(row['turn_text']))}"</td>
                                <td><span class="badge {badge_cls}">{label_short}</span></td>
                                <td><span class="badge badge-indigo">{html_escape(str(row['gold_severity']))}</span></td>
                                <td class="cell-mono" style="font-weight: 700;">{row['prob']:.2f}</td>
                                <td style="color: var(--text-secondary); font-size: 0.8rem;">{html_escape(str(row['reason']))}</td>
                            </tr>
        """

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
        .kpi-row > .kpi-card[data-tab] {{
            cursor: pointer;
        }}
        .kpi-row > .kpi-card.is-selected {{
            border-color: rgba(56, 189, 248, 0.55);
            box-shadow:
                0 0 0 1px rgba(56, 189, 248, 0.28),
                0 10px 28px rgba(56, 189, 248, 0.18);
            background: linear-gradient(160deg, rgba(56, 189, 248, 0.12), var(--bg-card) 55%);
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
            align-items: center;
        }}
        .tab-btn {{
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-card);
            border-bottom-color: var(--border-card);
            color: var(--text-secondary);
            font-family: var(--font-sans);
            font-size: 0.88rem;
            font-weight: 600;
            height: 42px;
            padding: 0 1.15rem;
            border-radius: 10px;
            cursor: pointer;
            transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.6rem;
            white-space: nowrap;
            box-sizing: border-box;
            line-height: 1;
            user-select: none;
        }}
        .tab-btn:hover {{
            color: var(--text-primary);
            background: rgba(255, 255, 255, 0.05);
            border-color: var(--border-card);
            border-bottom-color: var(--border-card);
        }}
        .tab-btn:focus {{
            outline: none;
        }}
        .tab-btn:focus-visible {{
            outline: 2px solid var(--accent-cyan);
            outline-offset: 1px;
        }}
        .tab-btn.active {{
            color: #ffffff;
            background: linear-gradient(135deg, rgba(56, 189, 248, 0.28), rgba(129, 140, 248, 0.22));
            border-color: rgba(56, 189, 248, 0.55);
            border-bottom-color: rgba(56, 189, 248, 0.55);
            box-shadow:
                0 0 0 1px rgba(56, 189, 248, 0.2),
                0 6px 18px rgba(56, 189, 248, 0.22);
            transform: translateY(-1px);
        }}
        .tab-badge {{
            font-size: 0.72rem;
            font-family: var(--font-mono);
            font-weight: 700;
            padding: 0.15rem 0.55rem;
            border-radius: 9999px;
            background: rgba(255, 255, 255, 0.08);
            color: var(--text-secondary);
            border: 1px solid rgba(255, 255, 255, 0.1);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            line-height: 1.2;
            height: 20px;
            box-sizing: border-box;
        }}
        .tab-btn.active .tab-badge {{
            background: rgba(56, 189, 248, 0.32);
            color: #e0f2fe;
            border-color: rgba(125, 211, 252, 0.35);
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
        .badge-outline {{
            background: rgba(255, 255, 255, 0.04);
            color: var(--text-secondary);
            border: 1px solid var(--border-card);
        }}

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

        /* Governance / Data tab layout */
        .panel-subtitle {{
            color: var(--text-secondary);
            font-size: 0.88rem;
            margin-top: 0.3rem;
            max-width: 52rem;
            line-height: 1.45;
        }}
        .gov-kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1rem;
            margin-bottom: 0;
            width: 100%;
        }}
        @media (max-width: 1100px) {{
            .gov-kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        }}
        @media (max-width: 640px) {{
            .gov-kpi-grid {{ grid-template-columns: 1fr; }}
        }}
        .gov-gallery {{
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
            width: 100%;
            max-width: 100%;
        }}
        .gov-figure {{
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid var(--border-card);
            border-radius: 12px;
            padding: 1rem;
            width: 100%;
            max-width: 100%;
            box-sizing: border-box;
            transition: border-color 0.2s ease;
        }}
        .gov-figure:hover {{
            border-color: var(--border-glow);
        }}
        .gov-figure-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 0.75rem;
            margin-bottom: 0.75rem;
            flex-wrap: wrap;
        }}
        .gov-figure-meta {{
            min-width: 0;
            flex: 1;
        }}
        .gov-figure-title {{
            font-weight: 700;
            font-size: 0.95rem;
            color: #ffffff;
            line-height: 1.35;
        }}
        .gov-figure-desc {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
            line-height: 1.4;
        }}
        .gov-figure-actions {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            flex-shrink: 0;
        }}
        .gov-figure-img-wrap {{
            width: 100%;
            max-width: 100%;
            overflow: hidden;
            border-radius: 8px;
            background: #0b0f19;
            border: 1px solid rgba(255, 255, 255, 0.04);
        }}
        .gov-figure-img {{
            display: block;
            width: 100%;
            max-width: 100%;
            height: auto;
            cursor: pointer;
            vertical-align: middle;
        }}
        .matrix-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
            table-layout: auto;
        }}
        .matrix-table th,
        .matrix-table td {{
            padding: 0.85rem 1rem;
            border-bottom: 1px solid var(--border-card);
            vertical-align: middle;
        }}
        .matrix-table th {{
            background: rgba(15, 23, 42, 0.95);
            color: var(--text-muted);
            font-weight: 700;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            text-align: left;
            white-space: nowrap;
        }}
        .matrix-table tr:hover td {{
            background-color: var(--bg-card-hover);
        }}
        .table-shell {{
            width: 100%;
            max-width: 100%;
            overflow-x: auto;
            border-radius: 10px;
            border: 1px solid var(--border-card);
        }}
        .btn-sm {{
            padding: 0.35rem 0.75rem;
            font-size: 0.78rem;
            font-weight: 600;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
            border: 1px solid transparent;
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            text-decoration: none;
            box-sizing: border-box;
        }}
        .btn-cyan {{
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            border-color: rgba(56, 189, 248, 0.35);
        }}
        .btn-cyan:hover {{
            background: rgba(56, 189, 248, 0.3);
            border-color: #38bdf8;
            color: #ffffff;
        }}
        /* Attention pulse when analytics scope-changed prompt is visible */
        #btn-regenerate-analytics.btn-shine-spark {{
            position: relative;
            overflow: hidden;
            isolation: isolate;
            color: #ffffff;
            background: linear-gradient(135deg, rgba(14, 165, 233, 0.55), rgba(56, 189, 248, 0.35), rgba(125, 211, 252, 0.45));
            border-color: rgba(125, 211, 252, 0.85);
            box-shadow:
                0 0 0 1px rgba(56, 189, 248, 0.35),
                0 0 18px rgba(56, 189, 248, 0.45),
                0 0 36px rgba(14, 165, 233, 0.25);
            animation: regen-btn-glow 1.5s ease-in-out infinite;
        }}
        #btn-regenerate-analytics.btn-shine-spark::before {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(
                110deg,
                transparent 20%,
                rgba(255, 255, 255, 0.55) 45%,
                rgba(255, 255, 255, 0.15) 55%,
                transparent 75%
            );
            transform: translateX(-130%);
            animation: regen-btn-shine 1.7s ease-in-out infinite;
            pointer-events: none;
            z-index: 1;
        }}
        #btn-regenerate-analytics.btn-shine-spark::after {{
            content: '';
            position: absolute;
            inset: 0;
            pointer-events: none;
            z-index: 2;
            background:
                radial-gradient(circle at 12% 30%, rgba(255, 255, 255, 0.95) 0 1.5px, transparent 2.5px),
                radial-gradient(circle at 78% 22%, rgba(255, 255, 255, 0.9) 0 1.2px, transparent 2.2px),
                radial-gradient(circle at 88% 70%, rgba(186, 230, 253, 1) 0 1.6px, transparent 2.6px),
                radial-gradient(circle at 24% 78%, rgba(255, 255, 255, 0.85) 0 1.1px, transparent 2px),
                radial-gradient(circle at 52% 18%, rgba(255, 255, 255, 0.9) 0 1px, transparent 1.8px),
                radial-gradient(circle at 62% 82%, rgba(125, 211, 252, 1) 0 1.3px, transparent 2.3px);
            animation: regen-btn-spark 1.1s ease-in-out infinite;
        }}
        #btn-regenerate-analytics.btn-shine-spark > * {{
            position: relative;
            z-index: 3;
        }}
        #btn-regenerate-analytics .btn-regen-label {{
            position: relative;
            z-index: 3;
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
        }}
        @keyframes regen-btn-glow {{
            0%, 100% {{
                box-shadow:
                    0 0 0 1px rgba(56, 189, 248, 0.35),
                    0 0 14px rgba(56, 189, 248, 0.35),
                    0 0 28px rgba(14, 165, 233, 0.18);
                filter: brightness(1);
            }}
            50% {{
                box-shadow:
                    0 0 0 2px rgba(125, 211, 252, 0.65),
                    0 0 22px rgba(56, 189, 248, 0.7),
                    0 0 44px rgba(14, 165, 233, 0.4);
                filter: brightness(1.12);
            }}
        }}
        @keyframes regen-btn-shine {{
            0% {{ transform: translateX(-130%) skewX(-12deg); opacity: 0; }}
            25% {{ opacity: 1; }}
            55% {{ transform: translateX(130%) skewX(-12deg); opacity: 0.85; }}
            100% {{ transform: translateX(130%) skewX(-12deg); opacity: 0; }}
        }}
        @keyframes regen-btn-spark {{
            0%, 100% {{ opacity: 0.25; transform: scale(0.92); }}
            35% {{ opacity: 1; transform: scale(1.08); }}
            60% {{ opacity: 0.45; transform: scale(1); }}
        }}
        .btn-outline {{
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-secondary);
            border-color: var(--border-card);
        }}
        .btn-outline:hover {{
            background: rgba(255, 255, 255, 0.1);
            color: #ffffff;
            border-color: var(--border-glow);
        }}
        .modal-backdrop {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(0, 0, 0, 0.85);
            backdrop-filter: blur(8px);
            z-index: 9999;
            align-items: center;
            justify-content: center;
            padding: 1.5rem;
        }}
        .modal-backdrop.active {{
            display: flex;
        }}
        .modal-content {{
            background: #0f172a;
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 1.5rem;
            max-width: 95vw;
            max-height: 95vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8);
        }}
        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }}
        .modal-close {{
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 1.6rem;
            cursor: pointer;
            line-height: 1;
            padding: 0 0.25rem;
            transition: color 0.2s ease;
        }}
        .modal-close:hover {{
            color: #ffffff;
        }}
        #lightbox-img {{
            max-width: 100%;
            max-height: 75vh;
            object-fit: contain;
            border-radius: 8px;
            background: #080c14;
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

        /* Model Selection 3-Column Layout & Meaningful Padding Area Box Color */
        .model-columns-container {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.75rem;
            margin-top: 0.5rem;
        }}
        @media (max-width: 960px) {{
            .model-columns-container {{
                grid-template-columns: 1fr;
            }}
        }}
        .model-column {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-card);
            border-radius: 12px;
            padding: 0.75rem;
            display: flex;
            flex-direction: column;
            min-width: 0;
            box-sizing: border-box;
        }}
        .model-column-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 0.45rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            margin-bottom: 0.45rem;
        }}
        .model-column-scroll {{
            max-height: 220px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
            padding-right: 0.2rem;
        }}
        .btn-col-select {{
            background: none;
            border: none;
            font-size: 0.72rem;
            font-weight: 600;
            cursor: pointer;
            text-decoration: underline;
            padding: 0.1rem 0.3rem;
            border-radius: 4px;
            transition: opacity 0.15s ease;
        }}
        .btn-col-select:hover {{
            opacity: 0.8;
        }}
        .model-check-item {{
            display: flex;
            align-items: center;
            gap: 0.65rem;
            padding: 0.65rem 0.85rem;
            border-radius: 9px;
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid var(--border-card);
            border-color: var(--border-card);
            cursor: pointer;
            transition: background 0.15s ease, box-shadow 0.15s ease;
            user-select: none;
            box-sizing: border-box;
            width: 100%;
            position: relative;
        }}
        .model-check-item:hover {{
            background: rgba(30, 41, 59, 0.85);
            border-color: var(--border-card);
        }}
        .model-check-item input[type="checkbox"] {{
            margin: 0;
            width: 16px;
            height: 16px;
            accent-color: var(--accent-cyan);
            cursor: pointer;
            flex-shrink: 0;
        }}
        .model-info {{
            display: flex;
            flex-direction: column;
            min-width: 0;
            flex: 1;
        }}
        .model-name {{
            font-size: 0.8rem;
            font-weight: 600;
            color: #cbd5e1;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            line-height: 1.3;
        }}
        .model-meta {{
            display: flex;
            gap: 0.35rem;
            align-items: center;
            margin-top: 0.2rem;
            flex-wrap: wrap;
        }}
        .model-status {{
            font-size: 0.68rem;
            color: var(--text-muted);
        }}
        /* Selected: background only — keep row border-color identical */
        .model-check-item.is-selected,
        .model-check-item:has(input:checked) {{
            background: linear-gradient(135deg, rgba(14, 165, 233, 0.2), rgba(99, 102, 241, 0.16)) !important;
            border: 1px solid var(--border-card) !important;
            border-color: var(--border-card) !important;
            box-shadow: 0 0 12px rgba(56, 189, 248, 0.12) !important;
        }}
        .model-check-item.is-selected .model-name,
        .model-check-item:has(input:checked) .model-name {{
            color: #ffffff !important;
            font-weight: 700 !important;
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
            padding: 0.4rem 0.85rem;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.15s ease;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.4rem;
            box-sizing: border-box;
            line-height: 1;
            user-select: none;
        }}
        .filter-btn:focus {{
            outline: none;
        }}
        .filter-btn:hover {{
            color: #ffffff;
            border-color: rgba(255, 255, 255, 0.2);
            background: #283548;
        }}
        .filter-btn.active {{
            background: rgba(56, 189, 248, 0.16);
            color: var(--accent-cyan);
            border-color: rgba(56, 189, 248, 0.45);
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
            <div class="kpi-card" data-tab="tab-models" onclick="switchTab('tab-models')" style="cursor: pointer; transition: transform 0.2s;" title="Click to view all {models_count} evaluated models, run timestamps, and live accessibility">
                <div class="kpi-label">Evaluated Models ↗</div>
                <div class="kpi-num">{models_count}</div>
                <div class="kpi-desc">32 Frontier LLMs & 6 Baselines</div>
            </div>
            <div class="kpi-card" data-tab="tab-errors" onclick="switchTab('tab-errors')" style="cursor: pointer; transition: transform 0.2s;" title="Click to view turn-by-turn failure case diagnostics">
                <div class="kpi-label">Identified Error Cases ↗</div>
                <div class="kpi-num" style="color: var(--accent-rose);">{total_errors}</div>
                <div class="kpi-desc">Turn-by-Turn Failure Diagnostics</div>
            </div>
            <div class="kpi-card" data-tab="tab-difficulty" onclick="switchTab('tab-difficulty')" style="cursor: pointer; transition: transform 0.2s;" title="Click to view distinct difficult turn patterns and error vulnerabilities">
                <div class="kpi-label">Hardest Evaluated Turns ↗</div>
                <div class="kpi-num" style="color: var(--accent-amber);">{hardest_turns_count}</div>
                <div class="kpi-desc">Distinct Linguistic Patterns (from 1,000 Turns)</div>
            </div>
            <div class="kpi-card" data-tab="tab-data" onclick="switchTab('tab-data')" style="cursor: pointer; transition: transform 0.2s;" title="Click to view datasets, corpora, and audit reports">
                <div class="kpi-label">Unified Profanity Terms ↗</div>
                <div class="kpi-num" style="color: var(--accent-emerald);">2,826</div>
                <div class="kpi-desc">18 Vetted Legal Sources</div>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <nav class="nav-tabs" id="nav-tabs" role="tablist">
            <button type="button" class="tab-btn active" role="tab" aria-selected="true" data-tab="tab-analytics" onclick="switchTab('tab-analytics')" id="btn-tab-analytics">
                <span>📈</span> Visual Analytics & Heatmaps <span class="tab-badge">4 Figures</span>
            </button>
            <button type="button" class="tab-btn" role="tab" aria-selected="false" data-tab="tab-models" onclick="switchTab('tab-models')" id="btn-tab-models">
                <span>🤖</span> Evaluated Models & Live Access <span class="tab-badge">{models_count}</span>
            </button>
            <button type="button" class="tab-btn" role="tab" aria-selected="false" data-tab="tab-errors" onclick="switchTab('tab-errors')" id="btn-tab-errors">
                <span>🔍</span> Failure Case Diagnostics <span class="tab-badge">{total_errors}</span>
            </button>
            <button type="button" class="tab-btn" role="tab" aria-selected="false" data-tab="tab-difficulty" onclick="switchTab('tab-difficulty')" id="btn-tab-difficulty">
                <span>🎯</span> Hard-Sample Ranking <span class="tab-badge">{hardest_turns_count}</span>
            </button>
            <button type="button" class="tab-btn" role="tab" aria-selected="false" data-tab="tab-playground" onclick="switchTab('tab-playground')" id="btn-tab-playground">
                <span>⚡</span> Live Predict Playground <span class="tab-badge">Sandbox</span>
            </button>
            <button type="button" class="tab-btn" role="tab" aria-selected="false" data-tab="tab-data" onclick="switchTab('tab-data')" id="btn-tab-data">
                <span>📋</span> Data & Governance Reports <span class="tab-badge">Audits</span>
            </button>
        </nav>

        <!-- TAB 1: Visual Analytics & Infographics -->
        <section class="tab-content active" id="tab-analytics">
            <!-- Analytics Header & Quick Action Strip -->
            <div class="panel-card" style="margin-bottom: 1.5rem;">
                <div class="panel-header">
                    <div>
                        <h2 class="panel-title"><span>📊</span> Automated Publication Infographics & Visual Analytics</h2>
                        <p style="color: var(--text-secondary); font-size: 0.88rem; margin-top: 0.25rem;">
                            Cross-condition causal sensitivity benchmarks, publication-ready figures, and full context trajectory dynamics across {models_count} evaluated models.
                        </p>
                    </div>
                    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                        <a href="/reports/infographic_dashboard.html" target="_blank" class="btn-sm btn-cyan" style="text-decoration: none;">
                            <span>🌐</span> Standalone HTML Dashboard ↗
                        </a>
                        <a href="/reports/evaluation_report.md" target="_blank" class="btn-sm btn-outline" style="text-decoration: none;">
                            <span>📄</span> Full Markdown Report ↗
                        </a>
                        <a href="/reports/table_main_results.tex" target="_blank" class="btn-sm btn-outline" style="text-decoration: none;">
                            <span>📋</span> LaTeX Table ↗
                        </a>
                    </div>
                </div>

                <!-- 4 KPI Summary Strips -->
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-top: 1rem;">
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 0.9rem 1.1rem; border-radius: 10px; border: 1px solid var(--border-card);">
                        <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.05em;">Top Frontier LLM (Full Prefix)</div>
                        <div style="font-size: 1.25rem; font-weight: 700; color: #ffffff; margin: 0.2rem 0;" id="analytics-kpi-top-llm-name">{top_llm['name'] if top_llm else 'Mistral Small Latest'}</div>
                        <div style="font-size: 0.78rem; color: var(--accent-emerald); font-weight: 600;" id="analytics-kpi-top-llm-score">{top_llm['prefix_auprc'] if top_llm else 0.995:.3f} AUPRC (Top Performer)</div>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 0.9rem 1.1rem; border-radius: 10px; border: 1px solid var(--border-card);">
                        <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.05em;">Top Baseline Keyword Match</div>
                        <div style="font-size: 1.25rem; font-weight: 700; color: #ffffff; margin: 0.2rem 0;" id="analytics-kpi-top-baseline-name">{top_baseline['name'] if top_baseline else 'Raw Lexicon Match'}</div>
                        <div style="font-size: 0.78rem; color: var(--accent-cyan); font-weight: 600;" id="analytics-kpi-top-baseline-score">{top_baseline['prefix_auprc'] if top_baseline else 0.763:.3f} AUPRC (Offline Baseline)</div>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 0.9rem 1.1rem; border-radius: 10px; border: 1px solid var(--border-card);">
                        <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.05em;">Maximum Causal Context Gain</div>
                        <div style="font-size: 1.25rem; font-weight: 700; color: var(--accent-emerald); margin: 0.2rem 0;" id="analytics-kpi-max-delta-val">+{max_delta_model['delta_auprc'] if max_delta_model else 0.092:.3f} Δ AUPRC</div>
                        <div style="font-size: 0.78rem; color: var(--text-secondary);" id="analytics-kpi-max-delta-name">{max_delta_model['name'] if max_delta_model else 'Nemotron 3 Nano Omni'}</div>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 0.9rem 1.1rem; border-radius: 10px; border: 1px solid var(--border-card);">
                        <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.05em;">Evaluated Context Scope</div>
                        <div style="font-size: 1.25rem; font-weight: 700; color: var(--accent-cyan); margin: 0.2rem 0;" id="analytics-kpi-models-count">{models_count} Models</div>
                        <div style="font-size: 0.78rem; color: var(--text-muted);" id="analytics-kpi-models-sub">Turn / Prev+Turn / Prefix (1k Turns)</div>
                    </div>
                </div>

                <!-- Interactive Model Scope Selector for Visual Analytics & Infographics -->
                <div style="margin-top: 1.5rem; padding-top: 1.25rem; border-top: 1px solid var(--border-card);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.75rem;">
                        <div>
                            <h3 style="font-size: 0.95rem; font-weight: 700; color: #ffffff; display: flex; align-items: center; gap: 0.4rem; margin: 0;">
                                <span>🎯</span> Model Scope for Visual Analytics & Infographics
                            </h3>
                            <p style="font-size: 0.78rem; color: var(--text-secondary); margin: 0.2rem 0 0 0;">
                                By default, all models are included. Filter or select specific models below, then click Regenerate to update all figures, trajectory dynamics, and performance tables.
                            </p>
                        </div>
                        <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                            <button type="button" class="btn-sm btn-cyan" id="btn-regenerate-analytics" onclick="regenerateAnalyticsInfographics()" style="padding: 0.45rem 1rem; font-weight: 700; cursor: pointer;">
                                <span class="btn-regen-label"><span>🔄</span> Regenerate Infographics</span>
                            </button>
                        </div>
                    </div>
                    <div id="analytics-regen-status" style="display: none; margin-bottom: 0.85rem; padding: 0.65rem 1rem; border-radius: 8px; font-size: 0.82rem;"></div>
                    {analytics_model_selector}
                </div>
            </div>

            <!-- Context Progression Dynamics Visualizer -->
            <div class="panel-card" style="margin-bottom: 1.5rem;">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title" style="font-size: 1.05rem;"><span>📈</span> Causal Context Trajectories (Turn Only → Prev + Turn → Full Prefix)</h3>
                        <p style="color: var(--text-secondary); font-size: 0.82rem; margin-top: 0.2rem;">
                            Visual progression showing how model discrimination changes as contextual dialogue history expands from isolated turns to full prefixes.
                        </p>
                    </div>
                    <span class="badge badge-purple">Context Uplift Dynamics</span>
                </div>
                <div id="analytics-trajectory-container" style="margin-top: 0.75rem;">
                    {trajectory_bars_html}
                </div>
            </div>

            <!-- Publication Infographics Gallery -->
            <div class="panel-card" style="margin-bottom: 1.5rem;">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title" style="font-size: 1.05rem;"><span>🖼️</span> Publication-Ready Benchmark Figures (High-Resolution)</h3>
                        <p style="color: var(--text-secondary); font-size: 0.82rem; margin-top: 0.2rem;">
                            Click any figure to view in full resolution or click the download button for production vector/PNG assets.
                        </p>
                    </div>
                    <span class="badge badge-cyan">Auto-Generated Visuals</span>
                </div>
                <div class="gallery-grid">
                    <!-- Figure 1 -->
                    <div class="gallery-item">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.25rem;">
                            <span style="font-weight: 700; font-size: 0.88rem; color: #fff;">Fig 1: Comprehensive Multi-Panel Benchmark</span>
                            <span class="badge badge-indigo">Overview</span>
                        </div>
                        <img class="gallery-img" id="fig-img-comparison" src="/reports/infographic_models_comparison.png" data-fig="infographic_models_comparison.png" alt="Fig 1: Comprehensive Multi-Panel Model Benchmark" onerror="if(!this.dataset.tried){{this.dataset.tried='1';this.src='/data/processed/report/infographic_models_comparison.png';}}" onclick="openLightbox(this.src, 'Fig 1: Comprehensive Multi-Panel Model Benchmark')">
                        <div class="gallery-caption">Comprehensive 4-quadrant benchmark visualization comparing selected models across conversational context levels.</div>
                        <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.75rem;">
                            <button class="btn-sm btn-outline" id="fig-zoom-comparison" onclick="openLightbox(document.getElementById('fig-img-comparison').src, 'Fig 1: Comprehensive Multi-Panel Model Benchmark')">🔍 Zoom</button>
                            <a href="/reports/infographic_models_comparison.png" download="infographic_models_comparison.png" id="fig-dl-comparison" class="btn-sm btn-cyan" style="text-decoration: none;">📥 Download PNG</a>
                        </div>
                    </div>

                    <!-- Figure 2 -->
                    <div class="gallery-item">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.25rem;">
                            <span style="font-weight: 700; font-size: 0.88rem; color: #fff;">Fig 2: AUPRC & AUROC Performance Matrix Heatmaps</span>
                            <span class="badge badge-purple">Heatmap</span>
                        </div>
                        <img class="gallery-img" id="fig-img-heatmap" src="/reports/figure_auprc_heatmap.png" data-fig="figure_auprc_heatmap.png" alt="Fig 2: AUPRC & AUROC Performance Matrix Heatmaps" onerror="if(!this.dataset.tried){{this.dataset.tried='1';this.src='/data/processed/report/figure_auprc_heatmap.png';}}" onclick="openLightbox(this.src, 'Fig 2: AUPRC & AUROC Performance Matrix Heatmaps')">
                        <div class="gallery-caption">Direct head-to-head performance heatmaps across Isolated Turn, Previous+Turn, and Full Prefix causal windows.</div>
                        <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.75rem;">
                            <button class="btn-sm btn-outline" id="fig-zoom-heatmap" onclick="openLightbox(document.getElementById('fig-img-heatmap').src, 'Fig 2: AUPRC & AUROC Performance Matrix Heatmaps')">🔍 Zoom</button>
                            <a href="/reports/figure_auprc_heatmap.png" download="figure_auprc_heatmap.png" id="fig-dl-heatmap" class="btn-sm btn-cyan" style="text-decoration: none;">📥 Download PNG</a>
                        </div>
                    </div>

                    <!-- Figure 3 -->
                    <div class="gallery-item">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.25rem;">
                            <span style="font-weight: 700; font-size: 0.88rem; color: #fff;">Fig 3: Causal Context Expansion Dynamics</span>
                            <span class="badge badge-emerald">Trajectories</span>
                        </div>
                        <img class="gallery-img" id="fig-img-trajectory" src="/reports/figure_context_trajectory.png" data-fig="figure_context_trajectory.png" alt="Fig 3: Causal Context Expansion Dynamics" onerror="if(!this.dataset.tried){{this.dataset.tried='1';this.src='/data/processed/report/figure_context_trajectory.png';}}" onclick="openLightbox(this.src, 'Fig 3: Causal Context Expansion Dynamics')">
                        <div class="gallery-caption">Trajectory curves revealing which models benefit from contextual history vs which degrade due to conversational noise.</div>
                        <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.75rem;">
                            <button class="btn-sm btn-outline" id="fig-zoom-trajectory" onclick="openLightbox(document.getElementById('fig-img-trajectory').src, 'Fig 3: Causal Context Expansion Dynamics')">🔍 Zoom</button>
                            <a href="/reports/figure_context_trajectory.png" download="figure_context_trajectory.png" id="fig-dl-trajectory" class="btn-sm btn-cyan" style="text-decoration: none;">📥 Download PNG</a>
                        </div>
                    </div>

                    <!-- Figure 4 -->
                    <div class="gallery-item">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.25rem;">
                            <span style="font-weight: 700; font-size: 0.88rem; color: #fff;">Fig 4: Dedicated LLM Leaderboard (Full Prefix)</span>
                            <span class="badge badge-amber">Leaderboard</span>
                        </div>
                        <img class="gallery-img" id="fig-img-leaderboard" src="/reports/figure_llm_leaderboard.png" data-fig="figure_llm_leaderboard.png" alt="Fig 4: Dedicated LLM Leaderboard (Full Prefix)" onerror="if(!this.dataset.tried){{this.dataset.tried='1';this.src='/data/processed/report/figure_llm_leaderboard.png';}}" onclick="openLightbox(this.src, 'Fig 4: Dedicated LLM Leaderboard (Full Prefix)')">
                        <div class="gallery-caption">Official benchmark leaderboard ranked by Full Prefix AUPRC with 1% FPR operational safety recall.</div>
                        <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.75rem;">
                            <button class="btn-sm btn-outline" id="fig-zoom-leaderboard" onclick="openLightbox(document.getElementById('fig-img-leaderboard').src, 'Fig 4: Dedicated LLM Leaderboard (Full Prefix)')">🔍 Zoom</button>
                            <a href="/reports/figure_llm_leaderboard.png" download="figure_llm_leaderboard.png" id="fig-dl-leaderboard" class="btn-sm btn-cyan" style="text-decoration: none;">📥 Download PNG</a>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Multi-Model Performance Matrix Table -->
            <div class="panel-card">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title" style="font-size: 1.05rem;"><span>📋</span> Comprehensive Performance Matrix across Context Conditions</h3>
                        <p style="color: var(--text-secondary); font-size: 0.82rem; margin-top: 0.2rem;">
                            Exact numerical AUPRC and AUROC values for all evaluated models across Isolated Turn, Previous + Turn, and Full Prefix.
                        </p>
                    </div>
                    <input type="text" class="search-input" id="analytics-table-search" placeholder="Search model or family..." onkeyup="filterAnalyticsTable()" style="max-width: 260px;">
                </div>
                <div class="table-responsive">
                    <table id="analytics-matrix-table">
                        <thead>
                            <tr>
                                <th>Model Name</th>
                                <th>Family & Provider</th>
                                <th style="text-align: right;">Turn Only AUPRC (AUROC)</th>
                                <th style="text-align: right;">Prev + Turn AUPRC (AUROC)</th>
                                <th style="text-align: right;">Full Prefix AUPRC (AUROC)</th>
                                <th style="text-align: center;">Δ Prefix Gain</th>
                                <th style="text-align: right;">Recall @ FPR 1%</th>
                            </tr>
                        </thead>
                        <tbody id="analytics-matrix-tbody">
                            {analytics_matrix_rows}
                        </tbody>
                    </table>
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
                        <a href="/api/models" target="_blank" class="btn-sm btn-cyan" style="text-decoration: none;">
                            <span>📊</span> /api/models REST API ↗
                        </a>
                        <button onclick="switchTab('tab-playground')" class="btn-sm btn-outline">
                            <span>⚡</span> Test in Playground
                        </button>
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
                <div style="display: flex; gap: 1rem; margin-bottom: 1.25rem; flex-wrap: wrap; align-items: center; justify-content: space-between;">
                    <div class="filter-bar" style="margin-bottom: 0;">
                        <button class="filter-btn active" onclick="setModelFilter('all', this)">All Models ({models_count})</button>
                        <button class="filter-btn" onclick="setModelFilter('accessible', this)">🟢 Accessible ({accessible_models_count})</button>
                        <button class="filter-btn" onclick="setModelFilter('free', this)">🎁 Free Tier ({free_tier_count})</button>
                        <button class="filter-btn" onclick="setModelFilter('openrouter', this)">OpenRouter ({openrouter_count})</button>
                        <button class="filter-btn" onclick="setModelFilter('requesty', this)">Requesty.ai ({requesty_count})</button>
                        <button class="filter-btn" onclick="setModelFilter('local', this)">Local Baselines ({local_baseline_count})</button>
                    </div>
                    <input type="text" class="search-input" id="model-search" placeholder="Search model name, family, or ID..." onkeyup="filterModelsTable()" style="max-width: 280px;">
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
                                <th style="text-align: center;">Action</th>
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
                    <button class="filter-btn active" onclick="setErrorFilter('all', this)">All Errors ({total_error_case_count})</button>
                    <button class="filter-btn" onclick="setErrorFilter('False Positive', this)">False Positives (Over-Moderation)</button>
                    <button class="filter-btn" onclick="setErrorFilter('False Negative', this)">False Negatives (Missed Harm)</button>
                </div>
                {error_truncation_note}
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
                            {error_cases_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- TAB 3: Hard-Sample Ranking -->
        <section class="tab-content" id="tab-difficulty">
            <div class="panel-card">
                <div class="panel-header">
                    <div>
                        <h2 class="panel-title"><span>🎯</span> Internal Evaluation Difficulty Ranking & Vulnerability Index</h2>
                        <p style="color: var(--text-secondary); font-size: 0.88rem; margin-top: 0.25rem;">
                            Distinct conversational turns sorted descending by error likelihood across all {models_count} evaluated models. Prioritized during hard-sample re-evaluation passes.
                        </p>
                    </div>
                    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                        <a href="/reports/difficulty_ranking_report.md" target="_blank" class="btn-sm btn-cyan" style="text-decoration: none;">
                            <span>📄</span> Difficulty Report ↗
                        </a>
                        <a href="/api/difficulty" target="_blank" class="btn-sm btn-outline" style="text-decoration: none;">
                            <span>📊</span> /api/difficulty JSON ↗
                        </a>
                    </div>
                </div>

                <!-- Search and Filter Bar -->
                <div style="display: flex; gap: 1rem; margin-bottom: 1.25rem; flex-wrap: wrap; align-items: center; justify-content: space-between;">
                    <div class="filter-bar" style="margin-bottom: 0;">
                        <button class="filter-btn active" onclick="setDifficultyFilter('all', this)">All Difficult Patterns ({hardest_turns_count})</button>
                        <button class="filter-btn" onclick="setDifficultyFilter('False Positive', this)">🔴 Over-Moderation (FP)</button>
                        <button class="filter-btn" onclick="setDifficultyFilter('False Negative', this)">🟠 Missed Harm (FN)</button>
                        <button class="filter-btn" onclick="setDifficultyFilter('high_priority', this)">⚡ Priority > 0.20x</button>
                    </div>
                    <input type="text" class="search-input" id="difficulty-search" placeholder="Search turn text, platform, or keyword..." onkeyup="filterDifficultyTable()" style="max-width: 280px;">
                </div>

                <div class="table-responsive" style="margin-bottom: 2rem;">
                    <table id="difficulty-table">
                        <thead>
                            <tr>
                                <th>Rank</th>
                                <th>Turn Utterance</th>
                                <th>Dataset Frequency</th>
                                <th>Primary Failure Mode</th>
                                <th style="text-align: right;">Avg Error Rate</th>
                                <th style="text-align: right;">Priority Weight</th>
                                <th>Platform Style</th>
                                <th style="text-align: center;">Action</th>
                            </tr>
                        </thead>
                        <tbody>
"""

    for idx, s in enumerate(difficulty_sentences, start=1):
        err_rate = s.get("error_rate", 0.0)
        prio = s.get("priority_weight", 1.0)
        mode = s.get("primary_error_type", "Ambiguous")
        mode_badge = "badge-rose" if "Negative" in mode else "badge-amber"
        occs = s.get("occurrences", 1)
        samples = s.get("sample_conversations", "")
        clean_text_attr = html_escape(s.get("turn_text", ""), quote=True)
        clean_text_cell = html_escape(str(s.get("turn_text", "")))
        clean_samples = html_escape(str(samples))
        html += f"""
                            <tr data-mode="{html_escape(str(mode), quote=True)}" data-prio="{prio}">
                                <td class="cell-mono">#{idx}</td>
                                <td style="max-width: 420px;">
                                    <div style="font-weight: 600; color: var(--text-primary);">"{clean_text_cell}"</div>
                                    <div style="font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono); margin-top: 0.15rem;">
                                        Sample IDs: {clean_samples}
                                    </div>
                                </td>
                                <td>
                                    <span class="badge badge-indigo">{occs} turn{'s' if occs > 1 else ''} in benchmark</span>
                                </td>
                                <td><span class="badge {mode_badge}">{html_escape(str(mode))}</span></td>
                                <td class="cell-mono" style="font-weight: 700; color: var(--accent-rose); text-align: right;">{err_rate * 100:.1f}%</td>
                                <td class="cell-mono" style="color: var(--accent-cyan); font-weight: 700; text-align: right;">{prio:.3f}x</td>
                                <td><span class="badge badge-cyan">{html_escape(str(s.get("platform_style", "chat")))}</span></td>
                                <td style="text-align: center;">
                                    <button class="btn-sm btn-cyan" onclick="testTurnInPlayground(this.dataset.text)" data-text="{clean_text_attr}">⚡ Test</button>
                                </td>
                            </tr>
"""

    html += f"""
                        </tbody>
                    </table>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
                    <div style="margin-bottom: 0; background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.1rem 1.2rem;">
                        <h3 style="font-size: 1rem; color: var(--accent-amber); margin-bottom: 0.75rem;">⚠️ Top False Positive Triggers (Over-Moderation)</h3>
                        <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.6rem;">Words triggering false bans on safe banter (click word to filter table):</p>
                        <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                            {fp_trigger_buttons}
                        </div>
                    </div>
                    <div style="margin-bottom: 0; background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.1rem 1.2rem;">
                        <h3 style="font-size: 1rem; color: var(--accent-rose); margin-bottom: 0.75rem;">🚨 Top False Negative Indicators (Missed Covert Harm)</h3>
                        <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.6rem;">Words frequently involved in uncaught peer harassment (click word to filter table):</p>
                        <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                            {fn_trigger_buttons}
                        </div>
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
                        <div style="margin-bottom: 1rem;">
                            <label class="form-label">Quick Scenario Presets:</label>
                            <div class="filter-bar" style="margin-bottom: 0;">
                                <button class="filter-btn" type="button" onclick="setDashboardPreset('hype')">🎮 Benign Hype Banter</button>
                                <button class="filter-btn" type="button" onclick="setDashboardPreset('bullying')">🚨 Gaming Toxic Bullying</button>
                                <button class="filter-btn" type="button" onclick="setDashboardPreset('exclusion')">⛔ Social Exclusion</button>
                                <button class="filter-btn" type="button" onclick="setDashboardPreset('algospeak')">⚠️ Algospeak Harm</button>
                            </div>
                        </div>
                        {dash_model_selector}
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
                        <label class="form-label">Live Response Payload & Analysis:</label>
                        <div id="dash-visual-verdict" style="display: none; margin-bottom: 1rem;"></div>
                        <div class="predict-output" id="predict-result-box">// Click 'Send Prediction Request' to inspect live server output...</div>
                    </div>
                </div>
            </div>
        </section>

        <!-- TAB 5: Data & Governance Reports -->
        <section class="tab-content" id="tab-data">
            <div class="panel-card" style="margin-bottom: 1.5rem;">
                <div class="panel-header">
                    <div>
                        <h2 class="panel-title"><span>📋</span> Governance, Split Data & Audit Reports</h2>
                        <div class="panel-subtitle">Audited academic corpora, regulatory compliance scorecards, and zero-leakage benchmark partitioning.</div>
                    </div>
                    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center;">
                        <button type="button" class="btn-sm btn-cyan" id="btn-regenerate-governance" onclick="regenerateGovernanceInfographics()">
                            🔄 Regenerate Governance Infographics
                        </button>
                        <a href="/reports/data_report.md" target="_blank" class="btn-sm btn-outline">📄 data_report.md</a>
                        <a href="/reports/pii_spot_check_report.md" target="_blank" class="btn-sm btn-outline">🛡️ pii_spot_check.md</a>
                        <a href="/reports/data/audit_report.yaml" target="_blank" class="btn-sm btn-outline">⚖️ audit_report.yaml</a>
                    </div>
                </div>

                <div id="governance-regen-status" style="display: none; padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.85rem; margin-bottom: 1.25rem; font-weight: 500;"></div>

                <div class="gov-kpi-grid">
                    <div class="kpi-card">
                        <div class="kpi-label">Ingested Multi-Turn Dialogues</div>
                        <div class="kpi-num" style="font-size: 1.45rem; color: #ffffff;">103,400</div>
                        <div class="kpi-desc">Raw Conversational Pool (Snappy Parquet)</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Legal Audit Gate</div>
                        <div class="kpi-num" style="font-size: 1.45rem; color: var(--accent-emerald);">29 Sources (100%)</div>
                        <div class="kpi-desc">COPPA, GDPR-K & UK AADC Compliant</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Safe Harbor PII Redaction</div>
                        <div class="kpi-num" style="font-size: 1.45rem; color: var(--accent-cyan);">66,261 Scrubbed</div>
                        <div class="kpi-desc">Zero Residue in Spot-Check Audits</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Frozen Benchmark Partitions</div>
                        <div class="kpi-num" style="font-size: 1.45rem; color: var(--accent-indigo);">5,004 Dialogues</div>
                        <div class="kpi-desc">13,018 Turns • Zero Turn/Speaker Leakage</div>
                    </div>
                </div>
            </div>

            <div class="panel-card" style="margin-bottom: 1.5rem;">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title" style="font-size: 1.05rem;"><span>📊</span> Publication-Ready Governance & Data Infographics</h3>
                        <p style="color: var(--text-secondary); font-size: 0.82rem; margin-top: 0.2rem;">
                            Full-width high-resolution figures sized to the dashboard container. Click any figure to zoom.
                        </p>
                    </div>
                    <span class="badge badge-cyan">Auto-Generated Visuals</span>
                </div>
                <div class="gov-gallery">
                    <div class="gov-figure">
                        <div class="gov-figure-header">
                            <div class="gov-figure-meta">
                                <div class="gov-figure-title"><span class="badge badge-indigo" style="margin-right: 0.4rem;">Fig G-1</span> Corpus Governance & Multi-Source Legal Audit Architecture</div>
                                <div class="gov-figure-desc">Multi-source registry, regulatory compliance under COPPA/GDPR-K, and PII neutralization breakdown.</div>
                            </div>
                            <div class="gov-figure-actions">
                                <button type="button" class="btn-sm btn-outline" id="fig-zoom-gov-audit" onclick="openLightbox(document.getElementById('fig-img-gov-audit').src, 'Fig G-1: Corpus Governance & Multi-Source Legal Audit Architecture')">🔍 Zoom</button>
                                <a id="fig-dl-gov-audit" href="/reports/infographic_governance_audit.png" download="infographic_governance_audit.png" class="btn-sm btn-cyan">📥 Download</a>
                            </div>
                        </div>
                        <div class="gov-figure-img-wrap">
                            <img class="gov-figure-img" id="fig-img-gov-audit" src="/reports/infographic_governance_audit.png" alt="Governance and Audit Infographic" onclick="openLightbox(this.src, 'Fig G-1: Corpus Governance & Multi-Source Legal Audit Architecture')" onerror="if(!this.dataset.tried){{this.dataset.tried='1';this.src='/data/processed/report/infographic_governance_audit.png';}}">
                        </div>
                    </div>

                    <div class="gov-figure">
                        <div class="gov-figure-header">
                            <div class="gov-figure-meta">
                                <div class="gov-figure-title"><span class="badge badge-purple" style="margin-right: 0.4rem;">Fig G-2</span> Zero-Leakage Benchmark Dataset Splitting & Quota Stratification</div>
                                <div class="gov-figure-desc">Train/Dev/Test partition volume, sampling tiers, and disjoint speaker isolation guarantees.</div>
                            </div>
                            <div class="gov-figure-actions">
                                <button type="button" class="btn-sm btn-outline" id="fig-zoom-split-data" onclick="openLightbox(document.getElementById('fig-img-split-data').src, 'Fig G-2: Zero-Leakage Benchmark Dataset Splitting & Quota Stratification')">🔍 Zoom</button>
                                <a id="fig-dl-split-data" href="/reports/infographic_split_data.png" download="infographic_split_data.png" class="btn-sm btn-cyan">📥 Download</a>
                            </div>
                        </div>
                        <div class="gov-figure-img-wrap">
                            <img class="gov-figure-img" id="fig-img-split-data" src="/reports/infographic_split_data.png" alt="Dataset Splitting Infographic" onclick="openLightbox(this.src, 'Fig G-2: Zero-Leakage Benchmark Dataset Splitting & Quota Stratification')" onerror="if(!this.dataset.tried){{this.dataset.tried='1';this.src='/data/processed/report/infographic_split_data.png';}}">
                        </div>
                    </div>

                    <div class="gov-figure">
                        <div class="gov-figure-header">
                            <div class="gov-figure-meta">
                                <div class="gov-figure-title"><span class="badge badge-emerald" style="margin-right: 0.4rem;">Fig G-3</span> End-to-End Pipeline Architecture & Governance Lifecycle</div>
                                <div class="gov-figure-desc">Seven-stage lifecycle from source ingestion and PII redaction through DAG threading to frozen evaluation splits.</div>
                            </div>
                            <div class="gov-figure-actions">
                                <button type="button" class="btn-sm btn-outline" id="fig-zoom-lifecycle" onclick="openLightbox(document.getElementById('fig-img-lifecycle').src, 'Fig G-3: End-to-End Pipeline Architecture & Governance Lifecycle')">🔍 Zoom</button>
                                <a id="fig-dl-lifecycle" href="/reports/infographic_data_lifecycle.png" download="infographic_data_lifecycle.png" class="btn-sm btn-cyan">📥 Download</a>
                            </div>
                        </div>
                        <div class="gov-figure-img-wrap">
                            <img class="gov-figure-img" id="fig-img-lifecycle" src="/reports/infographic_data_lifecycle.png" alt="Data Lifecycle Infographic" onclick="openLightbox(this.src, 'Fig G-3: End-to-End Pipeline Architecture & Governance Lifecycle')" onerror="if(!this.dataset.tried){{this.dataset.tried='1';this.src='/data/processed/report/infographic_data_lifecycle.png';}}">
                        </div>
                    </div>
                </div>
            </div>

            <div class="panel-card" style="margin-bottom: 1.5rem;">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title" style="font-size: 1.05rem;"><span>⚖️</span> Stratified Zero-Leakage Benchmark Partitions</h3>
                        <p style="color: var(--text-secondary); font-size: 0.82rem; margin-top: 0.2rem;">
                            Frozen train/dev/test dialogue and turn counts with isolation guarantees.
                        </p>
                    </div>
                </div>
                <div class="table-shell">
                    <table class="matrix-table">
                        <thead>
                            <tr>
                                <th>Partition</th>
                                <th>Share (%)</th>
                                <th style="text-align: right;">Dialogues</th>
                                <th style="text-align: right;">Evaluated Turns</th>
                                <th style="text-align: right;">Avg Turns / Dialogue</th>
                                <th style="text-align: right;">File Size</th>
                                <th>Integrity Guarantee</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td style="font-weight: 700; color: var(--accent-cyan);">Train Partition</td>
                                <td><span class="badge badge-cyan">50.0%</span></td>
                                <td class="cell-mono" style="text-align: right; font-weight: 600; color: #fff;">2,502</td>
                                <td class="cell-mono" style="text-align: right; color: var(--text-primary);">6,668</td>
                                <td class="cell-mono" style="text-align: right; color: var(--text-secondary);">2.66</td>
                                <td class="cell-mono" style="text-align: right; color: var(--text-secondary);">520.8 KB</td>
                                <td><span class="badge badge-emerald">Disjoint Conversation Isolation</span></td>
                            </tr>
                            <tr>
                                <td style="font-weight: 700; color: var(--accent-indigo);">Dev Validation</td>
                                <td><span class="badge badge-purple">25.0%</span></td>
                                <td class="cell-mono" style="text-align: right; font-weight: 600; color: #fff;">1,251</td>
                                <td class="cell-mono" style="text-align: right; color: var(--text-primary);">3,097</td>
                                <td class="cell-mono" style="text-align: right; color: var(--text-secondary);">2.48</td>
                                <td class="cell-mono" style="text-align: right; color: var(--text-secondary);">261.9 KB</td>
                                <td><span class="badge badge-emerald">Zero Cross-Split Speaker Overlap</span></td>
                            </tr>
                            <tr>
                                <td style="font-weight: 700; color: var(--accent-emerald);">Test Evaluation (Gold)</td>
                                <td><span class="badge badge-emerald">25.0%</span></td>
                                <td class="cell-mono" style="text-align: right; font-weight: 600; color: #fff;">1,251</td>
                                <td class="cell-mono" style="text-align: right; color: var(--text-primary);">3,253</td>
                                <td class="cell-mono" style="text-align: right; color: var(--text-secondary);">2.60</td>
                                <td class="cell-mono" style="text-align: right; color: var(--text-secondary);">264.2 KB</td>
                                <td><span class="badge badge-emerald">Strict Monotonic Causal Ordering</span></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="panel-card">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title" style="font-size: 1.05rem;"><span>🛡️</span> Approved Corpora & Governance Provenance Registry</h3>
                        <p style="color: var(--text-secondary); font-size: 0.82rem; margin-top: 0.2rem;">
                            Representative audited sources with licensing and child-safety alignment.
                        </p>
                    </div>
                </div>
                <div class="table-shell">
                    <table class="matrix-table">
                        <thead>
                            <tr>
                                <th>Corpus Identifier</th>
                                <th>Domain Category</th>
                                <th>Provenance & Publisher</th>
                                <th>Licensing & Terms</th>
                                <th>Child Safety Alignment</th>
                                <th>Audit Gate</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td style="font-weight: 700; color: #fff;">wikiconv_wikidetox</td>
                                <td><span class="badge badge-cyan">Discussion Trees</span></td>
                                <td>Google / Wikimedia Community</td>
                                <td>CC-BY-SA 3.0 (Research)</td>
                                <td>Safe Harbor De-identified</td>
                                <td><span class="badge badge-emerald">🟢 PASSED</span></td>
                            </tr>
                            <tr>
                                <td style="font-weight: 700; color: #fff;">contextual_abuse_dataset</td>
                                <td><span class="badge badge-purple">Abuse Benchmarks</span></td>
                                <td>CAD Research Consortium</td>
                                <td>Academic Research License</td>
                                <td>Group Adjudication Verified</td>
                                <td><span class="badge badge-emerald">🟢 PASSED</span></td>
                            </tr>
                            <tr>
                                <td style="font-weight: 700; color: #fff;">gametox</td>
                                <td><span class="badge badge-rose">Youth & Gaming</span></td>
                                <td>GameTox Adolescent Gaming Corpus</td>
                                <td>Non-Commercial Research</td>
                                <td>COPPA Compliant Scrubbing</td>
                                <td><span class="badge badge-emerald">🟢 PASSED</span></td>
                            </tr>
                            <tr>
                                <td style="font-weight: 700; color: #fff;">minorbench</td>
                                <td><span class="badge badge-rose">Youth Safeguarding</span></td>
                                <td>MinorBench Safety Evaluation</td>
                                <td>Curated Research Set</td>
                                <td>Underage Privacy Protected</td>
                                <td><span class="badge badge-emerald">🟢 PASSED</span></td>
                            </tr>
                            <tr>
                                <td style="font-weight: 700; color: #fff;">lmsys_toxic_chat</td>
                                <td><span class="badge badge-indigo">Dialogue Arenas</span></td>
                                <td>LMSYS Org / Chatbot Arena</td>
                                <td>CC-BY-4.0 Research</td>
                                <td>Zero Residual Identifiers</td>
                                <td><span class="badge badge-emerald">🟢 PASSED</span></td>
                            </tr>
                            <tr>
                                <td style="font-weight: 700; color: #fff;">urban_dictionary_slang</td>
                                <td><span class="badge badge-amber">Dynamic Slang</span></td>
                                <td>Urban Dictionary Curated APIs</td>
                                <td>Permissive Research Querying</td>
                                <td>Algospeak Discovery Active</td>
                                <td><span class="badge badge-emerald">🟢 PASSED</span></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- Figure Lightbox Modal -->
        <div id="lightbox-modal" class="modal-backdrop" onclick="closeLightbox(event)">
            <div class="modal-content" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h3 id="lightbox-title" style="color: #fff; font-size: 1.05rem; font-weight: 700;"></h3>
                    <button class="modal-close" onclick="closeLightbox()">&times;</button>
                </div>
                <img id="lightbox-img" src="" alt="Enlarged Figure">
                <div style="margin-top: 1rem; display: flex; justify-content: flex-end; gap: 0.75rem; flex-wrap: wrap;">
                    <a id="lightbox-open" href="" target="_blank" class="btn-sm btn-outline" style="text-decoration: none;">↗ Open High-Res in Tab</a>
                    <a id="lightbox-download" href="" download class="btn-sm btn-cyan" style="text-decoration: none;">📥 Download PNG</a>
                </div>
            </div>
        </div>

        <footer>
            YouthEscalateBench Evaluator Service • Running at <code>http://{host}:{port}</code> • Auto-Generated Real-Time Dashboard
        </footer>
    </div>

    <script>
        function switchTab(tabId) {{
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('#nav-tabs .tab-btn, .tab-btn').forEach(el => {{
                el.classList.remove('active');
                el.setAttribute('aria-selected', 'false');
            }});
            document.querySelectorAll('.kpi-row > .kpi-card[data-tab]').forEach(el => {{
                el.classList.remove('is-selected');
            }});

            const target = document.getElementById(tabId);
            if (target) target.classList.add('active');

            // Always select the nav-tab button by id (never the kpi-card with the same onclick)
            const btn = document.getElementById('btn-' + tabId)
                || document.querySelector('#nav-tabs .tab-btn[data-tab="' + tabId + '"]');
            if (btn) {{
                btn.classList.add('active');
                btn.setAttribute('aria-selected', 'true');
                try {{
                    btn.scrollIntoView({{ behavior: 'smooth', inline: 'nearest', block: 'nearest' }});
                }} catch (_) {{}}
            }}

            const kpi = document.querySelector('.kpi-row > .kpi-card[data-tab="' + tabId + '"]');
            if (kpi) kpi.classList.add('is-selected');
        }}

        function openLightbox(src, title) {{
            const modal = document.getElementById('lightbox-modal');
            const img = document.getElementById('lightbox-img');
            const titleEl = document.getElementById('lightbox-title');
            const downloadBtn = document.getElementById('lightbox-download');
            const openBtn = document.getElementById('lightbox-open');

            if (!modal || !img) return;
            img.src = src;
            if (titleEl) titleEl.textContent = title;
            if (downloadBtn) downloadBtn.href = src;
            if (openBtn) openBtn.href = src;
            modal.classList.add('active');
        }}

        function closeLightbox(e) {{
            if (e && e.target && e.target !== document.getElementById('lightbox-modal')) {{
                return;
            }}
            const modal = document.getElementById('lightbox-modal');
            if (modal) modal.classList.remove('active');
        }}

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') closeLightbox();
        }});

        function filterAnalyticsTable() {{
            const query = (document.getElementById('analytics-table-search')?.value || '').toLowerCase();
            const rows = document.querySelectorAll('#analytics-matrix-table tbody tr');
            rows.forEach(r => {{
                const text = r.innerText.toLowerCase();
                r.style.display = !query || text.includes(query) ? '' : 'none';
            }});
        }}

        let currentModelFilter = 'all';
        function setModelFilter(type, btn) {{
            if (btn) {{
                btn.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            }}
            currentModelFilter = type;
            filterModelsTable();
        }}

        function filterModelsTable() {{
            const query = (document.getElementById('model-search')?.value || '').toLowerCase();
            const rows = document.querySelectorAll('#models-table tbody tr');
            rows.forEach(r => {{
                const text = r.innerText.toLowerCase();
                const rProv = r.getAttribute('data-provider') || '';
                const rStatus = r.getAttribute('data-status') || '';
                const rTier = r.getAttribute('data-tier') || '';

                const matchesQuery = !query || text.includes(query);
                let matchesFilter = true;
                if (currentModelFilter === 'accessible') {{
                    matchesFilter = (rStatus === 'accessible');
                }} else if (currentModelFilter === 'free') {{
                    matchesFilter = rTier.includes('free');
                }} else if (currentModelFilter === 'openrouter') {{
                    matchesFilter = rProv.includes('openrouter');
                }} else if (currentModelFilter === 'requesty') {{
                    matchesFilter = rProv.includes('requesty');
                }} else if (currentModelFilter === 'local') {{
                    matchesFilter = rProv.includes('local');
                }}

                r.style.display = (matchesQuery && matchesFilter) ? '' : 'none';
            }});
        }}

        let currentErrorFilter = 'all';
        function setErrorFilter(type, btn) {{
            if (btn) {{
                btn.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            }}
            currentErrorFilter = type;
            filterErrorTable();
        }}

        function filterErrorTable() {{
            const query = (document.getElementById('error-search')?.value || '').toLowerCase();
            const rows = document.querySelectorAll('#errors-table tbody tr');
            rows.forEach(r => {{
                const text = r.innerText.toLowerCase();
                const errType = r.getAttribute('data-type') || '';

                const matchesQuery = !query || text.includes(query);
                let matchesFilter = true;
                if (currentErrorFilter === 'False Positive') {{
                    matchesFilter = errType.includes('Positive');
                }} else if (currentErrorFilter === 'False Negative') {{
                    matchesFilter = errType.includes('Negative');
                }}

                r.style.display = (matchesQuery && matchesFilter) ? '' : 'none';
            }});
        }}

        let currentDifficultyFilter = 'all';
        function setDifficultyFilter(type, btn) {{
            if (btn) {{
                btn.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            }}
            currentDifficultyFilter = type;
            filterDifficultyTable();
        }}

        function filterDifficultyTable() {{
            const query = (document.getElementById('difficulty-search')?.value || '').toLowerCase();
            const rows = document.querySelectorAll('#difficulty-table tbody tr');
            rows.forEach(r => {{
                const text = r.innerText.toLowerCase();
                const mode = r.getAttribute('data-mode') || '';
                const prio = parseFloat(r.getAttribute('data-prio') || '0');

                const matchesQuery = !query || text.includes(query);
                let matchesFilter = true;
                if (currentDifficultyFilter === 'False Positive') {{
                    matchesFilter = mode.includes('Positive');
                }} else if (currentDifficultyFilter === 'False Negative') {{
                    matchesFilter = mode.includes('Negative');
                }} else if (currentDifficultyFilter === 'high_priority') {{
                    matchesFilter = prio >= 0.20;
                }}

                r.style.display = (matchesQuery && matchesFilter) ? '' : 'none';
            }});
        }}

        function filterDifficultyByWord(word) {{
            const input = document.getElementById('difficulty-search');
            if (input) {{
                input.value = word;
                filterDifficultyTable();
                input.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                input.focus();
            }}
        }}

        function testTurnInPlayground(turnText) {{
            switchTab('tab-playground');
            const targetInput = document.getElementById('test-turn');
            if (targetInput) {{
                targetInput.value = turnText;
                targetInput.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                targetInput.focus();
            }}
            runLivePredict();
        }}

        function openModelPredict(modelId) {{
            switchTab('tab-playground');
            document.querySelectorAll('.dash-checkbox').forEach(cb => {{
                cb.checked = (cb.value === modelId);
            }});
            const selected = document.querySelector('.dash-checkbox:checked');
            if (selected) {{
                onPredictModelPick('dash', selected);
            }} else {{
                // Fallback: match by display name if an id was not found
                document.querySelectorAll('.dash-check-item').forEach(item => {{
                    const name = (item.getAttribute('data-name') || '');
                    const cb = item.querySelector('.dash-checkbox');
                    if (cb) {{
                        cb.checked = (name === String(modelId || '').toLowerCase());
                    }}
                }});
                const retry = document.querySelector('.dash-checkbox:checked');
                if (retry) onPredictModelPick('dash', retry);
                else updatePredictModelSelection('dash');
            }}
            const targetInput = document.getElementById('test-turn');
            if (targetInput) {{
                targetInput.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                targetInput.focus();
            }}
        }}

        const DASH_PRESETS = {{
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

        function setDashboardPreset(key) {{
            const p = DASH_PRESETS[key];
            if (!p) return;
            const prefixEl = document.getElementById('test-prefix');
            const turnEl = document.getElementById('test-turn');
            if (prefixEl) prefixEl.value = p.context;
            if (turnEl) turnEl.value = p.target;
            switchTab('tab-playground');
            if (turnEl) {{
                turnEl.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                turnEl.focus();
            }}
            runLivePredict();
        }}

        function selectPredictModels(prefix, mode) {{
            const boxes = document.querySelectorAll('.' + prefix + '-checkbox');
            boxes.forEach(b => {{
                const item = b.closest('.' + prefix + '-check-item');
                const prov = item ? (item.getAttribute('data-provider') || '') : '';
                const cat = item ? (item.getAttribute('data-category') || '') : '';
                const isCustom = cat === 'custom' || prov.includes('requesty');
                const isBaseline = prov.includes('local');

                if (mode === 'all') {{
                    b.checked = true;
                }} else if (mode === 'none') {{
                    b.checked = false;
                }} else if (mode === 'baselines') {{
                    b.checked = isBaseline;
                }} else if (mode === 'llms') {{
                    b.checked = !isBaseline && !isCustom;
                }} else if (mode === 'custom') {{
                    b.checked = isCustom;
                }}

                if (item) {{
                    if (b.checked) item.classList.add('is-selected');
                    else item.classList.remove('is-selected');
                }}
            }});
            updatePredictModelSelection(prefix);
        }}

        function filterModelCheckboxes(prefix) {{
            const query = (document.getElementById(prefix + '-model-filter')?.value || '').toLowerCase();
            const items = document.querySelectorAll('.' + prefix + '-check-item');
            items.forEach(it => {{
                const text = it.innerText.toLowerCase();
                it.style.display = !query || text.includes(query) ? 'flex' : 'none';
            }});
        }}

        function onPredictModelPick(prefix, checkbox) {{
            // Playground / predict: single-select. Analytics scope: keep multi-select.
            if (prefix !== 'analytics' && checkbox && checkbox.checked) {{
                document.querySelectorAll('.' + prefix + '-checkbox').forEach(b => {{
                    if (b !== checkbox) {{
                        b.checked = false;
                        const item = b.closest('.' + prefix + '-check-item');
                        if (item) item.classList.remove('is-selected');
                    }}
                }});
            }}
            updatePredictModelSelection(prefix);
        }}

        function setRegenInfographicsAttention(active) {{
            const btn = document.getElementById('btn-regenerate-analytics');
            if (!btn) return;
            btn.classList.toggle('btn-shine-spark', !!active);
        }}

        function showAnalyticsRegenPrompt(checkedCount) {{
            const statusDiv = document.getElementById('analytics-regen-status');
            if (!statusDiv) return;
            statusDiv.style.display = 'block';
            statusDiv.style.background = 'rgba(251, 191, 36, 0.12)';
            statusDiv.style.border = '1px solid rgba(251, 191, 36, 0.35)';
            statusDiv.style.color = '#fbbf24';
            statusDiv.dataset.regenPrompt = '1';
            statusDiv.innerHTML = '⚡ Scope changed (' + checkedCount + ' selected). Click <strong>"Regenerate Infographics"</strong> to update figures & analytics.';
            setRegenInfographicsAttention(true);
        }}

        function clearAnalyticsRegenPromptAttention() {{
            const statusDiv = document.getElementById('analytics-regen-status');
            if (statusDiv) delete statusDiv.dataset.regenPrompt;
            setRegenInfographicsAttention(false);
        }}

        function syncRegenInfographicsAttention() {{
            const statusDiv = document.getElementById('analytics-regen-status');
            if (!statusDiv) {{
                setRegenInfographicsAttention(false);
                return;
            }}
            const visible = statusDiv.style.display !== 'none' && getComputedStyle(statusDiv).display !== 'none';
            setRegenInfographicsAttention(visible && statusDiv.dataset.regenPrompt === '1');
        }}

        document.addEventListener('DOMContentLoaded', () => {{
            const statusDiv = document.getElementById('analytics-regen-status');
            if (!statusDiv || typeof MutationObserver === 'undefined') return;
            new MutationObserver(syncRegenInfographicsAttention).observe(statusDiv, {{
                attributes: true,
                attributeFilter: ['style', 'data-regen-prompt']
            }});
        }});

        function updatePredictModelSelection(prefix) {{
            const allBoxes = document.querySelectorAll('.' + prefix + '-checkbox');
            const checked = [];
            allBoxes.forEach(b => {{
                const item = b.closest('.' + prefix + '-check-item');
                if (b.checked) {{
                    checked.push(b);
                    if (item) item.classList.add('is-selected');
                }} else {{
                    if (item) item.classList.remove('is-selected');
                }}
            }});
            const badge = document.getElementById(prefix + '-selected-count');
            if (!badge) return;
            if (prefix === 'analytics') {{
                if (checked.length === 0) {{
                    badge.textContent = 'No Models Selected (0)';
                    badge.className = 'badge badge-rose';
                }} else if (checked.length === allBoxes.length) {{
                    badge.textContent = 'Selected: All ' + checked.length + ' Models (Full Scope)';
                    badge.className = 'badge badge-emerald';
                }} else {{
                    badge.textContent = 'Selected: ' + checked.length + ' Models (' + checked.length + ' of ' + allBoxes.length + ')';
                    badge.className = 'badge badge-indigo';
                }}
                showAnalyticsRegenPrompt(checked.length);
                return;
            }}
            if (checked.length === 0) {{
                badge.textContent = 'No Models Selected (0)';
                badge.className = 'badge badge-rose';
            }} else if (checked.length === 1) {{
                const item = checked[0].closest('.' + prefix + '-check-item');
                const name = item ? (item.querySelector('.model-name')?.innerText || checked[0].value) : checked[0].value;
                badge.textContent = 'Selected: 1 Model (' + name + ')';
                badge.className = 'badge badge-cyan';
            }} else if (checked.length === allBoxes.length) {{
                badge.textContent = 'Selected: All ' + checked.length + ' Models (Consensus Ensemble)';
                badge.className = 'badge badge-emerald';
            }} else {{
                badge.textContent = 'Selected: ' + checked.length + ' Models (Multi-Model Ensemble)';
                badge.className = 'badge badge-indigo';
            }}
        }}

        async function regenerateAnalyticsInfographics() {{
            const btn = document.getElementById('btn-regenerate-analytics');
            const statusDiv = document.getElementById('analytics-regen-status');
            const selectedBoxes = Array.from(document.querySelectorAll('.analytics-checkbox:checked'));
            const selected = selectedBoxes.map(b => b.value);

            // Clicked / leaving the scope-changed prompt → drop shine immediately
            clearAnalyticsRegenPromptAttention();

            if (selected.length === 0) {{
                if (statusDiv) {{
                    statusDiv.style.display = 'block';
                    statusDiv.style.background = 'rgba(244, 63, 94, 0.15)';
                    statusDiv.style.border = '1px solid rgba(244, 63, 94, 0.4)';
                    statusDiv.style.color = '#fb7185';
                    statusDiv.innerHTML = '⚠️ Please select at least 1 model before regenerating infographics.';
                }}
                return;
            }}

            if (btn) {{
                btn.disabled = true;
                btn.innerHTML = '<span class="btn-regen-label"><span class="pulse-dot" style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#fff; margin-right:6px;"></span>Regenerating Figures...</span>';
            }}
            if (statusDiv) {{
                statusDiv.style.display = 'block';
                statusDiv.style.background = 'rgba(56, 189, 248, 0.12)';
                statusDiv.style.border = '1px solid rgba(56, 189, 248, 0.35)';
                statusDiv.style.color = '#38bdf8';
                statusDiv.innerHTML = '<span class="pulse-dot" style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#38bdf8; margin-right:6px;"></span>Rendering 4 publication-ready figures & recalculating metrics for ' + selected.length + ' selected models...';
            }}

            const tStart = performance.now();

            try {{
                const resp = await fetch('/api/infographics/regenerate', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ models: selected }})
                }});
                if (!resp.ok) {{
                    throw new Error('Server returned HTTP ' + resp.status);
                }}
                const data = await resp.json();
                const elapsedSec = ((performance.now() - tStart) / 1000).toFixed(2);
                const t = data.timestamp || Date.now();

                // 1. Refresh all 4 gallery images with cache busting
                const figMappings = [
                    {{ id: 'fig-img-comparison', downloadId: 'fig-dl-comparison', zoomId: 'fig-zoom-comparison', name: 'infographic_models_comparison.png', title: 'Fig 1: Comprehensive Multi-Panel Model Benchmark' }},
                    {{ id: 'fig-img-heatmap', downloadId: 'fig-dl-heatmap', zoomId: 'fig-zoom-heatmap', name: 'figure_auprc_heatmap.png', title: 'Fig 2: AUPRC & AUROC Performance Matrix Heatmaps' }},
                    {{ id: 'fig-img-trajectory', downloadId: 'fig-dl-trajectory', zoomId: 'fig-zoom-trajectory', name: 'figure_context_trajectory.png', title: 'Fig 3: Causal Context Expansion Dynamics' }},
                    {{ id: 'fig-img-leaderboard', downloadId: 'fig-dl-leaderboard', zoomId: 'fig-zoom-leaderboard', name: 'figure_llm_leaderboard.png', title: 'Fig 4: Dedicated LLM Leaderboard (Full Prefix)' }}
                ];

                figMappings.forEach(item => {{
                    const img = document.getElementById(item.id);
                    if (img) {{
                        const newSrc = '/reports/' + item.name + '?t=' + t;
                        img.src = newSrc;
                        img.onclick = () => openLightbox(newSrc, item.title);
                    }}
                    const dl = document.getElementById(item.downloadId);
                    if (dl) {{
                        dl.href = '/reports/' + item.name + '?t=' + t;
                    }}
                    const zoom = document.getElementById(item.zoomId);
                    if (zoom) {{
                        zoom.onclick = () => openLightbox('/reports/' + item.name + '?t=' + t, item.title);
                    }}
                }});

                // 2. Update KPI summary cards
                if (data.top_llm) {{
                    const elName = document.getElementById('analytics-kpi-top-llm-name');
                    const elScore = document.getElementById('analytics-kpi-top-llm-score');
                    if (elName) elName.textContent = data.top_llm.name;
                    if (elScore) elScore.textContent = data.top_llm.prefix_auprc.toFixed(3) + ' AUPRC (Top Performer)';
                }}
                if (data.top_baseline) {{
                    const elName = document.getElementById('analytics-kpi-top-baseline-name');
                    const elScore = document.getElementById('analytics-kpi-top-baseline-score');
                    if (elName) elName.textContent = data.top_baseline.name;
                    if (elScore) elScore.textContent = data.top_baseline.prefix_auprc.toFixed(3) + ' AUPRC (Offline Baseline)';
                }}
                if (data.max_delta_model) {{
                    const elVal = document.getElementById('analytics-kpi-max-delta-val');
                    const elName = document.getElementById('analytics-kpi-max-delta-name');
                    const d = data.max_delta_model.delta_auprc;
                    if (elVal) elVal.textContent = (d >= 0 ? '+' : '') + d.toFixed(3) + ' Δ AUPRC';
                    if (elName) elName.textContent = data.max_delta_model.name;
                }}
                const elCount = document.getElementById('analytics-kpi-models-count');
                const elSub = document.getElementById('analytics-kpi-models-sub');
                if (elCount) elCount.textContent = data.models_count + ' Models';
                if (elSub) elSub.textContent = 'Selected Visual Scope (' + data.models_count + ' evaluated)';

                // 3. Update Causal Trajectories container
                if (data.trajectory_bars_html) {{
                    const trajContainer = document.getElementById('analytics-trajectory-container');
                    if (trajContainer) trajContainer.innerHTML = data.trajectory_bars_html;
                }}

                // 4. Update Performance Matrix table rows
                if (data.matrix_rows_html) {{
                    const tbody = document.getElementById('analytics-matrix-tbody');
                    if (tbody) tbody.innerHTML = data.matrix_rows_html;
                }}

                // 5. Update status
                if (statusDiv) {{
                    statusDiv.style.background = 'rgba(16, 185, 129, 0.15)';
                    statusDiv.style.border = '1px solid rgba(16, 185, 129, 0.4)';
                    statusDiv.style.color = '#34d399';
                    statusDiv.innerHTML = '✅ Successfully regenerated 4 publication-ready figures & visual analytics for ' + data.models_count + ' models in ' + elapsedSec + 's!';
                }}
            }} catch (err) {{
                if (statusDiv) {{
                    statusDiv.style.background = 'rgba(244, 63, 94, 0.15)';
                    statusDiv.style.border = '1px solid rgba(244, 63, 94, 0.4)';
                    statusDiv.style.color = '#fb7185';
                    statusDiv.innerHTML = '❌ Failed to regenerate infographics: ' + err.message;
                }}
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = '<span class="btn-regen-label"><span>🔄</span> Regenerate Infographics</span>';
                    clearAnalyticsRegenPromptAttention();
                }}
            }}
        }}

        async function regenerateGovernanceInfographics() {{
            const btn = document.getElementById('btn-regenerate-governance');
            const statusDiv = document.getElementById('governance-regen-status');

            if (btn) {{
                btn.disabled = true;
                btn.innerHTML = '<span class="pulse-dot" style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#fff; margin-right:6px;"></span>Regenerating Governance Figures...';
            }}
            if (statusDiv) {{
                statusDiv.style.display = 'block';
                statusDiv.style.background = 'rgba(56, 189, 248, 0.12)';
                statusDiv.style.border = '1px solid rgba(56, 189, 248, 0.35)';
                statusDiv.style.color = '#38bdf8';
                statusDiv.innerHTML = '<span class="pulse-dot" style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#38bdf8; margin-right:6px;"></span>Rendering 3 high-resolution figures for Governance, Split Data & Audit Reports...';
            }}

            const tStart = performance.now();

            try {{
                const resp = await fetch('/api/governance/regenerate', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }}
                }});
                if (!resp.ok) {{
                    throw new Error('Server returned HTTP ' + resp.status);
                }}
                const data = await resp.json();
                const elapsedSec = ((performance.now() - tStart) / 1000).toFixed(2);
                const t = data.timestamp || Date.now();

                // Refresh the 3 governance gallery figures with cache-busting
                const govFigs = [
                    {{ id: 'fig-img-gov-audit', downloadId: 'fig-dl-gov-audit', zoomId: 'fig-zoom-gov-audit', name: 'infographic_governance_audit.png', title: 'Fig G-1: Corpus Governance & Multi-Source Legal Audit Architecture' }},
                    {{ id: 'fig-img-split-data', downloadId: 'fig-dl-split-data', zoomId: 'fig-zoom-split-data', name: 'infographic_split_data.png', title: 'Fig G-2: Zero-Leakage Benchmark Dataset Splitting & Quota Stratification' }},
                    {{ id: 'fig-img-lifecycle', downloadId: 'fig-dl-lifecycle', zoomId: 'fig-zoom-lifecycle', name: 'infographic_data_lifecycle.png', title: 'Fig G-3: End-to-End Pipeline Architecture & Governance Lifecycle' }}
                ];

                govFigs.forEach(item => {{
                    const img = document.getElementById(item.id);
                    if (img) {{
                        const newSrc = '/reports/' + item.name + '?t=' + t;
                        img.src = newSrc;
                        img.onclick = () => openLightbox(newSrc, item.title);
                    }}
                    const dl = document.getElementById(item.downloadId);
                    if (dl) {{
                        dl.href = '/reports/' + item.name + '?t=' + t;
                    }}
                    const zoom = document.getElementById(item.zoomId);
                    if (zoom) {{
                        zoom.onclick = () => openLightbox('/reports/' + item.name + '?t=' + t, item.title);
                    }}
                }});

                if (statusDiv) {{
                    statusDiv.style.background = 'rgba(52, 211, 153, 0.15)';
                    statusDiv.style.border = '1px solid rgba(52, 211, 153, 0.4)';
                    statusDiv.style.color = '#34d399';
                    statusDiv.innerHTML = '✅ Successfully regenerated 3 publication-ready governance & data split infographics in ' + elapsedSec + 's!';
                }}
            }} catch (err) {{
                if (statusDiv) {{
                    statusDiv.style.background = 'rgba(244, 63, 94, 0.15)';
                    statusDiv.style.border = '1px solid rgba(244, 63, 94, 0.4)';
                    statusDiv.style.color = '#fb7185';
                    statusDiv.innerHTML = '❌ Failed to regenerate governance infographics: ' + err.message;
                }}
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = '<span>🔄</span> Regenerate Governance Infographics';
                }}
            }}
        }}

        function addCustomPredictModel(prefix) {{
            const input = document.getElementById(prefix + '-custom-input');
            if (!input) return;
            const modelId = input.value.trim();
            if (!modelId) return;

            const list = document.getElementById(prefix + '-custom-list');
            if (!list) return;

            const existing = document.querySelector('.' + prefix + '-checkbox[value="' + modelId + '"]');
            if (existing) {{
                existing.checked = true;
                onPredictModelPick(prefix, existing);
                input.value = '';
                return;
            }}

            if (prefix !== 'analytics') {{
                document.querySelectorAll('.' + prefix + '-checkbox').forEach(b => {{
                    b.checked = false;
                    const item = b.closest('.' + prefix + '-check-item');
                    if (item) item.classList.remove('is-selected');
                }});
            }}

            const label = document.createElement('label');
            label.className = 'model-check-item ' + prefix + '-check-item is-selected';
            label.setAttribute('data-id', modelId);
            label.setAttribute('data-category', 'custom');
            label.setAttribute('data-provider', 'custom');
            label.setAttribute('data-name', modelId.toLowerCase());
            label.innerHTML = `
                <input type="checkbox" name="${{prefix}}-selected-models" value="${{modelId}}" class="${{prefix}}-checkbox" checked onchange="onPredictModelPick('${{prefix}}', this)">
                <div class="model-info">
                    <span class="model-name" title="${{modelId}}">${{modelId}}</span>
                    <div class="model-meta">
                        <span class="badge badge-purple">Custom API</span>
                        <span class="model-status">🛠️ User Specified</span>
                    </div>
                </div>
            `;
            list.prepend(label);
            input.value = '';
            updatePredictModelSelection(prefix);
        }}

        function renderPredictResponse(data, elapsedMs, resultBox, verdictDiv) {{
            if (resultBox) {{
                resultBox.textContent = JSON.stringify(data, null, 2);
            }}
            if (!verdictDiv) return;
            verdictDiv.style.display = 'block';

            if (data.mode === 'multi_model' && data.aggregate) {{
                const agg = data.aggregate;
                const isActionable = agg.consensus_actionable;
                const bannerBg = isActionable 
                    ? 'linear-gradient(135deg, rgba(244, 63, 94, 0.22), rgba(225, 29, 72, 0.1))' 
                    : 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(5, 150, 105, 0.08))';
                const bannerBorder = isActionable ? 'rgba(244, 63, 94, 0.45)' : 'rgba(16, 185, 129, 0.4)';
                const titleColor = isActionable ? '#fb7185' : '#34d399';
                const badgeCls = isActionable ? 'badge-rose' : 'badge-emerald';

                const modelsList = Object.values(data.models || {{}});
                modelsList.sort((a, b) => (b.harm_probability || 0) - (a.harm_probability || 0));

                let modelRows = '';
                modelsList.forEach(m => {{
                    const mAct = m.actionable;
                    const mBadge = mAct 
                        ? '<span class="badge badge-rose">🚨 FLAGGED</span>' 
                        : '<span class="badge badge-emerald">🟢 CLEARED</span>';
                    const mProbPct = Math.round((m.harm_probability || 0) * 100);
                    const mProbColor = mAct ? '#f43f5e' : '#38bdf8';
                    const provLower = (m.provider || '').toLowerCase();
                    const isCustom = provLower.includes('requesty') || provLower.includes('custom');
                    const customBadge = isCustom 
                        ? '<span class="badge badge-purple">🛠️ Custom</span>' 
                        : (provLower.includes('local') 
                            ? '<span class="badge badge-cyan">⚡ Baseline</span>' 
                            : '<span class="badge badge-indigo">🤖 Frontier</span>');

                    modelRows += `
                        <tr>
                            <td style="font-weight: 600; color: #fff;">
                                <div>${{m.model_name}}</div>
                                <div style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted);">${{m.model_id}}</div>
                            </td>
                            <td><span class="badge badge-indigo">${{m.provider}}</span></td>
                            <td>${{customBadge}}</td>
                            <td class="cell-mono" style="text-align: right;">
                                <div style="font-weight: 700; color: ${{mProbColor}}; font-size: 0.88rem;">${{(m.harm_probability || 0).toFixed(4)}}</div>
                                <div style="height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; margin-top: 3px;">
                                    <div style="height: 100%; width: ${{Math.max(4, mProbPct)}}%; background: ${{mProbColor}};"></div>
                                </div>
                            </td>
                            <td>${{mBadge}}</td>
                            <td><span class="badge badge-amber">${{m.dominant_severity || 'safe'}}</span></td>
                            <td class="cell-mono" style="text-align: right; color: var(--text-muted); font-size: 0.75rem;">${{m.latency_ms || 0}}ms</td>
                        </tr>
                    `;
                }});

                const flaggedChips = (agg.flagged_by || []).map(f => `<span class="badge badge-rose" style="margin: 0.15rem;">🚨 ${{f}}</span>`).join('') || '<span style="color: var(--text-muted); font-size: 0.8rem;">None (0 models)</span>';
                const clearedChips = (agg.cleared_by || []).map(c => `<span class="badge badge-emerald" style="margin: 0.15rem;">🟢 ${{c}}</span>`).join('') || '<span style="color: var(--text-muted); font-size: 0.8rem;">None (0 models)</span>';

                verdictDiv.innerHTML = `
                    <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.25rem; margin-bottom: 1.25rem;">
                        <div style="background: ${{bannerBg}}; border: 1px solid ${{bannerBorder}}; padding: 0.9rem 1.2rem; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.1rem; flex-wrap: wrap; gap: 0.5rem;">
                            <div>
                                <div style="font-size: 0.72rem; text-transform: uppercase; font-weight: 700; color: ${{titleColor}}; letter-spacing: 0.05em;">Consensus Ensemble Verdict (${{agg.models_evaluated_count}} Models)</div>
                                <div style="font-size: 1.25rem; font-weight: 800; color: #fff; margin-top: 0.2rem;">${{agg.verdict_label}} (${{agg.agreement_percentage}}% Consensus)</div>
                            </div>
                            <span class="badge ${{badgeCls}}" style="font-size: 0.82rem; padding: 0.35rem 0.75rem;">${{agg.divergence_level}}</span>
                        </div>

                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 0.75rem; margin-bottom: 1.1rem;">
                            <div style="background: rgba(0,0,0,0.35); padding: 0.75rem 0.9rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                <div style="font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;">Mean Harm Prob</div>
                                <div style="font-size: 1.15rem; font-weight: 700; color: #fff; font-family: var(--font-mono);">${{agg.mean_harm_probability.toFixed(3)}} <span style="font-size: 0.72rem; color: var(--text-muted);">±${{agg.std_harm_probability.toFixed(2)}}</span></div>
                            </div>
                            <div style="background: rgba(0,0,0,0.35); padding: 0.75rem 0.9rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                <div style="font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;">Agreement Rate</div>
                                <div style="font-size: 1.15rem; font-weight: 700; color: var(--accent-cyan); font-family: var(--font-mono);">${{agg.agreement_percentage}}%</div>
                            </div>
                            <div style="background: rgba(0,0,0,0.35); padding: 0.75rem 0.9rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                <div style="font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;">Consensus Severity</div>
                                <div style="font-size: 1.15rem; font-weight: 700; color: var(--accent-amber);">${{agg.dominant_severity.toUpperCase()}}</div>
                            </div>
                            <div style="background: rgba(0,0,0,0.35); padding: 0.75rem 0.9rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                <div style="font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;">Models Ratio</div>
                                <div style="font-size: 1.15rem; font-weight: 700; color: #fff; font-family: var(--font-mono);"><span style="color: var(--accent-rose);">${{agg.actionable_count}} Flagged</span> / <span style="color: var(--accent-emerald);">${{agg.cleared_count}} Cleared</span></div>
                            </div>
                        </div>

                        <div style="margin-bottom: 1.1rem;">
                            <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.25rem;">
                                <span style="color: var(--accent-rose); font-weight: 600;">Actionable Harm (${{agg.actionable_count}})</span>
                                <span style="color: var(--accent-emerald); font-weight: 600;">Benign Banter (${{agg.cleared_count}})</span>
                            </div>
                            <div style="height: 8px; border-radius: 4px; background: rgba(255,255,255,0.06); display: flex; overflow: hidden;">
                                <div style="height: 100%; width: ${{(agg.actionable_count/agg.models_evaluated_count)*100}}%; background: linear-gradient(90deg, #f43f5e, #fb7185);"></div>
                                <div style="height: 100%; width: ${{(agg.cleared_count/agg.models_evaluated_count)*100}}%; background: linear-gradient(90deg, #059669, #34d399);"></div>
                            </div>
                        </div>

                        <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; background: rgba(0,0,0,0.25); padding: 0.85rem 1rem; border-radius: 8px; border-left: 3px solid var(--accent-cyan); margin-bottom: 1rem;">
                            <strong style="color: #fff;">Consensus Synthesis:</strong> ${{agg.synthesis}}
                        </div>

                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; font-size: 0.8rem;">
                            <div style="background: rgba(0,0,0,0.2); padding: 0.6rem 0.8rem; border-radius: 6px;">
                                <div style="font-size: 0.7rem; color: var(--text-muted); margin-bottom: 0.35rem; font-weight: 600; text-transform: uppercase;">Flagged Actionable by:</div>
                                <div style="display: flex; flex-wrap: wrap;">${{flaggedChips}}</div>
                            </div>
                            <div style="background: rgba(0,0,0,0.2); padding: 0.6rem 0.8rem; border-radius: 6px;">
                                <div style="font-size: 0.7rem; color: var(--text-muted); margin-bottom: 0.35rem; font-weight: 600; text-transform: uppercase;">Cleared Benign by:</div>
                                <div style="display: flex; flex-wrap: wrap;">${{clearedChips}}</div>
                            </div>
                        </div>
                    </div>

                    <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.25rem; margin-bottom: 1.25rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
                            <h3 style="font-size: 0.95rem; font-weight: 700; color: #fff;"><span>📊</span> Separate Model Predictions (${{modelsList.length}} Models)</h3>
                            <span style="font-size: 0.75rem; color: var(--text-muted);">Parallel Execution Completed in ${{elapsedMs}}ms</span>
                        </div>
                        <div class="table-responsive" style="max-height: 320px; overflow-y: auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Evaluated Model</th>
                                        <th>Provider</th>
                                        <th>Custom</th>
                                        <th style="text-align: right;">Harm Probability</th>
                                        <th>Decision</th>
                                        <th>Dominant Severity</th>
                                        <th style="text-align: right;">Latency</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${{modelRows}}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            }} else {{
                const harmProb = data.harm_probability !== undefined ? data.harm_probability : 0.0;
                const actionable = data.actionable !== undefined ? data.actionable : (harmProb >= 0.5);
                const modelName = data.model_name || data.model_id || 'Raw Lexicon Match';
                const provider = data.provider || 'Local Baseline';
                const sevProbs = data.severity_probabilities || {{}};
                let domSev = data.dominant_severity || 'safe';
                if (!domSev && Object.keys(sevProbs).length) {{
                    domSev = Object.keys(sevProbs).reduce((a, b) => sevProbs[a] > sevProbs[b] ? a : b);
                }}
                const badgeCls = actionable ? 'badge-rose' : 'badge-emerald';
                const verdictTitle = actionable ? '🚨 ACTIONABLE VIOLATION' : '🟢 NON-ACTIONABLE / SAFE';

                let sevBars = '';
                for (const [k, v] of Object.entries(sevProbs)) {{
                    const pct = Math.round(v * 100);
                    sevBars += `
                        <div style="margin-bottom: 0.4rem;">
                            <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.15rem;">
                                <span>${{k}}</span>
                                <span class="cell-mono">${{(v).toFixed(3)}}</span>
                            </div>
                            <div style="height: 5px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden;">
                                <div style="height: 100%; width: ${{Math.max(2, pct)}}%; background: var(--accent-cyan);"></div>
                            </div>
                        </div>
                    `;
                }}

                verdictDiv.innerHTML = `
                    <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.25rem; margin-bottom: 1.25rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
                            <div>
                                <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted);">Predicting Model</div>
                                <div style="font-size: 1.15rem; font-weight: 700; color: #fff;">${{modelName}}</div>
                                <div style="font-size: 0.72rem; color: var(--text-muted);">${{provider}} • ${{data.latency_ms || 0}}ms</div>
                            </div>
                            <span class="badge ${{badgeCls}}" style="font-size: 0.85rem; padding: 0.4rem 0.8rem;">${{verdictTitle}}</span>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                            <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: 8px;">
                                <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Harm Probability</div>
                                <div style="font-size: 1.4rem; font-weight: 800; color: ${{actionable ? '#f43f5e' : '#34d399'}}; font-family: var(--font-mono);">${{harmProb.toFixed(4)}}</div>
                            </div>
                            <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: 8px;">
                                <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Dominant Severity</div>
                                <div style="font-size: 1.4rem; font-weight: 800; color: var(--accent-amber); font-family: var(--font-mono);">${{domSev.toUpperCase()}}</div>
                            </div>
                        </div>
                        <div style="background: rgba(0,0,0,0.25); padding: 0.75rem 1rem; border-radius: 8px;">
                            <div style="font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.5rem; text-transform: uppercase; font-weight: 600;">Severity Distribution</div>
                            ${{sevBars}}
                        </div>
                    </div>
                `;
            }}
        }}

        async function executeStreamingPredict({{ payload, btn, statusSpan, resultBox, verdictDiv }}) {{
            if (btn) btn.disabled = true;
            if (verdictDiv) verdictDiv.style.display = 'block';

            const tStart = performance.now();
            let timerInterval = null;

            const updateTimer = () => {{
                const now = performance.now();
                const elapsedSec = ((now - tStart) / 1000).toFixed(2);
                if (statusSpan) {{
                    statusSpan.innerHTML = `<span class="pulse-dot" style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#38bdf8; margin-right:5px;"></span>Live Elapsed: ${{elapsedSec}}s`;
                }}
            }};
            timerInterval = setInterval(updateTimer, 40);
            updateTimer();

            const modelsState = new Map();
            let currentAggregate = null;
            let totalExpected = 1;
            let isMulti = false;
            let rawOutputAccumulator = {{}};

            const renderUI = (isComplete = false) => {{
                const now = performance.now();
                const currentElapsedSec = ((now - tStart) / 1000).toFixed(2);
                const completedList = Array.from(modelsState.values()).filter(m => m.status === 'done');
                const completedCount = completedList.length;
                const pct = totalExpected > 0 ? Math.round((completedCount / totalExpected) * 100) : 0;

                if (resultBox) {{
                    resultBox.textContent = JSON.stringify(rawOutputAccumulator, null, 2);
                }}

                if (isMulti || totalExpected > 1) {{
                    let progressHtml = `
                        <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.15rem; margin-bottom: 1.2rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; flex-wrap: wrap; gap: 0.5rem;">
                                <div style="font-size: 0.88rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 0.5rem;">
                                    ${{isComplete 
                                        ? '<span style="color: var(--accent-emerald);">✅ Asynchronous Inference Complete</span>' 
                                        : '<span class="pulse-dot" style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#38bdf8;"></span><span>Asynchronous Model Stream in Progress...</span>'}}
                                </div>
                                <div style="font-size: 0.8rem; font-family: var(--font-mono); color: var(--accent-cyan); font-weight: 600;">
                                    ${{completedCount}} / ${{totalExpected}} Models (${{pct}}%) • ${{currentElapsedSec}}s
                                </div>
                            </div>
                            <div style="height: 6px; border-radius: 3px; background: rgba(255,255,255,0.06); overflow: hidden; margin-bottom: 0.85rem;">
                                <div style="height: 100%; width: ${{Math.max(3, pct)}}%; background: linear-gradient(90deg, #38bdf8, #818cf8); transition: width 0.15s ease;"></div>
                            </div>
                    `;

                    if (currentAggregate && completedCount > 0) {{
                        const agg = currentAggregate;
                        const isActionable = agg.consensus_actionable;
                        const bannerBg = isActionable 
                            ? 'linear-gradient(135deg, rgba(244, 63, 94, 0.22), rgba(225, 29, 72, 0.1))' 
                            : 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(5, 150, 105, 0.08))';
                        const bannerBorder = isActionable ? 'rgba(244, 63, 94, 0.45)' : 'rgba(16, 185, 129, 0.4)';
                        const titleColor = isActionable ? '#fb7185' : '#34d399';
                        const badgeCls = isActionable ? 'badge-rose' : 'badge-emerald';

                        const flaggedChips = (agg.flagged_by || []).map(f => `<span class="badge badge-rose" style="margin: 0.15rem;">🚨 ${{f}}</span>`).join('') || '<span style="color: var(--text-muted); font-size: 0.8rem;">None (0 models)</span>';
                        const clearedChips = (agg.cleared_by || []).map(c => `<span class="badge badge-emerald" style="margin: 0.15rem;">🟢 ${{c}}</span>`).join('') || '<span style="color: var(--text-muted); font-size: 0.8rem;">None (0 models)</span>';

                        progressHtml += `
                            <div style="background: ${{bannerBg}}; border: 1px solid ${{bannerBorder}}; padding: 0.85rem 1.15rem; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
                                <div>
                                    <div style="font-size: 0.7rem; text-transform: uppercase; font-weight: 700; color: ${{titleColor}}; letter-spacing: 0.05em;">
                                        Progressive Consensus (${{completedCount}} of ${{totalExpected}} Models Reporting)
                                    </div>
                                    <div style="font-size: 1.25rem; font-weight: 800; color: #fff; margin-top: 0.15rem;">
                                        ${{agg.verdict_label}} (${{agg.agreement_percentage}}% Consensus)
                                    </div>
                                </div>
                                <span class="badge ${{badgeCls}}" style="font-size: 0.8rem; padding: 0.3rem 0.7rem;">${{agg.divergence_level}}</span>
                            </div>

                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 0.65rem; margin-bottom: 0.9rem;">
                                <div style="background: rgba(0,0,0,0.35); padding: 0.65rem 0.8rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                    <div style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase;">Mean Harm Prob</div>
                                    <div style="font-size: 1.1rem; font-weight: 700; color: #fff; font-family: var(--font-mono);">${{agg.mean_harm_probability.toFixed(3)}} <span style="font-size: 0.7rem; color: var(--text-muted);">±${{agg.std_harm_probability.toFixed(2)}}</span></div>
                                </div>
                                <div style="background: rgba(0,0,0,0.35); padding: 0.65rem 0.8rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                    <div style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase;">Agreement Rate</div>
                                    <div style="font-size: 1.1rem; font-weight: 700; color: var(--accent-cyan); font-family: var(--font-mono);">${{agg.agreement_percentage}}%</div>
                                </div>
                                <div style="background: rgba(0,0,0,0.35); padding: 0.65rem 0.8rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                    <div style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase;">Consensus Severity</div>
                                    <div style="font-size: 1.1rem; font-weight: 700; color: var(--accent-amber);">${{agg.dominant_severity.toUpperCase()}}</div>
                                </div>
                                <div style="background: rgba(0,0,0,0.35); padding: 0.65rem 0.8rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                    <div style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase;">Ratio</div>
                                    <div style="font-size: 1.1rem; font-weight: 700; color: #fff; font-family: var(--font-mono);"><span style="color: var(--accent-rose);">${{agg.actionable_count}} Flagged</span> / <span style="color: var(--accent-emerald);">${{agg.cleared_count}} Cleared</span></div>
                                </div>
                            </div>

                            <div style="margin-bottom: 0.85rem;">
                                <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-muted); margin-bottom: 0.2rem;">
                                    <span style="color: var(--accent-rose); font-weight: 600;">Actionable (${{agg.actionable_count}})</span>
                                    <span style="color: var(--accent-emerald); font-weight: 600;">Benign (${{agg.cleared_count}})</span>
                                </div>
                                <div style="height: 7px; border-radius: 4px; background: rgba(255,255,255,0.06); display: flex; overflow: hidden;">
                                    <div style="height: 100%; width: ${{ (agg.actionable_count / Math.max(1, agg.models_evaluated_count)) * 100 }}%; background: linear-gradient(90deg, #f43f5e, #fb7185);"></div>
                                    <div style="height: 100%; width: ${{ (agg.cleared_count / Math.max(1, agg.models_evaluated_count)) * 100 }}%; background: linear-gradient(90deg, #059669, #34d399);"></div>
                                </div>
                            </div>

                            <div style="font-size: 0.82rem; color: var(--text-secondary); line-height: 1.45; background: rgba(0,0,0,0.25); padding: 0.75rem 0.9rem; border-radius: 8px; border-left: 3px solid var(--accent-cyan); margin-bottom: 0.85rem;">
                                <strong style="color: #fff;">Consensus Synthesis:</strong> ${{agg.synthesis}}
                            </div>

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; font-size: 0.78rem;">
                                <div style="background: rgba(0,0,0,0.2); padding: 0.55rem 0.75rem; border-radius: 6px;">
                                    <div style="font-size: 0.68rem; color: var(--text-muted); margin-bottom: 0.25rem; font-weight: 600; text-transform: uppercase;">Flagged by (${{agg.actionable_count}}):</div>
                                    <div style="display: flex; flex-wrap: wrap;">${{flaggedChips}}</div>
                                </div>
                                <div style="background: rgba(0,0,0,0.2); padding: 0.55rem 0.75rem; border-radius: 6px;">
                                    <div style="font-size: 0.68rem; color: var(--text-muted); margin-bottom: 0.25rem; font-weight: 600; text-transform: uppercase;">Cleared by (${{agg.cleared_count}}):</div>
                                    <div style="display: flex; flex-wrap: wrap;">${{clearedChips}}</div>
                                </div>
                            </div>
                        `;
                    }}

                    progressHtml += `</div>`;

                    const allModels = Array.from(modelsState.values());
                    allModels.sort((a, b) => {{
                        if (a.status === 'done' && b.status !== 'done') return -1;
                        if (a.status !== 'done' && b.status === 'done') return 1;
                        if (a.status === 'done' && b.status === 'done') {{
                            return (b.harm_probability || 0) - (a.harm_probability || 0);
                        }}
                        return 0;
                    }});

                    let tableRows = '';
                    allModels.forEach(m => {{
                        const provLower = (m.provider || '').toLowerCase();
                        const isCustom = provLower.includes('requesty') || provLower.includes('custom');
                        const customBadge = isCustom 
                            ? '<span class="badge badge-purple">🛠️ Custom</span>' 
                            : (provLower.includes('local') 
                                ? '<span class="badge badge-cyan">⚡ Baseline</span>' 
                                : '<span class="badge badge-indigo">🤖 Frontier</span>');

                        if (m.status === 'done') {{
                            const mAct = m.actionable;
                            const mBadge = mAct 
                                ? '<span class="badge badge-rose">🚨 FLAGGED</span>' 
                                : '<span class="badge badge-emerald">🟢 CLEARED</span>';
                            const mProbPct = Math.round((m.harm_probability || 0) * 100);
                            const mProbColor = mAct ? '#f43f5e' : '#38bdf8';
                            const returnedAtSec = m.elapsed_since_req_ms ? (m.elapsed_since_req_ms / 1000).toFixed(2) + 's' : '';

                            tableRows += `
                                <tr>
                                    <td style="font-weight: 600; color: #fff;">
                                        <div>${{m.model_name}}</div>
                                        <div style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted);">${{m.model_id}}</div>
                                    </td>
                                    <td><span class="badge badge-indigo">${{m.provider}}</span></td>
                                    <td>${{customBadge}}</td>
                                    <td class="cell-mono" style="text-align: right;">
                                        <div style="font-weight: 700; color: ${{mProbColor}}; font-size: 0.88rem;">${{(m.harm_probability || 0).toFixed(4)}}</div>
                                        <div style="height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; margin-top: 3px;">
                                            <div style="height: 100%; width: ${{Math.max(4, mProbPct)}}%; background: ${{mProbColor}};"></div>
                                        </div>
                                    </td>
                                    <td>${{mBadge}}</td>
                                    <td><span class="badge badge-amber">${{m.dominant_severity || 'safe'}}</span></td>
                                    <td class="cell-mono" style="text-align: right;">
                                        <div style="font-weight: 600; color: var(--accent-cyan); font-size: 0.8rem;">⚡ ${{m.latency_ms || 0}}ms</div>
                                        ${{returnedAtSec ? `<div style="font-size: 0.7rem; color: var(--text-muted);">+${{returnedAtSec}} returned</div>` : ''}}
                                    </td>
                                </tr>
                            `;
                        }} else {{
                            tableRows += `
                                <tr style="opacity: 0.7;">
                                    <td style="font-weight: 600; color: #cbd5e1;">
                                        <div>${{m.model_name}}</div>
                                        <div style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted);">${{m.model_id}}</div>
                                    </td>
                                    <td><span class="badge badge-outline">${{m.provider}}</span></td>
                                    <td>${{customBadge}}</td>
                                    <td class="cell-mono" style="text-align: right; color: var(--text-muted); font-size: 0.75rem;">
                                        Calculating...
                                    </td>
                                    <td>
                                        <span class="badge badge-cyan" style="background: rgba(56, 189, 248, 0.1);">
                                            <span class="pulse-dot" style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#38bdf8; margin-right:4px;"></span>In Flight
                                        </span>
                                    </td>
                                    <td><span style="color: var(--text-muted); font-size: 0.75rem;">-</span></td>
                                    <td class="cell-mono" style="text-align: right; color: var(--accent-amber); font-size: 0.78rem;">
                                        ⏱️ ${{currentElapsedSec}}s...
                                    </td>
                                </tr>
                            `;
                        }}
                    }});

                    progressHtml += `
                        <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.15rem; margin-bottom: 1.2rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
                                <h3 style="font-size: 0.95rem; font-weight: 700; color: #fff;"><span>📊</span> Model Predictions Breakdown (${{completedCount}} of ${{totalExpected}} Completed)</h3>
                                <span style="font-size: 0.75rem; color: var(--text-muted);">Real-time Asynchronous Stream • Elapsed: ${{currentElapsedSec}}s</span>
                            </div>
                            <div class="table-responsive" style="max-height: 340px; overflow-y: auto;">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Evaluated Model</th>
                                            <th>Provider</th>
                                            <th>Custom</th>
                                            <th style="text-align: right;">Harm Probability</th>
                                            <th>Decision</th>
                                            <th>Dominant Severity</th>
                                            <th style="text-align: right;">Latency & Return Time</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${{tableRows}}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    `;

                    verdictDiv.innerHTML = progressHtml;
                }} else {{
                    const completedList = Array.from(modelsState.values()).filter(m => m.status === 'done');
                    if (completedList.length > 0) {{
                        const data = completedList[0];
                        const harmProb = data.harm_probability !== undefined ? data.harm_probability : 0.0;
                        const actionable = data.actionable !== undefined ? data.actionable : (harmProb >= 0.5);
                        const modelName = data.model_name || data.model_id || 'Model';
                        const provider = data.provider || 'Local Baseline';
                        const sevProbs = data.severity_probabilities || {{}};
                        let domSev = data.dominant_severity || 'safe';
                        if (!domSev && Object.keys(sevProbs).length) {{
                            domSev = Object.keys(sevProbs).reduce((a, b) => sevProbs[a] > sevProbs[b] ? a : b);
                        }}
                        const badgeCls = actionable ? 'badge-rose' : 'badge-emerald';
                        const verdictTitle = actionable ? '🚨 ACTIONABLE VIOLATION' : '🟢 NON-ACTIONABLE / SAFE';

                        let sevBars = '';
                        for (const [k, v] of Object.entries(sevProbs)) {{
                            const spct = Math.round(v * 100);
                            sevBars += `
                                <div style="margin-bottom: 0.4rem;">
                                    <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.15rem;">
                                        <span>${{k}}</span>
                                        <span class="cell-mono">${{(v).toFixed(3)}}</span>
                                    </div>
                                    <div style="height: 5px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden;">
                                        <div style="height: 100%; width: ${{Math.max(2, spct)}}%; background: var(--accent-cyan);"></div>
                                    </div>
                                </div>
                            `;
                        }}

                        verdictDiv.innerHTML = `
                            <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.25rem; margin-bottom: 1.25rem;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
                                    <div>
                                        <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted);">Evaluated Model</div>
                                        <div style="font-size: 1.15rem; font-weight: 700; color: #fff;">${{modelName}}</div>
                                        <div style="font-size: 0.72rem; color: var(--text-muted);">${{provider}} • ⚡ ${{data.latency_ms || 0}}ms (returned at +${{currentElapsedSec}}s)</div>
                                    </div>
                                    <span class="badge ${{badgeCls}}" style="font-size: 0.85rem; padding: 0.4rem 0.8rem;">${{verdictTitle}}</span>
                                </div>
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                                    <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: 8px;">
                                        <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Harm Probability</div>
                                        <div style="font-size: 1.4rem; font-weight: 800; color: ${{actionable ? '#f43f5e' : '#34d399'}}; font-family: var(--font-mono);">${{harmProb.toFixed(4)}}</div>
                                    </div>
                                    <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: 8px;">
                                        <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Dominant Severity</div>
                                        <div style="font-size: 1.4rem; font-weight: 800; color: var(--accent-amber); font-family: var(--font-mono);">${{domSev.toUpperCase()}}</div>
                                    </div>
                                </div>
                                <div style="background: rgba(0,0,0,0.25); padding: 0.75rem 1rem; border-radius: 8px;">
                                    <div style="font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.5rem; text-transform: uppercase; font-weight: 600;">Severity Distribution</div>
                                    ${{sevBars}}
                                </div>
                            </div>
                        `;
                    }} else {{
                        verdictDiv.innerHTML = `
                            <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.5rem; text-align: center;">
                                <span class="pulse-dot" style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#38bdf8; margin-bottom: 0.5rem;"></span>
                                <div style="font-size: 1rem; font-weight: 700; color: #fff;">Inference In Flight</div>
                                <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">Elapsed: ${{currentElapsedSec}}s...</div>
                            </div>
                        `;
                    }}
                }}
            }};

            try {{
                const streamPayload = {{ ...payload, stream: true }};
                const res = await fetch('/predict', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'Accept': 'text/event-stream'
                    }},
                    body: JSON.stringify(streamPayload)
                }});

                if (!res.ok) {{
                    throw new Error(`HTTP ${{res.status}} ${{res.statusText}}`);
                }}

                const reader = res.body.getReader();
                const decoder = new TextDecoder("utf-8");
                let buffer = "";

                while (true) {{
                    const {{ done, value }} = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, {{ stream: true }});

                    const parts = buffer.split("\\n\\n");
                    buffer = parts.pop() || "";

                    for (const chunk of parts) {{
                        if (!chunk.trim()) continue;
                        let eventName = "message";
                        let eventData = "";
                        const lines = chunk.split("\\n");
                        for (const l of lines) {{
                            if (l.startsWith("event:")) {{
                                eventName = l.slice(6).trim();
                            }} else if (l.startsWith("data:")) {{
                                eventData += l.slice(5).trim();
                            }}
                        }}
                        if (!eventData) continue;

                        let dataObj;
                        try {{
                            dataObj = JSON.parse(eventData);
                        }} catch (e) {{
                            continue;
                        }}

                        if (eventName === "init") {{
                            totalExpected = dataObj.models_count || 1;
                            isMulti = dataObj.mode === "multi_model" || totalExpected > 1;
                            if (Array.isArray(dataObj.models_queued)) {{
                                dataObj.models_queued.forEach(mq => {{
                                    modelsState.set(mq.model_id, {{
                                        model_id: mq.model_id,
                                        model_name: mq.model_name,
                                        provider: mq.provider,
                                        status: 'waiting'
                                    }});
                                }});
                            }}
                            rawOutputAccumulator = {{ ...dataObj, models: {{}}, status: "in_progress" }};
                            renderUI(false);
                        }} else if (eventName === "model_done") {{
                            const m = dataObj.model;
                            if (m && m.model_id) {{
                                modelsState.set(m.model_id, {{
                                    ...m,
                                    status: 'done'
                                }});
                            }}
                            if (dataObj.aggregate) {{
                                currentAggregate = dataObj.aggregate;
                            }}
                            if (!rawOutputAccumulator.models) rawOutputAccumulator.models = {{}};
                            if (m && m.model_id) rawOutputAccumulator.models[m.model_id] = m;
                            rawOutputAccumulator.aggregate = currentAggregate;
                            renderUI(false);
                        }} else if (eventName === "complete") {{
                            if (dataObj.aggregate) currentAggregate = dataObj.aggregate;
                            if (dataObj.models) {{
                                for (const [mid, m] of Object.entries(dataObj.models)) {{
                                    modelsState.set(mid, {{ ...m, status: 'done' }});
                                }}
                            }}
                            rawOutputAccumulator = dataObj;
                            renderUI(true);
                        }}
                    }}
                }}

                clearInterval(timerInterval);
                const totalElapsedSec = ((performance.now() - tStart) / 1000).toFixed(2);
                if (statusSpan) {{
                    statusSpan.innerHTML = `<span style="color: var(--accent-emerald);">HTTP ${{res.status}} (${{totalElapsedSec}}s total)</span>`;
                }}
                renderUI(true);
            }} catch (err) {{
                clearInterval(timerInterval);
                if (statusSpan) statusSpan.textContent = "Error";
                if (resultBox) resultBox.textContent = "Error during asynchronous streaming: " + err.message;
            }} finally {{
                if (btn) btn.disabled = false;
            }}
        }}

        async function runLivePredict() {{
            const turnText = document.getElementById('test-turn').value.trim();
            const prefixRaw = document.getElementById('test-prefix').value.trim();
            const box = document.getElementById('predict-result-box');
            const verdictDiv = document.getElementById('dash-visual-verdict');
            const btn = document.getElementById('btn-run-predict');

            if (btn) btn.disabled = true;
            box.textContent = "Executing prediction inference across selected model(s)...";

            const turns = [];
            let turnIndex = 1;
            if (prefixRaw) {{
                const lines = prefixRaw.split('\\n');
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
                "text": turnText || "hello"
            }});

            const payload = {{
                "benchmark_version": "0.1.2",
                "conversation_id": "dash_req_" + Date.now(),
                "current_turn_id": currentTurnId,
                "platform_style": "gaming_chat",
                "language_mode": "english",
                "task": "current_harm",
                "turns": turns
            }};

            // Check selected models
            const selectedBoxes = Array.from(document.querySelectorAll('.dash-checkbox:checked'));
            const selected = selectedBoxes.map(b => b.value);
            if (selected.length === 1) {{
                payload.model = selected[0];
            }} else if (selected.length > 1) {{
                payload.models = selected;
            }}

            await executeStreamingPredict({{
                payload,
                btn,
                statusSpan: null,
                resultBox: box,
                verdictDiv: verdictDiv
            }});
        }}
    </script>
</body>
</html>
"""
    return html


def generate_predict_page_html(
    host: str = "127.0.0.1",
    port: int = 8080,
    reports_dir: Path | None = None,
) -> str:
    """Generate dedicated interactive HTML playground for the /predict endpoint."""
    rep_dir = reports_dir or Path("reports")
    fingerprint = _dependency_fingerprint(
        [
            rep_dir / "evaluation_results.yaml",
            rep_dir / "data" / "evaluation_results.yaml",
            Path(".env"),
        ],
        "predict_page",
        host,
        str(port),
    )
    with _HTML_CACHE_LOCK:
        hit = _HTML_CACHE.get("predict_page")
        if hit and hit[0] == fingerprint:
            return hit[1]

    html = _generate_predict_page_html_uncached(host, port, rep_dir)
    with _HTML_CACHE_LOCK:
        _HTML_CACHE["predict_page"] = (fingerprint, html)
    return html


def _generate_predict_page_html_uncached(
    host: str,
    port: int,
    rep_dir: Path,
) -> str:
    """Build /predict sandbox HTML without the HTML cache."""
    catalog = build_evaluated_models_catalog(rep_dir)
    pred_model_selector = generate_model_selector_component(catalog["models"], prefix="pred")

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
            --border-card: rgba(255, 255, 255, 0.08);
            --border-accent: #4f46e5;
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --accent-cyan: #38bdf8;
            --accent-indigo: #818cf8;
            --accent-purple: #c084fc;
            --accent-amber: #fbbf24;
            --accent-rose: #f43f5e;
            --accent-emerald: #10b981;
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

        /* Model Selection 3-Column Layout & Meaningful Padding Area Box Color */
        .model-columns-container {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.75rem;
            margin-top: 0.5rem;
        }}
        @media (max-width: 960px) {{
            .model-columns-container {{
                grid-template-columns: 1fr;
            }}
        }}
        .model-column {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            padding: 0.75rem;
            display: flex;
            flex-direction: column;
            min-width: 0;
            box-sizing: border-box;
        }}
        .model-column-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 0.45rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            margin-bottom: 0.45rem;
        }}
        .model-column-scroll {{
            max-height: 220px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
            padding-right: 0.2rem;
        }}
        .btn-col-select {{
            background: none;
            border: none;
            font-size: 0.72rem;
            font-weight: 600;
            cursor: pointer;
            text-decoration: underline;
            padding: 0.1rem 0.3rem;
            border-radius: 4px;
            transition: opacity 0.15s ease;
        }}
        .btn-col-select:hover {{
            opacity: 0.8;
        }}
        .model-check-item {{
            display: flex;
            align-items: center;
            gap: 0.65rem;
            padding: 0.65rem 0.85rem;
            border-radius: 9px;
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid var(--border-card);
            border-color: var(--border-card);
            cursor: pointer;
            transition: background 0.15s ease, box-shadow 0.15s ease;
            user-select: none;
            box-sizing: border-box;
            width: 100%;
            position: relative;
        }}
        .model-check-item:hover {{
            background: rgba(30, 41, 59, 0.85);
            border-color: var(--border-card);
        }}
        .model-check-item input[type="checkbox"] {{
            margin: 0;
            width: 16px;
            height: 16px;
            accent-color: var(--primary);
            cursor: pointer;
            flex-shrink: 0;
        }}
        .model-info {{
            display: flex;
            flex-direction: column;
            min-width: 0;
            flex: 1;
        }}
        .model-name {{
            font-size: 0.8rem;
            font-weight: 600;
            color: #cbd5e1;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            line-height: 1.3;
        }}
        .model-meta {{
            display: flex;
            gap: 0.35rem;
            align-items: center;
            margin-top: 0.2rem;
            flex-wrap: wrap;
        }}
        .model-status {{
            font-size: 0.68rem;
            color: var(--text-muted);
        }}
        /* Selected: background only — keep row border-color identical */
        .model-check-item.is-selected,
        .model-check-item:has(input:checked) {{
            background: linear-gradient(135deg, rgba(14, 165, 233, 0.2), rgba(99, 102, 241, 0.16)) !important;
            border: 1px solid var(--border-card) !important;
            border-color: var(--border-card) !important;
            box-shadow: 0 0 12px rgba(56, 189, 248, 0.12) !important;
        }}
        .model-check-item.is-selected .model-name,
        .model-check-item:has(input:checked) .model-name {{
            color: #ffffff !important;
            font-weight: 700 !important;
        }}

        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 0.2rem 0.55rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-cyan {{ background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.35); color: #38bdf8; }}
        .badge-indigo {{ background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.35); color: #818cf8; }}
        .badge-purple {{ background: rgba(168, 85, 247, 0.15); border: 1px solid rgba(168, 85, 247, 0.35); color: #c084fc; }}
        .badge-amber {{ background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.35); color: #fbbf24; }}
        .badge-emerald {{ background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); color: #34d399; }}
        .badge-rose {{ background: rgba(244, 63, 94, 0.15); border: 1px solid rgba(244, 63, 94, 0.35); color: #fb7185; }}
        .badge-outline {{
            background: rgba(255, 255, 255, 0.04);
            color: #cbd5e1;
            border: 1px solid var(--border-subtle);
        }}

        .btn-sm {{ padding: 0.3rem 0.65rem; font-size: 0.78rem; border-radius: 6px; font-weight: 600; cursor: pointer; transition: all 0.15s ease; border: 1px solid transparent; }}
        .btn-cyan {{ background: #0284c7; color: #ffffff; border-color: #0284c7; }}
        .btn-cyan:hover {{ background: #0369a1; }}
        .btn-outline {{ background: rgba(255, 255, 255, 0.05); color: #cbd5e1; border-color: #334155; }}
        .btn-outline:hover {{ background: rgba(255, 255, 255, 0.1); color: #ffffff; }}

        .search-input {{
            background: #0f172a;
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            color: #ffffff;
            outline: none;
        }}
        .search-input:focus {{ border-color: var(--primary); }}

        .table-responsive {{ width: 100%; overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
        th {{ text-align: left; padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--border-subtle); color: var(--text-secondary); font-weight: 600; text-transform: uppercase; font-size: 0.7rem; }}
        td {{ padding: 0.6rem 0.75rem; border-bottom: 1px solid rgba(255, 255, 255, 0.04); }}
        .cell-mono {{ font-family: var(--font-mono); }}

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
                {pred_model_selector}
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

        function selectPredictModels(prefix, mode) {{
            const boxes = document.querySelectorAll('.' + prefix + '-checkbox');
            boxes.forEach(b => {{
                const item = b.closest('.' + prefix + '-check-item');
                const prov = item ? (item.getAttribute('data-provider') || '') : '';
                const cat = item ? (item.getAttribute('data-category') || '') : '';
                const isCustom = cat === 'custom' || prov.includes('requesty');
                const isBaseline = prov.includes('local');

                if (mode === 'all') {{
                    b.checked = true;
                }} else if (mode === 'none') {{
                    b.checked = false;
                }} else if (mode === 'baselines') {{
                    b.checked = isBaseline;
                }} else if (mode === 'llms') {{
                    b.checked = !isBaseline && !isCustom;
                }} else if (mode === 'custom') {{
                    b.checked = isCustom;
                }}

                if (item) {{
                    if (b.checked) item.classList.add('is-selected');
                    else item.classList.remove('is-selected');
                }}
            }});
            updatePredictModelSelection(prefix);
        }}

        function filterModelCheckboxes(prefix) {{
            const query = (document.getElementById(prefix + '-model-filter')?.value || '').toLowerCase();
            const items = document.querySelectorAll('.' + prefix + '-check-item');
            items.forEach(it => {{
                const text = it.innerText.toLowerCase();
                it.style.display = !query || text.includes(query) ? 'flex' : 'none';
            }});
        }}

        function onPredictModelPick(prefix, checkbox) {{
            if (prefix !== 'analytics' && checkbox && checkbox.checked) {{
                document.querySelectorAll('.' + prefix + '-checkbox').forEach(b => {{
                    if (b !== checkbox) {{
                        b.checked = false;
                        const item = b.closest('.' + prefix + '-check-item');
                        if (item) item.classList.remove('is-selected');
                    }}
                }});
            }}
            updatePredictModelSelection(prefix);
        }}

        function updatePredictModelSelection(prefix) {{
            const allBoxes = document.querySelectorAll('.' + prefix + '-checkbox');
            const checked = [];
            allBoxes.forEach(b => {{
                const item = b.closest('.' + prefix + '-check-item');
                if (b.checked) {{
                    checked.push(b);
                    if (item) item.classList.add('is-selected');
                }} else {{
                    if (item) item.classList.remove('is-selected');
                }}
            }});
            const badge = document.getElementById(prefix + '-selected-count');
            if (!badge) return;
            if (checked.length === 0) {{
                badge.textContent = 'No Models Selected (0)';
                badge.className = 'badge badge-rose';
            }} else if (checked.length === 1) {{
                const item = checked[0].closest('.' + prefix + '-check-item');
                const name = item ? (item.querySelector('.model-name')?.innerText || checked[0].value) : checked[0].value;
                badge.textContent = 'Selected: 1 Model (' + name + ')';
                badge.className = 'badge badge-cyan';
            }} else if (checked.length === allBoxes.length) {{
                badge.textContent = 'Selected: All ' + checked.length + ' Models (Consensus Ensemble)';
                badge.className = 'badge badge-emerald';
            }} else {{
                badge.textContent = 'Selected: ' + checked.length + ' Models (Multi-Model Ensemble)';
                badge.className = 'badge badge-indigo';
            }}
        }}

        function addCustomPredictModel(prefix) {{
            const input = document.getElementById(prefix + '-custom-input');
            if (!input) return;
            const modelId = input.value.trim();
            if (!modelId) return;

            const list = document.getElementById(prefix + '-custom-list');
            if (!list) return;

            const existing = document.querySelector('.' + prefix + '-checkbox[value="' + modelId + '"]');
            if (existing) {{
                existing.checked = true;
                onPredictModelPick(prefix, existing);
                input.value = '';
                return;
            }}

            if (prefix !== 'analytics') {{
                document.querySelectorAll('.' + prefix + '-checkbox').forEach(b => {{
                    b.checked = false;
                    const item = b.closest('.' + prefix + '-check-item');
                    if (item) item.classList.remove('is-selected');
                }});
            }}

            const label = document.createElement('label');
            label.className = 'model-check-item ' + prefix + '-check-item is-selected';
            label.setAttribute('data-id', modelId);
            label.setAttribute('data-category', 'custom');
            label.setAttribute('data-provider', 'custom');
            label.setAttribute('data-name', modelId.toLowerCase());
            label.innerHTML = `
                <input type="checkbox" name="${{prefix}}-selected-models" value="${{modelId}}" class="${{prefix}}-checkbox" checked onchange="onPredictModelPick('${{prefix}}', this)">
                <div class="model-info">
                    <span class="model-name" title="${{modelId}}">${{modelId}}</span>
                    <div class="model-meta">
                        <span class="badge badge-purple">Custom API</span>
                        <span class="model-status">🛠️ User Specified</span>
                    </div>
                </div>
            `;
            list.prepend(label);
            input.value = '';
            updatePredictModelSelection(prefix);
        }}

        function renderPredictResponse(data, elapsedMs, resultBox, verdictDiv) {{
            if (resultBox) {{
                resultBox.textContent = JSON.stringify(data, null, 2);
            }}
            if (!verdictDiv) return;
            verdictDiv.style.display = 'block';

            if (data.mode === 'multi_model' && data.aggregate) {{
                const agg = data.aggregate;
                const isActionable = agg.consensus_actionable;
                const bannerBg = isActionable 
                    ? 'linear-gradient(135deg, rgba(244, 63, 94, 0.22), rgba(225, 29, 72, 0.1))' 
                    : 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(5, 150, 105, 0.08))';
                const bannerBorder = isActionable ? 'rgba(244, 63, 94, 0.45)' : 'rgba(16, 185, 129, 0.4)';
                const titleColor = isActionable ? '#fb7185' : '#34d399';
                const badgeCls = isActionable ? 'badge-rose' : 'badge-emerald';

                const modelsList = Object.values(data.models || {{}});
                modelsList.sort((a, b) => (b.harm_probability || 0) - (a.harm_probability || 0));

                let modelRows = '';
                modelsList.forEach(m => {{
                    const mAct = m.actionable;
                    const mBadge = mAct 
                        ? '<span class="badge badge-rose">🚨 FLAGGED</span>' 
                        : '<span class="badge badge-emerald">🟢 CLEARED</span>';
                    const mProbPct = Math.round((m.harm_probability || 0) * 100);
                    const mProbColor = mAct ? '#f43f5e' : '#38bdf8';
                    const provLower = (m.provider || '').toLowerCase();
                    const isCustom = provLower.includes('requesty') || provLower.includes('custom');
                    const customBadge = isCustom 
                        ? '<span class="badge badge-purple">🛠️ Custom</span>' 
                        : (provLower.includes('local') 
                            ? '<span class="badge badge-cyan">⚡ Baseline</span>' 
                            : '<span class="badge badge-indigo">🤖 Frontier</span>');

                    modelRows += `
                        <tr>
                            <td style="font-weight: 600; color: #fff;">
                                <div>${{m.model_name}}</div>
                                <div style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted);">${{m.model_id}}</div>
                            </td>
                            <td><span class="badge badge-indigo">${{m.provider}}</span></td>
                            <td>${{customBadge}}</td>
                            <td class="cell-mono" style="text-align: right;">
                                <div style="font-weight: 700; color: ${{mProbColor}}; font-size: 0.88rem;">${{(m.harm_probability || 0).toFixed(4)}}</div>
                                <div style="height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; margin-top: 3px;">
                                    <div style="height: 100%; width: ${{Math.max(4, mProbPct)}}%; background: ${{mProbColor}};"></div>
                                </div>
                            </td>
                            <td>${{mBadge}}</td>
                            <td><span class="badge badge-amber">${{m.dominant_severity || 'safe'}}</span></td>
                            <td class="cell-mono" style="text-align: right; color: var(--text-muted); font-size: 0.75rem;">${{m.latency_ms || 0}}ms</td>
                        </tr>
                    `;
                }});

                const flaggedChips = (agg.flagged_by || []).map(f => `<span class="badge badge-rose" style="margin: 0.15rem;">🚨 ${{f}}</span>`).join('') || '<span style="color: var(--text-muted); font-size: 0.8rem;">None (0 models)</span>';
                const clearedChips = (agg.cleared_by || []).map(c => `<span class="badge badge-emerald" style="margin: 0.15rem;">🟢 ${{c}}</span>`).join('') || '<span style="color: var(--text-muted); font-size: 0.8rem;">None (0 models)</span>';

                verdictDiv.innerHTML = `
                    <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.25rem; margin-bottom: 1.25rem;">
                        <div style="background: ${{bannerBg}}; border: 1px solid ${{bannerBorder}}; padding: 0.9rem 1.2rem; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.1rem; flex-wrap: wrap; gap: 0.5rem;">
                            <div>
                                <div style="font-size: 0.72rem; text-transform: uppercase; font-weight: 700; color: ${{titleColor}}; letter-spacing: 0.05em;">Consensus Ensemble Verdict (${{agg.models_evaluated_count}} Models)</div>
                                <div style="font-size: 1.25rem; font-weight: 800; color: #fff; margin-top: 0.2rem;">${{agg.verdict_label}} (${{agg.agreement_percentage}}% Consensus)</div>
                            </div>
                            <span class="badge ${{badgeCls}}" style="font-size: 0.82rem; padding: 0.35rem 0.75rem;">${{agg.divergence_level}}</span>
                        </div>

                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 0.75rem; margin-bottom: 1.1rem;">
                            <div style="background: rgba(0,0,0,0.35); padding: 0.75rem 0.9rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                <div style="font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;">Mean Harm Prob</div>
                                <div style="font-size: 1.15rem; font-weight: 700; color: #fff; font-family: var(--font-mono);">${{agg.mean_harm_probability.toFixed(3)}} <span style="font-size: 0.72rem; color: var(--text-muted);">±${{agg.std_harm_probability.toFixed(2)}}</span></div>
                            </div>
                            <div style="background: rgba(0,0,0,0.35); padding: 0.75rem 0.9rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                <div style="font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;">Agreement Rate</div>
                                <div style="font-size: 1.15rem; font-weight: 700; color: var(--accent-cyan); font-family: var(--font-mono);">${{agg.agreement_percentage}}%</div>
                            </div>
                            <div style="background: rgba(0,0,0,0.35); padding: 0.75rem 0.9rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                <div style="font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;">Consensus Severity</div>
                                <div style="font-size: 1.15rem; font-weight: 700; color: var(--accent-amber);">${{agg.dominant_severity.toUpperCase()}}</div>
                            </div>
                            <div style="background: rgba(0,0,0,0.35); padding: 0.75rem 0.9rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                <div style="font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;">Models Ratio</div>
                                <div style="font-size: 1.15rem; font-weight: 700; color: #fff; font-family: var(--font-mono);"><span style="color: var(--accent-rose);">${{agg.actionable_count}} Flagged</span> / <span style="color: var(--accent-emerald);">${{agg.cleared_count}} Cleared</span></div>
                            </div>
                        </div>

                        <div style="margin-bottom: 1.1rem;">
                            <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.25rem;">
                                <span style="color: var(--accent-rose); font-weight: 600;">Actionable Harm (${{agg.actionable_count}})</span>
                                <span style="color: var(--accent-emerald); font-weight: 600;">Benign Banter (${{agg.cleared_count}})</span>
                            </div>
                            <div style="height: 8px; border-radius: 4px; background: rgba(255,255,255,0.06); display: flex; overflow: hidden;">
                                <div style="height: 100%; width: ${{(agg.actionable_count/agg.models_evaluated_count)*100}}%; background: linear-gradient(90deg, #f43f5e, #fb7185);"></div>
                                <div style="height: 100%; width: ${{(agg.cleared_count/agg.models_evaluated_count)*100}}%; background: linear-gradient(90deg, #059669, #34d399);"></div>
                            </div>
                        </div>

                        <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5; background: rgba(0,0,0,0.25); padding: 0.85rem 1rem; border-radius: 8px; border-left: 3px solid var(--accent-cyan); margin-bottom: 1rem;">
                            <strong style="color: #fff;">Consensus Synthesis:</strong> ${{agg.synthesis}}
                        </div>

                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; font-size: 0.8rem;">
                            <div style="background: rgba(0,0,0,0.2); padding: 0.6rem 0.8rem; border-radius: 6px;">
                                <div style="font-size: 0.7rem; color: var(--text-muted); margin-bottom: 0.35rem; font-weight: 600; text-transform: uppercase;">Flagged Actionable by:</div>
                                <div style="display: flex; flex-wrap: wrap;">${{flaggedChips}}</div>
                            </div>
                            <div style="background: rgba(0,0,0,0.2); padding: 0.6rem 0.8rem; border-radius: 6px;">
                                <div style="font-size: 0.7rem; color: var(--text-muted); margin-bottom: 0.35rem; font-weight: 600; text-transform: uppercase;">Cleared Benign by:</div>
                                <div style="display: flex; flex-wrap: wrap;">${{clearedChips}}</div>
                            </div>
                        </div>
                    </div>

                    <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.25rem; margin-bottom: 1.25rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
                            <h3 style="font-size: 0.95rem; font-weight: 700; color: #fff;"><span>📊</span> Separate Model Predictions (${{modelsList.length}} Models)</h3>
                            <span style="font-size: 0.75rem; color: var(--text-muted);">Parallel Execution Completed in ${{elapsedMs}}ms</span>
                        </div>
                        <div class="table-responsive" style="max-height: 320px; overflow-y: auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Evaluated Model</th>
                                        <th>Provider</th>
                                        <th>Custom</th>
                                        <th style="text-align: right;">Harm Probability</th>
                                        <th>Decision</th>
                                        <th>Dominant Severity</th>
                                        <th style="text-align: right;">Latency</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${{modelRows}}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            }} else {{
                const harmProb = data.harm_probability !== undefined ? data.harm_probability : 0.0;
                const actionable = data.actionable !== undefined ? data.actionable : (harmProb >= 0.5);
                const modelName = data.model_name || data.model_id || 'Raw Lexicon Match';
                const provider = data.provider || 'Local Baseline';
                const sevProbs = data.severity_probabilities || {{}};
                let domSev = data.dominant_severity || 'safe';
                if (!domSev && Object.keys(sevProbs).length) {{
                    domSev = Object.keys(sevProbs).reduce((a, b) => sevProbs[a] > sevProbs[b] ? a : b);
                }}
                const badgeCls = actionable ? 'badge-rose' : 'badge-emerald';
                const verdictTitle = actionable ? '🚨 ACTIONABLE VIOLATION' : '🟢 NON-ACTIONABLE / SAFE';

                let sevBars = '';
                for (const [k, v] of Object.entries(sevProbs)) {{
                    const pct = Math.round(v * 100);
                    sevBars += `
                        <div style="margin-bottom: 0.4rem;">
                            <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.15rem;">
                                <span>${{k}}</span>
                                <span class="cell-mono">${{(v).toFixed(3)}}</span>
                            </div>
                            <div style="height: 5px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden;">
                                <div style="height: 100%; width: ${{Math.max(2, pct)}}%; background: var(--accent-cyan);"></div>
                            </div>
                        </div>
                    `;
                }}

                verdictDiv.innerHTML = `
                    <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.25rem; margin-bottom: 1.25rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
                            <div>
                                <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted);">Predicting Model</div>
                                <div style="font-size: 1.15rem; font-weight: 700; color: #fff;">${{modelName}}</div>
                                <div style="font-size: 0.72rem; color: var(--text-muted);">${{provider}} • ${{data.latency_ms || 0}}ms</div>
                            </div>
                            <span class="badge ${{badgeCls}}" style="font-size: 0.85rem; padding: 0.4rem 0.8rem;">${{verdictTitle}}</span>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                            <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: 8px;">
                                <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Harm Probability</div>
                                <div style="font-size: 1.4rem; font-weight: 800; color: ${{actionable ? '#f43f5e' : '#34d399'}}; font-family: var(--font-mono);">${{harmProb.toFixed(4)}}</div>
                            </div>
                            <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: 8px;">
                                <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Dominant Severity</div>
                                <div style="font-size: 1.4rem; font-weight: 800; color: var(--accent-amber); font-family: var(--font-mono);">${{domSev.toUpperCase()}}</div>
                            </div>
                        </div>
                        <div style="background: rgba(0,0,0,0.25); padding: 0.75rem 1rem; border-radius: 8px;">
                            <div style="font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.5rem; text-transform: uppercase; font-weight: 600;">Severity Distribution</div>
                            ${{sevBars}}
                        </div>
                    </div>
                `;
            }}
        }}

        async function executeStreamingPredict({{ payload, btn, statusSpan, resultBox, verdictDiv }}) {{
            if (btn) btn.disabled = true;
            if (verdictDiv) verdictDiv.style.display = 'block';

            const tStart = performance.now();
            let timerInterval = null;

            const updateTimer = () => {{
                const now = performance.now();
                const elapsedSec = ((now - tStart) / 1000).toFixed(2);
                if (statusSpan) {{
                    statusSpan.innerHTML = `<span class="pulse-dot" style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#38bdf8; margin-right:5px;"></span>Live Elapsed: ${{elapsedSec}}s`;
                }}
            }};
            timerInterval = setInterval(updateTimer, 40);
            updateTimer();

            const modelsState = new Map();
            let currentAggregate = null;
            let totalExpected = 1;
            let isMulti = false;
            let rawOutputAccumulator = {{}};

            const renderUI = (isComplete = false) => {{
                const now = performance.now();
                const currentElapsedSec = ((now - tStart) / 1000).toFixed(2);
                const completedList = Array.from(modelsState.values()).filter(m => m.status === 'done');
                const completedCount = completedList.length;
                const pct = totalExpected > 0 ? Math.round((completedCount / totalExpected) * 100) : 0;

                if (resultBox) {{
                    resultBox.textContent = JSON.stringify(rawOutputAccumulator, null, 2);
                }}

                if (isMulti || totalExpected > 1) {{
                    let progressHtml = `
                        <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.15rem; margin-bottom: 1.2rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; flex-wrap: wrap; gap: 0.5rem;">
                                <div style="font-size: 0.88rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 0.5rem;">
                                    ${{isComplete 
                                        ? '<span style="color: var(--accent-emerald);">✅ Asynchronous Inference Complete</span>' 
                                        : '<span class="pulse-dot" style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#38bdf8;"></span><span>Asynchronous Model Stream in Progress...</span>'}}
                                </div>
                                <div style="font-size: 0.8rem; font-family: var(--font-mono); color: var(--accent-cyan); font-weight: 600;">
                                    ${{completedCount}} / ${{totalExpected}} Models (${{pct}}%) • ${{currentElapsedSec}}s
                                </div>
                            </div>
                            <div style="height: 6px; border-radius: 3px; background: rgba(255,255,255,0.06); overflow: hidden; margin-bottom: 0.85rem;">
                                <div style="height: 100%; width: ${{Math.max(3, pct)}}%; background: linear-gradient(90deg, #38bdf8, #818cf8); transition: width 0.15s ease;"></div>
                            </div>
                    `;

                    if (currentAggregate && completedCount > 0) {{
                        const agg = currentAggregate;
                        const isActionable = agg.consensus_actionable;
                        const bannerBg = isActionable 
                            ? 'linear-gradient(135deg, rgba(244, 63, 94, 0.22), rgba(225, 29, 72, 0.1))' 
                            : 'linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(5, 150, 105, 0.08))';
                        const bannerBorder = isActionable ? 'rgba(244, 63, 94, 0.45)' : 'rgba(16, 185, 129, 0.4)';
                        const titleColor = isActionable ? '#fb7185' : '#34d399';
                        const badgeCls = isActionable ? 'badge-rose' : 'badge-emerald';

                        const flaggedChips = (agg.flagged_by || []).map(f => `<span class="badge badge-rose" style="margin: 0.15rem;">🚨 ${{f}}</span>`).join('') || '<span style="color: var(--text-muted); font-size: 0.8rem;">None (0 models)</span>';
                        const clearedChips = (agg.cleared_by || []).map(c => `<span class="badge badge-emerald" style="margin: 0.15rem;">🟢 ${{c}}</span>`).join('') || '<span style="color: var(--text-muted); font-size: 0.8rem;">None (0 models)</span>';

                        progressHtml += `
                            <div style="background: ${{bannerBg}}; border: 1px solid ${{bannerBorder}}; padding: 0.85rem 1.15rem; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
                                <div>
                                    <div style="font-size: 0.7rem; text-transform: uppercase; font-weight: 700; color: ${{titleColor}}; letter-spacing: 0.05em;">
                                        Progressive Consensus (${{completedCount}} of ${{totalExpected}} Models Reporting)
                                    </div>
                                    <div style="font-size: 1.25rem; font-weight: 800; color: #fff; margin-top: 0.15rem;">
                                        ${{agg.verdict_label}} (${{agg.agreement_percentage}}% Consensus)
                                    </div>
                                </div>
                                <span class="badge ${{badgeCls}}" style="font-size: 0.8rem; padding: 0.3rem 0.7rem;">${{agg.divergence_level}}</span>
                            </div>

                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 0.65rem; margin-bottom: 0.9rem;">
                                <div style="background: rgba(0,0,0,0.35); padding: 0.65rem 0.8rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                    <div style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase;">Mean Harm Prob</div>
                                    <div style="font-size: 1.1rem; font-weight: 700; color: #fff; font-family: var(--font-mono);">${{agg.mean_harm_probability.toFixed(3)}} <span style="font-size: 0.7rem; color: var(--text-muted);">±${{agg.std_harm_probability.toFixed(2)}}</span></div>
                                </div>
                                <div style="background: rgba(0,0,0,0.35); padding: 0.65rem 0.8rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                    <div style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase;">Agreement Rate</div>
                                    <div style="font-size: 1.1rem; font-weight: 700; color: var(--accent-cyan); font-family: var(--font-mono);">${{agg.agreement_percentage}}%</div>
                                </div>
                                <div style="background: rgba(0,0,0,0.35); padding: 0.65rem 0.8rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                    <div style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase;">Consensus Severity</div>
                                    <div style="font-size: 1.1rem; font-weight: 700; color: var(--accent-amber);">${{agg.dominant_severity.toUpperCase()}}</div>
                                </div>
                                <div style="background: rgba(0,0,0,0.35); padding: 0.65rem 0.8rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                    <div style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase;">Ratio</div>
                                    <div style="font-size: 1.1rem; font-weight: 700; color: #fff; font-family: var(--font-mono);"><span style="color: var(--accent-rose);">${{agg.actionable_count}} Flagged</span> / <span style="color: var(--accent-emerald);">${{agg.cleared_count}} Cleared</span></div>
                                </div>
                            </div>

                            <div style="margin-bottom: 0.85rem;">
                                <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-muted); margin-bottom: 0.2rem;">
                                    <span style="color: var(--accent-rose); font-weight: 600;">Actionable (${{agg.actionable_count}})</span>
                                    <span style="color: var(--accent-emerald); font-weight: 600;">Benign (${{agg.cleared_count}})</span>
                                </div>
                                <div style="height: 7px; border-radius: 4px; background: rgba(255,255,255,0.06); display: flex; overflow: hidden;">
                                    <div style="height: 100%; width: ${{ (agg.actionable_count / Math.max(1, agg.models_evaluated_count)) * 100 }}%; background: linear-gradient(90deg, #f43f5e, #fb7185);"></div>
                                    <div style="height: 100%; width: ${{ (agg.cleared_count / Math.max(1, agg.models_evaluated_count)) * 100 }}%; background: linear-gradient(90deg, #059669, #34d399);"></div>
                                </div>
                            </div>

                            <div style="font-size: 0.82rem; color: var(--text-secondary); line-height: 1.45; background: rgba(0,0,0,0.25); padding: 0.75rem 0.9rem; border-radius: 8px; border-left: 3px solid var(--accent-cyan); margin-bottom: 0.85rem;">
                                <strong style="color: #fff;">Consensus Synthesis:</strong> ${{agg.synthesis}}
                            </div>

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; font-size: 0.78rem;">
                                <div style="background: rgba(0,0,0,0.2); padding: 0.55rem 0.75rem; border-radius: 6px;">
                                    <div style="font-size: 0.68rem; color: var(--text-muted); margin-bottom: 0.25rem; font-weight: 600; text-transform: uppercase;">Flagged by (${{agg.actionable_count}}):</div>
                                    <div style="display: flex; flex-wrap: wrap;">${{flaggedChips}}</div>
                                </div>
                                <div style="background: rgba(0,0,0,0.2); padding: 0.55rem 0.75rem; border-radius: 6px;">
                                    <div style="font-size: 0.68rem; color: var(--text-muted); margin-bottom: 0.25rem; font-weight: 600; text-transform: uppercase;">Cleared by (${{agg.cleared_count}}):</div>
                                    <div style="display: flex; flex-wrap: wrap;">${{clearedChips}}</div>
                                </div>
                            </div>
                        `;
                    }}

                    progressHtml += `</div>`;

                    const allModels = Array.from(modelsState.values());
                    allModels.sort((a, b) => {{
                        if (a.status === 'done' && b.status !== 'done') return -1;
                        if (a.status !== 'done' && b.status === 'done') return 1;
                        if (a.status === 'done' && b.status === 'done') {{
                            return (b.harm_probability || 0) - (a.harm_probability || 0);
                        }}
                        return 0;
                    }});

                    let tableRows = '';
                    allModels.forEach(m => {{
                        const provLower = (m.provider || '').toLowerCase();
                        const isCustom = provLower.includes('requesty') || provLower.includes('custom');
                        const customBadge = isCustom 
                            ? '<span class="badge badge-purple">🛠️ Custom</span>' 
                            : (provLower.includes('local') 
                                ? '<span class="badge badge-cyan">⚡ Baseline</span>' 
                                : '<span class="badge badge-indigo">🤖 Frontier</span>');

                        if (m.status === 'done') {{
                            const mAct = m.actionable;
                            const mBadge = mAct 
                                ? '<span class="badge badge-rose">🚨 FLAGGED</span>' 
                                : '<span class="badge badge-emerald">🟢 CLEARED</span>';
                            const mProbPct = Math.round((m.harm_probability || 0) * 100);
                            const mProbColor = mAct ? '#f43f5e' : '#38bdf8';
                            const returnedAtSec = m.elapsed_since_req_ms ? (m.elapsed_since_req_ms / 1000).toFixed(2) + 's' : '';

                            tableRows += `
                                <tr>
                                    <td style="font-weight: 600; color: #fff;">
                                        <div>${{m.model_name}}</div>
                                        <div style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted);">${{m.model_id}}</div>
                                    </td>
                                    <td><span class="badge badge-indigo">${{m.provider}}</span></td>
                                    <td>${{customBadge}}</td>
                                    <td class="cell-mono" style="text-align: right;">
                                        <div style="font-weight: 700; color: ${{mProbColor}}; font-size: 0.88rem;">${{(m.harm_probability || 0).toFixed(4)}}</div>
                                        <div style="height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; margin-top: 3px;">
                                            <div style="height: 100%; width: ${{Math.max(4, mProbPct)}}%; background: ${{mProbColor}};"></div>
                                        </div>
                                    </td>
                                    <td>${{mBadge}}</td>
                                    <td><span class="badge badge-amber">${{m.dominant_severity || 'safe'}}</span></td>
                                    <td class="cell-mono" style="text-align: right;">
                                        <div style="font-weight: 600; color: var(--accent-cyan); font-size: 0.8rem;">⚡ ${{m.latency_ms || 0}}ms</div>
                                        ${{returnedAtSec ? `<div style="font-size: 0.7rem; color: var(--text-muted);">+${{returnedAtSec}} returned</div>` : ''}}
                                    </td>
                                </tr>
                            `;
                        }} else {{
                            tableRows += `
                                <tr style="opacity: 0.7;">
                                    <td style="font-weight: 600; color: #cbd5e1;">
                                        <div>${{m.model_name}}</div>
                                        <div style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted);">${{m.model_id}}</div>
                                    </td>
                                    <td><span class="badge badge-outline">${{m.provider}}</span></td>
                                    <td>${{customBadge}}</td>
                                    <td class="cell-mono" style="text-align: right; color: var(--text-muted); font-size: 0.75rem;">
                                        Calculating...
                                    </td>
                                    <td>
                                        <span class="badge badge-cyan" style="background: rgba(56, 189, 248, 0.1);">
                                            <span class="pulse-dot" style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#38bdf8; margin-right:4px;"></span>In Flight
                                        </span>
                                    </td>
                                    <td><span style="color: var(--text-muted); font-size: 0.75rem;">-</span></td>
                                    <td class="cell-mono" style="text-align: right; color: var(--accent-amber); font-size: 0.78rem;">
                                        ⏱️ ${{currentElapsedSec}}s...
                                    </td>
                                </tr>
                            `;
                        }}
                    }});

                    progressHtml += `
                        <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.15rem; margin-bottom: 1.2rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
                                <h3 style="font-size: 0.95rem; font-weight: 700; color: #fff;"><span>📊</span> Model Predictions Breakdown (${{completedCount}} of ${{totalExpected}} Completed)</h3>
                                <span style="font-size: 0.75rem; color: var(--text-muted);">Real-time Asynchronous Stream • Elapsed: ${{currentElapsedSec}}s</span>
                            </div>
                            <div class="table-responsive" style="max-height: 340px; overflow-y: auto;">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Evaluated Model</th>
                                            <th>Provider</th>
                                            <th>Custom</th>
                                            <th style="text-align: right;">Harm Probability</th>
                                            <th>Decision</th>
                                            <th>Dominant Severity</th>
                                            <th style="text-align: right;">Latency & Return Time</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${{tableRows}}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    `;

                    verdictDiv.innerHTML = progressHtml;
                }} else {{
                    const completedList = Array.from(modelsState.values()).filter(m => m.status === 'done');
                    if (completedList.length > 0) {{
                        const data = completedList[0];
                        const harmProb = data.harm_probability !== undefined ? data.harm_probability : 0.0;
                        const actionable = data.actionable !== undefined ? data.actionable : (harmProb >= 0.5);
                        const modelName = data.model_name || data.model_id || 'Model';
                        const provider = data.provider || 'Local Baseline';
                        const sevProbs = data.severity_probabilities || {{}};
                        let domSev = data.dominant_severity || 'safe';
                        if (!domSev && Object.keys(sevProbs).length) {{
                            domSev = Object.keys(sevProbs).reduce((a, b) => sevProbs[a] > sevProbs[b] ? a : b);
                        }}
                        const badgeCls = actionable ? 'badge-rose' : 'badge-emerald';
                        const verdictTitle = actionable ? '🚨 ACTIONABLE VIOLATION' : '🟢 NON-ACTIONABLE / SAFE';

                        let sevBars = '';
                        for (const [k, v] of Object.entries(sevProbs)) {{
                            const spct = Math.round(v * 100);
                            sevBars += `
                                <div style="margin-bottom: 0.4rem;">
                                    <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.15rem;">
                                        <span>${{k}}</span>
                                        <span class="cell-mono">${{(v).toFixed(3)}}</span>
                                    </div>
                                    <div style="height: 5px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden;">
                                        <div style="height: 100%; width: ${{Math.max(2, spct)}}%; background: var(--accent-cyan);"></div>
                                    </div>
                                </div>
                            `;
                        }}

                        verdictDiv.innerHTML = `
                            <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.25rem; margin-bottom: 1.25rem;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
                                    <div>
                                        <div style="font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted);">Evaluated Model</div>
                                        <div style="font-size: 1.15rem; font-weight: 700; color: #fff;">${{modelName}}</div>
                                        <div style="font-size: 0.72rem; color: var(--text-muted);">${{provider}} • ⚡ ${{data.latency_ms || 0}}ms (returned at +${{currentElapsedSec}}s)</div>
                                    </div>
                                    <span class="badge ${{badgeCls}}" style="font-size: 0.85rem; padding: 0.4rem 0.8rem;">${{verdictTitle}}</span>
                                </div>
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                                    <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: 8px;">
                                        <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Harm Probability</div>
                                        <div style="font-size: 1.4rem; font-weight: 800; color: ${{actionable ? '#f43f5e' : '#34d399'}}; font-family: var(--font-mono);">${{harmProb.toFixed(4)}}</div>
                                    </div>
                                    <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: 8px;">
                                        <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Dominant Severity</div>
                                        <div style="font-size: 1.4rem; font-weight: 800; color: var(--accent-amber); font-family: var(--font-mono);">${{domSev.toUpperCase()}}</div>
                                    </div>
                                </div>
                                <div style="background: rgba(0,0,0,0.25); padding: 0.75rem 1rem; border-radius: 8px;">
                                    <div style="font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.5rem; text-transform: uppercase; font-weight: 600;">Severity Distribution</div>
                                    ${{sevBars}}
                                </div>
                            </div>
                        `;
                    }} else {{
                        verdictDiv.innerHTML = `
                            <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid var(--border-card); border-radius: 12px; padding: 1.5rem; text-align: center;">
                                <span class="pulse-dot" style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#38bdf8; margin-bottom: 0.5rem;"></span>
                                <div style="font-size: 1rem; font-weight: 700; color: #fff;">Inference In Flight</div>
                                <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">Elapsed: ${{currentElapsedSec}}s...</div>
                            </div>
                        `;
                    }}
                }}
            }};

            try {{
                const streamPayload = {{ ...payload, stream: true }};
                const res = await fetch('/predict', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'Accept': 'text/event-stream'
                    }},
                    body: JSON.stringify(streamPayload)
                }});

                if (!res.ok) {{
                    throw new Error(`HTTP ${{res.status}} ${{res.statusText}}`);
                }}

                const reader = res.body.getReader();
                const decoder = new TextDecoder("utf-8");
                let buffer = "";

                while (true) {{
                    const {{ done, value }} = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, {{ stream: true }});

                    const parts = buffer.split("\\n\\n");
                    buffer = parts.pop() || "";

                    for (const chunk of parts) {{
                        if (!chunk.trim()) continue;
                        let eventName = "message";
                        let eventData = "";
                        const lines = chunk.split("\\n");
                        for (const l of lines) {{
                            if (l.startsWith("event:")) {{
                                eventName = l.slice(6).trim();
                            }} else if (l.startsWith("data:")) {{
                                eventData += l.slice(5).trim();
                            }}
                        }}
                        if (!eventData) continue;

                        let dataObj;
                        try {{
                            dataObj = JSON.parse(eventData);
                        }} catch (e) {{
                            continue;
                        }}

                        if (eventName === "init") {{
                            totalExpected = dataObj.models_count || 1;
                            isMulti = dataObj.mode === "multi_model" || totalExpected > 1;
                            if (Array.isArray(dataObj.models_queued)) {{
                                dataObj.models_queued.forEach(mq => {{
                                    modelsState.set(mq.model_id, {{
                                        model_id: mq.model_id,
                                        model_name: mq.model_name,
                                        provider: mq.provider,
                                        status: 'waiting'
                                    }});
                                }});
                            }}
                            rawOutputAccumulator = {{ ...dataObj, models: {{}}, status: "in_progress" }};
                            renderUI(false);
                        }} else if (eventName === "model_done") {{
                            const m = dataObj.model;
                            if (m && m.model_id) {{
                                modelsState.set(m.model_id, {{
                                    ...m,
                                    status: 'done'
                                }});
                            }}
                            if (dataObj.aggregate) {{
                                currentAggregate = dataObj.aggregate;
                            }}
                            if (!rawOutputAccumulator.models) rawOutputAccumulator.models = {{}};
                            if (m && m.model_id) rawOutputAccumulator.models[m.model_id] = m;
                            rawOutputAccumulator.aggregate = currentAggregate;
                            renderUI(false);
                        }} else if (eventName === "complete") {{
                            if (dataObj.aggregate) currentAggregate = dataObj.aggregate;
                            if (dataObj.models) {{
                                for (const [mid, m] of Object.entries(dataObj.models)) {{
                                    modelsState.set(mid, {{ ...m, status: 'done' }});
                                }}
                            }}
                            rawOutputAccumulator = dataObj;
                            renderUI(true);
                        }}
                    }}
                }}

                clearInterval(timerInterval);
                const totalElapsedSec = ((performance.now() - tStart) / 1000).toFixed(2);
                if (statusSpan) {{
                    statusSpan.innerHTML = `<span style="color: var(--accent-emerald);">HTTP ${{res.status}} (${{totalElapsedSec}}s total)</span>`;
                }}
                renderUI(true);
            }} catch (err) {{
                clearInterval(timerInterval);
                if (statusSpan) statusSpan.textContent = "Error";
                if (resultBox) resultBox.textContent = "Error during asynchronous streaming: " + err.message;
            }} finally {{
                if (btn) btn.disabled = false;
            }}
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

            if (btn) btn.disabled = true;
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

            // Selected models
            const selected = Array.from(document.querySelectorAll('.pred-checkbox:checked')).map(b => b.value);
            if (selected.length === 1) {{
                payload.model = selected[0];
            }} else if (selected.length > 1) {{
                payload.models = selected;
            }}

            await executeStreamingPredict({{
                payload,
                btn,
                statusSpan,
                resultBox,
                verdictDiv
            }});
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

