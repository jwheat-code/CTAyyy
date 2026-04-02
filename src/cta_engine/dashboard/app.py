import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Resolve paths — walk up from this file until we find the data/ directory
def _find_project_root() -> Path:
    candidate = Path(__file__).resolve()
    for _ in range(6):
        candidate = candidate.parent
        if (candidate / "data" / "cta_library.json").exists():
            return candidate
    # Last resort: repo root is wherever this file lives up to 4 levels
    return Path(__file__).resolve().parent.parent.parent.parent

PROJECT_ROOT = _find_project_root()
DATA_DIR = PROJECT_ROOT / "data"
CRAWLED_DIR = DATA_DIR / "crawled"
CLASSIFIED_DIR = DATA_DIR / "classified"
CTA_LIBRARY_PATH = DATA_DIR / "cta_library.json"


def load_cta_library() -> dict:
    """Load CTA library as a dict keyed by cta_id."""
    if not CTA_LIBRARY_PATH.exists():
        return {}
    with open(CTA_LIBRARY_PATH) as f:
        ctas = json.load(f)
    return {c["cta_id"]: c for c in ctas}


def load_crawled_articles() -> dict[str, dict]:
    """Load all crawled articles keyed by slug."""
    articles = {}
    if not CRAWLED_DIR.exists():
        return articles
    for path in sorted(CRAWLED_DIR.glob("*.json")):
        with open(path) as f:
            data = json.load(f)
        articles[data.get("slug", path.stem)] = data
    return articles


def load_analyses() -> dict[str, dict]:
    """Load all analyses keyed by slug."""
    analyses = {}
    if not CLASSIFIED_DIR.exists():
        return analyses
    for path in sorted(CLASSIFIED_DIR.glob("*.json")):
        with open(path) as f:
            data = json.load(f)
        analyses[data.get("slug", path.stem)] = data
    return analyses


def build_health_df(analyses: dict, articles: dict) -> pd.DataFrame:
    """Build a summary DataFrame across all analyses."""
    rows = []
    for slug, analysis in analyses.items():
        article = articles.get(slug, {})
        section_analyses = analysis.get("section_analyses", [])
        misaligned = analysis.get("misaligned_count", 0)
        total = len(section_analyses)

        rows.append({
            "Article": analysis.get("title", slug),
            "Author": analysis.get("author", article.get("author", "")),
            "Published": (analysis.get("published_date", article.get("published_date", "")) or "")[:10],
            "URL": analysis.get("url", ""),
            "Slug": slug,
            "Sections": total,
            "Misaligned": misaligned,
            "Aligned": total - misaligned,
            "Health Score": analysis.get("overall_health_score", 0),
            "Has Analysis": True,
        })

    # Add articles without analysis
    for slug, article in articles.items():
        if slug not in analyses:
            rows.append({
                "Article": article.get("title", slug),
                "Author": article.get("author", ""),
                "Published": (article.get("published_date", "") or "")[:10],
                "URL": article.get("url", ""),
                "Slug": slug,
                "Sections": len(article.get("sections", [])),
                "Misaligned": 0,
                "Aligned": 0,
                "Health Score": None,
                "Has Analysis": False,
            })

    return pd.DataFrame(rows)


# --- Page Config ---
st.set_page_config(page_title="CTA Engine", page_icon="🎯", layout="wide")
st.title("CTA Engine — Health Report")

# Load data
cta_library = load_cta_library()
articles = load_crawled_articles()
analyses = load_analyses()


if not articles:
    st.warning("No crawled articles found. Run the crawler first: `python scripts/crawl.py`")
    st.stop()

# --- Sidebar ---
st.sidebar.header("Controls")

# Article selector
article_slugs = sorted(articles.keys())
analyzed_slugs = sorted(analyses.keys())

filter_mode = st.sidebar.radio("Show", ["All Articles", "Analyzed Only", "Not Analyzed"])
if filter_mode == "Analyzed Only":
    display_slugs = [s for s in article_slugs if s in analyses]
elif filter_mode == "Not Analyzed":
    display_slugs = [s for s in article_slugs if s not in analyses]
