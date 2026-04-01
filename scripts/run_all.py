#!/usr/bin/env python3
"""Run the full CTA Engine pipeline: crawl → analyze → report."""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cta_engine.config import settings
from cta_engine.scoring.engine import generate_health_report, get_summary_stats, load_all_analyses


def print_report():
    """Print a summary of the CTA health report."""
    analyses = load_all_analyses()
    if not analyses:
        print("No analyses found. Run: python scripts/analyze.py --all")
        return

    df = generate_health_report(analyses)
    stats = get_summary_stats(df)

    print("\n" + "=" * 60)
    print("CTA ENGINE — HEALTH REPORT SUMMARY")
    print("=" * 60)
    print(f"Articles analyzed:   {stats['total_articles']}")
    print(f"Total sections:      {stats['total_sections']}")
    print(f"Misaligned CTAs:     {stats['misaligned_sections']}")
    print(f"Alignment rate:      {stats['alignment_rate']:.0%}")
    print(f"Avg health score:    {stats['avg_health_score']:.0%}")
    print(f"Avg confidence:      {stats['avg_confidence']:.0%}")
    print(f"No-CTA recommended:  {stats['sections_with_no_cta_recommended']}")

    print(f"\nFunnel distribution:")
    for stage, count in stats["funnel_distribution"].items():
        print(f"  {stage}: {count}")

    print(f"\nIntent distribution:")
    for intent, count in stats["intent_distribution"].items():
        print(f"  {intent}: {count}")

    # Top misaligned articles
    misaligned = df[df["is_misaligned"]].groupby("article_slug").size().sort_values(ascending=False)
    if len(misaligned) > 0:
        print(f"\nTop misaligned articles:")
        for slug, count in misaligned.head(10).items():
            title = df[df["article_slug"] == slug]["article_title"].iloc[0]
            print(f"  {count} issues — {title[:60]}")

    # Export
    output_path = settings.data_dir / "cta_health_report.csv"
    df.to_csv(output_path, index=False)
    print(f"\nFull report exported to: {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    print_report()
