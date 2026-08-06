"""Quota sampling and deduplication stage."""

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from youth_escalate_bench.dedup.minhash import find_near_duplicates, normalized_text_hash
from youth_escalate_bench.io.parquet import read_conversations, write_conversations
from youth_escalate_bench.schemas.conversation import ConversationRecord, SourceTier
from youth_escalate_bench.stages.common import find_parquet


def run_sample(config: dict[str, Any], input_dir: Path, output_dir: Path) -> dict[str, Any]:
    in_path = find_parquet(input_dir, "conversations_threaded.parquet", "conversations.parquet")
    conversations = read_conversations(in_path)

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

    # Include fixture tier if present (not in quotas)
    if by_tier.get("fixture"):
        selected.extend(by_tier["fixture"])

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
    """Emit scenario plan JSONL from templates for adult-staged collection."""
    templates_path = Path(config.get("templates_path", "configs/scenario_templates.yaml"))
    with templates_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    import json
    import random

    random.Random(config.get("random_seed", 42))
    count = config.get("plans_per_template", 2)
    plans_path = output_dir / "scenario_plans.jsonl"

    written = 0
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

    # Functional minimal-pair scaffold
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

    return {
        "output_files": ["scenario_plans.jsonl", "minimal_pair_specs.jsonl"],
        "row_counts": {"scenario_plans.jsonl": written},
        "metadata": {"plans": written, "minimal_pair_groups": len(pair_specs)},
    }
