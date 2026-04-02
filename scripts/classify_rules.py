#!/usr/bin/env python3
"""
Rule-based classifier — no API needed.
Classifies crawled articles using keyword heuristics + CTA library matching.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from cta_engine.config import settings

# ---------------------------------------------------------------------------
# Product keyword map
# ---------------------------------------------------------------------------
PRODUCT_KEYWORDS = {
    "agentforce": [
        "agentforce", "ai agent", "autonomous agent", "agentic", "atlas reasoning",
        "digital labor", "agent builder", "copilot", "ai worker", "large action model",
        "lam ", "human in the loop", "hitl", "ai-powered agent", "agent testing",
    ],
    "einstein_ai": [
        "einstein", "predictive ai", "generative ai", "gen ai", "llm", "large language model",
        "ai model", "ai features", "machine learning", "prompt engineering",
        "foundation model", "gpt", "system-level ai", "rl training",
    ],
    "sales_cloud": [
        "sales cloud", "crm", "pipeline", "forecasting", "sales automation",
        "salesforce sales", "sales rep", "deal", "quota", "revenue", "lead",
        "opportunity", "salesblazer", "sales kickoff", "upsell", "close rate",
        "account executive", "sales cycle", "lead qualification",
    ],
    "service_cloud": [
        "service cloud", "customer service", "contact center", "case management",
        "serviceblazer", "support agent", "help desk", "itsm", "servicenow",
        "field service", "csat", "customer satisfaction", "ticketing", "service desk",
        "it service", "voice technology", "ivr", "escalation",
    ],
    "marketing_cloud": [
        "marketing cloud", "email marketing", "marketing automation", "customer journey",
        "personalization", "campaign", "segmentation", "account engagement",
        "pardot", "marketing analytics", "state of marketing", "distributed marketing",
        "seo", "semrush", "revenue marketing", "demand generation", "b2b marketing",
        "content marketing", "mailchimp", "internet marketing",
    ],
    "commerce_cloud": [
        "commerce cloud", "ecommerce", "b2c commerce", "b2b commerce",
        "storefront", "shopping", "order management", "checkout", "merchandising",
        "agentforce commerce", "retail", "commerce innovations",
    ],
    "slack": [
        "slack", "collaboration tool", "slack channel", "slack canvas", "huddle",
        "workflow builder", "context-switching", "slack for", "smbs.*slack",
    ],
    "data_cloud": [
        "data cloud", "cdp", "customer data platform", "data unification",
        "real-time profile", "identity resolution", "unified profile", "first-party data",
        "data strategy", "grl", "precision filter",
    ],
    "platform": [
        "salesforce platform", "force.com", "appexchange", "apex", "lwc",
        "sandbox", "devops", "vibe cod", "low-code", "no-code", "pro-code",
        "transaction security", "backup", "backup & recover", "data masking",
        "developer", "salesforce developer", "integration pattern", "domain-driven",
        "deployment", "devops center", "app store optimization",
    ],
    "tableau": ["tableau", "visualization", "bi dashboard", "business intelligence"],
    "mulesoft": ["mulesoft", "integration platform", "api management", "anypoint", "composing.*systems"],
    "starter": [
        "starter suite", "starter plan", "small business suite",
        "salesforce starter", "foundations", "free crm", "smb suite",
        "salesforce suites", "pro suite", "salesforce for small business",
        "crm for small", "small business crm",
    ],
    "industry_clouds": [
        "health cloud", "financial services cloud", "nonprofit", "manufacturing cloud",
        "healthcare", "insurance", "banking", "life sciences",
    ],
    "general": [],
}

# ---------------------------------------------------------------------------
# Intent keyword patterns
# ---------------------------------------------------------------------------
INTENT_PATTERNS = {
    "learning": [
        r"\bwhat (is|are)\b", r"\bintroduction to\b", r"\bexplained?\b",
        r"\bdefined?\b", r"\bguide to\b", r"\bprimer\b", r"\boverview\b",
        r"\bbasics\b", r"\b101\b", r"\bhow .* works?\b",
    ],
    "problem_solving": [
        r"\bhow to\b", r"\bsolve\b", r"\bfix\b", r"\bimprove\b", r"\bboost\b",
        r"\btips?\b", r"\bways to\b", r"\bstrateg", r"\bbest practice",
        r"\boptimize\b", r"\bstreamline\b",
    ],
    "evaluating": [
        r"\balternatives?\b", r"\bvs\.?\b", r"\bcompare\b", r"\bcomparison\b",
        r"\bbest .*(tool|software|platform|crm)\b", r"\btop \d+\b",
        r"\bchoos(e|ing)\b", r"\bselect(ing)?\b",
    ],
    "inspiring": [
        r"\bfuture of\b", r"\bvision\b", r"\btransform", r"\brevolution\b",
        r"\bnext phase\b", r"\bera of\b", r"\bpeak\b", r"\binnovat",
    ],
    "implementing": [
        r"\bstep[- ]by[- ]step\b", r"\bhow to (build|deploy|set up|implement|configure)\b",
        r"\bget started\b", r"\bsetup\b", r"\btutorial\b", r"\bplaybook\b",
        r"\bresponsibly\b", r"\blaunch\b",
    ],
}

FUNNEL_PATTERNS = {
    "decision": [
        r"\btry (for )?free\b", r"\bfree trial\b", r"\bget started\b",
        r"\bsign up\b", r"\bpricing\b", r"\bbuy\b", r"\bpurchase\b",
        r"\bbook a demo\b", r"\bcontact sales\b", r"\bget a quote\b",
    ],
    "consideration": [
        r"\bcompare\b", r"\balternative\b", r"\bvs\.?\b", r"\bevaluate\b",
        r"\bchoosing\b", r"\bbest .* for\b", r"\btop \d+\b",
        r"\bfeatures?\b", r"\bcapabilit", r"\bbenefit",
    ],
    "awareness": [
        r"\bwhat (is|are)\b", r"\bhow does\b", r"\bintroduction\b",
        r"\blearn\b", r"\bunderstand\b", r"\bdefined?\b", r"\bexplained?\b",
        r"\btrend\b", r"\bfuture of\b", r"\bstate of\b",
    ],
}

PERSONA_KEYWORDS = {
    "small_business_owner": [
        "small business", "startup", "smb", "sme", "entrepreneur", "founder",
        "growing business", "small team",
    ],
    "sales_leader": [
        "sales rep", "sales team", "account executive", "sales leader",
        "salesblazer", "sales manager", "quota", "pipeline", "revenue",
    ],
    "marketing_leader": [
        "marketer", "marketing team", "marketing leader", "cmo",
        "marketing manager", "campaign", "demand gen",
    ],
    "service_leader": [
        "service team", "support team", "serviceblazer", "contact center",
        "customer service", "service leader", "service agent",
    ],
    "it_leader": [
        "it team", "it leader", "cio", "admin", "administrator",
        "security", "platform", "it service", "itsm", "sysadmin",
    ],
    "developer": [
        "developer", "dev ", "code", "coding", "build", "deploy",
        "api", "sandbox", "vibe cod", "lwc", "apex",
    ],
    "business_leader": [
        "ceo", "executive", "leader", "company", "business", "enterprise",
        "organization", "strategy", "growth", "roi", "efficiency",
    ],
}


def detect_products(text: str, title: str) -> list[str]:
    combined = (title + " " + text[:3000]).lower()
    found = []
    for product, keywords in PRODUCT_KEYWORDS.items():
        if product == "general":
            continue
        for kw in keywords:
            if re.search(kw, combined):
                found.append(product)
                break
    # Always include agentforce for articles that discuss AI agents generically
    if not found and re.search(r"\bai\b.*\b(agent|automat|work)", combined):
        found.append("agentforce")
    # Cap at 4 most relevant products
    found = found[:4]
    return found if found else ["general"]


def detect_intent(heading: str, text: str) -> str:
    combined = (heading + " " + text[:1000]).lower()
    scores = {intent: 0 for intent in INTENT_PATTERNS}
    for intent, patterns in INTENT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, combined):
                scores[intent] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "learning"


def detect_funnel(heading: str, text: str, intent: str) -> str:
    combined = (heading + " " + text[:1000]).lower()
    scores = {f: 0 for f in FUNNEL_PATTERNS}
    for funnel, patterns in FUNNEL_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, combined):
                scores[funnel] += 1

    if scores["decision"] > 0:
        return "decision"
    if scores["consideration"] > 1:
        return "consideration"
    if scores["awareness"] > 0:
        return "awareness"

    # Fall back by intent
    intent_to_funnel = {
        "learning": "awareness",
        "inspiring": "awareness",
        "problem_solving": "consideration",
        "evaluating": "consideration",
        "implementing": "consideration",
    }
    return intent_to_funnel.get(intent, "awareness")


def detect_persona(text: str, title: str, products: list[str]) -> tuple[str, str | None]:
    combined = (title + " " + text[:2000]).lower()
    scores = {p: 0 for p in PERSONA_KEYWORDS}
    for persona, keywords in PERSONA_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                scores[persona] += 1

    # Product-based persona hints
    if "service_cloud" in products:
        scores["service_leader"] += 2
    if "marketing_cloud" in products:
        scores["marketing_leader"] += 2
    if "platform" in products or "developer" in products:
        scores["developer"] += 2
    if "starter" in products:
        scores["small_business_owner"] += 2

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary = ranked[0][0] if ranked[0][1] > 0 else "business_leader"
    secondary = ranked[1][0] if len(ranked) > 1 and ranked[1][1] > 0 and ranked[1][0] != primary else None
    return primary, secondary


def should_skip_cta(heading: str, text: str, word_count: int) -> tuple[bool, str]:
    h = heading.lower()
    t = text[:200].lower()
    if word_count < 30:
        return True, "Section too short for a CTA."
    if any(x in h for x in ["table of contents", "frequently asked", "faq", "key takeaway"]):
        return False, ""  # These are fine to have CTAs
    if h in ("introduction", "summary", "conclusion", "overview"):
        return False, ""
    # Navigation/listing sections
    if re.match(r"^\d+\.", heading.strip()) and word_count < 50:
        return True, "Short numbered intro section."
    return False, ""


def get_topic_tags(text: str, title: str, products: list[str]) -> list[str]:
    combined = (title + " " + text[:1500]).lower()
    tags = []
    tag_patterns = {
        "ai_agents": ["ai agent", "agentforce", "autonomous"],
        "small_business": ["small business", "smb", "startup", "entrepreneur"],
        "crm": ["crm", "customer relationship"],
        "ai_tools": ["ai tool", "artificial intelligence", "generative ai"],
        "sales_automation": ["sales automation", "sales process", "pipeline"],
        "marketing_automation": ["marketing automation", "email marketing"],
        "customer_service": ["customer service", "support", "help desk"],
        "data_analytics": ["analytics", "data", "dashboard", "reporting"],
        "productivity": ["productivity", "efficiency", "automate"],
        "security": ["security", "compliance", "backup", "protect"],
        "ecommerce": ["ecommerce", "commerce", "shopping", "checkout"],
        "collaboration": ["slack", "collaboration", "communication", "team"],
        "thought_leadership": ["future", "trend", "innovation", "transform"],
        "platform": ["platform", "sandbox", "developer", "api"],
        "trailhead": ["trailhead", "learning", "certification", "trail"],
    }
    for tag, keywords in tag_patterns.items():
        for kw in keywords:
            if kw in combined:
                tags.append(tag)
                break
    return tags[:6] if tags else ["general"]


def score_existing_cta(cta: dict, products: list, funnel: str, persona: str, cta_lib: list) -> dict:
    url = cta.get("button_url", "")
    button_text = cta.get("button_text", "").lower()

    # Try to find in library
    lib_match = None
    for lib_cta in cta_lib:
        dest = lib_cta.get("destination_url", "")
        # Normalize comparison
        if dest and (dest[:50] in url or url[:50] in dest):
            lib_match = lib_cta
            break

    funnel_order = ["awareness", "consideration", "decision"]

    if lib_match:
        cta_funnel = lib_match["funnel_stage"]
        cta_product = lib_match["product"]
    else:
        # Infer from URL/text
        if any(x in url for x in ["trial", "signup", "free-crm", "freetrial"]):
            cta_funnel = "decision"
        elif any(x in url for x in ["trailhead", "report", "guide", "form/conf", "ebook"]):
            cta_funnel = "awareness"
        else:
            cta_funnel = "consideration"
        cta_product = next((p for p in products if p != "general"), "sales_cloud")

    # Funnel alignment score
    try:
        cf = funnel_order.index(cta_funnel)
        sf = funnel_order.index(funnel)
        diff = cf - sf
    except ValueError:
        diff = 0

    base = 0.55
    if diff == 0:
        base += 0.30
        funnel_align = "match"
    elif abs(diff) == 1:
        base += 0.10
        funnel_align = "adjacent"
    else:
        base -= 0.20
        funnel_align = "mismatch"

    # Product alignment
    if lib_match and lib_match["product"] in products:
        base += 0.15
        prod_align = "match"
    elif lib_match and lib_match["product"] == "agentforce" and "agentforce" in products:
        base += 0.15
        prod_align = "match"
    else:
        prod_align = "partial"

    score = round(min(1.0, max(0.0, base)), 2)
    issues = []
    if funnel_align == "mismatch":
        issues.append(f"Funnel mismatch: CTA is {cta_funnel}-stage but section is {funnel}-stage")
    if prod_align == "partial":
        issues.append("Product alignment is partial — a more targeted CTA may perform better")

    return {
        "relevance_score": score,
        "funnel_alignment": funnel_align,
        "persona_match": "match",
        "product_alignment": prod_align,
        "issues": issues,
        "rationale": (
            f"CTA targets {cta_funnel}-stage readers; section is {funnel}-stage. "
            f"Product alignment: {prod_align}."
        ),
    }


def _score_item(item: dict, products: list, funnel: str, persona: str) -> float:
    """Unified scoring for both CTAs and trails."""
    funnel_order = ["awareness", "consideration", "decision"]
    sf = funnel_order.index(funnel) if funnel in funnel_order else 0
    cf = funnel_order.index(item["funnel_stage"]) if item["funnel_stage"] in funnel_order else 0

    s = 0.0
    diff = cf - sf
    if diff == 0:
        s += 0.45
    elif diff == 1:
        s += 0.25
    elif diff == -1:
        s += 0.10

    item_product = item.get("product", "general")
    if item_product in products:
        s += 0.40
    elif item_product == "general":
        s += 0.05
    elif item_product == "agentforce" and "agentforce" in products:
        s += 0.40

    # Multi-product trails get a bonus if any product matches
    for p in item.get("products", []):
        if p in products and p != item_product:
            s += 0.10
            break

    personas = item.get("target_personas", [])
    if persona in personas or "all" in personas:
        s += 0.10

    return round(s, 2)


def get_recommendations(products: list, funnel: str, persona: str, cta_lib: list,
                        trail_lib: list = None, n: int = 3) -> list[dict]:
    """Return top n recommendations mixing CTAs and trails, each labeled by type."""
    funnel_order = ["awareness", "consideration", "decision"]

    scored = []
    for cta in cta_lib:
        s = _score_item(cta, products, funnel, persona)
        scored.append((s, "cta", cta))

    for trail in (trail_lib or []):
        s = _score_item(trail, products, funnel, persona)
        scored.append((s, "trail", trail))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    seen_products = set()
    seen_types = {"cta": 0, "trail": 0}

    for score, item_type, item in scored:
        if len(results) >= n:
            break
        prod_key = item.get("product", "general")
        if prod_key in seen_products and len(seen_products) < 3:
            continue
        # Ensure at least 1 trail in recommendations if trails exist
        if item_type == "cta" and seen_types["trail"] == 0 and len(results) >= n - 1 and trail_lib:
            continue
        seen_products.add(prod_key)
        seen_types[item_type] += 1

        if item_type == "trail":
            results.append({
                "type": "trail",
                "trail_id": item["trail_id"],
                "name": item["name"],
                "url": item["url"],
                "duration_minutes": item.get("duration_minutes"),
                "score": score,
                "match_rationale": (
                    f"Trail targets {item['product']} at {item['funnel_stage']} stage "
                    f"for {funnel}-stage {persona} reader."
                ),
            })
        else:
            results.append({
                "type": "cta",
                "cta_id": item["cta_id"],
                "score": score,
                "match_rationale": (
                    f"CTA targets {item['product']} at {item['funnel_stage']} stage "
                    f"for {funnel}-stage {persona} reader."
                ),
            })
    return results


def classify_article(article: dict, cta_lib: list, trail_lib: list = None) -> dict:
    title = article["title"]
    author = article.get("author", "")
    published_date = article.get("published_date", "")
    sections = article.get("sections", [])
    existing_ctas = article.get("existing_ctas", [])
    cta_by_section = {c.get("position_after_section", -1): c for c in existing_ctas}

    section_analyses = []
    section_scores = []
    misaligned = 0

    for section in sections:
        idx = section["index"]
        heading = section.get("heading", "")
        text = section.get("text", "")
        word_count = section.get("word_count", 0)

        products = detect_products(text, title)
        intent = detect_intent(heading, text)
        funnel = detect_funnel(heading, text, intent)
        primary_persona, secondary_persona = detect_persona(text, title, products)
        tags = get_topic_tags(text, title, products)

        skip_cta, skip_reason = should_skip_cta(heading, text, word_count)

        existing_cta_raw = cta_by_section.get(idx)
        existing_cta_obj = None
        existing_cta_score_obj = None

        if existing_cta_raw and existing_cta_raw.get("button_text"):
            existing_cta_obj = {
                "heading": existing_cta_raw.get("heading", ""),
                "body": existing_cta_raw.get("body", ""),
                "button_text": existing_cta_raw.get("button_text", ""),
                "button_url": existing_cta_raw.get("button_url", ""),
                "position_after_section": idx,
            }
            existing_cta_score_obj = score_existing_cta(
                existing_cta_raw, products, funnel, primary_persona, cta_lib
            )

        if skip_cta:
            recommendations = []
            recommend_no_cta = True
            no_cta_reason = skip_reason
        else:
            recommendations = get_recommendations(products, funnel, primary_persona, cta_lib, trail_lib)
            recommend_no_cta = False
            no_cta_reason = ""

        # Health scoring
        has_cta = existing_cta_obj is not None
        if not has_cta and not recommend_no_cta and recommendations:
            section_scores.append(0.0)
            misaligned += 1
        elif has_cta and recommend_no_cta:
            section_scores.append(0.0)
            misaligned += 1
        elif has_cta and existing_cta_score_obj:
            s = existing_cta_score_obj["relevance_score"]
            section_scores.append(s)
            if s < 0.5:
                misaligned += 1
        else:
            section_scores.append(1.0)

        confidence = 0.75  # rule-based confidence
        rationale = (
            f"Rule-based: {intent} intent detected in '{heading}'. "
            f"Products: {', '.join(products)}. Funnel: {funnel}."
        )

        section_analyses.append({
            "section_index": idx,
            "section_heading": heading,
            "classification": {
                "reader_intent": intent,
                "primary_persona": primary_persona,
                "secondary_persona": secondary_persona,
                "funnel_stage": funnel,
                "product_alignment": products,
                "topic_tags": tags,
                "confidence": confidence,
                "rationale": rationale,
            },
            "existing_cta": existing_cta_obj,
            "existing_cta_score": existing_cta_score_obj,
            "recommendations": recommendations,
            "recommend_no_cta": recommend_no_cta,
            "no_cta_reason": no_cta_reason,
        })

    health = sum(section_scores) / len(section_scores) if section_scores else 1.0

    return {
        "url": article["url"],
        "slug": article["slug"],
        "title": title,
        "author": author,
        "published_date": published_date,
        "section_analyses": section_analyses,
        "overall_health_score": round(health, 4),
        "misaligned_count": misaligned,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Classify all unclassified crawled articles")
    parser.add_argument("--slug", help="Classify a specific article")
    parser.add_argument("--force", action="store_true", help="Re-classify already-classified articles too")
    args = parser.parse_args()

    crawled_dir = settings.crawled_dir
    classified_dir = settings.classified_dir
    classified_dir.mkdir(parents=True, exist_ok=True)

    with open(settings.cta_library_path) as f:
        cta_lib = json.load(f)

    trail_lib_path = settings.cta_library_path.parent / "trail_library.json"
    trail_lib = []
    if trail_lib_path.exists():
        with open(trail_lib_path) as f:
            trail_lib = json.load(f)
        print(f"Loaded {len(trail_lib)} trails from trail_library.json")

    if args.slug:
        paths = [crawled_dir / f"{args.slug}.json"]
    elif args.all:
        paths = sorted(crawled_dir.glob("*.json"))
    else:
        parser.print_help()
        return

    done = 0
    skipped = 0
    for path in paths:
        out_path = classified_dir / path.name
        if out_path.exists() and not args.force:
            skipped += 1
            continue
        with open(path) as f:
            article = json.load(f)
        if not article.get("title") or not article.get("sections"):
            print(f"  SKIP (no content): {path.stem}")
            continue
        result = classify_article(article, cta_lib, trail_lib)
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        done += 1
        print(f"  [{done}] {article['title'][:65]} → {result['overall_health_score']:.0%}")

    print(f"\nDone: {done} classified, {skipped} skipped (already done).")


if __name__ == "__main__":
    main()
