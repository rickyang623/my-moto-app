import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v14.2", page_icon="🛵", layout="centered")

# --- CSS 魔法：讓按鈕變小、跟文字置中對齊 ---
st.markdown("""
<style>
    /* 讓 columns 裡面的內容垂直置中 */
    [data-testid="stHorizontalBlock"] {
        align-items: center;
    }
    /* 讓 icon 按鈕看起來像文字的一部分 */
    .stButton>button {
        padding: 0px 8px !important;
        height: 24px !important;
        line-height: 24px !important;
        font-size: 12px !important;
        border-radius: 4px !important;
    }
</style>
""", unsafe_allow_html=True)

REPO_NAME = "rickyang623/my-moto-app"
FILE_PATH = "data.csv"
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# 2. 登入 GitHub 與載入資料 (維持 v14.0 邏輯)
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
    if '漏記' not in data.columns: data['漏記'] = 'No'
    data['日期'] = pd.to_datetime(data['日期'])
    data = data.sort_values("日期", ascending=False).reset_index(drop=True)
    return data, file_content.sha

df, file_sha = load_data()

# 3. 彈窗編輯 (維持 v14.0 邏輯)
@st.dialog("📝 編輯紀錄")
def edit_dialog(index, row_data):
    current_dt = row_data['日期']
    with st.form("edit_form"):
        f_date = st.date_input("日期", current_dt.date())
        f_time = st.time_input("時間", current_dt.time())
        f_type = st.selectbox("油種", list(GAS_PRICES.keys()))
        f_amt = st.number_input("金額 ($)", min_value=0, value=int(row_data['金額']))
        f_km = st.number_input("里程 (km)", min_value=0, value=int(row_data['里程']))
        f_miss = st.checkbox("本次紀錄前有漏掉次數", value=(row_data['漏記'] == 'Yes'))
        
        calc_L = round(f_amt / GAS_PRICES[f_type], 2) if f_amt > 0 else 0.0
        if st.form_submit_button("💾 確認更新", use_container_width=True):
            full_dt = datetime.combine(f_date, f_time).strftime('%Y-%m-%d %H:%M')
            df.loc[index] = {
                "日期": pd.to_datetime(full_dt), "類別": "加油", 
                "里程": f_km, "金額": f_amt, "細目": f"{f_type}/{calc_L}L",
                "漏記": "Yes" if f_miss else "No"
            }
            final_df = df.sort_values("日期", ascending=False)
            final_df['日期'] = final_df['日期'].dt.strftime('%Y-%m-%d %H:%M')
            repo.update_file(FILE_PATH, "Edit", final_df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
            st.cache_data.clear()
            st.rerun()

    st.write("---")
    if st.button("🗑️ 刪除紀錄", use_container_width=True, type="secondary"):
        new_df = df.drop(index).reset_index(drop=True)
        new_df['日期'] = new_df['日期'].dt.strftime('%Y-%m-%d %H:%M')
        repo.update_file(FILE_PATH, "Delete", new_df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
        st.cache_data.clear()
        st.rerun()

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "⛽ 新增加油"])

with tab1:
    st.write("🛵 <span style='font-size: 14px; color: gray;'>小迪</span>", unsafe_allow_html=True)
    
    # 儀表板數據
    avg_eff = "--"
    latest_km = df['里程'].max() if not df.empty else 0
    if len(df) >= 2 and df.iloc[0]['漏記'] == 'No':
        try:
            prev_liters = float(re.findall(r"(\d+\.\d+)L", df.iloc[1]['細目'])[0])
            avg_eff = f"{round((df.iloc[0]['里程'] - df.iloc[1]['里程']) / prev_liters, 2)} km/L"
        except: pass

    m_col1, m_col2 = st.columns(2)
    m_col1.metric("目前里程", f"{latest_km} km")
    m_col2.metric("平均油耗", avg_eff)
    
    st.divider()
    
    # --- 整合式單列紀錄清單 ---
    items_per_page = 10 # 再次提高顯示密度
    total_pages = (len(df) // items_per_page) + (1 if len(df) % items_per_page > 0 else 0)
    page = st.select_slider("頁碼", options=range(1, total_pages + 1), value=1) if total_pages > 1 else 1
    
    start_idx = (page - 1) * items_per_page
    
    for index, row in df.iloc[start_idx : start_idx + items_per_page].iterrows():
        # 關鍵：將 columns 分配得更極致 [日期+漏記, 資訊, 小按鈕]
        c_main, c_icon = st.columns([8, 1])
        
        # 1. 主資訊欄 (日期 + 資訊)
        with c_main:
            dt_str = row['日期'].strftime('%m/%d %H:%M')
            miss_tag = "⚠️" if row['漏記'] == 'Yes' else ""
            
            # 使用 markdown 讓資訊排在同一行，並調整大小
            info_html = f"""
            <div style='font-size:14px;'>
                <b>{dt_str}</b>{miss_tag} | 
                <span style='color:green;background-color:#e6ffe6;padding:1px 4px;border-radius:3px;'>{row['里程']}k</span> | 
                <span style='color:blue;background-color:#e6f3ff;padding:1px 4px;border-radius:3px;'>${row['金額']}</span> | 
                <span style='color:gray;'>{row['細目'].split('/')[0]}</span>
            </div>
            """
            st.markdown(info_html, unsafe_allow_html=True)
        
        # 2. 小圖示按鈕欄
        # 使用 use_container_width=False 並縮小按鈕
        if c_icon.button("📝", key=f"btn_{index}", help="編輯紀錄"):
            edit_dialog(index, row)
        
        st.write('<div style="margin-top:-10px; opacity:0.2;"><hr/></div>', unsafe_allow_html=True)

# (Tab 2 與 v14.0 相同，省略不贅述)
