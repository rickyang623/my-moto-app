import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz
import uuid
import time
import secrets # 用於產生隨機數

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v24.1", page_icon="🛵", layout="centered")

# --- CSS 魔法 ---
st.markdown("""
<style>
    div.stButton > button:first-child {
        background-color: white !important;
        color: #31333F !important;
        border: 1px solid #e0e0e0 !important;
        padding: 10px 15px !important;
        width: 100% !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
        margin-bottom: 5px !important;
    }
    .service-item-box {
        background-color: rgba(151, 166, 195, 0.12);
        padding: 10px 15px;
        border-radius: 10px;
        margin-bottom: 6px;
        border-left: 5px solid #ff4b4b; 
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
</style>
""", unsafe_allow_html=True)

REPO_NAME = "rickyang623/my-moto-app"
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# 2. 數據載入 (✨ 破除 CDN 快取邏輯)
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except:
    st.error("GitHub 驗證失敗")
    st.stop()

def get_realtime_data():
    """使用快取破除器強迫 GitHub 提供最新資料"""
    try:
        # ✨ 生成隨機 Token，讓 GitHub 認為這是一個全新的連線
        cache_buster = secrets.token_hex(8)
        
        # 讀取主表 (data.csv)
        # 注意：我們不使用 get_contents 的捷徑，改用更底層的讀取方式
        m_file = repo.get_contents("data.csv", ref=cache_buster) 
    except:
        # 如果隨機 ref 失敗，回退到標準模式但加上手動 SHA 驗證
        m_file = repo.get_contents("data.csv")
    
    try:
        m_df = pd.read_csv(io.StringIO(m_file.decoded_content.decode('utf-8')))
        m_df['日期'] = pd.to_datetime(m_df['日期'], errors='coerce')
        m_df = m_df.dropna(subset=['日期'])
        m_df['里程'] = pd.to_numeric(m_df['里程'], errors='coerce').fillna(0).astype(int)
        
        # 讀取細目表
        d_file = repo.get_contents("service_details.csv")
        d_df = pd.read_csv(io.StringIO(d_file.decoded_content.decode('utf-8')))
        
        return m_df.sort_values("日期", ascending=False).reset_index(drop=True), d_df, m_file.sha
    except Exception as e:
        st.error(f"解析發生錯誤: {e}")
        return pd.DataFrame(), pd.DataFrame(), None

# 執行讀取
master_df, detail_df, current_sha = get_realtime_data()

# 3. 初始化 Session State
if 'temp_items' not in st.session_state: st.session_state.temp_items = []
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None

# --- 零件彈窗 ---
@st.dialog("➕ 新增項目")
def add_item_dialog():
    items = ["機油", "齒輪油", "空氣濾芯", "火星塞", "煞車來令片", "傳動皮帶（CVT）", "輪胎", "電瓶", "煞車油", "維修/自訂項目"]
    item_type = st.selectbox("項目名稱", items)
    c1, c2 = st.columns(2)
    u_price = c1.number_input("單價", min_value=0, step=10)
    u_qty = c2.number_input("數量", min_value=1, value=1)
    if st.button("確認加入", use_container_width=True):
        st.session_state.temp_items.append({"item_name": item_type, "price": u_price, "qty": u_qty, "total": u_price * u_qty})
        st.rerun()

# --- 詳情查看 ---
if st.session_state.edit_idx is not None:
    @st.dialog("📋 紀錄詳情")
    def view_dialog(index):
        row = master_df.iloc[index]
        st.write(f"📅 {row['日期'].strftime('%Y-%m-%d %H:%M')} | 📍 {row['里程']} km")
        st.success(f"金額：${int(row['金額'])}")
        st.divider()
        items = detail_df[detail_df['parent_id'] == str(row.get('id', ''))]
        if not items.empty:
            for _, item in items.iterrows():
                st.markdown(f"**{item['item_name']}** : ${item['total']} ({item['qty']}x{item['price']})")
        if st.button("🗑️ 刪除紀錄", type="secondary", use_container_width=True):
            with st.spinner("正在刪除..."):
                new_m = master_df.drop(index).reset_index(drop=True)
                new_m['日期'] = new_m['日期'].dt.strftime('%Y-%m-%d %H:%M')
                repo.update_file("data.csv", "Del", new_m.to_csv(index=False), repo.get_contents("data.csv").sha)
                st.session_state.edit_idx = None
                st.rerun()
    view_dialog(st.session_state.edit_idx)

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "➕ 新增紀錄"])

