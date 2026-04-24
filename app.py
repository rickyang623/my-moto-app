import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import pytz
import uuid
import re

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v25.3", page_icon="🛵", layout="centered")

# --- CSS 樣式美化 ---
st.markdown("""
<style>
    div.stButton > button:first-child {
        background-color: white !important;
        color: #31333F !important;
        border: 1px solid #e0e0e0 !important;
        padding: 10px 15px !important;
        width: 100% !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
        margin-bottom: 5px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Google Sheets 連線引擎 ---
@st.cache_resource
def get_worksheet():
    # 定義存取權限範圍
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    # 從 Streamlit Secrets 讀取金鑰
    try:
        creds_info = st.secrets["gsheet"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(creds)
        
        # 優先嘗試透過名稱開啟 (避免 ID 複製時的空格問題)
        try:
            sh = client.open("MyMoto99_Data")
        except:
            # 如果名稱找不到，則使用 Secrets 裡的 ID
            ss_id = creds_info["spreadsheet_id"].strip()
            sh = client.open_by_key(ss_id)
            
        # 尋找名稱為 master 的分頁
        all_worksheets = [w.title for w in sh.worksheets()]
        target = next((t for t in all_worksheets if t.strip().lower() == "master"), None)
        
        if target:
            return sh.worksheet(target)
        else:
            st.error(f"❌ 找不到 'master' 分頁！目前偵測到的分頁有：{all_worksheets}")
            st.stop()
    except Exception as e:
        st.error(f"❌ Google Sheets 連線失敗: {e}")
        st.stop()

# 取得工作表實例
wks = get_worksheet()

# 2. 數據載入與清洗
def load_data():
    all_data = wks.get_all_records()
    if not all_data:
        return pd.DataFrame()
    
    data = pd.DataFrame(all_data)
    
    # 確保日期格式正確
    data['日期'] = pd.to_datetime(data['日期'], errors='coerce')
    data = data.dropna(subset=['日期'])
    
    # 按日期排序
    data = data.sort_values("日期", ascending=False).reset_index(drop=True)
    return data

df = load_data()

# 3. 介面與功能
TAIPEI_TZ = pytz.timezone('Asia/Taipei')
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

st.title("🛵 小迪紀錄本")

tab1, tab2 = st.tabs(["🏠 歷史紀錄", "➕ 新增紀錄"])

with tab1:
    if not df.empty:
        # 顯示目前里程
        latest_km = int(df['里程'].max())
        st.metric("目前總里程", f"{latest_km} km")
        
        # 油耗簡易計算
        gas_df = df[df['類別'] == "加油"].reset_index(drop=True)
        if len(gas_df) >= 2:
            try:
                dist = float(gas_df.iloc[0]['里程']) - float(gas_df.iloc[1]['里程'])
                # 解析細目中的公升數 (例如: 92無鉛/5.31L)
                liters_match = re.search(r"(\d+\.?\d*)L", str(gas_df.iloc[1]['細目']))
                if liters_match:
                    liters = float(liters_match.group(1))
                    eff = round(dist / liters, 2)
                    st.write(f"⛽ 上次油耗：**{eff} km/L**")
            except:
                pass
        
        st.divider()
        
        # 列出最近 20 筆紀錄
        for index, row in df.head(20).iterrows():
            icon = "⛽" if row['類別'] == "加油" else "🛠️"
            title = f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | ${int(row['金額'])}"
            with st.expander(title):
                st.write(f"**📍 里程：** {int(row['里程'])} km")
                st.write(f"**📝 項目：** {row['細目']}")
                if row['店家']: st.write(f"**🏠 店家：** {row['店家']}")
                if row['備註']: st.write(f"**💬 備註：** {row['備註']}")
    else:
        st.info("目前還沒有資料，去「新增紀錄」寫下第一筆吧！")

with tab2:
    mode = st.radio("選擇類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    
    with st.form("main_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", datetime.now(TAIPEI_TZ).date())
        a_time = c2.time_input("時間", datetime.now(TAIPEI_TZ).time())
        
        # 自動帶入上次里程
        current_max_km = int(df['里程'].max() if not df.empty else 0)
        a_km = st.number_input("目前里程 (km)", value=current_max_km, step=1)
        
        a_note = st.text_input("備註 (選填)")
        
        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
            a_amt = st.number_input("加油金額 ($)", min_value=0, step=10)
            
            submit = st.form_submit_button("🚀 儲存加油紀錄", use_container_width=True)
            if submit:
                dt_str = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
                
                # 確保 9 個欄位對齊：日期, 類別, 里程, 金額, 細目, 漏記, 備註, 店家, id
                wks.append_row([
                    dt_str, "加油", a_km, a_amt, f"{a_type}/{calc_L}L", 
                    "No", a_note, "", str(uuid.uuid4())
                ])
                st.success("✅ 加油紀錄已同步至雲端！")
                st.rerun()
                
        else:
            a_items = st.text_area("保養項目 (例如：機油、齒輪油)")
            a_total = st.number_input("保養總金額 ($)", min_value=0, step=50)
            a_shop = st.text_input("施工店家")
            
            submit = st.form_submit_button("💾 儲存保養紀錄", use_container_width=True)
            if submit:
                dt_str = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                
                # 確保 9 個欄位對齊：日期, 類別, 里程, 金額, 細目, 漏記, 備註, 店家, id
                wks.append_row([
                    dt_str, "保養", a_km, a_total, a_items, 
                    "No", a_note, a_shop, str(uuid.uuid4())
                ])
                st.success("✅ 保養紀錄已同步至雲端！")
                st.rerun()
