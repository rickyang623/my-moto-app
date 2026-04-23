import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz
import base64

# 1. 頁面配置
st.set_page_config(page_title="MyMoto99 v20", page_icon="🛵", layout="centered")

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
    # 確保新欄位存在
    for col in ['漏記', '備註', '照片', '店家']:
        if col not in data.columns: data[col] = ''
    data['日期'] = pd.to_datetime(data['日期'])
    data = data.sort_values("日期", ascending=False).reset_index(drop=True)
    return data, file_content.sha

df, file_sha_val = load_data()

if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None

# 照片 Base64 轉換
def img_to_b64(file):
    return base64.b64encode(file.getvalue()).decode() if file else ""

# 3. 詳情查看彈窗
@st.dialog("📝 紀錄詳情")
def view_dialog(index):
    row = df.iloc[index]
    st.write(f"📅 **日期：** {row['日期'].strftime('%Y-%m-%d %H:%M')}")
    st.write(f"🏷️ **類別：** {row['類別']} | 📍 {row['里程']} km")
    if row['店家']: st.write(f"🏠 **店家：** {row['店家']}")
    st.success(f"💰 **總計金額：** ${int(row['金額'])}")
    st.divider()
    st.write("**項目明細：**")
    st.write(row['細目'])
    if row['備註']: st.info(f"備註：{row['備註']}")
    if row['照片']:
        st.image(base64.b64decode(row['照片']), use_container_width=True)
    
    if st.button("🗑️ 刪除紀錄", use_container_width=True, type="secondary"):
        new_df = df.drop(index).reset_index(drop=True)
        new_df['日期'] = new_df['日期'].dt.strftime('%Y-%m-%d %H:%M')
        repo.update_file(FILE_PATH, "Delete", new_df.to_csv(index=False), repo.get_contents(FILE_PATH).sha)
        st.cache_data.clear()
        st.session_state.edit_idx = None
        st.rerun()

if st.session_state.edit_idx is not None: view_dialog(st.session_state.edit_idx)

# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "➕ 新增紀錄"])

with tab1:
    st.write("🛵 <span style='font-size: 13px; color: gray;'>小迪</span>", unsafe_allow_html=True)
    
    # 儀表板
    gas_df = df[df['類別'] == '加油'].copy()
    avg_eff = "--"
    if len(gas_df) >= 2 and gas_df.iloc[0]['漏記'] == 'No':
        try:
            prev_liters = float(re.findall(r"(\d+\.\d+)L", gas_df.iloc[1]['細目'])[0])
            avg_eff = f"{round((gas_df.iloc[0]['里程'] - gas_df.iloc[1]['里程']) / prev_liters, 1)}"
        except: pass

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
    items_per_page = 8
    total_pages = max((len(df) // items_per_page) + (1 if len(df) % items_per_page > 0 else 0), 1)
    page = st.select_slider("頁碼", options=range(1, total_pages + 1), value=1) if total_pages > 1 else 1
    
    start_idx = (page - 1) * items_per_page
    for index, row in df.iloc[start_idx : start_idx + items_per_page].iterrows():
        icon = "⛽" if row['類別'] == '加油' else "🛠️"
        dt = row['日期'].strftime('%m/%d %H:%M')
        km = f"{row['里程']}k"
        amt = f"${int(row['金額'])}"
        summary = row['細目'][:15] + ".."
        
        if st.button(f"{icon} {dt} | {km} | {amt} | {summary}", key=f"rec_{index}", use_container_width=True):
            st.session_state.edit_idx = index
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
        a_shop = st.text_input("施工店家 (選填)")
        a_note = st.text_input("備註 (選填)")
        a_photo = st.file_uploader("新增照片", type=['png', 'jpg', 'jpeg'])

        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
            a_amt = st.number_input("加油金額 ($)", min_value=0, step=10)
            a_miss = st.checkbox("本次紀錄前有漏掉次數")
            calc_L = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
            st.info(f"💡 自動換算：{calc_L} L")
            
            if st.form_submit_button("🚀 儲存加油", use_container_width=True):
                full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                new_row = {"日期": full_dt, "類別": "加油", "里程": a_km, "金額": a_amt, "細目": f"{a_type}/{calc_L}L", "漏記": "Yes" if a_miss else "No", "備註": a_note, "照片": img_to_b64(a_photo), "店家": a_shop}
                new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                new_df['日期'] = pd.to_datetime(new_df['日期'])
                repo.update_file(FILE_PATH, "Gas", new_df.sort_values("日期", ascending=False).to_csv(index=False), repo.get_contents(FILE_PATH).sha)
                st.cache_data.clear()
                st.rerun()

        else: # 保養模式
            st.write("🔧 **保養明細 (可點擊下方表格新增行數)**")
            # 使用數據編輯器，方便一次輸入多項
            init_df = pd.DataFrame([{"項目": "", "單價": 0, "數量": 1}])
            edited_df = st.data_editor(init_df, num_rows="dynamic", use_container_width=True)
            
            # 計算加總
            edited_df['總計'] = edited_df['單價'] * edited_df['數量']
            total_sum = edited_df['總計'].sum()
            st.success(f"💰 總金額預覽：${total_sum}")
            
            if st.form_submit_button("💾 儲存保養紀錄", use_container_width=True):
                # 組合細目字串：機油(1x450), 齒輪油(1x50)...
                items_str = ", ".join([f"{r['項目']}({r['數量']}x{r['單價']})" for _, r in edited_df.iterrows() if r['項目']])
                full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                new_row = {"日期": full_dt, "類別": "保養", "里程": a_km, "金額": total_sum, "細目": items_str, "漏記": "No", "備註": a_note, "照片": img_to_b64(a_photo), "店家": a_shop}
                new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                new_df['日期'] = pd.to_datetime(new_df['日期'])
                repo.update_file(FILE_PATH, "Service", new_df.sort_values("日期", ascending=False).to_csv(index=False), repo.get_contents(FILE_PATH).sha)
                st.cache_data.clear()
                st.rerun()
