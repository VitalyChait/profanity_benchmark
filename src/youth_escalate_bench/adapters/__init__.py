"""Adapter registry for dataset ingest."""

from __future__ import annotations

from typing import Any

from youth_escalate_bench.adapters.base import IngestAdapter
from youth_escalate_bench.adapters.cad import CADAdapter
from youth_escalate_bench.adapters.convotox import ConvoToxAdapter
from youth_escalate_bench.adapters.fixture import FixtureAdapter
from youth_escalate_bench.adapters.gametox import GameToxAdapter
from youth_escalate_bench.adapters.generic import GenericConversationAdapter
from youth_escalate_bench.adapters.joiner import FlatToMultiTurnJoiner
from youth_escalate_bench.adapters.wikiconv import WikiConvAdapter

ADAPTERS: dict[str, IngestAdapter] = {
    "wikiconv_wikidetox": WikiConvAdapter(),
    "contextual_abuse_dataset": CADAdapter(),
    "convotox": ConvoToxAdapter(),
    "gametox": GameToxAdapter(),
    "davidson": FlatToMultiTurnJoiner(source_id="davidson", platform_style="group_chat"),
    "minorbench": GenericConversationAdapter(source_id="minorbench"),
    "wildchat": GenericConversationAdapter(source_id="wildchat"),
    "lmsys_chat_1m": GenericConversationAdapter(source_id="lmsys_chat_1m"),
    "personachat": GenericConversationAdapter(source_id="personachat"),
    "generic": GenericConversationAdapter(),
    "generic_conversation": GenericConversationAdapter(),
    "flat_joiner": FlatToMultiTurnJoiner(),
    "fixture": FixtureAdapter(),
    "fixture_wikiconv": FixtureAdapter(),
    "fixture_cad": FixtureAdapter(),
}


def get_adapter(source_id: str, **kwargs: Any) -> IngestAdapter:
    """Retrieve adapter by source ID with fallback to GenericConversationAdapter."""
    if source_id in ADAPTERS:
        return ADAPTERS[source_id]
    # Fallback to Generic adapter dynamically for any unknown source_id
    return GenericConversationAdapter(source_id=source_id, **kwargs)
