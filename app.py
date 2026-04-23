import streamlit as st
import pandas as pd
from datetime import date

# 設定頁面與深色調視覺
st.set_page_config(page_title="MyMoto99 v3", page_icon="🛵", layout="wide")

# 模擬從 API 抓取的今日油價 (後續可改為自動爬蟲)
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

# 初始化資料
if 'logs' not in st.session_state:
    st.session_state.logs = pd.DataFrame(columns=["日期時間", "里程", "公升", "金額", "油耗", "種類"])

# --- 頂部導覽頁籤 (仿截圖中間的 儀表板/紀錄/費用統計) ---
tab1, tab2, tab3 = st.tabs(["📊 儀表板", "📝 歷史紀錄", "💰 費用統計"])

with tab1:
    st.title("🛵 小迪 (新迪爵 125)")
    
    # 仿截圖上半部：核心數據
    m_col1, m_col2 = st.columns([1, 1])
    with m_col1:
        st.markdown(f"### 總里程\n# {st.session_state.logs['里程'].max() if not st.session_state.logs.empty else 0} <small>公里</small>", unsafe_allow_html=True)
    with m_col2:
        st.markdown("### 今日油價 (中油)\n" + " | ".join([f"{k}: **{v}**" for k, v in GAS_PRICES.items()]))

    st.divider()

    # 快速新增按鈕區 (仿底部的 + 號功能)
    st.subheader("➕ 快速新增紀錄")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        fuel_type = st.selectbox("燃料種類", list(GAS_PRICES.keys()))
    with c2:
        total_pay = st.number_input("加油總額 ($)", min_value=0, step=10)
    with c3:
        new_km = st.number_input("當前里程 (km)", min_value=0)

    # 自動計算邏輯 (你的需求 3)
    calc_liters = round(total_pay / GAS_PRICES[fuel_type], 2) if total_pay > 0 else 0.0
    st.info(f"💡 自動換算加油量：**{calc_liters} 公升**")

    if st.button("確認儲存紀錄", use_container_width=True):
        # 簡單油耗計算
        last_km = st.session_state.logs['里程'].max() if not st.session_state.logs.empty else new_km
        distance = new_km - last_km
        efficiency = round(distance / calc_liters, 2) if calc_liters > 0 else 0
        
        new_data = {
            "日期時間": date.today(),
            "里程": new_km,
            "公升": calc_liters,
            "金額": total_pay,
            "油耗": efficiency,
            "種類": fuel_type
        }
        st.session_state.logs = pd.concat([st.session_state.logs, pd.DataFrame([new_data])], ignore_index=True)
        st.success(f"紀錄已完成！本次行駛 {distance}km，油耗 {efficiency}km/L")

with tab2:
    st.subheader("📜 加油明細查詢")
    st.table(st.session_state.logs.sort_values("日期時間", ascending=False))

with tab3:
    st.subheader("💸 養車費用統計")
    total_cost = st.session_state.logs['金額'].sum()
    st.write(f"目前累計總加油花費： **NT$ {total_cost}**")
