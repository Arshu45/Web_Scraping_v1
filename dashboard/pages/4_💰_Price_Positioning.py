import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go

from utils.styles import apply_css, PLOT_LAYOUT, page_header, section_label, GRID_COLOR
from utils.db import get_price_band_data

st.set_page_config(page_title="Price Positioning · Market Intelligence", page_icon="◈", layout="wide")
apply_css()

page_header("Price Positioning", "Budget vs mid-range vs premium — where does each brand sit?")

with st.spinner(""):
    band_counts, band_order = get_price_band_data()

brands = ["Our Store", "Forever New", "Vero Moda"]
BAND_COLORS = {
    "Budget (<₹1.5K)":      "#1FAF8A",
    "Mid-Range (₹1.5K–5K)": "#5B50E8",
    "Premium (₹5K–10K)":    "#D04A6A",
    "Luxury (>₹10K)":       "#C4892A",
}

# ── Toggle ─────────────────────────────────────────────────────────
section_label("Price Band Distribution by Brand")

view_col, _ = st.columns([2, 5])
with view_col:
    view_mode = st.segmented_control(
        "View",
        options=["Donut", "Bar"],
        default="Donut",
        label_visibility="collapsed",
    )

# Shared legend strip
legend_html = " ".join([
    f"<span style='display:inline-flex;align-items:center;gap:6px;margin-right:20px;'>"
    f"<span style='width:8px;height:8px;border-radius:50%;background:{c};display:inline-block'></span>"
    f"<span style='font-size:0.78rem;color:#909098;'>{b}</span></span>"
    for b, c in BAND_COLORS.items()
])
st.markdown(f"<div style='margin-bottom:16px'>{legend_html}</div>", unsafe_allow_html=True)

if view_mode == "Donut":
    # ── Three donut charts ──────────────────────────────────────────
    cols = st.columns(3)
    for idx, brand in enumerate(brands):
        bdf  = band_counts[band_counts["brand"] == brand]
        bdf  = bdf.set_index("price_band").reindex(band_order).fillna(0).reset_index()
        total = int(bdf["count"].sum())
        clrs  = [BAND_COLORS.get(b, "#CCC") for b in bdf["price_band"]]

        fig = go.Figure(go.Pie(
            labels=bdf["price_band"], values=bdf["count"],
            hole=0.65, marker_colors=clrs,
            marker=dict(line=dict(color="#FAFAFA", width=2)),
            textinfo="percent", textfont=dict(size=11, color="#505060"),
            hovertemplate="<b>%{label}</b><br>%{value:,} products (%{percent})<extra></extra>",
        ))
        fig.update_layout(
            **PLOT_LAYOUT, height=300,
            title=dict(
                text=f"<b style='color:#1A1A2E;font-size:13px'>{brand}</b><br>"
                     f"<span style='color:#A0A0B0;font-size:11px'>{total:,} products</span>",
                x=0.5, xanchor="center",
            ),
            showlegend=False,
            annotations=[dict(text=brand.split()[0], x=0.5, y=0.5,
                              font=dict(size=13, color="#909098"), showarrow=False)],
        )
        with cols[idx]:
            st.plotly_chart(fig, width="stretch")

else:
    # ── Stacked bar chart ───────────────────────────────────────────
    fig2 = go.Figure()
    for band in band_order:
        vals = [
            int(band_counts[(band_counts["brand"] == brand) & (band_counts["price_band"] == band)]["count"].values[0])
            if not band_counts[(band_counts["brand"] == brand) & (band_counts["price_band"] == band)].empty else 0
            for brand in brands
        ]
        fig2.add_trace(go.Bar(
            name=band, x=brands, y=vals,
            marker_color=BAND_COLORS.get(band, "#CCC"), marker_line_width=0, opacity=0.88,
            text=vals, textposition="inside", textfont=dict(size=11, color="#FFFFFF"),
        ))
    fig2.update_layout(
        **PLOT_LAYOUT, barmode="stack", height=400, bargap=0.35,
        yaxis=dict(title="Number of Products", gridcolor=GRID_COLOR, zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
                    bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig2, width="stretch")


# ── Observation callouts ───────────────────────────────────────────
section_label("Key Observations")

col1, col2 = st.columns(2)
with col1:
    st.markdown("""
    <div style="background:#FFFFFF;border:1px solid #E5E5EE;border-left:3px solid #5B50E8;
                border-radius:8px;padding:16px 18px;">
        <div style="font-size:0.72rem;font-weight:600;color:#5B50E8;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.08em;">Price Tier Overlap</div>
        <div style="font-size:0.82rem;color:#909098;line-height:1.6;">
            If competitors have more Budget products but we're mostly Mid-Range,
            they are capturing price-sensitive customers we're missing.
        </div>
    </div>""", unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style="background:#FFFFFF;border:1px solid #E5E5EE;border-left:3px solid #D04A6A;
                border-radius:8px;padding:16px 18px;">
        <div style="font-size:0.72rem;font-weight:600;color:#D04A6A;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.08em;">Competitor Discount Strategy</div>
        <div style="font-size:0.82rem;color:#909098;line-height:1.6;">
            Competitors offer 40–55% discounts while we average ~12%. Their effective
            selling price is significantly lower despite comparable list prices.
        </div>
    </div>""", unsafe_allow_html=True)
