import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import pytz
import uuid
import re

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v25.4 Pro", page_icon="🛵", layout="centered")

# --- CSS 樣式 (卡片與按鈕美化) ---
st.markdown("""
<style>
    .reportview-container .main .block-container { padding-top: 2rem; }
    div.stButton > button:first-child {
        border-radius: 8px;
        height: 3em;
        width: 100%;
    }
    .stat-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 核心連線引擎 ---
@st.cache_resource
def get_worksheet():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds_info = st.secrets["gsheet"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    client = gspread.authorize(creds)
    try:
        sh = client.open("MyMoto99_Data")
    except:
        sh = client.open_by_key(creds_info["spreadsheet_id"].strip())
    return sh.worksheet("master")

wks = get_worksheet()

# --- 數據加載與處理 ---
def load_data():
    all_rows = wks.get_all_values()
    if len(all_rows) <= 1: return pd.DataFrame()
    data = pd.DataFrame(all_rows[1:], columns=all_rows[0])
    data['日期'] = pd.to_datetime(data['日期'], errors='coerce')
    data['金額'] = pd.to_numeric(data['金額'], errors='coerce').fillna(0)
    data['里程'] = pd.to_numeric(data['里程'], errors='coerce').fillna(0)
    return data.dropna(subset=['日期']).sort_values("日期", ascending=False).reset_index(drop=True)

df = load_data()
TAIPEI_TZ = pytz.timezone('Asia/Taipei')
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

# ----------------- 介面邏輯 -----------------

# --- 編輯/刪除 彈窗 ---
@st.dialog("📋 管理紀錄")
def manage_entry(idx):
    row = df.iloc[idx]
    st.write(f"📅 **日期：** {row['日期'].strftime('%Y-%m-%d %H:%M')}")
    
    with st.form("edit_form"):
        new_km = st.number_input("里程 (km)", value=int(row['里程']))
        new_amt = st.number_input("金額 ($)", value=int(row['金額']))
        new_shop = st.text_input("店家", value=str(row['店家']))
        new_note = st.text_area("備註", value=str(row['備註']))
        
        c1, c2 = st.columns(2)
        save_btn = c1.form_submit_button("💾 儲存修改")
        del_btn = c2.form_submit_button("🗑️ 刪除紀錄", type="secondary")

        if save_btn:
            # 找到該 ID 在 Google Sheets 的位置 (標題是第 1 行，所以是 idx + 2)
            actual_row_idx = idx + 2 
            # 這裡簡單處理：直接更新特定欄位 (里程=C, 金額=D, 備註=G, 店家=H)
            wks.update_cell(actual_row_idx, 3, new_km)
            wks.update_cell(actual_row_idx, 4, new_amt)
            wks.update_cell(actual_row_idx, 7, new_note)
            wks.update_cell(actual_row_idx, 8, new_shop)
            st.success("修改成功！")
            st.rerun()

        if del_btn:
            wks.delete_rows(int(idx + 2))
            st.warning("紀錄已刪除")
            st.rerun()

# ----------------- 主介面 -----------------

st.title("🛵 小迪紀錄 Pro")

tab1, tab2, tab3 = st.tabs(["🏠 儀表板", "➕ 新增", "📊 數據"])

# --- Tab 1: 歷史紀錄 (帶管理功能) ---
with tab1:
    if df.empty:
        st.info("尚無資料")
    else:
        st.write(f"📍 目前里程: **{int(df['里程'].max())} km**")
        for i, row in df.head(15).iterrows():
            icon = "⛽" if row['類別'] == "加油" else "🛠️"
            col_a, col_b = st.columns([4, 1])
            with col_a:
                if st.button(f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | ${int(row['金額'])}", key=f"btn_{i}"):
                    manage_entry(i)
            with col_b:
                st.write(f"**{int(row['里程'])}k**")

# --- Tab 2: 新增紀錄 (原功能) ---
with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    with st.form("add_form", clear_on_submit=True):
        a_date = st.date_input("日期", datetime.now(TAIPEI_TZ).date())
        a_time = st.time_input("時間", datetime.now(TAIPEI_TZ).time())
        a_km = st.number_input("里程 (km)", value=int(df['里程'].max() if not df.empty else 0))
        
        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
            a_amt = st.number_input("金額 ($)", min_value=0)
            a_note = st.text_input("備註")
            if st.form_submit_button("🚀 儲存加油", use_container_width=True):
                dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
                wks.append_row([dt, "加油", a_km, a_amt, f"{a_type}/{calc_L}L", "No", a_note, "", str(uuid.uuid4())])
                st.rerun()
        else:
            a_items = st.text_area("項目")
            a_total = st.number_input("金額 ($)", min_value=0)
            a_shop = st.text_input("店家")
            a_note = st.text_area("備註")
            if st.form_submit_button("💾 儲存保養", use_container_width=True):
                dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                wks.append_row([dt, "保養", a_km, a_total, a_items, "No", a_note, a_shop, str(uuid.uuid4())])
                st.rerun()

# --- Tab 3: 數據統計分析 ---
with tab3:
    if not df.empty:
        # 1. 本月支出
        df['month'] = df['日期'].dt.strftime('%Y-%m')
        current_month = datetime.now(TAIPEI_TZ).strftime('%Y-%m')
        this_month_cost = df[df['month'] == current_month]['金額'].sum()
        
        # 2. 油耗趨勢
        gas_df = df[df['類別'] == '加油'].copy()
        avg_eff = 0
        if len(gas_df) >= 2:
            dist = gas_df['里程'].iloc[0] - gas_df['里程'].iloc[-1]
            # 這裡簡單抓所有加過的公升數
            total_l = sum([float(re.search(r"(\d+\.?\d*)L", str(x)).group(1)) for x in gas_df['細目'] if 'L' in str(x)])
            avg_eff = round(dist / total_l, 1) if total_l > 0 else 0

        c1, c2 = st.columns(2)
        c1.metric("本月總支出", f"${int(this_month_cost)}")
        c2.metric("歷史平均油耗", f"{avg_eff} km/L")
        
        st.write("### 支出比例")
        chart_data = df.groupby('類別')['金額'].sum()
        st.bar_chart(chart_data)
    else:
        st.write("尚無數據可供分析")
