import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go

from utils.styles import apply_css, BRAND_COLORS, PLOT_LAYOUT, gap_badge, page_header, section_label, GRID_COLOR
from utils.db import get_gap_analysis, get_category_price_distribution

st.set_page_config(page_title="Competitor Battle · Market Intelligence", page_icon="◈", layout="wide")
apply_css()

page_header("Competitor Battle", "Where are the biggest discount gaps? Where do we need to act?")

with st.spinner(""):
    gap_df = get_gap_analysis()

# ── Gap Table ──────────────────────────────────────────────────────
section_label("Category Discount Gap — Our Store vs Competitors")

display_df = gap_df.copy()
display_df["Signal"]      = display_df["max_gap"].apply(gap_badge)
display_df["Our Store"]   = display_df["our_discount"].astype(str) + "%"
display_df["Forever New"] = display_df["fn_discount"].astype(str) + "%"
display_df["Vero Moda"]   = display_df["vm_discount"].astype(str) + "%"
display_df["Max Gap"]     = display_df["max_gap"].astype(str) + "%"

st.markdown(
    display_df[["category", "Our Store", "Forever New", "Vero Moda", "Max Gap", "Signal"]]
    .rename(columns={"category": "Category"})
    .to_html(index=False, escape=False),
    unsafe_allow_html=True,
)
st.markdown("<br>", unsafe_allow_html=True)

# ── Bar chart ─────────────────────────────────────────────────────
section_label("Discount Gap Visual — Our Store vs Each Competitor")

cats = gap_df["category"].tolist()
fig = go.Figure()
for brand, col in [("Our Store", "our_discount"), ("Forever New", "fn_discount"), ("Vero Moda", "vm_discount")]:
    fig.add_trace(go.Bar(
        name=brand, x=cats, y=gap_df[col],
        marker_color=BRAND_COLORS[brand], marker_line_width=0, opacity=0.85,
    ))
fig.update_layout(
    **PLOT_LAYOUT, barmode="group", height=400, bargap=0.2, bargroupgap=0.05,
    xaxis=dict(tickangle=-30, gridcolor=GRID_COLOR, linecolor=GRID_COLOR),
    yaxis=dict(title="Avg Discount (%)", gridcolor=GRID_COLOR, ticksuffix="%", zeroline=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
)
st.plotly_chart(fig, width="stretch")

# ── Category Deep Dive ─────────────────────────────────────────────
st.markdown("<hr>", unsafe_allow_html=True)
section_label("Category Deep Dive — Price Distribution")

all_cats = sorted(gap_df["category"].tolist())
sel_cat = st.selectbox(
    "Select category", all_cats,
    index=all_cats.index("Tops") if "Tops" in all_cats else 0,
    label_visibility="collapsed",
)

with st.spinner(""):
    price_df = get_category_price_distribution(sel_cat)

if not price_df.empty:
    col1, col2 = st.columns([3, 1])
    with col1:
        fig2 = go.Figure()
        for brand in ["Our Store", "Forever New", "Vero Moda"]:
            bdf = price_df[price_df["brand"] == brand]["price"]
            if not bdf.empty:
                hex_color = BRAND_COLORS.get(brand, "#888").lstrip("#")
                r, g, b   = int(hex_color[0:2],16), int(hex_color[2:4],16), int(hex_color[4:6],16)
                fig2.add_trace(go.Box(
                    y=bdf, name=brand,
                    marker_color=BRAND_COLORS.get(brand, "#aaa"),
                    line_color=BRAND_COLORS.get(brand, "#aaa"),
                    fillcolor=f"rgba({r},{g},{b},0.10)",
                    boxmean=True,
                ))
        fig2.update_layout(
            **PLOT_LAYOUT, height=360,
            title=dict(text=f"MRP Distribution — {sel_cat}", font=dict(size=13, color="#909098")),
            yaxis=dict(title="MRP (₹)", gridcolor=GRID_COLOR, zeroline=False),
        )
        st.plotly_chart(fig2, width="stretch")

    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        cat_row = gap_df[gap_df["category"] == sel_cat].iloc[0] if sel_cat in gap_df["category"].values else None
        if cat_row is not None:
            st.metric("Our Store", f"{cat_row['our_discount']}%")
            st.metric("Forever New", f"{cat_row['fn_discount']}%",
                      delta=f"{round(float(cat_row['fn_discount'] - cat_row['our_discount']),1)}%",
                      delta_color="inverse")
            st.metric("Vero Moda", f"{cat_row['vm_discount']}%",
                      delta=f"{round(float(cat_row['vm_discount'] - cat_row['our_discount']),1)}%",
                      delta_color="inverse")
            st.markdown(f"<br>{gap_badge(float(cat_row['max_gap']))}", unsafe_allow_html=True)
