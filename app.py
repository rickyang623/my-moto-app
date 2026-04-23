import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v15", page_icon="🛵", layout="centered")

# --- CSS 魔法：定義真正的單列卡片樣式 ---
st.markdown("""
<style>
    .record-card {
        background-color: white;
        padding: 10px 15px;
        border-radius: 8px;
        border: 1px solid #f0f2f6;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .record-info {
        flex-grow: 1;
        font-size: 14px;
        line-height: 1.4;
        margin-right: 10px;
    }
    .record-date {
        font-weight: bold;
        color: #31333F;
        margin-right: 5px;
    }
    .tag {
        padding: 1px 4px;
        border-radius: 3px;
        font-size: 12px;
        margin: 0 2px;
    }
    .tag-km { color: green; background-color: #e6ffe6; }
    .tag-amt { color: blue; background-color: #e6f3ff; }
    .tag-miss { color: red; background-color: #ffe6e6; }
    
    /* 讓 st.button 看起來像 HTML 按鈕並靠右 */
    div.stButton > button:first-child {
        padding: 0px 10px !important;
        height: 28px !important;
        background-color: #f0f2f6 !important;
        border: 1px solid #d1d5db !important;
        color: #31333F !important;
        font-size: 12px !important;
    }
</style>
""", unsafe_allow_html=True)

REPO_NAME = "rickyang623/my-moto-app"
FILE_PATH = "data.csv"
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# 2. 登入 GitHub 與載入資料 (維持原邏輯)
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

# --- 核心邏輯：處理編輯狀態 ---
# 使用 session_state 來控制哪一筆資料正在被編輯
if 'edit_index' not in st.session_state:
    st.session_state.edit_index = None

# 3. 彈窗編輯 (改為由 session_state 觸發)
@st.dialog("📝 編輯紀錄")
def edit_dialog(index):
    row_data = df.iloc[index]
    current_dt = row_data['日期']
    
    with st.form("edit_form"):
        f_date = st.date_input("日期", current_dt.date())
        f_time = st.time_input("時間", current_dt.time())
        f_type = st.selectbox("油種", list(GAS_PRICES.keys()))
        f_amt = st.number_input("金額 ($)", min_value=0, value=int(row_data['金額']))
        f_km = st.number_input("里程 (km)", min_value=0, value=int(row_data['里程']))
        f_miss = st.checkbox("本次紀錄前有漏掉次數", value=(row_data['漏記'] == 'Yes'))
        
        calc_L = round(f_amt / GAS_PRICES[f_type], 2) if f_amt > 0 else 0.0
        
        col_s, col_c = st.columns(2)
        if col_s.form_submit_button("💾 更新", use_container_width=True):
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
            st.session_state.edit_index = None # 關閉編輯狀態
            st.rerun()
            
        if col_c.form_submit_button("❌ 取消", use_container_width=True):
            st.session_state.edit_index = None
            st.rerun()

    st.write("---")
    if st.button("🗑️ 刪除", use_container_width=True, type="secondary"):
        new_df = df.drop(index).reset_index(drop=True)
        new_df['日期'] = new_df['日期'].dt.strftime('%Y-%m-%d %H:%M')
        repo.update_file(FILE_PATH, "Delete", new_df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
        st.cache_data.clear()
        st.session_state.edit_index = None
        st.rerun()

# --- 檢測是否需要彈出編輯窗 ---
if st.session_state.edit_index is not None:
    edit_dialog(st.session_state.edit_index)

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "⛽ 新增加油"])

with tab1:
    st.write("🛵 <span style='font-size: 14px; color: gray;'>小迪</span>", unsafe_allow_html=True)
    
    # 儀表板數據 (維持原邏輯)
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
    
    # --- 全 HTML 渲染紀錄清單 ---
    items_per_page = 10
    total_pages = (len(df) // items_per_page) + (1 if len(df) % items_per_page > 0 else 0)
    page = st.select_slider("頁碼", options=range(1, total_pages + 1), value=1) if total_pages > 1 else 1
    
    start_idx = (page - 1) * items_per_page
    
    for index, row in df.iloc[start_idx : start_idx + items_per_page].iterrows():
        dt_str = row['日期'].strftime('%m/%d %H:%M')
        miss_tag = "<span class='tag tag-miss'>⚠️漏</span>" if row['漏記'] == 'Yes' else ""
        oil_type = row['細目'].split('/')[0]
        
        # 1. 先用 Columns 建立一個容器，[左邊資訊, 右邊按鈕]
        # 這次我們把比例分得更開 [9, 2]，並限制按鈕不准換行
        c_info, c_btn = st.columns([9, 2])
        
        # 2. 左邊：純 HTML 渲染所有文字資訊
        info_html = f"""
        <div style='line-height:1.5;'>
            <span class='record-date'>{dt_str}</span>{miss_tag}<br/>
            <span class='tag tag-km'>{row['里程']}k</span>
            <span class='tag tag-amt'>${row['金額']}</span>
            <span style='color:gray; font-size:13px;'>{oil_type}</span>
        </div>
        """
        c_info.markdown(info_html, unsafe_allow_html=True)
        
        # 3. 右邊：放置 Streamlit 的原生按鈕，但透過 CSS 強制縮小
        # 並使用垂直置中技巧
        st.write("""<style>div[data-testid="column"]+div[data-testid="column"]{align-self:center;}</style>""", unsafe_allow_html=True)
        if c_btn.button("📝", key=f"btn_{index}"):
            st.session_state.edit_index = index
            st.rerun()
        
        st.write('<div style="margin-top:-10px; opacity:0.1;"><hr/></div>', unsafe_allow_html=True)

# (Tab 2 保持原樣)
