#!/usr/bin/env python3
"""Run analysis on crawled articles."""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cta_engine.classifier.pipeline import analyze_article
from cta_engine.config import settings


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze crawled articles")
    parser.add_argument("--slug", type=str, help="Analyze a specific article by slug")
    parser.add_argument("--all", action="store_true", help="Analyze all crawled articles")
    parser.add_argument("--limit", type=int, default=10, help="Max articles to analyze (with --all)")
    args = parser.parse_args()

    logging.basicConfig(level=settings.log_level, format="%(levelname)s: %(message)s")

    if args.slug:
        path = settings.crawled_dir / f"{args.slug}.json"
        if not path.exists():
            print(f"Article not found: {args.slug}")
            sys.exit(1)

        with open(path) as f:
            article = json.load(f)

        print(f"Analyzing: {article['title']}")
        result = analyze_article(article)
        print(f"Health score: {result.overall_health_score:.0%}")
        print(f"Misaligned: {result.misaligned_count}/{len(result.section_analyses)}")

    elif args.all:
        if not settings.crawled_dir.exists():
            print("No crawled articles found. Run the crawler first.")
            sys.exit(1)

        paths = sorted(settings.crawled_dir.glob("*.json"))[:args.limit]
        print(f"Analyzing {len(paths)} articles...")

        for i, path in enumerate(paths):
            # Skip already analyzed
            classified_path = settings.classified_dir / path.name
            if classified_path.exists():
                print(f"  [{i+1}/{len(paths)}] Skipping (already analyzed): {path.stem}")
                continue

            with open(path) as f:
                article = json.load(f)

            print(f"  [{i+1}/{len(paths)}] {article.get('title', path.stem)[:60]}")
            try:
                result = analyze_article(article)
                print(f"    → Health: {result.overall_health_score:.0%}, Misaligned: {result.misaligned_count}")
            except Exception as e:
                print(f"    → ERROR: {e}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
