import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="P&L Dashboard", layout="wide")

# --- AUTH ---
@st.cache_resource
def get_gc():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

gc = get_gc()
SHEET_URL = "https://docs.google.com/spreadsheets/d/1kLIT79DBtG13nlOEkvrWe0FauQVOLi9IxMcYbLpdWL4"
sh = gc.open_by_url(SHEET_URL)

# --- LOAD DATA ---
@st.cache_data(ttl=600) # Refresh every 10 mins
def load_data(sheet_name, h_row=4, d_row=6):
    ws = sh.worksheet(sheet_name)
    data = ws.get_all_values()
    df = pd.DataFrame(data[d_row-1:], columns=data[h_row-1])
    return df

df_landed = load_data("LANDED COST ANALYSIS")
df_proc = load_data("PROCUREMENT")

# --- CLEANING ---
def to_n(s): return pd.to_numeric(s.str.replace("$","").str.replace(",","").str.replace("%","").str.strip(), errors='coerce').fillna(0)

df_landed['total_landed'] = to_n(df_landed.iloc[:, 26])
df_landed['gross_profit'] = to_n(df_landed.iloc[:, 29])
total_invested = df_landed['total_landed'].sum()
total_profit = df_landed['gross_profit'].sum()

# --- DISPLAY ---
st.title("📊 IT Asset Trading P&L Dashboard")
st.write(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

m1, m2, m3 = st.columns(3)
m1.metric("Total Invested", f"${total_invested:,.2f}")
m2.metric("Net Profit", f"${total_profit:,.2f}")
m3.metric("Lots", len(df_landed[df_landed.iloc[:, 0] != ""]))

# Waterfall Chart
fig = go.Figure(go.Waterfall(
    measure = ["relative", "total"],
    x = ["Purchase", "Total Landed"],
    y = [total_invested, 0],
    connector = {"line":{"color":"rgb(63, 63, 63)"}},
))
st.plotly_chart(fig, use_container_width=True)

st.dataframe(df_landed[df_landed.iloc[:, 0] != ""].iloc[:, [0, 2, 4, 26, 29]])
