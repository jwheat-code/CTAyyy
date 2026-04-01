#!/usr/bin/env python3
"""
Fetch all 2026 article URLs from the Salesforce blog sitemap
that haven't been crawled yet. Saves to /tmp/sitemap_urls_2026.json.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from cta_engine.config import settings

SITEMAPS = [
    "https://www.salesforce.com/blog/post-sitemap4.xml",
    "https://www.salesforce.com/blog/post-sitemap5.xml",
]
OUTPUT_PATH = "/tmp/sitemap_urls_2026.json"


def fetch_new_urls(min_year: str = "2026") -> list[dict]:
    crawled = {p.stem for p in settings.crawled_dir.glob("*.json")}
    results = []
    for sitemap_url in SITEMAPS:
        try:
            req = urllib.request.Request(
                sitemap_url, headers={"User-Agent": "CTAEngineBot/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
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
            if lastmod and lastmod[:4] >= min_year:
                slug = loc.rstrip("/").split("/")[-1]
                if slug and not slug.startswith("?") and slug not in crawled:
                    results.append({"slug": slug, "url": loc, "date": lastmod[:10]})

    # Deduplicate
    seen = set()
    unique = []
    for r in results:
        if r["slug"] not in seen:
            seen.add(r["slug"])
            unique.append(r)

    unique.sort(key=lambda x: x["date"], reverse=True)
    return unique


def main():
    print("Fetching 2026 article URLs from Salesforce blog sitemap...")
    urls = fetch_new_urls()
    with open(OUTPUT_PATH, "w") as f:
        json.dump(urls, f, indent=2)
    print(f"Found {len(urls)} new articles → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
