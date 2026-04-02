#!/usr/bin/env python3
"""
Fetch article URLs from the Salesforce blog sitemap for a given year range.
Saves to /tmp/sitemap_urls_{min_year}.json.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from cta_engine.config import settings

# Sitemap coverage (approximate):
#   post-sitemap2.xml  → 2024 and older
#   post-sitemap3.xml  → 2025 (partial)
#   post-sitemap4.xml  → 2025 (bulk) + some 2026
#   post-sitemap5.xml  → 2026 (latest)
SITEMAPS_BY_YEAR = {
    "2026": [
        "https://www.salesforce.com/blog/post-sitemap4.xml",
        "https://www.salesforce.com/blog/post-sitemap5.xml",
    ],
    "2025": [
        "https://www.salesforce.com/blog/post-sitemap3.xml",
        "https://www.salesforce.com/blog/post-sitemap4.xml",
        "https://www.salesforce.com/blog/post-sitemap5.xml",
    ],
}


def fetch_new_urls(min_year: str = "2026", max_year: str = None) -> list[dict]:
    crawled = {p.stem for p in settings.crawled_dir.glob("*.json")}

    # Pick sitemap list — use most inclusive set that covers min_year
    if min_year <= "2025":
        sitemaps = SITEMAPS_BY_YEAR["2025"]
    else:
        sitemaps = SITEMAPS_BY_YEAR["2026"]

    results = []
    for sitemap_url in sitemaps:
        print(f"  Fetching {sitemap_url}...")
        try:
            req = urllib.request.Request(
                sitemap_url, headers={"User-Agent": "CTAEngineBot/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                xml = r.read().decode()
        except Exception as e:
            print(f"  Warning: could not fetch {sitemap_url}: {e}")
            continue

        entries = re.findall(
            r"<loc>(https://www\.salesforce\.com/blog/[^<]+)</loc>"
            r"\s*(?:<lastmod>([^<]+)</lastmod>)?",
            xml,
        )
        for loc, lastmod in entries:
            year = lastmod[:4] if lastmod else ""
            if year < min_year:
                continue
            if max_year and year > max_year:
                continue
            slug = loc.rstrip("/").split("/")[-1]
            if slug and not slug.startswith("?") and slug not in crawled:
                results.append({"slug": slug, "url": loc, "date": lastmod[:10] if lastmod else ""})

    # Deduplicate by slug
    seen = set()
    unique = []
    for r in results:
        if r["slug"] not in seen:
            seen.add(r["slug"])
            unique.append(r)

    unique.sort(key=lambda x: x["date"], reverse=True)
    return unique


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-year", default="2026", help="Minimum publish year (default: 2026)")
    parser.add_argument("--max-year", default=None, help="Maximum publish year (optional)")
    parser.add_argument("--output", default=None, help="Output path (default: /tmp/sitemap_urls_{year}.json)")
    args = parser.parse_args()

    output = args.output or f"/tmp/sitemap_urls_{args.min_year}.json"

    print(f"Fetching {args.min_year}+ article URLs from Salesforce blog sitemap...")
    urls = fetch_new_urls(min_year=args.min_year, max_year=args.max_year)
    with open(output, "w") as f:
        json.dump(urls, f, indent=2)
    print(f"Found {len(urls)} new articles → {output}")


if __name__ == "__main__":
    main()
