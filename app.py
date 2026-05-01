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
#  PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="P&L Executive Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
#  CSS
# ============================================================
st.markdown("""
<style>
  .main {background-color:#F4F7FB;}
  #MainMenu {visibility:hidden;}
  footer {visibility:hidden;}
  header {visibility:hidden;}
  .block-container {padding-top:1rem;}
  hr {border-color:#E8ECF1;margin:12px 0;}
  .row-label {
    color:#1B3A6B;font-size:10px;font-weight:700;
    text-transform:uppercase;letter-spacing:2px;
    padding-left:8px;border-left:3px solid #3498DB;
    margin:16px 0 10px 0;font-family:Arial,sans-serif;
  }
</style>
""", unsafe_allow_html=True)

# ============================================================
#  AUTH + DATA
# ============================================================
credentials = st.secrets["gcp_service_account"]
scope = ['https://www.googleapis.com/auth/spreadsheets',
         'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(credentials, scopes=scope)
gc = gspread.authorize(creds)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1kLIT79DBtG13nlOEkvrWe0FauQVOLi9IxMcYbLpdWL4"
sh = gc.open_by_url(SHEET_URL)

@st.cache_data(ttl=600)
def get_data(name, h_row=4, d_row=6):
    try:
        ws = sh.worksheet(name)
        v = ws.get_all_values()
        df = pd.DataFrame(v[d_row-1:], columns=v[h_row-1])
        return df.replace("", pd.NA).dropna(how="all").fillna("")
    except Exception as e:
        st.error(f"Error loading {name}: {e}")
        return pd.DataFrame()

df_proc   = get_data("PROCUREMENT")
df_landed = get_data("LANDED COST ANALYSIS")
df_sales  = get_data("SALES")
df_cap    = get_data("CAPITAL LOG", h_row=3, d_row=4)

# ============================================================
#  HELPERS
# ============================================================
def to_n(s):
    return pd.to_numeric(
        s.astype(str).str.replace("$","",regex=False)
         .str.replace(",","",regex=False)
         .str.replace("%","",regex=False).str.strip(),
        errors="coerce").fillna(0)

def fmt(n):
    try: return f"${float(n):,.2f}"
    except: return "$0.00"

def fmtp(n):
    try: return f"{float(n):.1f}%"
    except: return "0.0%"

def clr(n):
    try: return "#27AE60" if float(n) >= 0 else "#E74C3C"
    except: return "#1B3A6B"

def warn_clr(n, g=70, o=40):
    try:
        v = float(n)
        if v >= g: return "#27AE60"
        elif v >= o: return "#F39C12"
        else: return "#E74C3C"
    except: return "#1B3A6B"

def kpi_card(label, value, sub, color):
    return f"""<div style="background:white;border-radius:12px;padding:16px 18px;box-shadow:0 2px 8px rgba(0,0,0,0.06);border-top:4px solid {color};margin-bottom:12px;min-height:100px;"><div style="color:#95A5A6;font-size:10px;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;margin-bottom:6px;font-family:Arial,sans-serif;">{label}</div><div style="font-size:20px;font-weight:700;color:{color};margin-bottom:3px;font-family:Arial,sans-serif;">{value}</div><div style="color:#BDC3C7;font-size:10px;font-family:Arial,sans-serif;">{sub}</div></div>"""

# ============================================================
#  KPIs
# ============================================================
total_revenue  = to_n(df_landed.iloc[:, 28]).sum()
landed_cost    = to_n(df_landed.iloc[:, 26]).sum()
gross_profit   = to_n(df_landed.iloc[:, 29]).sum()
net_margin     = (gross_profit/total_revenue*100) if total_revenue > 0 else 0
roi_pct        = (gross_profit/landed_cost*100) if landed_cost > 0 else 0

net_capital_in = to_n(df_cap.iloc[:, 4]).sum()
if net_capital_in == 0: net_capital_in = 5110.00

proc_spend     = to_n(df_proc.iloc[:, 16]).sum()
total_units    = to_n(df_landed.iloc[:, 4]).sum()
avg_unit       = landed_cost/total_units if total_units > 0 else 0
total_procured = to_n(df_proc.iloc[:, 6]).sum()

df_sc = df_sales[to_n(df_sales.iloc[:, 10]) > 0]
total_sold = to_n(df_sc.iloc[:, 7]).sum() if len(df_sc) > 0 else 0
remaining  = total_procured - total_sold

avail_buying    = net_capital_in - proc_spend
capital_deployed= remaining * avg_unit
cash_recovery   = (total_revenue/net_capital_in*100) if net_capital_in > 0 else 0
break_even      = (total_revenue/landed_cost*100) if landed_cost > 0 else 0
stock_sold_pct  = (total_sold/total_procured*100) if total_procured > 0 else 0

try:
    pd_dates = pd.to_datetime(df_proc.iloc[:,1].astype(str), errors="coerce").dropna()
    avg_days = (pd.Timestamp.now() - pd_dates.min()).days if len(pd_dates) > 0 else 0
except: avg_days = 0

now = datetime.now().strftime("%d %b %Y  %H:%M")

# Colors
c1  = clr(total_revenue)
c2  = clr(gross_profit)
c3  = clr(net_margin)
c4  = clr(roi_pct)
c5  = clr(avail_buying)
c6  = "#E74C3C" if capital_deployed > net_capital_in*0.7 else "#F39C12"
c7  = warn_clr(cash_recovery, g=50, o=20)
c8  = warn_clr(break_even, g=100, o=50)
c9  = "#27AE60" if remaining < total_procured*0.5 else "#F39C12"
c10 = warn_clr(stock_sold_pct, g=70, o=30)
c11 = "#27AE60" if avg_days < 45 else "#F39C12" if avg_days < 90 else "#E74C3C"
c12 = "#1B3A6B"

C_NAVY="#1B3A6B"; C_BLUE="#2471A3"; C_GREEN="#27AE60"
C_ORANGE="#E67E22"; C_RED="#E74C3C"; C_PURPLE="#9B59B6"; C_GREY="#95A5A6"

# ============================================================
#  HEADER
# ============================================================
logo_col, title_col = st.columns([1, 7])
with logo_col:
    try:
        r = requests.get("https://raw.githubusercontent.com/KATLLC/it-asset-dashboard/main/logo.png", timeout=5)
        if r.status_code == 300:
            st.image(Image.open(BytesIO(r.content)), width=160)
    except: pass

with title_col:
    st.markdown(f"""<div style="background:linear-gradient(135deg,#0F2B46 0%,#1B4F72 60%,#2471A3 100%);border-radius:14px;padding:18px 24px;display:flex;justify-content:space-between;align-items:center;"><div><div style="color:white;font-size:20px;font-weight:700;font-family:Arial,sans-serif;">📊 P&L Executive Dashboard</div><div style="color:rgba(255,255,255,0.55);font-size:11px;margin-top:4px;font-family:Arial,sans-serif;">IT Asset Trading &nbsp;·&nbsp; Procurement → Shipment → Clearing → Sales &nbsp;·&nbsp; {now}</div></div><div style="background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.25);border-radius:20px;padding:5px 14px;color:white;font-size:11px;font-weight:600;font-family:Arial,sans-serif;">🟢 LIVE DATA</div></div>""", unsafe_allow_html=True)

# ============================================================
#  ROW 1: THE BOTTOM LINE
# ============================================================
st.markdown('<div class="row-label">📈 The Bottom Line</div>', unsafe_allow_html=True)
r1a, r1b, r1c, r1d = st.columns(4)
with r1a: st.markdown(kpi_card("💰 Total Revenue", fmt(total_revenue), "All sales recorded", c1), unsafe_allow_html=True)
with r1b: st.markdown(kpi_card("📈 Gross Profit", fmt(gross_profit), "Revenue minus landed cost", c2), unsafe_allow_html=True)
with r1c: st.markdown(kpi_card("🎯 Net Margin %", fmtp(net_margin), "Target > 25%", c3), unsafe_allow_html=True)
with r1d: st.markdown(kpi_card("🔄 ROI %", fmtp(roi_pct), "Target > 30%", c4), unsafe_allow_html=True)

# ============================================================
#  ROW 2: CASH POSITION
# ============================================================
st.markdown('<div class="row-label">💵 Cash Position</div>', unsafe_allow_html=True)
r2a, r2b, r2c, r2d = st.columns(4)
with r2a: st.markdown(kpi_card("✅ Available Buying Power", fmt(avail_buying), f"Of {fmt(net_capital_in)} total capital", c5), unsafe_allow_html=True)
with r2b: st.markdown(kpi_card("🔒 Capital Deployed", fmt(capital_deployed), "Locked in unsold stock", c6), unsafe_allow_html=True)
with r2c: st.markdown(kpi_card("💹 Cash Recovery Rate", fmtp(cash_recovery), "Revenue / Net Capital In", c7), unsafe_allow_html=True)
with r2d: st.markdown(kpi_card("🎯 Break Even Progress", fmtp(break_even), "100% = break even", c8), unsafe_allow_html=True)

# ============================================================
#  ROW 3: STOCK HEALTH
# ============================================================
st.markdown('<div class="row-label">📦 Stock Health</div>', unsafe_allow_html=True)
days_label = "Good" if avg_days < 45 else "Aging" if avg_days < 90 else "Action needed"
r3a, r3b, r3c, r3d = st.columns(4)
with r3a: st.markdown(kpi_card("🏭 Units Remaining", f"{int(remaining):,}", f"Of {int(total_procured):,} procured", c9), unsafe_allow_html=True)
with r3b: st.markdown(kpi_card("📤 Stock Sold %", fmtp(stock_sold_pct), f"Target > 70% | {int(total_sold):,} sold", c10), unsafe_allow_html=True)
with r3c: st.markdown(kpi_card("📅 Avg Days in Stock", f"{avg_days} days", days_label, c11), unsafe_allow_html=True)
with r3d: st.markdown(kpi_card("🔢 Landed Cost / Unit", fmt(avg_unit), "True cost per unit", c12), unsafe_allow_html=True)

# ============================================================
#  BUYING POWER BAR
# ============================================================
st.markdown("---")
st.markdown('<div class="row-label">💵 Auction Buying Power</div>', unsafe_allow_html=True)
pct_avail = (avail_buying/net_capital_in*100) if net_capital_in > 0 else 0
pct_sp = max(100 - pct_avail, 1)
pct_av = max(pct_avail, 1)

st.markdown(f"""<div style="background:white;border-radius:12px;padding:16px 18px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:12px;"><div style="display:flex;justify-content:space-between;margin-bottom:8px;"><span style="color:#7F8C8D;font-size:11px;font-weight:600;font-family:Arial,sans-serif;">Budget Utilization</span><span style="color:#1B3A6B;font-size:11px;font-weight:700;font-family:Arial,sans-serif;">{fmtp(100-pct_avail)} deployed | {fmtp(pct_avail)} available</span></div><div style="display:flex;height:14px;border-radius:8px;overflow:hidden;"><div style="width:{pct_sp:.1f}%;background:linear-gradient(90deg,#E67E22,#D35400);"></div><div style="width:{pct_av:.1f}%;background:linear-gradient(90deg,#27AE60,#1E8449);"></div></div><div style="display:flex;gap:20px;margin-top:8px;"><div style="display:flex;align-items:center;gap:5px;font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;"><div style="width:8px;height:8px;border-radius:50%;background:#E67E22;"></div>Spent: {fmt(proc_spend)}</div><div style="display:flex;align-items:center;gap:5px;font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;"><div style="width:8px;height:8px;border-radius:50%;background:#27AE60;"></div>Available: {fmt(avail_buying)}</div><div style="display:flex;align-items:center;gap:5px;font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;"><div style="width:8px;height:8px;border-radius:50%;background:#1B3A6B;"></div>Total Capital: {fmt(net_capital_in)}</div></div></div>""", unsafe_allow_html=True)

# ============================================================
#  INVENTORY BAR
# ============================================================
st.markdown('<div class="row-label">📦 Inventory Pipeline</div>', unsafe_allow_html=True)
ps = max(float(stock_sold_pct), 1)
pr = max(float(100 - stock_sold_pct), 1)

st.markdown(f"""<div style="background:white;border-radius:12px;padding:16px 18px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:12px;"><div style="display:flex;justify-content:space-between;margin-bottom:8px;"><span style="color:#7F8C8D;font-size:11px;font-weight:600;font-family:Arial,sans-serif;">Stock Movement</span><span style="color:#1B3A6B;font-size:11px;font-weight:700;font-family:Arial,sans-serif;">{fmtp(stock_sold_pct)} sold</span></div><div style="display:flex;height:14px;border-radius:8px;overflow:hidden;"><div style="width:{ps:.1f}%;background:linear-gradient(90deg,#27AE60,#1E8449);"></div><div style="width:{pr:.1f}%;background:linear-gradient(90deg,#E67E22,#D35400);"></div></div><div style="display:flex;gap:20px;margin-top:8px;"><div style="display:flex;align-items:center;gap:5px;font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;"><div style="width:8px;height:8px;border-radius:50%;background:#27AE60;"></div>Sold: {int(total_sold):,} units</div><div style="display:flex;align-items:center;gap:5px;font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;"><div style="width:8px;height:8px;border-radius:50%;background:#E67E22;"></div>Remaining: {int(remaining):,} units ({fmt(capital_deployed)} at cost)</div><div style="display:flex;align-items:center;gap:5px;font-size:10px;color:#7F8C8D;font-family:Arial,sans-serif;"><div style="width:8px;height:8px;border-radius:50%;background:#1B3A6B;"></div>Total: {int(total_procured):,} units</div></div></div>""", unsafe_allow_html=True)

# ============================================================
#  CHARTS
# ============================================================
st.markdown("---")
ch1, ch2 = st.columns(2)

cost_purchase = to_n(df_landed.iloc[:, 9]).sum()
cost_usa = to_n(df_landed.iloc[:, 10]).sum() + to_n(df_landed.iloc[:, 11]).sum()
cost_freight = to_n(df_landed.iloc[:, 16]).sum()
cost_duty = to_n(df_landed.iloc[:, 18]).sum()
cost_agent = to_n(df_landed.iloc[:, 20]).sum()
cost_local = to_n(df_landed.iloc[:, 22]).sum()
cost_other = to_n(df_landed.iloc[:, 24]).sum()

with ch1:
    st.markdown('<div class="row-label">💸 Cost Structure</div>', unsafe_allow_html=True)
    lb = ["Purchase","USA Costs","Freight","Customs Duty","Agent Fee","Local Transport","Other"]
    vl = [cost_purchase,cost_usa,cost_freight,cost_duty,cost_agent,cost_local,cost_other]
    cl = [C_NAVY,C_BLUE,C_ORANGE,C_RED,C_PURPLE,C_GREEN,C_GREY]
    nz = [(l,v,c) for l,v,c in zip(lb,vl,cl) if v > 0]
    if not nz: nz = [("Purchase", max(cost_purchase,1), C_NAVY)]
    fig = go.Figure(go.Pie(labels=[x[0] for x in nz], values=[x[1] for x in nz], hole=0, marker=dict(colors=[x[2] for x in nz], line=dict(color="white",width=3)), textinfo="percent+label", textfont=dict(size=11,color="white")))
    fig.update_layout(height=320, paper_bgcolor="white", showlegend=True, margin=dict(t=20,b=20,l=20,r=20), legend=dict(font=dict(size=10,color=C_NAVY)))
    st.plotly_chart(fig, use_container_width=True)

with ch2:
    st.markdown('<div class="row-label">🏗️ How Cost Builds Up</div>', unsafe_allow_html=True)
    my = max(landed_cost*1.4, 10)
    fig2 = go.Figure(go.Waterfall(orientation="v", measure=["relative","relative","relative","relative","relative","relative","total"], x=["Purchase","USA\nPrep","Freight","Customs\nDuty","Agent\nFees","Local\nTrans","TOTAL\nLANDED"], y=[cost_purchase,cost_usa,cost_freight,cost_duty,cost_agent,cost_local,0], text=[fmt(cost_purchase),fmt(cost_usa),fmt(cost_freight),fmt(cost_duty),fmt(cost_agent),fmt(cost_local),fmt(landed_cost)], textposition="outside", textfont=dict(size=10,color=C_NAVY), connector=dict(line=dict(color="#E8ECF1",width=1,dash="dot")), increasing=dict(marker=dict(color="rgba(36,113,163,0.85)")), decreasing=dict(marker=dict(color="rgba(231,76,60,0.85)")), totals=dict(marker=dict(color="rgba(27,58,107,0.90)"))))
    fig2.update_layout(height=320, paper_bgcolor="white", plot_bgcolor="#FAFBFD", showlegend=False, margin=dict(t=20,b=60,l=60,r=40), yaxis=dict(gridcolor=C_GREY,range=[0,my],tickfont=dict(size=9)), xaxis=dict(tickfont=dict(size=9)))
    st.plotly_chart(fig2, use_container_width=True)

# ============================================================
#  GAUGES
# ============================================================
st.markdown('<div class="row-label">📊 Business Health Gauges</div>', unsafe_allow_html=True)
cr = (remaining/total_procured*100) if total_procured > 0 else 100
fg = go.Figure()
fg.add_trace(go.Indicator(mode="gauge+number", value=float(stock_sold_pct), title={"text":f"<b>Stock Sold</b><br><span style='font-size:11px;color:#7F8C8D;'>{int(total_sold):,} of {int(total_procured):,} units</span>","font":{"size":13,"color":C_NAVY}}, number={"suffix":"%","font":{"size":28,"color":C_NAVY}}, gauge={"axis":{"range":[0,100],"dtick":25,"tickfont":{"size":9,"color":C_GREY}}, "bar":{"color":C_GREEN,"thickness":0.3}, "bgcolor":"#F0F3F8","borderwidth":0, "steps":[{"range":[0,25],"color":"#FADBD8"},{"range":[25,50],"color":"#FCF3CF"},{"range":[50,75],"color":"#D5F5E3"},{"range":[75,100],"color":"#ABEBC6"}], "threshold":{"line":{"color":C_NAVY,"width":2},"thickness":0.75,"value":float(stock_sold_pct)}}, domain={"x":[0.05,0.45],"y":[0.05,0.95]}))
fg.add_trace(go.Indicator(mode="gauge+number", value=float(break_even), title={"text":f"<b>Break Even Progress</b><br><span style='font-size:11px;color:#7F8C8D;'>100% = break even</span>","font":{"size":13,"color":C_NAVY}}, number={"suffix":"%","font":{"size":28,"color":C_BLUE}}, gauge={"axis":{"range":[0,150],"dtick":25,"tickfont":{"size":9,"color":C_GREY}}, "bar":{"color":C_BLUE,"thickness":0.3}, "bgcolor":"#F0F3F8","borderwidth":0, "steps":[{"range":[0,50],"color":"#FADBD8"},{"range":[50,100],"color":"#FCF3CF"},{"range":[100,150],"color":"#D5F5E3"}], "threshold":{"line":{"color":C_GREEN,"width":3},"thickness":0.75,"value":100}}, domain={"x":[0.55,0.95],"y":[0.05,0.95]}))
fg.update_layout(height=280, paper_bgcolor="white", margin=dict(t=40,b=20,l=30,r=30))
st.plotly_chart(fg, use_container_width=True)

# ============================================================
#  LOT TABLE
# ============================================================
st.markdown("---")
st.markdown('<div class="row-label">📋 Lot Detail — Full Breakdown</div>', unsafe_allow_html=True)

if len(df_landed) > 0:
    ci = 
