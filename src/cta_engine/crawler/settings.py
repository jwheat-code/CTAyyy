BOT_NAME = "cta_engine"

SPIDER_MODULES = ["cta_engine.crawler.spiders"]
NEWSPIDER_MODULE = "cta_engine.crawler.spiders"

USER_AGENT = "CTAEngineBot/1.0 (research audit; non-commercial)"
ROBOTSTXT_OBEY = True

CONCURRENT_REQUESTS = 1
DOWNLOAD_DELAY = 2.5

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2.5
AUTOTHROTTLE_MAX_DELAY = 10

HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 86400
HTTPCACHE_DIR = "httpcache"

ITEM_PIPELINES = {
    "cta_engine.crawler.pipelines.JsonWriterPipeline": 300,
}

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

LOG_LEVEL = "INFO"
