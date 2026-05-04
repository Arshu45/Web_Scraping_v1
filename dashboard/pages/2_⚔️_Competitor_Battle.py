import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from utils.styles import apply_css, BRAND_COLORS, PLOT_LAYOUT, gap_badge
from utils.db import get_gap_analysis, get_category_price_distribution, get_volume_heatmap

st.set_page_config(page_title="Competitor Battle | Market Intelligence", page_icon="⚔️", layout="wide")
apply_css()

st.markdown("<h1 style='color:#fff; font-weight:800;'>⚔️ Competitor Battle</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#888;'>Where are the biggest discount gaps? Where do we need to act?</p>", unsafe_allow_html=True)
st.markdown("---")

with st.spinner("Loading gap analysis..."):
    gap_df = get_gap_analysis()

# ── Discount Gap Table ─────────────────────────────────────────────────
st.markdown("<div class='section-header'>Category Discount Gap — Our Store vs Competitors</div>", unsafe_allow_html=True)

display_df = gap_df.copy()
display_df["signal"] = display_df["max_gap"].apply(gap_badge)
display_df["Forever New Disc"] = display_df["fn_discount"].astype(str) + "%"
display_df["Vero Moda Disc"] = display_df["vm_discount"].astype(str) + "%"
display_df["Our Disc"] = display_df["our_discount"].astype(str) + "%"
display_df["Max Gap"] = display_df["max_gap"].astype(str) + "%"

table_cols = ["category", "Our Disc", "Forever New Disc", "Vero Moda Disc", "Max Gap", "signal"]
st.markdown(
    display_df[table_cols].rename(columns={
        "category": "Category", "signal": "Signal"
    }).to_html(index=False, escape=False),
    unsafe_allow_html=True
)

st.markdown("<br>", unsafe_allow_html=True)

# ── Grouped Bar: Gap Visualisation ────────────────────────────────────
st.markdown("<div class='section-header'>Discount Gap Visual — Our Store vs Each Competitor</div>", unsafe_allow_html=True)

cats = gap_df["category"].tolist()
fig = go.Figure()
fig.add_trace(go.Bar(name="Our Store", x=cats, y=gap_df["our_discount"], marker_color=BRAND_COLORS["Our Store"], opacity=0.9))
fig.add_trace(go.Bar(name="Forever New", x=cats, y=gap_df["fn_discount"], marker_color=BRAND_COLORS["Forever New"], opacity=0.9))
fig.add_trace(go.Bar(name="Vero Moda", x=cats, y=gap_df["vm_discount"], marker_color=BRAND_COLORS["Vero Moda"], opacity=0.9))
fig.update_layout(
    **PLOT_LAYOUT, barmode="group", height=420,
    xaxis=dict(tickangle=-30, gridcolor="rgba(255,255,255,0.05)"),
    yaxis=dict(title="Avg Discount (%)", gridcolor="rgba(255,255,255,0.05)", ticksuffix="%"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, width="stretch")

# ── Category Deep Dive ────────────────────────────────────────────────
st.markdown("---")
st.markdown("<div class='section-header'>Category Deep Dive — Price Distribution</div>", unsafe_allow_html=True)

all_cats = sorted(gap_df["category"].tolist())
sel_cat = st.selectbox("Select a category to compare price ranges:", all_cats, index=all_cats.index("Tops") if "Tops" in all_cats else 0)

with st.spinner(f"Loading price data for {sel_cat}..."):
    price_df = get_category_price_distribution(sel_cat)

if not price_df.empty:
    col1, col2 = st.columns([2, 1])
    with col1:
        fig2 = go.Figure()
        for brand in ["Our Store", "Forever New", "Vero Moda"]:
            bdf = price_df[price_df["brand"] == brand]["price"]
            if not bdf.empty:
                fig2.add_trace(go.Box(
                    y=bdf, name=brand,
                    marker_color=BRAND_COLORS.get(brand, "#aaa"),
                    boxmean=True, opacity=0.85,
                ))
        fig2.update_layout(
            **PLOT_LAYOUT, height=380, title=f"MRP Distribution — {sel_cat}",
            yaxis=dict(title="MRP (₹)", gridcolor="rgba(255,255,255,0.05)"),
        )
        st.plotly_chart(fig2, width="stretch")

    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        cat_row = gap_df[gap_df["category"] == sel_cat].iloc[0] if sel_cat in gap_df["category"].values else None
        if cat_row is not None:
            st.metric("Our Store — Avg Disc", f"{cat_row['our_discount']}%")
            st.metric("Forever New — Avg Disc", f"{cat_row['fn_discount']}%", delta=f"{round(float(cat_row['fn_discount'] - cat_row['our_discount']),1)}% vs us", delta_color="inverse")
            st.metric("Vero Moda — Avg Disc", f"{cat_row['vm_discount']}%", delta=f"{round(float(cat_row['vm_discount'] - cat_row['our_discount']),1)}% vs us", delta_color="inverse")
            st.markdown(f"**Signal:** {gap_badge(float(cat_row['max_gap']))}", unsafe_allow_html=True)
