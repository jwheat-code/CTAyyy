import scrapy


class ArticleItem(scrapy.Item):
    url = scrapy.Field()
    slug = scrapy.Field()
    title = scrapy.Field()
    author = scrapy.Field()
    published_date = scrapy.Field()
    category = scrapy.Field()
    sections = scrapy.Field()
    existing_ctas = scrapy.Field()
    raw_html = scrapy.Field()
