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
TRAIL_LIBRARY_PATH = DATA_DIR / "trail_library.json"
COMPETITORS_DIR = DATA_DIR / "competitors"

BRAND_CONFIG = {
    "Salesforce": {"color": "#00A1E0", "icon": "☁️"},
    "HubSpot": {"color": "#FF7A59", "icon": "🟠"},
    "Shopify": {"color": "#96BF48", "icon": "🟢"},
    "ServiceNow": {"color": "#81B5A1", "icon": "🔧"},
}


def load_competitor_summary(name: str) -> dict | None:
    """Load a competitor audit JSON by name (e.g. 'hubspot')."""
    path = COMPETITORS_DIR / f"{name.lower()}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def build_competitor_health_df(data: dict) -> pd.DataFrame:
    """Build a summary DataFrame from competitor audit data."""
    rows = []
    for row in data.get("article_rows", []):
        rows.append({
            "Article": row.get("title", ""),
            "Author": row.get("author", ""),
            "Published": row.get("published", row.get("date", "")),
            "Sections": row.get("sections", 0),
            "Misaligned": row.get("misaligned", 0),
            "Aligned": row.get("sections", 0) - row.get("misaligned", 0),
            "Health Score": row.get("health", 0),
            "Has Analysis": True,
        })
    return pd.DataFrame(rows)


def load_cta_library() -> dict:
    """Load CTA library as a dict keyed by cta_id."""
    if not CTA_LIBRARY_PATH.exists():
        return {}
    with open(CTA_LIBRARY_PATH) as f:
        ctas = json.load(f)
    return {c["cta_id"]: c for c in ctas}


def load_trail_library() -> dict:
    """Load trail library as a dict keyed by trail_id."""
    if not TRAIL_LIBRARY_PATH.exists():
        return {}
    with open(TRAIL_LIBRARY_PATH) as f:
        trails = json.load(f)
    return {t["trail_id"]: t for t in trails}


def render_recommendation(rec: dict, cta_library: dict, trail_library: dict) -> str:
    """Render a single recommendation (CTA or trail) as markdown."""
    rec_type = rec.get("type", "cta")
    score = rec.get("score", 0)

    if rec_type == "trail":
        trail = trail_library.get(rec.get("trail_id", ""), {})
        name = trail.get("name") or rec.get("name", rec.get("trail_id", "Unknown trail"))
        url = trail.get("url") or rec.get("url", "")
        mins = trail.get("duration_minutes") or rec.get("duration_minutes")
        dur = f" · {mins} min" if mins else ""
        return (
            f"🎓 **Trail** — [{name}]({url}){dur}\n\n"
            f"Match score: {score:.0%}"
        )
    else:
        cta = cta_library.get(rec.get("cta_id", ""), {})
        headline = cta.get("headline") or rec.get("cta_id", "Unknown CTA")
        body = cta.get("body", "")
        btn = cta.get("button_text", "")
        dest = cta.get("destination_url", "")
        link = f"→ [{btn}]({dest})\n\n" if btn and dest else ""
        return (
            f"📣 **CTA** — **{headline}**\n\n"
            f"{body}\n\n"
            f"{link}"
            f"Match score: {score:.0%}"
        )


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

# --- Brand Selector (prominent, top of page) ---
available_brands = ["Salesforce"]
for name in ["HubSpot", "Shopify", "ServiceNow"]:
    if (COMPETITORS_DIR / f"{name.lower()}.json").exists():
        available_brands.append(name)

selected_brand = st.session_state.get("selected_brand", "Salesforce")

brand_cols = st.columns(len(available_brands) + 1)
for i, brand in enumerate(available_brands):
    cfg = BRAND_CONFIG.get(brand, {})
    is_active = brand == selected_brand
    with brand_cols[i]:
        if is_active:
            st.markdown(
                f"<div style='background:{cfg.get('color','#00A1E0')};color:white;padding:10px 16px;"
                f"border-radius:8px;text-align:center;font-weight:700;font-size:15px;cursor:default;'>"
                f"{cfg.get('icon','')} {brand}</div>",
                unsafe_allow_html=True,
            )
        else:
            if st.button(f"{cfg.get('icon', '')} {brand}", key=f"brand_{brand}", use_container_width=True):
                st.session_state["selected_brand"] = brand
                st.rerun()

with brand_cols[-1]:
    selected_year = st.selectbox("", ["Year: 2026", "Year: 2025", "Year: All"], index=0, key="year_filter", label_visibility="collapsed")
    selected_year = selected_year.replace("Year: ", "")

st.title("CTA Engine — Health Report")

