"""Unit tests for trusted profanity sources ingestion and unified database."""

from pathlib import Path

from click.testing import CliRunner

from youth_escalate_bench.cli import main
from youth_escalate_bench.external.profanity_sources import (
    CURATED_ALGOSPEAK_TERMS,
    CURATED_GAMING_TOXICITY_TERMS,
    CURATED_URBAN_SLANG_TERMS,
    ProfanityDatabase,
    ProfanityTerm,
    parse_badwords_json,
    parse_dsojevic_json,
    parse_google_list,
    parse_hatecheck_placeholders,
    parse_hurtlex_tsv,
    parse_ldnoobw_list,
    sync_lexicon_files,
)


def test_parse_google_list() -> None:
    raw = "ass\n# comment\nbadword\n\n"
    terms = parse_google_list(raw)
    assert len(terms) == 2
    assert terms[0].word == "ass"
    assert terms[0].sources == ["google_profanity_words"]
    assert terms[0].severity == 2


def test_parse_ldnoobw_list() -> None:
    raw = "bitch\nasshole\n"
    terms = parse_ldnoobw_list(raw)
    assert len(terms) == 2
    assert terms[1].word == "asshole"
    assert terms[1].sources == ["ldnoobw"]


def test_parse_dsojevic_json() -> None:
    raw = """[
      {
        "id": "bad-term",
        "match": "bad-term|bad term",
        "tags": ["sexual", "shock"],
        "severity": 3
      }
    ]"""
    terms = parse_dsojevic_json(raw)
    assert len(terms) == 1
    assert terms[0].word == "bad-term"
    assert terms[0].severity == 3
    assert "sexual" in terms[0].categories
    assert "bad term" in terms[0].match_patterns


def test_parse_hatecheck_placeholders() -> None:
    raw = """Placeholder,Values
[SLUR_S],"slur1, slur2"
[SLUR_S_leet],"slur1leet"
[IDENTITY_S],"person"
"""
    terms = parse_hatecheck_placeholders(raw)
    assert len(terms) == 3
    assert terms[0].word == "slur1"
    assert terms[0].severity == 4
    assert "slur_hate_speech" in terms[0].categories
    assert "leetspeak_evasion" in terms[2].categories


def test_parse_hurtlex_tsv() -> None:
    raw = """id\tpos\tcategory\tstereotype\tlemma\tlevel
EN1\tn\tcds\tno\tdumbass\tconservative
EN2\tn\tasm\tno\tracist_slur\tconservative
EN3\tn\tqas\tno\tneutralword\tinclusive
"""
    terms = parse_hurtlex_tsv(raw)
    assert len(terms) == 2
    assert terms[0].word == "dumbass"
    assert terms[0].severity == 3
    assert terms[1].word == "racist_slur"
    assert terms[1].severity == 4


def test_parse_badwords_json() -> None:
    raw = """["badword1", "badword2"]"""
    terms = parse_badwords_json(raw)
    assert len(terms) == 2
    assert terms[0].word == "badword1"
    assert terms[0].sources == ["badwords_en"]


def test_curated_profanity_sources_structure() -> None:
    assert len(CURATED_ALGOSPEAK_TERMS) >= 20
    assert "unalive" in CURATED_ALGOSPEAK_TERMS
    assert CURATED_ALGOSPEAK_TERMS["unalive"][0] == 3

    assert len(CURATED_GAMING_TOXICITY_TERMS) >= 15
    assert "dogwater" in CURATED_GAMING_TOXICITY_TERMS
    assert "uninstall" in CURATED_GAMING_TOXICITY_TERMS

    assert len(CURATED_URBAN_SLANG_TERMS) >= 10
    assert "deadass" in CURATED_URBAN_SLANG_TERMS



def test_profanity_database_operations(tmp_path: Path) -> None:
    db = ProfanityDatabase(
        {
            "trash": ProfanityTerm(
                word="trash",
                severity=3,
                categories=["derogatory_insult"],
                sources=["bench_seeds"],
            ),
            "fag": ProfanityTerm(
                word="fag",
                severity=4,
                categories=["slur_hate_speech"],
                sources=["hatecheck", "dsojevic"],
            ),
        }
    )

    assert db.is_profane("trash")
    assert db.is_profane("TRASH")
    assert not db.is_profane("flower")
    assert db.get_severity("trash") == 3
    assert db.get_severity("fag") == 4
    assert db.get_severity("flower") == 0

    stats = db.stats()
    assert stats["total_terms"] == 2
    assert stats["by_severity"][3] == 1
    assert stats["by_severity"][4] == 1

    # Roundtrip save/load
    db_file = tmp_path / "test_db.json"
    db.save_json(db_file)
    loaded = ProfanityDatabase.load_json(db_file)
    assert loaded.is_profane("trash")
    assert loaded.get_severity("fag") == 4


def test_sync_lexicon_files(tmp_path: Path) -> None:
    seed_file = tmp_path / "seeds.txt"
    seed_file.write_text("trash\nkys\n", encoding="utf-8")

    db = ProfanityDatabase(
        {
            "trash": ProfanityTerm("trash", severity=3, sources=["bench_seeds"]),
            "kys": ProfanityTerm("kys", severity=3, sources=["bench_seeds"]),
            "newprofanity": ProfanityTerm("newprofanity", severity=2, sources=["google"]),
        }
    )

    lexicon_out = tmp_path / "profanity_lexicon.txt"
    db_out = tmp_path / "db.json"

    seeds_count, total = sync_lexicon_files(
        db=db,
        lexicon_txt_path=lexicon_out,
        database_json_path=db_out,
        original_seed_path=seed_file,
    )

    assert seeds_count == 2
    assert total == 3
    assert lexicon_out.exists()
    assert db_out.exists()

    content = lexicon_out.read_text(encoding="utf-8")
    # Verify seed words appear before ingested sources
    trash_pos = content.find("trash")
    new_pos = content.find("newprofanity")
    assert trash_pos < new_pos


def test_cli_profanity_commands() -> None:
    runner = CliRunner()

    res1 = runner.invoke(main, ["lexicon-stats"])
    assert res1.exit_code == 0
    assert "Unified Profanity Lexicon Statistics" in res1.output
    assert "Total Unique Terms" in res1.output

    res2 = runner.invoke(main, ["profanity-check", "trash"])
    assert res2.exit_code == 0
    assert "Term        : trash" in res2.output

    res3 = runner.invoke(main, ["profanity-check", "nonexistentwordxyz123"])
    assert res3.exit_code == 0
    assert "NOT in the unified profanity database" in res3.output
