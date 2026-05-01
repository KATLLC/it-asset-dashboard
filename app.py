import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests
from PIL import Image
from io import BytesIO

st.set_page_config(page_title="P&L Executive Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.main {background-color: #F4F7FB;}
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 1rem;}
.row-label {color: #1B3A6B; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; padding-left: 8px; border-left: 3px solid #3498DB; margin: 16px 0 10px 0; font-family: Arial, sans-serif;}
hr {border-color: #E8ECF1; margin: 12px 0;}
</style>
""", unsafe_allow_html=True)

credentials = st.secrets["gcp_service_account"]
creds = Credentials.from_service_account_info(credentials, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
gc = gspread.authorize(creds)
sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1kLIT79DBtG13nlOEkvrWe0FauQVOLi9IxMcYbLpdWL4")

@st.cache_data(ttl=600)
def get_data(name, h_row=4, d_row=6):
    try:
        ws = sh.worksheet(name)
        v = ws.get_all_values()
        df = pd.DataFrame(v[d_row-1:], columns=v[h_row-1])
        return df.replace("", pd.NA).dropna(how="all").fillna("")
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

df_proc = get_data("PROCUREMENT")
df_landed = get_data("LANDED COST ANALYSIS")
df_sales = get_data("SALES")
df_cap = get_data("CAPITAL LOG", h_row=3, d_row=4)

def to_n(s):
    return pd.to_numeric(s.astype(str).str.replace("$","",regex=False).str.replace(",","",regex=False).str.replace("%","",regex=False).str.strip(), errors="coerce").fillna(0)

def fmt(n):
    try: return f"${float(n):,.2f}"
    except: return "$0.00"

def fmtp(n):
    try: return f"{float(n):.1f}%"
    except: return "0.0%"

def scol(df, i):
    return to_n(df.iloc[:, i]) if len(df.columns) > i else pd.Series([0]*max(len(df),1))

def cpos(v):
    try: return "#27AE60" if float(v) >= 0 else "#E74C3C"
    except: return "#1B3A6B"

def cwarn(v, g=70, o=40):
    try:
        x = float(v)
        if x >= g: return "#27AE60"
        elif x >= o: return "#F39C12"
        return "#E74C3C"
    except: return "#1B3A6B"

def card(label, value, sub, color):
    return f'<div style="background:white;border-radius:12px;padding:16px 18px;box-shadow:0 2px 8px rgba(0,0,0,0.06);border-top:4px solid {color};margin-bottom:12px;min-height:108px;"><div style="color:#7A8899;font-size:10px;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;margin-bottom:6px;font-family:Arial;">{label}</div><div style="font-size:18px;font-weight:700;color:{color};margin-bottom:4px;font-family:Arial;line-height:1.25;word-break:break-word;">{value}</div><div style="color:#6C7A89;font-size:10px;font-family:Arial;">{sub}</div></div>'

if not df_proc.empty:
    df_proc = df_proc[df_proc.iloc[:,0].astype(str).str.strip() != ""]
    df_proc = df_proc[df_proc.iloc[:,0].astype(str).str.upper() != "TOTALS"]
if not df_landed.empty:
    df_landed = df_landed[df_landed.iloc[:,0].astype(str).str.strip() != ""]
    df_landed = df_landed[df_landed.iloc[:,0].astype(str).str.upper() != "TOTALS"]
    df_landed = df_landed[~df_landed.iloc[:,0].astype(str).str.contains("From|Lot Number", na=False)]
if not df_sales.empty and len(df_sales.columns) > 10:
    df_sales = df_sales[scol(df_sales, 10) > 0]

total_revenue = scol(df_landed, 28).sum()
landed_cost = scol(df_landed, 26).sum()
gross_profit = scol(df_landed, 29).sum()
net_margin = (gross_profit/total_revenue*100) if total_revenue > 0 else 0
roi_pct = (gross_profit/landed_cost*100) if landed_cost > 0 else 0

net_cap = scol(df_cap, 4).sum()
if net_cap == 0: net_cap = 5110.00
proc_spend = scol(df_proc, 16).sum()
avail_buy = net_cap - proc_spend

total_units = scol(df_landed, 4).sum()
avg_cost = landed_cost/total_units if total_units > 0 else 0
total_proc = scol(df_proc, 6).sum()
total_sold = scol(df_sales, 7).sum()
remaining = total_proc - total_sold

cap_deployed = remaining * avg_cost
cash_recov = (total_revenue/net_cap*100) if net_cap > 0 else 0
brk_even = (total_revenue/landed_cost*100) if landed_cost > 0 else 0
stock_pct = (total_sold/total_proc*100) if total_proc > 0 else 0

try:
    pd_dates = pd.to_datetime(df_proc.iloc[:,1].astype(str), errors="coerce").dropna()
    avg_days = (pd.Timestamp.now() - pd_dates.min()).days if len(pd_dates) > 0 else 0
except: avg_days = 0

cp = scol(df_landed,9).sum()
cu = scol(df_landed,10).sum()+scol(df_landed,11).sum()
cf = scol(df_landed,16).sum()
cd = scol(df_landed,18).sum()
ca = scol(df_landed,20).sum()
cl = scol(df_landed,22).sum()
co = scol(df_landed,24).sum()

now = datetime.now().strftime("%d %b %Y  %H:%M")
pbu = (proc_spend/net_cap*100) if net_cap > 0 else 0
pba = 100 - pbu

c1=cpos(total_revenue); c2=cpos(gross_profit); c3=cpos(net_margin); c4=cpos(roi_pct)
c5=cpos(avail_buy); c6="#E74C3C" if cap_deployed>net_cap*0.7 else "#F39C12"
c7=cwarn(cash_recov,g=50,o=20); c8=cwarn(brk_even,g=100,o=50)
c9="#27AE60" if remaining<total_proc*0.5 else "#F39C12"
c10=cwarn(stock_pct,g=70,o=30)
c11="#27AE60" if avg_days<45 else "#F39C12" if avg_days<90 else "#E74C3C"
c12="#1B3A6B"

CN="#1B3A6B"; CB="#2471A3"; CG="#27AE60"; CO="#E67E22"; CR="#E74C3C"; CP="#9B59B6"; CY="#95A5A6"

# HEADER
lc, tc = st.columns([1, 7])
with lc:
    try:
        r = requests.get("https://raw.githubusercontent.com/KATLLC/it-asset-dashboard/main/logo.png", timeout=5)
        if r.status_code == 200: st.image(Image.open(BytesIO(r.content)), width=160)
    except: pass
with tc:
    st.markdown(f'<div style="background:linear-gradient(135deg,#0F2B46 0%,#1B4F72 60%,#2471A3 100%);border-radius:14px;padding:18px 24px;display:flex;justify-content:space-between;align-items:center;"><div><div style="color:white;font-size:20px;font-weight:700;font-family:Arial;">📊 P&L Executive Dashboard</div><div style="color:rgba(255,255,255,0.60);font-size:11px;margin-top:4px;font-family:Arial;">IT Asset Trading · Procurement → Shipment → Clearing → Sales · {now}</div></div><div style="background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.25);border-radius:20px;padding:5px 14px;color:white;font-size:11px;font-weight:600;">🟢 LIVE DATA</div></div>', unsafe_allow_html=True)

# ROW 1
st.markdown('<div class="row-label">📈 The Bottom Line</div>', unsafe_allow_html=True)
a,b,c,d = st.columns(4)
with a: st.markdown(card("💰 Total Revenue", fmt(total_revenue), "All sales recorded", c1), unsafe_allow_html=True)
with b: st.markdown(card("📈 Gross Profit", fmt(gross_profit), "Revenue minus landed cost", c2), unsafe_allow_html=True)
with c: st.markdown(card("🎯 Net Margin %", fmtp(net_margin), "Target above 25%", c3), unsafe_allow_html=True)
with d: st.markdown(card("🔄 ROI %", fmtp(roi_pct), "Target above 30%", c4), unsafe_allow_html=True)

# ROW 2
st.markdown('<div class="row-label">💵 Cash Position</div>', unsafe_allow_html=True)
a,b,c,d = st.columns(4)
with a: st.markdown(card("✅ Buying Power", fmt(avail_buy), f"Of {fmt(net_cap)} total capital", c5), unsafe_allow_html=True)
with b: st.markdown(card("🔒 Capital Deployed", fmt(cap_deployed), "Locked in unsold stock", c6), unsafe_allow_html=True)
with c: st.markdown(card("💹 Cash Recovery", fmtp(cash_recov), "Revenue / Capital In", c7), unsafe_allow_html=True)
with d: st.markdown(card("🎯 Break Even", fmtp(brk_even), "100% = break even", c8), unsafe_allow_html=True)

# ROW 3
st.markdown('<div 
