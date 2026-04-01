#!/usr/bin/env python3
"""
Scrape all unique CTAs from the Salesforce blog and build a ground-truth library.
Outputs data/cta_library_discovered.json with every unique CTA found.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bs4 import BeautifulSoup


def normalize_url(url: str) -> str:
    """Strip tracking params and normalize URL for deduplication."""
    if not url:
        return ""
    parsed = urlparse(url)
    # Drop query params that are just tracking (?bc=DB, ?d=cta, etc.)
    clean = parsed._replace(query="", fragment="")
    return clean.geturl().rstrip("/")


def extract_ctas_from_html(html: str) -> list[dict]:
    """Extract all CTA blocks from article HTML."""
    soup = BeautifulSoup(html, "html.parser")
    ctas = []
    seen = set()

    for button in soup.select("a.wp-block-button__link"):
        url = button.get("href", "").strip()
        button_text = button.get_text(strip=True)

        if not button_text or not url:
            continue

        norm_url = normalize_url(url)
        if norm_url in seen:
            continue
        seen.add(norm_url)

        # Walk up to find the containing block
        block = button
        for ancestor in button.parents:
            classes = " ".join(ancestor.get("class", []))
            if any(k in classes for k in ("wp-block-offer", "wp-block-columns", "has-background")):
                block = ancestor
                break

        heading_el = block.select_one("h2, h3, h4, strong") if block != button else None
        heading = heading_el.get_text(strip=True) if heading_el else ""

        paras = block.select("p") if block != button else []
        body = " ".join(p.get_text(strip=True) for p in paras if p.get_text(strip=True))[:300]

        ctas.append({
            "heading": heading,
            "body": body,
            "button_text": button_text,
            "button_url": url,
            "normalized_url": norm_url,
        })

    return ctas


def infer_metadata(cta: dict) -> dict:
    """Infer product, funnel stage, and content type from URL and text."""
    url = cta["button_url"].lower()
    heading = cta["heading"].lower()
    button = cta["button_text"].lower()
    combined = f"{url} {heading} {button}"

    # Product
    product = "general"
    product_map = {
        "agentforce": "agentforce",
        "sales": "sales_cloud",
        "service": "service_cloud",
        "marketing": "marketing_cloud",
        "commerce": "commerce_cloud",
        "data": "data_cloud",
        "tableau": "tableau",
        "mulesoft": "mulesoft",
        "slack": "slack",
        "trailhead": "platform",
        "trailblazer": "platform",
        "starter": "starter",
        "foundations": "starter",
        "small.business": "starter",
        "smb": "starter",
    }
    for keyword, prod in product_map.items():
        if keyword in combined:
            product = prod
            break

    # Content type + funnel stage
    content_type = "general"
    funnel_stage = "consideration"

    if any(x in combined for x in ("freetrial", "free-trial", "trial", "try it free", "try for free", "start free")):
        content_type = "trial"
        funnel_stage = "decision"
    elif any(x in combined for x in ("demo", "watch demo", "see it in action")):
        content_type = "demo"
        funnel_stage = "consideration"
    elif any(x in combined for x in ("contact", "talk to", "speak to", "get in touch", "contactme")):
        content_type = "contact"
        funnel_stage = "decision"
    elif any(x in combined for x in ("pricing", "price", "cost", "plan")):
        content_type = "pricing"
        funnel_stage = "decision"
    elif any(x in combined for x in ("ebook", "e-book", "guide", "playbook", "whitepaper", "report", "download")):
        content_type = "guide"
        funnel_stage = "awareness"
    elif any(x in combined for x in ("webinar", "event", "register", "join us")):
        content_type = "event"
        funnel_stage = "awareness"
    elif any(x in combined for x in ("trailhead", "learn", "training", "badge", "trail")):
        content_type = "learning"
        funnel_stage = "awareness"
    elif any(x in combined for x in ("newsletter", "subscribe", "sign up")):
        content_type = "newsletter"
        funnel_stage = "awareness"
    elif any(x in combined for x in ("customer", "story", "case study")):
        content_type = "social_proof"
        funnel_stage = "consideration"

    return {
        "product": product,
        "funnel_stage": funnel_stage,
        "content_type": content_type,
    }


def main():
    crawled_dir = Path(__file__).resolve().parent.parent / "data" / "crawled"
    output_path = Path(__file__).resolve().parent.parent / "data" / "cta_library_discovered.json"

    if not crawled_dir.exists():
        print("No crawled data found. Run the crawler first.")
        sys.exit(1)

    files = list(crawled_dir.glob("*.json"))
    print(f"Scanning {len(files)} articles for CTAs...")

    # Collect all CTAs, deduplicated by normalized URL
    seen_urls = {}  # normalized_url -> cta dict
    url_article_count = defaultdict(int)  # how many articles each CTA appears in

    for path in sorted(files):
        with open(path) as f:
            article = json.load(f)

        html = article.get("raw_html", "")
        if not html:
            continue

        ctas = extract_ctas_from_html(html)
        for cta in ctas:
            norm = cta["normalized_url"]
            if norm:
                url_article_count[norm] += 1
                if norm not in seen_urls:
                    seen_urls[norm] = cta

    print(f"Found {len(seen_urls)} unique CTAs across {len(files)} articles\n")

    # Build library entries
    library = []
    for i, (norm_url, cta) in enumerate(
        sorted(seen_urls.items(), key=lambda x: -url_article_count[x[0]])
    ):
        meta = infer_metadata(cta)
        count = url_article_count[norm_url]

        cta_id = norm_url.split("salesforce.com/")[-1].strip("/").replace("/", "-")[:50] or f"cta-{i}"

        entry = {
            "cta_id": cta_id,
            "headline": cta["heading"] or cta["button_text"],
            "body": cta["body"],
            "button_text": cta["button_text"],
            "destination_url": cta["button_url"],
            "product": meta["product"],
            "funnel_stage": meta["funnel_stage"],
            "content_type": meta["content_type"],
            "target_personas": [],  # to be enriched later
            "tags": [],
            "appearances": count,  # how many articles this CTA appears in
        }
        library.append(entry)

        print(f"  [{count:3}x] {entry['funnel_stage']:13} | {entry['product']:15} | {entry['button_text'][:40]:40} | {cta['button_url'][:60]}")

    with open(output_path, "w") as f:
        json.dump(library, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(library)} CTAs to {output_path}")
    print("\nTop content types:")
    from collections import Counter
    types = Counter(e["content_type"] for e in library)
    for ct, n in types.most_common():
        print(f"  {ct}: {n}")

    print("\nTop funnel stages:")
    stages = Counter(e["funnel_stage"] for e in library)
    for s, n in stages.most_common():
        print(f"  {s}: {n}")


if __name__ == "__main__":
    main()
