"""Unit tests for misclassification difficulty ranking and priority evaluation sampling."""

from pathlib import Path
from unittest.mock import MagicMock

from click.testing import CliRunner

from youth_escalate_bench.cli import main
from youth_escalate_bench.evaluation.conditions import ContextCondition
from youth_escalate_bench.evaluation.difficulty import (
    DifficultyIndex,
    SentenceRanking,
    WordRanking,
    compute_difficulty_index,
    generate_difficulty_markdown_report,
    load_difficulty_index,
    save_difficulty_index,
    score_request_difficulty,
)
from youth_escalate_bench.evaluation.runner import (
    PredictionRow,
    run_evaluation,
)
from youth_escalate_bench.schemas.conversation import (
    ConversationRecord,
    SourceTier,
    StoredTurn,
)
from youth_escalate_bench.schemas.inference import ModelOutput


def _create_sample_conversations() -> list[ConversationRecord]:
    return [
        ConversationRecord(
            conversation_id="conv_hard_1",
            source_id="synthetic",
            source_tier=SourceTier.SYNTHETIC,
            platform_style="direct_messaging",
            turns=[
                StoredTurn(
                    turn_id="t1",
                    speaker_id="u1",
                    role="user",
                    relative_time="0s",
                    text="i will find you after school",
                ),
            ],
        ),
        ConversationRecord(
            conversation_id="conv_easy_2",
            source_id="synthetic",
            source_tier=SourceTier.SYNTHETIC,
            platform_style="direct_messaging",
            turns=[
                StoredTurn(
                    turn_id="t1",
                    speaker_id="u2",
                    role="user",
                    relative_time="0s",
                    text="hello friend how are you",
                ),
            ],
        ),
        ConversationRecord(
            conversation_id="conv_fp_3",
            source_id="synthetic",
            source_tier=SourceTier.SYNTHETIC,
            platform_style="gaming_chat",
            turns=[
                StoredTurn(
                    turn_id="t1",
                    speaker_id="u3",
                    role="user",
                    relative_time="0s",
                    text="why did he say kys in quote",
                ),
            ],
        ),
    ]


def test_compute_difficulty_index() -> None:
    conversations = _create_sample_conversations()
    labels = {
        ("conv_hard_1", "t1"): True,  # Gold actionable
        ("conv_easy_2", "t1"): False,  # Gold benign
        ("conv_fp_3", "t1"): False,  # Gold benign
    }

    # Model 1 and Model 2 predictions
    predictions = [
        # conv_hard_1: Both models miss it (False Negative)
        PredictionRow("conv_hard_1", "t1", "model_a", "current_turn_only", 0.1, False),
        PredictionRow("conv_hard_1", "t1", "model_b", "current_turn_only", 0.2, False),
        # conv_easy_2: Both models correctly predict safe
        PredictionRow("conv_easy_2", "t1", "model_a", "current_turn_only", 0.05, False),
        PredictionRow("conv_easy_2", "t1", "model_b", "current_turn_only", 0.02, False),
        # conv_fp_3: Model A over-moderates (False Positive)
        PredictionRow("conv_fp_3", "t1", "model_a", "current_turn_only", 0.9, True),
        PredictionRow("conv_fp_3", "t1", "model_b", "current_turn_only", 0.4, False),
    ]

    index = compute_difficulty_index(predictions, labels, conversations)

    assert len(index.sentences) == 3
    # Top hardest sentence should be conv_hard_1 (100% error rate, false negative on harm)
    top = index.sentences[0]
    assert top.conversation_id == "conv_hard_1"
    assert top.error_rate == 1.0
    assert top.total_errors == 2
    assert "False Negative" in top.primary_error_type

    # conv_fp_3 should have 50% error rate and be identified as False Positive
    fp_turn = next(s for s in index.sentences if s.conversation_id == "conv_fp_3")
    assert fp_turn.error_rate == 0.5
    assert fp_turn.false_positive_count == 1
    assert "False Positive" in fp_turn.primary_error_type

    # Verify word rankings
    words_dict = {w.word: w for w in index.words}
    assert "school" in words_dict
    assert words_dict["school"].primary_failure_mode == "false_negative_indicator"
    assert "kys" in words_dict
    assert words_dict["kys"].primary_failure_mode == "false_positive_trigger"


