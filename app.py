import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime, date
import io

# 1. 基本設定與油價定義
st.set_page_config(page_title="MyMoto99 v8", page_icon="🛵", layout="wide")
REPO_NAME = "rickyang623/my-moto-app"
FILE_PATH = "data.csv"
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

# 2. 登入 GitHub 與讀取資料
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error(f"GitHub 驗證失敗，請檢查 Secrets。錯誤訊息: {e}")
    st.stop()

@st.cache_data(ttl=60)
def load_data():
    file_content = repo.get_contents(FILE_PATH)
    data = pd.read_csv(io.StringIO(file_content.decoded_content.decode('utf-8')))
    return data, file_content.sha

df, file_sha = load_data()

# 3. 初始化編輯狀態
if 'editing_index' not in st.session_state:
    st.session_state.editing_index = None

# 4. 定義分頁 (解決 NameError 的關鍵)
tab1, tab2 = st.tabs(["📊 儀表板與管理", "⛽ 加油紀錄(新增/修改)"])

# --- Tab 1: 儀表板與搜尋管理 ---
with tab1:
    st.title("🛵 小迪 數據中心")
    curr_km = df['里程'].max() if not df.empty else 0
    st.metric("目前總里程", f"{curr_km} km")
    
    st.divider()
    st.subheader("🔍 搜尋與編輯紀錄")
    search_query = st.text_input("輸入關鍵字搜尋 (如：日期、里程)：", placeholder="例如：2026-04")
    
    # 過濾邏輯
    if search_query:
        mask = df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
        filtered_df = df[mask]
    else:
        filtered_df = df

    # 清單式編輯按鈕
    display_limit = 10
    st.write(f"顯示最近 {display_limit} 筆符合的紀錄：")
    
    for index, row in filtered_df.sort_values("日期", ascending=False).head(display_limit).iterrows():
        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.write(f"📅 {row['日期']} | 📍 {row['里程']} km | 💰 {row['金額']} 元 | 📝 {row['細目']}")
        with col_btn:
            if st.button(f"編輯 #{index}", key=f"edit_{index}"):
                st.session_state.editing_index = index
                st.success(f"已載入 #{index}，請點擊上方標籤『加油紀錄』進行修改")
                st.rerun()

# --- Tab 2: 加油表單 (支援新增與修改回填) ---
with tab2:
    is_edit_mode = st.session_state.editing_index is not None
    st.subheader("📝 修改紀錄" if is_edit_mode else "⛽ 新增加油紀錄")
    
    # 判斷預填資料
    if is_edit_mode:
        old_data = df.iloc[st.session_state.editing_index]
        try:
            d_date = datetime.strptime(str(old_data['日期']), '%Y-%m-%d').date()
        except:
            d_date = date.today()
        d_km = int(old_data['里程'])
        d_amt = int(old_data['金額'])
        st.warning(f"⚠️ 正在編輯序號 #{st.session_state.editing_index} 的資料")
    else:
        d_date = date.today()
        d_km = int(curr_km)
        d_amt = 0

    with st.form("fuel_form", clear_on_submit=not is_edit_mode):
        f_date = st.date_input("加油日期", d_date)
        f_type = st.selectbox("加油種類", list(GAS_PRICES.keys()))
        f_amt = st.number_input("加油金額 ($)", min_value=0, value=d_amt)
        f_km = st.number_input("當前里程 (km)", min_value=0, value=d_km)
        
        # 自動換算功能
        calc_L = round(f_amt / GAS_PRICES[f_type], 2) if f_amt > 0 else 0.0
        st.info(f"💡 自動換算公升數: **{calc_L} L**")
        
        btn_label = "💾 更新舊紀錄" if is_edit_mode else "🚀 儲存新紀錄"
        if st.form_submit_button(btn_label):
            new_data = {
                "日期": str(f_date),
                "類別": "加油",
                "里程": f_km,
                "金額": f_amt,
                "細目": f"{f_type} / {calc_L}L"
            }
            
            if is_edit_mode:
                df.iloc[st.session_state.editing_index] = new_data
                st.session_state.editing_index = None
            else:
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
            
            # 推送到 GitHub
            repo.update_file(FILE_PATH, "Update log via web", df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
            st.success("🎉 雲端同步成功！")
            st.cache_data.clear()
            st.rerun()

    if is_edit_mode:
        if st.button("❌ 放棄修改"):
            st.session_state.editing_index = None
            st.rerun()
