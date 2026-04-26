import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import pytz
import uuid
import re

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v31.5 Pro", page_icon="🚗", layout="centered")

# --- CSS 樣式美化 ---
st.markdown("""
<style>
    div.stButton > button:first-child { border-radius: 8px; height: 3em; width: 100%; }
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 10px; }
    .metric-card h2 { color: #ff4b4b; margin: 0; }
    .metric-card h5 { color: #555; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 參數設定 ---
CAR_CONFIG = {
    "🛵 小迪": {"sheet": "小迪", "gas": ["92無鉛", "95無鉛"], "def_gas": "92無鉛"},
    "🐳 小白鯨": {"sheet": "小白鯨", "gas": ["95無鉛", "98無鉛"], "def_gas": "98無鉛"}
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
    try:
        sh = client.open("MyMoto99_Data")
        return sh.worksheet(sheet_name)
    except Exception as e:
        st.error(f"❌ 找不到分頁 [{sheet_name}]，請確認名稱是否正確。")
        st.stop()

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

# --- 編輯/管理彈窗 ---
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
                wks.update(range_name=f'A{r}', values=[[full_dt]])
                wks.update(range_name=f'C{r}:H{r}', values=[[new_km, new_amt, new_detail, new_miss, new_note, new_shop]])
                st.rerun()
        if cd.form_submit_button("🗑️ 刪除", type="secondary"):
            cells = wks.findall(row['id'])
            if cells: wks.delete_rows(cells[0].row); st.rerun()

# --- 主介面頁籤 ---
st.title(f"{selected_label}")
tab1, tab2, tab3 = st.tabs(["🏠 歷史", "➕ 新增", "📊 數據"])

with tab1:
    if df.empty: st.info(f"[{selected_label}] 目前尚無資料")
    else:
        st.metric("目前里程", f"{int(df['里程'].max())} km")
        for i, row in df.head(20).iterrows():
            icon = "⛽" if row['類別'] == "加油" else "🛠️"
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
        # 1. 本月支出
        this_month = datetime.now(TAIPEI_TZ).strftime('%Y-%m')
        monthly_total = df[df['日期'].dt.strftime('%Y-%m') == this_month]['金額'].sum()
        
        # 2. 油耗計算邏輯 (兩筆以上加油紀錄)
        gas_df = df[(df['類別'] == '加油') & (df['漏記'] != 'Yes')].sort_values('日期')
        avg_eff = 0
        if len(gas_df) >= 2:
            total_dist = gas_df['里程'].max() - gas_df['里程'].min()
            try:
                liters = []
                for x in gas_df['細目']:
                    match = re.search(r"(\d+\.?\d*)L", str(x))
                    if match: liters.append(float(match.group(1)))
                # 排除第一筆加油量(因為里程從那開始算)或採總量平均。
                # 這裡採標準算法：總里程差 / (總公升 - 最後一筆)
                if total_dist > 0 and len(liters) >= 2:
                    avg_eff = round(total_dist / sum(liters[1:]), 2)
            except: avg_eff = 0

        # 顯示看板
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="metric-card"><h5>本月總支出</h5><h2>${int(monthly_total)}</h2></div>', unsafe_allow_html=True)
        with c2:
            display_eff = f"{avg_eff} <small>km/L</small>" if avg_eff > 0 else "--"
            st.markdown(f'<div class="metric-card"><h5>平均油耗</h5><h2>{display_eff}</h2></div>', unsafe_allow_html=True)
        
        st.divider()
        st.write("📊 **累計支出比例**")
        st.bar_chart(df.groupby('類別')['金額'].sum())
        
        st.write("📈 **里程增長趨勢**")
        st.line_chart(df.sort_values('日期').set_index('日期')['里程'])
    else:
        st.info("尚無數據可供統計。")
