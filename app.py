import streamlit as st
import pandas as pd
from github import Github
from datetime import date
import io

# 1. 基本設定
st.set_page_config(page_title="MyMoto99 GitHub DB", page_icon="🛵")
REPO_NAME = "rickyang623/my-moto-app" # 請確認這是不是你的帳號/專案名
FILE_PATH = "data.csv"

# 2. 登入 GitHub
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except:
    st.error("GitHub Token 驗證失敗，請檢查 Secrets 設定")

# 3. 讀取資料函式
def load_data():
    file_content = repo.get_contents(FILE_PATH)
    return pd.read_csv(io.StringIO(file_content.decoded_content.decode('utf-8'))), file_content.sha

df, file_sha = load_data()

# --- 介面開始 ---
tab1, tab2 = st.tabs(["📊 儀表板", "⛽ 加油紀錄"])

with tab1:
    st.title("🛵 小迪 GitHub 存檔版")
    curr_km = df['里程'].max()
    st.metric("目前總里程", f"{curr_km} km")
    st.dataframe(df.sort_values("日期", ascending=False), use_container_width=True)

with tab2:
    with st.form("fuel_form"):
        f_date = st.date_input("日期", date.today())
        f_km = st.number_input("里程", min_value=int(curr_km))
        f_amt = st.number_input("金額", min_value=0)
        
        if st.form_submit_button("儲存並推送到 GitHub"):
            # 新增資料
            new_row = f"\n{f_date},加油,{f_km},{f_amt},自動記錄"
            
            # 讀取舊內容並附加新內容
            old_content = repo.get_contents(FILE_PATH).decoded_content.decode('utf-8')
            new_content = old_content + new_row
            
            # 推送回 GitHub
            repo.update_file(FILE_PATH, "App 自動更新紀錄", new_content, file_sha)
            
            st.success("✅ 資料已存入 GitHub CSV！網頁將在 3 秒後重新整理...")
            st.rerun()
