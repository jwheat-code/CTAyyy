#!/usr/bin/env python3
"""
Crawl specific article URLs discovered from the blog sitemap.
No pagination needed — hits each URL directly.
"""
import json
import sys
import urllib.request
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from cta_engine.config import settings

from scrapy.crawler import CrawlerProcess
from cta_engine.crawler.spiders.blog_spider import SalesforceBlogSpider


class SitemapSpider(SalesforceBlogSpider):
    """Spider variant that starts from an explicit URL list instead of category pages."""
    name = "salesforce_blog_sitemap"

    def __init__(self, url_list_path=None, *args, **kwargs):
        # Don't call parent __init__ which sets start_urls
        import scrapy
        self.max_articles = 9999
        self.min_year = "2000"  # No year filter — sitemap already filtered
        self.seen_urls = set()
        self.article_count = 0
        self.custom_settings = {"CLOSESPIDER_ITEMCOUNT": 9999}

        crawled_dir = Path(__file__).resolve().parent.parent / "data" / "crawled"
        self.crawled_slugs = {p.stem for p in crawled_dir.glob("*.json")} if crawled_dir.exists() else set()

        if url_list_path:
            with open(url_list_path) as f:
                entries = json.load(f)
            self.start_urls = [e["url"] for e in entries]
        else:
            self.start_urls = []

    def parse(self, response):
        """Each start URL is already an article — parse directly."""
        from urllib.parse import urlparse
        parsed = urlparse(response.url)
        slug = parsed.path.rstrip("/").split("/")[-1]
        if slug and slug not in self.crawled_slugs:
            yield from self.parse_article(response)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--url-list", default="/tmp/sitemap_urls_2025.json",
                        help="JSON file with [{slug, url, date}] entries")
    parser.add_argument("--limit", type=int, default=999)
    args = parser.parse_args()

    # Trim to limit
    with open(args.url_list) as f:
        entries = json.load(f)
    entries = entries[:args.limit]
    print(f"Crawling {len(entries)} articles from sitemap...")

    tmp_path = "/tmp/sitemap_urls_current.json"
    with open(tmp_path, "w") as f:
        json.dump(entries, f)

    scrapy_settings = {
        "BOT_NAME": "cta_engine",
        "USER_AGENT": "CTAEngineBot/1.0 (research audit; non-commercial)",
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.5,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 2.5,
        "AUTOTHROTTLE_MAX_DELAY": 10,
        "HTTPCACHE_ENABLED": True,
        "HTTPCACHE_EXPIRATION_SECS": 86400,
        "HTTPCACHE_DIR": str(Path(__file__).resolve().parent.parent / ".scrapy" / "httpcache"),
        "ITEM_PIPELINES": {"cta_engine.crawler.pipelines.JsonWriterPipeline": 300},
        "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "LOG_LEVEL": "WARNING",
        "CLOSESPIDER_ITEMCOUNT": args.limit,
    }

    process = CrawlerProcess(scrapy_settings)
    process.crawl(SitemapSpider, url_list_path=tmp_path)
    process.start()
    print(f"\nDone. Crawled articles saved to {settings.crawled_dir}")


if __name__ == "__main__":
    main()
