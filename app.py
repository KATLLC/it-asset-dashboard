import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests
from PIL import Image
from io import BytesIO

st.set_page_config(
    page_title="P&L Executive Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
    hr {border-color: #E8ECF1; margin: 12px 0;}
    [data-testid="metric-container"] {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        border-top: 4px solid #1B3A6B;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    [data-testid="metric-container"] label {
        color: #7F8C8D !important;
        font-size: 12px !important;
    }
    [data-testid="metric-container"] [data-testid="metric-value"] {
        color: #1B3A6B !important;
        font-size: 20px !important;
        font-weight: 700 !important;
    }
    [data-testid="stProgress"] > div > div > div {
        height: 14px !important;
        border-radius: 8px !important;
    }
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
        headers = all_vals[h_row - 1]
        data = all_vals[d_row - 1:]
        df = pd.DataFrame(data, columns=headers)
        df = df.replace("", pd.NA).dropna(how="all").fillna("")
        return df
    except Exception as e:
        st.error(f"Error loading {name}: {e}")
        return pd.DataFrame()

df_proc = get_data("PROCUREMENT")
df_landed = get_data("LANDED COST ANALYSIS")
df_sales = get_data("SALES")
df_cap = get_data("CAPITAL LOG", h_row=3, d_row=4)

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

def card_html(label, value, sub, color):
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
            color:#7F8C8D;
            font-size:10px;
            text-transform:uppercase;
            letter-spacing:1.5px;
            font-weight:600;
            margin-bottom:6px;
            font-family:Arial,sans-serif;
        ">{label}</div>
        <div style="
            font-size:18px;
            font-weight:700;
            color:{color};
            margin-bottom:4px;
            font-family:Arial,sans-serif;
            line-height:1.2;
            word-break:break-word;
        ">{value}</div>
        <div style="
            color:#7F8C8D;
            font-size:10px;
            font-family:Arial,sans-serif;
        ">{sub}</div>
    </div>
    """

# Clean data
if not df_proc.empty:
    df_proc = df_proc[df_proc.iloc[:, 0].astype(str).str.strip() != ""]
    df_proc = df_proc[df_proc.iloc[:, 0].astype(str).str.upper() != "TOTALS"]

if not df_landed.empty:
    df_landed = df_landed[df_landed.iloc[:, 0].astype(str).str.strip() != ""]
    df_landed = df_landed[df_landed.iloc[:, 0].astype(str).str.upper() != "TOTALS"]
    df_landed = df_landed[~df_landed.iloc[:, 0].astype(str).str.contains("From|Lot Number", na=False)]

if not df_sales.empty and len(df_sales.columns) > 10:
    df_sales = df_sales[safe_col(df_sales, 10) > 0]

# KPIs
total_revenue = safe_col(df_landed, 28).sum()
landed_cost = safe_col(df_landed, 26).sum()
gross_profit = safe_col(df_landed, 29).sum()
net_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
roi_pct = (gross_profit / landed_cost * 100) if landed_cost > 0 else 0

net_capital_in = safe_col(df_cap, 4).sum()
if net_capital_in == 0:
    net_capital_in = 5110.00

proc_spend = safe_col(df_proc, 16).sum()
avail_buying = net_capital_in - proc_spend

total_units = safe_col(df_landed, 4).sum()
avg_unit_cost = landed_cost / total_units if total_units > 0 else 0
total_procured = safe_col(df_proc, 6).sum()
total_sold = safe_col(df_sales, 7).sum()
units_remaining = total_procured - total_sold
stock_sold_pct = (total_sold / total_procured * 100) if total_procured > 0 else 0

capital_deployed = units_remaining * avg_unit_cost
cash_recovery = (total_revenue / net_capital_in * 100) if net_capital_in > 0 else 0
break_even = (total_revenue / landed_cost * 100) if landed_cost > 0 else 0

try:
    proc_dates = pd.to_datetime(df_proc.iloc[:, 1].astype(str), errors="coerce").dropna()
    avg_days = (pd.Timestamp.now() - proc_dates.min()).days if len(proc_dates) > 0 else 0
except:
    avg_days = 0

cost_purchase = safe_col(df_landed, 9).sum()
cost_usa = safe_col(df_landed, 10).sum() + safe_col(df_landed, 11).sum()
cost_freight = safe_col(df_landed, 16).sum()
cost_duty = safe_col(df_landed, 18).sum()
cost_agent = safe_col(df_landed, 20).sum()
cost_local = safe_col(df_landed, 22).sum()
cost_other = safe_col(df_landed, 24).sum()

now = datetime.now().strftime("%d %b %Y  %H:%M")

def clr(n):
    try:
        return "#27AE60" if float(n) >= 0 else "#E74C3C"
    except:
        return "#1B3A6B"

def wclr(n, g=70, o=40):
    try:
        v = float(n)
        if v >= g: return "#27AE60"
        elif v >= o: return "#F39C12"
        return "#E74C3C"
    except:
        return "#1B3A6B"

c1 = clr(total_revenue)
c2 = clr(gross_profit)
c3 = clr(net_margin)
c4 = clr(roi_pct)
c5 = clr(avail_buying)
c6 = "#E74C3C" if capital_deployed > net_capital_in * 0.7 else "#F39C12"
c7 = wclr(cash_recovery, g=50, o=20)
c8 = wclr(break_even, g=100, o=50)
c9 = "#27AE60" if units_remaining < total_procured * 0.5 else "#F39C12"
c10 = wclr(stock_sold_pct, g=70, o=30)
c11 = "#27AE60" if avg_days < 45 else "#F39C12" if avg_days < 90 else "#E74C3C"
c12 = "#1B3A6B"

C_NAVY = "#1B3A6B"
C_BLUE = "#2471A3"
C_GREEN = "#27AE60"
C_ORANGE = "#E67E22"
C_RED = "#E74C3C"
C_PURPLE = "#9B59B6"
C_GREY = "#95A5A6"

# ============================================================
# HEADER
# ============================================================
logo_col, title_col = st.columns([1, 7])

with logo_col:
    try:
        logo_url = "https://raw.githubusercontent.com/KATLLC/it-asset-dashboard/main/logo.png"
        response = requests.get(logo_url, timeout=5)
        if response.status_code == 200:
            st.image(Image.open(BytesIO(response.content)), width=350)
    except:
        pass

with title_col:
    st.markdown(f"""
    <div style="
        background:linear-gradient(135deg,#0F2B46 0%,#1B4F72 60%,#2471A3 100%);
        border-radius:14px;padding:18px 24px;
        display:flex;justify-content:space-between;align-items:center;
    ">
        <div>
            <div style="color:white;font-size:20px;font-weight:700;font-family:Arial;">
                📊 P&L Executive Dashboard
            </div>
            <div style="color:rgba(255,255,255,0.55);font-size:11px;margin-top:4px;font-family:Arial;">
                IT Asset Trading · Procurement → Shipment → Clearing → Sales · {now}
            </div>
        </div>
        <div style="background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.25);
                     border-radius:20px;padding:5px 14px;color:white;font-size:11px;font-weight:600;">
            🟢 LIVE DATA
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# ROW 1 — THE BOTTOM LINE
# ============================================================
st.markdown('<div class="row-label">📈 The Bottom Line</div>', unsafe_allow_html=True)
r1a, r1b, r1c, r1d = st.columns(4)
with r1a:
    st.markdown(card_html("💰 Total Revenue", fmt(total_revenue), "All sales recorded", c1), unsafe_allow_html=True)
with r1b:
    st.markdown(card_html("📈 Gross Profit", fmt(gross_profit), "Revenue minus landed cost", c2), unsafe_allow_html=True)
with r1c:
    st.markdown(card_html("🎯 Net Margin %", fmtp(net_margin), "Target above 25%", c3), unsafe_allow_html=True)
with r1d:
    st.markdown(card_html("🔄 ROI %", fmtp(roi_pct), "Target above 30%", c4), unsafe_allow_html=True)

# ============================================================
# ROW 2 — CASH POSITION
# ============================================================
st.markdown('<div class="row-label">💵 Cash Position</div>', unsafe_allow_html=True)
r2a, r2b, r2c, r2d = st.columns(4)
with r2a:
    st.markdown(card_html("✅ Buying Power", fmt(avail_buying), f"Of {fmt(net_capital_in)} total capital", c5), unsafe_allow_html=True)
with r2b:
    st.markdown(card_html("🔒 Capital Deployed", fmt(capital_deployed), "Locked in unsold stock", c6), unsafe_allow_html=True)
with r2c:
    st.markdown(card_html("💹 Cash Recovery", fmtp(cash_recovery), "Revenue / Capital In", c7), unsafe_allow_html=True)
with r2d:
    st.markdown(card_html("🎯 Break Even", fmtp(break_even), "100% means break even", c8), unsafe_allow_html=True)

# ============================================================
# ROW 3 — STOCK HEALTH
# ============================================================
st.markdown('<div class="row-label">📦 Stock Health</div>', unsafe_allow_html=True)
days_text = "Good" if avg_days < 45 else "Aging" if avg_days < 90 else "Action needed"
r3a, r3b, r3c, r3d = st.columns(4)
with r3a:
    st.markdown(card_html("🏭 Units Remaining", f"{int(units_remaining):,}", f"Of {int(total_procured):,} procured", c9), unsafe_allow_html=True)
with r3b:
    st.markdown(card_html("📤 Stock Sold %", fmtp(stock_sold_pct), f"Target above 70% | {int(total_sold):,} sold", c10), unsafe_allow_html=True)
with r3c:
    st.markdown(card_html("📅 Days in Stock", f"{avg_days} days", days_text, c11), unsafe_allow_html=True)
with r3d:
    st.markdown(card_html("🔢 Cost Per Unit", fmt(avg_unit_cost), "True landed cost per unit", c12), unsafe_allow_html=True)

# ============================================================
# BUYING POWER BAR (using Streamlit native)
# ============================================================
st.markdown("---")
st.markdown('<div class="row-label">💵 Auction Buying Power</div>', unsafe_allow_html=True)

pct_budget_used = (proc_spend / net_capital_in * 100) if net_capital_in > 0 else 0
pct_budget_avail = 100 - pct_budget_used

bp1, bp2, bp3 = st.columns(3)
bp1.metric("💼 Total Capital", fmt(net_capital_in))
bp2.metric("🛒 Spent", fmt(proc_spend), f"{fmtp(pct_budget_used)} used")
bp3.metric("✅ Available", fmt(avail_buying), f"{fmtp(pct_budget_avail)} free")

st.progress(min(pct_budget_used / 100, 1.0))
st.caption(f"Budget Utilization: {fmtp(pct_budget_used)} deployed | {fmtp(pct_budget_avail)} available")

# ============================================================
# INVENTORY PIPELINE (using Streamlit native)
# ============================================================
st.markdown("---")
st.markdown('<div class="row-label">📦 Inventory Pipeline</div>', unsafe_allow_html=True)

inv1, inv2, inv3 = st.columns(3)
inv1.metric("📥 Procured", f"{int(total_procured):,}")
inv2.metric("📤 Sold", f"{int(total_sold):,}", f"{fmtp(stock_sold_pct)} of stock")
inv3.metric("🏭 Remaining", f"{int(units_remaining):,}", f"{fmt(capital_deployed)} at cost")

st.progress(min(stock_sold_pct / 100, 1.0))
st.caption(f"Stock Movement: {fmtp(stock_sold_pct)} sold | {int(total_sold):,} units sold | {int(units_remaining):,} remaining")

# ============================================================
# CHARTS
# ============================================================
st.markdown("---")
ch1, ch2 = st.columns(2)

with ch1:
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
        marker=dict(colors=[x[2] for x in nz], line=dict(color="white", width=3)),
        textinfo="percent+label",
        textfont=dict(size=11, color="white")
    ))
    fig_pie.update_layout(height=320, paper_bgcolor="white", showlegend=True, margin=dict(t=20, b=20, l=20, r=20), legend=dict(font=dict(size=10, color=C_NAVY)))
    st.plotly_chart(fig_pie, use_container_width=True)

with ch2:
    st.markdown('<div class="row-label">🏗️ How Cost Builds Up</div>', unsafe_allow_html=True)
    max_y = max(landed_cost * 1.4, 10)
    fig_wf = go.Figure(go.Waterfall(
        orientation="v",
        measure=["relative", "relative", "relative", "relative", "relative", "relative", "total"],
        x=["Purchase", "USA Prep", "Freight", "Duty", "Agent", "Local", "TOTAL"],
        y=[cost_purchase, cost_usa, cost_freight, cost_duty, cost_agent, cost_local, 0],
        text=[fmt(cost_purchase), fmt(cost_usa), fmt(cost_freight), fmt(cost_duty), fmt(cost_agent), fmt(cost_local), fmt(landed_cost)],
        textposition="outside",
        textfont=dict(size=10, color=C_NAVY),
        connector=dict(line=dict(color="#E8ECF1", width=1, dash="dot")),
        increasing=dict(marker=dict(color="rgba(36,113,163,0.85)")),
        decreasing=dict(marker=dict(color="rgba(231,76,60,0.85)")),
        totals=dict(marker=dict(color="rgba(27,58,107,0.90)"))
    ))
    fig_wf.update_layout(height=320, paper_bgcolor="white", plot_bgcolor="#FAFBFD", showlegend=False, margin=dict(t=20, b=60, l=60, r=40), yaxis=dict(gridcolor=C_GREY, range=[0, max_y], tickfont=dict(size=9)), xaxis=dict(tickfont=dict(size=9)))
    st.plotly_chart(fig_wf, use_container_width=True)

# ============================================================
# GAUGES
# ============================================================
st.markdown('<div class="row-label">📊 Business Health Gauges</div>', unsafe_allow_html=True)
fig_g = go.Figure()
fig_g.add_trace(go.Indicator(
    mode="gauge+number", value=float(stock_sold_pct),
    title={"text": f"<b>Stock Sold</b><br><span style='font-size:11px;color:#7F8C8D;'>{int(total_sold):,} of {int(total_procured):,} units</span>", "font": {"size": 13, "color": C_NAVY}},
    number={"suffix": "%", "font": {"size": 28, "color": C_NAVY}},
    gauge={"axis": {"range": [0, 100], "dtick": 25, "tickfont": {"size": 9, "color": C_GREY}}, "bar": {"color": C_GREEN, "thickness": 0.3}, "bgcolor": "#F0F3F8", "borderwidth": 0, "steps": [{"range": [0, 25], "color": "#FADBD8"}, {"range": [25, 50], "color": "#FCF3CF"}, {"range": [50, 75], "color": "#D5F5E3"}, {"range": [75, 100], "color": "#ABEBC6"}], "threshold": {"line": {"color": C_NAVY, "width": 2}, "thickness": 0.75, "value": float(stock_sold_pct)}},
    domain={"x": [0.05, 0.45], "y": [0.05, 0.95]}
))
fig_g.add_trace(go.Indicator(
    mode="gauge+number", value=float(break_even),
    title={"text": "<b>Break Even</b><br><span style='font-size:11px;color:#7F8C8D;'>100% = break even</span>", "font": {"size": 13, "color": C_NAVY}},
    number={"suffix": "%", "font": {"size": 28, "color": C_BLUE}},
    gauge={"axis": {"range": [0, 150], "dtick": 25, "tickfont": {"size": 9, "color": C_GREY}}, "bar": {"color": C_BLUE, "thickness": 0.3}, "bgcolor": "#F0F3F8", "borderwidth": 0, "steps": [{"range": [0, 50], "color": "#FADBD8"}, {"range": [50, 100], "color": "#FCF3CF"}, {"range": [100, 150], "color": "#D5F5E3"}], "threshold": {"line": {"color": C_GREEN, "width": 3}, "thickness": 0.75, "value": 100}},
    domain={"x": [0.55, 0.95], "y": [0.05, 0.95]}
))
fig_g.update_layout(height=280, paper_bgcolor="white", margin=dict(t=40, b=20, l=30, r=30))
st.plotly_chart(fig_g, use_container_width=True)

# ============================================================
# LOT TABLE
# ============================================================
st.markdown("---")
st.markdown('<div class="row-label">📋 Lot Detail</div>', unsafe_allow_html=True)

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
    display_df = display_df[display_df["Lot"].astype(str).str.strip() != ""]
    display_df = display_df[display_df["Lot"].astype(str).str.upper() != "TOTALS"]
    st.dataframe(display_df, use_container_width=True)
else:
    st.info("No lot data available yet.")

st.markdown("---")
st.markdown(f"""
<div style="text-align:center;color:#95A5A6;font-size:11px;padding:10px;font-family:Arial;">
    📊 IT Asset Trading P&L Dashboard · Connected Live to Google Sheets · Auto-refreshes every 10 minutes · {now}
</div>
""", unsafe_allow_html=True)
