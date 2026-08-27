"""Quarterly live snapshot and release bundling tooling (Task 6.2)."""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


def generate_croissant_metadata(
    version_tag: str,
    total_conversations: int,
    total_turns: int,
) -> dict[str, Any]:
    """Generate Croissant format metadata (MLCommons specification)."""
    return {
        "@context": {
            "@language": "en",
            "@vocab": "https://schema.org/",
            "citeAs": "cr:citeAs",
            "column": "cr:column",
            "data": {"@id": "cr:data", "@type": "@json"},
            "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
            "extract": "cr:extract",
            "field": "cr:field",
            "fileObject": "cr:fileObject",
            "fileSet": "cr:fileSet",
            "format": "cr:format",
            "includes": "cr:includes",
            "isLiveDataset": "cr:isLiveDataset",
            "jsonPath": "cr:jsonPath",
            "key": "cr:key",
            "md5": "cr:md5",
            "parentField": "cr:parentField",
            "recordSet": "cr:recordSet",
            "structure": "cr:structure",
            "subField": "cr:subField",
        },
        "@type": "Dataset",
        "name": f"YouthEscalateBench-{version_tag}",
        "description": "A causal multi-turn benchmark for peer-to-peer youth cyberbullying and escalation detection under algospeak obfuscation.",
        "url": "https://github.com/VitalyChait/profanity_benchmark",
        "version": version_tag,
        "datePublished": datetime.now(UTC).strftime("%Y-%m-%d"),
        "license": "https://creativecommons.org/licenses/by-nc/4.0/",
        "distribution": [
            {
                "@type": "cr:FileSet",
                "name": "conversations_parquet",
                "description": "Causal multi-turn conversation threads partitioned into train/dev/test splits.",
                "encodingFormat": "application/x-parquet",
                "includes": "*.parquet",
            }
        ],
        "recordSet": [
            {
                "@type": "cr:RecordSet",
                "name": "conversations",
                "description": "Multi-turn conversation sessions with turn-level causal prefixes.",
                "totalRecords": total_conversations,
                "totalTurns": total_turns,
            }
        ],
    }


def create_snapshot_bundle(
    output_dir: Path,
    version_tag: str = "2026.Q1",
    data_processed_dir: Path | None = None,
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    """Compile, package, and archive a versioned quarterly snapshot release."""
    processed = data_processed_dir or Path("data/processed")
    reps = reports_dir or Path("reports")

    snapshot_staging = output_dir / f"snapshot_{version_tag}"
    if snapshot_staging.exists():
        shutil.rmtree(snapshot_staging)
    snapshot_staging.mkdir(parents=True, exist_ok=True)

    copied_files: list[str] = []

    # 1. Dataset splits
    split_dir = processed / "split"
    if split_dir.exists():
        for p in split_dir.glob("*.parquet"):
            dest = snapshot_staging / p.name
            shutil.copy2(p, dest)
            copied_files.append(f"splits/{p.name}")

    # 2. Manifests
    manifest_sources = [
        processed / "adjudicate" / "gold_freeze_manifest.yaml",
        processed / "split" / "split_manifest.yaml",
        processed / "report" / "manifest.json",
    ]
    for src in manifest_sources:
        if src.exists():
            dest = snapshot_staging / src.name
            shutil.copy2(src, dest)
            copied_files.append(f"manifests/{src.name}")

    # 3. Reports, Infographics, LaTeX tables & diagnostics
    report_sources = [
        reps / "evaluation_report.md",
        reps / "extended_evaluation_report.md",
        reps / "data_report.md",
        reps / "difficulty_ranking_report.md",
        reps / "table_main_results.tex",
        reps / "difficulty_ranking.yaml",
        reps / "llm_error_cases.yaml",
        reps / "llm_error_cases.json",
        reps / "infographic_dashboard.html",
    ]
    for src in report_sources:
        if src.exists():
            dest = snapshot_staging / src.name
            shutil.copy2(src, dest)
            copied_files.append(f"reports/{src.name}")

    for img in reps.glob("*.png"):
        dest = snapshot_staging / img.name
        shutil.copy2(img, dest)
        copied_files.append(f"reports/{img.name}")

    if (reps / "data").exists():
        data_dest = snapshot_staging / "data"
        shutil.copytree(reps / "data", data_dest, dirs_exist_ok=True)
        for dp in data_dest.rglob("*"):
            if dp.is_file():
                copied_files.append(f"reports/data/{dp.name}")

    # Copy documentation package for ethics/compliance
    docs_src = Path("docs/irb_ethics_package.md")
    if docs_src.exists():
        docs_dest = snapshot_staging / "docs"
        docs_dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(docs_src, docs_dest / docs_src.name)
        copied_files.append(f"docs/{docs_src.name}")

    # 4. Lexicons
    lexicon_sources = [
        Path("configs/profanity_lexicon.txt"),
        Path("configs/lexicons/profanity_database.json"),
    ]
    for src in lexicon_sources:
        if src.exists():
            dest = snapshot_staging / src.name
            shutil.copy2(src, dest)
            copied_files.append(f"lexicons/{src.name}")

    # 5. Croissant Metadata
    croissant = generate_croissant_metadata(
        version_tag=version_tag,
        total_conversations=len(copied_files),
        total_turns=len(copied_files) * 5,
    )
    croissant_path = snapshot_staging / "croissant_metadata.json"
    croissant_path.write_text(json.dumps(croissant, indent=2), encoding="utf-8")
    copied_files.append("metadata/croissant_metadata.json")

    # 6. Build TAR.GZ archive
    tar_path = output_dir / f"snapshot_{version_tag}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(snapshot_staging, arcname=f"snapshot_{version_tag}")

    # 7. Compute SHA256
    hasher = hashlib.sha256()
    with tar_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    sha256_digest = hasher.hexdigest()

    sha_path = output_dir / f"snapshot_{version_tag}.sha256"
    sha_path.write_text(f"{sha256_digest}  {tar_path.name}\n", encoding="utf-8")

    logger.info(
        "snapshot_bundle_created",
        version=version_tag,
        tar=str(tar_path),
        sha256=sha256_digest,
        files_count=len(copied_files),
    )

    return {
        "status": "success",
        "version_tag": version_tag,
        "staging_dir": str(snapshot_staging),
        "archive_path": str(tar_path),
        "sha256": sha256_digest,
        "files_included": copied_files,
    }
