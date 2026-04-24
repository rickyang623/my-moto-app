import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import pytz
import uuid

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 GS-v25", page_icon="🛵", layout="centered")

# --- Google Sheets 連線引擎 ---
def get_gspread_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    # 從 Streamlit Secrets 讀取憑證
    creds_dict = st.secrets["gsheet"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

try:
    client = get_gspread_client()
    sh = client.open_by_key(st.secrets["gsheet"]["spreadsheet_id"])
    wks = sh.worksheet("master")
except Exception as e:
    st.error(f"連線至 Google Sheets 失敗，請檢查設定: {e}")
    st.stop()

# 2. 數據載入 (✨ Google Sheets 讀取極快且穩定)
def load_data():
    data = pd.DataFrame(wks.get_all_records())
    if not data.empty:
        data['日期'] = pd.to_datetime(data['日期'], errors='coerce')
        data = data.dropna(subset=['日期']).sort_values("日期", ascending=False).reset_index(drop=True)
    return data

df = load_data()

# 3. 介面與功能
TAIPEI_TZ = pytz.timezone('Asia/Taipei')
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

tab1, tab2 = st.tabs(["🏠 首頁紀錄", "➕ 新增紀錄"])

with tab1:
    if not df.empty:
        st.metric("目前里程", f"{df['里程'].max()} km")
        for index, row in df.head(20).iterrows():
            icon = "⛽" if row['類別'] == "加油" else "🛠️"
            if st.button(f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | ${row['金額']}", key=f"r_{index}", use_container_width=True):
                st.write(f"**詳細內容：** {row['細目']}")
                st.write(f"**備註：** {row['備註']}")
    else:
        st.info("目前還沒有資料。")

with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", datetime.now(TAIPEI_TZ).date())
        a_time = c2.time_input("時間", datetime.now(TAIPEI_TZ).time())
        a_km = st.number_input("里程 (km)", value=int(df['里程'].max() if not df.empty else 0))
        
        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
            a_amt = st.number_input("金額 ($)", min_value=0)
            if st.form_submit_button("🚀 儲存加油", use_container_width=True):
                dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
                # ✨ 寫入 Google Sheets 只需這一行，超穩定！
                wks.append_row([dt, "加油", a_km, a_amt, f"{a_type}/{calc_L}L", "No", "", "", str(uuid.uuid4())])
                st.success("存檔成功！")
                st.rerun()
        else:
            a_items = st.text_area("保養項目")
            a_total = st.number_input("總金額", min_value=0)
            a_shop = st.text_input("施工店家")
            if st.form_submit_button("💾 儲存保養", use_container_width=True):
                dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                wks.append_row([dt, "保養", a_km, a_total, a_items, "No", "", a_shop, str(uuid.uuid4())])
                st.success("保養紀錄已存入雲端試算表！")
                st.rerun()
