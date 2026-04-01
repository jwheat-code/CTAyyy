import re
from urllib.parse import urlparse

import scrapy
from bs4 import BeautifulSoup

from cta_engine.crawler.items import ArticleItem


class SalesforceBlogSpider(scrapy.Spider):
    name = "salesforce_blog"
    allowed_domains = ["www.salesforce.com"]

    # Category listing pages — pages 1-5 to get deeper into archive
    start_urls = [
        url
        for base in [
            "https://www.salesforce.com/blog/",
            "https://www.salesforce.com/blog/ai/",
            "https://www.salesforce.com/blog/agentic-ai/",
            "https://www.salesforce.com/blog/sales/",
            "https://www.salesforce.com/blog/service/",
            "https://www.salesforce.com/blog/marketing/",
            "https://www.salesforce.com/blog/commerce/",
            "https://www.salesforce.com/blog/analytics/",
            "https://www.salesforce.com/blog/it/",
            "https://www.salesforce.com/blog/small-business/",
        ]
        for url in [base] + [f"{base}page/{p}/" for p in range(2, 6)]
    ]

    custom_settings = {
        "CLOSESPIDER_ITEMCOUNT": 100,
    }

    def __init__(self, max_articles=100, min_year="2026", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_articles = int(max_articles)
        self.min_year = str(min_year)
        self.seen_urls = set()
        self.article_count = 0
        self.custom_settings["CLOSESPIDER_ITEMCOUNT"] = self.max_articles

        # Pre-load already-crawled slugs so we can skip them
        from pathlib import Path
        crawled_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "crawled"
        self.crawled_slugs = {p.stem for p in crawled_dir.glob("*.json")} if crawled_dir.exists() else set()

    def parse(self, response):
        """Parse category listing pages to discover article URLs."""
        links = response.css("a::attr(href)").getall()
        for href in links:
            if not href:
                continue
            # Normalize to absolute URL
            url = response.urljoin(href)
            parsed = urlparse(url)

            # Match article pattern: /blog/{slug}/ but not /blog/author/ or /blog/category/
            path = parsed.path.rstrip("/")
            if not path.startswith("/blog/"):
                continue

            parts = path.split("/")
            # Article URLs are /blog/{slug} (3 parts: '', 'blog', 'slug')
            if len(parts) != 3:
                continue

            slug = parts[2]
            # Skip non-article pages
            if slug in ("author", "category", "search", "feed", "page"):
                continue

            # Skip category pages we already know about
            category_slugs = {
                "ai", "agentic-ai", "sales", "service", "marketing",
                "commerce", "analytics", "it", "small-business",
            }
            if slug in category_slugs:
                continue

            canonical = f"https://www.salesforce.com/blog/{slug}/"
            if canonical in self.seen_urls:
                continue
            if slug in self.crawled_slugs:
                continue
            self.seen_urls.add(canonical)

            if self.article_count >= self.max_articles:
                return

            yield scrapy.Request(canonical, callback=self.parse_article, meta={"slug": slug})

    def parse_article(self, response):
        """Extract article content, sections, and CTAs."""
        from urllib.parse import urlparse as _urlparse
        slug = response.meta.get("slug") or _urlparse(response.url).path.rstrip("/").split("/")[-1]
        soup = BeautifulSoup(response.text, "html.parser")

        # Title
        title_el = soup.select_one("h1")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return

        # Author
        author_el = soup.select_one(".author-name, .post-author, [class*='author'] a")
        author = author_el.get_text(strip=True) if author_el else ""

        # Published date
        date_meta = soup.select_one('meta[property="article:published_time"]')
        published_date = date_meta["content"] if date_meta else ""

        # Skip articles older than min_year
        if published_date and published_date[:4] < self.min_year:
            self.logger.info(f"Skipping pre-{self.min_year} article: {slug} ({published_date[:10]})")
            return

        # Category
        cat_el = soup.select_one(".category-badge, .post-category, [class*='category'] a")
        category = cat_el.get_text(strip=True) if cat_el else ""

        # Find the article body — prefer the post content div where editorial h2s live
        article_el = (
            soup.select_one(".post__content.post__content-v2")
            or soup.select_one(".post__content")
            or soup.select_one("article, .post-content, .article-body, .entry-content")
            or soup.select_one("main, .main-content")
        )
        if not article_el:
            self.logger.warning(f"No article body found for {slug}")
            return

        # Extract sections (split on h2 boundaries)
        sections = self._extract_sections(article_el)

        # Extract existing CTAs from the full page (CTA blocks may be outside post__content)
        full_article = soup.select_one("article") or article_el
        existing_ctas = self._extract_ctas(full_article, sections)

        # Mark sections that have CTAs after them
        cta_positions = {cta["position_after_section"] for cta in existing_ctas}
        for section in sections:
            section["has_existing_cta"] = section["index"] in cta_positions

        self.article_count += 1

        yield ArticleItem(
            url=response.url,
            slug=slug,
            title=title,
            author=author,
            published_date=published_date,
            category=category,
            sections=sections,
            existing_ctas=existing_ctas,
            raw_html=str(article_el),
        )

    def _extract_sections(self, article_el):
        """Split article content into sections based on h2 headings.

        Uses a flat traversal of all block-level elements and h2s in document
        order, regardless of nesting depth.
        """
        # CTA / chrome class fragments to skip
        SKIP_CLASSES = {
            "has-background", "wp-block-button", "wp-block-offer",
            "related-trail", "post__social", "post__tags", "post__author",
            "newsletter", "sidebar",
        }

        def should_skip(el):
            classes = " ".join(el.get("class", []))
            return any(skip in classes for skip in SKIP_CLASSES)

        # Collect all h2s and paragraph-level elements in document order
        tags_of_interest = article_el.find_all(["h2", "p", "ul", "ol", "blockquote"])

        sections = []
        current_heading = "Introduction"
        current_text_parts = []
        current_links = []
        section_idx = 0

        for el in tags_of_interest:
            # Skip elements inside CTA / chrome blocks
            if any(should_skip(ancestor) for ancestor in el.parents if hasattr(ancestor, "get")):
                continue

            if el.name == "h2":
                heading_text = el.get_text(strip=True)
                # Skip non-editorial h2s (social share, "Related articles", etc.)
                if heading_text.lower() in {"share article", "share", "related articles",
                                             "explore related content by topic"}:
                    continue

                if current_text_parts:
                    text = re.sub(r"\s+", " ", " ".join(current_text_parts).strip())
                    if len(text) > 50:
                        sections.append({
                            "index": section_idx,
                            "heading": current_heading,
                            "text": text,
                            "word_count": len(text.split()),
                            "has_existing_cta": False,
                            "inline_links": current_links,
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
                    link_text = link.get_text(strip=True)
                    link_href = link.get("href", "")
                    if link_text and link_href:
                        current_links.append({"text": link_text, "href": link_href})

        # Last section
        if current_text_parts:
            text = re.sub(r"\s+", " ", " ".join(current_text_parts).strip())
            if len(text) > 50:
                sections.append({
                    "index": section_idx,
                    "heading": current_heading,
                    "text": text,
                    "word_count": len(text.split()),
                    "has_existing_cta": False,
                    "inline_links": current_links,
                })

        return sections

    def _extract_ctas(self, article_el, sections):
        """Extract existing CTA blocks from the article.

        The Salesforce blog uses wp-block-offer containers for CTAs.
        Each button link (a.wp-block-button__link) is a CTA.
        We walk all buttons in document order and associate each with the
        nearest preceding h2 section.
        """
        ctas = []
        seen_urls = set()

        # Collect all CTA buttons in document order
        buttons = article_el.select("a.wp-block-button__link")

        for button in buttons:
            url = button.get("href", "").strip()
            button_text = button.get_text(strip=True)

            if not button_text or not url:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Walk up to find the containing offer/CTA block
            block = button
            for ancestor in button.parents:
                classes = " ".join(ancestor.get("class", []))
                if any(k in classes for k in ("wp-block-offer", "wp-block-columns", "has-background")):
                    block = ancestor
                    break

            # Extract heading and body from the block
            heading_el = block.select_one("h2, h3, h4, strong") if block != button else None
            heading = heading_el.get_text(strip=True) if heading_el else ""

            paras = block.select("p") if block != button else []
            body = " ".join(p.get_text(strip=True) for p in paras if p.get_text(strip=True))

            # Find which section this CTA follows (by preceding h2 in document order)
            position = self._find_cta_position_by_h2(button, article_el, sections)

            ctas.append({
                "heading": heading,
                "body": body[:300],
                "button_text": button_text,
                "button_url": url,
                "position_after_section": position,
            })

        return ctas

    def _find_cta_position_by_h2(self, button_el, article_el, sections):
        """Find the section index that precedes this button in document order.

        Only considers editorial h2s (not h2s inside CTA/offer blocks).
        """
        CTA_BLOCK_CLASSES = {"wp-block-offer", "wp-block-columns", "has-background"}

        def is_inside_cta_block(el):
            return any(
                any(cls in " ".join(ancestor.get("class", [])) for cls in CTA_BLOCK_CLASSES)
                for ancestor in el.parents
                if hasattr(ancestor, "get")
            )

        all_tags = article_el.find_all(["h2", "a"])
        last_editorial_h2 = None

        for tag in all_tags:
            if tag.name == "h2":
                if is_inside_cta_block(tag):
                    continue
                text = tag.get_text(strip=True)
                if text.lower() not in {"share article", "share", "related articles",
                                        "explore related content by topic"}:
                    last_editorial_h2 = text
            elif tag is button_el:
                break

        if last_editorial_h2:
            for section in sections:
                if section["heading"] == last_editorial_h2:
                    return section["index"]

        return len(sections) - 1 if sections else 0
