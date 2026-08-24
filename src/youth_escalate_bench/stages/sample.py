"""Quota sampling and deduplication stage."""

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from youth_escalate_bench.dedup.minhash import find_near_duplicates, normalized_text_hash
from youth_escalate_bench.io.parquet import read_conversations, write_conversations
from youth_escalate_bench.schemas.conversation import ConversationRecord, SourceTier
from youth_escalate_bench.schemas.labels import AnnotationRecord
from youth_escalate_bench.stages.common import find_parquet


def run_sample(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    in_path = find_parquet(
        input_dir,
        "conversations_threaded.parquet",
        "conversations.parquet",
        "generated_conversations.parquet",
        "conversations_redacted.parquet",
    )
    conversations = read_conversations(in_path)

    # If synthetic/staged conversations exist from stage_generate, include them
    syn_path = Path("data/processed/stage_generate/generated_conversations.parquet")
    if syn_path.exists():
        conversations.extend(read_conversations(syn_path))

    quotas = config.get(
        "quotas",
        {
            "organic": 4000,
            "staged": 2000,
            "synthetic": 3000,
            "functional": 2000,
            "live": 1000,
        },
    )

    by_tier: dict[str, list[ConversationRecord]] = defaultdict(list)
    for conv in conversations:
        if hasattr(conv.source_tier, "value"):
            tier = conv.source_tier.value
        else:
            tier = str(conv.source_tier)
        by_tier[tier].append(conv)

    selected: list[ConversationRecord] = []
    quota_report: dict[str, dict[str, int]] = {}

    import random

    rng = random.Random(config.get("random_seed", 42))

    for tier, target in quotas.items():
        pool = by_tier.get(tier, [])
        rng.shuffle(pool)
        take = min(target, len(pool))
        selected.extend(pool[:take])
        quota_report[tier] = {
            "available": len(pool),
            "target": target,
            "selected": take,
            "gap": max(0, target - take),
        }

    # Include fixture tier if present and not already in quotas
    if by_tier.get("fixture") and "fixture" not in quotas:
        selected.extend(by_tier["fixture"])

    # Deduplicate selected conversations by conversation_id
    seen_convs: set[str] = set()
    deduped_selected: list[ConversationRecord] = []
    for c in selected:
        if c.conversation_id not in seen_convs:
            seen_convs.add(c.conversation_id)
            deduped_selected.append(c)
    selected = deduped_selected

    out_path = output_dir / "conversations_sampled.parquet"
    write_conversations(out_path, selected)

    # Dedup report on selected
    texts = []
    ids = []
    for conv in selected:
        for turn in conv.turns:
            texts.append(turn.text)
            ids.append(f"{conv.conversation_id}:{turn.turn_id}")

    exact_hashes: dict[str, list[str]] = {}
    for id_, text in zip(ids, texts, strict=True):
        h = normalized_text_hash(text)
        exact_hashes.setdefault(h, []).append(id_)
    exact_dupes = {h: v for h, v in exact_hashes.items() if len(v) > 1}
    near = find_near_duplicates(texts, threshold=config.get("minhash_threshold", 0.8))

    report = {
        "quotas": quota_report,
        "total_selected": len(selected),
        "total_turns": sum(len(c.turns) for c in selected),
        "exact_duplicate_groups": len(exact_dupes),
        "near_duplicate_pairs": len(near),
    }
    report_path = output_dir / "quota_report.yaml"
    with report_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(report, f)

    return {
        "output_files": ["conversations_sampled.parquet", "quota_report.yaml"],
        "row_counts": {"conversations_sampled.parquet": sum(len(c.turns) for c in selected)},
        "metadata": report,
    }


def run_stage_generate(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Emit scenario plan JSONL from templates, plus full synthetic conversations and minimal pairs."""
    from youth_escalate_bench.generation.generator import SyntheticDialogueGenerator
    from youth_escalate_bench.transforms.minimal_pairs import build_minimal_pair_conversations

    templates_path = Path(config.get("templates_path", "configs/scenario_templates.yaml"))
    with templates_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    import json
    import random

    seed = config.get("random_seed", 42)
    random.Random(seed)
    generator = SyntheticDialogueGenerator(seed=seed)
    count = config.get("plans_per_template", 2)
    plans_path = output_dir / "scenario_plans.jsonl"

    written = 0
    generated_convs: list[ConversationRecord] = []
    generated_anns: list[AnnotationRecord] = []

    with plans_path.open("w", encoding="utf-8") as f:
        for template in data.get("templates", []):
            for i in range(count):
                plan = {
                    "plan_id": f"{template['template_id']}_{i}",
                    "template_id": template["template_id"],
                    "platform_style": template["platform_style"],
                    "transition_pattern": template["transition_pattern"],
                    "intended_harm_type": template.get("harm_type"),
                    "turns_min": template.get("turns_min", 4),
                    "turns_max": template.get("turns_max", 8),
                    "language_mode": template.get("language_mode", "english"),
                    "description": template.get("description", ""),
                    "source_tier": SourceTier.STAGED.value,
                    "collection_status": "pending_recruitment",
                }
                f.write(json.dumps(plan) + "\n")
                written += 1

                # Synthesize dialogue for testing and development
                conv, anns = generator.generate_conversation(plan)
                generated_convs.append(conv)
                generated_anns.extend(anns)

    # Functional minimal-pair suite
    mp_convs, mp_anns = build_minimal_pair_conversations()
    generated_convs.extend(mp_convs)
    generated_anns.extend(mp_anns)

    # Write generated parquet and annotations
    gen_parquet_path = output_dir / "generated_conversations.parquet"
    write_conversations(gen_parquet_path, generated_convs)

    gen_ann_path = output_dir / "generated_annotations.jsonl"
    with gen_ann_path.open("w", encoding="utf-8") as f:
        for ann in generated_anns:
            f.write(json.dumps(ann.model_dump(mode="json")) + "\n")

    # Functional minimal-pair scaffold specs
    pairs_path = output_dir / "minimal_pair_specs.jsonl"
    pair_specs = [
        {"group_id": "mp_targeted_vs_general", "factor": "targeting"},
        {"group_id": "mp_banter_vs_bullying", "factor": "pragmatic_use"},
        {"group_id": "mp_quote_vs_endorse", "factor": "quotation"},
        {"group_id": "mp_reclaimed_vs_attack", "factor": "reclaimed_language"},
        {"group_id": "mp_idiom_vs_threat", "factor": "threat_credibility"},
        {"group_id": "mp_context_flip", "factor": "context_dependence"},
    ]
    with pairs_path.open("w", encoding="utf-8") as f:
        for spec in pair_specs:
            f.write(json.dumps(spec) + "\n")

    output_files = [
        "scenario_plans.jsonl",
        "minimal_pair_specs.jsonl",
        "generated_conversations.parquet",
        "generated_annotations.jsonl",
    ]
    return {
        "output_files": output_files,
        "row_counts": {
            "scenario_plans.jsonl": written,
            "generated_conversations.parquet": sum(len(c.turns) for c in generated_convs),
        },
        "metadata": {
            "plans": written,
            "generated_conversations": len(generated_convs),
            "generated_turns": sum(len(c.turns) for c in generated_convs),
            "minimal_pair_groups": len(pair_specs),
        },
    }
