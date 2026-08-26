"""Automated file verification test suite (CI-style static & artifact verification)."""

import json
from pathlib import Path

import yaml

from youth_escalate_bench.schemas.export import export_all


def test_configs_stages_yaml_integrity() -> None:
    """Verify that every stage config YAML in configs/stages/ is valid and well-formed."""
    stages_dir = Path("configs/stages")
    assert stages_dir.is_dir(), "configs/stages directory must exist"

    stage_files = list(stages_dir.glob("*.yaml"))
    assert len(stage_files) >= 11, f"Expected at least 11 stage configs, found {len(stage_files)}"

    for path in stage_files:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict), f"{path.name} must parse into a YAML dict"
        assert "stage" in data, f"{path.name} must declare 'stage' key"
        assert "benchmark_version" in data, f"{path.name} must declare 'benchmark_version'"
        # Stage name should match filename stem
        assert data["stage"] == path.stem, f"Stage '{data['stage']}' does not match filename stem '{path.stem}'"


def test_source_registry_file_integrity() -> None:
    """Verify that configs/source_registry.yaml registers all 14 approved research sources."""
    reg_path = Path("configs/source_registry.yaml")
    assert reg_path.is_file(), "configs/source_registry.yaml must exist"

    with reg_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "sources" in data, "source_registry must contain 'sources' mapping"
    sources = data["sources"]
    assert len(sources) >= 14, f"Expected 14 registered sources, found {len(sources)}"

    required_fields = ["source_id", "name", "license", "status", "reviewer", "intended_use"]
    for info in sources:
        src_id = info.get("source_id", "unknown")
        for field in required_fields:
            assert field in info, f"Source '{src_id}' missing required field '{field}'"
        assert info["status"] == "approved", f"Source '{src_id}' must have status 'approved', found {info['status']}"
        assert info.get("reviewer") is not None, f"Source '{src_id}' must have a designated reviewer"


