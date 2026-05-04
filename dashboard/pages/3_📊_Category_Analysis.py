import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go

from utils.styles import apply_css, BRAND_COLORS, PLOT_LAYOUT, page_header, section_label, GRID_COLOR
from utils.db import get_brand_discount_overview

st.set_page_config(page_title="Category Analysis · Market Intelligence", page_icon="◈", layout="wide")
apply_css()

page_header("Category Analysis", "Discount depth and pricing behaviour per category across all three brands.")

with st.spinner(""):
    df = get_brand_discount_overview()

all_cats = sorted(df["master_category"].unique())

with st.sidebar:
    st.markdown("<div style='font-size:0.7rem;font-weight:600;color:#A0A0B0;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;'>Filters</div>", unsafe_allow_html=True)
    selected_cats = st.multiselect("Categories", all_cats, default=all_cats[:8], label_visibility="collapsed")
    st.markdown("<div style='font-size:0.7rem;color:#A0A0B0;margin-top:8px;margin-bottom:4px;'>Brands</div>", unsafe_allow_html=True)
    selected_brands = st.multiselect("Brands", ["Our Store", "Forever New", "Vero Moda"],
                                     default=["Our Store", "Forever New", "Vero Moda"],
                                     label_visibility="collapsed")

if not selected_cats:
    st.warning("Select at least one category from the sidebar.")
    st.stop()

filtered = df[df["master_category"].isin(selected_cats) & df["brand"].isin(selected_brands)]

# ── Horizontal Bar ─────────────────────────────────────────────────
section_label("Avg Discount by Category & Brand")

fig = go.Figure()
for brand in selected_brands:
    bdf = filtered[filtered["brand"] == brand].sort_values("master_category")
    fig.add_trace(go.Bar(
        name=brand, y=bdf["master_category"], x=bdf["avg_discount"],
        orientation="h",
        marker_color=BRAND_COLORS.get(brand, "#888"), marker_line_width=0, opacity=0.85,
        text=[f"{v}%" for v in bdf["avg_discount"]],
        textposition="outside", textfont=dict(size=10, color="#A0A0B0"),
    ))
fig.update_layout(
    **PLOT_LAYOUT, barmode="group",
    height=max(320, len(selected_cats) * 42 + 80),
    bargap=0.2,
    xaxis=dict(title="Avg Discount (%)", ticksuffix="%", gridcolor=GRID_COLOR, zeroline=False),
    yaxis=dict(gridcolor=GRID_COLOR),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
)
st.plotly_chart(fig, width="stretch")

# ── Scatter ────────────────────────────────────────────────────────
section_label("Product Volume vs Discount Depth")
st.caption("Each bubble = one brand × category. Larger = more products.")

fig2 = go.Figure()
for brand in selected_brands:
    bdf = filtered[filtered["brand"] == brand]
    fig2.add_trace(go.Scatter(
        x=bdf["products"], y=bdf["avg_discount"],
        mode="markers+text", name=brand,
        text=bdf["master_category"], textposition="top center",
        textfont=dict(size=9, color="#A0A0B0"),
        marker=dict(
            size=bdf["products"].clip(6, 50),
            color=BRAND_COLORS.get(brand, "#888"),
            opacity=0.75, line=dict(width=0),
        ),
    ))
fig2.update_layout(
    **PLOT_LAYOUT, height=420,
    xaxis=dict(title="Number of Products", gridcolor=GRID_COLOR, zeroline=False),
    yaxis=dict(title="Avg Discount (%)", ticksuffix="%", gridcolor=GRID_COLOR, zeroline=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
)
st.plotly_chart(fig2, width="stretch")
