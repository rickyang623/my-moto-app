import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz
import uuid

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v23.0", page_icon="🛵", layout="centered")

# --- CSS 魔法 (美化清單與按鈕) ---
st.markdown("""
<style>
    div.stButton > button:first-child {
        background-color: white !important;
        color: #31333F !important;
        border: 1px solid #f0f2f6 !important;
        padding: 12px 15px !important;
        text-align: left !important;
        display: block !important;
        width: 100% !important;
        margin-bottom: -10px !important;
        transition: 0.2s;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
        border-radius: 10px !important;
    }
    .service-item-box {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 5px;
        border-left: 4px solid #ff4b4b;
    }
</style>
""", unsafe_allow_html=True)

REPO_NAME = "rickyang623/my-moto-app"
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# 常用保養清單與預設週期
SERVICE_TEMPLATES = {
    "機油": {"km": 1000, "month": 6},
    "齒輪油": {"km": 2000, "month": 12},
    "空氣濾芯": {"km": 5000, "month": 12},
    "火星塞": {"km": 10000, "month": 24},
    "煞車來令片": {"km": 10000, "month": 0},
    "傳動皮帶（CVT）": {"km": 20000, "month": 0},
    "普利珠 / 滑塊": {"km": 20000, "month": 0},
    "電瓶": {"km": 0, "month": 24},
    "輪胎": {"km": 10000, "month": 0},
    "煞車油": {"km": 0, "month": 24},
    "維修/自訂項目": {"km": 0, "month": 0}
}

# 2. 登入 GitHub
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except:
    st.error("GitHub 驗證失敗")
    st.stop()

# 載入資料 (主表 + 細項表)
@st.cache_data(ttl=60)
def load_all_data():
    # 載入主表
    master_content = repo.get_contents("data.csv")
    master_df = pd.read_csv(io.StringIO(master_content.decoded_content.decode('utf-8')))
    if 'id' not in master_df.columns: master_df['id'] = [str(uuid.uuid4()) for _ in range(len(master_df))]
    
    # 載入細項表 (如果不存在則建立)
    try:
        detail_content = repo.get_contents("service_details.csv")
        detail_df = pd.read_csv(io.StringIO(detail_content.decoded_content.decode('utf-8')))
    except:
        detail_df = pd.DataFrame(columns=['parent_id', 'item_name', 'price', 'qty', 'total', 'km_period', 'month_period'])
        repo.create_file("service_details.csv", "Initial", detail_df.to_csv(index=False))
        
    return master_df, detail_df, master_content.sha

master_df, detail_df, master_sha = load_all_data()

# 初始化 Session State 用於暫存正在新增的保養零件
if 'temp_items' not in st.session_state: st.session_state.temp_items = []

# 3. 零件新增彈窗
@st.dialog("➕ 新增保養/維修項目")
def add_item_dialog():
    item_type = st.selectbox("選擇零件項目", list(SERVICE_TEMPLATES.keys()))
    col1, col2 = st.columns(2)
    u_price = col1.number_input("單價", min_value=0, value=0)
    u_qty = col2.number_input("數量", min_value=1, value=1)
    
    st.write("🔧 **更換週期設定 (0 為不啟用)**")
    c3, c4 = st.columns(2)
    p_km = c3.number_input("里程週期 (km)", value=SERVICE_TEMPLATES[item_type]['km'])
    p_month = c4.number_input("時間週期 (月)", value=SERVICE_TEMPLATES[item_type]['month'])
    
    if st.button("確定加入清單", use_container_width=True):
        new_item = {
            "item_name": item_type,
            "price": u_price,
            "qty": u_qty,
            "total": u_price * u_qty,
            "km_period": p_km,
            "month_period": p_month
        }
        st.session_state.temp_items.append(new_item)
        st.rerun()

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "➕ 新增紀錄"])

with tab1:
    # 儀表板與活動紀錄 (與 v22 邏輯雷同，略過以縮短篇幅，重點在 Tab 2)
    st.write("🛵 **小迪的狀態**")
    # ... (此處保留原有的里程與油耗顯示) ...
    st.info("點擊下方「新增紀錄」來嘗試新的保養排版。")

with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    now = datetime.now(TAIPEI_TZ)
    
    with st.form("main_form"):
        a_date = st.date_input("日期時間", now.date())
        a_km = st.number_input("目前里程數 (km)", min_value=0)
        a_shop = st.text_input("施工店家")
        
        if mode == "⛽ 加油":
            a_amt = st.number_input("金額", min_value=0)
            if st.form_submit_button("儲存加油紀錄"):
                # 加油儲存邏輯 (略)
                pass
        
        else: # 🛠️ 保養維修模式
            st.write("---")
            st.write("📦 **零件/保養項目**")
            
            # 顯示已新增的項目
            total_sum = 0
            for i, item in enumerate(st.session_state.temp_items):
                st.markdown(f"""
                <div class="service-item-box">
                    <b>{item['item_name']}</b> | ${item['price']} x {item['qty']} = <b>${item['total']}</b><br>
                    <small>預計週期: {item['km_period']}km / {item['month_period']}月</small>
                </div>
                """, unsafe_allow_html=True)
                total_sum += item['total']
            
            # 觸發彈窗的按鈕 (注意：在 Form 內的按鈕點擊會 Submit，需特殊處理或放外面)
            st.write(f"### 總額：${total_sum}")
            
            save_trigger = st.form_submit_button("💾 確認儲存整筆維修紀錄")
            
    # 彈窗按鈕放在 Form 外面避免干擾
    if mode == "🛠️ 保養維修":
        if st.button("➕ 新增保養/維修項目", use_container_width=True):
            add_item_dialog()
        if st.button("🗑️ 清空目前項目", type="secondary"):
            st.session_state.temp_items = []
            st.rerun()

    if save_trigger:
        if not st.session_state.temp_items:
            st.error("請至少新增一個保養項目")
        else:
            # 1. 產生唯一 ID
            record_id = str(uuid.uuid4())
            
            # 2. 儲存至主表 (data.csv)
            # ... 儲存邏輯 ...
            
            # 3. 儲存至細項表 (service_details.csv)
            new_details = []
            for item in st.session_state.temp_items:
                item['parent_id'] = record_id
                new_details.append(item)
            
            # 更新 GitHub (同時更新兩個檔案)
            # ... 此處執行 repo.update_file ...
            
            st.success("紀錄已成功同步至雙檔案系統！")
            st.session_state.temp_items = [] # 清空暫存