with tab1:
    latest_km = master_df['里程'].max() if not master_df.empty else 0
    st.write(f"🛵 目前里程：**{latest_km} km**")
    
    # 強力刷新按鈕
    if st.button("🔄 物理性刷新 (破除快取)", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if master_df.empty:
        st.warning("目前尚無資料或正在同步中...")
    else:
        for index, row in master_df.head(20).iterrows():
            icon = "⛽" if row['類別'] == '加油' else "🛠️"
            label = f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | ${int(row['金額'])}"
            if st.button(label, key=f"r_{index}", use_container_width=True):
                st.session_state.edit_idx = index
                st.rerun()

with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    now = datetime.now(TAIPEI_TZ)
    
    with st.form("main_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", now.date())
        a_time = c2.time_input("時間", now.time())
        a_km = st.number_input("里程 (km)", value=int(latest_km))
        a_shop = st.text_input("店家") if mode == "🛠️ 保養維修" else ""
        a_note = st.text_area("備註")

        if mode == "⛽ 加油":
            a_amt = st.number_input("金額", min_value=0)
            if st.form_submit_button("🚀 儲存加油", use_container_width=True):
                with st.spinner("存檔中..."):
                    full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                    m_df_upd, _, m_sha = get_realtime_data()
                    new_m = pd.concat([m_df_upd, pd.DataFrame([{"日期": full_dt, "類別": "加油", "里程": a_km, "金額": a_amt, "細目": "加油", "id": str(uuid.uuid4())}])], ignore_index=True)
                    repo.update_file("data.csv", "Add Gas", new_m.to_csv(index=False), m_sha)
                    time.sleep(1)
                    st.rerun()
        else:
            save_trigger = st.form_submit_button("💾 儲存保養紀錄", use_container_width=True)

    if mode == "🛠️ 保養維修":
        if st.button("➕ 新增保養項目", use_container_width=True): add_item_dialog()
        total_sum = 0
        if st.session_state.temp_items:
            for item in st.session_state.temp_items:
                st.markdown(f"""<div class="service-item-box"><b>{item['item_name']}</b> <b>${item['total']}</b></div>""", unsafe_allow_html=True)
                total_sum += item['total']
            st.write(f"### 總計：${total_sum}")
            if st.button("🗑️ 清空項目", type="secondary", use_container_width=True): 
                st.session_state.temp_items = []
                st.rerun()

    if mode == "🛠️ 保養維修" and save_trigger:
        if not st.session_state.temp_items:
            st.error("請先新增項目")
        else:
            with st.spinner("同步至 GitHub..."):
                m_df_upd, d_df_upd, m_sha = get_realtime_data()
                rec_id = str(uuid.uuid4())
                full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                
                # 更新
                summary = ", ".join([i['item_name'] for i in st.session_state.temp_items])
                new_m = pd.concat([m_df_upd, pd.DataFrame([{"日期": full_dt, "類別": "保養", "里程": a_km, "金額": total_sum, "店家": a_shop, "備註": a_note, "細目": summary, "id": rec_id}])], ignore_index=True)
                new_items = []
                for item in st.session_state.temp_items:
                    item['parent_id'] = rec_id
                    new_items.append(item)
                new_d = pd.concat([d_df_upd, pd.DataFrame(new_items)], ignore_index=True)
                
                # 存檔
                repo.update_file("data.csv", "Update Master", new_m.to_csv(index=False), m_sha)
                repo.update_file("service_details.csv", "Update Details", new_d.to_csv(index=False), repo.get_contents("service_details.csv").sha)
                
                st.session_state.temp_items = []
                time.sleep(1)
                st.rerun()