is_competitor = selected_brand != "Salesforce"

# --- Load data based on brand ---
if is_competitor:
    competitor_data = load_competitor_summary(selected_brand)
    if not competitor_data:
        st.error(f"No data found for {selected_brand}")
        st.stop()
    # Filter competitor articles by year
    if selected_year != "All" and competitor_data.get("article_rows"):
        competitor_data["article_rows"] = [
            r for r in competitor_data["article_rows"]
            if (r.get("published") or r.get("date", "")).startswith(selected_year)
        ]
        # Recompute totals from filtered rows
        competitor_data["total_articles"] = len(competitor_data["article_rows"])
        competitor_data["total_sections"] = sum(r.get("sections", 0) for r in competitor_data["article_rows"])
        competitor_data["total_cta_issues"] = sum(r.get("misaligned", 0) for r in competitor_data["article_rows"])
        competitor_data["healthy_articles"] = sum(1 for r in competitor_data["article_rows"] if r.get("health", 0) >= 0.7)
    # Warn if no data for selected year
    if competitor_data["total_articles"] == 0 and selected_year != "All":
        st.error(f"No {selected_year} data exists for {selected_brand} at this time. Competitor audits currently cover 2026 only.")
        st.stop()
    cta_library = {}
    trail_library = {}
    articles = {}
    analyses = {}
else:
    competitor_data = None
    cta_library = load_cta_library()
    trail_library = load_trail_library()
    articles = load_crawled_articles()
    analyses = load_analyses()

    # Filter Salesforce data by year
    if selected_year != "All":
        articles = {
            slug: a for slug, a in articles.items()
            if (a.get("published_date") or "")[:4] == selected_year
        }
        analyses = {
            slug: a for slug, a in analyses.items()
            if slug in articles
        }

    if not articles:
        st.warning(f"No articles found for {selected_year}. Try a different year.")
        st.stop()

# --- Sidebar ---
st.sidebar.header("Controls")

if is_competitor:
    # Competitor mode — simplified sidebar
    cd = competitor_data
    total_articles = cd.get("total_articles", len(cd.get("article_rows", [])))
    avg = sum(r.get("health", 0) for r in cd.get("article_rows", [])) / total_articles if total_articles else 0
    st.sidebar.metric("Total Articles", total_articles)
    st.sidebar.metric("Avg CTA Health", f"{int(avg * 100)}/100", help="See Methodology tab")

# Article selector (Salesforce only)
article_slugs = sorted(articles.keys())
analyzed_slugs = sorted(analyses.keys())

selected_slug = None
if not is_competitor and article_slugs:
    # Sort by published date descending (newest first)
    sorted_slugs = sorted(
        article_slugs,
        key=lambda s: articles[s].get("published_date", "") or "",
        reverse=True,
    )
    selected_slug = st.sidebar.selectbox(
        "Select Article",
        sorted_slugs,
        format_func=lambda s: f"{(articles[s].get('published_date','') or '')[:10]}  {articles[s].get('title', s)[:50]}",
    )

if not is_competitor:
    st.sidebar.markdown("---")
    st.sidebar.metric("Total Articles Crawled", len(articles))
    st.sidebar.metric("Articles Analyzed", len(analyses))
if not is_competitor and analyses:
    avg_health = sum(a.get("overall_health_score", 0) for a in analyses.values()) / len(analyses)
    st.sidebar.metric("Avg CTA Health", f"{int(avg_health * 100)}/100", help="See Methodology tab")

# Export button
if analyses:
    health_df = build_health_df(analyses, articles)
    csv = health_df.to_csv(index=False)
    st.sidebar.download_button("Export Summary CSV", csv, "cta_health_summary.csv", "text/csv")

# Crawl & Analyze button (password-protected)
st.sidebar.markdown("---")
st.sidebar.markdown("**Refresh Content**")
unanalyzed = [s for s in articles if s not in analyses]
if unanalyzed:
    st.sidebar.caption(f"{len(unanalyzed)} crawled article(s) not yet analyzed")
crawl_pw = st.sidebar.text_input("Admin password", type="password", key="crawl_pw")
crawl_clicked = st.sidebar.button("Crawl & Analyze New (2026)", type="primary")
if crawl_clicked and crawl_pw != "cta2026!":
    st.sidebar.error("Wrong password.")
    crawl_clicked = False
if crawl_clicked:
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
tab1, tab2, tab3, tab4 = st.tabs(["Article Overview", "Section Analysis", "Scorecard", "Methodology"])

