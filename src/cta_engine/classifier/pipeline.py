import asyncio
import json
import logging
from pathlib import Path

import anthropic

from cta_engine.classifier.client import get_client
from cta_engine.classifier.prompts import (
    CLASSIFICATION_SYSTEM_PROMPT,
    CLASSIFICATION_USER_TEMPLATE,
    CTA_MATCH_SYSTEM_PROMPT,
    CTA_MATCH_USER_TEMPLATE,
    CTA_SCORE_SYSTEM_PROMPT,
    CTA_SCORE_USER_TEMPLATE,
)
from cta_engine.classifier.schemas import CTAMatchResponse, CTAScoreResponse, SectionClassificationResponse
from cta_engine.config import settings
from cta_engine.models.schemas import (
    ArticleAnalysis,
    CTARecommendation,
    ExistingCTA,
    ExistingCTAScore,
    SectionAnalysis,
    SectionClassification,
)

logger = logging.getLogger(__name__)


def load_cta_library() -> list[dict]:
    with open(settings.cta_library_path) as f:
        return json.load(f)


def format_cta_library(ctas: list[dict]) -> str:
    lines = []
    for cta in ctas:
        lines.append(
            f"- ID: {cta['cta_id']} | {cta['headline']} | "
            f"Product: {cta['product']} | Funnel: {cta['funnel_stage']} | "
            f"Personas: {', '.join(cta['target_personas'])} | "
            f"Type: {cta['content_type']}"
        )
    return "\n".join(lines)


