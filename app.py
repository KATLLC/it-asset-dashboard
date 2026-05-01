import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests
from PIL import Image
from io import BytesIO

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="P&L Executive Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
    .main {background-color: #F4F7FB;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 1rem;}

    .row-label {
        color: #1B3A6B;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 2px;
        padding-left: 8px;
        border-left: 3px solid #3498DB;
        margin: 16px 0 10px 0;
        font-family: Arial, sans-serif;
    }

    hr {
        border-color: #E8ECF1;
        margin: 12px 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# AUTHENTICATION
# ============================================================
credentials = st.secrets["gcp_service_account"]
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(credentials, scopes=scope)
gc = gspread.authorize(creds)

# ============================================================
# LOAD GOOGLE SHEETS
# ============================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1kLIT79DBtG13nlOEkvrWe0FauQVOLi9IxMcYbLpdWL4"
sh = gc.open_by_url(SHEET_URL)

@st.cache_data(ttl=600)
def get_data(name, h_row=4, d_row=6):
    try:
        ws = sh.worksheet(name)
        all_vals = ws.get_all_values()
        headers = all_vals[h_row - 1]
        data = all_vals[d_row - 1:]
        df = pd.DataFrame(data, columns=headers)
        df = df.replace("", pd.NA).dropna(how="all").fillna("")
        return df
    except Exception as e:
        st.error(f"Error loading {name}: {e}")
        return pd.DataFrame()

df_proc   = get_data("PROCUREMENT")
df_landed = get_data("LANDED COST ANALYSIS")
df_sales  = get_data("SALES")
df_cap    = get_data("CAPITAL LOG", h_row=3, d_row=4)

# ============================================================
# HELPERS
# ============================================================
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
    try:
        return f"${float(n):,.2f}"
    except:
        return "$0.00"

def fmtp(n):
    try:
        return f"{float(n):.1f}%"
    except:
        return "0.0%"

def safe_col(df, idx):
    if len(df.columns) > idx:
        return to_n(df.iloc[:, idx])
    return pd.Series([0] * len(df))

def color_positive(value):
    try:
        return "#27AE60" if float(value) >= 0 else "#E74C3C"
    except:
        return "#1B3A6B"

def threshold_color(value, green=70, orange=40):
    try:
        v = float(value)
        if v >= green:
            return "#27AE60"
        elif v >= orange:
            return "#F39C12"
        return "#E74C3C"
    except:
        return "#1B3A6B"

def card_html(label, value, subtitle, color):
    return f"""
    <div style="
        background:white;
        border-radius:12px;
        padding:16px 18px;
        box-shadow:0 2px 8px rgba(0,0,0,0.06);
        border-top:4px solid {color};
        margin-bottom:12px;
        min-height:104px;
    ">
        <div style="
            color:#95A5A6;
            font-size:10px;
            text-transform:uppercase;
            letter-spacing:1.5px;
            font-weight:600;
            margin-bottom:6px;
            font-family:Arial,sans-serif;
        ">
            {label}
        </div>
        <div style="
            font-size:18px;
            font-weight:700;
            color:{color};
            margin-bottom:4px;
            font-family:Arial,sans-serif;
            line-height:1.2;
            word-break:break-word;
        ">
            {value}
        </div>
        <div style="
            color:#BDC3C7;
            font-size:10px;
            font-family:Arial,sans-serif;
        ">
            {subtitle}
        </div>
    </div>
    """

# ============================================================
# CLEAN DATA
# ============================================================
# PROCUREMENT
if not df_proc.empty:
    df_proc = df_proc[df_proc.iloc[:, 0].astype(str).str.strip() != ""]
    df_proc = df_proc[df_proc.iloc[:, 0].astype(str).str.upper() != "TOTALS"]

# LANDED
if not df_landed.empty:
    df_landed = df_landed[df_landed.iloc[:, 0].astype(str).str.strip() != ""]
    df_landed = df_landed[df_landed.iloc[:, 0].astype(str).str.upper() != "TOTALS"]
    df_landed = df_landed[
        ~df_landed.iloc[:, 0].astype(str).str.contains("From|Lot Number", na=False)
    ]

# SALES
if not df_sales.empty and len(df_sales.columns) > 10:
    sales_revenue = safe_col(df_sales, 10)
    df_sales = df_sales[sales_revenue > 0]

# ============================================================
# KPI CALCULATIONS
# ============================================================
# Bottom line
total_revenue = safe_col(df_landed, 28).sum()
landed_cost   = safe_col(df_landed, 26).sum()
gross_profit  = safe_col(df_landed, 29).sum()
net_margin    = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
roi_pct       = (gross_profit / landed_cost * 100) if landed_cost > 0 else 0

# Cash position
net_capital_in = safe_col(df_cap, 4).sum()
if net_capital_in == 0:
    net_capital_in = 5110.00

proc_spend       = safe_col(df_proc, 16).sum()
avail_buying     = net_capital_in - proc_spend

# Inventory
total_units      = safe_col(df_landed, 4).sum()
avg_unit_cost    = landed_cost / total_units if total_units > 0 else 0
total_procured   = safe_col(df_proc, 6).sum()
total_sold       = safe_col(df_sales, 7).sum()
units_remaining  = total_procured - total_sold
stock_sold_pct   = (total_sold / total_procured * 100) if total_procured > 0 else 0

capital_deployed = units_remaining * avg_unit_cost
cash_recovery    = (total_revenue / net_capital_in * 100) if net_capital_in > 0 else 0
break_even       = (total_revenue / landed_cost * 100) if landed_cost > 0 else 0

# Days in stock
try:
    proc_dates = pd.to_datetime(df_proc.iloc[:, 1].astype(str), errors="coerce").dropna()
    avg_days_in_stock = (pd.Timestamp.now() - proc_dates.min()).days if len(proc_dates) > 0 else 0
except Exception:
    avg_days_in_stock = 0

# Lot extremes
try:
    landed_per_unit_series = safe_col(df_landed, 27)
    max_idx = landed_per_unit_series.idxmax()
    min_idx = landed_per_unit_series.idxmin()
    highest_lot = str(df_landed.iloc[max_idx, 0])
    highest_val = float(landed_per_unit_series.loc[max_idx])
    lowest_lot  = str(df_landed.iloc[min_idx, 0])
    lowest_val  = float(landed_per_unit_series.loc[min_idx])
except Exception:
    highest_lot = "N/A"
    highest_val = 0
    lowest_lot = "N/A"
    lowest_val = 0

# Cost structure
cost_purchase = safe_col(df_landed, 9).sum()
cost_usa      = safe_col(df_landed, 10).sum() + safe_col(df_landed, 11).sum()
cost_freight  = safe_col(df_landed, 16).sum()
cost_duty     = safe_col(df_landed, 18).sum()
cost_agent    = safe_col(df_landed, 20).sum()
cost_local    = safe_col(df_landed, 22).sum()
cost_other    = safe_col(df_landed, 24).sum()

now = datetime.now().strftime("%d %b %Y  %H:%M")

# Colors
c1  = color_positive(total_revenue)
c2  = color_positive(gross_profit)
c3  = color_positive(net_margin)
c4  = color_positive(roi_pct)
c5  = color_positive(avail_buying)
c6  = "#E74C3C" if capital_deployed > net_capital_in * 0.7 else "#F39C12"
c7  = threshold_color(cash_recovery, green=50, orange=20)
c8  = threshold_color(break_even, green=100, orange=50)
c9  = "#27AE60" if units_remaining < total_procured * 0.5 else "#F39C12"
c10 = threshold_color(stock_sold_pct, green=70, orange=30)
c11 = "#27AE60" if avg_days_in_stock < 45 else "#F39C12" if avg_days_in_stock < 90 else "#E74C3C"
c12 = "#1B3A6B"

C_NAVY   = "#1B3A6B"
C_BLUE   = "#2471A3"
C_GREEN  = "#27AE60"
C_ORANGE = "#E67E22"
C_RED    = "#E74C3C"
C_PURPLE = "#9B59B6"
C_GREY   = "#95A5A6"

# ============================================================
# HEADER WITH LOGO
# ============================================================
logo_col, title_col = st.columns([1, 7])

with logo_col:
    try:
        logo_url = "https://raw.githubusercontent.com/KATLLC/it-asset-dashboard/main/logo.png"
        response = requests.get(logo_url, timeout=5)
        if response.status_code == 200:
            logo_img = Image.open(BytesIO(response.content))
            st.image(logo_img, width=300)
    except Exception:
        st.write("")

with title_col:
    st.markdown(f"""
    <div style="
        background:linear-gradient(135deg,#0F2B46 0%,#1B4F72 60%,#2471A3 100%);
        border-radius:14px;
        padding:18px 24px;
        display:flex;
        justify-content:space-between;
        align-items:center;
    ">
        <div>
            <div style="color:white;font-size:20px;font-weight:700;font-family:Arial,sans-serif;">
                📊 P&L Executive Dashboard
            </div>
            <div style="color:rgba(255,255,255,0.55);font-size:11px;margin-top:4px;font-family:Arial,sans-serif;">
                IT Asset Trading &nbsp;·&nbsp;
                Procurement → Shipment → Clearing → Sales
                &nbsp;·&nbsp; {now}
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
    """, unsafe_allow_html=True)

# ============================================================
# ROW 1 — THE BOTTOM LINE
# ============================================================
st.markdown('<div class="row-label">📈 The Bottom Line</div>', unsafe_allow_html=True)
r1c1, r1c2, r1c3, r1c4 = st.columns(4)

with r1c1:
    st.markdown(card_html("💰 Total Revenue", fmt(total_revenue), "All sales recorded", c1), unsafe_allow_html=True)
with r1c2:
    st.markdown(card_html("📈 Gross Profit", fmt(gross_profit), "Revenue minus landed cost", c2), unsafe_allow_html=True)
with r1c3:
    st.markdown(card_html("🎯 Net Margin %", fmtp(net_margin), "Target > 25%", c3), unsafe_allow_html=True)
with r1c4:
    st.markdown(card_html("🔄 ROI %", fmtp(roi_pct), "Target > 30%", c4), unsafe_allow_html=True)

# ============================================================
# ROW 2 — CASH POSITION
# ============================================================
st.markdown('<div class="row-label">💵 Cash Position</div>', unsafe_allow_html=True)
r2c1, r2c2, r2c3, r2c4 = st.columns(4)

with r2c1:
    st.markdown(card_html("✅ Available Buying Power", fmt(avail_buying), f"Of {fmt(net_capital_in)} total capital", c5), unsafe_allow_html=True)
with r2c2:
    st.markdown(card_html("🔒 Capital Deployed", fmt(capital_deployed), "Locked in unsold stock", c6), unsafe_allow_html=True)
with r2c3:
    st.markdown(card_html("💹 Cash Recovery Rate", fmtp(cash_recovery), "Revenue / Net Capital In", c7), unsafe_allow_html=True)
with r2c4:
    st.markdown(card_html("🎯 Break Even Progress", fmtp(break_even), "100% = break even", c8), unsafe_allow_html=True)

# ============================================================
# ROW 3 — STOCK HEALTH
# ============================================================
st.markdown('<div class="row-label">📦 Stock Health</div>', unsafe_allow_html=True)
r3c1, r3c2, r3c3, r3c4 = st.columns(4)

days_text = "Good" if avg_days_in_stock < 45 else "Aging" if avg_days_in_stock < 90 else "Action needed"

with r3c1:
    st.markdown(card_html("🏭 Units Remaining", f"{int(units_remaining):,}", f"Of {int(total_procured):,} procured", c9), unsafe_allow_html=True)
with r3c2:
    st.markdown(card_html("📤 Stock Sold %", fmtp(stock_sold_pct), f"Target > 70% | {int(total_sold):,} sold", c10), unsafe_allow_html=True)
with r3c3:
    st.markdown(card_html("📅 Avg Days in Stock", f"{avg_days_in_stock} days", days_text, c11), unsafe_allow_html=True)
with r3c4:
    st.markdown(card_html("🔢 Landed Cost / Unit", fmt(avg_unit_cost), "True cost per unit", c12), unsafe_allow_html=True)

# ============================================================
# BUYING POWER BAR
# ============================================================
st.markdown("---")
st.markdown('<div class="row-label">💵 Auction Buying Power</div>', unsafe_allow_html=True)

pct_available = (avail_buying / net_capital_in * 100) if net_capital_in > 0 else 0
pct_spent     = 100 - pct_available

spent_display = max(pct_spent, 1)
avail_display = max(pct_available, 1)

st.markdown(f"""
<div style="
    background:white;
    border-radius:12px;
    padding:16px 18px;
    box-shadow:0 2px 8px rgba(0,0,0,0.06);
    margin-bottom:12px;
">
    <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
        <span style="color:#7F8C8D;font-size:11px;font-weight:600;font-family:Arial,sans-serif;">
            Budget Utilization
        </span>
        <span style="color:#1B3A6B;font-size:11px;font-weight:700;font-family:Arial,sans-serif;">
            {fmtp(pct_spent)} deployed | {fmtp(pct_available)} available
        </span>
    </div>

    <div style="display:flex;height:14px;border-radius:8px;overflow:hidden;">
        <div style="width:{spent_display:.1f}%;background:linear-gradient(90deg,#E67E22,#D35400);"></div>
        <div style="width:{avail_display:.1f}%;background:linear-gradient(90deg,#27AE60,#1E8449);"></div>
    </div>

    <div style="display:flex;gap:20px;margin-top:8px;">
        <div style="display:flex;align-items:center;gap:5px;font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;">
            <div style="width:8px;height:8px;border-radius:50%;background:#E67E22;"></div>
            Spent: {fmt(proc_spend)}
        </div>
        <div style="display:flex;align-items:center;gap:5px;font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;">
            <div style="width:8px;height:8px;border-radius:50%;background:#27AE60;"></div>
            Available: {fmt(avail_buying)}
        </div>
        <div style="display:flex;align-items:center;gap:5px;font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;">
            <div style="width:8px;height:8px;border-radius:50%;background:#1B3A6B;"></div>
            Total Capital: {fmt(net_capital_in)}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# INVENTORY PIPELINE BAR
# ============================================================
st.markdown('<div class="row-label">📦 Inventory Pipeline</div>', unsafe_allow_html=True)

sold_display = max(stock_sold_pct, 1)
remain_display = max(100 - stock_sold_pct, 1)

st.markdown(f"""
<div style="
    background:white;
    border-radius:12px;
    padding:16px 18px;
    box-shadow:0 2px 8px rgba(0,0,0,0.06);
    margin-bottom:12px;
">
    <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
        <span style="color:#7F8C8D;font-size:11px;font-weight:600;font-family:Arial,sans-serif;">
            Stock Movement
        </span>
        <span style="color:#1B3A6B;font-size:11px;font-weight:700;font-family:Arial,sans-serif;">
            {fmtp(stock_sold_pct)} sold
        </span>
    </div>

    <div style="display:flex;height:14px;border-radius:8px;overflow:hidden;">
        <div style="width:{sold_display:.1f}%;background:linear-gradient(90deg,#27AE60,#1E8449);"></div>
        <div style="width:{remain_display:.1f}%;background:linear-gradient(90deg,#E67E22,#D35400);"></div>
    </div>

    <div style="display:flex;gap:20px;margin-top:8px;">
        <div style="display:flex;align-items:center;gap:5px;font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;">
            <div style="width:8px;height:8px;border-radius:50%;background:#27AE60;"></div>
            Sold: {int(total_sold):,} units
        </div>
        <div style="display:flex;align-items:center;gap:5px;font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;">
            <div style="width:8px;height:8px;border-radius:50%;background:#E67E22;"></div>
            Remaining: {int(units_remaining):,} units ({fmt(capital_deployed)} at cost)
        </div>
        <div style="display:flex;align-items:center;gap:5px;font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;">
            <div style="width:8px;height:8px;border-radius:50%;background:#1B3A6B;"></div>
            Total: {int(total_procured):,} units
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# CHARTS
# ============================================================
st.markdown("---")
chart1, chart2 = st.columns(2)

with chart1:
    st.markdown('<div class="row-label">💸 Cost Structure</div>', unsafe_allow_html=True)

    labels = ["Purchase", "USA Costs", "Freight", "Customs Duty", "Agent Fee", "Local Transport", "Other"]
    values = [cost_purchase, cost_usa, cost_freight, cost_duty, cost_agent, cost_local, cost_other]
    colors = [C_NAVY, C_BLUE, C_ORANGE, C_RED, C_PURPLE, C_GREEN, C_GREY]

    nz = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
    if not nz:
        nz = [("Purchase", max(cost_purchase, 1), C_NAVY)]

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
        height=320,
        paper_bgcolor="white",
        showlegend=True,
        margin=dict(t=20, b=20, l=20, r=20),
        legend=dict(font=dict(size=10, color=C_NAVY))
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with chart2:
    st.markdown('<div class="row-label">🏗️ How Cost Builds Up</div>', unsafe_allow_html=True)

    max_y = max(landed_cost * 1.4, 10)

    fig_wf = go.Figure(go.Waterfall(
        orientation="v",
        measure=["relative", "relative", "relative", "relative", "relative", "relative", "total"],
        x=["Purchase", "USA Prep", "Freight", "Duty", "Agent Fees", "Local Trans", "TOTAL LANDED"],
        y=[cost_purchase, cost_usa, cost_freight, cost_duty, cost_agent, cost_local, 0],
        text=[fmt(cost_purchase), fmt(cost_usa), fmt(cost_freight), fmt(cost_duty), fmt(cost_agent), fmt(cost_local), fmt(landed_cost)],
        textposition="outside",
        textfont=dict(size=10, color=C_NAVY),
        connector=dict(line=dict(color="#E8ECF1", width=1, dash="dot")),
        increasing=dict(marker=dict(color="rgba(36,113,163,0.85)")),
        decreasing=dict(marker=dict(color="rgba(231,76,60,0.85)")),
        totals=dict(marker=dict(color="rgba(27,58,107,0.90)"))
    ))
    fig_wf.update_layout(
        height=320,
        paper_bgcolor="white",
        plot_bgcolor="#FAFBFD",
        showlegend=False,
        margin=dict(t=20, b=60, l=60, r=40),
        yaxis=dict(gridcolor=C_GREY, range=[0, max_y], tickfont=dict(size=9)),
        xaxis=dict(tickfont=dict(size=9))
    )
    st.plotly_chart(fig_wf, use_container_width=True)

# ============================================================
# GAUGES
# ============================================================
st.markdown('<div class="row-label">📊 Business Health Gauges</div>', unsafe_allow_html=True)

capital_risk = (units_remaining / total_procured * 100) if total_procured > 0 else 100

fig_g = go.Figure()

fig_g.add_trace(go.Indicator(
    mode="gauge+number",
    value=float(stock_sold_pct),
    title={
        "text": f"<b>Stock Sold</b><br><span style='font-size:11px;color:#7F8C8D;'>{int(total_sold):,} of {int(total_procured):,} units</span>",
        "font": {"size": 13, "color": C_NAVY}
    },
    number={"suffix": "%", "font": {"size": 28, "color": C_NAVY}},
    gauge={
        "axis": {"range": [0, 100], "dtick": 25, "tickfont": {"size": 9, "color": C_GREY}},
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
        "text": "<b>Break Even Progress</b><br><span style='font-size:11px;color:#7F8C8D;'>100% = break even</span>",
        "font": {"size": 13, "color": C_NAVY}
    },
    number={"suffix": "%", "font": {"size": 28, "color": C_BLUE}},
    gauge={
        "axis": {"range": [0, 150], "dtick": 25, "tickfont": {"size": 9, "color": C_GREY}},
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
# LOT DETAIL TABLE
# ============================================================
st.markdown("---")
st.markdown('<div class="row-label">📋 Lot Detail — Full Breakdown</div>', unsafe_allow_html=True)

if not df_landed.empty:
    col_indexes = [0, 1, 2, 4, 9, 17, 19, 26, 27, 28, 29, 31, 32]
    col_names = ["Lot", "Shipment", "Category", "Qty", "Purchase", "Freight", "Duty", "Total Landed", "$/Unit", "Revenue", "Profit", "Margin%", "ROI%"]

    display_df = pd.DataFrame()
    for idx, name in zip(col_indexes, col_names):
        if len(df_landed.columns) > idx:
            display_df[name] = df_landed.iloc[:, idx]

    money_cols = ["Purchase", "Freight", "Duty", "Total Landed", "$/Unit", "Revenue", "Profit"]
    pct_cols = ["Margin%", "ROI%"]

    for c in money_cols:
        if c in display_df.columns:
            display_df[c] = to_n(display_df[c]).map(lambda x: fmt(x))
    for c in pct_cols:
        if c in display_df.columns:
            display_df[c] = to_n(display_df[c]).map(lambda x: fmtp(x))

    display_df = display_df[
        display_df["Lot"].astype(str).str.strip() != ""
    ]
    display_df = display_df[
        display_df["Lot"].astype(str).str.upper() != "TOTALS"
    ]

    st.dataframe(display_df, use_container_width=True)

else:
    st.info("No lot data available yet.")

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown(f"""
<div style="
    text-align:center;
    color:#95A5A6;
    font-size:11px;
    padding:10px;
    font-family:Arial,sans-serif;
">
    📊 IT Asset Trading P&L Dashboard &nbsp;·&nbsp;
    Connected Live to Google Sheets &nbsp;·&nbsp;
    Auto-refreshes every 10 minutes &nbsp;·&nbsp;
    {now}
</div>
""", unsafe_allow_html=True)
