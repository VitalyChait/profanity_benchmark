"""Functional and diagnostic minimal-pair generator (HateCheck style for youth discourse)."""

from dataclasses import dataclass, field
from enum import StrEnum

from youth_escalate_bench.schemas.conversation import ConversationRecord, SourceTier, StoredTurn
from youth_escalate_bench.schemas.labels import (
    AnnotationRecord,
    HarmType,
    PragmaticUse,
    ProfanityForm,
    Severity,
    TargetType,
)


class DiagnosticCategory(StrEnum):
    BANTER_VS_ABUSE = "banter_vs_abuse"
    TARGETED_VS_UNTARGETED = "targeted_vs_untargeted"
    QUOTATION_VS_ENDORSEMENT = "quotation_vs_endorsement"
    RECLAIMED_VS_SLUR = "reclaimed_vs_slur"
    NEGATION_COUNTERSPEECH = "negation_counterspeech"
    CODE_SWITCH_CONTRAST = "code_switch_contrast"


@dataclass
class MinimalPair:
    pair_id: str
    category: DiagnosticCategory
    benign_text: str
    harmful_text: str
    shared_trigger_words: list[str] = field(default_factory=list)
    benign_pragmatic_use: PragmaticUse = PragmaticUse.AFFILIATIVE_BANTER
    harmful_pragmatic_use: PragmaticUse = PragmaticUse.TARGETED_ABUSE
    harm_types: list[HarmType] = field(default_factory=lambda: [HarmType.TARGETED_INSULT])
    context_prefix: list[str] = field(default_factory=list)