else:
    display_slugs = article_slugs

selected_slug = st.sidebar.selectbox(
    "Select Article",
    display_slugs,
    format_func=lambda s: articles[s].get("title", s)[:60],
)

st.sidebar.markdown("---")
st.sidebar.metric("Total Articles Crawled", len(articles))
st.sidebar.metric("Articles Analyzed", len(analyses))
if analyses:
    avg_health = sum(a.get("overall_health_score", 0) for a in analyses.values()) / len(analyses)
    st.sidebar.metric("Avg Health Score", f"{avg_health:.0%}")

# Export button
if analyses:
    health_df = build_health_df(analyses, articles)
    csv = health_df.to_csv(index=False)
    st.sidebar.download_button("Export Summary CSV", csv, "cta_health_summary.csv", "text/csv")

# Crawl & Analyze button (local only)
st.sidebar.markdown("---")
st.sidebar.markdown("**Refresh Content**")
unanalyzed = [s for s in articles if s not in analyses]
if unanalyzed:
    st.sidebar.caption(f"{len(unanalyzed)} crawled article(s) not yet analyzed")
if st.sidebar.button("Crawl & Analyze New (2026)", type="primary"):
    scripts_dir = PROJECT_ROOT / "scripts"
    sitemap_cmd = [sys.executable, str(scripts_dir / "fetch_sitemap_urls.py")]
    crawl_cmd = [sys.executable, str(scripts_dir / "crawl_from_sitemap.py"), "--limit", "100"]
    classify_cmd = [sys.executable, str(scripts_dir / "classify_rules.py"), "--all"]
    log = st.sidebar.empty()
    try:
        log.info("Finding new 2026 articles from sitemap...")
        result = subprocess.run(sitemap_cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        log.info("Crawling new articles...")
        result = subprocess.run(crawl_cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        if result.returncode != 0:
            st.sidebar.error(f"Crawl failed: {result.stderr[-500:]}")
        else:
            log.info("Classifying new articles...")
            result = subprocess.run(classify_cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
            if result.returncode != 0:
                st.sidebar.error(f"Classification failed: {result.stderr[-500:]}")
            else:
                log.success("Done! Reloading...")
                st.rerun()
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

# --- Main Content ---
tab1, tab2, tab3 = st.tabs(["Article Overview", "Section Analysis", "Batch Summary"])

# === Tab 1: Article Overview ===
with tab1:
    if selected_slug:
        article = articles[selected_slug]
        analysis = analyses.get(selected_slug)

        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader(article.get("title", ""))
            st.markdown(f"[View on Salesforce Blog]({article.get('url', '')})")
            st.caption(
                f"Author: {article.get('author', 'Unknown')} | "
                f"Category: {article.get('category', 'Unknown')} | "
                f"Published: {article.get('published_date', 'Unknown')[:10]}"
            )

        with col2:
            if analysis:
                st.metric("Health Score", f"{analysis['overall_health_score']:.0%}")
                st.metric("Misaligned CTAs", analysis["misaligned_count"])
            else:
                st.info("Not yet analyzed")

        st.markdown("### Sections")
        sections = article.get("sections", [])
        existing_ctas = article.get("existing_ctas", [])
        cta_positions = {c.get("position_after_section", -1) for c in existing_ctas}

        for section in sections:
            idx = section["index"]
            has_cta = idx in cta_positions
            icon = "✅" if has_cta else "—"
            with st.expander(f"{icon} Section {idx}: {section['heading'][:80]}", expanded=False):
                st.write(section["text"][:500] + ("..." if len(section["text"]) > 500 else ""))
                st.caption(f"Words: {section['word_count']}")
                if has_cta:
                    cta = next(c for c in existing_ctas if c.get("position_after_section") == idx)
                    st.info(
                        f"**Existing CTA:** {cta.get('heading', '')} — "
                        f"[{cta.get('button_text', '')}]({cta.get('button_url', '')})"
                    )

# === Tab 2: Section-by-Section Analysis ===
with tab2:
    if selected_slug and selected_slug in analyses:
        analysis = analyses[selected_slug]
        article = articles[selected_slug]

        st.subheader(f"Analysis: {analysis.get('title', '')}")

        for sa in analysis.get("section_analyses", []):
            section_data = None
            for s in article.get("sections", []):
                if s["index"] == sa["section_index"]:
                    section_data = s
                    break

            st.markdown(f"### Section {sa['section_index']}: {sa['section_heading']}")

            # Classification badges
            cls = sa["classification"]
            badge_cols = st.columns(5)
            badge_cols[0].markdown(f"**Intent:** `{cls['reader_intent']}`")
            badge_cols[1].markdown(f"**Persona:** `{cls['primary_persona']}`")
            badge_cols[2].markdown(f"**Funnel:** `{cls['funnel_stage']}`")
            badge_cols[3].markdown(f"**Products:** `{', '.join(cls['product_alignment'])}`")
            badge_cols[4].markdown(f"**Confidence:** `{cls['confidence']:.0%}`")

            # Before / After columns
            col_before, col_after = st.columns(2)

            with col_before:
                st.markdown("#### Current CTA")
                existing = sa.get("existing_cta")
                score_data = sa.get("existing_cta_score")
                if existing and existing.get("button_text"):
                    relevance = score_data["relevance_score"] if score_data else None
                    if relevance is not None:
                        if relevance >= 0.7:
                            color = "green"
                            label = f"✅ Relevance: {relevance:.0%}"
                        elif relevance >= 0.5:
                            color = "orange"
                            label = f"⚠️ Relevance: {relevance:.0%}"
                        else:
                            color = "red"
                            label = f"❌ Relevance: {relevance:.0%}"
                        st.markdown(f"**:{color}[{label}]**")
                    body_preview = (existing.get("body") or "")[:120]
                    st.warning(
                        f"**{existing.get('heading', '')}**\n\n"
                        f"{body_preview}\n\n"
                        f"→ [{existing.get('button_text', '')}]({existing.get('button_url', '')})"
                    )
                    if score_data and score_data.get("rationale"):
                        st.caption(f"📋 {score_data['rationale']}")
                    if score_data and score_data.get("issues"):
                        for issue in score_data["issues"]:
                            st.caption(f"• {issue}")
                else:
                    st.info("No CTA currently placed here")

            with col_after:
                st.markdown("#### Recommended CTA")
                if sa.get("recommend_no_cta"):
                    st.success(f"**No CTA recommended**\n\n{sa.get('no_cta_reason', '')}")
                elif sa.get("recommendations"):
                    top = sa["recommendations"][0]
                    cta_detail = cta_library.get(top["cta_id"], {})
                    st.success(
                        f"**{cta_detail.get('headline', top['cta_id'])}**\n\n"
                        f"{cta_detail.get('body', '')}\n\n"
                        f"→ [{cta_detail.get('button_text', '')}]({cta_detail.get('destination_url', '')})\n\n"
                        f"Match score: {top['score']:.0%}"
                    )
                else:
                    st.info("No recommendation available")

            # Expandable rationale
            with st.expander("View Details", expanded=False):
                st.markdown(f"**Classification Rationale:** {cls['rationale']}")
                st.markdown(f"**Topics:** {', '.join(cls.get('topic_tags', []))}")

                if sa.get("recommendations"):
                    st.markdown("**All Candidates:**")
                    for i, rec in enumerate(sa["recommendations"]):
                        cta_d = cta_library.get(rec["cta_id"], {})
                        st.markdown(
                            f"{i+1}. **{cta_d.get('headline', rec['cta_id'])}** "
                            f"(Score: {rec['score']:.0%}) — {rec['match_rationale']}"
                        )

            st.divider()

    elif selected_slug:
        st.info(f"No analysis for **{articles[selected_slug].get('title', selected_slug)}** yet.")

# === Tab 3: Batch Summary ===
with tab3:
    if analyses:
        health_df = build_health_df(analyses, articles)
        analyzed_df = health_df[health_df["Has Analysis"]].copy()

        # Top-line metrics
        total_sections = int(analyzed_df["Sections"].sum())
        total_misaligned = int(analyzed_df["Misaligned"].sum())
        avg = analyzed_df["Health Score"].mean() if len(analyzed_df) > 0 else 0
        pct_healthy = (analyzed_df["Health Score"] >= 0.7).sum()

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Articles", len(analyzed_df))
        m2.metric("Sections", total_sections)
        m3.metric("CTA Issues", total_misaligned)
        m4.metric("Healthy Articles", f"{pct_healthy}/{len(analyzed_df)}")
        m5.metric("Avg Health Score", f"{avg:.0%}")

        st.markdown("---")

        # Opportunity breakdown
        opp_col, dist_col = st.columns(2)

        with opp_col:
            st.markdown("#### CTA Opportunity Breakdown")
            missing_cta = 0
            wrong_cta = 0
            good_cta = 0
            no_cta_needed = 0
            for slug, analysis in analyses.items():
                for sa in analysis.get("section_analyses", []):
                    has_cta = sa.get("existing_cta") is not None
                    no_cta_rec = sa.get("recommend_no_cta", False)
                    score_data = sa.get("existing_cta_score")
                    recs = sa.get("recommendations", [])
                    if not has_cta and not no_cta_rec and recs:
                        missing_cta += 1
                    elif has_cta and no_cta_rec:
                        wrong_cta += 1
                    elif has_cta and score_data:
                        s = score_data["relevance_score"]
                        if s < 0.5:
                            wrong_cta += 1
                        else:
                            good_cta += 1
                    else:
                        no_cta_needed += 1
            opp_df = pd.DataFrame([
                {"Status": "✅ Good CTA", "Sections": good_cta},
                {"Status": "❌ Missing CTA", "Sections": missing_cta},
                {"Status": "⚠️ Wrong CTA", "Sections": wrong_cta},
                {"Status": "— No CTA Needed", "Sections": no_cta_needed},
            ])
            st.dataframe(opp_df, use_container_width=True, hide_index=True)

        with dist_col:
            st.markdown("#### Funnel Stage Distribution")
            funnel_counts = {"awareness": 0, "consideration": 0, "decision": 0}
            for slug, analysis in analyses.items():
                for sa in analysis.get("section_analyses", []):
                    f = sa.get("classification", {}).get("funnel_stage", "")
                    if f in funnel_counts:
                        funnel_counts[f] += 1
            funnel_df = pd.DataFrame([
                {"Funnel Stage": k.title(), "Sections": v}
                for k, v in funnel_counts.items()
            ])
            st.dataframe(funnel_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Article Health Scores")

        # Table
        display_df = (
            analyzed_df[["Article", "Author", "Published", "Sections", "Misaligned", "Aligned", "Health Score"]]
            .sort_values("Health Score", ascending=True)
            .copy()
        )
        display_df["Health Score"] = display_df["Health Score"].map(lambda x: f"{x:.0%}")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Detailed export
        detail_rows = []
        for slug, analysis in analyses.items():
            for sa in analysis.get("section_analyses", []):
                cls = sa["classification"]
                top = sa["recommendations"][0] if sa.get("recommendations") else None
                detail_rows.append({
                    "Article": analysis.get("title", slug),
                    "Section": sa["section_heading"],
                    "Intent": cls["reader_intent"],
                    "Persona": cls["primary_persona"],
                    "Funnel": cls["funnel_stage"],
                    "Confidence": cls["confidence"],
                    "Current CTA": sa.get("existing_cta", {}).get("heading", "") if sa.get("existing_cta") else "",
                    "Recommended CTA": cta_library.get(top["cta_id"], {}).get("headline", top["cta_id"]) if top else "None",
                    "Score": top["score"] if top else 0,
                    "Rationale": top["match_rationale"] if top else sa.get("no_cta_reason", ""),
                })

        detail_df = pd.DataFrame(detail_rows)
        csv = detail_df.to_csv(index=False)
        st.download_button(
            "Export Detailed Report CSV",
            csv,
            "cta_detailed_report.csv",
            "text/csv",
        )
    else:
        st.info("No analyses available yet. Analyze some articles first.")
