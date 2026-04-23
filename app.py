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
st.set_page_config(page_title="MyMoto99 v24.3", page_icon="🛵", layout="centered")

# --- CSS 魔法 (簡約版) ---
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
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

# 2. 核心數據引擎 (✨ 物理性強抓)
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except:
    st.error("GitHub 驗證失敗")
    st.stop()

def get_atomic_data(file_name):
    """確保抓到最新版本的分支內容"""
    try:
        # 強制指定 main 分支的最新 commit 以避開任何快取
        branch = repo.get_branch("main")
        contents = repo.get_contents(file_name, ref=branch.commit.sha)
        df = pd.read_csv(io.StringIO(contents.decoded_content.decode('utf-8')))
        return df, contents.sha
    except Exception as e:
        st.error(f"讀取 {file_name} 失敗: {e}")
        return pd.DataFrame(), None

# 執行即時讀取
master_df, master_sha = get_atomic_data("data.csv")
detail_df, detail_sha = get_atomic_data("service_details.csv")

# 清洗主表
if not master_df.empty:
    master_df['日期'] = pd.to_datetime(master_df['日期'], errors='coerce')
    master_df = master_df.dropna(subset=['日期']).sort_values("日期", ascending=False).reset_index(drop=True)
    master_df['里程'] = pd.to_numeric(master_df['里程'], errors='coerce').fillna(0).astype(int)

# 3. 初始化狀態
if 'temp_items' not in st.session_state: st.session_state.temp_items = []
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None

# --- 零件新增彈窗 ---
@st.dialog("➕ 新增項目")
def add_item_dialog():
    items = ["機油", "齒輪油", "空氣濾芯", "火星塞", "煞車來令片", "傳動皮帶（CVT）", "輪胎", "電瓶", "煞車油", "維修/自訂項目"]
    item_type = st.selectbox("項目名稱", items)
    c1, c2 = st.columns(2)
    u_price = c1.number_input("單價", min_value=0, step=10)
    u_qty = c2.number_input("數量", min_value=1, value=1)
    if st.button("確認加入紀錄", use_container_width=True):
        st.session_state.temp_items.append({
            "item_name": item_type, "price": u_price, "qty": u_qty, "total": u_price * u_qty
        })
        st.rerun()

# --- 詳情查看 ---
if st.session_state.edit_idx is not None:
    @st.dialog("📋 紀錄管理")
    def view_dialog(index):
        row = master_df.iloc[index]
        st.write(f"📅 {row['日期'].strftime('%Y-%m-%d %H:%M')} | 📍 {row['里程']} km")
        st.divider()
        items = detail_df[detail_df['parent_id'] == str(row.get('id', ''))]
        if not items.empty:
            for _, item in items.iterrows():
                st.markdown(f"**{item['item_name']}** : ${item['total']} ({item['qty']}x{item['price']})")
        else: st.info(str(row['細目']))
        
        if st.button("🗑️ 刪除這筆紀錄", type="secondary", use_container_width=True):
            with st.spinner("正在執行同步刪除..."):
                latest_master, m_sha = get_atomic_data("data.csv")
                # 這裡使用 ID 匹配進行刪除最安全
                target_id = str(row['id'])
                new_m = latest_master[latest_master['id'] != target_id]
                repo.update_file("data.csv", "Delete", new_m.to_csv(index=False), m_sha)
                st.session_state.edit_idx = None
                st.rerun()
    view_dialog(st.session_state.edit_idx)

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "➕ 新增紀錄"])

with tab1:
    latest_km = master_df['里程'].max() if not master_df.empty else 0
    st.write(f"🛵 目前里程：**{latest_km} km**")
    
    if st.button("🔄 同步雲端最新紀錄", use_container_width=True):
        st.rerun()

    for index, row in master_df.head(20).iterrows():
        icon = "⛽" if row['類別'] == '加油' else "🛠️"
        if st.button(f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | ${int(row['金額'])}", key=f"r_{index}", use_container_width=True):
            st.session_state.edit_idx = index
            st.rerun()

with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    
    with st.form("main_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", datetime.now(TAIPEI_TZ).date())
        a_time = c2.time_input("時間", datetime.now(TAIPEI_TZ).time())
        a_km = st.number_input("里程 (km)", value=int(latest_km))
        a_shop = st.text_input("店家 (選填)") if mode == "🛠️ 保養維修" else ""
        a_note = st.text_area("備註 (選填)")

        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
            a_amt = st.number_input("金額 ($)", min_value=0)
            if st.form_submit_button("🚀 儲存加油", use_container_width=True):
                with st.spinner("存檔同步中..."):
                    # ✨ 儲存前最後一刻抓取最新 SHA
                    real_m, sha_m = get_atomic_data("data.csv")
                    full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                    calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
                    new_row = {"日期": full_dt, "類別": "加油", "里程": a_km, "金額": a_amt, "細目": f"{a_type}/{calc_L}L", "漏記": "No", "備註": a_note, "店家": "", "id": str(uuid.uuid4())}
                    updated_m = pd.concat([real_m, pd.DataFrame([new_row])], ignore_index=True)
                    repo.update_file("data.csv", "Add Gas", updated_m.to_csv(index=False), sha_m)
                    time.sleep(1) # 給予 GitHub 小緩衝
                    st.rerun()
        else:
            save_trigger = st.form_submit_button("💾 儲存保養紀錄", use_container_width=True)

    if mode == "🛠️ 保養維修":
        if st.button("➕ 新增零件項目", use_container_width=True): add_item_dialog()
        total_sum = 0
        if st.session_state.temp_items:
            for item in st.session_state.temp_items:
                st.markdown(f"""<div class="service-item-box"><b>{item['item_name']}</b> <b>${item['total']}</b></div>""", unsafe_allow_html=True)
                total_sum += item['total']
            st.write(f"### 總計：${total_sum}")
            if st.button("🗑️ 清空暫存項目", type="secondary", use_container_width=True): 
                st.session_state.temp_items = []
                st.rerun()

    if mode == "🛠️ 保養維修" and save_trigger:
        if not st.session_state.temp_items:
            st.error("清單為空，請先新增零件")
        else:
            with st.spinner("📦 正在執行雙檔案同步存檔..."):
                # 重新抓取
                real_m, sha_m = get_atomic_data("data.csv")
                real_d, sha_d = get_atomic_data("service_details.csv")
                
                rec_id = str(uuid.uuid4())
                full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                summary = ", ".join([i['item_name'] for i in st.session_state.temp_items])
                
                # 更新主表
                new_m_row = {"日期": full_dt, "類別": "保養", "里程": a_km, "金額": total_sum, "細目": summary, "漏記": "No", "備註": a_note, "店家": a_shop, "id": rec_id}
                updated_m = pd.concat([real_m, pd.DataFrame([new_m_row])], ignore_index=True)
                
                # 更新細項表
                new_details = []
                for item in st.session_state.temp_items:
                    item['parent_id'] = rec_id
                    new_details.append(item)
                updated_d = pd.concat([real_d, pd.DataFrame(new_details)], ignore_index=True)
                
                # 送出
                repo.update_file("data.csv", "Sync Master", updated_m.to_csv(index=False), sha_m)
                repo.update_file("service_details.csv", "Sync Detail", updated_d.to_csv(index=False), sha_d)
                
                st.session_state.temp_items = []
                st.success("同步存檔成功！")
                time.sleep(1)
                st.rerun()
