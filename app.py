import streamlit as st
import pandas as pd
from datetime import date

# --- 頁面設定 ---
st.set_page_config(page_title="MyMoto99", page_icon="🛵", layout="wide")

# --- 模擬資料庫 (Session State) ---
if 'vehicle' not in st.session_state:
    st.session_state.vehicle = {"name": "我的愛車", "current_km": 5000, "oil_interval": 1000}
if 'logs' not in st.session_state:
    # 預設一些範例資料方便你看到明細
    st.session_state.logs = pd.DataFrame([
        {"日期": date(2026, 4, 1), "類別": "加油", "里程": 4800, "公升": 5.0, "金額": 150, "油耗": 0.0},
        {"日期": date(2026, 4, 15), "類別": "加油", "里程": 5000, "公升": 4.8, "金額": 145, "油耗": 41.6}
    ])

# --- 頂部導覽頁籤 ---
tab1, tab2, tab3, tab4 = st.tabs(["🏠 首頁儀表板", "⛽ 加油紀錄", "🔧 維修紀錄", "⚙️ 車輛設定"])

# --- 1. 首頁儀表板 ---
with tab1:
    st.title(f"🚀 {st.session_state.vehicle['name']} 狀態")
    col1, col2, col3 = st.columns(3)
    
    current_km = st.session_state.vehicle['current_km']
    col1.metric("目前里程", f"{current_km} km")
    
    # 計算平均油耗
    fuel_df = st.session_state.logs[st.session_state.logs['類別'] == "加油"]
    avg_fuel = fuel_df['油耗'].mean() if not fuel_df.empty else 0
    col2.metric("平均油耗", f"{avg_fuel:.1f} km/L")
    col3.metric("本月花費", f"${fuel_df['金額'].sum():.0f}")

    # 機油進度條
    st.write("---")
    st.subheader("🛠️ 耗材狀態")
    last_oil_km = fuel_df['里程'].max() if not fuel_df.empty else 0
    oil_used = current_km - last_oil_km
    oil_ratio = min(oil_used / st.session_state.vehicle['oil_interval'], 1.0)
    st.write(f"機油 (剩餘 {st.session_state.vehicle['oil_interval'] - oil_used} km)")
    st.progress(oil_ratio)

    # 2. 查詢明細 (你的需求)
    st.write("---")
    st.subheader("📝 近期加油明細")
    st.dataframe(st.session_state.logs.sort_values("日期", ascending=False), use_container_width=True)

# --- 2. 加油紀錄 (你的自動換算需求) ---
with tab2:
    st.subheader("⛽ 快速記帳")
    # 模擬串接中油油價 (這可以手動改或未來寫爬蟲)
    today_price = 30.5 
    st.info(f"今日參考油價 (95無鉛): ${today_price}/L")
    
    with st.form("fuel_form"):
        f_date = st.date_input("加油日期", date.today())
        f_km = st.number_input("本次里程 (km)", value=st.session_state.vehicle['current_km'])
        f_total_price = st.number_input("輸入總金額 ($)", min_value=0)
        
        # 自動計算公升
        auto_liters = round(f_total_price / today_price, 2) if f_total_price > 0 else 0.0
        st.write(f"💡 自動預估公升數: **{auto_liters} L**")
        
        if st.form_submit_button("確認儲存"):
            # 計算本次油耗
            prev_km = st.session_state.logs['里程'].max() if not st.session_state.logs.empty else f_km
            this_fuel_eff = round((f_km - prev_km) / auto_liters, 1) if auto_liters > 0 else 0
            
            # 存入紀錄
            new_log = {"日期": f_date, "類別": "加油", "里程": f_km, "公升": auto_liters, "金額": f_total_price, "油耗": this_fuel_eff}
            st.session_state.logs = pd.concat([st.session_state.logs, pd.DataFrame([new_log])], ignore_index=True)
            st.session_state.vehicle['current_km'] = f_km
            st.success("紀錄成功！")

# --- 3. 維修紀錄 (略) ---
with tab3:
    st.write("維修功能建置中...")

# --- 4. 車車設定 ---
with tab4:
    st.session_state.vehicle['name'] = st.text_input("車輛暱稱", st.session_state.vehicle['name'])
    st.session_state.vehicle['oil_interval'] = st.number_input("機油提醒間隔", value=1000)
