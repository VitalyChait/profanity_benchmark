"""Split leakage detection tests."""

from youth_escalate_bench.schemas.conversation import ConversationRecord, SourceTier, StoredTurn
from youth_escalate_bench.split.leakage import check_split_leakage


def _conv(id_: str, text: str = "hello") -> ConversationRecord:
    return ConversationRecord(
        conversation_id=id_,
        source_id="fixture",
        source_tier=SourceTier.FIXTURE,
        platform_style="gaming_chat",
        turns=[
            StoredTurn(turn_id="t1", speaker_id="s", role="peer", text=text, relative_time="t0")
        ],
    )


def test_no_leakage_clean_splits():
    splits = {
        "train": [_conv("c1", "hello one"), _conv("c2", "hello two")],
        "test": [_conv("c3", "hello three")],
    }
    findings = check_split_leakage(splits)
    overlap = [f for f in findings if "overlap" in f.kind]
    assert len(overlap) == 0


def test_detects_id_overlap():
    splits = {
        "train": [_conv("c1")],
        "test": [_conv("c1")],
    }
    findings = check_split_leakage(splits)
    assert any(f.kind == "conversation_id_overlap" for f in findings)
