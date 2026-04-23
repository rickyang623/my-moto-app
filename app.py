import streamlit as st
import pandas as pd
from github import Github
from datetime import date
import io

# 1. 基本設定
st.set_page_config(page_title="MyMoto99 v5", page_icon="🛵", layout="wide")
REPO_NAME = "rickyang623/my-moto-app"
FILE_PATH = "data.csv"

# 設定參考油價 (之後可升級為自動爬蟲)
GAS_PRICES = {
    "92無鉛": 32.4,
    "95無鉛": 33.9,
    "98無鉛": 35.9,
    "超級柴油": 31.0
}

# 2. 登入 GitHub
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error(f"GitHub 驗證失敗: {e}")

# 3. 讀取資料函式
@st.cache_data(ttl=60) # 每一分鐘緩存一次，避免頻繁請求 GitHub
def load_data():
    file_content = repo.get_contents(FILE_PATH)
    data = pd.read_csv(io.StringIO(file_content.decoded_content.decode('utf-8')))
    return data, file_content.sha

df, file_sha = load_data()
curr_km = df['里程'].max() if not df.empty else 0

# --- 介面開始 ---
tab1, tab2 = st.tabs(["📊 儀表板", "⛽ 加油紀錄"])

with tab1:
    st.title("🛵 小迪 雲端數據中心")
    
    # 頂部儀表
    c1, c2, c3 = st.columns(3)
    c1.metric("目前里程", f"{curr_km} km")
    
    # 計算平均油耗 (假設細目欄位存的是公升數)
    try:
        # 從細目欄位提取 L 之前的數字來計算 (簡易邏輯)
        df['公升數'] = df['細目'].str.extract('(\d+\.\d+)').astype(float)
        total_l = df['公升數'].sum()
        c2.metric("累計用油", f"{total_l:.1f} L")
    except:
        c2.metric("累計用油", "計算中")

    st.write("---")
    st.subheader("📜 歷史明細")
    st.dataframe(df.sort_values("日期", ascending=False), use_container_width=True)

with tab2:
    st.subheader("⛽ 快速加油記帳")
    
    # 顯示今日油價參考
    st.write("📢 **今日中油參考油價**")
    price_cols = st.columns(4)
    for i, (name, price) in enumerate(GAS_PRICES.items()):
        price_cols[i].caption(name)
        price_cols[i].write(f"**${price}**")

    st.write("---")
    
    with st.form("fuel_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            f_date = st.date_input("加油日期", date.today())
            f_type = st.selectbox("加油種類", list(GAS_PRICES.keys()))
            f_amt = st.number_input("加油總金額 ($)", min_value=0, step=10)
        
        with col_b:
            f_km = st.number_input("當前里程 (km)", min_value=int(curr_km))
            # 自動換算邏輯
            calc_L = round(f_amt / GAS_PRICES[f_type], 2) if f_amt > 0 else 0.0
            st.info(f"💡 自動換算公升數: **{calc_L} L**")
        
        submit = st.form_submit_button("確認儲存並同步至雲端")
        
        if submit:
            if f_km <= curr_km and not df.empty:
                st.warning("請確認里程數是否正確（需大於上次紀錄）")
            else:
                # 準備新資料列
                new_row = f"\n{f_date},加油,{f_km},{f_amt},{f_type} / {calc_L}L"
                
                # 讀取、附加、推送到 GitHub
                old_content = repo.get_contents(FILE_PATH).decoded_content.decode('utf-8')
                new_content = old_content + new_row
                repo.update_file(FILE_PATH, f"Update fuel log: {f_km}km", new_content, file_sha)
                
                st.success(f"✅ 已成功存入！本次加油 {calc_L}L，同步完成。")
                st.cache_data.clear() # 強制清除快取以抓取新資料
                st.rerun()
