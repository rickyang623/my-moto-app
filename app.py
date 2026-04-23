import streamlit as st
import pandas as pd
from datetime import date

# --- 頁面設定 ---
st.set_page_config(page_title="MyMoto99", page_icon="🛵")

# --- 模擬資料庫 (實際使用時會串接 CSV 或 Google Sheets) ---
if 'vehicle' not in st.session_state:
    st.session_state.vehicle = {"name": "我的愛車", "current_km": 5000, "oil_interval": 1000}
if 'logs' not in st.session_state:
    st.session_state.logs = pd.DataFrame(columns=["日期", "類別", "里程", "公升", "金額"])

# --- 側邊選單 ---
with st.sidebar:
    st.title("🛡️ 導覽選單")
    page = st.radio("前往項目", ["🏠 首頁儀表板", "⛽ 加油紀錄", "🔧 維修紀錄", "⚙️ 車輛設定"])
    st.info(f"當前車輛：{st.session_state.vehicle['name']}")

# --- 1. 首頁儀表板 ---
if page == "🏠 首頁儀表板":
    st.title("🚀 愛車動態儀表板")
    
    # 核心指標
    col1, col2 = st.columns(2)
    col1.metric("目前里程", f"{st.session_state.vehicle['current_km']} km")
    
    # 模擬計算油耗 (拿最後兩次加油)
    fuel_logs = st.session_state.logs[st.session_state.logs['類別'] == "加油"]
    avg_fuel = 42.5 if fuel_logs.empty else 38.2 # 範例數值
    col2.metric("平均油耗", f"{avg_fuel} km/L")

    st.write("---")
    
    # 保養進度條
    st.subheader("🛠️ 耗材更換進度")
    
    # 模擬計算機油剩餘 (假設上次更換是 4500km)
    last_oil_change = 4500 
    oil_used = st.session_state.vehicle['current_km'] - last_oil_change
    oil_ratio = min(oil_used / st.session_state.vehicle['oil_interval'], 1.0)
    
    st.write(f"**機油** (距離上次更換已行駛 {oil_used} km)")
    if oil_ratio >= 0.9:
        st.error(f"⚠️ 剩餘 {1000 - oil_used} km，請儘速更換！")
    st.progress(oil_ratio)

# --- 2. 加油紀錄 ---
elif page == "⛽ 加油紀錄":
    st.title("⛽ 新增加油紀錄")
    with st.form("fuel_form"):
        f_date = st.date_input("加油日期", date.today())
        f_km = st.number_input("本次里程", value=st.session_state.vehicle['current_km'])
        f_L = st.number_input("加油公升數", min_value=0.1)
        f_amt = st.number_input("加油金額", min_value=1)
        if st.form_submit_button("儲存紀錄"):
            st.session_state.vehicle['current_km'] = f_km
            st.success("紀錄已儲存，里程已同步更新！")

# --- 3. 維修紀錄 ---
elif page == "🔧 維修紀錄":
    st.title("🔧 維修保養項目")
    items = st.multiselect("更換項目", ["機油", "齒輪油", "空濾", "輪胎", "皮帶", "洗車"])
    m_km = st.number_input("維修里程", value=st.session_state.vehicle['current_km'])
    m_note = st.text_area("維修備註")
    if st.button("儲存維修資料"):
        st.write("✅ 已記錄：", items)

# --- 4. 車輛設定 ---
elif page == "⚙️ 車輛設定":
    st.title("⚙️ 設定愛車資訊")
    st.session_state.vehicle['name'] = st.text_input("車輛名稱", value=st.session_state.vehicle['name'])
    st.session_state.vehicle['oil_interval'] = st.number_input("機油更換頻率", value=1000)
    st.button("儲存設定")
