"""Unit tests for the Unofficial Urban Dictionary API client and CLI integration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from youth_escalate_bench.cli import main
from youth_escalate_bench.external.urban_dictionary import (
    DEFAULT_API_URL,
    UrbanDefinition,
    UrbanDictionaryClient,
)
from youth_escalate_bench.transforms.algospeak import verify_slang_in_urban_dictionary

MOCK_SEARCH_RESPONSE = {
    "statusCode": 200,
    "term": "yeet",
    "found": True,
    "data": [
        {
            "word": "yeet",
            "meaning": "To discard an item at a high velocity",
            "example": "Alex proceeds to yeet his empty can into the bin.",
            "contributor": "slang_master",
            "date": "2020-01-01",
        },
        {
            "word": "yeeter",
            "meaning": "One who yeets",
            "example": "He is a master yeeter.",
            "contributor": "user2",
            "date": "2020-01-02",
        },
    ],
}

MOCK_RANDOM_RESPONSE = {
    "statusCode": 200,
    "data": [
        {
            "word": "gyatt",
            "meaning": "An exclamation used when seeing an attractive person",
            "example": "Bro saw her and said gyatt",
            "contributor": "zoomer",
            "date": "2023-05-10",
        }
    ],
}


def test_urban_definition_dataclass() -> None:
    defn = UrbanDefinition(
        word="bussin",
        meaning="Extremely good or tasty",
        example="This pizza is bussin",
        contributor="chef",
        date="2022-01-01",
    )
    assert defn.word == "bussin"
    assert defn.meaning == "Extremely good or tasty"
    d = defn.to_dict()
    assert d["word"] == "bussin"
    assert d["example"] == "This pizza is bussin"


def test_client_init_and_url_normalization() -> None:
    client = UrbanDictionaryClient("https://unofficialurbandictionaryapi.com///")
    assert client.base_url == "https://unofficialurbandictionaryapi.com"
    assert client.timeout == 12.0

    client_default = UrbanDictionaryClient()
    assert client_default.base_url == DEFAULT_API_URL.rstrip("/")


@patch.object(UrbanDictionaryClient, "_request")
def test_search_and_strict_filtering(mock_request: MagicMock) -> None:
    mock_request.return_value = MOCK_SEARCH_RESPONSE
    client = UrbanDictionaryClient()

    # Non-strict search: returns both "yeet" and "yeeter"
    results = client.search("yeet", strict=False)
    assert len(results) == 2
    assert results[0].word == "yeet"
    assert results[1].word == "yeeter"

    # Strict search: returns only exact "yeet"
    client_strict = UrbanDictionaryClient()
    strict_results = client_strict.search("yeet", strict=True)
    assert len(strict_results) == 1
    assert strict_results[0].word == "yeet"


@patch.object(UrbanDictionaryClient, "_request")
def test_lookup_and_is_slang_defined(mock_request: MagicMock) -> None:
    mock_request.return_value = MOCK_SEARCH_RESPONSE
    client = UrbanDictionaryClient()

    top_entry = client.lookup("yeet")
    assert top_entry is not None
    assert top_entry.word == "yeet"
    assert "high velocity" in top_entry.meaning

    assert client.is_slang_defined("yeet") is True


@patch.object(UrbanDictionaryClient, "_request")
def test_get_random(mock_request: MagicMock) -> None:
    mock_request.return_value = MOCK_RANDOM_RESPONSE
    client = UrbanDictionaryClient()

    random_defs = client.get_random(limit=1)
    assert len(random_defs) == 1
    assert random_defs[0].word == "gyatt"


@patch.object(UrbanDictionaryClient, "_request")
def test_caching_behavior(mock_request: MagicMock, tmp_path: Path) -> None:
    mock_request.return_value = MOCK_SEARCH_RESPONSE
    client = UrbanDictionaryClient(cache_dir=tmp_path / "urban_cache")

    # First call triggers network _request
    first = client.search("yeet", strict=True)
    assert len(first) == 1
    assert mock_request.call_count == 1

    # Second call uses cache, does not call _request
    second = client.search("yeet", strict=True)
    assert len(second) == 1
    assert mock_request.call_count == 1


@patch.object(UrbanDictionaryClient, "_request")
def test_error_handling_graceful(mock_request: MagicMock) -> None:
    mock_request.return_value = None
    client = UrbanDictionaryClient()

    # Network error or timeout returns empty list without crashing
    res = client.search("error_term")
    assert res == []
    assert client.lookup("error_term") is None
    assert client.is_slang_defined("error_term") is False


@patch.object(UrbanDictionaryClient, "_request")
def test_extract_and_define_slang(mock_request: MagicMock) -> None:
    mock_request.return_value = MOCK_SEARCH_RESPONSE
    client = UrbanDictionaryClient()

    extracted = client.extract_and_define_slang(
        "I just saw him yeet the soda can",
        candidate_words=["yeet"],
    )
    assert "yeet" in extracted
    assert "velocity" in extracted["yeet"]


@patch.object(UrbanDictionaryClient, "_request")
def test_algospeak_helper_integration(mock_request: MagicMock) -> None:
    mock_request.return_value = MOCK_SEARCH_RESPONSE
    client = UrbanDictionaryClient()
    assert verify_slang_in_urban_dictionary("yeet", client=client) is True


@patch.object(UrbanDictionaryClient, "_request")
def test_cli_urban_dict_command(mock_request: MagicMock) -> None:
    mock_request.return_value = MOCK_SEARCH_RESPONSE
    runner = CliRunner()

    result = runner.invoke(main, ["urban-dict", "yeet", "--limit", "1"])
    assert result.exit_code == 0
    assert "Urban Dictionary Results" in result.output
    assert "yeet" in result.output
    assert "high velocity" in result.output


def test_cli_urban_dict_missing_args() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["urban-dict"])
    assert result.exit_code != 0
    assert "Missing argument 'TERM'" in result.output
