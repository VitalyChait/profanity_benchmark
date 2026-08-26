"""Unit tests for autonomous agentic discovery framework and release tooling."""

from pathlib import Path
from unittest.mock import MagicMock

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
    loop.scout.scout_targeted_terms = MagicMock(return_value=[
        SlangCandidate(
            term="scuzzbag",
            meaning="an offensive derogatory insult for a disgusting person",
            example="you are a scuzzbag",
            source="mock",
        )
    ])
    loop.scout.scout_random_slang = MagicMock(return_value=[])

    res = loop.run_discovery_cycle(target_terms=["scuzzbag"], random_limit=0)
    assert res["candidates_count"] == 1
    assert "scuzzbag" in res["new_terms_added"]
    assert db_path.exists()
    assert digest_path.exists()
    assert "scuzzbag" in digest_path.read_text(encoding="utf-8")


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
