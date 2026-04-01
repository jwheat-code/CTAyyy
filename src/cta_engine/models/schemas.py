from enum import Enum

from pydantic import BaseModel


class ReaderIntent(str, Enum):
    LEARNING = "learning"
    EVALUATING = "evaluating"
    PROBLEM_SOLVING = "problem_solving"
    INSPIRING = "inspiring"
    IMPLEMENTING = "implementing"


class Persona(str, Enum):
    IT_LEADER = "it_leader"
    BUSINESS_LEADER = "business_leader"
    SALES_LEADER = "sales_leader"
    MARKETING_LEADER = "marketing_leader"
    SERVICE_LEADER = "service_leader"
    DEVELOPER = "developer"
    ADMIN = "admin"
    GENERAL = "general"


class FunnelStage(str, Enum):
    AWARENESS = "awareness"
    CONSIDERATION = "consideration"
    DECISION = "decision"


class ExistingCTA(BaseModel):
    heading: str = ""
    body: str = ""
    button_text: str = ""
    button_url: str = ""
    position_after_section: int = -1


class Section(BaseModel):
    index: int
    heading: str
    text: str
    word_count: int
    has_existing_cta: bool = False
    inline_links: list[dict] = []


class Article(BaseModel):
    url: str
    slug: str
    title: str
    author: str = ""
    published_date: str = ""
    category: str = ""
    sections: list[Section] = []
    existing_ctas: list[ExistingCTA] = []


class SectionClassification(BaseModel):
    reader_intent: ReaderIntent
    primary_persona: Persona
    secondary_persona: Persona | None = None
    funnel_stage: FunnelStage
    product_alignment: list[str]
    topic_tags: list[str]
    confidence: float
    rationale: str


class CTACandidate(BaseModel):
    cta_id: str
    headline: str
    body: str
    button_text: str
    destination_url: str
    product: str
    funnel_stage: FunnelStage
    target_personas: list[str]
    content_type: str
    tags: list[str] = []


class CTARecommendation(BaseModel):
    cta_id: str
    score: float
    match_rationale: str


class ExistingCTAScore(BaseModel):
    relevance_score: float = 0.0
    funnel_alignment: str = ""
    persona_match: str = ""
    product_alignment: str = ""
    issues: list[str] = []
    rationale: str = ""


class SectionAnalysis(BaseModel):
    section_index: int
    section_heading: str
    classification: SectionClassification
    existing_cta: ExistingCTA | None = None
    existing_cta_score: ExistingCTAScore | None = None
    recommendations: list[CTARecommendation]
    recommend_no_cta: bool = False
    no_cta_reason: str = ""


class ArticleAnalysis(BaseModel):
    url: str
    slug: str
    title: str
    section_analyses: list[SectionAnalysis]
    overall_health_score: float = 0.0
    misaligned_count: int = 0
