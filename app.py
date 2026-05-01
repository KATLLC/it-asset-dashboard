import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

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
  /* Main background */
  .main { background-color: #F4F7FB; }
  
  /* Hide Streamlit branding */
  #MainMenu {visibility: hidden;}
  footer {visibility: hidden;}
  header {visibility: hidden;}

  /* KPI cards */
  [data-testid="metric-container"] {
    background-color: white;
    border-radius: 10px;
    padding: 15px;
    border-top: 4px solid #1B3A6B;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  }

  /* Metric label */
  [data-testid="metric-container"] label {
    color: #95A5A6 !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  /* Metric value */
  [data-testid="metric-container"] [data-testid="metric-value"] {
    color: #1B3A6B !important;
    font-size: 22px !important;
    font-weight: 700 !important;
  }

  /* Section headers */
  h2 {
    color: #1B3A6B !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    border-left: 4px solid #3498DB;
    padding-left: 10px;
  }

  /* Divider */
  hr {
    border-color: #E8ECF1;
  }

  /* Dataframe */
  .dataframe {
    font-family: Arial, sans-serif !important;
    font-size: 12px !important;
  }
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

# ============================================================
#  CLEAN & CALCULATE KPIs
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

# LANDED COST columns by position
landed_cost    = to_n(df_landed.iloc[:, 26]).sum()
total_revenue  = to_n(df_landed.iloc[:, 28]).sum()
gross_profit   = to_n(df_landed.iloc[:, 29]).sum()
cost_purchase  = to_n(df_landed.iloc[:, 9]).sum()
cost_duty      = to_n(df_landed.iloc[:, 18]).sum()
cost_agent     = to_n(df_landed.iloc[:, 20]).sum()
cost_local     = to_n(df_landed.iloc[:, 22]).sum()
cost_other     = to_n(df_landed.iloc[:, 24]).sum()
cost_freight   = to_n(df_landed.iloc[:, 16]).sum()
cost_usa       = (to_n(df_landed.iloc[:, 10]).sum() +
                  to_n(df_landed.iloc[:, 11]).sum())

total_lots     = len(df_landed[df_landed.iloc[:, 0].astype(str).str.strip() != ""])
total_units    = to_n(df_landed.iloc[:, 4]).sum()
avg_per_unit   = landed_cost / total_units if total_units > 0 else 0

overall_margin = (gross_profit / total_revenue * 100
                  if total_revenue > 0 else 0)
overall_roi    = (gross_profit / landed_cost * 100
                  if landed_cost > 0 else 0)

# PROCUREMENT
total_procured = to_n(df_proc.iloc[:, 6]).sum()
cash_spent     = to_n(df_proc.iloc[:, 16]).sum()

# SALES
df_sales_clean = df_sales[to_n(df_sales.iloc[:, 10]) > 0]
total_sold     = to_n(df_sales_clean.iloc[:, 7]).sum() if len(df_sales_clean) > 0 else 0

remaining      = total_procured - total_sold
pct_sold       = (total_sold / total_procured * 100
                  if total_procured > 0 else 0)
pct_remaining  = 100 - pct_sold

# BUDGET
BUDGET         = 5110.00
cash_available = BUDGET - cash_spent
pct_used       = (cash_spent / BUDGET * 100 if BUDGET > 0 else 0)
pct_free       = 100 - pct_used

if pct_free >= 50:
    budget_status = "HEALTHY"
    budget_color  = "#27AE60"
elif pct_free >= 25:
    budget_status = "MODERATE"
    budget_color  = "#F39C12"
else:
    budget_status = "LOW"
    budget_color  = "#E74C3C"

profit_color = "#27AE60" if gross_profit >= 0 else "#E74C3C"
roi_color    = "#27AE60" if overall_roi >= 0 else "#E74C3C"

now = datetime.now().strftime("%d %b %Y  %H:%M")

# ============================================================
#  HEADER
# ============================================================
st.markdown(f"""
<div style="
  background: linear-gradient(135deg, #0F2B46 0%, #1B4F72 60%, #2471A3 100%);
  border-radius: 14px;
  padding: 22px 28px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
">
  <div>
    <div style="color:white;font-size:22px;font-weight:700;">
      📊 P&L Executive Dashboard
    </div>
    <div style="color:rgba(255,255,255,0.55);font-size:11px;margin-top:4px;">
      IT Asset Trading &nbsp;·&nbsp;
      Procurement → Shipment → Clearing → Sales
      &nbsp;·&nbsp; {now}
    </div>
  </div>
  <div style="
    background:rgba(255,255,255,0.12);
    border:1px solid rgba(255,255,255,0.25);
    border-radius:20px;padding:5px 14px;
    color:white;font-size:11px;font-weight:600;">
    🟢 LIVE DATA
  </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
#  SECTION 1: BUSINESS OVERVIEW KPI CARDS
# ============================================================
st.markdown("#### 💼 Business Overview")

c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("💰 Revenue",       fmt(total_revenue))
c2.metric("📈 Gross Profit",  fmt(gross_profit))
c3.metric("🎯 Margin",        fmtp(overall_margin))
c4.metric("🔄 ROI",           fmtp(overall_roi))
c5.metric("📦 Total Lots",    str(total_lots))
c6.metric("🔢 Avg/Unit",      fmt(avg_per_unit))

st.divider()

# ============================================================
#  SECTION 2: BUYING POWER
# ============================================================
st.markdown(f"#### 💵 Auction Buying Power &nbsp; "
            f"<span style='background:{budget_color}22;"
            f"color:{budget_color};"
            f"border:1px solid {budget_color}44;"
            f"border-radius:20px;padding:2px 10px;"
            f"font-size:11px;font-weight:700;'>"
            f"{budget_status}</span>",
            unsafe_allow_html=True)

b1, b2, b3 = st.columns(3)
b1.metric("💼 Total Budget",        fmt(BUDGET))
b2.metric("🛒 Spent on Auctions",   fmt(cash_spent),   f"{fmtp(pct_used)} used")
b3.metric("✅ Available for Bidding",fmt(cash_available),f"{fmtp(pct_free)} remaining")

# Progress bar
st.markdown(f"""
<div style="margin:10px 0;">
  <div style="display:flex;justify-content:space-between;
              margin-bottom:4px;font-size:11px;color:#7F8C8D;">
    <span>Budget Utilization</span>
    <span style="font-weight:700;color:#1B3A6B;">
      {fmtp(pct_used)} deployed
    </span>
  </div>
  <div style="background:#EEF2F9;border-radius:6px;
              height:10px;overflow:hidden;">
    <div style="width:{min(pct_used,100):.1f}%;
                height:100%;
                background:linear-gradient(90deg,#E67E22,#D35400);
                border-radius:6px;">
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ============================================================
#  SECTION 3: INVENTORY PIPELINE
# ============================================================
st.markdown("#### 📦 Inventory Pipeline")

i1, i2, i3 = st.columns(3)
i1.metric("📥 Procured",  f"{int(total_procured):,}", "Total units bought")
i2.metric("📤 Sold",      f"{int(total_sold):,}",     f"{fmtp(pct_sold)} of stock")
i3.metric("🏭 Remaining", f"{int(remaining):,}",      "Unsold inventory")

# Inventory bar
st.markdown(f"""
<div style="margin:10px 0;">
  <div style="display:flex;height:24px;border-radius:8px;overflow:hidden;">
    <div style="width:{max(pct_sold,1):.1f}%;
                background:linear-gradient(90deg,#27AE60,#1E8449);
                display:flex;align-items:center;justify-content:center;
                color:white;font-size:11px;font-weight:600;">
      {"Sold" if pct_sold > 8 else ""}
    </div>
    <div style="width:{max(pct_remaining,1):.1f}%;
                background:linear-gradient(90deg,#E67E22,#D35400);
                display:flex;align-items:center;justify-content:center;
                color:white;font-size:11px;font-weight:600;">
      {"Remaining" if pct_remaining > 8 else ""}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ============================================================
#  SECTION 4: CHARTS
# ============================================================

# Chart colors
C_NAVY   = "#1B3A6B"
C_BLUE   = "#2471A3"
C_GREEN  = "#27AE60"
C_ORANGE = "#E67E22"
C_RED    = "#E74C3C"
C_PURPLE = "#9B59B6"
C_GREY   = "#95A5A6"

chart_col1, chart_col2 = st.columns(2)

# ── Pie Chart ─────────────────────────────────────────────────
with chart_col1:
    st.markdown("#### 💸 Cost Structure")

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
        labels    = [x[0] for x in nz],
        values    = [x[1] for x in nz],
        hole      = 0,
        marker    = dict(
            colors=[x[2] for x in nz],
            line=dict(color="white", width=3)
        ),
        textinfo  = "percent+label",
        textfont  = dict(size=11, color="white")
    ))
    fig_pie.update_layout(
        height        = 350,
        paper_bgcolor = "white",
        showlegend    = True,
        margin        = dict(t=20,b=20,l=20,r=20),
        legend        = dict(font=dict(size=10,color=C_NAVY))
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# ── Waterfall Chart ───────────────────────────────────────────
with chart_col2:
    st.markdown("#### 🏗️ How Cost Builds Up")

    max_y = max(landed_cost * 1.40, 10)

    fig_wf = go.Figure(go.Waterfall(
        orientation  = "v",
        measure      = ["relative","relative","relative",
                        "relative","relative","relative","total"],
        x            = ["Purchase","USA\nPrep","Freight",
                        "Customs\nDuty","Agent\nFees",
                        "Local\nTrans","TOTAL\nLANDED"],
        y            = [cost_purchase,cost_usa,cost_freight,
                        cost_duty,cost_agent,cost_local,0],
        text         = [fmt(cost_purchase),fmt(cost_usa),
                        fmt(cost_freight),fmt(cost_duty),
                        fmt(cost_agent),fmt(cost_local),
                        fmt(landed_cost)],
        textposition = "outside",
        textfont     = dict(size=10,color=C_NAVY),
        connector    = dict(line=dict(color="#E8ECF1",width=1,dash="dot")),
        increasing   = dict(marker=dict(color="rgba(36,113,163,0.85)")),
        decreasing   = dict(marker=dict(color="rgba(231,76,60,0.85)")),
        totals       = dict(marker=dict(color="rgba(27,58,107,0.90)"))
    ))
    fig_wf.update_layout(
        height        = 350,
        paper_bgcolor = "white",
        plot_bgcolor  = "#FAFBFD",
        showlegend    = False,
        margin        = dict(t=30,b=60,l=60,r=40),
        yaxis         = dict(
            gridcolor=C_GREY,
            range=[0, max_y],
            tickfont=dict(size=9)
        ),
        xaxis         = dict(tickfont=dict(size=9))
    )
    st.plotly_chart(fig_wf, use_container_width=True)

# ── Gauges ────────────────────────────────────────────────────
st.markdown("#### 📊 Business Health Gauges")

capital_risk = (remaining / total_procured * 100
                if total_procured > 0 else 100)

fig_g = go.Figure()

fig_g.add_trace(go.Indicator(
    mode   = "gauge+number",
    value  = pct_sold,
    title  = {
        "text": f"<b>Stock Sold</b><br>"
                f"<span style='font-size:11px;color:#7F8C8D;'>"
                f"{int(total_sold):,} of {int(total_procured):,} units"
                f"</span>",
        "font": {"size":13,"color":C_NAVY}
    },
    number = {"suffix":"%","font":{"size":28,"color":C_NAVY}},
    gauge  = {
        "axis" : {"range":[0,100],"dtick":25,
                  "tickfont":{"size":9,"color":C_GREY}},
        "bar"  : {"color":C_GREEN,"thickness":0.3},
        "bgcolor": "#F0F3F8","borderwidth":0,
        "steps": [
            {"range":[0,25],"color":"#FADBD8"},
            {"range":[25,50],"color":"#FCF3CF"},
            {"range":[50,75],"color":"#D5F5E3"},
            {"range":[75,100],"color":"#ABEBC6"}
        ],
        "threshold": {
            "line":{"color":C_NAVY,"width":2},
            "thickness":0.75,"value":pct_sold
        }
    },
    domain = {"x":[0.05,0.45],"y":[0.05,0.95]}
))

fig_g.add_trace(go.Indicator(
    mode   = "gauge+number",
    value  = capital_risk,
    title  = {
        "text": f"<b>Capital at Risk</b><br>"
                f"<span style='font-size:11px;color:#7F8C8D;'>"
                f"{fmt(remaining * avg_per_unit)} unsold"
                f"</span>",
        "font": {"size":13,"color":C_NAVY}
    },
    number = {"suffix":"%","font":{"size":28,"color":C_RED}},
    gauge  = {
        "axis" : {"range":[0,100],"dtick":25,
                  "tickfont":{"size":9,"color":C_GREY}},
        "bar"  : {"color":C_RED,"thickness":0.3},
        "bgcolor": "#F0F3F8","borderwidth":0,
        "steps": [
            {"range":[0,25],"color":"#ABEBC6"},
            {"range":[25,50],"color":"#D5F5E3"},
            {"range":[50,75],"color":"#FCF3CF"},
            {"range":[75,100],"color":"#FADBD8"}
        ],
        "threshold": {
            "line":{"color":C_RED,"width":2},
            "thickness":0.75,"value":capital_risk
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

st.divider()

# ============================================================
#  SECTION 5: LOT DETAIL TABLE
# ============================================================
st.markdown("#### 📋 Lot Detail — Full Breakdown")

if len(df_landed) > 0:
    # Select key columns by position
    cols_to_show = [0,1,2,4,9,17,19,26,27,28,29,31,32]
    col_names    = [
        "Lot","Shipment","Category","Qty",
        "Purchase","Freight","Duty",
        "Total Landed","$/Unit",
        "Revenue","Profit","Margin%","ROI%"
    ]

    # Build display table
    display_df = pd.DataFrame()
    for i, (col_idx, col_name) in enumerate(zip(cols_to_show, col_names)):
        if col_idx < len(df_landed.columns):
            display_df[col_name] = df_landed.iloc[:, col_idx]

    # Convert money columns to numeric for display
    money_cols = ["Purchase","Freight","Duty",
                  "Total Landed","$/Unit","Revenue","Profit"]
    pct_cols   = ["Margin%","ROI%"]

    for c in money_cols:
        if c in display_df.columns:
            display_df[c] = to_n(display_df[c])

    for c in pct_cols:
        if c in display_df.columns:
            display_df[c] = to_n(display_df[c])

    # Remove empty rows
    display_df = display_df[
        display_df["Lot"].astype(str).str.strip() != ""
    ]
    display_df = display_df[
        display_df["Lot"].astype(str).str.upper() != "TOTALS"
    ]

    # Format for display
    format_dict = {}
    for c in money_cols:
        if c in display_df.columns:
            format_dict[c] = "${:,.2f}"
    for c in pct_cols:
        if c in display_df.columns:
            format_dict[c] = "{:.1f}%"

    # Style the table
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

    styled = styled.set_table_styles([{
        "selector": "th",
        "props": [
            ("background-color", "#1B3A6B"),
            ("color", "white"),
            ("font-size", "10px"),
            ("font-weight", "700"),
            ("text-transform", "uppercase"),
            ("letter-spacing", "1px"),
            ("padding", "8px 12px"),
            ("border", "1px solid #2471A3")
        ]
    },{
        "selector": "tr:nth-child(even)",
        "props": [("background-color", "#F4F7FB")]
    }])

    st.write(styled.to_html(), unsafe_allow_html=True)

else:
    st.info("No lot data available yet.")

# ============================================================
#  FOOTER
# ============================================================
st.divider()
st.markdown(f"""
<div style="text-align:center;color:#95A5A6;font-size:11px;padding:10px;">
  📊 IT Asset Trading P&L Dashboard &nbsp;·&nbsp;
  Connected Live to Google Sheets &nbsp;·&nbsp;
  Auto-refreshes every 10 minutes &nbsp;·&nbsp;
  {now}
</div>
""", unsafe_allow_html=True)
