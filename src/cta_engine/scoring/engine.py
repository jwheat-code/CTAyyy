"""Scoring utilities for CTA health reports.

The primary scoring happens in the classifier pipeline via Claude.
This module provides aggregate scoring and reporting functions.
"""

import json
from pathlib import Path

import pandas as pd

from cta_engine.config import settings
from cta_engine.models.schemas import ArticleAnalysis


def load_all_analyses() -> list[ArticleAnalysis]:
    """Load all classified article analyses."""
    analyses = []
    classified_dir = settings.classified_dir
    if not classified_dir.exists():
        return analyses

    for path in sorted(classified_dir.glob("*.json")):
        with open(path) as f:
            data = json.load(f)
        analyses.append(ArticleAnalysis.model_validate(data))
    return analyses


def generate_health_report(analyses: list[ArticleAnalysis]) -> pd.DataFrame:
    """Generate a CTA health report across all analyzed articles."""
    rows = []
    for a in analyses:
        for sa in a.section_analyses:
            top_rec = sa.recommendations[0] if sa.recommendations else None
            rows.append({
                "article_title": a.title,
                "article_url": a.url,
                "article_slug": a.slug,
                "article_health_score": a.overall_health_score,
                "section_index": sa.section_index,
                "section_heading": sa.section_heading,
                "reader_intent": sa.classification.reader_intent.value,
                "persona": sa.classification.primary_persona.value,
                "funnel_stage": sa.classification.funnel_stage.value,
                "products": ", ".join(sa.classification.product_alignment),
                "confidence": sa.classification.confidence,
                "existing_cta_heading": sa.existing_cta.heading if sa.existing_cta else "",
                "existing_cta_button": sa.existing_cta.button_text if sa.existing_cta else "",
                "existing_cta_url": sa.existing_cta.button_url if sa.existing_cta else "",
                "existing_cta_score": sa.existing_cta_score.relevance_score if sa.existing_cta_score else None,
                "existing_cta_funnel_alignment": sa.existing_cta_score.funnel_alignment if sa.existing_cta_score else "",
                "existing_cta_persona_match": sa.existing_cta_score.persona_match if sa.existing_cta_score else "",
                "existing_cta_issues": "; ".join(sa.existing_cta_score.issues) if sa.existing_cta_score else "",
                "existing_cta_score_rationale": sa.existing_cta_score.rationale if sa.existing_cta_score else "",
                "recommended_cta_id": top_rec.cta_id if top_rec else "",
                "recommended_score": top_rec.score if top_rec else 0.0,
                "recommended_rationale": top_rec.match_rationale if top_rec else "",
                "recommend_no_cta": sa.recommend_no_cta,
                "no_cta_reason": sa.no_cta_reason,
                "is_misaligned": _is_misaligned(sa),
            })

    return pd.DataFrame(rows)


def _is_misaligned(sa) -> bool:
    """Determine if a section's CTA is misaligned.

    - Missing CTA where one is recommended → misaligned
    - Has CTA where none is recommended → misaligned
    - Has CTA with relevance score < 0.5 → misaligned (wrong CTA)
    """
    if not sa.existing_cta and sa.recommendations and not sa.recommend_no_cta:
        return True
    if sa.existing_cta and sa.recommend_no_cta:
        return True
    if sa.existing_cta and sa.existing_cta_score and sa.existing_cta_score.relevance_score < 0.5:
        return True
    return False


def get_summary_stats(df: pd.DataFrame) -> dict:
    """Compute summary statistics from the health report."""
    total_sections = len(df)
    misaligned = df["is_misaligned"].sum()
    articles = df["article_slug"].nunique()

    return {
        "total_articles": articles,
        "total_sections": total_sections,
        "misaligned_sections": int(misaligned),
        "alignment_rate": 1.0 - (misaligned / total_sections) if total_sections > 0 else 1.0,
        "avg_health_score": df["article_health_score"].mean() if len(df) > 0 else 0.0,
        "avg_confidence": df["confidence"].mean() if len(df) > 0 else 0.0,
        "sections_with_no_cta_recommended": int(df["recommend_no_cta"].sum()),
        "funnel_distribution": df["funnel_stage"].value_counts().to_dict(),
        "intent_distribution": df["reader_intent"].value_counts().to_dict(),
        "persona_distribution": df["persona"].value_counts().to_dict(),
    }
