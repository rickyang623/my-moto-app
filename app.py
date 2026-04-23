import streamlit as st
import pandas as pd
from datetime import date
from PIL import Image

# 設定頁面
st.set_page_config(page_title="MyMoto99 v4", page_icon="🛵", layout="wide")

# 模擬資料與油價
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}
if 'logs' not in st.session_state:
    st.session_state.logs = pd.DataFrame(columns=["日期", "類別", "里程", "金額", "細目", "照片"])

# 頂部導覽
tab1, tab2, tab3 = st.tabs(["📊 儀表板", "⛽ 加油紀錄", "🔧 維修紀錄"])

# --- 1. 儀表板 (新增照片預覽功能) ---
with tab1:
    st.title("🛵 小迪 狀態中心")
    curr_km = st.session_state.logs['里程'].max() if not st.session_state.logs.empty else 0
    st.metric("總累計里程", f"{curr_km} km")
    
    st.write("---")
    st.subheader("📝 最近紀錄明細")
    if not st.session_state.logs.empty:
        # 顯示表格，但不顯示照片的原始數據，只顯示文字
        display_df = st.session_state.logs.drop(columns=['照片'])
        st.dataframe(display_df.sort_values("日期", ascending=False), use_container_width=True)
    else:
        st.info("目前尚無紀錄，快去加油或維修吧！")

# --- 2. 加油紀錄 (含照片上傳) ---
with tab2:
    st.subheader("⛽ 新增加油")
    with st.form("fuel_form", clear_on_submit=True):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            f_date = st.date_input("加油日期", date.today())
            f_type = st.selectbox("燃料種類", list(GAS_PRICES.keys()))
            f_total = st.number_input("加油金額 ($)", min_value=0)
        with f_col2:
            f_km = st.number_input("本次里程 (km)", min_value=int(curr_km))
            f_photo = st.file_uploader("拍下收據 (選填)", type=["jpg", "png", "jpeg"])
        
        if st.form_submit_button("儲存加油紀錄"):
            calc_L = round(f_total / GAS_PRICES[f_type], 2) if f_total > 0 else 0
            new_log = {
                "日期": f_date, "類別": "加油", "里程": f_km, 
                "金額": f_total, "細目": f"{f_type} / {calc_L}L", "照片": f_photo
            }
            st.session_state.logs = pd.concat([st.session_state.logs, pd.DataFrame([new_log])], ignore_index=True)
            st.success("⛽ 加油紀錄已儲存！")

# --- 3. 維修紀錄 (含照片上傳) ---
with tab3:
    st.subheader("🔧 新增維修/保養")
    with st.form("maint_form", clear_on_submit=True):
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            m_date = st.date_input("維修日期", date.today())
            m_item = st.text_input("維修項目", placeholder="例如：換機油、換後輪")
            m_cost = st.number_input("維修費用 ($)", min_value=0)
        with m_col2:
            m_km = st.number_input("維修里程 (km)", min_value=int(curr_km))
            m_photo = st.file_uploader("拍下零件或收據 (選填)", type=["jpg", "png", "jpeg"])
            
        if st.form_submit_button("儲存維修紀錄"):
            new_log = {
                "日期": m_date, "類別": "維修", "里程": m_km, 
                "金額": m_cost, "細目": m_item, "照片": m_photo
            }
            st.session_state.logs = pd.concat([st.session_state.logs, pd.DataFrame([new_log])], ignore_index=True)
            st.success("🔧 維修紀錄已儲存！")