def classify_section(
    client, article_title: str, section: dict, existing_cta_text: str = "None"
) -> SectionClassificationResponse:
    user_msg = CLASSIFICATION_USER_TEMPLATE.format(
        article_title=article_title,
        section_heading=section["heading"],
        section_text=section["text"][:2000],
        existing_cta=existing_cta_text,
    )

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=CLASSIFICATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        tools=[
            {
                "name": "classify_section",
                "description": "Classify a blog section by intent, persona, funnel stage, and product alignment",
                "input_schema": SectionClassificationResponse.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "classify_section"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return SectionClassificationResponse.model_validate(block.input)

    raise ValueError("No tool_use block in classification response")


def match_ctas(
    client,
    classification: SectionClassificationResponse,
    section: dict,
    cta_library: list[dict],
) -> CTAMatchResponse:
    user_msg = CTA_MATCH_USER_TEMPLATE.format(
        reader_intent=classification.reader_intent.value,
        primary_persona=classification.primary_persona.value,
        funnel_stage=classification.funnel_stage.value,
        product_alignment=", ".join(classification.product_alignment),
        topic_tags=", ".join(classification.topic_tags),
        section_heading=section["heading"],
        section_text_preview=" ".join(section["text"].split()[:200]),
        cta_library_formatted=format_cta_library(cta_library),
    )

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=CTA_MATCH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        tools=[
            {
                "name": "match_ctas",
                "description": "Select and rank the best CTAs for this section",
                "input_schema": CTAMatchResponse.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "match_ctas"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return CTAMatchResponse.model_validate(block.input)

    raise ValueError("No tool_use block in CTA match response")


def score_existing_cta(
    client,
    classification: SectionClassificationResponse,
    section: dict,
    existing_cta: dict,
) -> CTAScoreResponse:
    """Score an existing CTA against a section's classification."""
    user_msg = CTA_SCORE_USER_TEMPLATE.format(
        section_heading=section["heading"],
        reader_intent=classification.reader_intent.value,
        primary_persona=classification.primary_persona.value,
        funnel_stage=classification.funnel_stage.value,
        product_alignment=", ".join(classification.product_alignment),
        section_text_preview=" ".join(section["text"].split()[:150]),
        cta_heading=existing_cta.get("heading", ""),
        cta_body=existing_cta.get("body", ""),
        cta_button_text=existing_cta.get("button_text", ""),
        cta_url=existing_cta.get("button_url", ""),
    )

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=512,
        system=CTA_SCORE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        tools=[
            {
                "name": "score_cta",
                "description": "Score an existing CTA's relevance to this section",
                "input_schema": CTAScoreResponse.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "score_cta"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return CTAScoreResponse.model_validate(block.input)

    raise ValueError("No tool_use block in CTA score response")


async def _analyze_section(
    haiku_client: anthropic.AsyncAnthropic,
    sonnet_client: anthropic.AsyncAnthropic,
    title: str,
    section: dict,
    existing_cta: dict | None,
    cta_library: list[dict],
) -> dict:
    """Analyze a single section: Haiku classifies, Sonnet matches + scores."""
    idx = section["index"]
    existing_cta_text = (
        f"{existing_cta.get('heading', '')} — {existing_cta.get('button_text', '')}"
        if existing_cta else "None"
    )

    # Step 1: Haiku classifies the section (cheap structured extraction)
    classify_msg = CLASSIFICATION_USER_TEMPLATE.format(
        article_title=title,
        section_heading=section["heading"],
        section_text=section["text"][:2000],
        existing_cta=existing_cta_text,
    )
    classify_coro = haiku_client.messages.create(
        model=settings.claude_haiku_model,
        max_tokens=1024,
        system=CLASSIFICATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": classify_msg}],
        tools=[{"name": "classify_section", "description": "Classify a blog section",
                "input_schema": SectionClassificationResponse.model_json_schema()}],
        tool_choice={"type": "tool", "name": "classify_section"},
    )

    classify_resp = await classify_coro
    classification = None
    for block in classify_resp.content:
        if block.type == "tool_use":
            classification = SectionClassificationResponse.model_validate(block.input)
            break
    if not classification:
        raise ValueError(f"No classification for section {idx}")

    # Now run match + score concurrently
    match_msg = CTA_MATCH_USER_TEMPLATE.format(
        reader_intent=classification.reader_intent.value,
        primary_persona=classification.primary_persona.value,
        funnel_stage=classification.funnel_stage.value,
        product_alignment=", ".join(classification.product_alignment),
        topic_tags=", ".join(classification.topic_tags),
        section_heading=section["heading"],
        section_text_preview=" ".join(section["text"].split()[:200]),
        cta_library_formatted=format_cta_library(cta_library),
    )
    # Step 2: Sonnet matches + scores (strategic reasoning)
    match_coro = sonnet_client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=CTA_MATCH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": match_msg}],
        tools=[{"name": "match_ctas", "description": "Select and rank the best CTAs",
                "input_schema": CTAMatchResponse.model_json_schema()}],
        tool_choice={"type": "tool", "name": "match_ctas"},
    )

    score_coro = None
    if existing_cta:
        score_msg = CTA_SCORE_USER_TEMPLATE.format(
            section_heading=section["heading"],
            reader_intent=classification.reader_intent.value,
            primary_persona=classification.primary_persona.value,
            funnel_stage=classification.funnel_stage.value,
            product_alignment=", ".join(classification.product_alignment),
            section_text_preview=" ".join(section["text"].split()[:150]),
            cta_heading=existing_cta.get("heading", ""),
            cta_body=existing_cta.get("body", ""),
            cta_button_text=existing_cta.get("button_text", ""),
            cta_url=existing_cta.get("button_url", ""),
        )
        score_coro = sonnet_client.messages.create(
            model=settings.claude_model,
            max_tokens=512,
            system=CTA_SCORE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": score_msg}],
            tools=[{"name": "score_cta", "description": "Score an existing CTA",
                    "input_schema": CTAScoreResponse.model_json_schema()}],
            tool_choice={"type": "tool", "name": "score_cta"},
        )

    if score_coro:
        match_resp, score_resp = await asyncio.gather(match_coro, score_coro)
    else:
        match_resp = await match_coro
        score_resp = None

    match_result = None
    for block in match_resp.content:
        if block.type == "tool_use":
            match_result = CTAMatchResponse.model_validate(block.input)
            break

    score_result = None
    if score_resp:
        for block in score_resp.content:
            if block.type == "tool_use":
                score_result = CTAScoreResponse.model_validate(block.input)
                break

    return {
        "section": section,
        "classification": classification,
        "match_result": match_result,
        "score_result": score_result,
        "existing_cta": existing_cta,
    }


def analyze_article(article_data: dict) -> ArticleAnalysis:
    """Run the full analysis pipeline on a single article."""
    return asyncio.run(_analyze_article_async(article_data))


async def _analyze_article_async(article_data: dict) -> ArticleAnalysis:
    """Async implementation — runs all sections concurrently."""
    async_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    haiku_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    cta_library = load_cta_library()

    title = article_data["title"]
    sections = article_data.get("sections", [])
    existing_ctas = article_data.get("existing_ctas", [])

    # Map section_index -> existing CTA dict
    cta_by_section: dict[int, dict] = {}
    for cta in existing_ctas:
        pos = cta.get("position_after_section", -1)
        cta_by_section[pos] = cta

    logger.info(f"  Analyzing {len(sections)} sections concurrently...")

    # Run all sections in parallel (rate limit: max 5 at a time)
    semaphore = asyncio.Semaphore(5)

    async def bounded(section):
        async with semaphore:
            return await _analyze_section(
                haiku_client, async_client, title, section,
                cta_by_section.get(section["index"]),
                cta_library,
            )

    results = await asyncio.gather(*[bounded(s) for s in sections])

    # Build section analyses in order
    section_analyses = []
    prev_recommended_cta = None

    for r in results:
        section = r["section"]
        idx = section["index"]
        classification = r["classification"]
        match_result = r["match_result"]
        score_result = r["score_result"]
        existing_cta = r["existing_cta"]

        recommendations = []
        if match_result:
            for ranking in match_result.rankings:
                if ranking.cta_id == prev_recommended_cta and len(match_result.rankings) > 1:
                    continue
                recommendations.append(CTARecommendation(
                    cta_id=ranking.cta_id,
                    score=ranking.score,
                    match_rationale=ranking.match_rationale,
                ))
        if recommendations:
            prev_recommended_cta = recommendations[0].cta_id

        existing_cta_obj = None
        existing_cta_score_obj = None
        if existing_cta:
            existing_cta_obj = ExistingCTA(
                heading=existing_cta.get("heading", ""),
                body=existing_cta.get("body", ""),
                button_text=existing_cta.get("button_text", ""),
                button_url=existing_cta.get("button_url", ""),
                position_after_section=idx,
            )
        if score_result:
            existing_cta_score_obj = ExistingCTAScore(
                relevance_score=score_result.relevance_score,
                funnel_alignment=score_result.funnel_alignment,
                persona_match=score_result.persona_match,
                product_alignment=score_result.product_alignment,
                issues=score_result.issues,
                rationale=score_result.rationale,
            )

        section_analyses.append(SectionAnalysis(
            section_index=idx,
            section_heading=section["heading"],
            classification=SectionClassification(
                reader_intent=classification.reader_intent,
                primary_persona=classification.primary_persona,
                secondary_persona=classification.secondary_persona,
                funnel_stage=classification.funnel_stage,
                product_alignment=classification.product_alignment,
                topic_tags=classification.topic_tags,
                confidence=classification.confidence,
                rationale=classification.rationale,
            ),
            existing_cta=existing_cta_obj,
            existing_cta_score=existing_cta_score_obj,
            recommendations=recommendations,
            recommend_no_cta=match_result.recommend_no_cta if match_result else False,
            no_cta_reason=match_result.no_cta_reason if match_result else "",
        ))

    # Calculate health score
    # Each section contributes a score 0.0–1.0:
    #   - Missing CTA (where one is recommended) → 0.0
    #   - Has CTA but none recommended → 0.0
    #   - Has CTA → use the relevance score (0.0–1.0)
    #   - No CTA and none recommended → 1.0 (intentionally clean)
    section_scores = []
    misaligned = 0
    for sa in section_analyses:
        if not sa.existing_cta and not sa.recommend_no_cta and sa.recommendations:
            section_scores.append(0.0)
            misaligned += 1
        elif sa.existing_cta and sa.recommend_no_cta:
            section_scores.append(0.0)
            misaligned += 1
        elif sa.existing_cta and sa.existing_cta_score:
            score = sa.existing_cta_score.relevance_score
            section_scores.append(score)
            if score < 0.5:
                misaligned += 1
        else:
            section_scores.append(1.0)  # No CTA, none needed

    total = len(section_scores)
    health_score = sum(section_scores) / total if total > 0 else 1.0

    analysis = ArticleAnalysis(
        url=article_data["url"],
        slug=article_data["slug"],
        title=title,
        section_analyses=section_analyses,
        overall_health_score=health_score,
        misaligned_count=misaligned,
    )

    # Save to classified dir
    settings.classified_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.classified_dir / f"{article_data['slug']}.json"
    with open(output_path, "w") as f:
        f.write(analysis.model_dump_json(indent=2))

    logger.info(
        f"  Analysis complete: health={health_score:.0%}, misaligned={misaligned}/{total}"
    )
    return analysis
