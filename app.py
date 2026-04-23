import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz
import base64

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v21.3", page_icon="🛵", layout="centered")

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
    .stTextInput { height: 0px !important; padding: 0px !important; margin: 0px !important; opacity: 0 !important; }
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

@st.cache_data(ttl=60)
def load_data():
    file_content = repo.get_contents(FILE_PATH)
    data = pd.read_csv(io.StringIO(file_content.decoded_content.decode('utf-8')))
    for col in ['漏記', '備註', '照片', '店家', '類別']:
        if col not in data.columns: data[col] = 'No' if col == '漏記' else ''
    data['日期'] = pd.to_datetime(data['日期'])
    data = data.sort_values("日期", ascending=False).reset_index(drop=True)
    return data, file_content.sha

df, file_sha_val = load_data()

# 初始化狀態
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None
if 'mode' not in st.session_state: st.session_state.mode = "view" # view or edit

def img_to_b64(file):
    return base64.b64encode(file.getvalue()).decode() if file else ""

# 3. 詳情與編輯彈窗
@st.dialog("📋 紀錄管理")
def manage_dialog(index):
    row = df.iloc[index]
    
    if st.session_state.mode == "view":
        st.write(f"📅 **日期：** {row['日期'].strftime('%Y-%m-%d %H:%M')}")
        st.write(f"🏷️ **類別：** {row['類別']} | 📍 {row['里程']} km")
        if row['類別'] == '保養' and row['店家']: st.write(f"🏠 **店家：** {row['店家']}")
        st.success(f"💰 **金額：** ${int(row['金額'])}")
        st.divider()
        st.write("**明細：**")
        st.info(row['細目'])
        if row['備註']: st.write(f"💬 備註：{row['備註']}")
        if row['照片'] and str(row['照片']).strip() != "":
            try: st.image(base64.b64decode(row['照片']), use_container_width=True)
            except: st.warning("⚠️ 圖片損壞")
        
        st.divider()
        c1, c2 = st.columns(2)
        if c1.button("📝 進入編輯模式", use_container_width=True):
            st.session_state.mode = "edit"
            st.rerun()
        if c2.button("🗑️ 刪除紀錄", use_container_width=True, type="secondary"):
            new_df = df.drop(index).reset_index(drop=True)
            new_df['日期'] = new_df['日期'].dt.strftime('%Y-%m-%d %H:%M')
            repo.update_file(FILE_PATH, "Delete", new_df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
            st.cache_data.clear()
            st.session_state.edit_idx = None
            st.rerun()

    else: # 編輯模式
        with st.form("edit_mode_form"):
            st.write("🔧 **正在編輯紀錄**")
            e_date = st.date_input("日期", row['日期'].date())
            e_time = st.time_input("時間", row['日期'].time())
            e_km = st.number_input("里程 (km)", value=int(row['里程']))
            e_amt = st.number_input("金額 ($)", value=int(row['金額']))
            e_note = st.text_area("備註", value=str(row['備註']))
            
            # 根據類別顯示特定欄位
            e_miss = row['漏記']
            e_shop = row['店家']
            e_detail = row['細目']
            
            if row['類別'] == "加油":
                e_miss_bool = st.checkbox("漏記標記", value=(row['漏記'] == "Yes"))
                e_miss = "Yes" if e_miss_bool else "No"
            else:
                e_shop = st.text_input("店家", value=str(row['店家']))
                e_detail = st.text_area("保養明細", value=str(row['細目']))

            if st.form_submit_button("💾 儲存更新", use_container_width=True):
                full_dt = datetime.combine(e_date, e_time).strftime('%Y-%m-%d %H:%M')
                df.loc[index, '日期'] = pd.to_datetime(full_dt)
                df.loc[index, '里程'] = e_km
                df.loc[index, '金額'] = e_amt
                df.loc[index, '備註'] = e_note
                df.loc[index, '漏記'] = e_miss
                df.loc[index, '店家'] = e_shop
                df.loc[index, '細目'] = e_detail
                
                final_df = df.sort_values("日期", ascending=False)
                final_df['日期'] = final_df['日期'].dt.strftime('%Y-%m-%d %H:%M')
                repo.update_file(FILE_PATH, "Edit", final_df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
                st.cache_data.clear()
                st.session_state.edit_idx = None
                st.session_state.mode = "view"
                st.rerun()
            
            if st.button("⬅️ 返回檢視", use_container_width=True):
                st.session_state.mode = "view"
                st.rerun()

if st.session_state.edit_idx is not None: manage_dialog(st.session_state.edit_idx)

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "➕ 新增紀錄"])

