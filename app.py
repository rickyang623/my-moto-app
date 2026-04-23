import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz
import uuid

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v23.4", page_icon="🛵", layout="centered")

# --- CSS 魔法：將清單顏色調整為與系統輸入框一致 ---
st.markdown("""
<style>
    /* 操作按鈕美化 */
    div.stButton > button:first-child {
        background-color: white !important;
        color: #31333F !important;
        border: 1px solid #f0f2f6 !important;
        padding: 10px 15px !important;
        width: 100% !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    }
    
    /* 零件清單卡片：使用與日期輸入框一致的灰色 */
    .service-item-box {
        background-color: rgba(151, 166, 195, 0.15); /* 模仿 Streamlit 預設輸入框的微透明灰 */
        color: inherit;
        padding: 12px 15px;
        border-radius: 10px;
        margin-bottom: 8px;
        border: 1px solid rgba(151, 166, 195, 0.2);
        border-left: 5px solid #ff4b4b; 
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .item-main { font-size: 16px; font-weight: bold; }
    .item-sub { font-size: 12px; opacity: 0.7; }
    .item-price { font-size: 16px; font-weight: bold; }
    
    /* 隱藏焦點轉移器 */
    .stTextInput { height: 0px !important; padding: 0px !important; margin: 0px !important; opacity: 0 !important; }
</style>
""", unsafe_allow_html=True)

REPO_NAME = "rickyang623/my-moto-app"
TAIPEI_TZ = pytz.timezone('Asia/Taipei')
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

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

# 2. 數據載入
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except:
    st.error("GitHub 驗證失敗")
    st.stop()

@st.cache_data(ttl=60)
def load_data():
    m_content = repo.get_contents("data.csv")
    m_df = pd.read_csv(io.StringIO(m_content.decoded_content.decode('utf-8')))
    m_df['日期'] = pd.to_datetime(m_df['日期'])
    try:
        d_content = repo.get_contents("service_details.csv")
        d_df = pd.read_csv(io.StringIO(d_content.decoded_content.decode('utf-8')))
    except:
        d_df = pd.DataFrame(columns=['parent_id', 'item_name', 'price', 'qty', 'total', 'km_period', 'month_period'])
    return m_df.sort_values("日期", ascending=False).reset_index(drop=True), d_df, m_content.sha

master_df, detail_df, master_sha = load_data()

if 'temp_items' not in st.session_state: st.session_state.temp_items = []
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None

# 3. 零件新增彈窗
@st.dialog("➕ 新增項目")
def add_item_dialog():
    item_type = st.selectbox("項目名稱", list(SERVICE_TEMPLATES.keys()))
    c1, c2 = st.columns(2)
    u_price = c1.number_input("單價", min_value=0, step=10)
    u_qty = c2.number_input("數量", min_value=1, value=1)
    st.write("🔧 **週期設定 (0 為不啟用)**")
    c3, c4 = st.columns(2)
    p_km = c3.number_input("里程週期 (km)", value=SERVICE_TEMPLATES[item_type]['km'])
    p_month = c4.number_input("時間週期 (月)", value=SERVICE_TEMPLATES[item_type]['month'])
    
    if st.button("確認加入", use_container_width=True):
        st.session_state.temp_items.append({
            "item_name": item_type, "price": u_price, "qty": u_qty,
            "total": u_price * u_qty, "km_period": p_km, "month_period": p_month
        })
        st.rerun()

# 詳情彈窗
if st.session_state.edit_idx is not None:
    @st.dialog("📋 紀錄詳情")
    def view_dialog(index):
        row = master_df.iloc[index]
        st.write(f"📅 **日期：** {row['日期'].strftime('%Y-%m-%d %H:%M')}")
        st.write(f"📍 **里程：** {row['里程']} km | 💰 **總額：** ${int(row['金額'])}")
        st.divider()
        items = detail_df[detail_df['parent_id'] == str(row['id'])]
        if not items.empty:
            for _, item in items.iterrows():
                st.markdown(f"**{item['item_name']}** : ${item['total']} ({item['qty']}x{item['price']})")
        else: st.info(str(row['細目']))
        
        if st.button("🗑️ 刪除紀錄", type="secondary", use_container_width=True):
            new_m = master_df.drop(index).reset_index(drop=True)
            new_m['日期'] = new_m['日期'].dt.strftime('%Y-%m-%d %H:%M')
            repo.update_file("data.csv", "Delete", new_m.to_csv(index=False), master_sha)
            st.cache_data.clear()
            st.session_state.edit_idx = None
            st.rerun()
    view_dialog(st.session_state.edit_idx)

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "➕ 新增紀錄"])

