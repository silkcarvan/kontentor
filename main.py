#!/usr/bin/env python3
"""Kontentor CLI — 100% Autonomous Central Asian History AI YouTuber."""

import argparse
import json
from typing import Optional

from kontentor.brain import KontentorBrain
from kontentor.config import load_style_memory
from kontentor.pipeline import KontentorPipeline
from kontentor.researcher import WikipediaResearcher


def cmd_auto(topic: Optional[str], format_type: str) -> None:
    """Run the 100% autonomous AI YouTuber pipeline from scratch (0 dan)."""
    pipeline = KontentorPipeline()
    res = pipeline.run_autonomous_youtuber(topic=topic, format_type=format_type)
    print("\n=== AUTONOMOUS YOUTUBER OUTPUT ===")
    print(json.dumps(res, indent=2, ensure_ascii=False))


def cmd_train() -> None:
    """Run the self-improving analytics loop."""
    brain = KontentorBrain()
    sample_metrics = [
        {
            "title": "Amir Temur: The Undefeated Strategist of Samarkand #Shorts",
            "views": 24500,
            "ctr_percent": 10.2,
            "avg_percentage_viewed": 86.5,
            "drop_off_second": 0,
        }
    ]
    res = brain.self_train_from_analytics(sample_metrics)
    print("\n=== SELF-LEARNING MEMORY UPDATED ===")
    print(json.dumps(res, indent=2, ensure_ascii=False))


def cmd_topics() -> None:
    """Display autonomous topic queue and learned rules."""
    memory = load_style_memory()
    print("=== AUTONOMOUS TOPIC QUEUE ===")
    for idx, t in enumerate(WikipediaResearcher.list_recommended_topics(), start=1):
        print(f"  {idx}. {t}")
    print("\n=== LEARNED CHANNEL INSIGHTS ===")
    for lesson in memory.get("lessons_learned", []):
        print(f"  * [{lesson.get('date')}] {lesson.get('insight')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kontentor — 100% Autonomous Central Asian History AI YouTuber"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_auto = sub.add_parser(
        "auto",
        help="Autonomously pick topic (or use given topic), draw images from 0, voice, subtitle & build MP4",
    )
    p_auto.add_argument(
        "--topic",
        default=None,
        help="Optional topic (if omitted, AI picks the next topic from its queue automatically)",
    )
    p_auto.add_argument("--format", default="short", choices=["short", "long"])

    sub.add_parser("train", help="Run self-learning analytics feedback loop")
    sub.add_parser("topics", help="Show autonomous topic queue and learned rules")

    args = parser.parse_args()
    if args.command == "auto":
        cmd_auto(args.topic, args.format)
    elif args.command == "train":
        cmd_train()
    elif args.command == "topics":
        cmd_topics()


if __name__ == "__main__":
    main()
