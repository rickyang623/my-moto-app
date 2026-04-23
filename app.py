import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz
import uuid

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v23.1", page_icon="🛵", layout="centered")

# --- CSS 魔法 ---
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
        margin-bottom: 8px;
        border-left: 5px solid #ff4b4b;
    }
    .stTextInput { height: 0px !important; padding: 0px !important; margin: 0px !important; opacity: 0 !important; }
</style>
""", unsafe_allow_html=True)

REPO_NAME = "rickyang623/my-moto-app"
TAIPEI_TZ = pytz.timezone('Asia/Taipei')
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

# 常用保養模板
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

@st.cache_data(ttl=60)
def load_data():
    m_content = repo.get_contents("data.csv")
    m_df = pd.read_csv(io.StringIO(m_content.decoded_content.decode('utf-8')))
    if 'id' not in m_df.columns: m_df['id'] = ''
    m_df['日期'] = pd.to_datetime(m_df['日期'])
    
    try:
        d_content = repo.get_contents("service_details.csv")
        d_df = pd.read_csv(io.StringIO(d_content.decoded_content.decode('utf-8')))
    except:
        d_df = pd.DataFrame(columns=['parent_id', 'item_name', 'price', 'qty', 'total', 'km_period', 'month_period'])
    
    return m_df.sort_values("日期", ascending=False).reset_index(drop=True), d_df, m_content.sha

master_df, detail_df, master_sha = load_data()

# 初始化暫存 Session State
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

# 4. 詳情查看 (關聯細目)
@st.dialog("📋 紀錄詳情")
def view_dialog(index):
    row = master_df.iloc[index]
    st.write(f"📅 **日期：** {row['日期'].strftime('%Y-%m-%d %H:%M')}")
    st.write(f"📍 **里程：** {row['里程']} km | 💰 **金額：** ${int(row['金額'])}")
    if str(row['店家']) != 'nan': st.write(f"🏠 **店家：** {row['店家']}")
    
    if row['類別'] == '保養':
        st.divider()
        st.write("📦 **維修明細：**")
        items = detail_df[detail_df['parent_id'] == str(row['id'])]
        if not items.empty:
            for _, item in items.iterrows():
                st.markdown(f"- {item['item_name']} (${item['price']} x {item['qty']})")
        else:
            st.info(row['細目'])
            
    if str(row['備註']) != 'nan' and row['備註'] != '': st.info(f"💬 備註：{row['備註']}")
    
    if st.button("🗑️ 刪除紀錄", use_container_width=True, type="secondary"):
        new_master = master_df.drop(index).reset_index(drop=True)
        new_master['日期'] = new_master['日期'].dt.strftime('%Y-%m-%d %H:%M')
        # 同步刪除細目
        new_detail = detail_df[detail_df['parent_id'] != str(row['id'])]
        
        repo.update_file("data.csv", "Delete Master", new_master.to_csv(index=False), master_sha)
        repo.update_file("service_details.csv", "Delete Detail", new_detail.to_csv(index=False), repo.get_contents("service_details.csv").sha)
        st.cache_data.clear()
        st.session_state.edit_idx = None
        st.rerun()

if st.session_state.edit_idx is not None: view_dialog(st.session_state.edit_idx)

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "➕ 新增紀錄"])

with tab1:
    st.write("🛵 <span style='font-size: 13px; color: gray;'>小迪的狀態</span>", unsafe_allow_html=True)
    
    # 儀表板
    latest_km = master_df['里程'].max() if not master_df.empty else 0
    avg_eff = "--"
    gas_only = master_df[master_df['類別'] == '加油'].copy().reset_index(drop=True)
    if len(gas_only) >= 2 and str(gas_only.iloc[0]['漏記']) != 'Yes':
        try:
            curr_km, prev_km = gas_only.iloc[0]['里程'], gas_only.iloc[1]['里程']
            match = re.search(r"(\d+\.?\d*)L", str(gas_only.iloc[1]['細目']))
            if match: avg_eff = f"{round((curr_km - prev_km) / float(match.group(1)), 1)}"
        except: pass

    st.markdown(f"""
    <div style="display: flex; gap: 8px; margin: 5px 0 15px 0;">
        <div style="flex: 1; background: white; padding: 15px 10px; border-radius: 12px; border: 1px solid #f0f2f6; text-align: center;">
            <div style="font-size: 12px; color: #666;">目前里程</div>
            <div style="font-size: 22px; font-weight: 800; color: #31333F;">{latest_km} <span style="font-size: 13px;">km</span></div>
        </div>
        <div style="flex: 1; background: white; padding: 15px 10px; border-radius: 12px; border: 1px solid #f0f2f6; text-align: center;">
            <div style="font-size: 12px; color: #666;">平均油耗</div>
            <div style="font-size: 22px; font-weight: 800; color: #31333F;">{avg_eff} <span style="font-size: 14px;">km/L</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 紀錄清單
    for index, row in master_df.head(10).iterrows():
        icon = "⛽" if row['類別'] == '加油' else "🛠️"
        label = f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | {row['里程']}k | ${int(row['金額'])}"
        if st.button(label, key=f"rec_{index}", use_container_width=True):
            st.session_state.edit_idx = index
            st.rerun()

