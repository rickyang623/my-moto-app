import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date

# 頁面設定
st.set_page_config(page_title="MyMoto99 Cloud", page_icon="🛵", layout="wide")

# 1. 建立 Google Sheets 連線
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 讀取現有資料
try:
    df = conn.read(worksheet="logs", ttl="10m") # 每10分鐘快取一次
except:
    st.error("無法連動雲端試算表，請檢查 Secrets 設定")
    df = pd.DataFrame(columns=["日期", "類別", "里程", "金額", "細目"])

# 模擬油價
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}
curr_km = df['里程'].max() if not df.empty else 0

tab1, tab2, tab3 = st.tabs(["📊 儀表板", "⛽ 加油紀錄", "🔧 維修紀錄"])

with tab1:
    st.title("🛵 小迪 雲端管理中心")
    st.metric("目前總里程", f"{curr_km} km")
    st.write("---")
    st.subheader("📝 雲端紀錄明細 (最新 10 筆)")
    st.dataframe(df.sort_values("日期", ascending=False).head(10), use_container_width=True)

with tab2:
    st.subheader("⛽ 快速記帳")
    with st.form("fuel_form"):
        f_date = st.date_input("日期", date.today())
        f_type = st.selectbox("種類", list(GAS_PRICES.keys()))
        f_total = st.number_input("金額 ($)", min_value=0)
        f_km = st.number_input("里程 (km)", min_value=int(curr_km))
        
        if st.form_submit_button("儲存到雲端"):
            calc_L = round(f_total / GAS_PRICES[f_type], 2) if f_total > 0 else 0
            # 準備新資料
            new_row = pd.DataFrame([{
                "日期": str(f_date),
                "類別": "加油",
                "里程": f_km,
                "金額": f_total,
                "細目": f"{f_type} / {calc_L}L"
            }])
            
            # 更新並寫回 Google Sheets
            updated_df = pd.concat([df, new_row], ignore_index=True)
            conn.update(worksheet="logs", data=updated_df)
            st.success("✅ 資料已同步至 Google Sheets！")
            st.cache_data.clear() # 清除快取以顯示新資料
            st.rerun()
