import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import pytz
import uuid
import re

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v25.1", page_icon="🛵", layout="centered")

# --- Google Sheets 連線引擎 (完全移除 GitHub 邏輯) ---
@st.cache_resource
def get_gspread_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gsheet"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

try:
    client = get_gspread_client()
    # 使用 Secrets 裡的 ID 連線
    sh = client.open_by_key(st.secrets["gsheet"]["spreadsheet_id"])
    wks = sh.worksheet("master")
except Exception as e:
    st.error(f"❌ 連線失敗！請確認：\n1. Secrets 格式正確\n2. 已將 client_email 加入 Google Sheet 共用人員")
    st.stop()

# 2. 核心數據處理
def load_data():
    data = pd.DataFrame(wks.get_all_records())
    if not data.empty:
        data['日期'] = pd.to_datetime(data['日期'], errors='coerce')
        data = data.dropna(subset=['日期']).sort_values("日期", ascending=False).reset_index(drop=True)
    return data

df = load_data()

# 3. 介面設定
TAIPEI_TZ = pytz.timezone('Asia/Taipei')
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

st.title("🛵 小迪紀錄本 (GS版)")

tab1, tab2 = st.tabs(["🏠 首頁紀錄", "➕ 新增紀錄"])

with tab1:
    if not df.empty:
        latest_km = df['里程'].max()
        st.metric("目前總里程", f"{latest_km} km")
        
        # 簡單油耗計算
        gas_only = df[df['類別'] == "加油"].copy().reset_index(drop=True)
        if len(gas_only) >= 2:
            try:
                curr_km = float(gas_only.iloc[0]['里程'])
                prev_km = float(gas_only.iloc[1]['里程'])
                # 從細目抓取公升數，例如 "95無鉛/10.5L"
                match = re.search(r"(\d+\.?\d*)L", str(gas_only.iloc[1]['細目']))
                if match:
                    liters = float(match.group(1))
                    eff = round((curr_km - prev_km) / liters, 2)
                    st.write(f"⛽ 上次油耗：**{eff} km/L**")
            except: pass

        st.divider()
        for index, row in df.head(20).iterrows():
            icon = "⛽" if row['類別'] == "加油" else "🛠️"
            with st.expander(f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | ${row['金額']}"):
                st.write(f"**項目：** {row['細目']}")
                if row['店家']: st.write(f"**店家：** {row['店家']}")
                if row['備註']: st.write(f"**備註：** {row['備註']}")
                st.write(f"**里程：** {row['里程']} km")
    else:
        st.info("目前還沒有資料，去新增一筆吧！")

with tab2:
    mode = st.radio("選擇類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    
    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", datetime.now(TAIPEI_TZ).date())
        a_time = c2.time_input("時間", datetime.now(TAIPEI_TZ).time())
        a_km = st.number_input("里程 (km)", value=int(df['里程'].max() if not df.empty else 0))
        
        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
            a_amt = st.number_input("加油金額 ($)", min_value=0)
            a_note = st.text_input("備註")
            if st.form_submit_button("🚀 儲存加油紀錄", use_container_width=True):
                dt_str = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
                # 寫入 master 分頁：日期, 類別, 里程, 金額, 細目, 漏記, 備註, 照片, 店家, id
                wks.append_row([dt_str, "加油", a_km, a_amt, f"{a_type}/{calc_L}L", "No", a_note, "", "", str(uuid.uuid4())])
                st.success("✅ 加油紀錄已同步至 Google Sheets！")
                st.rerun()
        else:
            a_items = st.text_area("保養項目 (例如：機油、齒輪油)")
            a_total = st.number_input("保養總金額 ($)", min_value=0)
            a_shop = st.text_input("施工店家")
            a_note = st.text_area("其他備註")
            if st.form_submit_button("💾 儲存保養紀錄", use_container_width=True):
                dt_str = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                wks.append_row([dt_str, "保養", a_km, a_total, a_items, "No", a_note, "", a_shop, str(uuid.uuid4())])
                st.success("✅ 保養紀錄已同步至 Google Sheets！")
                st.rerun()