def test_roundtrip_save_and_load(tmp_path: Path) -> None:
    index = DifficultyIndex(
        sentences=[
            SentenceRanking(
                conversation_id="c1",
                turn_id="t1",
                turn_text="example text",
                gold_actionable=True,
                total_evaluations=4,
                total_errors=3,
                error_rate=0.75,
                priority_weight=1.2,
            )
        ],
        words=[
            WordRanking(
                word="slang",
                vulnerability_score=0.85,
                total_occurrences=2,
                error_occurrences=2,
                fp_occurrences=0,
                fn_occurrences=2,
                error_rate=1.0,
                primary_failure_mode="false_negative_indicator",
            )
        ],
        metadata={"total_evaluated_turns": 1},
    )

    save_path = tmp_path / "difficulty_ranking.yaml"
    save_difficulty_index(index, save_path)
    assert save_path.exists()

    loaded = load_difficulty_index(save_path)
    assert loaded is not None
    assert len(loaded.sentences) == 1
    assert loaded.sentences[0].conversation_id == "c1"
    assert loaded.sentences[0].priority_weight == 1.2
    assert len(loaded.words) == 1
    assert loaded.words[0].word == "slang"


def test_score_request_difficulty() -> None:
    index = DifficultyIndex(
        sentences=[
            SentenceRanking(
                conversation_id="c1",
                turn_id="t1",
                turn_text="test text",
                gold_actionable=True,
                priority_weight=1.5,
            )
        ],
        words=[
            WordRanking(
                word="toxic",
                vulnerability_score=0.9,
                total_occurrences=5,
                error_occurrences=4,
                fp_occurrences=4,
                fn_occurrences=0,
                error_rate=0.8,
                primary_failure_mode="false_positive_trigger",
            )
        ],
    )

    # Turn in index: receives base weight 1.5
    score1 = score_request_difficulty(index, "c1", "t1", "clean text")
    assert score1 >= 1.5

    # New turn containing vulnerable word "toxic" receives word vulnerability boost
    score2 = score_request_difficulty(index, "c99", "t1", "this is so toxic")
    assert score2 > 0.0


def test_priority_sampling_in_run_evaluation() -> None:
    conversations = _create_sample_conversations()
    labels = {
        ("conv_hard_1", "t1"): True,
        ("conv_easy_2", "t1"): False,
        ("conv_fp_3", "t1"): False,
    }

    # Pre-built difficulty index marking conv_hard_1 as high priority
    diff_index = DifficultyIndex(
        sentences=[
            SentenceRanking(
                conversation_id="conv_hard_1",
                turn_id="t1",
                turn_text="i will find you",
                gold_actionable=True,
                priority_weight=2.5,
            ),
            SentenceRanking(
                conversation_id="conv_easy_2",
                turn_id="t1",
                turn_text="hello friend",
                gold_actionable=False,
                priority_weight=0.0,
            ),
        ]
    )

    mock_scorer = MagicMock()
    mock_scorer.predict.return_value = ModelOutput(
        harm_probability=0.1,
        is_harmful=False,
        actionable=False,
        severity_probabilities={"benign": 0.9, "actionable": 0.1, "urgent": 0.0},
    )

    # Run evaluation with max_samples = 1 and priority sampling enabled
    bundle = run_evaluation(
        conversations=conversations,
        scorers={"mock_model": mock_scorer},
        labels=labels,
        conditions=[ContextCondition.CURRENT_TURN_ONLY],
        max_samples=1,
        difficulty_index=diff_index,
        prioritize_hard_samples=True,
    )

    # Only 1 sample evaluated: it MUST be the hard sample conv_hard_1!
    assert len(bundle.predictions) == 1
    assert bundle.predictions[0].conversation_id == "conv_hard_1"
    assert bundle.difficulty_index is not None


def test_generate_difficulty_markdown_report() -> None:
    index = DifficultyIndex(
        sentences=[
            SentenceRanking(
                conversation_id="c1",
                turn_id="t1",
                turn_text="you are dead",
                gold_actionable=True,
                total_evaluations=2,
                total_errors=2,
                error_rate=1.0,
                primary_error_type="False Negative",
                priority_weight=1.5,
            )
        ],
        words=[
            WordRanking(
                word="dead",
                vulnerability_score=1.1,
                total_occurrences=3,
                error_occurrences=3,
                fp_occurrences=0,
                fn_occurrences=3,
                error_rate=1.0,
                primary_failure_mode="false_negative_indicator",
            )
        ],
        metadata={"total_evaluated_turns": 1, "total_misclassified_turns": 1},
    )

    md = generate_difficulty_markdown_report(index)
    assert "# Internal Evaluation Difficulty" in md
    assert "Top Misclassified Sentences" in md
    assert "dead" in md


