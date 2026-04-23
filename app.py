import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz
import uuid
import time

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v24.2", page_icon="🛵", layout="centered")

# --- CSS 魔法 ---
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

REPO_NAME = "rickyang623/my-moto-app"
TAIPEI_TZ = pytz.timezone('Asia/Taipei')
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

# 2. 核心數據引擎 (✨ 強化抓取邏輯)
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except:
    st.error("GitHub 驗證失敗")
    st.stop()

def force_fetch_data(file_name):
    """徹底繞過快取抓取最新檔案"""
    # 通過獲取最新 commit 來確保 SHA 是最新的
    contents = repo.get_contents(file_name, ref=repo.get_branch("main").commit.sha)
    df = pd.read_csv(io.StringIO(contents.decoded_content.decode('utf-8')))
    return df, contents.sha

# 初次載入
try:
    master_df, _ = force_fetch_data("data.csv")
    detail_df, _ = force_fetch_data("service_details.csv")
    master_df['日期'] = pd.to_datetime(master_df['日期'], errors='coerce')
    master_df = master_df.dropna(subset=['日期']).sort_values("日期", ascending=False).reset_index(drop=True)
except:
    st.warning("初始化讀取失敗，請重新整理")
    st.stop()

if 'temp_items' not in st.session_state: st.session_state.temp_items = []
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "➕ 新增紀錄"])

with tab1:
    latest_km = master_df['里程'].max() if not master_df.empty else 0
    st.write(f"🛵 目前里程：**{latest_km} km**")
    
    # 刷新功能直接整合在首頁頂部
    if st.button("🔄 同步雲端最新紀錄", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    for index, row in master_df.head(20).iterrows():
        icon = "⛽" if row['類別'] == '加油' else "🛠️"
        if st.button(f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | ${int(row['金額'])}", key=f"r_{index}", use_container_width=True):
            st.session_state.edit_idx = index
            st.rerun()

with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    now = datetime.now(TAIPEI_TZ)
    
    with st.form("save_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", now.date())
        a_time = c2.time_input("時間", now.time())
        a_km = st.number_input("里程 (km)", value=int(latest_km))
        a_shop = st.text_input("店家") if mode == "🛠️ 保養維修" else ""
        a_note = st.text_area("備註")
        
        # 加油專用
        a_amt = 0
        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
            a_amt = st.number_input("金額", min_value=0)
            
        submit = st.form_submit_button("🚀 確認儲存 (將自動同步最新版本)", use_container_width=True)

    # 保養項目新增 (放在 form 外面)
    if mode == "🛠️ 保養維修":
        if st.button("➕ 新增保養項目", use_container_width=True):
            # ... 彈窗代碼 ... (此處可沿用之前的 add_item_dialog)
            pass

    if submit:
        with st.spinner("📦 正在執行「先讀後寫」保護存檔..."):
            # ✨ 關鍵保護：儲存前那一秒，重新抓取 GitHub 上「真正的」最新版
            real_latest_master, latest_sha_m = force_fetch_data("data.csv")
            real_latest_detail, latest_sha_d = force_fetch_data("service_details.csv")
            
            full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
            rec_id = str(uuid.uuid4())
            
            if mode == "⛽ 加油":
                calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
                new_row = {"日期": full_dt, "類別": "加油", "里程": a_km, "金額": a_amt, "細目": f"{a_type}/{calc_L}L", "漏記": "No", "備註": a_note, "店家": "", "id": rec_id}
                updated_master = pd.concat([real_latest_master, pd.DataFrame([new_row])], ignore_index=True)
                repo.update_file("data.csv", "Add Gas Safe", updated_master.to_csv(index=False), latest_sha_m)
            else:
                # 保養模式比照辦理
                total_sum = sum([i['total'] for i in st.session_state.temp_items])
                summary = ", ".join([i['item_name'] for i in st.session_state.temp_items])
                new_m = {"日期": full_dt, "類別": "保養", "里程": a_km, "金額": total_sum, "細目": summary, "店家": a_shop, "備註": a_note, "id": rec_id}
                updated_master = pd.concat([real_latest_master, pd.DataFrame([new_m])], ignore_index=True)
                
                new_details = []
                for item in st.session_state.temp_items:
                    item['parent_id'] = rec_id
                    new_details.append(item)
                updated_detail = pd.concat([real_latest_detail, pd.DataFrame(new_details)], ignore_index=True)
                
                repo.update_file("data.csv", "Add M Safe", updated_master.to_csv(index=False), latest_sha_m)
                repo.update_file("service_details.csv", "Add D Safe", updated_detail.to_csv(index=False), latest_sha_d)
                st.session_state.temp_items = []

            st.success("✅ 存檔完成！已確保不覆蓋任何既有資料。")
            time.sleep(1.5)
            st.rerun()
