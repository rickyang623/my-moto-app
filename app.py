import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime, date
import io
import re

# 1. 頁面配置 (RWD 原則)
st.set_page_config(page_title="MyMoto99 v11", page_icon="🛵", layout="centered")

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
    return data, file_content.sha

df, file_sha = load_data()

# 3. 彈窗編輯函式
@st.dialog("📝 編輯紀錄")
def edit_dialog(index, row_data):
    try:
        d_date = datetime.strptime(str(row_data['日期']), '%Y-%m-%d').date()
    except:
        d_date = date.today()
        
    with st.form("edit_form"):
        f_date = st.date_input("加油日期", d_date)
        f_type = st.selectbox("加油種類", list(GAS_PRICES.keys()))
        f_amt = st.number_input("加油金額 ($)", min_value=0, value=int(row_data['金額']))
        f_km = st.number_input("當前里程 (km)", min_value=0, value=int(row_data['里程']))
        
        calc_L = round(f_amt / GAS_PRICES[f_type], 2) if f_amt > 0 else 0.0
        st.info(f"💡 自動換算：{calc_L} L")
        
        if st.form_submit_button("💾 確認更新", use_container_width=True):
            df.iloc[index] = {
                "日期": str(f_date), "類別": "加油", "里程": f_km, "金額": f_amt, "細目": f"{f_type}/{calc_L}L"
            }
            repo.update_file(FILE_PATH, "Edit log", df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
            st.success("同步成功")
            st.cache_data.clear()
            st.rerun()

# --- 介面佈局 ---
# 1.「紀錄表」改為「首頁」
tab1, tab2 = st.tabs(["🏠 首頁", "⛽ 新增加油"])

with tab1:
    # 2. 移除數據中心，3. 小迪字體縮小
    st.write("🛵 <span style='font-size: 18px;'>小迪</span>", unsafe_allow_html=True)
    
    # 4. 計算里程與油耗
    if not df.empty and len(df) >= 2:
        sorted_df = df.sort_values("里程", ascending=False).reset_index(drop=True)
        latest_km = sorted_df.iloc[0]['里程']
        prev_km = sorted_df.iloc[1]['里程']
        
        # 從細目中提取上次加油的公升數 (正則表達式)
        prev_detail = sorted_df.iloc[1]['細目']
        try:
            prev_liters = float(re.findall(r"(\d+\.\d+)L", prev_detail)[0])
            avg_efficiency = round((latest_km - prev_km) / prev_liters, 2)
        except:
            avg_efficiency = 0.0
    else:
        latest_km = df['里程'].max() if not df.empty else 0
        avg_efficiency = 0.0

    # 儀表板顯示
    m_col1, m_col2 = st.columns(2)
    m_col1.metric("目前總里程", f"{latest_km} km")
    m_col2.metric("平均油耗", f"{avg_efficiency} km/L")
    
    st.divider()
    
    # 紀錄清單
    st.subheader("📋 紀錄")
    search_query = st.text_input("🔍 搜尋：", placeholder="日期、里程...")
    
    filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)] if search_query else df

    for index, row in filtered_df.sort_values("日期", ascending=False).iterrows():
        with st.container(border=True):
            col_top1, col_top2 = st.columns([1, 1])
            col_top1.write(f"📅 **{row['日期']}**")
            col_top2.write(f"💰 **${row['金額']}**")
            
            col_mid1, col_mid2 = st.columns([1, 1])
            col_mid1.write(f"📍 `{row['里程']} km`")
            col_mid2.write(f"⛽ {row['細目']}")
            
            if st.button("編輯紀錄", key=f"btn_{index}", use_container_width=True):
                edit_dialog(index, row)

with tab2:
    st.subheader("⛽ 新增加油紀錄")
    with st.form("add_form", clear_on_submit=True):
        a_date = st.date_input("加油日期", date.today())
        a_type = st.selectbox("加油種類", list(GAS_PRICES.keys()))
        a_amt = st.number_input("加油金額 ($)", min_value=0, step=10)
        # 里程自動帶入當前最大值，方便快速微調
        a_km = st.number_input("當前里程 (km)", min_value=int(latest_km), value=int(latest_km))
        
        a_calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
        st.info(f"💡 自動換算公升數: **{a_calc_L} L**")
        
        if st.form_submit_button("🚀 儲存紀錄", use_container_width=True):
            new_data = pd.DataFrame([{
                "日期": str(a_date), "類別": "加油", "里程": a_km, "金額": a_amt, "細目": f"{a_type}/{a_calc_L}L"
            }])
            new_df = pd.concat([df, new_data], ignore_index=True)
            repo.update_file(FILE_PATH, f"Add log: {a_km}km", new_df.to_csv(index=False), file_sha)
            st.success("儲存成功")
            st.cache_data.clear()
            st.rerun()
