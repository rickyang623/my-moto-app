import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime, date
import io

# 1. 初始化與 GitHub 連線 (維持原樣)
st.set_page_config(page_title="MyMoto99 v7", page_icon="🛵", layout="wide")
REPO_NAME = "rickyang623/my-moto-app"
FILE_PATH = "data.csv"
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

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

# --- 核心邏輯：處理「編輯模式」的暫存狀態 ---
if 'editing_index' not in st.session_state:
    st.session_state.editing_index = None  # None 表示新增模式，數字表示正在修第幾列

# --- 介面開始 ---
tab1, tab2 = st.tabs(["📊 儀表板與管理", "⛽ 加油紀錄(新增/修改)"])

with tab1:
    st.title("🛵 資料庫管理")
    
    # 策略 1：搜尋過濾器
    search_query = st.text_input("🔍 搜尋紀錄 (輸入日期、里程或細目)：", placeholder="例如：2026-04 或 80km")
    
    # 根據關鍵字篩選資料
    if search_query:
        mask = df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
        filtered_df = df[mask]
    else:
        filtered_df = df

    st.write(f"共找到 {len(filtered_df)} 筆符合的紀錄")

    # 策略 2：互動式表格選擇 (取代長長的下拉選單)
    # 我們利用 st.dataframe 的 selection 功能，或者用按鈕陣列
    st.subheader("📝 點擊下方『編輯』按鈕載入資料")
    
    # 建立一個清爽的顯示表格
    # 為了方便操作，我們只顯示最新的 10-20 筆，其餘可透過搜尋找
    display_limit = 15
    for index, row in filtered_df.sort_values("日期", ascending=False).head(display_limit).iterrows():
        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.write(f"📅 {row['日期']} | 📍 {row['里程']} km | 💰 {row['金額']} 元 | 📝 {row['細目']}")
        with col_btn:
            if st.button(f"編輯 #{index}", key=f"edit_{index}"):
                st.session_state.editing_index = index
                st.success(f"已載入 #{index} 紀錄，請切換分頁。")
                st.rerun()
    
    if len(filtered_df) > display_limit:
        st.info(f"💡 還有 {len(filtered_df) - display_limit} 筆較舊的紀錄，請使用上方的搜尋框尋找。")

    st.divider()
    # 保留原始表格預覽
    with st.expander("👀 查看原始完整數據表"):
        st.dataframe(df, use_container_width=True)

with tab2:
    mode_title = "📝 修改舊紀錄" if st.session_state.editing_index is not None else "⛽ 新增加油紀錄"
    st.subheader(mode_title)
    
    # 如果是修改模式，預填入舊資料
    if st.session_state.editing_index is not None:
        old_data = df.iloc[st.session_state.editing_index]
        default_date = datetime.strptime(old_data['日期'], '%Y-%m-%d').date()
        default_km = int(old_data['里程'])
        default_amt = int(old_data['金額'])
        st.warning(f"目前正在修改原始紀錄中... (索引: {st.session_state.editing_index})")
    else:
        default_date = date.today()
        default_km = int(df['里程'].max()) if not df.empty else 0
        default_amt = 0

    with st.form("fuel_form"):
        f_date = st.date_input("日期", default_date)
        f_type = st.selectbox("種類", list(GAS_PRICES.keys()))
        f_amt = st.number_input("金額 ($)", min_value=0, value=default_amt)
        f_km = st.number_input("里程 (km)", min_value=0, value=default_km)
        
        # 自動換算依然存在！
        calc_L = round(f_amt / GAS_PRICES[f_type], 2) if f_amt > 0 else 0.0
        st.info(f"💡 自動換算公升數: **{calc_L} L**")
        
        btn_label = "💾 確認更新舊紀錄" if st.session_state.editing_index is not None else "🚀 確認儲存新紀錄"
        if st.form_submit_button(btn_label):
            new_row_data = {
                "日期": str(f_date),
                "類別": "加油",
                "里程": f_km,
                "金額": f_amt,
                "細目": f"{f_type} / {calc_L}L"
            }
            
            if st.session_state.editing_index is not None:
                # 修改模式：替換掉那一列
                df.iloc[st.session_state.editing_index] = new_row_data
                st.session_state.editing_index = None # 修正完回到新增模式
            else:
                # 新增模式：附加在最後
                df = pd.concat([df, pd.DataFrame([new_row_data])], ignore_index=True)
            
            # 推送到 GitHub
            repo.update_file(FILE_PATH, "App 表單更新/修改資料", df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
            st.success("✅ 雲端同步成功！")
            st.cache_data.clear()
            st.rerun()

    if st.session_state.editing_index is not None:
        if st.button("❌ 放棄修改，回到新增模式"):
            st.session_state.editing_index = None
            st.rerun()

# --- 前面的 GitHub 登入與資料讀取 load_data() 保持不變 ---

# 1. 【關鍵步驟】先定義標籤變數
tab1, tab2 = st.tabs(["📊 儀表板與管理", "⛽ 加油紀錄(新增/修改)"])

# 2. 接著才開始使用這些變數
with tab1:
    st.title("🛵 資料庫管理")
    
    # --- 這裡放入我上一則訊息給你的搜尋過濾與清單程式碼 ---
    search_query = st.text_input("🔍 搜尋紀錄：", placeholder="輸入關鍵字...")
    
    # ... (中間的過濾邏輯與 for 迴圈列表) ...

with tab2:
    # --- 這裡放入原本的加油表單邏輯 ---
    st.subheader("⛽ 加油紀錄表單")
