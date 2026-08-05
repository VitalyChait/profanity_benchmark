"""Annotation label schemas (plan.md Section 2 taxonomy)."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from youth_escalate_bench.schemas.taxonomy import (
    CONTEXT_DEPENDENCE,
    HARM_TYPES,
    PRAGMATIC_USES,
    PROFANITY_FORMS,
    SEVERITY_LEVELS,
    TARGET_TYPES,
)


class ProfanityForm(StrEnum):
    NONE = "none"
    LITERAL = "literal"
    ORTHOGRAPHICALLY_OBFUSCATED = "orthographically_obfuscated"
    PHONETIC = "phonetic"
    EUPHEMISTIC_ALGO_CODED = "euphemistic_algo_coded"
    ACRONYM = "acronym"
    EMOJI_REBUS = "emoji_rebus"
    CODE_SWITCHED = "code_switched"


class PragmaticUse(StrEnum):
    ABSENT = "absent"
    AFFILIATIVE_BANTER = "affiliative_banter"
    EMOTIONAL_EMPHASIS = "emotional_emphasis"
    QUOTATION_REPORTING = "quotation_reporting"
    RECLAIMED_SELF_REFERENCE = "reclaimed_self_reference"
    TARGETED_ABUSE = "targeted_abuse"
    AMBIGUOUS = "ambiguous"


class HarmType(StrEnum):
    TARGETED_INSULT = "targeted_insult"
    REPEATED_HARASSMENT = "repeated_harassment"
    IDENTITY_ATTACK = "identity_attack"
    THREAT_INTIMIDATION = "threat_intimidation"
    SEXUALIZED_HARASSMENT = "sexualized_harassment"
    SELF_HARM_ENCOURAGEMENT = "self_harm_encouragement"
    EXCLUSION_COERCION = "exclusion_coercion"
    HUMILIATION_RUMOR = "humiliation_rumor"
    DOGPILING_MOBILIZATION = "dogpiling_mobilization"


class TargetType(StrEnum):
    NONE = "none"
    SELF = "self"
    INDIVIDUAL_PEER = "individual_peer"
    NON_PROTECTED_GROUP = "non_protected_group"
    PROTECTED_GROUP = "protected_group"
    INDETERMINATE = "indeterminate"


class Severity(StrEnum):
    BENIGN = "benign"  # 0
    COARSE_MONITOR = "coarse_monitor"  # 1
    ACTIONABLE = "actionable"  # 2
    URGENT = "urgent"  # 3


class EscalationTransition(StrEnum):
    DE_ESCALATING = "de_escalating"
    STABLE = "stable"
    ESCALATING = "escalating"
    NOT_APPLICABLE = "not_applicable"


class ContextDependence(StrEnum):
    INVARIANT = "invariant"
    AMPLIFIED = "amplified"
    MITIGATED = "mitigated"
    LABEL_FLIPPED = "label_flipped"
    INSUFFICIENT_CONTEXT = "insufficient_context"


def severity_index(severity: Severity) -> int:
    return list(Severity).index(severity)


def is_actionable(severity: Severity) -> bool:
    return severity in (Severity.ACTIONABLE, Severity.URGENT)


class ConversationEvent(BaseModel):
    first_actionable_turn_id: str | None = None
    peak_severity: Severity = Severity.BENIGN
    repeated_target_pattern: bool = False
    de_escalation_occurs: bool = False


class AnnotationRecord(BaseModel):
    """Gold labels for a single turn (private; never exposed at inference)."""

    conversation_id: str
    turn_id: str
    profanity_form: ProfanityForm = ProfanityForm.NONE
    pragmatic_use: PragmaticUse = PragmaticUse.ABSENT
    harm_types: Annotated[list[HarmType], Field(default_factory=list)]
    target_type: TargetType = TargetType.NONE
    severity: Severity = Severity.BENIGN
    escalation_transition: EscalationTransition = EscalationTransition.NOT_APPLICABLE
    context_dependence: ContextDependence = ContextDependence.INVARIANT
    evidence_spans: Annotated[list[tuple[int, int]], Field(default_factory=list)]
    evidence_turn_ids: Annotated[list[str], Field(default_factory=list)]
    annotator_id: str | None = None
    adjudicated: bool = False

    @classmethod
    def taxonomy_coverage(cls) -> dict[str, tuple[str, ...]]:
        return {
            "harm_types": HARM_TYPES,
            "severity_levels": SEVERITY_LEVELS,
            "target_types": TARGET_TYPES,
            "profanity_forms": PROFANITY_FORMS,
            "pragmatic_uses": PRAGMATIC_USES,
            "context_dependence": CONTEXT_DEPENDENCE,
        }
