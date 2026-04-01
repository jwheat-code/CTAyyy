from pydantic import BaseModel, Field

from cta_engine.models.schemas import FunnelStage, Persona, ReaderIntent


class CTAScoreResponse(BaseModel):
    """Structured output for scoring an existing CTA against a section's classification."""

    relevance_score: float = Field(
        ge=0.0, le=1.0,
        description="Overall relevance score from 0.0 (completely wrong) to 1.0 (perfect fit)"
    )
    funnel_alignment: str = Field(
        description="'match' | 'adjacent' | 'mismatch' — does the CTA's funnel stage fit?"
    )
    persona_match: str = Field(
        description="'match' | 'partial' | 'mismatch' — does the CTA speak to the right persona?"
    )
    product_alignment: str = Field(
        description="'match' | 'partial' | 'mismatch' | 'none' — does the CTA's product fit the section topic?"
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Specific problems with this CTA for this section (empty if score >= 0.7)"
    )
    rationale: str = Field(
        description="One sentence explaining the score"
    )


class SectionClassificationResponse(BaseModel):
    """Structured output schema for Claude section classification."""

    reader_intent: ReaderIntent = Field(
        description="The primary intent of a reader consuming this section"
    )
    primary_persona: Persona = Field(
        description="The most likely persona reading this content"
    )
    secondary_persona: Persona | None = Field(
        default=None,
        description="A secondary persona, if applicable",
    )
    funnel_stage: FunnelStage = Field(
        description="Where this content falls in the marketing funnel"
    )
    product_alignment: list[str] = Field(
        description="Salesforce products most relevant to this section (e.g., 'agentforce', 'sales_cloud', 'data_cloud')"
    )
    topic_tags: list[str] = Field(
        description="3-5 topic tags for this section (e.g., 'disaster_relief', 'ai_agents', 'crm')"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Classification confidence from 0.0 to 1.0"
    )
    rationale: str = Field(
        description="Brief explanation of why this classification was chosen"
    )


class CTAMatchResponse(BaseModel):
    """Structured output schema for Claude CTA matching."""

    class CTARanking(BaseModel):
        cta_id: str = Field(description="The ID of the recommended CTA from the library")
        score: float = Field(
            ge=0.0, le=1.0, description="Relevance score from 0.0 to 1.0"
        )
        match_rationale: str = Field(
            description="Why this CTA is a good fit for this section"
        )

    recommend_no_cta: bool = Field(
        description="True if no CTA is appropriate for this section"
    )
    no_cta_reason: str = Field(
        default="",
        description="If recommend_no_cta is true, explain why",
    )
    rankings: list[CTARanking] = Field(
        default_factory=list,
        description="Top 3 CTA candidates ranked by relevance (empty if recommend_no_cta is true)",
    )
