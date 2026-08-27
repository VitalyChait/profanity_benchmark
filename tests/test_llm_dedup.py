"""Tests for LLM model deduplication pre-flight gates, scorers, and targets."""

import os
from unittest.mock import patch

from click.testing import CliRunner

from youth_escalate_bench.baselines.scorers import (
    PromptedLLMScorer,
    RuleBasedSafeguardScorer,
    build_default_scorers,
    deduplicate_scorers,
    load_lexicon,
)
from youth_escalate_bench.cli import main
from youth_escalate_bench.evaluation.conditions import ContextCondition
from youth_escalate_bench.evaluation.runner import run_evaluation
from youth_escalate_bench.llm.keys import (
    audit_llm_model_duplicates,
    get_expanded_eval_targets,
    get_openrouter_models,
)
from youth_escalate_bench.schemas.conversation import ConversationRecord, SourceTier, StoredTurn


def test_get_openrouter_models_deduplication() -> None:
    """Verify that get_openrouter_models removes duplicate model definitions."""
    env_str = "google/gemma-4-31b-it:free, openai/gpt-5.6-luna, google/gemma-4-31b-it:free, GOOGLE/GEMMA-4-31B-IT:FREE, mistral/mistral-large"
    with patch.dict(os.environ, {"OPENROUTER_MODELS": env_str}):
        models = get_openrouter_models()
        assert len(models) == 3
        assert models == [
            "google/gemma-4-31b-it:free",
            "openai/gpt-5.6-luna",
            "mistral/mistral-large",
        ]


def test_get_expanded_eval_targets_has_zero_duplicates() -> None:
    """Verify that get_expanded_eval_targets produces strictly unique (provider, model) pairs."""
    targets = get_expanded_eval_targets()
    normalized_keys = [(p.lower(), m.lower()) for p, m in targets]
    assert len(normalized_keys) == len(set(normalized_keys)), (
        "Expanded eval targets must contain zero duplicates"
    )


def test_deduplicate_scorers_removes_redundant_llm_entries() -> None:
    """Verify deduplicate_scorers drops duplicate PromptedLLMScorer instances targeting same model."""
    lexicon = load_lexicon("configs/profanity_lexicon.txt")
    guard = RuleBasedSafeguardScorer(lexicon)

    llm1 = PromptedLLMScorer(
        provider="openrouter", model="meta-llama/llama-3-8b", name="llm_llama3_a"
    )
    llm2 = PromptedLLMScorer(
        provider="openrouter", model="meta-llama/llama-3-8b", name="llm_llama3_b"
    )
    llm3 = PromptedLLMScorer(provider="openrouter", model="google/gemini-flash", name="llm_gemini")

    scorers = {
        "guard": guard,
        "llm1": llm1,
        "llm2": llm2,
        "llm3": llm3,
    }

    deduped, removed = deduplicate_scorers(scorers)

    assert len(deduped) == 3
    assert "guard" in deduped
    assert "llm1" in deduped
    assert "llm3" in deduped
    assert "llm2" not in deduped

    assert len(removed) == 1
    assert removed[0]["removed_scorer"] == "llm2"
    assert removed[0]["retained_scorer"] == "llm1"
    assert removed[0]["model"] == "meta-llama/llama-3-8b"


def test_deduplicate_scorers_prefers_explicit_over_generic() -> None:
    """Verify that an explicit named model replaces an identical generic fallback."""
    lexicon = load_lexicon("configs/profanity_lexicon.txt")
    guard = RuleBasedSafeguardScorer(lexicon)

    generic_llm = PromptedLLMScorer(provider="openrouter", model=None, name="prompted_llm_judge")
    explicit_llm = PromptedLLMScorer(
        provider="openrouter",
        model="google/gemma-4-31b-it:free",
        name="llm_openrouter_gemma",
    )

    scorers = {
        "guard": guard,
        "prompted_llm_judge": generic_llm,
        "llm_openrouter_gemma": explicit_llm,
    }

    with patch.dict(os.environ, {"OPENROUTER_MODEL": "google/gemma-4-31b-it:free"}):
        deduped, removed = deduplicate_scorers(scorers)

        assert "llm_openrouter_gemma" in deduped
        assert "prompted_llm_judge" not in deduped
        assert len(removed) == 1
        assert removed[0]["removed_scorer"] == "prompted_llm_judge"
        assert removed[0]["retained_scorer"] == "llm_openrouter_gemma"


def test_build_default_scorers_has_zero_duplicate_models() -> None:
    """Verify build_default_scorers guarantees zero duplicate model entries."""
    scorers = build_default_scorers("configs/profanity_lexicon.txt")
    targets_seen: set[tuple[str, str]] = set()

    for name, s in scorers.items():
        if isinstance(s, PromptedLLMScorer):
            key = (str(s.provider).lower(), str(s.model).lower())
            assert key not in targets_seen, f"Scorer '{name}' is a duplicate of target {key}"
            targets_seen.add(key)


