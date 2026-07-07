import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go

from utils.styles import apply_css, BRAND_COLORS, PLOT_LAYOUT, kpi_card, gap_badge, page_header, section_label, GRID_COLOR
from utils.db import get_kpis, get_brand_discount_overview, get_gap_analysis, get_gap_analysis_by_price_band

st.set_page_config(page_title="Overview · Market Intelligence", page_icon="◈", layout="wide")
apply_css()

page_header("Overview", "Executive KPIs and the overall discount landscape across all brands.")

with st.spinner(""):
    kpis       = get_kpis()
    df_overview = get_brand_discount_overview()

# ── KPI Cards ──────────────────────────────────────────────────────────
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

# ── Price-Band-Aware Discount Gap ──────────────────────────────────────
section_label("Discount Gap by Category")

PRICE_BANDS = {
    "All Products":             (0,     0),
    "Budget  < ₹1,500":        (0,     1500),
    "Mid-Range  ₹1,500–₹5,000": (1500,  5000),
    "Premium  ₹5,000–₹10,000":  (5000,  10000),
    "Luxury  > ₹10,000":        (10000, 0),
}

st.markdown("""
<div style="background:#F4F4F8;border:1px solid #E5E5EE;border-radius:10px;padding:12px 16px;margin-bottom:1rem;">
    <div style="font-size:0.78rem;color:#707080;line-height:1.5;">
        Average discount across wildly different price points is misleading — filter to a
        price band to compare <strong>like-for-like</strong> products across brands.
    </div>
</div>
""", unsafe_allow_html=True)

selected_band = st.radio(
    "Price band",
    options=list(PRICE_BANDS.keys()),
    index=0,
    horizontal=True,
    label_visibility="collapsed",
)

min_p, max_p = PRICE_BANDS[selected_band]

with st.spinner(""):
    gap_df = get_gap_analysis() if (min_p == 0 and max_p == 0) else get_gap_analysis_by_price_band(float(min_p), float(max_p))

if gap_df.empty:
    st.warning(f"No products found in **{selected_band}** for one or more brands.")
else:
    # Context strip — avg MRP per brand in this band
    band_label = selected_band.split("  ")[-1].strip()
    mrp_col1, mrp_col2, mrp_col3 = st.columns(3)
    for col, brand, mrp_key, color in [
        (mrp_col1, "Our Store",   "our_avg_mrp", "#5B50E8"),
        (mrp_col2, "Forever New", "fn_avg_mrp",  "#D04A6A"),
        (mrp_col3, "Vero Moda",   "vm_avg_mrp",  "#1FAF8A"),
    ]:
        avg_mrp = int(gap_df[mrp_key].mean()) if mrp_key in gap_df.columns else 0
        with col:
            st.markdown(f"""
            <div style="background:#FFFFFF;border:1px solid #E5E5EE;border-radius:8px;padding:10px 14px;border-top:3px solid {color};margin-bottom:1rem;">
                <div style="font-size:0.68rem;font-weight:600;color:{color};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:3px;">{brand}</div>
                <div style="font-size:0.78rem;color:#505060;">Avg MRP in band: <strong style="color:#1A1A2E;">₹{avg_mrp:,}</strong></div>
            </div>""", unsafe_allow_html=True)

    # Enriched table
    display_df = gap_df.copy()
    display_df["Signal"]      = display_df["max_gap"].apply(gap_badge)
    display_df["Our Store"]   = display_df.apply(
        lambda r: f"<span style='color:#1A1A2E;font-weight:500'>{r['our_discount']}%</span>"
                  f"<br><span style='color:#A0A0B0;font-size:0.75rem;'>₹{int(r['our_avg_mrp']):,} avg · {r['our_pct_on_sale']}% on sale</span>", axis=1)
    display_df["Forever New"] = display_df.apply(
        lambda r: f"<span style='color:#D04A6A;font-weight:500'>{r['fn_discount']}%</span>"
                  f"<br><span style='color:#A0A0B0;font-size:0.75rem;'>₹{int(r['fn_avg_mrp']):,} avg · {r['fn_pct_on_sale']}% on sale</span>", axis=1)
    display_df["Vero Moda"]   = display_df.apply(
        lambda r: f"<span style='color:#1FAF8A;font-weight:500'>{r['vm_discount']}%</span>"
                  f"<br><span style='color:#A0A0B0;font-size:0.75rem;'>₹{int(r['vm_avg_mrp']):,} avg · {r['vm_pct_on_sale']}% on sale</span>", axis=1)
    display_df["Max Gap"]     = display_df["max_gap"].apply(
        lambda g: f"<strong style='color:#C0354A'>+{g}%</strong>" if g > 15 else f"+{g}%")

    st.markdown(
        display_df[["category", "Our Store", "Forever New", "Vero Moda", "Max Gap", "Signal"]]
        .rename(columns={"category": "Category"})
        .to_html(index=False, escape=False),
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # # Bar chart
    # cats = gap_df["category"].tolist()
    # fig = go.Figure()
    # for brand, col_name in [("Our Store", "our_discount"), ("Forever New", "fn_discount"), ("Vero Moda", "vm_discount")]:
    #     fig.add_trace(go.Bar(
    #         name=brand, x=cats, y=gap_df[col_name],
    #         marker_color=BRAND_COLORS[brand], marker_line_width=0, opacity=0.85,
    #     ))
    # fig.update_layout(
    #     **PLOT_LAYOUT, barmode="group", height=380, bargap=0.2, bargroupgap=0.05,
    #     xaxis=dict(tickangle=-30, gridcolor=GRID_COLOR, linecolor=GRID_COLOR, tickfont=dict(size=11)),
    #     yaxis=dict(title="Avg Discount (%)", gridcolor=GRID_COLOR, ticksuffix="%", zeroline=False),
    #     legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
    # )
    # st.plotly_chart(fig, width="stretch")

# ── Product Volume Heatmap ──────────────────────────────────────────────
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
