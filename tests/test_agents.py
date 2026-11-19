"""Unit tests for autonomous agentic discovery framework and release tooling."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from youth_escalate_bench.agents.generator import GeneratorAgent
from youth_escalate_bench.agents.runner import DiscoveryLoop
from youth_escalate_bench.agents.scout import ScoutAgent, SlangCandidate
from youth_escalate_bench.agents.verifier import VerifierAgent
from youth_escalate_bench.cli import main
from youth_escalate_bench.external.urban_dictionary import UrbanDefinition
from youth_escalate_bench.pii.audit import run_pii_audit
from youth_escalate_bench.snapshot import create_snapshot_bundle


def test_scout_agent_mock() -> None:
    mock_client = MagicMock()
    mock_client.get_random.return_value = [
        UrbanDefinition(word="clapped", meaning="ugly or bad", example="that is clapped"),
    ]
    mock_client.search.return_value = [
        UrbanDefinition(word="bot", meaning="a bad player", example="you are a bot"),
    ]

    scout = ScoutAgent(client=mock_client)
    random_cands = scout.scout_random_slang(limit=1)
    assert len(random_cands) == 1
    assert random_cands[0].term == "clapped"

    targeted_cands = scout.scout_targeted_terms(["bot"])
    assert len(targeted_cands) == 1
    assert targeted_cands[0].term == "bot"


def test_verifier_agent_classifications() -> None:
    verifier = VerifierAgent()

    # 1. Slur / hate speech candidate
    c_slur = SlangCandidate(
        term="testslur",
        meaning="a racial slur against a group",
        example="do not use this term",
        source="mock",
    )
    res_slur = verifier.verify_candidate(c_slur)
    assert res_slur.is_profane_or_toxic
    assert res_slur.severity == 4
    assert "slur_hate_speech" in res_slur.categories

    # 2. Insult candidate
    c_insult = SlangCandidate(
        term="goofball",
        meaning="an annoying idiot or stupid person",
        example="stop being a goofball",
        source="mock",
    )
    res_insult = verifier.verify_candidate(c_insult)
    assert res_insult.is_profane_or_toxic
    assert res_insult.severity == 2
    assert "derogatory_insult" in res_insult.categories

    # 3. Benign youth slang
    c_benign = SlangCandidate(
        term="rizz",
        meaning="charisma or ability to attract someone playfully",
        example="he has unlimited rizz",
        source="mock",
    )
    res_benign = verifier.verify_candidate(c_benign)
    assert not res_benign.is_profane_or_toxic
    assert "benign_youth_slang" in res_benign.categories


def test_generator_agent_contrastive_pairs() -> None:
    gen = GeneratorAgent()
    pair = gen.generate_contrastive_pair("trash", template_idx=0, transform_family="leetspeak")

    assert "trash" in pair.benign_turn
    assert "trash" in pair.hostile_turn
    assert pair.transformed_hostile_turn != pair.hostile_turn
    assert "7r45h" in pair.transformed_hostile_turn or "7" in pair.transformed_hostile_turn

    conv = gen.create_synthetic_conversation("test_conv_1", "clown", is_hostile=True)
    assert len(conv.turns) == 2
    assert "clown" in conv.turns[1].text
    assert conv.metadata["is_hostile"] is True


def test_discovery_loop_run(tmp_path: Path) -> None:
    db_path = tmp_path / "profanity_database.json"
    lex_path = tmp_path / "profanity_lexicon.txt"
    digest_path = tmp_path / "discovery_digest.md"

    lex_path.write_text("trash\nkys\n", encoding="utf-8")

    loop = DiscoveryLoop(
        db_path=db_path,
        lexicon_txt_path=lex_path,
        digest_path=digest_path,
    )
    # Mock scout to return fixed candidate
    loop.scout.scout_targeted_terms = MagicMock(
        return_value=[
            SlangCandidate(
                term="scuzzbag",
                meaning="an offensive derogatory insult for a disgusting person",
                example="you are a scuzzbag",
                source="mock",
            )
        ]
    )
    loop.scout.scout_random_slang = MagicMock(return_value=[])

    res = loop.run_discovery_cycle(target_terms=["scuzzbag"], random_limit=0)
    assert res["candidates_count"] == 1
    assert "scuzzbag" in res["new_terms_added"]
    assert db_path.exists()
    assert digest_path.exists()
    assert "scuzzbag" in digest_path.read_text(encoding="utf-8")


def test_discovery_digest_collapses_consecutive_identical_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "profanity_database.json"
    lex_path = tmp_path / "profanity_lexicon.txt"
    digest_path = tmp_path / "discovery_digest.md"

    lex_path.write_text("trash\nkys\n", encoding="utf-8")

    loop = DiscoveryLoop(
        db_path=db_path,
        lexicon_txt_path=lex_path,
        digest_path=digest_path,
    )
    loop.scout.scout_targeted_terms = MagicMock(return_value=[])
    loop.scout.scout_random_slang = MagicMock(return_value=[])

    timestamps = [
        datetime(2026, 8, 26, 21, 15, 26, tzinfo=UTC),
        datetime(2026, 11, 19, 19, 13, 15, tzinfo=UTC),
        datetime(2026, 11, 19, 19, 15, 26, tzinfo=UTC),
        datetime(2026, 11, 26, 4, 0, 0, tzinfo=UTC),
        datetime(2026, 12, 3, 4, 0, 0, tzinfo=UTC),
    ]

    with patch("youth_escalate_bench.agents.runner.datetime") as mock_dt:
        mock_dt.now.side_effect = [
            timestamps[0],
            timestamps[0],
            timestamps[1],
            timestamps[1],
            timestamps[2],
            timestamps[2],
            timestamps[3],
            timestamps[3],
            timestamps[4],
            timestamps[4],
        ]

        # Run 1: 7 scouted, 0 added
        loop.scout.scout_random_slang = MagicMock(
            return_value=[
                SlangCandidate(term=f"benign_{i}", meaning="friendly greeting", example="yo", source="mock")
                for i in range(7)
            ]
        )
        res_1 = loop.run_discovery_cycle(random_limit=7)
        assert res_1["same_as_previous"] is False

        # Runs 2, 3, 4: 0 scouted, 0 added (identical results)
        loop.scout.scout_random_slang = MagicMock(return_value=[])
        res_2 = loop.run_discovery_cycle(random_limit=15)
        assert res_2["same_as_previous"] is False
        text_after_2 = digest_path.read_text(encoding="utf-8")
        assert "## Discovery Run: `2026-11-19 19:13:15 UTC`" in text_after_2
        assert "same for last" not in text_after_2

        res_3 = loop.run_discovery_cycle(random_limit=15)
        assert res_3["same_as_previous"] is True
        text_after_3 = digest_path.read_text(encoding="utf-8")
        assert "2026-11-19 19:13:15 UTC" not in text_after_3
        assert "## Discovery Run: `2026-11-19 19:15:26 UTC` (same for last 2 runs)" in text_after_3
        assert text_after_3.count("## Discovery Run:") == 2

        res_4 = loop.run_discovery_cycle(random_limit=15)
        assert res_4["same_as_previous"] is True
        text_after_4 = digest_path.read_text(encoding="utf-8")
        assert "2026-11-19 19:15:26 UTC" not in text_after_4
        assert "## Discovery Run: `2026-11-26 04:00:00 UTC` (same for last 3 runs)" in text_after_4
        assert text_after_4.count("## Discovery Run:") == 2

        # Run 5: different result (1 scouted, 0 added) -> new entry appended
        loop.scout.scout_random_slang = MagicMock(
            return_value=[
                SlangCandidate(term="chill", meaning="relaxed", example="stay chill", source="mock")
            ]
        )
        res_5 = loop.run_discovery_cycle(random_limit=1)
        assert res_5["same_as_previous"] is False
        text_after_5 = digest_path.read_text(encoding="utf-8")
        assert "## Discovery Run: `2026-11-26 04:00:00 UTC` (same for last 3 runs)" in text_after_5
        assert "## Discovery Run: `2026-12-03 04:00:00 UTC`" in text_after_5
        assert text_after_5.count("## Discovery Run:") == 3


def test_cli_agent_discover_writes_github_output(tmp_path: Path) -> None:
    gh_output = tmp_path / "github_output.txt"
    runner = CliRunner()

    mock_result = {
        "timestamp": "2026-11-19T00:00:00+00:00",
        "candidates_count": 0,
        "new_terms_added": [],
        "contrastive_pairs_count": 0,
        "same_as_previous": True,
    }
    with patch("youth_escalate_bench.agents.runner.DiscoveryLoop") as mock_loop_cls:
        mock_loop_cls.return_value.run_discovery_cycle.return_value = mock_result
        res = runner.invoke(
            main,
            ["agent-discover", "--random-limit", "0"],
            env={"GITHUB_OUTPUT": str(gh_output)},
        )

    assert res.exit_code == 0
    assert "Same as Previous   : True" in res.output
    assert gh_output.read_text(encoding="utf-8") == "same_as_previous=true\n"


def test_pii_audit_module(tmp_path: Path) -> None:
    test_parquet = Path("data/processed/split/split_test.parquet")
    if test_parquet.exists():
        res = run_pii_audit(test_parquet, sample_size=10)
        assert res["status"] in ("passed", "warning")
        assert res["sample_size"] > 0


def test_snapshot_bundle_creation(tmp_path: Path) -> None:
    out_dir = tmp_path / "snapshots"
    res = create_snapshot_bundle(output_dir=out_dir, version_tag="test.Q1")
    assert res["status"] == "success"
    assert Path(res["archive_path"]).exists()
    assert len(res["sha256"]) == 64


def test_cli_agent_and_snapshot_commands() -> None:
    runner = CliRunner()

    res_pii = runner.invoke(main, ["audit-pii", "--sample-size", "5"])
    assert res_pii.exit_code == 0
    assert "PII Spot-Check Result" in res_pii.output


def test_pii_audit_nonexistent_dataset_graceful(tmp_path: Path) -> None:
    """Verify run_pii_audit on nonexistent file returns error dict with flag_count without raising KeyError."""
    res = run_pii_audit(tmp_path / "non_existent_dataset.parquet")
    assert res["status"] == "error"
    assert "flag_count" in res
    assert res["flag_count"] == 0
    assert res["total_turns"] == 0
