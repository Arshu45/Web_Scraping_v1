import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from utils.styles import apply_css, BRAND_COLORS, PLOT_LAYOUT
from utils.db import get_promotions

st.set_page_config(page_title="Promotions Intel | Market Intelligence", page_icon="🎯", layout="wide")
apply_css()

st.markdown("<h1 style='color:#fff; font-weight:800;'>🎯 Promotions Intelligence</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#888;'>Live competitor coupons, promo types, and discount range analysis from GrabOn & CouponDunia.</p>", unsafe_allow_html=True)
st.markdown("---")

with st.spinner("Loading promotions..."):
    df = get_promotions()

brands_avail = sorted(df["brand"].unique())
sel_brands = st.sidebar.multiselect("Filter by brand", brands_avail, default=brands_avail)
filtered = df[df["brand"].isin(sel_brands)]

total_promos = len(filtered)
avg_max_disc = filtered["discount_max"].dropna().mean()
has_code = filtered["coupon_code"].notna().sum()

# ── KPI Row ───────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Total Promotions Tracked", total_promos)
with c2:
    st.metric("Avg Max Discount", f"{round(avg_max_disc, 1)}%" if pd.notna(avg_max_disc) else "N/A")
with c3:
    st.metric("Promotions with Coupon Code", has_code)

st.markdown("<br>", unsafe_allow_html=True)

col_left, col_right = st.columns([3, 2])

# ── Live Promotions Table ─────────────────────────────────────────────
with col_left:
    st.markdown("<div class='section-header'>Live Promotions Feed</div>", unsafe_allow_html=True)
    display = filtered[["brand", "offer_title", "coupon_code", "discount_max", "min_purchase", "user_type", "source_name", "scraped_date"]].copy()
    display.columns = ["Brand", "Offer", "Coupon Code", "Max Disc %", "Min Purchase ₹", "User Type", "Source", "Scraped"]
    display = display.sort_values("Scraped", ascending=False)
    st.dataframe(display, width="stretch", height=480)

# ── Promo Charts ─────────────────────────────────────────────────────
with col_right:
    # Promo by Brand — pie
    st.markdown("<div class='section-header'>Promotions by Brand</div>", unsafe_allow_html=True)
    brand_counts = filtered["brand"].value_counts().reset_index()
    brand_counts.columns = ["brand", "count"]
    clrs = [BRAND_COLORS.get(b, "#aaa") for b in brand_counts["brand"]]
    fig1 = go.Figure(go.Pie(
        labels=brand_counts["brand"],
        values=brand_counts["count"],
        hole=0.55,
        marker_colors=clrs,
        textinfo="label+percent",
    ))
    fig1.update_layout(**PLOT_LAYOUT, height=250, showlegend=False)
    st.plotly_chart(fig1, width="stretch")

    # Discount Max distribution — histogram
    st.markdown("<div class='section-header'>Discount Range Distribution</div>", unsafe_allow_html=True)
    disc_df = filtered[filtered["discount_max"].notna()]
    fig2 = go.Figure()
    for brand in sel_brands:
        bdf = disc_df[disc_df["brand"] == brand]["discount_max"]
        if not bdf.empty:
            fig2.add_trace(go.Histogram(
                x=bdf, name=brand,
                marker_color=BRAND_COLORS.get(brand, "#aaa"),
                opacity=0.75, nbinsx=12,
            ))
    fig2.update_layout(
        **PLOT_LAYOUT, barmode="overlay", height=250,
        xaxis=dict(title="Discount Max (%)", gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(title="# Promos", gridcolor="rgba(255,255,255,0.05)"),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig2, width="stretch")

# ── User Type Analysis ────────────────────────────────────────────────
st.markdown("---")
st.markdown("<div class='section-header'>Who Are Promotions Targeting?</div>", unsafe_allow_html=True)
ut = filtered[filtered["user_type"].notna()].groupby(["brand", "user_type"]).size().reset_index(name="count")
if not ut.empty:
    fig3 = px.bar(
        ut, x="user_type", y="count", color="brand",
        barmode="group",
        color_discrete_map=BRAND_COLORS,
        labels={"user_type": "Target User Segment", "count": "Promotions", "brand": "Brand"},
    )
    fig3.update_layout(**PLOT_LAYOUT, height=320,
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    )
    st.plotly_chart(fig3, width="stretch")