# === Tab 1: Article Overview ===
with tab1:
    if is_competitor:
        cfg = BRAND_CONFIG.get(selected_brand, {})
        st.info(f"Article-level analysis is only available for Salesforce. Switch to **Scorecard** to see {cfg.get('icon', '')} {selected_brand} data.")
    elif selected_slug:
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
                score = analysis.get("cta_health_score", int(analysis["overall_health_score"] * 100))
                grade = analysis.get("cta_health_grade", "")
                grade_colors = {"excellent": "green", "solid": "blue", "needs_work": "orange", "poor": "red"}
                grade_labels = {"excellent": "Excellent", "solid": "Solid", "needs_work": "Needs Work", "poor": "Poor"}
                st.metric("CTA Health", f"{score}/100", help="Article-level CTA health based on quantity, placement, intent match, and UX. See Methodology tab.")
                if grade:
                    color = grade_colors.get(grade, "gray")
                    st.markdown(f"**:{color}[{grade_labels.get(grade, grade)}]**")
                # Show issues if present
                issues = analysis.get("cta_health_issues", [])
                if issues:
                    with st.expander(f"{len(issues)} issue(s) found"):
                        for issue in issues:
                            st.caption(f"• {issue}")
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
    if is_competitor:
        cfg = BRAND_CONFIG.get(selected_brand, {})
        st.info(f"Section-level analysis is only available for Salesforce. Switch to **Scorecard** to see {cfg.get('icon', '')} {selected_brand} data.")
    elif selected_slug and selected_slug in analyses:
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
                    st.success(render_recommendation(top, cta_library, trail_library))
                else:
                    st.info("No recommendation available")

            # Expandable rationale
            with st.expander("View Details", expanded=False):
                st.markdown(f"**Classification Rationale:** {cls['rationale']}")
                st.markdown(f"**Topics:** {', '.join(cls.get('topic_tags', []))}")

                if sa.get("recommendations"):
                    st.markdown("**All Candidates:**")
                    for i, rec in enumerate(sa["recommendations"]):
                        rec_type = rec.get("type", "cta")
                        label = "🎓 Trail" if rec_type == "trail" else "📣 CTA"
                        if rec_type == "trail":
                            t = trail_library.get(rec.get("trail_id", ""), {})
                            name = t.get("name") or rec.get("trail_id", "Unknown")
                        else:
                            t = cta_library.get(rec.get("cta_id", ""), {})
                            name = t.get("headline") or rec.get("cta_id", "Unknown")
                        st.markdown(
                            f"{i+1}. {label} — **{name}** "
                            f"(Score: {rec['score']:.0%}) — {rec['match_rationale']}"
                        )

            st.divider()

    elif selected_slug:
        st.info(f"No analysis for **{articles[selected_slug].get('title', selected_slug)}** yet.")

