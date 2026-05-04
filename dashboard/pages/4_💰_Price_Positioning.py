import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go

from utils.styles import apply_css, BRAND_COLORS, PLOT_LAYOUT
from utils.db import get_price_band_data

st.set_page_config(page_title="Price Positioning | Market Intelligence", page_icon="💰", layout="wide")
apply_css()

st.markdown("<h1 style='color:#fff; font-weight:800;'>💰 Price Positioning</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#888;'>How does our store's price tier compare to competitors? Budget, mid-range, or premium?</p>", unsafe_allow_html=True)
st.markdown("---")

with st.spinner("Loading price data..."):
    band_counts, band_order = get_price_band_data()

brands = ["Our Store", "Forever New", "Vero Moda"]

# ── Side-by-side Donut Charts ─────────────────────────────────────────
st.markdown("<div class='section-header'>Price Band Distribution by Brand</div>", unsafe_allow_html=True)

band_colors = {
    "Budget (<₹1.5K)":       "#43D9AD",
    "Mid-Range (₹1.5K–5K)":  "#6C63FF",
    "Premium (₹5K–10K)":     "#FF6584",
    "Luxury (>₹10K)":        "#FFB347",
}

cols = st.columns(3)
for idx, brand in enumerate(brands):
    bdf = band_counts[band_counts["brand"] == brand]
    bdf = bdf.set_index("price_band").reindex(band_order).fillna(0).reset_index()
    total = int(bdf["count"].sum())
    clrs = [band_colors.get(b, "#aaa") for b in bdf["price_band"]]

    fig = go.Figure(go.Pie(
        labels=bdf["price_band"],
        values=bdf["count"],
        hole=0.6,
        marker_colors=clrs,
        textinfo="percent",
        hovertemplate="<b>%{label}</b><br>%{value:,} products (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        **PLOT_LAYOUT,
        height=320,
        title=dict(text=f"<b>{brand}</b><br><span style='font-size:12px;color:#888'>{total:,} products</span>", x=0.5),
        showlegend=False,
        annotations=[dict(text=brand.split()[0], x=0.5, y=0.5, font_size=14, font_color="#fff", showarrow=False)],
    )
    with cols[idx]:
        st.plotly_chart(fig, width="stretch")

# ── Legend ────────────────────────────────────────────────────────────
legend_html = "".join([
    f"<span style='background:{c}; width:12px; height:12px; display:inline-block; border-radius:3px; margin-right:6px;'></span><span style='color:#ccc; margin-right:20px;'>{b}</span>"
    for b, c in band_colors.items()
])
st.markdown(f"<div style='text-align:center; margin-top:-10px; margin-bottom: 1rem;'>{legend_html}</div>", unsafe_allow_html=True)

# ── Stacked Bar: Price Band per Band across brands ────────────────────
st.markdown("<div class='section-header'>Price Band Comparison — Side by Side</div>", unsafe_allow_html=True)

fig2 = go.Figure()
for band in band_order:
    vals = []
    for brand in brands:
        row = band_counts[(band_counts["brand"] == brand) & (band_counts["price_band"] == band)]
        vals.append(int(row["count"].values[0]) if not row.empty else 0)
    fig2.add_trace(go.Bar(
        name=band,
        x=brands,
        y=vals,
        marker_color=band_colors.get(band, "#aaa"),
        opacity=0.9,
        text=vals,
        textposition="inside",
    ))

fig2.update_layout(
    **PLOT_LAYOUT, barmode="stack", height=380,
    yaxis=dict(title="Number of Products", gridcolor="rgba(255,255,255,0.05)"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
)
st.plotly_chart(fig2, width="stretch")

# ── Insight Cards ─────────────────────────────────────────────────────
st.markdown("<div class='section-header'>📌 Insights</div>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.info("""
**Price Tier Overlap**  
Compare where price bands overlap between Our Store and competitors.
If competitors have more "Budget" products but we're mostly "Mid-Range",
they are capturing price-sensitive customers we're missing.
""")
with col2:
    st.warning("""
**Competitor Discount Strategy**  
Even if our MRP is similar to competitors, they offer **40–55% discounts**
while we average **~12%**. This means competitors' effective selling price
is significantly lower despite comparable list prices.
""")
