import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v22.2 Stable", page_icon="🛵", layout="centered")

# --- CSS 魔法 (簡潔穩定版) ---
st.markdown("""
<style>
    div.stButton > button:first-child {
        background-color: white !important;
        color: #31333F !important;
        border: 1px solid #f0f2f6 !important;
        padding: 10px 15px !important;
        width: 100% !important;
        border-radius: 10px !important;
        margin-bottom: -5px !important;
    }
</style>
""", unsafe_allow_html=True)

REPO_NAME = "rickyang623/my-moto-app"
FILE_PATH = "data.csv"
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# 2. 登入 GitHub
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except:
    st.error("GitHub 驗證失敗")
    st.stop()

@st.cache_data(ttl=30)
def load_data():
    file_content = repo.get_contents(FILE_PATH)
    data = pd.read_csv(io.StringIO(file_content.decoded_content.decode('utf-8')))
    
    # 強制清洗類型
    text_cols = ['漏記', '備註', '店家', '類別', '細目']
    for col in text_cols:
        if col not in data.columns: data[col] = ''
        data[col] = data[col].fillna('').astype(str)
        
    data['日期'] = pd.to_datetime(data['日期'], errors='coerce')
    data = data.dropna(subset=['日期']).sort_values("日期", ascending=False).reset_index(drop=True)
    return data, file_content.sha

df, file_sha_val = load_data()

if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None
if 'dialog_mode' not in st.session_state: st.session_state.dialog_mode = "view"

# 3. 詳情與編輯彈窗
@st.dialog("📋 紀錄管理")
def manage_dialog(index):
    row = df.iloc[index]
    
    if st.session_state.dialog_mode == "view":
        st.write(f"📅 **日期：** {row['日期'].strftime('%Y-%m-%d %H:%M')}")
        st.write(f"🏷️ **類別：** {row['類別']} | 📍 {row['里程']} km")
        if row['店家'] and row['店家'] != 'nan': st.write(f"🏠 **店家：** {row['店家']}")
        st.success(f"💰 **金額：** ${int(row['金額'])}")
        st.divider()
        st.write("**明細：**")
        st.info(row['細目'])
        if row['備註'] and row['備註'] != 'nan' and row['備註'] != '':
            st.write(f"💬 **備註：** {row['備註']}")
        
        st.divider()
        c1, c2 = st.columns(2)
        if c1.button("📝 編輯", use_container_width=True):
            st.session_state.dialog_mode = "edit"
            st.rerun()
        if c2.button("🗑️ 刪除", use_container_width=True, type="secondary"):
            new_df = df.drop(index).reset_index(drop=True)
            new_df['日期'] = new_df['日期'].dt.strftime('%Y-%m-%d %H:%M')
            repo.update_file(FILE_PATH, "Delete", new_df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
            st.cache_data.clear()
            st.session_state.edit_idx = None
            st.rerun()

    else: # 編輯模式
        with st.form("edit_form"):
            e_date = st.date_input("日期", row['日期'].date())
            e_time = st.time_input("時間", row['日期'].time())
            e_km = st.number_input("里程 (km)", value=int(row['里程']))
            e_amt = st.number_input("金額 ($)", value=int(row['金額']))
            e_note = st.text_area("備註", value=str(row['備註']) if str(row['備註']) != 'nan' else "")
            
            e_miss = row['漏記']
            e_shop = row['店家']
            e_detail = row['細目']
            
            if row['類別'] == "加油":
                e_miss_bool = st.checkbox("漏記標記", value=(row['漏記'] == "Yes"))
                e_miss = "Yes" if e_miss_bool else "No"
            else:
                e_shop = st.text_input("施工店家", value=str(row['店家']))
                e_detail = st.text_area("保養明細", value=str(row['細目']))

            if st.form_submit_button("💾 儲存更新", use_container_width=True):
                full_dt = datetime.combine(e_date, e_time).strftime('%Y-%m-%d %H:%M')
                # 直接寫入更新
                df.at[index, '日期'] = pd.to_datetime(full_dt)
                df.at[index, '里程'] = e_km
                df.at[index, '金額'] = e_amt
                df.at[index, '備註'] = e_note
                df.at[index, '漏記'] = e_miss
                df.at[index, '店家'] = e_shop
                df.at[index, '細目'] = e_detail
                
                final_df = df.sort_values("日期", ascending=False)
                final_df['日期'] = final_df['日期'].dt.strftime('%Y-%m-%d %H:%M')
                repo.update_file(FILE_PATH, "Edit", final_df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
                st.cache_data.clear()
                st.session_state.edit_idx = None
                st.session_state.dialog_mode = "view"
                st.rerun()
        if st.button("⬅️ 返回", use_container_width=True):
            st.session_state.dialog_mode = "view"
            st.rerun()

if st.session_state.edit_idx is not None: manage_dialog(st.session_state.edit_idx)

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "➕ 新增紀錄"])

