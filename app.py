import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import pytz
import uuid
import re

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v31.3", page_icon="🛵", layout="centered")

# --- CSS 樣式 ---
st.markdown("""
<style>
    div.stButton > button:first-child { border-radius: 8px; height: 3em; width: 100%; }
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 參數設定 ---
CAR_CONFIG = {
    "🛵 小迪 (機車)": {"sheet": "小迪", "gas": ["92無鉛", "95無鉛"], "def_gas": "92無鉛"},
    "🐳 小白鯨 (汽車)": {"sheet": "小白鯨", "gas": ["95無鉛", "98無鉛"], "def_gas": "98無鉛"}
}
MAINTAIN_TYPES = ["定期保養", "零件維修", "輪胎相關", "規費/保險", "美容/洗車", "其他"]
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# --- 核心連線引擎 ---
@st.cache_resource
def get_worksheet(sheet_name):
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds_info = st.secrets["gsheet"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    client = gspread.authorize(creds)
    sh = client.open("MyMoto99_Data")
    return sh.worksheet(sheet_name)

# --- 側邊欄：切換車輛 ---
with st.sidebar:
    st.title("🚜 我的車庫")
    selected_label = st.selectbox("切換操作車輛", list(CAR_CONFIG.keys()))
    current_conf = CAR_CONFIG[selected_label]
    st.info(f"管理中：{selected_label}")

wks = get_worksheet(current_conf["sheet"])

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

# --- 編輯彈窗 (修正：加入漏記編輯) ---
@st.dialog("📝 管理紀錄")
def manage_entry(idx):
    row = df.iloc[idx]
    is_gas = (row['類別'] == "加油")
    with st.form("edit_form"):
        c1, c2 = st.columns(2)
        new_date = c1.date_input("日期", row['日期'].date())
        new_time = c2.time_input("時間", row['日期'].time())
        c3, c4 = st.columns(2)
        new_km = c3.number_input("里程 (km)", value=int(row['里程']), step=1)
        new_amt = c4.number_input("金額 ($)", value=int(row['金額']), step=1)
        
        new_miss = row['漏記']
        if is_gas:
            current_type = row['細目'].split('/')[0] if '/' in row['細目'] else current_conf["def_gas"]
            selected_gas = st.selectbox("油種", current_conf["gas"], index=current_conf["gas"].index(current_type) if current_type in current_conf["gas"] else 0)
            new_detail, new_shop = f"{selected_gas}/{round(new_amt/GAS_PRICES.get(selected_gas, 34), 2)}L", ""
            # 加油紀錄顯示漏記勾選
            new_miss = "Yes" if st.checkbox("這是一筆漏記紀錄", value=(row['漏記'] == "Yes")) else "No"
        else:
            match = re.match(r"\[(.*?)\]\s*(.*)", str(row['細目']))
            tag = match.group(1) if match and match.group(1) in MAINTAIN_TYPES else "定期保養"
            content = match.group(2) if match else str(row['細目'])
            new_tag = st.selectbox("類別", MAINTAIN_TYPES, index=MAINTAIN_TYPES.index(tag))
            new_content = st.text_area("保養內容", value=content)
            new_detail = f"[{new_tag}] {new_content}"
            new_shop = st.text_input("店家", value=str(row['店家']))
            
        new_note = st.text_area("備註", value=str(row['備註']))
        st.divider()
        cs, cd = st.columns(2)
        if cs.form_submit_button("💾 儲存修改"):
            full_dt = datetime.combine(new_date, new_time).strftime('%Y-%m-%d %H:%M')
            cells = wks.findall(row['id'])
            if cells:
                r = cells[0].row
                # 更新 A:日期, C:里程, D:金額, E:細目, F:漏記, G:備註, H:店家
                wks.update(range_name=f'A{r}', values=[[full_dt]])
                wks.update(range_name=f'C{r}:H{r}', values=[[new_km, new_amt, new_detail, new_miss, new_note, new_shop]])
                st.rerun()
        if cd.form_submit_button("🗑️ 刪除", type="secondary"):
            cells = wks.findall(row['id'])
            if cells: wks.delete_rows(cells[0].row); st.rerun()

# --- 主介面 ---
st.title(f"{selected_label}")
tab1, tab2, tab3 = st.tabs(["🏠 歷史", "➕ 新增", "📊 數據"])

with tab1:
    if df.empty: st.info("尚無資料")
    else:
        st.metric("目前里程", f"{int(df['里程'].max())} km")
        for i, row in df.head(20).iterrows():
            icon = "⛽" if row['類別'] == "加油" else "🛠️"
            # 如果是漏記，標題加個提示
            miss_tag = " (漏記)" if row['漏記'] == "Yes" else ""
            if st.button(f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | ${int(row['金額'])}{miss_tag}", key=f"rec_{i}"):
                manage_entry(i)

with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", datetime.now(TAIPEI_TZ).date())
        a_time = c2.time_input("時間", datetime.now(TAIPEI_TZ).time())
        a_km = st.number_input("目前里程 (km)", value=int(df['里程'].max() if not df.empty else 0))
        
        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", current_conf["gas"])
            a_amt = st.number_input("金額 ($)", min_value=0)
            a_miss = st.checkbox("這是漏記紀錄 (此次油耗不列入計算)")
            a_note = st.text_input("備註")
            if st.form_submit_button("🚀 儲存加油"):
                dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                miss_val = "Yes" if a_miss else "No"
                # 順序：日期, 類別, 里程, 金額, 細目, 漏記, 備註, 店家, id
                wks.append_row([dt, "加油", a_km, a_amt, f"{a_type}/{round(a_amt/GAS_PRICES.get(a_type, 34), 2)}L", miss_val, a_note, "", str(uuid.uuid4())])
                st.rerun()
        else:
            a_tag = st.selectbox("大類別", MAINTAIN_TYPES)
            a_items = st.text_area("保養內容詳情")
            a_total = st.number_input("總金額 ($)", min_value=0)
            a_shop = st.text_input("施工店家")
            a_note = st.text_area("備註")
            if st.form_submit_button("💾 儲存保養"):
                dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                full_detail = f"[{a_tag}] {a_items}"
                wks.append_row([dt, "保養", a_km, a_total, full_detail, "No", a_note, a_shop, str(uuid.uuid4())])
                st.rerun()

with tab3:
    if not df.empty:
        # 計算平均油耗時，排除「漏記=Yes」的項目
        gas_df = df[(df['類別'] == '加油') & (df['漏記'] != 'Yes')].sort_values('日期')
        # ... (其餘統計邏輯維持不變)
        monthly_total = df[df['日期'].dt.strftime('%Y-%m') == datetime.now(TAIPEI_TZ).strftime('%Y-%m')]['金額'].sum()
        st.metric("本月總支出", f"${int(monthly_total)}")
        st.write("📊 **支出比例**")
        st.bar_chart(df.groupby('類別')['金額'].sum())
    else: st.info("尚無數據。")
