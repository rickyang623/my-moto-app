import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime, date
import io

# 1. 基本設定
st.set_page_config(page_title="MyMoto99 v9", page_icon="🛵", layout="wide")
REPO_NAME = "rickyang623/my-moto-app"
FILE_PATH = "data.csv"
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

# 2. 登入 GitHub 與讀取資料
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error(f"GitHub 驗證失敗: {e}")
    st.stop()

@st.cache_data(ttl=60)
def load_data():
    file_content = repo.get_contents(FILE_PATH)
    data = pd.read_csv(io.StringIO(file_content.decoded_content.decode('utf-8')))
    return data, file_content.sha

df, file_sha = load_data()

# 3. 定義彈窗編輯函式
@st.dialog("📝 編輯紀錄")
def edit_dialog(index, row_data):
    st.write(f"正在修改原紀錄...")
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
        st.info(f"💡 自動換算公升數: **{calc_L} L**")
        
        if st.form_submit_button("💾 確認更新並同步"):
            # 更新記憶體中的 df
            df.iloc[index] = {
                "日期": str(f_date),
                "類別": "加油",
                "里程": f_km,
                "金額": f_amt,
                "細目": f"{f_type} / {calc_L}L"
            }
            # 同步至 GitHub
            repo.update_file(FILE_PATH, f"Edit log via Modal: {f_km}km", df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
            st.success("同步成功！")
            st.cache_data.clear()
            st.rerun()

# 4. 介面佈局
tab1, tab2 = st.tabs(["📊 儀表板與管理", "⛽ 新增加油"])

with tab1:
    st.title("🛵 小迪 數據中心")
    curr_km = df['里程'].max() if not df.empty else 0
    st.metric("目前總里程", f"{curr_km} km")
    
    st.divider()
    st.subheader("🔍 搜尋紀錄")
    search_query = st.text_input("輸入關鍵字搜尋：", placeholder="日期、里程或細目")
    
    filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)] if search_query else df

    # 清單式列表
    for index, row in filtered_df.sort_values("日期", ascending=False).iterrows():
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"📅 **{row['日期']}** | 📍 `{row['里程']} km` | 💰 `${row['金額']}` | 📝 {row['細目']}")
        with c2:
            # 按鈕不再顯示編號，純粹叫「編輯」
            if st.button("編輯", key=f"btn_{index}", use_container_width=True):
                edit_dialog(index, row)

with tab2:
    st.subheader("⛽ 新增加油紀錄")
    with st.form("add_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            a_date = st.date_input("加油日期", date.today())
            a_type = st.selectbox("加油種類", list(GAS_PRICES.keys()))
        with col2:
            a_amt = st.number_input("加油金額 ($)", min_value=0, step=10)
            a_km = st.number_input("當前里程 (km)", min_value=int(curr_km))
        
        a_calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
        st.info(f"💡 自動換算公升數: **{a_calc_L} L**")
        
        if st.form_submit_button("🚀 儲存新紀錄"):
            new_data = pd.DataFrame([{
                "日期": str(a_date), "類別": "加油", "里程": a_km, "金額": a_amt, "細目": f"{a_type} / {a_calc_L}L"
            }])
            new_df = pd.concat([df, new_data], ignore_index=True)
            repo.update_file(FILE_PATH, f"Add log: {a_km}km", new_df.to_csv(index=False), file_sha)
            st.success("儲存成功！")
            st.cache_data.clear()
            st.rerun()
