import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v17", page_icon="🛵", layout="centered")

# --- CSS 魔法：美化全寬度按鈕紀錄列 ---
st.markdown("""
<style>
    /* 讓按鈕看起來像清單列而非傳統按鈕 */
    div.stButton > button:first-child {
        background-color: white !important;
        color: #31333F !important;
        border: 1px solid #f0f2f6 !important;
        padding: 10px 15px !important;
        text-align: left !important;
        display: block !important;
        width: 100% !important;
        margin-bottom: -10px !important;
        transition: 0.2s;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    }
    div.stButton > button:hover {
        border-color: #ff4b4b !important;
        background-color: #fffafb !important;
    }
    .tag-km { color: #28a745; font-weight: bold; }
    .tag-amt { color: #007bff; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

REPO_NAME = "rickyang623/my-moto-app"
FILE_PATH = "data.csv"
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# 2. 登入 GitHub 與載入資料
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

# 初始化編輯狀態
if 'edit_idx' not in st.session_state:
    st.session_state.edit_idx = None

# 3. 彈窗編輯函式
@st.dialog("📝 編輯紀錄")
def edit_dialog(index):
    row_data = df.iloc[index]
    with st.form("edit_form"):
        f_date = st.date_input("日期", row_data['日期'].date())
        f_time = st.time_input("時間", row_data['日期'].time())
        f_type = st.selectbox("油種", list(GAS_PRICES.keys()))
        f_amt = st.number_input("金額 ($)", min_value=0, value=int(row_data['金額']))
        f_km = st.number_input("里程 (km)", min_value=0, value=int(row_data['里程']))
        f_miss = st.checkbox("本次紀錄前有漏記", value=(row_data['漏記'] == 'Yes'))
        
        calc_L = round(f_amt / GAS_PRICES[f_type], 2) if f_amt > 0 else 0.0
        
        col_s, col_c = st.columns(2)
        if col_s.form_submit_button("💾 更新", use_container_width=True):
            full_dt = datetime.combine(f_date, f_time).strftime('%Y-%m-%d %H:%M')
            df.loc[index] = {
                "日期": pd.to_datetime(full_dt), "類別": "加油", 
                "里程": f_km, "金額": f_amt, "細目": f"{f_type}/{calc_L}L", "漏記": "Yes" if f_miss else "No"
            }
            final_df = df.sort_values("日期", ascending=False)
            final_df['日期'] = final_df['日期'].dt.strftime('%Y-%m-%d %H:%M')
            repo.update_file(FILE_PATH, "Edit", final_df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
            st.cache_data.clear()
            st.session_state.edit_idx = None
            st.rerun()
        if col_c.form_submit_button("❌ 取消", use_container_width=True):
            st.session_state.edit_idx = None
            st.rerun()

    st.write("---")
    if st.button("🗑️ 刪除", use_container_width=True, type="secondary"):
        new_df = df.drop(index).reset_index(drop=True)
        new_df['日期'] = new_df['日期'].dt.strftime('%Y-%m-%d %H:%M')
        repo.update_file(FILE_PATH, "Delete", new_df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
        st.cache_data.clear()
        st.session_state.edit_idx = None
        st.rerun()

# 檢查是否開啟編輯窗
if st.session_state.edit_idx is not None:
    edit_dialog(st.session_state.edit_idx)

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "⛽ 新增加油"])

with tab1:
    st.write("🛵 <span style='font-size: 14px; color: gray;'>小迪</span>", unsafe_allow_html=True)
    
    # 儀表數據計算
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
    st.subheader("📋 紀錄")
    
    items_per_page = 8
    total_pages = max((len(df) // items_per_page) + (1 if len(df) % items_per_page > 0 else 0), 1)
    page = st.select_slider("頁碼", options=range(1, total_pages + 1), value=1) if total_pages > 1 else 1
    
    start_idx = (page - 1) * items_per_page
    
    # 渲染紀錄清單
    for index, row in df.iloc[start_idx : start_idx + items_per_page].iterrows():
        dt = row['日期'].strftime('%m/%d %H:%M')
        miss = "⚠️" if row['漏記'] == 'Yes' else ""
        km = f"{row['里程']}k"
        amt = f"${row['金額']}"
        oil = row['細目'].split('/')[0]
        
        # 關鍵：將內容組合成一個單一的字串作為按鈕 Label
        btn_label = f"{dt}{miss} | {km} | {amt} | {oil}"
        
        # 每個紀錄都是一個佔滿寬度的按鈕
        if st.button(btn_label, key=f"rec_{index}", use_container_width=True):
            st.session_state.edit_idx = index
            st.rerun()

with tab2:
    st.subheader("⛽ 加油紀錄")
    now_taipei = datetime.now(TAIPEI_TZ)
    with st.form("add_form", clear_on_submit=True):
        col_d, col_t = st.columns(2)
        a_date = col_d.date_input("日期", now_taipei.date())
        a_time = col_t.time_input("時間", now_taipei.time())
        a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
        a_amt = st.number_input("金額 ($)", min_value=0, step=10)
        a_km = st.number_input("里程 (km)", min_value=0, value=int(latest_km))
        a_miss = st.checkbox("本次紀錄前有漏記")
        
        a_calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
        st.info(f"💡 自動換算：{a_calc_L} L")
        
        if st.form_submit_button("🚀 儲存紀錄", use_container_width=True):
            if a_km <= latest_km and not df.empty:
                st.error(f"❌ 里程不可少於目前總里程 ({latest_km} km)")
            elif a_amt <= 0:
                st.error("❌ 金額需大於 0")
            else:
                full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                new_row = pd.DataFrame([{"日期": full_dt, "類別": "加油", "里程": a_km, "金額": a_amt, "細目": f"{a_type}/{a_calc_L}L", "漏記": "Yes" if a_miss else "No"}])
                combined_df = pd.concat([df, new_row], ignore_index=True)
                combined_df['日期'] = pd.to_datetime(combined_df['日期'])
                combined_df = combined_df.sort_values("日期", ascending=False)
                combined_df['日期'] = combined_df['日期'].dt.strftime('%Y-%m-%d %H:%M')
                repo.update_file(FILE_PATH, "Add", combined_df.to_csv(index=False), file_sha)
                st.cache_data.clear()
                st.rerun()
