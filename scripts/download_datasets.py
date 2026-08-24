"""Automated dataset downloader and catalog for YouthEscalateBench.

Downloads and extracts real-world conversational, escalation, toxicity,
and cyberbullying benchmark datasets directly into data/raw/ (which is git-ignored).
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import urllib.request


@dataclass
class DatasetSource:
    source_id: str
    name: str
    citation: str
    license: str
    url: str
    filename: str
    format: str  # zip, csv, json, jsonl, txt, tsv
    size_approx: str
    platform_style: str
    description: str
    is_archive: bool = False
    subfolder: str = ""


# Verified Live Web Sources Catalog
DATASET_CATALOG: dict[str, DatasetSource] = {
    "conversations_gone_awry_wikipedia": DatasetSource(
        source_id="conversations_gone_awry_wikipedia",
        name="Conversations Gone Awry (Wikipedia Talk Pages)",
        citation="Zhang et al. (ACL 2018)",
        license="CC-BY 4.0 / Academic Research",
        url="https://zissou.infosci.cornell.edu/convokit/datasets/conversations-gone-awry-corpus/conversations-gone-awry-corpus.zip",
        filename="conversations-gone-awry-corpus.zip",
        format="zip",
        size_approx="45.2 MB",
        platform_style="forum_thread",
        description="Multi-turn Wikipedia talk-page conversation trees that derailed into personal attacks, annotated turn-by-turn.",
        is_archive=True,
        subfolder="conversations_gone_awry_wikipedia",
    ),
    "conversations_gone_awry_cmv": DatasetSource(
        source_id="conversations_gone_awry_cmv",
        name="Conversations Gone Awry (Reddit CMV)",
        citation="Chang et al. (EMNLP 2019)",
        license="Academic Research License",
        url="https://zissou.infosci.cornell.edu/convokit/datasets/conversations-gone-awry-cmv-corpus/conversations-gone-awry-cmv-corpus.zip",
        filename="conversations-gone-awry-cmv-corpus.zip",
        format="zip",
        size_approx="51.5 MB",
        platform_style="forum_thread",
        description="Multi-turn Reddit ChangeMyView conversational threads with escalation, uncivil behavior, and rule-breaking harassment.",
        is_archive=True,
        subfolder="conversations_gone_awry_cmv",
    ),
    "lmsys_toxic_chat_train": DatasetSource(
        source_id="lmsys_toxic_chat_train",
        name="LMSYS ToxicChat (Train Set)",
        citation="Lin et al. (EMNLP 2023)",
        license="LMSYS Terms / Research Use",
        url="https://huggingface.co/datasets/lmsys/toxic-chat/raw/main/data/0124/toxic-chat_annotation_train.csv",
        filename="toxic-chat_annotation_train.csv",
        format="csv",
        size_approx="8.2 MB",
        platform_style="group_chat",
        description="Real-world multi-turn conversational queries annotated by humans for toxicity, jailbreaking, and harm.",
    ),
    "lmsys_toxic_chat_test": DatasetSource(
        source_id="lmsys_toxic_chat_test",
        name="LMSYS ToxicChat (Test Set)",
        citation="Lin et al. (EMNLP 2023)",
        license="LMSYS Terms / Research Use",
        url="https://huggingface.co/datasets/lmsys/toxic-chat/raw/main/data/0124/toxic-chat_annotation_test.csv",
        filename="toxic-chat_annotation_test.csv",
        format="csv",
        size_approx="8.1 MB",
        platform_style="group_chat",
        description="Evaluation test split of LMSYS ToxicChat multi-turn user dialogues.",
    ),
    "davidson_hate_speech": DatasetSource(
        source_id="davidson_hate_speech",
        name="Automated Hate Speech & Offensive Language Detection",
        citation="Davidson et al. (ICWSM 2017)",
        license="MIT License",
        url="https://raw.githubusercontent.com/t-davidson/hate-speech-and-offensive-language/master/data/labeled_data.csv",
        filename="davidson_labeled_data.csv",
        format="csv",
        size_approx="1.05 MB",
        platform_style="group_chat",
        description="24,783 labeled tweets categorizing hate speech, offensive/slang banter, and neutral language.",
    ),
    "dynabench_hate_speech": DatasetSource(
        source_id="dynabench_hate_speech",
        name="Dynamically Generated Hate Speech Dataset (Rounds 1-4)",
        citation="Vidgen et al. (ACL 2021)",
        license="CC-BY-NC 4.0",
        url="https://raw.githubusercontent.com/bvidgen/Dynamically-Generated-Hate-Speech-Dataset/main/Dynamically%20Generated%20Hate%20Dataset%20v0.2.3.csv",
        filename="dynabench_hate_speech.csv",
        format="csv",
        size_approx="2.5 MB",
        platform_style="group_chat",
        description="41,255 human-and-model-in-the-loop dynamically generated adversarial abusive examples and benign perturbations.",
    ),
    "hatexplain": DatasetSource(
        source_id="hatexplain",
        name="HateXplain: A Benchmark for Explainable Hate Speech",
        citation="Mathew et al. (AAAI 2021)",
        license="Academic Research License",
        url="https://raw.githubusercontent.com/hate-alert/HateXplain/master/Data/dataset.json",
        filename="hatexplain.json",
        format="json",
        size_approx="2.03 MB",
        platform_style="group_chat",
        description="20,148 multi-label annotated posts with rationale spans and target community labels.",
    ),
    "tweeteval_offensive": DatasetSource(
        source_id="tweeteval_offensive",
        name="TweetEval: Offensive Language Identification",
        citation="Barbieri et al. (EMNLP 2020)",
        license="MIT / Research",
        url="https://raw.githubusercontent.com/cardiffnlp/tweeteval/main/datasets/offensive/train_text.txt",
        filename="tweeteval_offensive_train.txt",
        format="txt",
        size_approx="608 KB",
        platform_style="group_chat",
        description="Standard benchmark for offensive language and insult identification.",
    ),
    "tweeteval_hate": DatasetSource(
        source_id="tweeteval_hate",
        name="TweetEval: Hate Speech Detection",
        citation="Barbieri et al. (EMNLP 2020)",
        license="MIT / Research",
        url="https://raw.githubusercontent.com/cardiffnlp/tweeteval/main/datasets/hate/train_text.txt",
        filename="tweeteval_hate_train.txt",
        format="txt",
        size_approx="490 KB",
        platform_style="group_chat",
        description="Standard benchmark for hate speech and identity attack identification.",
    ),
    "profanity_en_lexicon": DatasetSource(
        source_id="profanity_en_lexicon",
        name="Comprehensive Multilingual Profanity & Slur Lexicon",
        citation="LDNOOBW Open Profanity Database",
        license="CC0 / Public Domain",
        url="https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/en",
        filename="profanity_en_expanded.txt",
        format="txt",
        size_approx="2 KB",
        platform_style="any",
        description="Curated list of profane terms, slurs, and offensive expressions.",
    ),
}


def download_file(url: str, dest: Path) -> None:
    """Download a file with progress reporting."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading: {url}")
    print(f"  Destination: {dest}")

    def reporthook(block_num: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            percent = min(100.0, block_num * block_size * 100.0 / total_size)
            downloaded_mb = (block_num * block_size) / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            sys.stdout.write(f"\r  Progress: {percent:.1f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB)")
            sys.stdout.flush()

    urllib.request.urlretrieve(url, dest, reporthook=reporthook)
    print(f"\n  ✓ Saved to {dest} ({dest.stat().st_size:,} bytes)")


def extract_archive(zip_path: Path, extract_to: Path) -> None:
    """Extract a ZIP archive into a target directory."""
    print(f"  Extracting {zip_path.name} to {extract_to}...")
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_to)
    print(f"  ✓ Extracted {len(list(extract_to.glob('**/*')))} items.")


