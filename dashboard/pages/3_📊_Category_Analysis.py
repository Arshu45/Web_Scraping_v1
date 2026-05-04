import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from utils.styles import apply_css, BRAND_COLORS, PLOT_LAYOUT
from utils.db import get_brand_discount_overview

st.set_page_config(page_title="Category Analysis | Market Intelligence", page_icon="📊", layout="wide")
apply_css()

st.markdown("<h1 style='color:#fff; font-weight:800;'>📊 Category Analysis</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#888;'>Understand discount depth and pricing behaviour per category across all three brands.</p>", unsafe_allow_html=True)
st.markdown("---")

with st.spinner("Loading..."):
    df = get_brand_discount_overview()

all_cats = sorted(df["master_category"].unique())

# Sidebar filter
st.sidebar.markdown("### Filters")
selected_cats = st.sidebar.multiselect("Categories", all_cats, default=all_cats[:8])
selected_brands = st.sidebar.multiselect("Brands", ["Our Store", "Forever New", "Vero Moda"], default=["Our Store", "Forever New", "Vero Moda"])

if not selected_cats:
    st.warning("Select at least one category from the sidebar.")
    st.stop()

filtered = df[df["master_category"].isin(selected_cats) & df["brand"].isin(selected_brands)]

# ── Horizontal Bar: Avg Discount per Category ─────────────────────────
st.markdown("<div class='section-header'>Avg Discount by Category & Brand</div>", unsafe_allow_html=True)
fig = go.Figure()
for brand in selected_brands:
    bdf = filtered[filtered["brand"] == brand].sort_values("master_category")
    fig.add_trace(go.Bar(
        name=brand,
        y=bdf["master_category"],
        x=bdf["avg_discount"],
        orientation="h",
        marker_color=BRAND_COLORS.get(brand, "#aaa"),
        opacity=0.9,
        text=[f"{v}%" for v in bdf["avg_discount"]],
        textposition="outside",
    ))
fig.update_layout(
    **PLOT_LAYOUT, barmode="group", height=max(350, len(selected_cats) * 45 + 80),
    xaxis=dict(title="Avg Discount (%)", ticksuffix="%", gridcolor="rgba(255,255,255,0.05)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, width="stretch")

# ── Scatter: Avg MRP vs Avg Discount ─────────────────────────────────
st.markdown("<div class='section-header'>Price Tier vs Discount Depth — Scatter View</div>", unsafe_allow_html=True)
st.caption("Each bubble = one brand × category. Bigger bubble = more products. Right = higher price, Up = higher discount.")

scatter_df = filtered.copy()
scatter_df["avg_mrp"] = scatter_df.apply(
    lambda row: float(df[(df["brand"] == row["brand"]) & (df["master_category"] == row["master_category"])]["products"].values[0]) if len(df[(df["brand"] == row["brand"]) & (df["master_category"] == row["master_category"])]) > 0 else 10,
    axis=1
)

fig2 = go.Figure()
for brand in selected_brands:
    bdf = scatter_df[scatter_df["brand"] == brand]
    fig2.add_trace(go.Scatter(
        x=bdf["products"],
        y=bdf["avg_discount"],
        mode="markers+text",
        name=brand,
        text=bdf["master_category"],
        textposition="top center",
        textfont=dict(size=9),
        marker=dict(
            size=bdf["products"].clip(5, 60),
            color=BRAND_COLORS.get(brand, "#aaa"),
            opacity=0.8,
            line=dict(width=1, color="rgba(255,255,255,0.2)")
        ),
    ))
fig2.update_layout(
    **PLOT_LAYOUT, height=450,
    xaxis=dict(title="Number of Products", gridcolor="rgba(255,255,255,0.05)"),
    yaxis=dict(title="Avg Discount (%)", ticksuffix="%", gridcolor="rgba(255,255,255,0.05)"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig2, width="stretch")
