import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="P&L Executive Dashboard", layout="wide")

# --- AUTHENTICATION ---
credentials = st.secrets["gcp_service_account"]
scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(credentials, scopes=scope)
gc = gspread.authorize(creds)

# --- LOAD DATA ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1kLIT79DBtG13nlOEkvrWe0FauQVOLi9IxMcYbLpdWL4"
sh = gc.open_by_url(SHEET_URL)

@st.cache_data(ttl=600)
def get_data(name, h_row=4, d_row=6):
    ws = sh.worksheet(name)
    all_vals = ws.get_all_values()
    df = pd.DataFrame(all_vals[d_row-1:], columns=all_vals[h_row-1])
    return df

# Load Sheets
df_proc = get_data("PROCUREMENT")
df_landed = get_data("LANDED COST ANALYSIS")
df_sales = get_data("SALES")

# --- CLEANING ---
def to_n(s): 
    return pd.to_numeric(s.astype(str).str.replace("$","").str.replace(",","").str.replace("%","").str.strip(), errors="coerce").fillna(0)

landed_cost = to_n(df_landed.iloc[:, 26]).sum()
revenue = to_n(df_landed.iloc[:, 28]).sum()
profit = to_n(df_landed.iloc[:, 29]).sum()
total_procured = to_n(df_proc.iloc[:, 6]).sum()
total_sold = to_n(df_sales.iloc[:, 7]).sum()
remaining = total_procured - total_sold
pct_sold = (total_sold / total_procured * 100) if total_procured > 0 else 0

# --- HEADER ---
st.title("📊 P&L Executive Dashboard")
st.write(f"IT Asset Trading • Last Update: {datetime.now().strftime('%d %b %Y %H:%M')}")

# --- TOP KPI ROW ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Invested", f"${landed_cost:,.2f}")
c2.metric("Revenue", f"${revenue:,.2f}")
c3.metric("Gross Profit", f"${profit:,.2f}")
c4.metric("Inventory Sold", f"{pct_sold:.1f}%")

st.divider()

# --- CHARTS ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🏗️ Landed Cost Build-up")
    purchase = to_n(df_landed.iloc[:, 9]).sum()
    duties = to_n(df_landed.iloc[:, 18]).sum()
    fees = to_n(df_landed.iloc[:, 20]).sum()
    
    fig_wf = go.Figure(go.Waterfall(
        orientation = "v",
        measure = ["relative", "relative", "relative", "total"],
        x = ["Purchase", "Duties", "Fees", "Total Landed"],
        y = [purchase, duties, fees, 0],
        connector = {"line":{"color":"#BDC3C7"}},
        increasing = {"marker":{"color":"#3498DB"}},
        totals = {"marker":{"color":"#1B3A6B"}}
    ))
    st.plotly_chart(fig_wf, use_container_width=True)

with col_right:
    st.subheader("📦 Inventory Status")
    fig_pie = go.Figure(go.Pie(
        labels=["Sold", "Remaining"],
        values=[total_sold, remaining],
        marker=dict(colors=['#27AE60', '#E67E22']),
        hole=0.4
    ))
    st.plotly_chart(fig_pie, use_container_width=True)

# --- DATA TABLE ---
st.subheader("📋 Lot Details")
st.dataframe(df_landed.iloc[:, [0,1,2,4,26,28,29]], use_container_width=True)

st.success("Connected Live to Google Sheets")