def test_audit_llm_model_duplicates_detects_env_duplicates() -> None:
    """Verify audit_llm_model_duplicates detects duplicates in OPENROUTER_MODELS string."""
    env_str = "model/a:free, model/b:free, model/a:free"
    with patch.dict(os.environ, {"OPENROUTER_MODELS": env_str}):
        removals = audit_llm_model_duplicates()
        assert len(removals) >= 1
        assert removals[0]["duplicate_model"] == "model/a:free"


def test_run_evaluation_deduplication_gate(capsys) -> None:
    """Verify run_evaluation prints deduplication gate report when duplicates are supplied."""
    lexicon = load_lexicon("configs/profanity_lexicon.txt")
    guard = RuleBasedSafeguardScorer(lexicon)
    llm1 = PromptedLLMScorer(provider="openrouter", model="test-model-dup", name="scorer_1")
    llm2 = PromptedLLMScorer(provider="openrouter", model="test-model-dup", name="scorer_2")

    conversations = [
        ConversationRecord(
            conversation_id="conv_dup_01",
            source_id="test_source",
            source_tier=SourceTier.FIXTURE,
            benchmark_version="0.1.0",
            platform_style="gaming_chat",
            language_mode="english",
            turns=[
                StoredTurn(
                    turn_id="t1",
                    speaker_id="u1",
                    role="user",
                    text="hello there",
                    relative_time="0s",
                ),
            ],
        )
    ]
    labels = {("conv_dup_01", "t1"): False}

    scorers = {"guard": guard, "scorer_1": llm1, "scorer_2": llm2}
    bundle = run_evaluation(
        conversations=conversations,
        scorers=scorers,
        labels=labels,
        conditions=[ContextCondition.CURRENT_TURN_ONLY],
        max_samples=1,
    )

    captured = capsys.readouterr().out
    assert "LLM PRE-FLIGHT DEDUPLICATION GATE" in captured
    assert "REMOVED : 'scorer_2'" in captured
    assert len(bundle.results) == 2  # guard and scorer_1 only, scorer_2 removed


def test_cli_audit_models_command() -> None:
    """Verify yeb audit-models command executes and prints diagnostic audit summary."""
    runner = CliRunner()
    res = runner.invoke(main, ["audit-models"])
    assert res.exit_code == 0
    assert "LLM Model Duplication Pre-Flight Audit" in res.output
    assert "Active Unique LLM Evaluation Targets" in res.output


def test_deduplicate_scorers_preserves_rag_comparison_variants() -> None:
    """Verify deduplicate_scorers does not prune RAG comparison variants of the same model."""
    from youth_escalate_bench.baselines.scorers import RAGPromptedLLMScorer

    llm_std = PromptedLLMScorer(
        provider="openrouter", model="meta-llama/llama-3-8b", name="llm_llama3"
    )
    llm_rag = RAGPromptedLLMScorer(
        provider="openrouter", model="meta-llama/llama-3-8b", name="rag_llm_llama3"
    )

    scorers = {"llm_llama3": llm_std, "rag_llm_llama3": llm_rag}
    deduped, removed = deduplicate_scorers(scorers)

    assert len(deduped) == 2
    assert "llm_llama3" in deduped
    assert "rag_llm_llama3" in deduped
    assert len(removed) == 0


def test_get_requesty_models_deduplication() -> None:
    """Verify that get_requesty_models removes duplicate model definitions."""
    from youth_escalate_bench.llm.keys import get_requesty_models

    env_str = "google/gemma-4-31b-it, nvidia/nemotron-3.5-content-safety, google/gemma-4-31b-it, GOOGLE/GEMMA-4-31B-IT, mistral/leanstral-1-5"
    with patch.dict(os.environ, {"REQUESTY_MODELS": env_str}):
        models = get_requesty_models()
        assert len(models) == 3
        assert models == [
            "google/gemma-4-31b-it",
            "nvidia/nemotron-3.5-content-safety",
            "mistral/leanstral-1-5",
        ]


def test_audit_llm_model_duplicates_detects_requesty_duplicates() -> None:
    """Verify audit_llm_model_duplicates detects duplicates in REQUESTY_MODELS string."""
    env_str = "google/gemma-4-31b-it, nvidia/nemotron-3.5-content-safety, google/gemma-4-31b-it"
    with patch.dict(os.environ, {"REQUESTY_MODELS": env_str}):
        dups = audit_llm_model_duplicates()
        rq_dups = [d for d in dups if d["scope"] == "REQUESTY_MODELS"]
        assert len(rq_dups) == 1
        assert rq_dups[0]["duplicate_model"] == "google/gemma-4-31b-it"
