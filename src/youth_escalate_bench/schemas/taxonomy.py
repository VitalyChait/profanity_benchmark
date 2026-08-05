"""Machine-readable taxonomy constants from plan.md Section 2."""

from typing import Final

HARM_TYPES: Final[tuple[str, ...]] = (
    "targeted_insult",
    "repeated_harassment",
    "identity_attack",
    "threat_intimidation",
    "sexualized_harassment",
    "self_harm_encouragement",
    "exclusion_coercion",
    "humiliation_rumor",
    "dogpiling_mobilization",
)

SEVERITY_LEVELS: Final[tuple[str, ...]] = (
    "benign",       # 0
    "coarse_monitor",  # 1
    "actionable",   # 2
    "urgent",       # 3
)

TARGET_TYPES: Final[tuple[str, ...]] = (
    "none",
    "self",
    "individual_peer",
    "non_protected_group",
    "protected_group",
    "indeterminate",
)

ESCALATION_STATES: Final[tuple[str, ...]] = (
    "de_escalating",
    "stable",
    "escalating",
    "not_applicable",
)

PROFANITY_FORMS: Final[tuple[str, ...]] = (
    "none",
    "literal",
    "orthographically_obfuscated",
    "phonetic",
    "euphemistic_algo_coded",
    "acronym",
    "emoji_rebus",
    "code_switched",
)

PRAGMATIC_USES: Final[tuple[str, ...]] = (
    "absent",
    "affiliative_banter",
    "emotional_emphasis",
    "quotation_reporting",
    "reclaimed_self_reference",
    "targeted_abuse",
    "ambiguous",
)

CONTEXT_DEPENDENCE: Final[tuple[str, ...]] = (
    "invariant",
    "amplified",
    "mitigated",
    "label_flipped",
    "insufficient_context",
)

PLATFORM_STYLES: Final[tuple[str, ...]] = (
    "gaming_chat",
    "group_chat",
    "direct_messaging",
    "forum_thread",
)

LANGUAGE_MODES: Final[tuple[str, ...]] = (
    "english",
    "english_led_code_switch",
)

TASK_TYPES: Final[tuple[str, ...]] = (
    "current_harm",
    "onset_detection",
    "two_turn_forecast",
)

PIPELINE_STAGES: Final[tuple[str, ...]] = (
    "source_audit",
    "ingest",
    "redact",
    "thread",
    "sample",
    "stage_generate",
    "transform",
    "annotate_export",
    "adjudicate",
    "split",
    "evaluate",
    "report",
)