def download_source(source_id: str, raw_dir: Path) -> Path:
    """Download and optionally extract a dataset source."""
    if source_id not in DATASET_CATALOG:
        raise ValueError(f"Unknown source_id '{source_id}'. Available: {list(DATASET_CATALOG.keys())}")

    ds = DATASET_CATALOG[source_id]
    target_dir = raw_dir / (ds.subfolder or ds.source_id)
    target_file = target_dir / ds.filename

    print(f"\n[{ds.source_id}] {ds.name}")
    print(f"  Citation: {ds.citation} | License: {ds.license}")
    download_file(ds.url, target_file)

    if ds.is_archive and target_file.suffix == ".zip":
        extract_archive(target_file, target_dir)

    return target_file


def list_catalog() -> None:
    """Print the complete catalog of available dataset sources."""
    print("=" * 80)
    print("YouthEscalateBench — Available Downloadable Real-World Datasets")
    print("=" * 80)
    for sid, ds in DATASET_CATALOG.items():
        print(f"\n📦 [{sid}]")
        print(f"   Name        : {ds.name}")
        print(f"   Citation    : {ds.citation}")
        print(f"   License     : {ds.license}")
        print(f"   Approx Size : {ds.size_approx}")
        print(f"   Format      : {ds.format.upper()}")
        print(f"   Direct URL  : {ds.url}")
        print(f"   Description : {ds.description}")
    print("\n" + "=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public real-world datasets for YouthEscalateBench.")
    parser.add_argument("--list", "-l", action="store_true", help="List all available datasets in catalog.")
    parser.add_argument("--all", "-a", action="store_true", help="Download all available datasets.")
    parser.add_argument("--source", "-s", nargs="+", help="Specific source ID(s) to download.")
    parser.add_argument("--raw-dir", default="data/raw", help="Destination folder for raw data (default: data/raw).")

    args = parser.parse_args()

    if args.list or (not args.all and not args.source):
        list_catalog()
        if not args.all and not args.source:
            print("\nUsage example:")
            print("  python scripts/download_datasets.py --all")
            print("  python scripts/download_datasets.py --source conversations_gone_awry_wikipedia davidson_hate_speech")
        return

    raw_path = Path(args.raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)

    sources_to_download = list(DATASET_CATALOG.keys()) if args.all else (args.source or [])

    print(f"Downloading {len(sources_to_download)} dataset(s) into {raw_path.resolve()}...")
    successful: list[str] = []
    failed: list[tuple[str, str]] = []

    for sid in sources_to_download:
        try:
            download_source(sid, raw_path)
            successful.append(sid)
        except Exception as e:
            print(f"  ❌ Failed to download {sid}: {e}")
            failed.append((sid, str(e)))

    print("\n" + "=" * 60)
    print(f"Download Summary: {len(successful)} succeeded, {len(failed)} failed.")
    print(f"All files saved to: {raw_path.resolve()} (Ignored by .gitignore)")
    print("=" * 60)


if __name__ == "__main__":
    main()