with tab1:
    latest_km = df['里程'].max() if not df.empty else 0
    st.write(f"🛵 目前里程：**{latest_km} km**")
    
    # 油耗計算
    avg_eff = "--"
    gas_only = df[df['類別'] == '加油'].copy().reset_index(drop=True)
    if len(gas_only) >= 2 and gas_only.iloc[0]['漏記'] != 'Yes':
        try:
            curr_km, prev_km = float(gas_only.iloc[0]['里程']), float(gas_only.iloc[1]['里程'])
            match = re.search(r"(\d+\.?\d*)L", str(gas_only.iloc[1]['細目']))
            if match: avg_eff = f"{round((curr_km - prev_km) / float(match.group(1)), 1)}"
        except: pass
    st.metric("平均油耗", f"{avg_eff} km/L")

    for index, row in df.head(15).iterrows():
        icon = "⛽" if row['類別'] == '加油' else "🛠️"
        label = f"{icon} {row['日期'].strftime('%m/%d')} | {row['里程']}k | ${int(row['金額'])}"
        if st.button(label, key=f"r_{index}", use_container_width=True):
            st.session_state.edit_idx = index
            st.session_state.dialog_mode = "view"
            st.rerun()

with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    with st.form("main_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", datetime.now(TAIPEI_TZ).date())
        a_time = c2.time_input("時間", datetime.now(TAIPEI_TZ).time())
        a_km = st.number_input("目前里程 (km)", value=int(latest_km))
        a_shop = st.text_input("施工店家") if mode == "🛠️ 保養維修" else ""
        
        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
            a_amt = st.number_input("金額 ($)", min_value=0)
            a_note = st.text_area("備註")
            if st.form_submit_button("🚀 儲存加油", use_container_width=True):
                full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
                new_r = {"日期": full_dt, "類別": "加油", "里程": a_km, "金額": a_amt, "細目": f"{a_type}/{calc_L}L", "漏記": "No", "備註": a_note, "店家": ""}
                new_df = pd.concat([df, pd.DataFrame([new_r])], ignore_index=True)
                repo.update_file(FILE_PATH, "Add Gas", new_df.sort_values("日期", ascending=False).to_csv(index=False), repo.get_contents(FILE_PATH).sha)
                st.cache_data.clear()
                st.rerun()
        else:
            a_items = st.text_area("保養項目 (例如: 機油, 齒輪油)")
            a_total = st.number_input("總金額 ($)", min_value=0)
            a_note = st.text_area("備註")
            if st.form_submit_button("💾 儲存保養", use_container_width=True):
                full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                new_r = {"日期": full_dt, "類別": "保養", "里程": a_km, "金額": a_total, "細目": a_items, "漏記": "No", "備註": a_note, "店家": a_shop}
                new_df = pd.concat([df, pd.DataFrame([new_r])], ignore_index=True)
                repo.update_file(FILE_PATH, "Add Service", new_df.sort_values("日期", ascending=False).to_csv(index=False), repo.get_contents(FILE_PATH).sha)
                st.cache_data.clear()
                st.rerun()
