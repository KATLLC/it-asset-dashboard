import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import requests
from PIL import Image
from io import BytesIO

# ============================================================
#  PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title = "P&L Executive Dashboard",
    page_icon  = "📊",
    layout     = "wide",
    initial_sidebar_state = "collapsed"
)

# ============================================================
#  CUSTOM CSS
# ============================================================
st.markdown("""
<style>
  .main { background-color: #F4F7FB; }
  #MainMenu {visibility: hidden;}
  footer {visibility: hidden;}
  header {visibility: hidden;}
  .block-container {padding-top: 1rem;}

  /* KPI card base */
  .kpi-card {
    background: white;
    border-radius: 12px;
    padding: 16px 18px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border-top: 4px solid #1B3A6B;
    margin-bottom: 12px;
    min-height: 120px;
  }
  .kpi-label {
    color: #95A5A6;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 600;
    margin-bottom: 6px;
    font-family: Arial, sans-serif;
  }
  .kpi-value {
    font-size: 20px;
    font-weight: 700;
    color: #1B3A6B;
    margin-bottom: 3px;
    font-family: Arial, sans-serif;
    letter-spacing: -0.3px;
  }
  .kpi-sub {
    color: #BDC3C7;
    font-size: 10px;
    font-family: Arial, sans-serif;
  }
  .kpi-green  { border-top-color: #27AE60 !important; }
  .kpi-red    { border-top-color: #E74C3C !important; }
  .kpi-orange { border-top-color: #E67E22 !important; }
  .kpi-blue   { border-top-color: #2471A3 !important; }
  .kpi-purple { border-top-color: #9B59B6 !important; }
  .kpi-navy   { border-top-color: #1B3A6B !important; }

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
  hr { border-color: #E8ECF1; margin: 12px 0; }
</style>
""", unsafe_allow_html=True)

# ============================================================
#  AUTHENTICATION
# ============================================================
credentials = st.secrets["gcp_service_account"]
scope = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
creds = Credentials.from_service_account_info(credentials, scopes=scope)
gc = gspread.authorize(creds)

# ============================================================
#  LOAD DATA
# ============================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1kLIT79DBtG13nlOEkvrWe0FauQVOLi9IxMcYbLpdWL4"
sh = gc.open_by_url(SHEET_URL)

@st.cache_data(ttl=600)
def get_data(name, h_row=4, d_row=6):
    try:
        ws       = sh.worksheet(name)
        all_vals = ws.get_all_values()
        headers  = all_vals[h_row - 1]
        data     = all_vals[d_row - 1:]
        df       = pd.DataFrame(data, columns=headers)
        df       = df.replace("", pd.NA).dropna(how="all").fillna("")
        return df
    except Exception as e:
        st.error(f"Error loading {name}: {e}")
        return pd.DataFrame()

df_proc   = get_data("PROCUREMENT")
df_landed = get_data("LANDED COST ANALYSIS")
df_sales  = get_data("SALES")
df_cap    = get_data("CAPITAL LOG", h_row=3, d_row=4)

