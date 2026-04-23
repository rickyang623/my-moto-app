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
    # 增加一個選擇器來挑選要修改的資料
    st.subheader("🔍 選擇紀錄進行編修")
    
    # 建立一個方便閱讀的清單
    df_display = df.copy()
    df_display['選擇'] = df_display.apply(lambda x: f"{x['日期']} | {x['里程']}km | {x['金額']}元", axis=1)
    
    selected_record = st.selectbox("請挑選一筆紀錄來修改：", 
                                   options=range(len(df)), 
                                   format_func=lambda x: df_display.iloc[x]['選擇'])
    
    if st.button("📝 載入這筆資料到加油頁面"):
        st.session_state.editing_index = selected_record
        st.success(f"已載入第 {selected_record+1} 筆資料，請切換至『加油紀錄』標籤進行修改。")

    st.divider()
    st.dataframe(df.sort_values("日期", ascending=False), use_container_width=True)

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
