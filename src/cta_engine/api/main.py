import json
import logging
from io import StringIO
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from cta_engine.classifier.pipeline import analyze_article
from cta_engine.config import settings
from cta_engine.models.schemas import ArticleAnalysis
from cta_engine.scoring.engine import generate_health_report, get_summary_stats, load_all_analyses

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="CTA Engine", version="0.1.0")


@app.get("/api/articles")
def list_articles():
    """List all crawled articles."""
    crawled_dir = settings.crawled_dir
    if not crawled_dir.exists():
        return []

    articles = []
    for path in sorted(crawled_dir.glob("*.json")):
        with open(path) as f:
            data = json.load(f)

        # Check if analysis exists
        classified_path = settings.classified_dir / path.name
        has_analysis = classified_path.exists()

        articles.append({
            "slug": data.get("slug", path.stem),
            "title": data.get("title", ""),
            "url": data.get("url", ""),
            "author": data.get("author", ""),
            "category": data.get("category", ""),
            "section_count": len(data.get("sections", [])),
            "cta_count": len(data.get("existing_ctas", [])),
            "has_analysis": has_analysis,
        })

    return articles


@app.get("/api/articles/{slug}")
def get_article(slug: str):
    """Get a single crawled article with sections and CTAs."""
    path = settings.crawled_dir / f"{slug}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Article '{slug}' not found")

    with open(path) as f:
        return json.load(f)


@app.post("/api/analysis/{slug}")
def run_analysis(slug: str):
    """Run the full classification + matching pipeline on one article."""
    path = settings.crawled_dir / f"{slug}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Article '{slug}' not found")

    with open(path) as f:
        article_data = json.load(f)

    logger.info(f"Starting analysis for: {slug}")
    analysis = analyze_article(article_data)
    return analysis.model_dump()


@app.get("/api/analysis/{slug}")
def get_analysis(slug: str):
    """Get existing analysis results for an article."""
    path = settings.classified_dir / f"{slug}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No analysis for '{slug}'")

    with open(path) as f:
        return json.load(f)


@app.get("/api/summary")
def get_summary():
    """Get aggregate stats across all analyzed articles."""
    analyses = load_all_analyses()
    if not analyses:
        return {"message": "No analyses found. Run analysis on some articles first."}

    df = generate_health_report(analyses)
    return get_summary_stats(df)


@app.get("/api/export/csv")
def export_csv():
    """Export all analysis results as CSV."""
    analyses = load_all_analyses()
    if not analyses:
        raise HTTPException(status_code=404, detail="No analyses found")

    df = generate_health_report(analyses)
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cta_health_report.csv"},
    )
