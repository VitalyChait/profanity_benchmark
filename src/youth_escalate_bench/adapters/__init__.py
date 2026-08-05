"""Adapter registry."""

from youth_escalate_bench.adapters.base import IngestAdapter
from youth_escalate_bench.adapters.cad import CADAdapter
from youth_escalate_bench.adapters.fixture import FixtureAdapter
from youth_escalate_bench.adapters.wikiconv import WikiConvAdapter

ADAPTERS: dict[str, IngestAdapter] = {
    "wikiconv_wikidetox": WikiConvAdapter(),
    "contextual_abuse_dataset": CADAdapter(),
    "fixture": FixtureAdapter(),
    "fixture_wikiconv": FixtureAdapter(),
    "fixture_cad": FixtureAdapter(),
}


def get_adapter(source_id: str) -> IngestAdapter:
    if source_id not in ADAPTERS:
        raise ValueError(f"No adapter for source_id={source_id}")
    return ADAPTERS[source_id]
