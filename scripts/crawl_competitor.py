#!/usr/bin/env python3
"""
Crawl a competitor blog and run the full classify_rules pipeline.
Outputs crawled + classified JSON in the same format as Salesforce articles.

Usage:
  python scripts/crawl_competitor.py --brand hubspot --limit 468
  python scripts/crawl_competitor.py --brand shopify --limit 72
"""
import json, re, sys, time, argparse
from pathlib import Path
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cta_engine.config import settings
from classify_rules import (
    classify_article, detect_products, detect_intent, detect_funnel,
    detect_persona, get_topic_tags, score_existing_cta,
)

HEADERS = {"User-Agent": "CTAEngineBot/1.0 (research; non-commercial)"}
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Brand-specific parsers
# ---------------------------------------------------------------------------

def parse_hubspot(url: str) -> dict | None:
    r = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")

    title_el = soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else ""
    if not title:
        return None

    # Author
    author_el = soup.select_one("[class*=author]")
    author = author_el.get_text(strip=True).replace("Written by:", "").strip() if author_el else ""

    # Date
    date_meta = soup.select_one('meta[property="article:published_time"]')
    published_date = date_meta["content"] if date_meta else ""

    # Article body
    article_el = soup.select_one("article, .post-body, .blog-post-body, main")

    # Sections (h2)
    SKIP_HEADINGS = {"free chatgpt guide", "download free", "download now", "share article",
                     "table of contents", "subscribe", "related articles"}
    sections = []
    section_idx = 0
    current_heading = "Introduction"
    current_text_parts = []
    current_links = []

    if article_el:
        for el in article_el.find_all(["h2", "h3", "p", "ul", "ol", "blockquote"]):
            if el.name in ("h2", "h3"):
                heading_text = el.get_text(strip=True)
                if heading_text.lower() in SKIP_HEADINGS:
                    continue
                if heading_text.upper() == heading_text and len(heading_text) < 30:
                    continue
                if current_text_parts:
                    text = re.sub(r"\s+", " ", " ".join(current_text_parts).strip())
                    if len(text) > 50:
                        sections.append({
                            "index": section_idx, "heading": current_heading,
                            "text": text[:3000], "word_count": len(text.split()),
                            "has_existing_cta": False, "inline_links": current_links,
                        })
                        section_idx += 1
                current_heading = heading_text
                current_text_parts = []
                current_links = []
            else:
                text = el.get_text(strip=True)
                if text:
                    current_text_parts.append(text)
                for link in el.select("a[href]"):
                    lt, lh = link.get_text(strip=True), link.get("href", "")
                    if lt and lh:
                        current_links.append({"text": lt, "href": lh})

        if current_text_parts:
            text = re.sub(r"\s+", " ", " ".join(current_text_parts).strip())
            if len(text) > 50:
                sections.append({
                    "index": section_idx, "heading": current_heading,
                    "text": text[:3000], "word_count": len(text.split()),
                    "has_existing_cta": False, "inline_links": current_links,
                })

    # CTAs
    existing_ctas = []
    seen_urls = set()
    for a in soup.select("a[href*=offers], a[href*=cta], a.cta-button, [class*=cta] a[href], a[href*=get-started], a[href*=demo], a[href*=free]"):
        btn_text = a.get_text(strip=True)
        btn_url = a.get("href", "")
        if btn_text and btn_url and len(btn_text) > 2 and len(btn_text) < 80 and btn_url not in seen_urls:
            seen_urls.add(btn_url)
            # Find which section this CTA is near
            pos = len(sections) - 1  # default to last
            existing_ctas.append({
                "heading": "", "body": "",
                "button_text": btn_text, "button_url": btn_url,
                "position_after_section": max(0, pos),
            })

    if not sections:
        return None

    slug = url.rstrip("/").split("/")[-1]
    return {
        "url": url, "slug": slug, "title": title, "author": author,
        "published_date": published_date, "category": "",
        "sections": sections, "existing_ctas": existing_ctas, "raw_html": "",
    }


def parse_shopify(url: str) -> dict | None:
    r = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")

    title_el = soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else ""
    if not title:
        return None

    author_el = soup.select_one("[class*=author]")
    author = author_el.get_text(strip=True) if author_el else ""

    time_el = soup.select_one("time")
    date_str = time_el.get_text(strip=True) if time_el else ""
    # Convert "Mar 28, 2026" to ISO-ish
    published_date = date_str

    SKIP_HEADINGS = {"table of contents", "start your free trial", "faq", "related articles"}
    sections = []
    section_idx = 0
    current_heading = "Introduction"
    current_text_parts = []
    current_links = []

    for el in soup.find_all(["h2", "h3", "p", "ul", "ol", "blockquote"]):
        if el.name in ("h2", "h3"):
            heading_text = el.get_text(strip=True)
            if heading_text.lower() in SKIP_HEADINGS:
                continue
            if current_text_parts:
                text = re.sub(r"\s+", " ", " ".join(current_text_parts).strip())
                if len(text) > 50:
                    sections.append({
                        "index": section_idx, "heading": current_heading,
                        "text": text[:3000], "word_count": len(text.split()),
                        "has_existing_cta": False, "inline_links": current_links,
                    })
                    section_idx += 1
            current_heading = heading_text
            current_text_parts = []
            current_links = []
        else:
            text = el.get_text(strip=True)
            if text:
                current_text_parts.append(text)
            for link in el.select("a[href]"):
                lt, lh = link.get_text(strip=True), link.get("href", "")
                if lt and lh:
                    current_links.append({"text": lt, "href": lh})

    if current_text_parts:
        text = re.sub(r"\s+", " ", " ".join(current_text_parts).strip())
        if len(text) > 50:
            sections.append({
                "index": section_idx, "heading": current_heading,
                "text": text[:3000], "word_count": len(text.split()),
                "has_existing_cta": False, "inline_links": current_links,
            })

    # CTAs
    existing_ctas = []
    seen_urls = set()
    for a in soup.select("a[href*=free-trial], a[href*=start], a[href*=signup], a.marketing-button, [class*=cta] a[href]"):
        btn_text = a.get_text(strip=True)
        btn_url = a.get("href", "")
        if btn_text and btn_url and 2 < len(btn_text) < 80 and btn_url not in seen_urls:
            seen_urls.add(btn_url)
            pos = len(sections) - 1
            existing_ctas.append({
                "heading": "", "body": "",
                "button_text": btn_text, "button_url": btn_url,
                "position_after_section": max(0, pos),
            })

    if not sections:
        return None

    slug = url.rstrip("/").split("/")[-1]
    return {
        "url": url, "slug": slug, "title": title, "author": author,
        "published_date": published_date, "category": "",
        "sections": sections, "existing_ctas": existing_ctas, "raw_html": "",
    }


