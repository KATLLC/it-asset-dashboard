import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests
from PIL import Image
from io import BytesIO

# ============================================================
# PAGE CONFIG - MOBILE OPTIMIZED
# ============================================================
st.set_page_config(
    page_title="KAT P&L Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- MOBILE CSS ENHANCEMENTS ---
st.markdown("""
<style>
    .main {background-color: #F4F7FB;}
    #MainMenu, footer, header {visibility: hidden;}
    
    /* Optimize padding for mobile */
    @media (max-width: 640px) {
        .block-container {
            padding-top: 1rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 18px !important;
        }
    }

    .row-label {
        color: #1B3A6B; font-size: 10px; font-weight: 700; text-transform: uppercase;
        letter-spacing: 2px; padding-left: 8px; border-left: 3px solid #3498DB;
        margin: 16px 0 10px 0; font-family: Arial, sans-serif;
    }
    hr {border-color: #E8ECF1; margin: 12px 0;}
</style>
""", unsafe_allow_html=True)

credentials = st.secrets["gcp_service_account"]
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(credentials, scopes=scope)
gc = gspread.authorize(creds)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1kLIT79DBtG13nlOEkvrWe0FauQVOLi9IxMcYbLpdWL4"
sh = gc.open_by_url(SHEET_URL)

@st.cache_data(ttl=600)
def get_data(name, h_row=4, d_row=6):
    try:
        ws = sh.worksheet(name)
        all_vals = ws.get_all_values()
        df = pd.DataFrame(all_vals[d_row-1:], columns=all_vals[h_row-1])
        return df.replace("", pd.NA).dropna(how="all").fillna("")
    except Exception as e:
        st.error(f"Error loading {name}: {e}")
        return pd.DataFrame()

df_proc   = get_data("PROCUREMENT")
df_landed = get_data("LANDED COST ANALYSIS")
df_sales  = get_data("SALES")
df_cap    = get_data("CAPITAL LOG", h_row=3, d_row=4)

def to_n(series):
    return pd.to_numeric(
        series.astype(str)
              .str.replace("$", "", regex=False)
              .str.replace(",", "", regex=False)
              .str.replace("%", "", regex=False)
              .str.strip(),
        errors="coerce"
    ).fillna(0)

def fmt(n):
    return f"${float(n):,.2f}"

def fmtp(n):
    return f"{float(n):.1f}%"

def safe_col(df, idx):
    return to_n(df.iloc[:, idx]) if len(df.columns) > idx else pd.Series([0] * max(len(df), 1))

def card_html(label, value, subtitle, color):
    return (
        "<div style='background:white;border-radius:12px;padding:16px 18px;"
        "box-shadow:0 2px 8px rgba(0,0,0,0.06);border-top:4px solid " + color + ";"
        "margin-bottom:12px;min-height:108px;'>"
        "<div style='color:#7F8C8D;font-size:10px;text-transform:uppercase;"
        "letter-spacing:1.5px;font-weight:600;margin-bottom:6px;"
        "font-family:Arial,sans-serif;'>" + label + "</div>"
        "<div style='font-size:18px;font-weight:700;color:" + color + ";"
        "margin-bottom:4px;font-family:Arial,sans-serif;line-height:1.25;'>" + value + "</div>"
        "<div style='color:#5D6D6E;font-size:10px;font-family:Arial,sans-serif;'>" + subtitle + "</div>"
        "</div>"
    )

def get_clr(val, target=0):
    return "#27AE60" if val >= target else "#E74C3C"

def threshold_clr(val, g=70, o=40):
    if val >= g:
        return "#27AE60"
    if val >= o:
        return "#F39C12"
    return "#E74C3C"

if not df_proc.empty:
    df_proc = df_proc[df_proc.iloc[:, 0].astype(str).str.strip() != ""]
    df_proc = df_proc[df_proc.iloc[:, 0].astype(str).str.upper() != "TOTALS"]

if not df_landed.empty:
    df_landed = df_landed[df_landed.iloc[:, 0].astype(str).str.strip() != ""]
    df_landed = df_landed[df_landed.iloc[:, 0].astype(str).str.upper() != "TOTALS"]
    df_landed = df_landed[
        ~df_landed.iloc[:, 0].astype(str).str.contains("From|Lot Number", na=False)
    ]

if not df_sales.empty and len(df_sales.columns) > 10:
    df_sales = df_sales[safe_col(df_sales, 10) > 0]

total_revenue  = safe_col(df_landed, 28).sum()
landed_cost    = safe_col(df_landed, 26).sum()
gross_profit   = safe_col(df_landed, 29).sum()
net_margin     = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
roi_pct        = (gross_profit / landed_cost * 100) if landed_cost > 0 else 0

net_capital_in = safe_col(df_cap, 4).sum()
if net_capital_in == 0:
    net_capital_in = 5110.00

proc_spend     = safe_col(df_proc, 16).sum()
avail_buying   = net_capital_in - proc_spend

total_units      = safe_col(df_landed, 4).sum()
avg_unit_cost    = landed_cost / total_units if total_units > 0 else 0
total_procured   = safe_col(df_proc, 6).sum()
total_sold       = safe_col(df_sales, 7).sum()
units_remaining  = total_procured - total_sold
stock_sold_pct   = (total_sold / total_procured * 100) if total_procured > 0 else 0
inv_turnover     = (total_sold / units_remaining) if units_remaining > 0 else 0
capital_at_risk  = units_remaining * avg_unit_cost
cash_recovery    = (total_revenue / net_capital_in * 100) if net_capital_in > 0 else 0
break_even       = (total_revenue / landed_cost * 100) if landed_cost > 0 else 0

c_purchase = safe_col(df_landed, 9).sum()
c_usa      = safe_col(df_landed, 10).sum() + safe_col(df_landed, 11).sum()
c_freight  = safe_col(df_landed, 16).sum()
c_duty     = safe_col(df_landed, 18).sum()
c_agent    = safe_col(df_landed, 20).sum()
c_local    = safe_col(df_landed, 22).sum()
c_other    = safe_col(df_landed, 24).sum()

c_rev    = get_clr(total_revenue)
c_profit = get_clr(gross_profit)
c_margin = get_clr(net_margin)
c_roi    = get_clr(roi_pct)
c_buy    = get_clr(avail_buying)
c_spend  = "#E67E22"
c_rec    = threshold_clr(cash_recovery, 50, 20)
c_be     = threshold_clr(break_even, 100, 50)
c_rem    = "#1B3A6B"
c_sold   = threshold_clr(stock_sold_pct, 70, 30)
c_turn   = threshold_clr(inv_turnover * 100, 100, 40)
c_risk   = "#1B3A6B"

now = datetime.now().strftime("%d %b %Y  %H:%M")

pct_budget_used  = (proc_spend / net_capital_in * 100) if net_capital_in > 0 else 0
pct_budget_avail = 100 - pct_budget_used
C_NAVY   = "#1B3A6B"
C_BLUE   = "#2471A3"
C_GREEN  = "#27AE60"
C_ORANGE = "#E67E22"
C_RED    = "#E74C3C"
C_PURPLE = "#9B59B6"
C_GREY   = "#95A5A6"

# ============================================================
# HEADER
# ============================================================
logo_col, title_col = st.columns([2, 0])

with logo_col:
    try:
        res = requests.get(
            "https://raw.githubusercontent.com/KATLLC/it-asset-dashboard/main/logo.png",
            timeout=5
        )
        if res.status_code == 200:
            st.image(Image.open(BytesIO(res.content)), width=160)
    except Exception:
        st.write("")

with title_col:
    st.markdown(
        f"""
        <div style="
            background:linear-gradient(135deg,#0F2B46 0%,#1B4F72 60%,#2471A3 100%);
            border-radius:14px;
            padding:18px 24px;
            display:flex;
            justify-content:space-between;
            align-items:center;
        ">
            <div>
                <div style="
                    color:white;
                    font-size:20px;
                    font-weight:700;
                    font-family:Arial,sans-serif;
                ">
                    📊 Key Asset Technologies
                </div>
                <div style="
                    color:rgba(255,255,255,0.60);
                    font-size:11px;
                    margin-top:4px;
                    font-family:Arial,sans-serif;
                ">
                    P&L Dashboard · Procurement → Shipment → Clearing → Sales · {now}
                </div>
            </div>
            <div style="
                background:rgba(255,255,255,0.12);
                border:1px solid rgba(255,255,255,0.25);
                border-radius:20px;
                padding:5px 14px;
                color:white;
                font-size:11px;
                font-weight:600;
                font-family:Arial,sans-serif;
            ">
                🟢 LIVE DATA
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================
# ROW 1 — THE BOTTOM LINE
# ============================================================
st.markdown('<div class="row-label">📈 The Bottom Line</div>', unsafe_allow_html=True)

r1a, r1b, r1c, r1d = st.columns(4)

with r1a:
    st.markdown(
        card_html("💰 Total Revenue", fmt(total_revenue), "Total sales recorded", c_rev),
        unsafe_allow_html=True
    )

with r1b:
    st.markdown(
        card_html("📈 Gross Profit", fmt(gross_profit), "Revenue minus landed cost", c_profit),
        unsafe_allow_html=True
    )

with r1c:
    st.markdown(
        card_html("🎯 Net Margin %", fmtp(net_margin), "Target > 25%", c_margin),
        unsafe_allow_html=True
    )

with r1d:
    st.markdown(
        card_html("🔄 ROI %", fmtp(roi_pct), "Target > 30%", c_roi),
        unsafe_allow_html=True
    )

# ============================================================
# ROW 2 — CASH POSITION
# ============================================================
st.markdown('<div class="row-label">💵 Cash Position</div>', unsafe_allow_html=True)

r2a, r2b, r2c, r2d = st.columns(4)

with r2a:
    st.markdown(
        card_html("✅ Buying Power", fmt(avail_buying), f"Of {fmt(net_capital_in)} capital", c_buy),
        unsafe_allow_html=True
    )

with r2b:
    st.markdown(
        card_html("🛒 Procurement Cost", fmt(proc_spend), "Spent on US auctions & prep", c_spend),
        unsafe_allow_html=True
    )

with r2c:
    st.markdown(
        card_html("💹 Cash Recovery", fmtp(cash_recovery), "Revenue / Capital In", c_rec),
        unsafe_allow_html=True
    )

with r2d:
    st.markdown(
        card_html("🎯 Break Even", fmtp(break_even), "100% = cost covered", c_be),
        unsafe_allow_html=True
    )

# ============================================================
# ROW 3 — STOCK HEALTH
# ============================================================
st.markdown('<div class="row-label">📦 Stock Health</div>', unsafe_allow_html=True)

r3a, r3b, r3c, r3d = st.columns(4)

with r3a:
    st.markdown(
        card_html(
            "🏭 Units Remaining",
            f"{int(units_remaining):,}",
            f"Out of {int(total_procured):,}",
            c_rem
        ),
        unsafe_allow_html=True
    )

with r3b:
    st.markdown(
        card_html(
            "📤 Stock Sold %",
            fmtp(stock_sold_pct),
            f"{int(total_sold):,} units sold",
            c_sold
        ),
        unsafe_allow_html=True
    )

with r3c:
    st.markdown(
        card_html(
            "🔄 Inventory Turnover",
            f"{inv_turnover:.2f}x",
            "Sold / Remaining",
            c_turn
        ),
        unsafe_allow_html=True
    )

with r3d:
    st.markdown(
        card_html(
            "📦 Inventory Value",
            fmt(capital_at_risk),
            "At landed cost",
            c_risk
        ),
        unsafe_allow_html=True
    )

# ============================================================
# THIN PROGRESS BARS
# ============================================================
st.markdown("---")
st.markdown('<div class="row-label">📊 Operational Progress</div>', unsafe_allow_html=True)

pb1, pb2 = st.columns(2)

with pb1:
    spent_w = max(min(float(pct_budget_used), 100), 0.5)
    avail_w = max(min(float(pct_budget_avail), 100), 0.5)

    components.html(
        f"""
        <div style="font-family:Arial,sans-serif;padding:4px 0;">
            <div style="
                display:flex;
                justify-content:space-between;
                font-size:11px;
                color:#6C7A89;
                margin-bottom:5px;
            ">
                <span>Capital Utilization (Procurement)</span>
                <span style="font-weight:700;color:#1B3A6B;">
                    {fmtp(spent_w)} used
                </span>
            </div>

            <div style="
                width:100%;
                height:10px;
                background:#EEF2F9;
                border-radius:999px;
                overflow:hidden;
                display:flex;
            ">
                <div style="
                    width:{spent_w}%;
                    height:10px;
                    background:linear-gradient(90deg,#E67E22,#D35400);
                "></div>
                <div style="
                    width:{avail_w}%;
                    height:10px;
                    background:linear-gradient(90deg,#27AE60,#1E8449);
                "></div>
            </div>

            <div style="
                display:flex;
                gap:16px;
                margin-top:6px;
                font-size:10px;
                color:#6C7A89;
            ">
                <span>🟠 Spent: {fmt(proc_spend)}</span>
                <span>🟢 Available: {fmt(avail_buying)}</span>
                <span>🔵 Total: {fmt(net_capital_in)}</span>
            </div>
        </div>
        """,
        height=70
    )

with pb2:
    sold_w = max(min(float(stock_sold_pct), 100), 0.5)
    remain_w = max(min(float(100 - stock_sold_pct), 100), 0.5)

    components.html(
        f"""
        <div style="font-family:Arial,sans-serif;padding:4px 0;">
            <div style="
                display:flex;
                justify-content:space-between;
                font-size:11px;
                color:#6C7A89;
                margin-bottom:5px;
            ">
                <span>Stock Movement</span>
                <span style="font-weight:700;color:#1B3A6B;">
                    {fmtp(sold_w)} sold
                </span>
            </div>

            <div style="
                width:100%;
                height:10px;
                background:#EEF2F9;
                border-radius:999px;
                overflow:hidden;
                display:flex;
            ">
                <div style="
                    width:{sold_w}%;
                    height:10px;
                    background:linear-gradient(90deg,#27AE60,#1E8449);
                "></div>
                <div style="
                    width:{remain_w}%;
                    height:10px;
                    background:linear-gradient(90deg,#E67E22,#D35400);
                "></div>
            </div>

            <div style="
                display:flex;
                gap:16px;
                margin-top:6px;
                font-size:10px;
                color:#6C7A89;
            ">
                <span>🟢 Sold: {int(total_sold):,} units</span>
                <span>🟠 Remaining: {int(units_remaining):,} units</span>
                <span>🔵 At Cost: {fmt(capital_at_risk)}</span>
            </div>
        </div>
        """,
        height=70
    )
    # ============================================================
# CHARTS
# ============================================================
st.markdown("---")

chart1, chart2 = st.columns(2)

with chart1:
    st.markdown(
        '<div class="row-label">💸 Cost Structure</div>',
        unsafe_allow_html=True
    )

    labels = [
        "Purchase", "USA Prep", "Freight",
        "Duty", "Agent", "Local", "Other"
    ]
    values = [
        c_purchase, c_usa, c_freight,
        c_duty, c_agent, c_local, c_other
    ]
    colors = [
        C_NAVY, C_BLUE, C_ORANGE,
        C_RED, C_PURPLE, C_GREEN, C_GREY
    ]

    nz = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
    if not nz:
        nz = [("Purchase", max(c_purchase, 1), C_NAVY)]

    fig_pie = go.Figure(go.Pie(
        labels=[x[0] for x in nz],
        values=[x[1] for x in nz],
        hole=0,
        marker=dict(
            colors=[x[2] for x in nz],
            line=dict(color="white", width=3)
        ),
        textinfo="percent+label",
        textfont=dict(size=11, color="white")
    ))

    fig_pie.update_layout(
        height=350,
        paper_bgcolor="white",
        showlegend=True,
        margin=dict(t=20, b=20, l=20, r=20),
        legend=dict(font=dict(size=10, color=C_NAVY))
    )

    st.plotly_chart(fig_pie, use_container_width=True)

with chart2:
    st.markdown(
        '<div class="row-label">🏗️ Landed Cost Build-up</div>',
        unsafe_allow_html=True
    )

    max_y = max(landed_cost * 1.4, 10)

    fig_wf = go.Figure(go.Waterfall(
        orientation="v",
        measure=[
            "relative", "relative", "relative",
            "relative", "relative", "relative", "total"
        ],
        x=[
            "Purchase", "USA Prep", "Freight",
            "Duty", "Agent", "Local", "TOTAL"
        ],
        y=[
            c_purchase, c_usa, c_freight,
            c_duty, c_agent, c_local, 0
        ],
        text=[
            fmt(c_purchase), fmt(c_usa), fmt(c_freight),
            fmt(c_duty), fmt(c_agent), fmt(c_local),
            fmt(landed_cost)
        ],
        textposition="outside",
        textfont=dict(size=10, color=C_NAVY),
        connector=dict(
            line=dict(color="#E8ECF1", width=1, dash="dot")
        ),
        increasing=dict(
            marker=dict(color="rgba(36,113,163,0.85)")
        ),
        decreasing=dict(
            marker=dict(color="rgba(231,76,60,0.85)")
        ),
        totals=dict(
            marker=dict(color="rgba(27,58,107,0.90)")
        )
    ))

    fig_wf.update_layout(
        height=350,
        paper_bgcolor="white",
        plot_bgcolor="#FAFBFD",
        showlegend=False,
        margin=dict(t=20, b=60, l=60, r=40),
        yaxis=dict(
            gridcolor=C_GREY,
            range=[0, max_y],
            tickfont=dict(size=9)
        ),
        xaxis=dict(tickfont=dict(size=9))
    )

    st.plotly_chart(fig_wf, use_container_width=True)

# ============================================================
# GAUGES
# ============================================================
st.markdown(
    '<div class="row-label">📊 Business Health Gauges</div>',
    unsafe_allow_html=True
)

fig_g = go.Figure()

fig_g.add_trace(go.Indicator(
    mode="gauge+number",
    value=float(stock_sold_pct),
    title={
        "text": (
            "<b>Stock Sold</b><br>"
            "<span style='font-size:11px;color:#7F8C8D;'>"
            + str(int(total_sold)) + " of "
            + str(int(total_procured)) + " units"
            + "</span>"
        ),
        "font": {"size": 13, "color": C_NAVY}
    },
    number={
        "suffix": "%",
        "font": {"size": 28, "color": C_NAVY}
    },
    gauge={
        "axis": {
            "range": [0, 100],
            "dtick": 25,
            "tickfont": {"size": 9, "color": C_GREY}
        },
        "bar": {"color": C_GREEN, "thickness": 0.3},
        "bgcolor": "#F0F3F8",
        "borderwidth": 0,
        "steps": [
            {"range": [0, 25], "color": "#FADBD8"},
            {"range": [25, 50], "color": "#FCF3CF"},
            {"range": [50, 75], "color": "#D5F5E3"},
            {"range": [75, 100], "color": "#ABEBC6"}
        ],
        "threshold": {
            "line": {"color": C_NAVY, "width": 2},
            "thickness": 0.75,
            "value": float(stock_sold_pct)
        }
    },
    domain={"x": [0.05, 0.45], "y": [0.05, 0.95]}
))

fig_g.add_trace(go.Indicator(
    mode="gauge+number",
    value=float(break_even),
    title={
        "text": (
            "<b>Break Even</b><br>"
            "<span style='font-size:11px;color:#7F8C8D;'>"
            "100% = break even"
            "</span>"
        ),
        "font": {"size": 13, "color": C_NAVY}
    },
    number={
        "suffix": "%",
        "font": {"size": 28, "color": C_BLUE}
    },
    gauge={
        "axis": {
            "range": [0, 150],
            "dtick": 25,
            "tickfont": {"size": 9, "color": C_GREY}
        },
        "bar": {"color": C_BLUE, "thickness": 0.3},
        "bgcolor": "#F0F3F8",
        "borderwidth": 0,
        "steps": [
            {"range": [0, 50], "color": "#FADBD8"},
            {"range": [50, 100], "color": "#FCF3CF"},
            {"range": [100, 150], "color": "#D5F5E3"}
        ],
        "threshold": {
            "line": {"color": C_GREEN, "width": 3},
            "thickness": 0.75,
            "value": 100
        }
    },
    domain={"x": [0.55, 0.95], "y": [0.05, 0.95]}
))

fig_g.update_layout(
    height=280,
    paper_bgcolor="white",
    margin=dict(t=40, b=20, l=30, r=30)
)

st.plotly_chart(fig_g, use_container_width=True)

# ============================================================
# LOT TABLE
# ============================================================
st.markdown("---")
st.markdown(
    '<div class="row-label">📋 Lot Detail — Full Breakdown</div>',
    unsafe_allow_html=True
)

if not df_landed.empty:
    col_indexes = [0, 1, 2, 4, 9, 17, 19, 26, 27, 28, 29, 31, 32]
    col_names = [
        "Lot Number", "Shipment", "Category", "Qty",
        "Purchase", "Freight", "Duty",
        "Total Landed", "Cost/Unit",
        "Revenue", "Profit", "Margin%", "ROI%"
    ]

    display_df = pd.DataFrame()
    for idx, name in zip(col_indexes, col_names):
        if len(df_landed.columns) > idx:
            display_df[name] = df_landed.iloc[:, idx]

    money_cols = [
        "Purchase", "Freight", "Duty",
        "Total Landed", "Cost/Unit",
        "Revenue", "Profit"
    ]
    pct_cols = ["Margin%", "ROI%"]

    for c in money_cols:
        if c in display_df.columns:
            display_df[c] = to_n(display_df[c]).map(fmt)

    for c in pct_cols:
        if c in display_df.columns:
            display_df[c] = to_n(display_df[c]).map(fmtp)

    display_df = display_df[
        display_df["Lot Number"].astype(str).str.strip() != ""
    ]
    display_df = display_df[
        display_df["Lot Number"].astype(str).str.upper() != "TOTALS"
    ]
    display_df = display_df[
        ~display_df["Lot Number"].astype(str).str.contains(
            "From|Lot Number", na=False
        )
    ]

    display_df = display_df.reset_index(drop=True)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=400
    )

else:
    st.info("No lot data available yet.")

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")

st.markdown(
    "<div style='"
    "text-align:center;"
    "color:#95A5A6;"
    "font-size:10px;"
    "padding:20px;"
    "font-family:Arial,sans-serif;"
    "'>📊 Key Asset Technologies P&L Dashboard · "
    "Connected Live to Google Sheets · "
    "Auto-refreshes every 10 minutes · "
    + now +
    "</div>",
    unsafe_allow_html=True
)