# === Tab 3: Scorecard ===
with tab3:
    if is_competitor and competitor_data:
        # --- Competitor Scorecard ---
        cfg = BRAND_CONFIG.get(selected_brand, {})
        st.markdown(f"### {cfg.get('icon', '')} {selected_brand} — {selected_year} Audit")

        cd = competitor_data
        total_articles = cd.get("total_articles", len(cd.get("article_rows", [])))
        total_sections = cd.get("total_sections", sum(r.get("sections", 0) for r in cd.get("article_rows", [])))
        total_issues = cd.get("total_cta_issues", sum(r.get("misaligned", 0) for r in cd.get("article_rows", [])))
        healthy = cd.get("healthy_articles", sum(1 for r in cd.get("article_rows", []) if r.get("health", 0) >= 0.7))
        avg = sum(r.get("health", 0) for r in cd.get("article_rows", [])) / total_articles if total_articles else 0

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Articles", total_articles)
        m2.metric("Sections", total_sections)
        m3.metric("Avg CTA Health", f"{int(avg * 100)}/100", help="See Methodology tab")
        m4.metric("Healthy (70+)", f"{healthy}/{total_articles}")
        m5.metric("CTA Issues", total_issues)

        st.markdown("---")

        opp_col, dist_col = st.columns(2)
        opp = cd.get("opportunity", {})
        with opp_col:
            st.markdown("#### CTA Opportunity Breakdown")
            opp_df = pd.DataFrame([
                {"Status": "✅ Good CTA", "Sections": opp.get("good_cta", 0)},
                {"Status": "❌ Missing CTA", "Sections": opp.get("missing_cta", 0)},
                {"Status": "⚠️ Wrong CTA", "Sections": opp.get("wrong_cta", 0)},
                {"Status": "— No CTA Needed", "Sections": opp.get("no_cta_needed", 0)},
            ])
            st.dataframe(opp_df, use_container_width=True, hide_index=True)

        funnel = cd.get("funnel_counts", {})
        with dist_col:
            st.markdown("#### Funnel Stage Distribution")
            funnel_df = pd.DataFrame([
                {"Funnel Stage": k.title(), "Sections": v}
                for k, v in funnel.items()
            ])
            st.dataframe(funnel_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Article Health Scores")
        comp_df = build_competitor_health_df(cd)
        if not comp_df.empty:
            comp_df["CTA Health"] = comp_df["Health Score"].map(lambda x: int(x * 100))
            comp_df["Grade"] = comp_df["Health Score"].map(
                lambda x: "🟢 Excellent" if x >= 0.85 else "🔵 Solid" if x >= 0.70 else "🟡 Needs Work" if x >= 0.55 else "🔴 Poor"
            )
            show_cols = [c for c in ["Article", "Author", "Published", "Sections", "CTA Health", "Grade"] if c in comp_df.columns]
            disp = comp_df[show_cols].sort_values("CTA Health", ascending=True).copy()
            st.dataframe(
                disp,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Article": st.column_config.TextColumn("Article", width="large"),
                    "Author": st.column_config.TextColumn("Author", width="medium"),
                    "Published": st.column_config.TextColumn("Published", width="small"),
                    "Sections": st.column_config.NumberColumn("Sections", width="small"),
                    "CTA Health": st.column_config.NumberColumn("CTA Health", width="small"),
                    "Grade": st.column_config.TextColumn("Grade", width="medium"),
                },
            )

    elif analyses:
        # --- Salesforce Scorecard ---
        health_df = build_health_df(analyses, articles)
        analyzed_df = health_df[health_df["Has Analysis"]].copy()

        # Top-line metrics
        total_sections = int(analyzed_df["Sections"].sum())
        avg = analyzed_df["Health Score"].mean() if len(analyzed_df) > 0 else 0
        avg_100 = int(avg * 100)
        excellent = (analyzed_df["Health Score"] >= 0.85).sum()
        solid = ((analyzed_df["Health Score"] >= 0.70) & (analyzed_df["Health Score"] < 0.85)).sum()
        needs_work = ((analyzed_df["Health Score"] >= 0.55) & (analyzed_df["Health Score"] < 0.70)).sum()
        poor = (analyzed_df["Health Score"] < 0.55).sum()

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Articles", len(analyzed_df))
        m2.metric("Sections", total_sections)
        m3.metric("Avg CTA Health", f"{avg_100}/100", help="Article-level CTA health score. See Methodology tab for details.")
        m4.metric("Excellent + Solid", f"{excellent + solid}/{len(analyzed_df)}", help="Articles scoring 70+ out of 100")
        m5.metric("Needs Work + Poor", f"{needs_work + poor}/{len(analyzed_df)}", help="Articles scoring below 70")

        st.markdown("---")

        # Opportunity breakdown
        opp_col, dist_col = st.columns(2)

        with opp_col:
            st.markdown("#### CTA Health Grade Distribution")
            opp_df = pd.DataFrame([
                {"Grade": "🟢 Excellent (85-100)", "Articles": int(excellent)},
                {"Grade": "🔵 Solid (70-84)", "Articles": int(solid)},
                {"Grade": "🟡 Needs Work (55-69)", "Articles": int(needs_work)},
                {"Grade": "🔴 Poor (below 55)", "Articles": int(poor)},
            ])
            st.dataframe(opp_df, use_container_width=True, hide_index=True)
            st.caption("Based on 100-point rubric. [See Methodology tab for scoring details.]")

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
        analyzed_df["CTA Health"] = analyzed_df["Health Score"].map(lambda x: int(x * 100))
        analyzed_df["Grade"] = analyzed_df["Health Score"].map(
            lambda x: "🟢 Excellent" if x >= 0.85 else "🔵 Solid" if x >= 0.70 else "🟡 Needs Work" if x >= 0.55 else "🔴 Poor"
        )
        display_df = (
            analyzed_df[["Article", "Author", "Published", "Sections", "CTA Health", "Grade"]]
            .sort_values("CTA Health", ascending=True)
            .copy()
        )
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=35 * len(display_df) + 38,
        )

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
                    "Recommended CTA": (
                        trail_library.get(top.get("trail_id",""), {}).get("name", top.get("trail_id",""))
                        if top and top.get("type") == "trail"
                        else cta_library.get(top.get("cta_id",""), {}).get("headline", top.get("cta_id","")) if top else "None"
                    ),
                    "Rec Type": top.get("type", "cta") if top else "",
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

# === Tab 4: Methodology ===
with tab4:
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