DEFAULT_MINIMAL_PAIRS: list[MinimalPair] = [
    # 1. Banter vs. Abuse
    MinimalPair(
        pair_id="mp_banter_01",
        category=DiagnosticCategory.BANTER_VS_ABUSE,
        benign_text="bro you're fucking crazy lmao that trickshot was unreal",
        harmful_text="bro you're fucking useless trash uninstall the game",
        shared_trigger_words=["fucking", "bro"],
        benign_pragmatic_use=PragmaticUse.AFFILIATIVE_BANTER,
        harmful_pragmatic_use=PragmaticUse.TARGETED_ABUSE,
        harm_types=[HarmType.TARGETED_INSULT],
        context_prefix=["yo watch this play", "clip that clip that!"],
    ),
    MinimalPair(
        pair_id="mp_banter_02",
        category=DiagnosticCategory.BANTER_VS_ABUSE,
        benign_text="i swear you're a dumbass for buying that skin haha",
        harmful_text="you're a dumbass who shouldn't be allowed on the server",
        shared_trigger_words=["dumbass"],
        benign_pragmatic_use=PragmaticUse.AFFILIATIVE_BANTER,
        harmful_pragmatic_use=PragmaticUse.TARGETED_ABUSE,
        harm_types=[HarmType.TARGETED_INSULT],
        context_prefix=["look at my new character loadout", "cost me 2000 credits"],
    ),
    MinimalPair(
        pair_id="mp_banter_03",
        category=DiagnosticCategory.BANTER_VS_ABUSE,
        benign_text="deadass you carry this team every single round",
        harmful_text="deadass nobody wants you in this call go leave",
        shared_trigger_words=["deadass"],
        benign_pragmatic_use=PragmaticUse.AFFILIATIVE_BANTER,
        harmful_pragmatic_use=PragmaticUse.TARGETED_ABUSE,
        harm_types=[HarmType.EXCLUSION_COERCION],
        context_prefix=["we won again!", "gg guys"],
    ),
    # 2. Targeted vs Untargeted Profanity
    MinimalPair(
        pair_id="mp_targeted_01",
        category=DiagnosticCategory.TARGETED_VS_UNTARGETED,
        benign_text="holy shit this level is impossible to beat",
        harmful_text="you are a piece of shit and nobody likes you",
        shared_trigger_words=["shit"],
        benign_pragmatic_use=PragmaticUse.EMOTIONAL_EMPHASIS,
        harmful_pragmatic_use=PragmaticUse.TARGETED_ABUSE,
        harm_types=[HarmType.TARGETED_INSULT],
        context_prefix=["how many attempts on boss 4?", "like 20 now"],
    ),
    MinimalPair(
        pair_id="mp_targeted_02",
        category=DiagnosticCategory.TARGETED_VS_UNTARGETED,
        benign_text="fuck yeah we finally got the victory royale",
        harmful_text="fuck you go cry to your mom loser",
        shared_trigger_words=["fuck"],
        benign_pragmatic_use=PragmaticUse.EMOTIONAL_EMPHASIS,
        harmful_pragmatic_use=PragmaticUse.TARGETED_ABUSE,
        harm_types=[HarmType.TARGETED_INSULT],
        context_prefix=["last squad down!", "nice clutch!"],
    ),
    # 3. Quotation/Condemnation vs Endorsement
    MinimalPair(
        pair_id="mp_quotation_01",
        category=DiagnosticCategory.QUOTATION_VS_ENDORSEMENT,
        benign_text="why did user4 send 'go kys' in the group chat?",
        harmful_text="everyone tell user4 go kys right now",
        shared_trigger_words=["kys"],
        benign_pragmatic_use=PragmaticUse.QUOTATION_REPORTING,
        harmful_pragmatic_use=PragmaticUse.TARGETED_ABUSE,
        harm_types=[HarmType.SELF_HARM_ENCOURAGEMENT, HarmType.DOGPILING_MOBILIZATION],
        context_prefix=["did anyone see what happened in general chat?", "yeah it got bad"],
    ),
    MinimalPair(
        pair_id="mp_quotation_02",
        category=DiagnosticCategory.QUOTATION_VS_ENDORSEMENT,
        benign_text="he literally called me a worthless loser for no reason",
        harmful_text="you are literally a worthless loser for no reason",
        shared_trigger_words=["worthless", "loser"],
        benign_pragmatic_use=PragmaticUse.QUOTATION_REPORTING,
        harmful_pragmatic_use=PragmaticUse.TARGETED_ABUSE,
        harm_types=[HarmType.TARGETED_INSULT],
        context_prefix=["why are you upset?", "let me tell you what he said"],
    ),
    # 4. Reclaimed Identity vs Identity Attack
    MinimalPair(
        pair_id="mp_reclaimed_01",
        category=DiagnosticCategory.RECLAIMED_VS_SLUR,
        benign_text="queer gaming squad meeting up at 7pm tonight!",
        harmful_text="get out of this lobby you disgusting queer freak",
        shared_trigger_words=["queer"],
        benign_pragmatic_use=PragmaticUse.RECLAIMED_SELF_REFERENCE,
        harmful_pragmatic_use=PragmaticUse.TARGETED_ABUSE,
        harm_types=[HarmType.IDENTITY_ATTACK],
        context_prefix=["who is hosting the private match?", "check the community board"],
    ),
    # 5. Negation and Counter-speech
    MinimalPair(
        pair_id="mp_negation_01",
        category=DiagnosticCategory.NEGATION_COUNTERSPEECH,
        benign_text="I don't hate you at all, you're doing great",
        harmful_text="I hate you so much, stop ruining our matches",
        shared_trigger_words=["hate", "you"],
        benign_pragmatic_use=PragmaticUse.ABSENT,
        harmful_pragmatic_use=PragmaticUse.TARGETED_ABUSE,
        harm_types=[HarmType.TARGETED_INSULT],
        context_prefix=["i feel like i messed up the game", "sorry everyone"],
    ),
    MinimalPair(
        pair_id="mp_negation_02",
        category=DiagnosticCategory.NEGATION_COUNTERSPEECH,
        benign_text="stop attacking him, he is not trash and he tried his best",
        harmful_text="keep attacking him, he is pure trash and threw the round",
        shared_trigger_words=["trash", "attacking"],
        benign_pragmatic_use=PragmaticUse.ABSENT,
        harmful_pragmatic_use=PragmaticUse.TARGETED_ABUSE,
        harm_types=[HarmType.TARGETED_INSULT, HarmType.DOGPILING_MOBILIZATION],
        context_prefix=["player 3 missed the shot", "now everyone is flaming him"],
    ),
]


