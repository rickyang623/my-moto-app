import pytz # 引入時區套件

# ... 前面代碼維持原樣 ...

with tab2:
    st.subheader("⛽ 加油紀錄")
    
    # 修正時區邏輯：強制抓取台北時間
    tz = pytz.timezone('Asia/Taipei')
    now = datetime.now(tz) # 這裡會精準抓到 13:18
    
    with st.form("add_form", clear_on_submit=True):
        col_d, col_t = st.columns(2)
        a_date = col_d.date_input("日期", now.date())
        a_time = col_t.time_input("時間", now.time())
        
        # ... 後續表單內容 ...
        
        if st.form_submit_button("🚀 儲存紀錄", use_container_width=True):
            # 儲存時也要確保是結合後的台北時間
            local_dt = datetime.combine(a_date, a_time)
            full_dt_str = local_dt.strftime('%Y-%m-%d %H:%M')
            
            # ... 存檔邏輯 ...

import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v13", page_icon="🛵", layout="centered")

REPO_NAME = "rickyang623/my-moto-app"
FILE_PATH = "data.csv"
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

# 2. 登入 GitHub 與讀取資料
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except:
    st.error("GitHub 驗證失敗")
    st.stop()

@st.cache_data(ttl=60)
def load_data():
    file_content = repo.get_contents(FILE_PATH)
    data = pd.read_csv(io.StringIO(file_content.decoded_content.decode('utf-8')))
    # 強制轉換日期格式並排序：由新到舊
    data['日期'] = pd.to_datetime(data['日期'])
    data = data.sort_values("日期", ascending=False).reset_index(drop=True)
    return data, file_content.sha

df, file_sha = load_data()

# 3. 彈窗編輯 (保持原樣，支援細修)
@st.dialog("📝 編輯紀錄")
def edit_dialog(index, row_data):
    current_dt = row_data['日期']
    with st.form("edit_form"):
        f_date = st.date_input("日期", current_dt.date())
        f_time = st.time_input("時間", current_dt.time())
        f_type = st.selectbox("加油種類", list(GAS_PRICES.keys()))
        f_amt = st.number_input("金額 ($)", min_value=0, value=int(row_data['金額']))
        f_km = st.number_input("里程 (km)", min_value=0, value=int(row_data['里程']))
        
        calc_L = round(f_amt / GAS_PRICES[f_type], 2) if f_amt > 0 else 0.0
        if st.form_submit_button("💾 確認更新", use_container_width=True):
            full_dt = datetime.combine(f_date, f_time).strftime('%Y-%m-%d %H:%M')
            df.iloc[index] = {"日期": full_dt, "類別": "加油", "里程": f_km, "金額": f_amt, "細目": f"{f_type}/{calc_L}L"}
            repo.update_file(FILE_PATH, "Edit", df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
            st.cache_data.clear()
            st.rerun()

    if st.button("🗑️ 刪除紀錄", use_container_width=True, type="secondary"):
        new_df = df.drop(index).reset_index(drop=True)
        repo.update_file(FILE_PATH, "Delete", new_df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
        st.cache_data.clear()
        st.rerun()

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "⛽ 新增加油"])

with tab1:
    st.write("🛵 <span style='font-size: 18px;'>小迪</span>", unsafe_allow_html=True)
    
    # 油耗計算 (取排序後的前兩筆)
    if len(df) >= 2:
        latest_km, prev_km = df.iloc[0]['里程'], df.iloc[1]['里程']
        try:
            prev_liters = float(re.findall(r"(\d+\.\d+)L", df.iloc[1]['細目'])[0])
            avg_efficiency = round((latest_km - prev_km) / prev_liters, 2)
        except: avg_efficiency = 0.0
    else:
        latest_km = df['里程'].max() if not df.empty else 0
        avg_efficiency = 0.0

    m_col1, m_col2 = st.columns(2)
    m_col1.metric("目前里程", f"{latest_km} km")
    m_col2.metric("平均油耗", f"{avg_efficiency} km/L")
    
    st.divider()
    st.subheader("📋 紀錄")
    
    # 分頁邏輯：每頁 5 筆
    items_per_page = 5
    total_pages = (len(df) // items_per_page) + (1 if len(df) % items_per_page > 0 else 0)
    
    if total_pages > 1:
        page = st.number_input("頁碼", min_value=1, max_value=total_pages, step=1)
    else:
        page = 1
        
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    
    for index, row in df.iloc[start_idx:end_idx].iterrows():
        with st.container(border=True):
            c1, c2 = st.columns([3, 2])
            c1.write(f"📅 **{row['日期'].strftime('%Y-%m-%d %H:%M')}**")
            c2.write(f"💰 **${row['金額']}**")
            c3, c4 = st.columns([1, 1])
            c3.write(f"📍 `{row['里程']} km`")
            c4.write(f"⛽ {row['細目']}")
            if st.button("編輯", key=f"btn_{index}", use_container_width=True):
                edit_dialog(index, row)

with tab2:
    st.subheader("⛽ 加油紀錄")
    # 補登情境：預設當下，但可手動調整
    now = datetime.now()
    
    with st.form("add_form", clear_on_submit=True):
        col_d, col_t = st.columns(2)
        a_date = col_d.date_input("日期", now.date())
        a_time = col_t.time_input("時間", now.time())
        
        a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
        a_amt = st.number_input("金額 ($)", min_value=0, step=10)
        a_km = st.number_input("里程 (km)", min_value=0, value=int(latest_km))
        
        a_calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
        st.info(f"💡 自動換算：{a_calc_L} L")
        
        if st.form_submit_button("🚀 儲存紀錄", use_container_width=True):
            if a_km <= latest_km and not df.empty:
                st.error(f"❌ 里程不可少於目前總里程 ({latest_km} km)")
            elif a_amt <= 0:
                st.error("❌ 金額需大於 0")
            else:
                full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                new_row = pd.DataFrame([{"日期": full_dt, "類別": "加油", "里程": a_km, "金額": a_amt, "細目": f"{a_type}/{a_calc_L}L"}])
                new_df = pd.concat([df, new_row], ignore_index=True)
                # 存檔前轉回 string
                new_df['日期'] = new_df['日期'].dt.strftime('%Y-%m-%d %H:%M')
                repo.update_file(FILE_PATH, "Add", new_df.to_csv(index=False), file_sha)
                st.cache_data.clear()
                st.rerun()
