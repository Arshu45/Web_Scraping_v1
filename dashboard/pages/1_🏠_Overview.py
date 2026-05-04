import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go

from utils.styles import apply_css, BRAND_COLORS, PLOT_LAYOUT, kpi_card, page_header, section_label, GRID_COLOR
from utils.db import get_kpis, get_brand_discount_overview

st.set_page_config(page_title="Overview · Market Intelligence", page_icon="◈", layout="wide")
apply_css()

page_header("Overview", "Executive KPIs and the overall discount landscape across all brands.")

with st.spinner(""):
    kpis = get_kpis()
    df_overview = get_brand_discount_overview()

c1, c2, c3, c4, c5 = st.columns(5)
kpi_data = [
    (c1, "Our Store Products",  f"{kpis['our_products']:,}",  "Internal catalog"),
    (c2, "Competitor Products", f"{kpis['comp_products']:,}", "Forever New + Vero Moda"),
    (c3, "Our Avg Discount",    f"{kpis['our_avg_disc']}%",   "Across all categories"),
    (c4, "Forever New Avg",     f"{kpis['fn_avg_disc']}%",    f"+{round(kpis['fn_avg_disc'] - kpis['our_avg_disc'], 1)}% vs us"),
    (c5, "Vero Moda Avg",       f"{kpis['vm_avg_disc']}%",    f"+{round(kpis['vm_avg_disc'] - kpis['our_avg_disc'], 1)}% vs us"),
]
for col, label, value, sub in kpi_data:
    with col:
        st.markdown(kpi_card(label, value, sub), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Grouped Bar ─────────────────────────────────────────────────────
section_label("Average Discount by Category")

brands     = ["Our Store", "Forever New", "Vero Moda"]
categories = sorted(df_overview["master_category"].unique())

fig = go.Figure()
for brand in brands:
    bdf = df_overview[df_overview["brand"] == brand]
    cat_vals = [
        float(bdf[bdf["master_category"] == c]["avg_discount"].values[0])
        if c in bdf["master_category"].values else 0
        for c in categories
    ]
    fig.add_trace(go.Bar(
        name=brand, x=categories, y=cat_vals,
        marker_color=BRAND_COLORS.get(brand, "#888"),
        marker_line_width=0, opacity=0.85,
        text=[f"{v:.0f}%" for v in cat_vals],
        textposition="outside",
        textfont=dict(size=10, color="#A0A0B0"),
    ))

fig.update_layout(
    **PLOT_LAYOUT, barmode="group", height=420, bargap=0.2, bargroupgap=0.05,
    xaxis=dict(tickangle=-30, gridcolor=GRID_COLOR, linecolor=GRID_COLOR, tickfont=dict(size=11)),
    yaxis=dict(title="Avg Discount (%)", gridcolor=GRID_COLOR, ticksuffix="%", zeroline=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
)
st.plotly_chart(fig, width="stretch")

# ── Heatmap ─────────────────────────────────────────────────────────
section_label("Product Volume by Brand & Category")

pivot = df_overview.pivot(index="brand", columns="master_category", values="products").fillna(0)

fig2 = go.Figure(data=go.Heatmap(
    z=pivot.values,
    x=pivot.columns.tolist(),
    y=pivot.index.tolist(),
    colorscale=[
        [0.0, "#F4F4FC"],
        [0.4, "#C5C2F5"],
        [0.7, "#8B85EF"],
        [1.0, "#5B50E8"],
    ],
    text=pivot.values.astype(int),
    texttemplate="%{text}",
    textfont=dict(size=11, color="#505060"),
    hovertemplate="<b>%{y}</b><br>%{x}: %{text} products<extra></extra>",
    showscale=False,
    xgap=3, ygap=3,
))
fig2.update_layout(**PLOT_LAYOUT, height=200, xaxis=dict(tickangle=-30, tickfont=dict(size=10)))
st.plotly_chart(fig2, width="stretch")