with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    
    # 為了修復 NameError，我們將所有的表單互動與變數初始化在最前面
    save_trigger = False
    
    with st.form("main_form", clear_on_submit=True):
        st.text_input("Focus", label_visibility="collapsed")
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", datetime.now(TAIPEI_TZ).date())
        a_time = c2.time_input("時間", datetime.now(TAIPEI_TZ).time())
        a_km = st.number_input("目前里程 (km)", value=int(latest_km))
        a_shop = st.text_input("施工店家 (選填)")
        a_note = st.text_area("備註")

        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
            a_amt = st.number_input("金額 ($)", min_value=0)
            a_miss = st.checkbox("漏記標記")
            if st.form_submit_button("🚀 儲存加油", use_container_width=True):
                full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
                new_row = {"日期": full_dt, "類別": "加油", "里程": a_km, "金額": a_amt, "細目": f"{a_type}/{calc_L}L", "漏記": "Yes" if a_miss else "No", "備註": a_note, "店家": "", "id": str(uuid.uuid4())}
                new_master = pd.concat([master_df, pd.DataFrame([new_row])], ignore_index=True)
                repo.update_file("data.csv", "Add Gas", new_master.to_csv(index=False), master_sha)
                st.cache_data.clear()
                st.rerun()
        else:
            # 保養模式
            st.write("📦 **已新增零件清單：**")
            total_sum = 0
            for item in st.session_state.temp_items:
                st.markdown(f"""<div class='service-item-box'><b>{item['item_name']}</b> | ${item['price']} x {item['qty']} = ${item['total']}</div>""", unsafe_allow_html=True)
                total_sum += item['total']
            st.write(f"### 總計金額：${total_sum}")
            save_trigger = st.form_submit_button("💾 儲存保養紀錄", use_container_width=True)

    # 彈窗按鈕放表單外
    if mode == "🛠️ 保養維修":
        c3, c4 = st.columns(2)
        if c3.button("➕ 新增項目", use_container_width=True): add_item_dialog()
        if c4.button("🗑️ 清空", use_container_width=True): 
            st.session_state.temp_items = []
            st.rerun()

    # 處理存檔 (保養模式)
    if save_trigger:
        if not st.session_state.temp_items:
            st.error("請至少新增一個項目")
        else:
            rec_id = str(uuid.uuid4())
            full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
            # 1. 更新主表
            summary_detail = ", ".join([i['item_name'] for i in st.session_state.temp_items])
            new_m = {"日期": full_dt, "類別": "保養", "里程": a_km, "金額": total_sum, "細目": summary_detail, "漏記": "No", "備註": a_note, "店家": a_shop, "id": rec_id}
            new_master_df = pd.concat([master_df, pd.DataFrame([new_m])], ignore_index=True)
            
            # 2. 更新細目表
            new_details = []
            for item in st.session_state.temp_items:
                item['parent_id'] = rec_id
                new_details.append(item)
            new_detail_df = pd.concat([detail_df, pd.DataFrame(new_details)], ignore_index=True)
            
            # 3. 推送到 GitHub
            repo.update_file("data.csv", "Add Master", new_master_df.to_csv(index=False), master_sha)
            repo.update_file("service_details.csv", "Add Details", new_detail_df.to_csv(index=False), repo.get_contents("service_details.csv").sha)
            
            st.session_state.temp_items = []
            st.cache_data.clear()
            st.success("儲存成功！")
            st.rerun()
