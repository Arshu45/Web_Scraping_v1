import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import os
import sys

# Add root folder to python path for importing connection
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.db import get_promotions
from utils.styles import apply_css, page_header, section_label

st.set_page_config(
    page_title="Promotional Intelligence",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_css()

# ── Sidebar Filters ──────────────────────────────────────────────────
st.sidebar.markdown("""
<div style="padding: 0.5rem 0 1rem 0;">
    <div style="font-size: 0.7rem; font-weight: 600; color: #A0A0B0; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.5rem;">Platform</div>
    <div style="font-size: 1rem; font-weight: 600; color: #1A1A2E; letter-spacing: -0.01em;">Market Intelligence</div>
</div>
<hr style="border-color: #E0E0EA; margin: 0 0 1.5rem 0;">
""", unsafe_allow_html=True)

st.sidebar.markdown('<div class="section-label">Filters</div>', unsafe_allow_html=True)

# Fetch promotions DataFrame
df = get_promotions()

if df.empty:
    page_header("Promotional Intelligence", "Real-time competitor promotion monitoring.")
    st.warning("⚠️ No promotions found in the database. Please initialize the DB and run the scraper first!")
    st.info("Run `python scripts/init_db.py` then `python flows/master_pipeline.py` to get started.")
    st.stop()

# 1. Brand Filter
all_brands = sorted(df["brand"].dropna().unique().tolist())
selected_brands = st.sidebar.multiselect("Select Brands", all_brands, default=all_brands)

# 2. Date Filter
min_date = df["scraped_date"].min()
max_date = df["scraped_date"].max()

# Default date inputs
start_date = st.sidebar.date_input("Start Date", min_date)
end_date = st.sidebar.date_input("End Date", max_date)

# 3. Source Filter
all_sources = sorted(df["source_name"].dropna().unique().tolist())
selected_sources = st.sidebar.multiselect("Select Extraction Sources", all_sources, default=all_sources)

# Apply filters
filtered_df = df[
    (df["brand"].isin(selected_brands)) &
    (df["scraped_date"] >= start_date) &
    (df["scraped_date"] <= end_date) &
    (df["source_name"].isin(selected_sources))
]

# ── Main Content ──
page_header("Promotional Intelligence", "Monitor active discounts and promotional campaigns across target brands.")

# Metrics
st.markdown('<div class="section-label">KPI Metrics</div>', unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Total Extracted Promotions</div>
        <div class="kpi-value">{len(filtered_df)}</div>
        <div class="kpi-sub">matching active filters</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    active_brands_count = filtered_df["brand"].nunique()
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Active Brands</div>
        <div class="kpi-value">{active_brands_count}</div>
        <div class="kpi-sub">running campaigns</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    today = datetime.date.today()
    promos_today = len(df[df["scraped_date"] == today])
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Scraped Today</div>
        <div class="kpi-value">{promos_today}</div>
        <div class="kpi-sub">unique offers found today</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ── Visualizations ──
if not filtered_df.empty:
    viz_col1, viz_col2 = st.columns(2)
    
    with viz_col1:
        st.markdown('<div class="section-label">Promotions by Brand</div>', unsafe_allow_html=True)
        brand_counts = filtered_df["brand"].value_counts().reset_index()
        brand_counts.columns = ["Brand", "Promotions"]
        fig_brand = px.bar(
            brand_counts,
            x="Promotions",
            y="Brand",
            orientation="h",
            color="Brand",
            color_discrete_sequence=px.colors.qualitative.Safe,
            text_auto=True
        )
        fig_brand.update_layout(
            showlegend=False,
            margin=dict(l=20, r=20, t=10, b=20),
            height=280,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="#EBEBF2"),
            yaxis=dict(showgrid=False)
        )
        st.plotly_chart(fig_brand, width="stretch")
        
    with viz_col2:
        st.markdown('<div class="section-label">Extraction Timeline</div>', unsafe_allow_html=True)
        timeline = filtered_df.groupby("scraped_date").size().reset_index()
        timeline.columns = ["Date", "Offers"]
        # Ensure Date is string for nice timeline sorting in plotly
        timeline["Date"] = timeline["Date"].astype(str)
        fig_time = px.line(
            timeline,
            x="Date",
            y="Offers",
            markers=True
        )
        fig_time.update_traces(line_color="#5B50E8", line_width=2.5, marker=dict(size=6))
        fig_time.update_layout(
            margin=dict(l=20, r=20, t=10, b=20),
            height=280,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="#EBEBF2"),
            yaxis=dict(showgrid=True, gridcolor="#EBEBF2")
        )
        st.plotly_chart(fig_time, width="stretch")

st.markdown("<hr>", unsafe_allow_html=True)

# ── Data Table ──
st.markdown('<div class="section-label">Extracted Promotions</div>', unsafe_allow_html=True)

if filtered_df.empty:
    st.info("No promotions match the selected filters.")
else:
    # Format table for display
    display_df = filtered_df[[
        "brand", "source_name", "offer_title", "raw_text", "source_url", "extraction_confidence", "scraped_at"
    ]].copy()
    
    display_df.columns = ["Brand", "Source Strategy", "Offer Title", "Raw Text", "Source URL", "Confidence", "Scraped Timestamp"]
    
    st.dataframe(
        display_df,
        column_config={
            "Source URL": st.column_config.LinkColumn("Source URL"),
            "Scraped Timestamp": st.column_config.DatetimeColumn("Scraped Timestamp", format="YYYY-MM-DD HH:mm:ss"),
        },
        width="stretch",
        hide_index=True
    )