with tab1:
    latest_km = master_df['里程'].max() if not master_df.empty else 0
    st.write(f"🛵 目前里程：**{latest_km} km**")
    for index, row in master_df.head(10).iterrows():
        icon = "⛽" if row['類別'] == '加油' else "🛠️"
        if st.button(f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | ${int(row['金額'])}", key=f"r_{index}", use_container_width=True):
            st.session_state.edit_idx = index
            st.rerun()

with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    save_trigger = False
    
    if mode == "🛠️ 保養維修":
        c_btn1, c_btn2 = st.columns(2)
        if c_btn1.button("➕ 新增項目", use_container_width=True): add_item_dialog()
        if c_btn2.button("🗑️ 清空清單", use_container_width=True): 
            st.session_state.temp_items = []
            st.rerun()
            
        total_sum = 0
        if st.session_state.temp_items:
            st.write("📦 **零件清單**")
            for item in st.session_state.temp_items:
                st.markdown(f"""
                <div class="service-item-box">
                    <div>
                        <div class="item-main">{item['item_name']}</div>
                        <div class="item-sub">${item['price']} x {item['qty']}</div>
                    </div>
                    <div class="item-price">${item['total']}</div>
                </div>
                """, unsafe_allow_html=True)
                total_sum += item['total']
            st.markdown(f"#### 總計金額：<span style='color:#FF4B4B'>${total_sum}</span>", unsafe_allow_html=True)
            st.divider()

    with st.form("main_form", clear_on_submit=True):
        st.write("📝 **基本資訊**")
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", datetime.now(TAIPEI_TZ).date())
        a_time = c2.time_input("時間", datetime.now(TAIPEI_TZ).time())
        a_km = st.number_input("里程數 (km)", value=int(latest_km))
        
        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
            a_amt = st.number_input("加油金額 ($)", min_value=0)
            if st.form_submit_button("🚀 儲存加油紀錄", use_container_width=True):
                full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
                new_row = {"日期": full_dt, "類別": "加油", "里程": a_km, "金額": a_amt, "細目": f"{a_type}/{calc_L}L", "漏記": "No", "備註": "", "店家": "", "id": str(uuid.uuid4())}
                new_master = pd.concat([master_df, pd.DataFrame([new_row])], ignore_index=True)
                repo.update_file("data.csv", "Add Gas", new_master.to_csv(index=False), master_sha)
                st.cache_data.clear()
                st.rerun()
        else:
            a_shop = st.text_input("施工店家")
            a_note = st.text_area("備註")
            save_trigger = st.form_submit_button("💾 儲存保養紀錄", use_container_width=True)

    if save_trigger:
        if not st.session_state.temp_items:
            st.error("清單是空的")
        else:
            rec_id = str(uuid.uuid4())
            full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
            summary = ", ".join([i['item_name'] for i in st.session_state.temp_items])
            new_m = pd.DataFrame([{"日期": full_dt, "類別": "保養", "里程": a_km, "金額": total_sum, "細目": summary, "漏記": "No", "備註": a_note, "店家": a_shop, "id": rec_id}])
            new_master = pd.concat([master_df, new_m], ignore_index=True)
            
            new_details = []
            for item in st.session_state.temp_items:
                item['parent_id'] = rec_id
                new_details.append(item)
            new_detail_df = pd.concat([detail_df, pd.DataFrame(new_details)], ignore_index=True)
            
            repo.update_file("data.csv", "Add M", new_master.to_csv(index=False), master_sha)
            repo.update_file("service_details.csv", "Add D", new_detail_df.to_csv(index=False), repo.get_contents("service_details.csv").sha)
            st.session_state.temp_items = []
            st.cache_data.clear()
            st.rerun()
