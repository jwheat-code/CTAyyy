#!/usr/bin/env python3
"""Run the Salesforce blog crawler."""
import sys
from pathlib import Path

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cta_engine.crawler.spiders.blog_spider import SalesforceBlogSpider


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Crawl Salesforce blog for CTA audit")
    parser.add_argument("--max-articles", type=int, default=20, help="Max articles to crawl")
    args = parser.parse_args()

    settings = {
        "BOT_NAME": "cta_engine",
        "SPIDER_MODULES": ["cta_engine.crawler.spiders"],
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
        "ITEM_PIPELINES": {
            "cta_engine.crawler.pipelines.JsonWriterPipeline": 300,
        },
        "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "LOG_LEVEL": "INFO",
        "CLOSESPIDER_ITEMCOUNT": args.max_articles,
    }

    process = CrawlerProcess(settings)
    process.crawl(SalesforceBlogSpider, max_articles=args.max_articles)
    process.start()


if __name__ == "__main__":
    main()
