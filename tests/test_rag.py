"""Tests for SlangRAGRetriever, RAGPromptedLLMJudgeScorer, and RAG benchmarking."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from youth_escalate_bench.baselines.scorers import (
    PromptedLLMScorer,
    RAGPromptedLLMScorer,
    build_default_scorers,
)
from youth_escalate_bench.cli import main
from youth_escalate_bench.external.urban_dictionary import UrbanDefinition
from youth_escalate_bench.rag import SlangRAGRetriever, get_default_rag_retriever
from youth_escalate_bench.schemas.inference import (
    InferenceRequest,
    PlatformStyle,
    TaskType,
    TurnRecord,
)
from youth_escalate_bench.stages.report import _generate_rag_impact_report


def test_rag_retriever_singleton() -> None:
    r1 = get_default_rag_retriever()
    r2 = get_default_rag_retriever()
    assert r1 is r2


def test_candidate_extraction_and_leetspeak() -> None:
    retriever = SlangRAGRetriever()

    text = "You are such a tr@sh kid, k!ll yourself and stop feeding."
    candidates = retriever.extract_candidates(text)

    # Stop words like "you", "are", "and" should be filtered out
    assert "you" not in candidates
    assert "are" not in candidates
    assert "and" not in candidates

    # Normalized forms of leetspeak tokens should be present
    assert "trash" in candidates
    assert "kill" in candidates


def test_rag_retrieval_and_block_formatting() -> None:
    retriever = SlangRAGRetriever(max_terms_per_request=3, max_definition_chars=80)

    # Mock Urban Dictionary client lookup for emerging neologisms
    retriever.urban_client.lookup = MagicMock(
        return_value=UrbanDefinition(
            word="crashout",
            meaning="An uncontrollable violent or aggressive outburst over a video game.",
            example="Bro had a major crashout on stream.",
        )
    )

    req = InferenceRequest(
        benchmark_version="0.1.2",
        conversation_id="conv_rag_01",
        current_turn_id="t2",
        platform_style=PlatformStyle.GAMING_CHAT,
        language_mode="english",
        task=TaskType.CURRENT_HARM,
        turns=[
            TurnRecord(
                turn_id="t1",
                speaker_id="u1",
                role="user",
                text="Are we winning?",
                relative_time="0s",
            ),
            TurnRecord(
                turn_id="t2",
                speaker_id="u2",
                role="user",
                text="He had a crashout bro",
                relative_time="+5s",
            ),
        ],
    )

    defs = retriever.retrieve_context_for_request(req)
    assert "crashout" in defs
    assert len(defs["crashout"]) <= 83  # <= 80 chars + potential '...'

    rag_block = retriever.format_rag_context_block(defs)
    assert "[Retrieved Dynamic Slang & Context Knowledge]:" in rag_block
    assert '"crashout":' in rag_block


def test_rag_llm_scorer_prompt_construction() -> None:
    scorer = RAGPromptedLLMScorer(
        provider="openai",
        model="gpt-4o-mini",
        prompt_template="Moderate the dialogue carefully.",
    )

    # Mock retriever
    scorer.retriever.retrieve_context_for_request = MagicMock(
        return_value={"crashout": "Violent aggressive fit in gaming."}
    )

    req = InferenceRequest(
        benchmark_version="0.1.2",
        conversation_id="conv_rag_02",
        current_turn_id="t1",
        platform_style=PlatformStyle.GAMING_CHAT,
        language_mode="english",
        task=TaskType.CURRENT_HARM,
        turns=[
            TurnRecord(
                turn_id="t1",
                speaker_id="u1",
                role="user",
                text="Major crashout",
                relative_time="0s",
            )
        ],
    )

    prompt = scorer.build_prompt(req)
    assert "Moderate the dialogue carefully." in prompt
    assert "[Retrieved Dynamic Slang & Context Knowledge]:" in prompt
    assert '"crashout": Violent aggressive fit in gaming.' in prompt
    assert "Conversation:\n[u1] (t1): Major crashout" in prompt


def test_build_default_scorers_rag_options() -> None:
    lex_path = "configs/profanity_lexicon.txt"

    # 1. Standard mode (No RAG)
    std_scorers = build_default_scorers(lex_path, enable_rag=False, rag_compare=False)
    assert any(isinstance(s, PromptedLLMScorer) for s in std_scorers.values())
    assert not any(s.startswith("rag_") for s in std_scorers)

    # 2. RAG enabled
    rag_scorers = build_default_scorers(lex_path, enable_rag=True, rag_compare=False)
    assert any(isinstance(s, RAGPromptedLLMScorer) for s in rag_scorers.values())
    assert any(s.startswith("rag_") for s in rag_scorers)

    # 3. RAG compare mode (both baseline and RAG present)
    compare_scorers = build_default_scorers(lex_path, enable_rag=False, rag_compare=True)
    has_std = any(
        isinstance(s, PromptedLLMScorer) and not isinstance(s, RAGPromptedLLMScorer)
        for s in compare_scorers.values()
    )
    has_rag = any(isinstance(s, RAGPromptedLLMScorer) for s in compare_scorers.values())
    assert has_std
    assert has_rag


def test_generate_rag_impact_report_formatting() -> None:
    data_by_scorer = {
        "prompted_llm_judge": {
            "full_prefix": {"auprc": 0.750, "auroc": 0.820, "f1": 0.720},
            "current_turn_only": {"auprc": 0.600, "auroc": 0.700, "f1": 0.580},
        },
        "rag_prompted_llm_judge": {
            "full_prefix": {"auprc": 0.830, "auroc": 0.880, "f1": 0.790},
            "current_turn_only": {"auprc": 0.710, "auroc": 0.790, "f1": 0.690},
        },
    }
    cache_stats = {
        "cached_entries": 42,
        "cache_hits": 18,
        "cache_misses": 2,
        "tokens_saved": 8500,
        "estimated_cost_usd_saved": 0.0128,
    }

    report = _generate_rag_impact_report(data_by_scorer, cache_stats)
    assert "# Dynamic RAG Impact & Token Efficiency Benchmark Report" in report
    assert "+0.080" in report  # 0.830 - 0.750
    assert "+0.110" in report  # 0.710 - 0.600
    assert "8,500" in report
    assert "90.0%" in report  # hit rate 18 / 20


def test_cli_pipeline_rag_options() -> None:
    runner = CliRunner()
    res = runner.invoke(main, ["pipeline", "--dry-run", "--rag"])
    assert res.exit_code == 0
    assert "RAG: ON" in res.output

    res_compare = runner.invoke(main, ["pipeline", "--dry-run", "--rag-compare"])
    assert res_compare.exit_code == 0
    assert "RAG Compare: ON" in res_compare.output