def test_cli_difficulty_ranking_command(tmp_path: Path) -> None:
    index = DifficultyIndex(
        sentences=[
            SentenceRanking(
                conversation_id="c1",
                turn_id="t1",
                turn_text="sample text",
                gold_actionable=True,
                total_evaluations=2,
                total_errors=1,
                error_rate=0.5,
                primary_error_type="False Positive",
                priority_weight=0.8,
            )
        ],
        words=[
            WordRanking(
                word="sample",
                vulnerability_score=0.5,
                total_occurrences=1,
                error_occurrences=1,
                fp_occurrences=1,
                fn_occurrences=0,
                error_rate=1.0,
                primary_failure_mode="false_positive_trigger",
            )
        ],
        metadata={"total_evaluated_turns": 1, "total_misclassified_turns": 1},
    )
    ranking_file = tmp_path / "difficulty_ranking.yaml"
    save_difficulty_index(index, ranking_file)

    runner = CliRunner()
    res = runner.invoke(main, ["difficulty-ranking", "--path", str(ranking_file)])
    assert res.exit_code == 0
    assert "Internal Evaluation Difficulty Ranking" in res.output
    assert "sample" in res.output


def test_score_request_difficulty_algospeak_and_covert() -> None:
    index = DifficultyIndex()

    # Plain clean text has baseline 0 difficulty
    score_clean = score_request_difficulty(index, "c0", "t0", "good game team well played")

    # Algospeak delimiter / leetspeak turn has significantly higher difficulty
    score_algospeak = score_request_difficulty(
        index, "c1", "t1", "k.y.5 y0u u53l355 p13c3 0f g4rb4g3", difficulty_level="hard"
    )
    assert score_algospeak > score_clean
    assert score_algospeak >= 0.50

    # Covert non-profane hostility receives high difficulty boost
    score_covert = score_request_difficulty(
        index, "c2", "t2", "nobody in this discord wanted you here, just leave", difficulty_level="hard"
    )
    assert score_covert > score_clean

    # Benign intense hype swear words (over-moderation stress test)
    score_hype = score_request_difficulty(
        index, "c3", "t3", "holy fucking shit you hit that cross-map snipe!", difficulty_level="hard"
    )
    assert score_hype > score_clean

    # Extreme difficulty level scales up difficulty further
    score_extreme = score_request_difficulty(
        index, "c1", "t1", "k.y.5 y0u u53l355 p13c3 0f g4rb4g3", difficulty_level="extreme"
    )
    assert score_extreme > score_algospeak


def test_synthetic_generator_difficulty_tiers() -> None:
    from youth_escalate_bench.generation.generator import SyntheticDialogueGenerator

    gen_hard = SyntheticDialogueGenerator(seed=42, difficulty_level="hard")
    plans = [
        {
            "plan_id": f"test_{i}",
            "template_id": "adversarial_algospeak_bypass" if i % 2 == 0 else "false_positive_hype_banter",
            "platform_style": "gaming_chat",
            "transition_pattern": "algospeak_obfuscation" if i % 2 == 0 else "intense_hype_false_alarm",
            "intended_harm_type": "targeted_insult" if i % 2 == 0 else None,
            "turns_min": 4,
            "turns_max": 6,
            "difficulty_level": "hard",
        }
        for i in range(10)
    ]

    all_turns = []
    for p in plans:
        conv, anns = gen_hard.generate_conversation(p)
        assert len(conv.turns) >= 4
        all_turns.extend([t.text for t in conv.turns])

    # High diversity: many unique turns generated across plans
    assert len(set(all_turns)) >= 15


def test_cli_pipeline_difficulty_level_argument() -> None:
    runner = CliRunner()
    res = runner.invoke(main, ["pipeline", "--dry-run", "--difficulty-level", "hard"])
    assert res.exit_code == 0
    assert "DRY RUN" in res.output

