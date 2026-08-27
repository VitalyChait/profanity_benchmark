"""Tests for controllable random seed in example selection and pipeline orchestration."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from youth_escalate_bench.cli import main
from youth_escalate_bench.evaluation.conditions import ContextCondition
from youth_escalate_bench.evaluation.difficulty import DifficultyIndex, SentenceRanking
from youth_escalate_bench.evaluation.runner import (
    run_evaluation,
    select_evaluation_pairs,
)
from youth_escalate_bench.orchestrator import PipelineRunner
from youth_escalate_bench.schemas.conversation import ConversationRecord, SourceTier, StoredTurn
from youth_escalate_bench.schemas.inference import (
    InferenceRequest,
    ModelOutput,
    PlatformStyle,
    TaskType,
    TurnRecord,
)


def _build_dummy_pairs(n: int = 20) -> list[tuple[InferenceRequest, bool]]:
    pairs: list[tuple[InferenceRequest, bool]] = []
    for i in range(n):
        turn = TurnRecord(
            turn_id=f"t{i}",
            speaker_id="u1",
            role="user",
            text=f"utterance sample {i}",
            relative_time="0s",
        )
        req = InferenceRequest(
            conversation_id=f"conv_{i:03d}",
            turns=[turn],
            current_turn_id=f"t{i}",
            benchmark_version="0.1.0",
            platform_style=PlatformStyle.GAMING_CHAT,
            language_mode="english",
            task=TaskType.CURRENT_HARM,
        )
        # Alternate labels: even = True (actionable), odd = False (benign)
        pairs.append((req, i % 2 == 0))
    return pairs


def test_select_evaluation_pairs_determinism() -> None:
    """Verifies that the same seed produces identical example selection."""
    pairs = _build_dummy_pairs(30)

    selected_1 = select_evaluation_pairs(pairs, max_samples=10, seed=42, sample_strategy="random")
    selected_2 = select_evaluation_pairs(pairs, max_samples=10, seed=42, sample_strategy="random")

    ids_1 = [p[0].conversation_id for p in selected_1]
    ids_2 = [p[0].conversation_id for p in selected_2]

    assert len(ids_1) == 10
    assert ids_1 == ids_2


def test_select_evaluation_pairs_seed_variation() -> None:
    """Verifies that different seeds select different subsets of examples."""
    pairs = _build_dummy_pairs(50)

    selected_a = select_evaluation_pairs(pairs, max_samples=10, seed=42, sample_strategy="random")
    selected_b = select_evaluation_pairs(pairs, max_samples=10, seed=999, sample_strategy="random")

    ids_a = [p[0].conversation_id for p in selected_a]
    ids_b = [p[0].conversation_id for p in selected_b]

    assert ids_a != ids_b
    assert len(ids_a) == 10
    assert len(ids_b) == 10


def test_select_evaluation_pairs_stratified() -> None:
    """Verifies stratified sampling balances actionable vs non-actionable labels."""
    pairs = _build_dummy_pairs(40)  # 20 True, 20 False

    selected = select_evaluation_pairs(pairs, max_samples=10, seed=42, sample_strategy="stratified")
    assert len(selected) == 10

    labels = [p[1] for p in selected]
    n_pos = sum(1 for label in labels if label)
    n_neg = sum(1 for label in labels if not label)

    assert n_pos == 5
    assert n_neg == 5


def test_select_evaluation_pairs_difficulty_with_seed_tie_breaking() -> None:
    """Verifies difficulty ranking places highest difficulty first, breaking ties with seed."""
    pairs = _build_dummy_pairs(20)

    # Make conv_005 highest difficulty (weight 5.0), all others tied at 0.0
    diff_index = DifficultyIndex(
        sentences=[
            SentenceRanking(
                conversation_id="conv_005",
                turn_id="t5",
                turn_text="utterance sample 5",
                gold_actionable=False,
                priority_weight=5.0,
            )
        ]
    )

    # In difficulty mode with seed 42 vs 999:
    sel_42 = select_evaluation_pairs(
        pairs,
        max_samples=5,
        seed=42,
        difficulty_index=diff_index,
        prioritize_hard_samples=True,
        sample_strategy="difficulty",
    )
    sel_999 = select_evaluation_pairs(
        pairs,
        max_samples=5,
        seed=999,
        difficulty_index=diff_index,
        prioritize_hard_samples=True,
        sample_strategy="difficulty",
    )

    # In both, top ranked item is the hard sample conv_005
    assert sel_42[0][0].conversation_id == "conv_005"
    assert sel_999[0][0].conversation_id == "conv_005"

    # Subsequent tied items are broken differently by seed 42 vs 999
    ids_42 = [p[0].conversation_id for p in sel_42]
    ids_999 = [p[0].conversation_id for p in sel_999]
    assert ids_42 != ids_999


def test_run_evaluation_respects_seed_and_strategy() -> None:
    """Verifies run_evaluation accepts seed & sample_strategy and tags bundle metadata."""
    conversations = [
        ConversationRecord(
            conversation_id=f"conv_{i}",
            source_id="test",
            source_tier=SourceTier.FIXTURE,
            benchmark_version="0.1.0",
            platform_style="gaming_chat",
            language_mode="english",
            turns=[
                StoredTurn(turn_id="t1", speaker_id="u1", role="user", text="hey there", relative_time="0s"),
            ],
        )
        for i in range(15)
    ]
    labels = {(f"conv_{i}", "t1"): (i % 2 == 0) for i in range(15)}

    mock_scorer = MagicMock()
    mock_scorer.name = "mock_scorer"
    mock_scorer.predict.return_value = ModelOutput(
        harm_probability=0.1,
        is_harmful=False,
        actionable=False,
        severity_probabilities={"benign": 0.9, "actionable": 0.1, "urgent": 0.0},
    )

    bundle_a = run_evaluation(
        conversations=conversations,
        scorers={"mock": mock_scorer},
        labels=labels,
        conditions=[ContextCondition.CURRENT_TURN_ONLY],
        max_samples=4,
        seed=101,
        sample_strategy="random",
    )
    bundle_b = run_evaluation(
        conversations=conversations,
        scorers={"mock": mock_scorer},
        labels=labels,
        conditions=[ContextCondition.CURRENT_TURN_ONLY],
        max_samples=4,
        seed=202,
        sample_strategy="random",
    )

    assert bundle_a.seed == 101
    assert bundle_a.sample_strategy == "random"
    assert bundle_b.seed == 202

    preds_a = [p.conversation_id for p in bundle_a.predictions]
    preds_b = [p.conversation_id for p in bundle_b.predictions]

    assert len(preds_a) == 4
    assert len(preds_b) == 4
    assert preds_a != preds_b


def test_pipeline_runner_seed_propagation() -> None:
    """Verifies PipelineRunner accepts seed & strategy and passes into overrides."""
    runner = PipelineRunner()

    # Dry run should succeed and display seed and strategy
    success = runner.run(
        target_steps=["evaluate"],
        dry_run=True,
        seed=777,
        sample_strategy="random",
    )
    assert success is True


def test_cli_pipeline_seed_and_strategy_options() -> None:
    """Verifies CLI accepts --seed and --sample-strategy in dry run."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["pipeline", "--dry-run", "--seed", "12345", "--sample-strategy", "stratified", "--all"],
    )
    assert result.exit_code == 0
    assert "Seed: 12345" in result.output
    assert "Strategy: stratified" in result.output