# ============================================================
#  CLEAN & CALCULATE ALL 12 KPIs
# ============================================================
def to_n(s):
    return pd.to_numeric(
        s.astype(str)
         .str.replace("$","",regex=False)
         .str.replace(",","",regex=False)
         .str.replace("%","",regex=False)
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

def clr(n, threshold=0):
    try:
        return "#27AE60" if float(n) >= threshold else "#E74C3C"
    except:
        return "#1B3A6B"

def warn_clr(n, green=70, orange=40):
    try:
        v = float(n)
        if v >= green:
            return "#27AE60"
        elif v >= orange:
            return "#F39C12"
        else:
            return "#E74C3C"
    except:
        return "#1B3A6B"

# ── ROW 1: BOTTOM LINE ───────────────────────────────────────
total_revenue  = to_n(df_landed.iloc[:, 28]).sum()
landed_cost    = to_n(df_landed.iloc[:, 26]).sum()
gross_profit   = to_n(df_landed.iloc[:, 29]).sum()
net_margin     = (gross_profit / total_revenue * 100
                  if total_revenue > 0 else 0)
roi_pct        = (gross_profit / landed_cost * 100
                  if landed_cost > 0 else 0)

# ── ROW 2: CASH POSITION ─────────────────────────────────────
# Net capital from CAPITAL LOG
net_capital_in  = to_n(df_cap.iloc[:, 4]).sum()
if net_capital_in == 0:
    net_capital_in = 5110.00

proc_spend      = to_n(df_proc.iloc[:, 16]).sum()
total_units     = to_n(df_landed.iloc[:, 4]).sum()
avg_landed_unit = landed_cost / total_units if total_units > 0 else 0
total_procured  = to_n(df_proc.iloc[:, 6]).sum()

df_sales_clean  = df_sales[to_n(df_sales.iloc[:, 10]) > 0]
total_sold      = (to_n(df_sales_clean.iloc[:, 7]).sum()
                   if len(df_sales_clean) > 0 else 0)
remaining       = total_procured - total_sold

# Card 5: Available Buying Power
avail_buying    = net_capital_in - proc_spend

# Card 6: Capital Deployed (locked in stock)
capital_deployed = remaining * avg_landed_unit

# Card 7: Cash Recovery Rate
cash_recovery   = (total_revenue / net_capital_in * 100
                   if net_capital_in > 0 else 0)

# Card 8: Break Even Progress
break_even      = (total_revenue / landed_cost * 100
                   if landed_cost > 0 else 0)

# ── ROW 3: STOCK HEALTH ──────────────────────────────────────
# Card 9: Units Remaining
# (already calculated above)

# Card 10: Stock Sold %
stock_sold_pct  = (total_sold / total_procured * 100
                   if total_procured > 0 else 0)

# Card 11: Avg Days in Stock
try:
    proc_dates = pd.to_datetime(
        df_proc.iloc[:, 1].astype(str),
        errors="coerce"
    ).dropna()
    if len(proc_dates) > 0:
        earliest = proc_dates.min()
        avg_days = (pd.Timestamp.now() - earliest).days
    else:
        avg_days = 0
except:
    avg_days = 0

# Card 12: Landed Cost Per Unit
landed_per_unit = avg_landed_unit

# Colors for all 12 cards
c1_color  = clr(total_revenue)
c2_color  = clr(gross_profit)
c3_color  = clr(net_margin)
c4_color  = clr(roi_pct)
c5_color  = clr(avail_buying)
c6_color  = "#E74C3C" if capital_deployed > net_capital_in * 0.7 else "#F39C12"
c7_color  = warn_clr(cash_recovery, green=50, orange=20)
c8_color  = warn_clr(break_even, green=100, orange=50)
c9_color  = "#27AE60" if remaining < total_procured * 0.5 else "#F39C12"
c10_color = warn_clr(stock_sold_pct, green=70, orange=30)
c11_color = ("#27AE60" if avg_days < 45
             else "#F39C12" if avg_days < 90
             else "#E74C3C")
c12_color = "#1B3A6B"

now = datetime.now().strftime("%d %b %Y  %H:%M")

# Chart colors
C_NAVY   = "#1B3A6B"
C_BLUE   = "#2471A3"
C_GREEN  = "#27AE60"
C_ORANGE = "#E67E22"
C_RED    = "#E74C3C"
C_PURPLE = "#9B59B6"
C_GREY   = "#95A5A6"

# ============================================================
#  HELPER: KPI Card HTML
# ============================================================
def kpi_card(label, value, sub="", color="#1B3A6B",
             progress=None, progress_color="#1B3A6B"):
    bar_html = ""
    if progress is not None:
        pct = max(min(float(progress), 100), 0)
        bar_html = f"""
        <div style="background:#EEF2F9;border-radius:4px;
                    height:6px;overflow:hidden;margin-top:8px;">
          <div style="width:{pct:.1f}%;height:100%;
                      background:{progress_color};
                      border-radius:4px;">
          </div>
        </div>
        """
    return f"""
    <div class="kpi-card" style="border-top-color:{color};">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value" style="color:{color};">{value}</div>
      <div class="kpi-sub">{sub}</div>
      {bar_html}
    </div>
    """

# ============================================================
#  HEADER WITH LOGO
# ============================================================
logo_col, title_col = st.columns([1, 7])

with logo_col:
    try:
        logo_url = (
            "https://raw.githubusercontent.com/"
            "KATLLC/it-asset-dashboard/main/logo.png"
        )
        response = requests.get(logo_url, timeout=5)
        if response.status_code == 200:
            logo_img = Image.open(BytesIO(response.content))
            st.image(logo_img, width=250)
    except:
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
        <div style="color:white;font-size:20px;font-weight:700;
                    font-family:Arial,sans-serif;">
          📊 P&L Executive Dashboard
        </div>
        <div style="color:rgba(255,255,255,0.55);font-size:11px;
                    margin-top:4px;font-family:Arial,sans-serif;">
          IT Asset Trading &nbsp;·&nbsp;
          Procurement → Shipment → Clearing → Sales
          &nbsp;·&nbsp; {now}
        </div>
      </div>
      <div style="
        background:rgba(255,255,255,0.12);
        border:1px solid rgba(255,255,255,0.25);
        border-radius:20px;padding:5px 14px;
        color:white;font-size:11px;font-weight:600;
        font-family:Arial,sans-serif;">
        🟢 LIVE DATA
      </div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
#  ROW 1: THE BOTTOM LINE
# ============================================================
st.markdown(
    '<div class="row-label">📈 Row 1 — The Bottom Line</div>',
    unsafe_allow_html=True
)

r1c1, r1c2, r1c3, r1c4 = st.columns(4)

with r1c1:
    st.markdown(kpi_card(
        "💰 Total Revenue",
        fmt(total_revenue),
        "All sales recorded",
        c1_color
    ), unsafe_allow_html=True)

with r1c2:
    st.markdown(kpi_card(
        "📈 Gross Profit",
        fmt(gross_profit),
        "Revenue minus landed cost",
        c2_color
    ), unsafe_allow_html=True)

with r1c3:
    st.markdown(kpi_card(
        "🎯 Net Margin %",
        fmtp(net_margin),
        "Target > 25%",
        c3_color,
        progress=max(net_margin, 0),
        progress_color=c3_color
    ), unsafe_allow_html=True)

with r1c4:
    st.markdown(kpi_card(
        "🔄 ROI %",
        fmtp(roi_pct),
        "Target > 30%",
        c4_color,
        progress=max(roi_pct, 0),
        progress_color=c4_color
    ), unsafe_allow_html=True)

# ============================================================
#  ROW 2: CASH POSITION
# ============================================================
st.markdown(
    '<div class="row-label">💵 Row 2 — Cash Position</div>',
    unsafe_allow_html=True
)

r2c1, r2c2, r2c3, r2c4 = st.columns(4)

with r2c1:
    st.markdown(kpi_card(
        "✅ Available Buying Power",
        fmt(avail_buying),
        f"Of {fmt(net_capital_in)} total capital",
        c5_color,
        progress=max(avail_buying / net_capital_in * 100
                     if net_capital_in > 0 else 0, 0),
        progress_color=c5_color
    ), unsafe_allow_html=True)

with r2c2:
    st.markdown(kpi_card(
        "🔒 Capital Deployed",
        fmt(capital_deployed),
        "Locked in unsold stock",
        c6_color,
        progress=max(capital_deployed / net_capital_in * 100
                     if net_capital_in > 0 else 0, 0),
        progress_color=c6_color
    ), unsafe_allow_html=True)

with r2c3:
    st.markdown(kpi_card(
        "💹 Cash Recovery Rate",
        fmtp(cash_recovery),
        "Revenue / Net Capital In",
        c7_color,
        progress=max(cash_recovery, 0),
        progress_color=c7_color
    ), unsafe_allow_html=True)

with r2c4:
    st.markdown(kpi_card(
        "🎯 Break Even Progress",
        fmtp(break_even),
        "100% = break even · >100% = profit",
        c8_color,
        progress=max(min(break_even, 100), 0),
        progress_color=c8_color
    ), unsafe_allow_html=True)

# ============================================================
#  ROW 3: STOCK HEALTH
# ============================================================
st.markdown(
    '<div class="row-label">📦 Row 3 — Stock Health</div>',
    unsafe_allow_html=True
)

r3c1, r3c2, r3c3, r3c4 = st.columns(4)

with r3c1:
    st.markdown(kpi_card(
        "🏭 Units Remaining",
        f"{int(remaining):,}",
        f"Of {int(total_procured):,} procured",
        c9_color,
        progress=max(100 - stock_sold_pct, 0),
        progress_color=c9_color
    ), unsafe_allow_html=True)

with r3c2:
    st.markdown(kpi_card(
        "📤 Stock Sold %",
        fmtp(stock_sold_pct),
        f"Target > 70% · {int(total_sold):,} units sold",
        c10_color,
        progress=max(stock_sold_pct, 0),
        progress_color=c10_color
    ), unsafe_allow_html=True)

with r3c3:
    days_label = (
        "✅ Good" if avg_days < 45
        else "⚠️ Aging" if avg_days < 90
        else "🔴 Action needed"
    )
    st.markdown(kpi_card(
        "📅 Avg Days in Stock",
        f"{avg_days} days",
        days_label,
        c11_color,
        progress=max(min(avg_days / 90 * 100, 100), 0),
        progress_color=c11_color
    ), unsafe_allow_html=True)

with r3c4:
    st.markdown(kpi_card(
        "🔢 Landed Cost / Unit",
        fmt(landed_per_unit),
        "True cost per unit",
        c12_color
    ), unsafe_allow_html=True)

# ============================================================
#  BUYING POWER BAR
# ============================================================
st.markdown("---")
pct_avail = (avail_buying / net_capital_in * 100
             if net_capital_in > 0 else 0)
pct_spent = 100 - pct_avail
pct_spent_display = max(pct_spent, 1)
pct_avail_display = max(pct_avail, 1)

st.markdown(
    '<div class="row-label">💵 Auction Buying Power</div>',
    unsafe_allow_html=True
)

st.markdown(f"""
<div style="background:white;border-radius:12px;
            padding:16px 18px;
            box-shadow:0 2px 8px rgba(0,0,0,0.06);
            margin-bottom:12px;">
  <div style="display:flex;justify-content:space-between;
              margin-bottom:8px;">
    <span style="color:#7F8C8D;font-size:11px;font-weight:600;
                 font-family:Arial,sans-serif;">
      Budget Utilization
    </span>
    <span style="color:#1B3A6B;font-size:11px;font-weight:700;
                 font-family:Arial,sans-serif;">
      {fmtp(pct_spent)} deployed &nbsp;|&nbsp;
      {fmtp(pct_avail)} available
    </span>
  </div>
  <div style="display:flex;height:14px;border-radius:8px;
              overflow:hidden;">
    <div style="width:{pct_spent_display:.1f}%;
                background:linear-gradient(90deg,#E67E22,#D35400);">
    </div>
    <div style="width:{pct_avail_display:.1f}%;
                background:linear-gradient(90deg,#27AE60,#1E8449);">
    </div>
  </div>
  <div style="display:flex;gap:20px;margin-top:8px;">
    <div style="display:flex;align-items:center;gap:5px;
                font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;">
      <div style="width:8px;height:8px;border-radius:50%;
                  background:#E67E22;"></div>
      Spent: {fmt(proc_spend)}
    </div>
    <div style="display:flex;align-items:center;gap:5px;
                font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;">
      <div style="width:8px;height:8px;border-radius:50%;
                  background:#27AE60;"></div>
      Available: {fmt(avail_buying)}
    </div>
    <div style="display:flex;align-items:center;gap:5px;
                font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;">
      <div style="width:8px;height:8px;border-radius:50%;
                  background:#1B3A6B;"></div>
      Total Capital: {fmt(net_capital_in)}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
#  INVENTORY PIPELINE BAR
# ============================================================
st.markdown(
    '<div class="row-label">📦 Inventory Pipeline</div>',
    unsafe_allow_html=True
)

pct_sold_d = max(float(stock_sold_pct), 1)
pct_rem_d  = max(float(100 - stock_sold_pct), 1)

st.markdown(f"""
<div style="background:white;border-radius:12px;
            padding:16px 18px;
            box-shadow:0 2px 8px rgba(0,0,0,0.06);
            margin-bottom:12px;">
  <div style="display:flex;justify-content:space-between;
              margin-bottom:8px;">
    <span style="color:#7F8C8D;font-size:11px;font-weight:600;
                 font-family:Arial,sans-serif;">
      Stock Movement
    </span>
    <span style="color:#1B3A6B;font-size:11px;font-weight:700;
                 font-family:Arial,sans-serif;">
      {fmtp(stock_sold_pct)} sold
    </span>
  </div>
  <div style="display:flex;height:14px;border-radius:8px;
              overflow:hidden;">
    <div style="width:{pct_sold_d:.1f}%;
                background:linear-gradient(90deg,#27AE60,#1E8449);">
    </div>
    <div style="width:{pct_rem_d:.1f}%;
                background:linear-gradient(90deg,#E67E22,#D35400);">
    </div>
  </div>
  <div style="display:flex;gap:20px;margin-top:8px;">
    <div style="display:flex;align-items:center;gap:5px;
                font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;">
      <div style="width:8px;height:8px;border-radius:50%;
                  background:#27AE60;"></div>
      Sold: {int(total_sold):,} units
    </div>
    <div style="display:flex;align-items:center;gap:5px;
                font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;">
      <div style="width:8px;height:8px;border-radius:50%;
                  background:#E67E22;"></div>
      Remaining: {int(remaining):,} units
      ({fmt(capital_deployed)} at cost)
    </div>
    <div style="display:flex;align-items:center;gap:5px;
                font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;">
      <div style="width:8px;height:8px;border-radius:50%;
                  background:#1B3A6B;"></div>
      Total: {int(total_procured):,} units
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
#  CHARTS
# ============================================================
st.markdown("---")
chart_col1, chart_col2 = st.columns(2)

# ── Pie Chart ─────────────────────────────────────────────────
with chart_col1:
    st.markdown(
        '<div class="row-label">💸 Cost Structure</div>',
        unsafe_allow_html=True
    )

    cost_purchase = to_n(df_landed.iloc[:, 9]).sum()
    cost_usa      = (to_n(df_landed.iloc[:, 10]).sum() +
                     to_n(df_landed.iloc[:, 11]).sum())
    cost_freight  = to_n(df_landed.iloc[:, 16]).sum()
    cost_duty     = to_n(df_landed.iloc[:, 18]).sum()
    cost_agent    = to_n(df_landed.iloc[:, 20]).sum()
    cost_local    = to_n(df_landed.iloc[:, 22]).sum()
    cost_other    = to_n(df_landed.iloc[:, 24]).sum()

    labels = ["Purchase","USA Costs","Freight",
              "Customs Duty","Agent Fee",
              "Local Transport","Other"]
    values = [cost_purchase, cost_usa, cost_freight,
              cost_duty, cost_agent, cost_local, cost_other]
    colors = [C_NAVY, C_BLUE, C_ORANGE,
              C_RED, C_PURPLE, C_GREEN, C_GREY]

    nz = [(l,v,c) for l,v,c in zip(labels,values,colors) if v > 0]
    if not nz:
        nz = [("Purchase", max(cost_purchase,1), C_NAVY)]

    fig_pie = go.Figure(go.Pie(
        labels   = [x[0] for x in nz],
        values   = [x[1] for x in nz],
        hole     = 0,
        marker   = dict(
            colors=[x[2] for x in nz],
            line=dict(color="white", width=3)
        ),
        textinfo = "percent+label",
        textfont = dict(size=11, color="white")
    ))
    fig_pie.update_layout(
        height        = 320,
        paper_bgcolor = "white",
        showlegend    = True,
        margin        = dict(t=20,b=20,l=20,r=20),
        legend        = dict(font=dict(size=10,color=C_NAVY))
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# ── Waterfall Chart ───────────────────────────────────────────
with chart_col2:
    st.markdown(
        '<div class="row-label">🏗️ How Cost Builds Up</div>',
        unsafe_allow_html=True
    )

    max_y = max(landed_cost * 1.40, 10)

    fig_wf = go.Figure(go.Waterfall(
        orientation  = "v",
        measure      = ["relative","relative","relative",
                        "relative","relative","relative","total"],
        x            = ["Purchase","USA\nPrep","Freight",
                        "Customs\nDuty","Agent\nFees",
                        "Local\nTrans","TOTAL\nLANDED"],
        y            = [cost_purchase, cost_usa, cost_freight,
                        cost_duty, cost_agent, cost_local, 0],
        text         = [fmt(cost_purchase), fmt(cost_usa),
                        fmt(cost_freight), fmt(cost_duty),
                        fmt(cost_agent), fmt(cost_local),
                        fmt(landed_cost)],
        textposition = "outside",
        textfont     = dict(size=10, color=C_NAVY),
        connector    = dict(
            line=dict(color="#E8ECF1", width=1, dash="dot")
        ),
        increasing   = dict(
            marker=dict(color="rgba(36,113,163,0.85)")
        ),
        decreasing   = dict(
            marker=dict(color="rgba(231,76,60,0.85)")
        ),
        totals       = dict(
            marker=dict(color="rgba(27,58,107,0.90)")
        )
    ))
    fig_wf.update_layout(
        height        = 320,
        paper_bgcolor = "white",
        plot_bgcolor  = "#FAFBFD",
        showlegend    = False,
        margin        = dict(t=20,b=60,l=60,r=40),
        yaxis         = dict(
            gridcolor=C_GREY,
            range=[0, max_y],
            tickfont=dict(size=9)
        ),
        xaxis = dict(tickfont=dict(size=9))
    )
    st.plotly_chart(fig_wf, use_container_width=True)

# ── Gauges ────────────────────────────────────────────────────
st.markdown(
    '<div class="row-label">📊 Business Health Gauges</div>',
    unsafe_allow_html=True
)

capital_risk = (remaining / total_procured * 100
                if total_procured > 0 else 100)

fig_g = go.Figure()

fig_g.add_trace(go.Indicator(
    mode   = "gauge+number",
    value  = float(stock_sold_pct),
    title  = {
        "text": (
            "<b>Stock Sold</b><br>"
            f"<span style='font-size:11px;color:#7F8C8D;'>"
            f"{int(total_sold):,} of {int(total_procured):,} units"
            f"</span>"
        ),
        "font": {"size":13,"color":C_NAVY}
    },
    number = {"suffix":"%","font":{"size":28,"color":C_NAVY}},
    gauge  = {
        "axis" : {"range":[0,100],"dtick":25,
                  "tickfont":{"size":9,"color":C_GREY}},
        "bar"  : {"color":C_GREEN,"thickness":0.3},
        "bgcolor"    : "#F0F3F8",
        "borderwidth": 0,
        "steps": [
            {"range":[0,25],"color":"#FADBD8"},
            {"range":[25,50],"color":"#FCF3CF"},
            {"range":[50,75],"color":"#D5F5E3"},
            {"range":[75,100],"color":"#ABEBC6"}
        ],
        "threshold": {
            "line"     : {"color":C_NAVY,"width":2},
            "thickness": 0.75,
            "value"    : float(stock_sold_pct)
        }
    },
    domain = {"x":[0.05,0.45],"y":[0.05,0.95]}
))

fig_g.add_trace(go.Indicator(
    mode   = "gauge+number",
    value  = float(break_even),
    title  = {
        "text": (
            "<b>Break Even Progress</b><br>"
            f"<span style='font-size:11px;color:#7F8C8D;'>"
            f"100% = break even"
            f"</span>"
        ),
        "font": {"size":13,"color":C_NAVY}
    },
    number = {"suffix":"%","font":{"size":28,"color":C_BLUE}},
    gauge  = {
        "axis" : {"range":[0,150],"dtick":25,
                  "tickfont":{"size":9,"color":C_GREY}},
        "bar"  : {"color":C_BLUE,"thickness":0.3},
        "bgcolor"    : "#F0F3F8",
        "borderwidth": 0,
        "steps": [
            {"range":[0,50],"color":"#FADBD8"},
            {"range":[50,100],"color":"#FCF3CF"},
            {"range":[100,150],"color":"#D5F5E3"},
        ],
        "threshold": {
            "line"     : {"color":C_GREEN,"width":3},
            "thickness": 0.75,
            "value"    : 100
        }
    },
    domain = {"x":[0.55,0.95],"y":[0.05,0.95]}
))

fig_g.update_layout(
    height        = 280,
    paper_bgcolor = "white",
    margin        = dict(t=40,b=20,l=30,r=30)
)
st.plotly_chart(fig_g, use_container_width=True)

# ============================================================
#  LOT DETAIL TABLE
# ============================================================
st.markdown("---")
st.markdown(
    '<div class="row-label">📋 Lot Detail — Full Breakdown</div>',
    unsafe_allow_html=True
)

if len(df_landed) > 0:
    cols_to_show = [0,1,2,4,9,17,19,26,27,28,29,31,32]
    col_names    = [
        "Lot","Shipment","Category","Qty",
        "Purchase","Freight","Duty",
        "Total Landed","$/Unit",
        "Revenue","Profit","Margin%","ROI%"
    ]

    display_df = pd.DataFrame()
    for col_idx, col_name in zip(cols_to_show, col_names):
        if col_idx < len(df_landed.columns):
            display_df[col_name] = df_landed.iloc[:, col_idx]

    money_cols = ["Purchase","Freight","Duty",
                  "Total Landed","$/Unit","Revenue","Profit"]
    pct_cols   = ["Margin%","ROI%"]

    for c in money_cols:
        if c in display_df.columns:
            display_df[c] = to_n(display_df[c])
    for c in pct_cols:
        if c in display_df.columns:
            display_df[c] = to_n(display_df[c])

    display_df = display_df[
        display_df["Lot"].astype(str).str.strip() != ""
    ]
    display_df = display_df[
        display_df["Lot"].astype(str).str.upper() != "TOTALS"
    ]
    display_df = display_df[
        ~display_df["Lot"].astype(str).str.contains(
            "From|Lot Number", na=False
        )
    ]

    format_dict = {}
    for c in money_cols:
        if c in display_df.columns:
            format_dict[c] = "${:,.2f}"
    for c in pct_cols:
        if c in display_df.columns:
            format_dict[c] = "{:.1f}%"

    def color_profit(val):
        try:
            color = "#27AE60" if float(val) >= 0 else "#E74C3C"
            return f"color: {color}; font-weight: bold"
        except:
            return ""

    styled = display_df.style.format(format_dict)

    if "Profit" in display_df.columns:
        styled = styled.map(color_profit, subset=["Profit"])
    if "Margin%" in display_df.columns:
        styled = styled.map(color_profit, subset=["Margin%"])

    styled = styled.set_properties(**{
        "background-color": "white",
        "color"           : "#1B3A6B",
        "border"          : "1px solid #E8ECF1",
        "font-size"       : "12px",
        "font-family"     : "Arial, sans-serif"
    })
    styled = styled.set_table_styles([
        {"selector": "th", "props": [
            ("background-color", "#1B3A6B"),
            ("color", "white"),
            ("font-size", "10px"),
            ("font-weight", "700"),
            ("text-transform", "uppercase"),
            ("letter-spacing", "1px"),
            ("padding", "8px 12px"),
            ("border", "1px solid #2471A3")
        ]},
        {"selector": "tr:nth-child(even)", "props": [
            ("background-color", "#F4F7FB")
        ]}
    ])

    st.write(styled.to_html(), unsafe_allow_html=True)

else:
    st.info("No lot data available yet.")

# ============================================================
#  FOOTER
# ============================================================
st.markdown("---")
st.markdown(f"""
<div style="text-align:center;color:#95A5A6;
            font-size:11px;padding:10px;
            font-family:Arial,sans-serif;">
  📊 IT Asset Trading P&L Dashboard &nbsp;·&nbsp;
  Connected Live to Google Sheets &nbsp;·&nbsp;
  Auto-refreshes every 10 minutes &nbsp;·&nbsp;
  {now}
</div>
""", unsafe_allow_html=True)
