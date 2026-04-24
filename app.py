import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import pytz
import uuid
import re

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v26.0 Pro", page_icon="🛵", layout="centered")

# --- CSS 樣式美化 ---
st.markdown("""
<style>
    div.stButton > button:first-child {
        border-radius: 8px;
        height: 3em;
        width: 100%;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 10px;
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
    
    all_worksheets = [w.title for w in sh.worksheets()]
    target = next((t for t in all_worksheets if t.strip().lower() == "master"), None)
    return sh.worksheet(target) if target else sh.get_worksheet(0)

wks = get_worksheet()

# --- 數據載入 ---
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

# --- 編輯/刪除 彈窗邏輯 (回歸原始置頂模式) ---
@st.dialog("📝 管理紀錄")
def manage_entry(idx):
    row = df.iloc[idx]
    is_gas = (row['類別'] == "加油")
    
    with st.form("edit_form"):
        # 日期時間直接置頂
        c1, c2 = st.columns(2)
        new_date = c1.date_input("日期", row['日期'].date())
        new_time = c2.time_input("時間", row['日期'].time())
        
        st.divider()

        # 主要數據
        c3, c4 = st.columns(2)
        new_km = c3.number_input("里程 (km)", value=int(row['里程']), step=1)
        new_amt = c4.number_input("金額 ($)", value=int(row['金額']), step=1)
        
        if is_gas:
            current_type = row['細目'].split('/')[0] if '/' in row['細目'] else "92無鉛"
            selected_gas = st.selectbox("油種", list(GAS_PRICES.keys()), 
                                      index=list(GAS_PRICES.keys()).index(current_type) if current_type in GAS_PRICES else 0)
            new_l = round(new_amt / GAS_PRICES[selected_gas], 2) if new_amt > 0 else 0.0
            new_detail, new_shop = f"{selected_gas}/{new_l}L", ""
        else:
            new_detail = st.text_area("項目", value=str(row['細目']))
            new_shop = st.text_input("店家", value=str(row['店家']))
            
        new_note = st.text_area("備註", value=str(row['備註']))

        st.divider()
        cs, cd = st.columns(2)
        
        if cs.form_submit_button("💾 儲存修改", use_container_width=True):
            full_dt = datetime.combine(new_date, new_time).strftime('%Y-%m-%d %H:%M')
            cells = wks.findall(row['id'])
            if cells:
                r = cells[0].row
                wks.update(range_name=f'A{r}', values=[[full_dt]])
                wks.update(range_name=f'C{r}:E{r}', values=[[new_km, new_amt, new_detail]])
                wks.update(range_name=f'G{r}:H{r}', values=[[new_note, new_shop]])
                st.rerun()

        if cd.form_submit_button("🗑️ 刪除", type="secondary", use_container_width=True):
            cells = wks.findall(row['id'])
            if cells:
                wks.delete_rows(cells[0].row)
                st.rerun()

# --- 主介面 ---
st.title("🛵 小迪紀錄 Pro")
tab1, tab2, tab3 = st.tabs(["🏠 歷史紀錄", "➕ 新增紀錄", "📊 數據統計"])

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
                wks.append_row([dt, "加油", a_km, a_amt, f"{a_type}/{round(a_amt/GAS_PRICES[a_type],2)}L", "No", a_note, "", str(uuid.uuid4())])
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
    if not df.empty:
        # 數據統計邏輯與前版一致
        this_month = datetime.now(TAIPEI_TZ).strftime('%Y-%m')
        monthly_total = df[df['日期'].dt.strftime('%Y-%m') == this_month]['金額'].sum()
        gas_df = df[df['類別'] == '加油'].sort_values('日期')
        avg_eff = 0
        if len(gas_df) >= 2:
            total_dist = gas_df['里程'].max() - gas_df['里程'].min()
            all_l = sum([float(re.search(r"(\d+\.?\d*)L", str(x)).group(1)) for x in gas_df['細目'] if 'L' in str(x)])
            if all_l > 0: avg_eff = round(total_dist / all_l, 2)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="metric-card"><h5>本月總支出</h5><h2>${int(monthly_total)}</h2></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><h5>平均油耗</h5><h2>{avg_eff} <small>km/L</small></h2></div>', unsafe_allow_html=True)
        
        st.divider()
        col_left, col_right = st.columns(2)
        with col_left:
            st.write("📊 **支出佔比**")
            st.bar_chart(df.groupby('類別')['金額'].sum())
        with col_right:
            st.write("📈 **里程增長**")
            st.line_chart(df.sort_values('日期').set_index('日期')['里程'])
    else:
        st.info("尚無數據。")