# ---------------------------------------------------------------------------
# URL sources
# ---------------------------------------------------------------------------

def get_hubspot_urls(min_year="2026"):
    print("Fetching HubSpot sitemap...")
    r = requests.get("https://blog.hubspot.com/sitemap.xml", headers=HEADERS, timeout=30)
    entries = re.findall(
        r'<loc>(https://blog\.hubspot\.com/[^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>', r.text
    )
    urls = []
    for url, date in entries:
        if not date.startswith(min_year):
            continue
        if "/topic-learning-path/" in url:
            continue
        urls.append(url)
    print(f"Found {len(urls)} {min_year} articles")
    return urls


def get_shopify_urls():
    """Load from pre-scraped URL list."""
    path = Path("/tmp/shopify_blog_urls_full.json")
    if not path.exists():
        path = Path("/tmp/shopify_blog_urls.json")
    if path.exists():
        return json.loads(path.read_text())
    return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", required=True, choices=["hubspot", "shopify"])
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--year", default="2026")
    args = parser.parse_args()

    brand = args.brand
    out_dir = PROJECT_ROOT / "data" / "competitors" / brand
    out_dir.mkdir(parents=True, exist_ok=True)
    classified_dir = out_dir / "classified"
    classified_dir.mkdir(parents=True, exist_ok=True)

    # Load CTA library for recommendations
    with open(settings.cta_library_path) as f:
        cta_lib = json.load(f)
    trail_lib_path = settings.cta_library_path.parent / "trail_library.json"
    trail_lib = json.loads(trail_lib_path.read_text()) if trail_lib_path.exists() else []

    # Get URLs
    if brand == "hubspot":
        urls = get_hubspot_urls(args.year)[:args.limit]
        parse_fn = parse_hubspot
    else:
        urls = get_shopify_urls()[:args.limit]
        parse_fn = parse_shopify

    done = 0
    skipped = 0
    for i, url in enumerate(urls):
        slug = url.rstrip("/").split("/")[-1]
        classified_path = classified_dir / f"{slug}.json"
        if classified_path.exists():
            skipped += 1
            continue

        try:
            article = parse_fn(url)
            if not article or not article.get("sections"):
                continue

            # Filter by year for Shopify (HubSpot already filtered by sitemap)
            if brand == "shopify":
                if args.year not in (article.get("published_date") or ""):
                    continue

            # Run full classifier
            result = classify_article(article, cta_lib, trail_lib)

            # Save classified result
            with open(classified_path, "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            done += 1
            score = result.get("cta_health_score", int(result.get("overall_health_score", 0) * 100))
            print(f"  [{done}] {article['title'][:55]} → {score}/100")

            time.sleep(0.8)

        except Exception as e:
            print(f"  ERROR {url}: {e}")
            time.sleep(1)

    print(f"\nDone: {done} classified, {skipped} skipped. → {classified_dir}")

    # Build summary JSON for dashboard
    summary = {
        "total_articles": 0, "total_sections": 0, "total_cta_issues": 0,
        "healthy_articles": 0,
        "opportunity": {"good_cta": 0, "missing_cta": 0, "wrong_cta": 0, "no_cta_needed": 0},
        "funnel_counts": {"awareness": 0, "consideration": 0, "decision": 0},
        "article_rows": [],
    }

    for p in sorted(classified_dir.glob("*.json")):
        d = json.loads(p.read_text())
        score = d.get("cta_health_score", int(d.get("overall_health_score", 0) * 100))
        sections = len(d.get("section_analyses", []))
        issues = len(d.get("cta_health_issues", []))

        summary["total_articles"] += 1
        summary["total_sections"] += sections
        summary["total_cta_issues"] += issues
        if score >= 70:
            summary["healthy_articles"] += 1

        for sa in d.get("section_analyses", []):
            f = sa.get("classification", {}).get("funnel_stage", "")
            if f in summary["funnel_counts"]:
                summary["funnel_counts"][f] += 1

        summary["article_rows"].append({
            "title": d.get("title", "")[:70],
            "author": d.get("author", ""),
            "published": (d.get("published_date") or "")[:10],
            "sections": sections,
            "misaligned": issues,
            "health": round(score / 100, 2),
        })

    summary_path = PROJECT_ROOT / "data" / "competitors" / f"{brand}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Summary: {summary['total_articles']} articles → {summary_path}")


if __name__ == "__main__":
    main()