def build_minimal_pair_conversations(
    pairs: list[MinimalPair] | None = None,
) -> tuple[list[ConversationRecord], list[AnnotationRecord]]:
    """Convert minimal pairs into ConversationRecords and gold AnnotationRecords for evaluation."""
    pairs = pairs or DEFAULT_MINIMAL_PAIRS
    conversations: list[ConversationRecord] = []
    annotations: list[AnnotationRecord] = []

    for pair in pairs:
        # Build benign conversation
        benign_cid = f"{pair.pair_id}_benign"
        benign_turns: list[StoredTurn] = []
        for idx, ctx in enumerate(pair.context_prefix):
            benign_turns.append(
                StoredTurn(
                    turn_id=f"t{idx + 1}",
                    speaker_id=f"user_{idx + 1}",
                    role="user",
                    text=ctx,
                    relative_time=f"+{idx * 5}s",
                )
            )
        target_turn_id = f"t{len(benign_turns) + 1}"
        benign_turns.append(
            StoredTurn(
                turn_id=target_turn_id,
                speaker_id="speaker_target",
                role="user",
                text=pair.benign_text,
                relative_time=f"+{len(benign_turns) * 5}s",
            )
        )
        conversations.append(
            ConversationRecord(
                conversation_id=benign_cid,
                source_id="functional_minimal_pair",
                source_tier=SourceTier.FUNCTIONAL,
                platform_style="gaming_chat",
                turns=benign_turns,
                metadata={"pair_id": pair.pair_id, "category": pair.category, "variant": "benign"},
            )
        )
        annotations.append(
            AnnotationRecord(
                conversation_id=benign_cid,
                turn_id=target_turn_id,
                profanity_form=ProfanityForm.LITERAL
                if pair.shared_trigger_words
                else ProfanityForm.NONE,
                pragmatic_use=pair.benign_pragmatic_use,
                harm_types=[],
                severity=Severity.BENIGN,
                target_type=TargetType.NONE,
                adjudicated=True,
            )
        )

        # Build harmful conversation
        harmful_cid = f"{pair.pair_id}_harmful"
        harmful_turns: list[StoredTurn] = []
        for idx, ctx in enumerate(pair.context_prefix):
            harmful_turns.append(
                StoredTurn(
                    turn_id=f"t{idx + 1}",
                    speaker_id=f"user_{idx + 1}",
                    role="user",
                    text=ctx,
                    relative_time=f"+{idx * 5}s",
                )
            )
        harmful_target_turn_id = f"t{len(harmful_turns) + 1}"
        harmful_turns.append(
            StoredTurn(
                turn_id=harmful_target_turn_id,
                speaker_id="speaker_target",
                role="user",
                text=pair.harmful_text,
                relative_time=f"+{len(harmful_turns) * 5}s",
            )
        )
        conversations.append(
            ConversationRecord(
                conversation_id=harmful_cid,
                source_id="functional_minimal_pair",
                source_tier=SourceTier.FUNCTIONAL,
                platform_style="gaming_chat",
                turns=harmful_turns,
                metadata={"pair_id": pair.pair_id, "category": pair.category, "variant": "harmful"},
            )
        )
        annotations.append(
            AnnotationRecord(
                conversation_id=harmful_cid,
                turn_id=harmful_target_turn_id,
                profanity_form=ProfanityForm.LITERAL
                if pair.shared_trigger_words
                else ProfanityForm.NONE,
                pragmatic_use=pair.harmful_pragmatic_use,
                harm_types=pair.harm_types,
                severity=Severity.ACTIONABLE,
                target_type=TargetType.INDIVIDUAL_PEER,
                adjudicated=True,
            )
        )

    return conversations, annotations
