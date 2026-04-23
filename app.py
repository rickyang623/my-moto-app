import streamlit as st
import pandas as pd
from github import Github
from datetime import date
import io

# 1. 基本設定
st.set_page_config(page_title="MyMoto99 v6 - 管理模式", page_icon="🛵", layout="wide")
REPO_NAME = "rickyang623/my-moto-app"
FILE_PATH = "data.csv"

# 2. 登入 GitHub
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error(f"GitHub 驗證失敗: {e}")
    st.stop()

# 3. 讀取資料函式
@st.cache_data(ttl=60)
def load_data():
    file_content = repo.get_contents(FILE_PATH)
    data = pd.read_csv(io.StringIO(file_content.decoded_content.decode('utf-8')))
    return data, file_content.sha

df, file_sha = load_data()

# --- 介面開始 ---
tab1, tab2, tab3 = st.tabs(["📊 儀表板", "⛽ 加油紀錄", "🛠️ 資料管理"])

with tab1:
    st.title("🛵 小迪 數據中心")
    curr_km = df['里程'].max() if not df.empty else 0
    st.metric("目前里程", f"{curr_km} km")
    st.write("---")
    st.subheader("📜 目前紀錄明細")
    st.dataframe(df.sort_values("日期", ascending=False), use_container_width=True)

with tab2:
    st.subheader("⛽ 快速加油紀錄")
    # (此處保留原本的加油 form 邏輯，為了節省篇幅省略，請維持 v5.0 的內容)
    st.info("請參考 v5.0 的加油表單邏輯")

with tab3:
    st.title("🛠️ 資料管理 (管理員模式)")
    st.warning("在此處修改後，必須按下下方的「確認同步到 GitHub」才會真正儲存。")
    
    # 核心功能：使用 data_editor 讓表格可編輯
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic", # 允許刪除或新增列
        use_container_width=True,
        key="data_editor_key"
    )
    
    # 比較資料是否有變動
    if st.button("💾 確認同步修改到 GitHub"):
        try:
            # 將編輯後的內容轉回 CSV 字串
            new_csv_content = edited_df.to_csv(index=False)
            
            # 推送到 GitHub (需要最新的 SHA 以避免衝突)
            # 這裡我們重新抓一次內容確保 SHA 是最新的
            current_file = repo.get_contents(FILE_PATH)
            repo.update_file(FILE_PATH, "Web介面手動編修資料", new_csv_content, current_file.sha)
            
            st.success("✅ GitHub 資料庫已更新！網頁將重新載入...")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"同步失敗：{e}")

    st.write("---")
    st.caption("註：點擊表格格子即可修改，選中行後按 Delete 鍵可刪除。")