with tab1:
    st.write("🛵 <span style='font-size: 13px; color: gray;'>小迪</span>", unsafe_allow_html=True)
    
    # 油耗計算 (精準過濾版)
    avg_eff = "--"
    gas_only = df[df['類別'] == '加油'].copy().reset_index(drop=True)
    if len(gas_only) >= 2 and gas_only.iloc[0]['漏記'] != 'Yes':
        try:
            curr_km = float(gas_only.iloc[0]['里程'])
            prev_km = float(gas_only.iloc[1]['里程'])
            match = re.search(r"(\d+\.?\d*)L", gas_only.iloc[1]['細目'])
            if match:
                prev_liters = float(match.group(1))
                if prev_liters > 0: avg_eff = f"{round((curr_km - prev_km) / prev_liters, 1)}"
        except: avg_eff = "--"

    latest_km = df['里程'].max() if not df.empty else 0
    dashboard_html = f"""
    <div style="display: flex; gap: 8px; margin: 5px 0 15px 0;">
        <div style="flex: 1; background: white; padding: 15px 10px; border-radius: 12px; border: 1px solid #f0f2f6; box-shadow: 0 1px 2px rgba(0,0,0,0.05); text-align: center;">
            <div style="font-size: 12px; color: #666;">目前里程</div>
            <div style="font-size: 22px; font-weight: 800; color: #31333F;">{latest_km} <span style="font-size: 13px;">km</span></div>
        </div>
        <div style="flex: 1; background: white; padding: 15px 10px; border-radius: 12px; border: 1px solid #f0f2f6; box-shadow: 0 1px 2px rgba(0,0,0,0.05); text-align: center;">
            <div style="font-size: 12px; color: #666;">平均油耗</div>
            <div style="font-size: 22px; font-weight: 800; color: #31333F;">{avg_eff} <span style="font-size: 13px;">km/L</span></div>
        </div>
    </div>
    """
    st.markdown(dashboard_html, unsafe_allow_html=True)
    
    st.write("📖 **活動紀錄**")
    items_per_page = 10
    total_pages = max((len(df) // items_per_page) + (1 if len(df) % items_per_page > 0 else 0), 1)
    page = st.select_slider("頁碼", options=range(1, total_pages + 1), value=1) if total_pages > 1 else 1
    
    for index, row in df.iloc[(page-1)*items_per_page : page*items_per_page].iterrows():
        icon = "⛽" if row['類別'] == '加油' else "🛠️"
        miss_tag = " ⚠️" if row['漏記'] == 'Yes' else ""
        label = f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | {row['里程']}k | ${int(row['金額'])}{miss_tag}"
        if st.button(label, key=f"rec_{index}", use_container_width=True):
            st.session_state.edit_idx = index
            st.session_state.mode = "view"
            st.rerun()

with tab2:
    mode = st.radio("選擇紀錄類型", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    now = datetime.now(TAIPEI_TZ)
    with st.form("main_form", clear_on_submit=True):
        st.text_input("Focus", label_visibility="collapsed")
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", now.date())
        a_time = c2.time_input("時間", now.time())
        a_km = st.number_input("目前里程 (km)", min_value=0, value=int(latest_km))
        a_shop = st.text_input("施工店家 (選填)") if mode == "🛠️ 保養維修" else ""
        a_photo = st.file_uploader("新增照片", type=['png', 'jpg', 'jpeg'])
        a_note = st.text_area("備註 (選填)")

        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
            a_amt = st.number_input("加油金額 ($)", min_value=0, step=10)
            a_miss = st.checkbox("本次紀錄前有漏掉次數")
            calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
            st.info(f"💡 自動換算：{calc_L} L")
            if st.form_submit_button("🚀 儲存加油", use_container_width=True):
                photo_b64 = img_to_b64(a_photo)
                new_row = {"日期": datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M'), "類別": "加油", "里程": a_km, "金額": a_amt, "細目": f"{a_type}/{calc_L}L", "漏記": "Yes" if a_miss else "No", "備註": a_note, "照片": photo_b64, "店家": ""}
                new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                repo.update_file(FILE_PATH, "Add", new_df.sort_values("日期", ascending=False).to_csv(index=False), repo.get_contents(FILE_PATH).sha)
                st.cache_data.clear()
                st.rerun()
        else:
            a_items = st.text_area("保養項目", placeholder="機油 450")
            a_total = st.number_input("總計金額 ($)", min_value=0)
            if st.form_submit_button("💾 儲存保養", use_container_width=True):
                photo_b64 = img_to_b64(a_photo)
                new_row = {"日期": datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M'), "類別": "保養", "里程": a_km, "金額": a_total, "細目": a_items.replace("\n", ", "), "漏記": "No", "備註": a_note, "照片": photo_b64, "店家": a_shop}
                new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                repo.update_file(FILE_PATH, "Service", new_df.sort_values("日期", ascending=False).to_csv(index=False), repo.get_contents(FILE_PATH).sha)
                st.cache_data.clear()
                st.rerun()
