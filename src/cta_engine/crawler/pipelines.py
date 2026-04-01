import json
from pathlib import Path


class JsonWriterPipeline:
    def open_spider(self, spider):
        self.output_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "crawled"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_item(self, item, spider):
        slug = item["slug"]
        # Reject slugs that look like query strings or are too short
        if not slug or slug.startswith("?") or slug.startswith("#") or len(slug) < 3:
            spider.logger.warning(f"Skipping bad slug: {slug!r}")
            return item
        path = self.output_dir / f"{slug}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dict(item), f, indent=2, ensure_ascii=False)
        spider.logger.info(f"Saved article: {slug}")
        return item
