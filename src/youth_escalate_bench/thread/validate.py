"""Conversation topology validation."""

from dataclasses import dataclass

from youth_escalate_bench.schemas.conversation import ConversationRecord


@dataclass
class TopologyIssue:
    conversation_id: str
    issue: str
    turn_id: str | None = None


def validate_topology(conv: ConversationRecord) -> list[TopologyIssue]:
    issues: list[TopologyIssue] = []
    turn_ids = conv.ordered_turn_ids()
    turn_set = set(turn_ids)

    for turn in conv.turns:
        if turn.parent_turn_id is not None:
            if turn.parent_turn_id not in turn_set:
                issues.append(
                    TopologyIssue(
                        conv.conversation_id,
                        "parent_turn_id references missing turn",
                        turn.turn_id,
                    )
                )
            elif turn.parent_turn_id == turn.turn_id:
                issues.append(
                    TopologyIssue(conv.conversation_id, "self-referential parent", turn.turn_id)
                )
            else:
                parent_idx = turn_ids.index(turn.parent_turn_id)
                child_idx = turn_ids.index(turn.turn_id)
                if parent_idx >= child_idx:
                    issues.append(
                        TopologyIssue(
                            conv.conversation_id,
                            "parent appears after child in turn order",
                            turn.turn_id,
                        )
                    )

    return issues


def validate_all(conversations: list[ConversationRecord]) -> list[TopologyIssue]:
    all_issues: list[TopologyIssue] = []
    for conv in conversations:
        all_issues.extend(validate_topology(conv))
    return all_issues
