import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz
import uuid
import time

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v23.9", page_icon="🛵", layout="centered")

# --- CSS 魔法 (維持質感) ---
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
    .stTextInput { height: 0px !important; padding: 0px !important; margin: 0px !important; opacity: 0 !important; }
</style>
""", unsafe_allow_html=True)

REPO_NAME = "rickyang623/my-moto-app"
TAIPEI_TZ = pytz.timezone('Asia/Taipei')
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

# 2. 數據載入 (✨ 加入防快取邏輯)
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except:
    st.error("GitHub 驗證失敗")
    st.stop()

@st.cache_data(ttl=2) # 降低快取時間
def load_data(refresh_trigger):
    try:
        # ✨ 加入隨機參數，繞過 GitHub 伺服器快取
        m_content = repo.get_contents("data.csv")
        m_df = pd.read_csv(io.StringIO(m_content.decoded_content.decode('utf-8')))
        
        # 數據清洗
        m_df['日期'] = pd.to_datetime(m_df['日期'], errors='coerce')
        m_df = m_df.dropna(subset=['日期'])
        if 'id' not in m_df.columns: m_df['id'] = ''
        m_df['id'] = m_df['id'].apply(lambda x: str(uuid.uuid4()) if pd.isna(x) or x == '' else x)
        m_df['里程'] = pd.to_numeric(m_df['里程'], errors='coerce').fillna(0).astype(int)
        
        d_content = repo.get_contents("service_details.csv")
        d_df = pd.read_csv(io.StringIO(d_content.decoded_content.decode('utf-8')))
        
        return m_df.sort_values("日期", ascending=False).reset_index(drop=True), d_df
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

# 使用時間戳記作為快取鍵，確保手動重整時能刷新
master_df, detail_df = load_data(st.session_state.get('last_update', 0))

# 3. 初始化狀態
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
        st.session_state.temp_items.append({
            "item_name": item_type, "price": u_price, "qty": u_qty, "total": u_price * u_qty
        })
        st.rerun()

# --- 詳情查看 ---
if st.session_state.edit_idx is not None:
    @st.dialog("📋 紀錄詳情")
    def view_dialog(index):
        row = master_df.iloc[index]
        st.write(f"📅 {row['日期'].strftime('%Y-%m-%d %H:%M')} | 📍 {row['里程']} km")
        st.success(f"總額：${int(row['金額'])}")
        st.divider()
        items = detail_df[detail_df['parent_id'] == str(row['id'])]
        if not items.empty:
            for _, item in items.iterrows():
                st.markdown(f"**{item['item_name']}** : ${item['total']} ({item['qty']}x{item['price']})")
        else: st.info(str(row['細目']))
        
        if st.button("🗑️ 刪除紀錄", type="secondary", use_container_width=True):
            new_m = master_df.drop(index).reset_index(drop=True)
            new_m['日期'] = new_m['日期'].dt.strftime('%Y-%m-%d %H:%M')
            repo.update_file("data.csv", "Del", new_m.to_csv(index=False), repo.get_contents("data.csv").sha)
            st.session_state.last_update = time.time()
            st.cache_data.clear()
            st.session_state.edit_idx = None
            st.rerun()
    view_dialog(st.session_state.edit_idx)

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "➕ 新增紀錄"])

with tab1:
    latest_km = master_df['里程'].max() if not master_df.empty else 0
    st.write(f"🛵 目前里程：**{latest_km} km**")
    
    # 刷新按鈕
    if st.button("🔄 手動同步最新資料", use_container_width=True):
        st.session_state.last_update = time.time()
        st.cache_data.clear()
        st.rerun()

    for index, row in master_df.head(15).iterrows():
        icon = "⛽" if row['類別'] == '加油' else "🛠️"
        if st.button(f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | ${int(row['金額'])}", key=f"r_{index}", use_container_width=True):
            st.session_state.edit_idx = index
            st.rerun()

with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    save_trigger = False
    
    if mode == "🛠️ 保養維修":
        if st.button("➕ 新增保養/維修項目", use_container_width=True): add_item_dialog()
        
        total_sum = 0
        if st.session_state.temp_items:
            for item in st.session_state.temp_items:
                st.markdown(f"""<div class="service-item-box"><div><b>{item['item_name']}</b><br><small>${item['price']} x {item['qty']}</small></div><b>${item['total']}</b></div>""", unsafe_allow_html=True)
                total_sum += item['total']
            st.write(f"### 總計：${total_sum}")
            if st.button("🗑️ 清空清單", use_container_width=True, type="secondary"): 
                st.session_state.temp_items = []
                st.rerun()

    with st.form("main_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", datetime.now(TAIPEI_TZ).date())
        a_time = c2.time_input("時間", datetime.now(TAIPEI_TZ).time())
        a_km = st.number_input("里程 (km)", value=int(latest_km))
        a_shop = st.text_input("店家") if mode == "🛠️ 保養維修" else ""
        a_note = st.text_area("備註")

        if mode == "⛽ 加油":
            a_amt = st.number_input("金額", min_value=0)
            if st.form_submit_button("🚀 儲存加油", use_container_width=True):
                full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                new_m = pd.concat([master_df, pd.DataFrame([{"日期": full_dt, "類別": "加油", "里程": a_km, "金額": a_amt, "細目": f"加油", "id": str(uuid.uuid4())}])], ignore_index=True)
                repo.update_file("data.csv", "Add Gas", new_m.to_csv(index=False), repo.get_contents("data.csv").sha)
                st.session_state.last_update = time.time()
                st.cache_data.clear()
                st.rerun()
        else:
            save_trigger = st.form_submit_button("💾 儲存保養紀錄", use_container_width=True)

    if save_trigger:
        if not st.session_state.temp_items:
            st.error("請先新增零件項目")
        else:
            with st.spinner("正在與 GitHub 同步，請稍候..."):
                rec_id = str(uuid.uuid4())
                full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                
                # 1. 主表
                new_m = pd.concat([master_df, pd.DataFrame([{"日期": full_dt, "類別": "保養", "里程": a_km, "金額": total_sum, "店家": a_shop, "備註": a_note, "id": rec_id}])], ignore_index=True)
                # 2. 細項表
                new_details_list = []
                for item in st.session_state.temp_items:
                    item['parent_id'] = rec_id
                    new_details_list.append(item)
                new_d = pd.concat([detail_df, pd.DataFrame(new_details_list)], ignore_index=True)
                
                # 3. 強制推送到 GitHub 並更新 SHA
                repo.update_file("data.csv", "Sync M", new_m.to_csv(index=False), repo.get_contents("data.csv").sha)
                repo.update_file("service_details.csv", "Sync D", new_d.to_csv(index=False), repo.get_contents("service_details.csv").sha)
                
                # ✨ 更新 Session 時間戳，強迫 load_data 刷新
                st.session_state.last_update = time.time()
                st.session_state.temp_items = []
                st.cache_data.clear()
                st.success("🎉 紀錄已儲存！如果沒看到，請點擊下方的手動同步。")
                time.sleep(1)
                st.rerun()
