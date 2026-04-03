import streamlit as st

st.set_page_config(page_title="CTA Engine — Methodology", page_icon="📖", layout="wide")

st.markdown("## CTA Health Scoring Methodology")
st.markdown("""
This engine scores each blog article's CTA effectiveness on a **100-point scale** across four evidence-based dimensions.
The model is calibrated using data from HubSpot's 330,000+ CTA analysis, Chartbeat scroll-depth research,
and Nielsen Norman Group's banner-blindness studies.

### Why not "every section needs a CTA"?

Research consistently shows that **2-4 well-placed CTAs outperform CTA saturation**.
HubSpot's own data found that personalized CTAs convert 202% better than generic ones —
but that says nothing about frequency. Placing a generic CTA in every section creates
banner blindness and reduces engagement by 15-20% on repeat visits.

---

### Scoring Dimensions

#### 1. Quantity & Density (25 points)
**What it measures:** Does the article have the right number of CTAs for its length?

| Article Length | Ideal CTAs | Max Score |
|---|---|---|
| < 1,000 words | 1-2 | 25 |
| 1,000-1,500 words | 2 | 25 |
| 1,500-3,000 words | 3 | 25 |

Soft CTAs (newsletter, related content, reports) count as 0.5.
Zero CTAs on a 1,000+ word article scores 0.
More than 5 CTAs scores 3-5 points.

#### 2. Placement Quality (35 points)
**What it measures:** Are CTAs positioned where readers are most engaged?

Based on Chartbeat scroll-depth data showing 70% of conversions occur past 50% depth:

- **Early zone** (first 20% of article): +10 points — captures skimmers
- **Mid zone** (35-65% of article): +15 points — highest-leverage position
- **End zone** (final 15% of article): +10 points — highest-intent readers
- **Contextual bonus**: +5 if mid CTA matches section topic

Articles with CTAs only at the top score poorly.
Articles with a strong mid + end CTA pattern score highest.

#### 3. Intent & Relevance Match (30 points)
**What it measures:** Do the CTAs match what the reader is trying to do?

- **Thought leadership** (learning/inspiring intent): Soft CTAs preferred.
  Hard commercial CTAs at the top of editorial content = -8 penalty.
- **Evaluation content** (comparing/problem-solving): Product CTAs expected.
  Generic newsletter as only CTA = -4 penalty.
- **Decision content** (ready to buy): Strong commercial CTAs needed.
  Fewer than 2 commercial CTAs = -6 penalty.

Funnel mismatches (e.g., a "free trial" CTA on an awareness article) are penalized.

#### 4. UX & Intrusiveness (10 points)
**What it measures:** Do CTAs respect the reading experience?

Starts at 10, subtracts for:
- Multiple CTAs crowding the top of the article: -3
- Same CTA repeated 3+ times (banner blindness): -3
- Promotional blocks pushing down content: -4

#### Penalties
- **Section saturation** (>50% of sections have CTAs): -5 to -10
- **Duplicate fatigue** (3+ identical CTA blocks): -4

---

### Grades

| Score | Grade | Meaning |
|---|---|---|
| 85-100 | **Excellent** | CTAs are well-placed, relevant, and respectful of the reading experience |
| 70-84 | **Solid** | Good foundation — may benefit from better placement or copy |
| 55-69 | **Needs Work** | Under- or over-instrumented — see issues for specific fixes |
| Below 55 | **Poor** | Missing CTAs entirely, or CTA spam that hurts engagement |

---

### What "No CTA Needed" means

Not every section needs a CTA. The engine marks sections as "No CTA Needed" when:

- **Introduction / first section** — the reader just arrived; let them engage first
- **Short narrative sections** (< 150 words) — not enough context for a meaningful CTA
- **Mid-article learning/story sections** — interrupting the narrative hurts engagement
- **Sections without evaluation or decision intent** — the reader isn't ready to act

CTAs are recommended for:
- **The final section** — readers who finish are your highest-intent audience
- **Mid-article sections with evaluation/decision intent** — the reader is actively comparing or deciding
- **After major proof/value sections** — the reader has received enough value to act

---

### Hard vs Soft CTAs

| Type | Examples | When to use |
|---|---|---|
| **Hard** (commercial) | Demo, Free Trial, Contact Sales, Pricing, Get Started | Evaluation and decision content |
| **Soft** (nurture) | Newsletter, Related Article, Report, Webinar, Trailhead Trail | Thought leadership and learning content |

Soft CTAs count as 0.5 for quantity scoring — they're less intrusive and appropriate at higher frequency.

---

### Sources

- [HubSpot: Personalized CTAs convert 202% better (330K+ CTA analysis)](https://blog.hubspot.com/marketing/personalized-calls-to-action-convert-better-data)
- [ContentSquare: 8 CTA Best Practices to Increase Conversions](https://contentsquare.com/blog/cta-best-practices/)
- [Nielsen Norman Group: Banner Blindness Revisited](https://www.nngroup.com/articles/banner-blindness-old-and-new-findings/)
- [Stratabeat: The Ultimate Guide to B2B Blogging](https://stratabeat.com/b2b-blogging/)
- [BlissDrive: Ideal Number of CTAs in a Long-Form Blog Post](https://www.blissdrive.com/people-also-asked/whats-the-ideal-number-of-ctas-in-a-long-form-blog-post/)
- [WSI: Blog Conversion Optimization Tips](https://wsi.leapdigital.ca/optimize-your-blog-for-conversions-cro-tactics-for-content-that-performs/)
- [Semrush: Crawlability & Indexability](https://www.semrush.com/blog/what-are-crawlability-and-indexability-of-a-website/)
""")

st.markdown("---")
st.caption("CTA Health Engine v2.0 — Scoring model updated April 2026")