def test_profanity_lexicon_txt_integrity() -> None:
    """Verify that configs/profanity_lexicon.txt is valid, non-empty, and contains core seeds."""
    lex_path = Path("configs/profanity_lexicon.txt")
    assert lex_path.is_file(), "configs/profanity_lexicon.txt must exist"

    lines = [
        line.strip().lower()
        for line in lex_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert len(lines) >= 2000, f"Expected >2,000 profanity terms, found {len(lines)}"

    # Ensure no empty or whitespace lines
    assert all(len(w) > 0 for w in lines)

    # Core canonical benchmark seed words should be present
    seed_words = ["trash", "stupid", "idiot", "loser", "ugly", "hate", "kill", "die", "unalive", "kys", "moron", "jerk", "dumb", "worthless", "scum", "garbage"]
    for seed in seed_words:
        assert seed in lines, f"Canonical seed '{seed}' missing from profanity lexicon"


def test_profanity_database_json_integrity() -> None:
    """Verify configs/lexicons/profanity_database.json schema and categories."""
    db_path = Path("configs/lexicons/profanity_database.json")
    assert db_path.is_file(), "configs/lexicons/profanity_database.json must exist"

    data = json.loads(db_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "Profanity database must be a JSON dictionary"
    assert "terms" in data, "Database must have 'terms' dictionary"
    assert "metadata" in data, "Database must have 'metadata' dictionary"

    terms = data["terms"]
    assert len(terms) >= 2000, f"Expected >2,000 database entries, found {len(terms)}"

    for word, item in list(terms.items())[:200]:
        assert "word" in item
        assert "severity" in item
        assert item["severity"] in (1, 2, 3, 4), f"Severity must be in [1,2,3,4], got {item['severity']}"
        assert "categories" in item and isinstance(item["categories"], list)
        assert len(item["categories"]) > 0
        assert "sources" in item and isinstance(item["sources"], list)
        assert len(item["sources"]) > 0


def test_reports_directory_artifacts_integrity() -> None:
    """Verify that all core markdown and structured reports exist in reports/."""
    reports_dir = Path("reports")
    assert reports_dir.is_dir(), "reports/ directory must exist"

    # 1. Core Markdown reports
    expected_reports = [
        "evaluation_report.md",
        "data_report.md",
        "difficulty_ranking_report.md",
        "pii_spot_check_report.md",
        "table_main_results.tex",
        "report_summary.yaml",
        "difficulty_ranking.yaml",
        "llm_error_cases.json",
        "infographic_dashboard.html",
    ]
    for rep in expected_reports:
        p = reports_dir / rep
        assert p.is_file(), f"Expected report artifact '{rep}' not found in reports/"
        assert p.stat().st_size > 50, f"Report artifact '{rep}' appears unexpectedly empty"

    # 2. Check LaTeX table format
    tex_content = (reports_dir / "table_main_results.tex").read_text(encoding="utf-8")
    assert "\\begin{table" in tex_content and "\\end{table" in tex_content

    # 3. Check PII audit status
    pii_report = (reports_dir / "pii_spot_check_report.md").read_text(encoding="utf-8")
    assert "AUDIT PASSED" in pii_report


def test_infographics_png_images_validity() -> None:
    """Verify that all 4 publication infographic figures exist and are valid PNG files."""
    reports_dir = Path("reports")
    expected_figures = [
        "figure_auprc_heatmap.png",
        "figure_context_trajectory.png",
        "figure_llm_leaderboard.png",
        "infographic_models_comparison.png",
    ]
    # Standard PNG magic number: \x89PNG\r\n\x1a\n
    png_magic = b"\x89PNG\r\n\x1a\n"

    for fig in expected_figures:
        fig_path = reports_dir / fig
        assert fig_path.is_file(), f"Figure '{fig}' must exist in reports/"
        assert fig_path.stat().st_size > 10_000, f"Figure '{fig}' size is unexpectedly small"
        with fig_path.open("rb") as f:
            header = f.read(8)
            assert header == png_magic, f"Figure '{fig}' does not have valid PNG magic bytes"


def test_documentation_and_project_links_exist() -> None:
    """Verify that all documentation files referenced in index exist."""
    expected_files = [
        Path("docs/datasheet.md"),
        Path("docs/benchmark_card.md"),
        Path("docs/threat_model.md"),
        Path("docs/preregistration.md"),
        Path("docs/license_audit_worksheet.md"),
        Path("docs/annotation_guidelines_v0.1.md"),
        Path("docs/annotator_wellness_protocol.md"),
        Path("docs/youth_advisory_protocol.md"),
        Path("docs/irb_ethics_package.md"),
        Path("docker/evaluator/Dockerfile"),
        Path("docker/evaluator/README.md"),
        Path("TASKS.md"),
        Path("TODO.md"),
        Path("README.md"),
        Path("README_extended.md"),
        Path("LICENSE"),
        Path("pyproject.toml"),
        Path(".env.example"),
    ]
    for path in expected_files:
        assert path.is_file(), f"Document or project file '{path}' is missing"
        assert path.stat().st_size > 0, f"Document '{path}' is empty"


def test_github_workflows_valid_yaml() -> None:
    """Verify that all GitHub Actions workflow files are valid YAML with jobs defined."""
    workflows_dir = Path(".github/workflows")
    assert workflows_dir.is_dir(), ".github/workflows directory must exist"

    ci_file = workflows_dir / "ci.yml"
    assert ci_file.is_file(), ".github/workflows/ci.yml must exist"
    with ci_file.open("r", encoding="utf-8") as f:
        ci_data = yaml.safe_load(f)
    assert "jobs" in ci_data and "test" in ci_data["jobs"]

    agent_file = workflows_dir / "agentic_discovery.yml"
    assert agent_file.is_file(), ".github/workflows/agentic_discovery.yml must exist"
    with agent_file.open("r", encoding="utf-8") as f:
        agent_data = yaml.safe_load(f)
    assert "jobs" in agent_data and "agentic-discovery" in agent_data["jobs"]


def test_env_example_no_secrets_leakage() -> None:
    """Verify that .env.example contains no hardcoded private API keys."""
    env_example = Path(".env.example")
    assert env_example.is_file(), ".env.example must exist"

    lines = env_example.read_text(encoding="utf-8").splitlines()
    sensitive_keys = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "XAI_API_KEY",
        "DASHSCOPE_API_KEY",
        "GLM_API_KEY",
        "GROQ_API_KEY",
        "DEEPSEEK_API_KEY",
        "MISTRAL_API_KEY",
        "COHERE_API_KEY",
        "OPENROUTER_API_KEY",
        "HF_TOKEN",
    ]

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("\"'")
            if key in sensitive_keys:
                assert val == "", f"Security risk: {key} has non-empty default value in .env.example: '{val}'"


def test_exported_json_schemas_validity(tmp_path: Path) -> None:
    """Verify that JSON Schema export generates valid draft schemas for all contracts."""
    out_paths = export_all(tmp_path)
    assert len(out_paths) >= 4, f"Expected at least 4 exported schemas, got {len(out_paths)}"

    for schema_path in out_paths:
        assert schema_path.is_file()
        content = json.loads(schema_path.read_text(encoding="utf-8"))
        assert "title" in content or "properties" in content
        assert content.get("type") == "object"
