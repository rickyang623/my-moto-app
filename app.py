import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz
import uuid

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v23.7", page_icon="🛵", layout="centered")

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
        font-size: 15px !important;
    }
    .service-item-box {
        background-color: rgba(151, 166, 195, 0.12);
        color: inherit;
        padding: 10px 15px;
        border-radius: 10px;
        margin-bottom: 6px;
        border-left: 5px solid #ff4b4b; 
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .item-main { font-size: 15px; font-weight: bold; }
    .item-price { font-size: 16px; font-weight: 800; }
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

# 2. 數據載入 (強化清洗邏輯)
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
    
    # 🛡️ 數據清洗：處理日期錯誤
    m_df['日期'] = pd.to_datetime(m_df['日期'], errors='coerce')
    m_df = m_df.dropna(subset=['日期']) # 移除日期壞掉的列
    
    # 補齊 ID 與里程類型轉換
    if 'id' not in m_df.columns: m_df['id'] = ''
    m_df['id'] = m_df['id'].apply(lambda x: str(uuid.uuid4()) if pd.isna(x) or x == '' else x)
    m_df['里程'] = pd.to_numeric(m_df['里程'], errors='coerce').fillna(0).astype(int)
    
    try:
        d_content = repo.get_contents("service_details.csv")
        d_df = pd.read_csv(io.StringIO(d_content.decoded_content.decode('utf-8')))
    except:
        d_df = pd.DataFrame(columns=['parent_id', 'item_name', 'price', 'qty', 'total', 'km_period', 'month_period'])
    
    return m_df.sort_values("日期", ascending=False).reset_index(drop=True), d_df, m_content.sha

master_df, detail_df, master_sha = load_data()

# 初始化狀態
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
    
    if st.button("確認加入紀錄", use_container_width=True):
        st.session_state.temp_items.append({
            "item_name": item_type, "price": u_price, "qty": u_qty,
            "total": u_price * u_qty, "km_period": p_km, "month_period": p_month
        })
        st.rerun()

# 4. 詳情查看
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
    
    # ⛽ 油耗計算 (精準過濾版)
    avg_eff = "--"
    gas_only = master_df[master_df['類別'] == '加油'].copy().reset_index(drop=True)
    if len(gas_only) >= 2 and str(gas_only.iloc[0]['漏記']) != 'Yes':
        try:
            curr_km = float(gas_only.iloc[0]['里程'])
            prev_km = float(gas_only.iloc[1]['里程'])
            match = re.search(r"(\d+\.?\d*)L", str(gas_only.iloc[1]['細目']))
            if match:
                prev_liters = float(match.group(1))
                if prev_liters > 0: avg_eff = f"{round((curr_km - prev_km) / prev_liters, 1)}"
        except: pass

    dashboard_html = f"""
    <div style="display: flex; gap: 8px; margin: 5px 0 15px 0;">
        <div style="flex: 1; background: white; padding: 15px 10px; border-radius: 12px; border: 1px solid #f0f2f6; text-align: center;">
            <div style="font-size: 12px; color: #666;">平均油耗</div>
            <div style="font-size: 22px; font-weight: 800; color: #31333F;">{avg_eff} <span style="font-size: 13px;">km/L</span></div>
        </div>
    </div>
    """
    st.markdown(dashboard_html, unsafe_allow_html=True)
    
    for index, row in master_df.head(10).iterrows():
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
            st.write("📦 **零件清單**")
            for item in st.session_state.temp_items:
                st.markdown(f"""<div class="service-item-box"><div><div class="item-main">{item['item_name']}</div><div class="item-sub">${item['price']} x {item['qty']}</div></div><div class="item-price">${item['total']}</div></div>""", unsafe_allow_html=True)
                total_sum += item['total']
            
            st.markdown(f"#### 總計金額：<span style='color:#FF4B4B'>${total_sum}</span>", unsafe_allow_html=True)
            if st.button("🗑️ 清空清單", use_container_width=True, type="secondary"): 
                st.session_state.temp_items = []
                st.rerun()
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
            a_miss = st.checkbox("漏記標記")
            if st.form_submit_button("🚀 儲存加油紀錄", use_container_width=True):
                full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
                rec_id = str(uuid.uuid4())
                new_row = pd.DataFrame([{"日期": full_dt, "類別": "加油", "里程": a_km, "金額": a_amt, "細目": f"{a_type}/{calc_L}L", "漏記": "Yes" if a_miss else "No", "備註": "", "店家": "", "id": rec_id}])
                new_master = pd.concat([master_df, new_row], ignore_index=True)
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
            
            new_details_list = []
            for item in st.session_state.temp_items:
                item['parent_id'] = rec_id
                new_details_list.append(item)
            new_detail_df = pd.concat([detail_df, pd.DataFrame(new_details_list)], ignore_index=True)
            
            repo.update_file("data.csv", "Add Master", new_master.to_csv(index=False), master_sha)
            repo.update_file("service_details.csv", "Add Details", new_detail_df.to_csv(index=False), repo.get_contents("service_details.csv").sha)
            st.session_state.temp_items = []
            st.cache_data.clear()
            st.success("紀錄已存檔！")
            st.rerun()
