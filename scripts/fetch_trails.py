#!/usr/bin/env python3
"""
Fetch Trailhead trail metadata from the sitemap + JSON-LD.
Classifies each trail by product, funnel stage, and persona.
Saves to data/trail_library.json.
"""
import json, re, sys, time
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from cta_engine.config import settings

SITEMAP_URL = "https://trailhead.salesforce.com/content_sitemap.xml"


HEADERS = {"User-Agent": "CTAEngineBot/1.0 (research; non-commercial)"}


def fetch_trails_from_sitemap(min_date: str = "2025-01-01") -> list[dict]:
    print(f"Fetching Trailhead sitemap...")
    r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    xml = r.text

    # Parse loc + lastmod pairs
    entries = re.findall(
        r'<loc>(https://trailhead\.salesforce\.com/content/learn/trails/[^<]+)</loc>'
        r'\s*<lastmod>([^<]+)</lastmod>',
        xml,
    )
    trails = []
    for loc, lastmod in entries:
        # Only top-level trails (not individual units inside a trail)
        path = loc.replace("https://trailhead.salesforce.com/content/learn/trails/", "")
        if "/" in path:
            continue
        if lastmod < min_date:
            continue
        trails.append({"url": loc, "slug": path, "lastmod": lastmod})

    # Deduplicate
    seen = set()
    unique = [t for t in trails if not (t["slug"] in seen or seen.add(t["slug"]))]
    unique.sort(key=lambda x: x["lastmod"], reverse=True)
    print(f"Found {len(unique)} trails updated since {min_date}")
    return unique


def fetch_trail_metadata(url: str) -> dict:
    """Fetch name, description, duration from a trail page via JSON-LD + meta."""
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    html = r.text

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    name = ""
    description = ""
    duration_minutes = None

    # JSON-LD Course schema
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            d = json.loads(script.string or "")
            t = d.get("@type", [])
            if isinstance(t, str):
                t = [t]
            if "Course" in t:
                name = d.get("name", "")
                description = d.get("description", "")
                workload = d.get("hasCourseInstance", {}).get("courseWorkload", "")
                # Parse ISO 8601 duration PT85.0M → 85
                m = re.match(r"PT([\d.]+)M", workload)
                if m:
                    duration_minutes = int(float(m.group(1)))
                break
        except Exception:
            continue

    # Fallback to og meta
    if not name:
        og = soup.select_one('meta[property="og:title"]')
        name = og["content"].replace(" | Salesforce Trailhead", "").strip() if og else ""
    if not description:
        og = soup.select_one('meta[property="og:description"]')
        description = og["content"].strip() if og else ""

    return {"name": name, "description": description, "duration_minutes": duration_minutes}


def classify_trail(trail: dict) -> dict:
    """Apply same rule-based product/funnel/persona detection as articles."""
    # Import from classify_rules (same heuristics)
    script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(script_dir))
    from classify_rules import detect_products, detect_funnel, detect_persona, detect_intent, get_topic_tags

    text = f"{trail['name']} {trail['description']}"
    title = trail["name"]

    products = detect_products(text, title)
    intent = detect_intent(title, text)
    funnel = detect_funnel(title, text, intent)
    primary_persona, secondary_persona = detect_persona(text, title, products)
    tags = get_topic_tags(text, title, products)

    return {
        "products": products,
        "funnel_stage": funnel,
        "primary_persona": primary_persona,
        "secondary_persona": secondary_persona,
        "tags": tags,
        "intent": intent,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-date", default="2025-01-01")
    parser.add_argument("--output", default=str(Path(__file__).resolve().parent.parent / "data" / "trail_library.json"))
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    trails = fetch_trails_from_sitemap(min_date=args.min_date)
    if args.limit:
        trails = trails[:args.limit]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing to avoid re-fetching
    existing = {}
    if output_path.exists():
        try:
            for t in json.loads(output_path.read_text()):
                existing[t["slug"]] = t
        except Exception:
            pass

    results = list(existing.values())
    existing_slugs = set(existing.keys())

    new_count = 0
    for i, trail in enumerate(trails):
        if trail["slug"] in existing_slugs:
            continue
        try:
            meta = fetch_trail_metadata(trail["url"])
            if not meta["name"]:
                print(f"  [{i+1}/{len(trails)}] SKIP (no name): {trail['slug']}")
                time.sleep(1)
                continue

            classification = classify_trail({**trail, **meta})

            entry = {
                "trail_id": f"trail-{trail['slug']}",
                "type": "trail",
                "name": meta["name"],
                "description": meta["description"],
                "url": trail["url"],
                "slug": trail["slug"],
                "lastmod": trail["lastmod"],
                "duration_minutes": meta["duration_minutes"],
                "product": classification["products"][0] if classification["products"] else "general",
                "products": classification["products"],
                "funnel_stage": classification["funnel_stage"],
                "primary_persona": classification["primary_persona"],
                "secondary_persona": classification["secondary_persona"],
                "tags": classification["tags"],
            }
            results.append(entry)
            new_count += 1
            print(f"  [{new_count}] {meta['name'][:60]} → {entry['product']} / {entry['funnel_stage']}")

            # Save incrementally
            output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
            time.sleep(1.2)

        except Exception as e:
            print(f"  [{i+1}] ERROR {trail['slug']}: {e}")
            time.sleep(2)

    print(f"\nDone: {new_count} new trails fetched, {len(results)} total → {output_path}")


if __name__ == "__main__":
    main()
