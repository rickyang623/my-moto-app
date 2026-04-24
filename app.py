import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import pytz
import uuid
import re

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v25.5", page_icon="🛵", layout="centered")

# --- CSS 樣式 ---
st.markdown("""
<style>
    div.stButton > button:first-child {
        border-radius: 8px;
        height: 3em;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- 核心連線引擎 ---
@st.cache_resource
def get_worksheet():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds_info = st.secrets["gsheet"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    client = gspread.authorize(creds)
    try:
        sh = client.open("MyMoto99_Data")
    except:
        sh = client.open_by_key(creds_info["spreadsheet_id"].strip())
    return sh.worksheet("master")

wks = get_worksheet()

# --- 數據加載 ---
def load_data():
    all_rows = wks.get_all_values()
    if len(all_rows) <= 1: return pd.DataFrame()
    data = pd.DataFrame(all_rows[1:], columns=all_rows[0])
    data['日期'] = pd.to_datetime(data['日期'], errors='coerce')
    data['金額'] = pd.to_numeric(data['金額'], errors='coerce').fillna(0)
    data['里程'] = pd.to_numeric(data['里程'], errors='coerce').fillna(0)
    return data.dropna(subset=['日期']).sort_values("日期", ascending=False).reset_index(drop=True)

df = load_data()
TAIPEI_TZ = pytz.timezone('Asia/Taipei')
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

# --- 編輯/刪除 彈窗邏輯 ---
@st.dialog("📝 管理紀錄")
def manage_entry(idx):
    row = df.iloc[idx]
    is_gas = (row['類別'] == "加油")
    
    with st.form("edit_form"):
        st.subheader(f"{'⛽ 加油' if is_gas else '🛠️ 保養'} 紀錄修改")
        
        # 1. 日期與時間修改
        c1, c2 = st.columns(2)
        new_date = c1.date_input("日期", row['日期'].date())
        new_time = c2.time_input("時間", row['日期'].time())
        
        # 2. 里程與金額
        c3, c4 = st.columns(2)
        new_km = c3.number_input("里程 (km)", value=int(row['里程']))
        new_amt = c4.number_input("金額 ($)", value=int(row['金額']))
        
        # 3. 類別特有項目
        new_detail = row['細目']
        new_shop = row['店家']
        
        if is_gas:
            # 嘗試解析現有的油種 (例如 "92無鉛/5.3L")
            current_gas_type = row['細目'].split('/')[0] if '/' in row['細目'] else "92無鉛"
            if current_gas_type not in GAS_PRICES: current_gas_type = "92無鉛"
            
            selected_gas = st.selectbox("油種", list(GAS_PRICES.keys()), index=list(GAS_PRICES.keys()).index(current_gas_type))
            # 計算公升 (修改金額後自動更新細目)
            new_l = round(new_amt / GAS_PRICES[selected_gas], 2) if new_amt > 0 else 0.0
            new_detail = f"{selected_gas}/{new_l}L"
            new_shop = "" # 加油不需要店家
        else:
            new_detail = st.text_area("保養項目", value=str(row['細目']))
            new_shop = st.text_input("施工店家", value=str(row['店家']))
            
        new_note = st.text_area("備註", value=str(row['備註']))
        
        st.divider()
        col_save, col_del = st.columns(2)
        if col_save.form_submit_button("💾 儲存修改", use_container_width=True):
            full_dt = datetime.combine(new_date, new_time).strftime('%Y-%m-%d %H:%M')
            # 找到在 Google Sheets 中的正確行數 (原始排序下)
            # 因為 df 是排序過的，我們需要靠 'id' 來定位 Sheet 中的行
            cells = wks.findall(row['id'])
            if cells:
                actual_row = cells[0].row
                # 更新 A(1):日期, B(2):類別, C(3):里程, D(4):金額, E(5):細目, G(7):備註, H(8):店家
                updates = [
                    {'range': f'A{actual_row}', 'values': [[full_dt]]},
                    {'range': f'C{actual_row}', 'values': [[new_km]]},
                    {'range': f'D{actual_row}', 'values': [[new_amt]]},
                    {'range': f'E{actual_row}', 'values': [[new_detail]]},
                    {'range': f'G{actual_row}', 'values': [[new_note]]},
                    {'range': f'H{actual_row}', 'values': [[new_shop]]}
                ]
                for up in updates:
                    wks.update(range_name=up['range'], values=up['values'])
                st.success("更新成功！")
                st.rerun()
            else:
                st.error("找不到該筆紀錄的 ID，無法更新。")

        if col_del.form_submit_button("🗑️ 刪除這筆", type="secondary", use_container_width=True):
            cells = wks.findall(row['id'])
            if cells:
                wks.delete_rows(cells[0].row)
                st.rerun()
            else:
                st.error("刪除失敗")

# --- 主介面 ---
st.title("🛵 小迪紀錄 Pro")

tab1, tab2, tab3 = st.tabs(["🏠 歷史紀錄", "➕ 新增", "📊 數據"])

with tab1:
    if df.empty:
        st.info("尚無資料")
    else:
        st.metric("目前里程", f"{int(df['里程'].max())} km")
        for i, row in df.head(20).iterrows():
            icon = "⛽" if row['類別'] == "加油" else "🛠️"
            if st.button(f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | ${int(row['金額'])}", key=f"rec_{i}"):
                manage_entry(i)

with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", datetime.now(TAIPEI_TZ).date())
        a_time = c2.time_input("時間", datetime.now(TAIPEI_TZ).time())
        a_km = st.number_input("里程 (km)", value=int(df['里程'].max() if not df.empty else 0))
        
        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
            a_amt = st.number_input("金額 ($)", min_value=0)
            a_note = st.text_input("備註")
            if st.form_submit_button("🚀 儲存加油", use_container_width=True):
                dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
                # 順序：日期, 類別, 里程, 金額, 細目, 漏記, 備註, 店家, id
                wks.append_row([dt, "加油", a_km, a_amt, f"{a_type}/{calc_L}L", "No", a_note, "", str(uuid.uuid4())])
                st.rerun()
        else:
            a_items = st.text_area("保養項目")
            a_total = st.number_input("金額 ($)", min_value=0)
            a_shop = st.text_input("施工店家")
            a_note = st.text_area("備註")
            if st.form_submit_button("💾 儲存保養", use_container_width=True):
                dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                wks.append_row([dt, "保養", a_km, a_total, a_items, "No", a_note, a_shop, str(uuid.uuid4())])
                st.rerun()

with tab3:
    # (此處可保留原有的統計圖表代碼...)
    st.write("📊 統計功能運作中...")
