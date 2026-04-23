import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import pytz
import uuid
import time

# ─────────────────────────────────────────
# 1. 頁面配置
# ─────────────────────────────────────────
st.set_page_config(page_title="MyMoto99 v24.1", page_icon="🛵", layout="centered")

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
    }
    .service-item-box {
        background-color: rgba(151, 166, 195, 0.12);
        padding: 10px 15px;
        border-radius: 10px;
        margin-bottom: 6px;
        border-left: 5px solid #ff4b4b;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
</style>
""", unsafe_allow_html=True)

REPO_NAME = "rickyang623/my-moto-app"
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# ─────────────────────────────────────────
# 2. GitHub 連線
# ─────────────────────────────────────────
try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error(f"GitHub 驗證失敗：{e}")
    st.stop()

# ─────────────────────────────────────────
# 3. 資料載入（無快取，確保即時）
# ─────────────────────────────────────────
def get_realtime_data():
    """直接向 GitHub 索取最新檔案內容，繞過所有快取"""
    try:
        # 主表
        m_file = repo.get_contents("data.csv")
        m_df = pd.read_csv(io.StringIO(m_file.decoded_content.decode('utf-8')))
        m_df['日期'] = pd.to_datetime(m_df['日期'], errors='coerce')
        m_df = m_df.dropna(subset=['日期'])
        m_df['里程'] = pd.to_numeric(m_df['里程'], errors='coerce').fillna(0).astype(int)
        # FIX #6：確保 id 欄位為字串，避免 parent_id 比對失敗
        if 'id' in m_df.columns:
            m_df['id'] = m_df['id'].astype(str)

        # 細項表
        d_file = repo.get_contents("service_details.csv")
        d_df = pd.read_csv(io.StringIO(d_file.decoded_content.decode('utf-8')))
        # FIX #6：確保 parent_id 為字串
        if 'parent_id' in d_df.columns:
            d_df['parent_id'] = d_df['parent_id'].astype(str)

        m_df_sorted = m_df.sort_values("日期", ascending=False).reset_index(drop=True)
        return m_df_sorted, d_df, m_file.sha

    except Exception as e:
        st.error(f"資料載入失敗：{e}")
        return pd.DataFrame(), pd.DataFrame(), None

master_df, detail_df, current_sha = get_realtime_data()

# FIX #2：將 latest_km 移至全域，tab1 / tab2 都可使用
latest_km = int(master_df['里程'].max()) if not master_df.empty else 0

# ─────────────────────────────────────────
# 4. Session State 初始化
# ─────────────────────────────────────────
if 'temp_items' not in st.session_state:
    st.session_state.temp_items = []
if 'edit_idx' not in st.session_state:
    st.session_state.edit_idx = None

# ─────────────────────────────────────────
# 5. Dialog：新增保養項目
# ─────────────────────────────────────────
@st.dialog("➕ 新增項目")
def add_item_dialog():
    PRESET_ITEMS = [
        "機油", "齒輪油", "空氣濾芯", "火星塞",
        "煞車來令片", "傳動皮帶（CVT）", "輪胎",
        "電瓶", "煞車油", "維修/自訂項目"
    ]
    item_type = st.selectbox("項目名稱", PRESET_ITEMS)

    # FIX #10：選「維修/自訂項目」時顯示自由輸入欄
    custom_name = ""
    if item_type == "維修/自訂項目":
        custom_name = st.text_input("請輸入自訂項目名稱")

    c1, c2 = st.columns(2)
    u_price = c1.number_input("單價", min_value=0, step=10)
    u_qty   = c2.number_input("數量", min_value=1, value=1)

    if st.button("確認加入", use_container_width=True):
        final_name = custom_name.strip() if item_type == "維修/自訂項目" and custom_name.strip() else item_type
        st.session_state.temp_items.append({
            "item_name": final_name,
            "price": u_price,
            "qty": u_qty,
            "total": u_price * u_qty
        })
        st.rerun()

# ─────────────────────────────────────────
# 6. Dialog：紀錄詳情 & 刪除
#    FIX #3：移至全域定義，避免每次 render 重新 decorate
# ─────────────────────────────────────────
@st.dialog("📋 紀錄詳情")
def view_dialog(index):
    row = master_df.iloc[index]
    st.write(f"📅 {row['日期'].strftime('%Y-%m-%d %H:%M')} | 📍 {row['里程']} km")
    st.success(f"金額：${int(row['金額'])}")
    st.divider()

    row_id = str(row.get('id', ''))
    items = detail_df[detail_df['parent_id'] == row_id] if row_id else pd.DataFrame()

    if not items.empty:
        for _, item in items.iterrows():
            st.markdown(f"**{item['item_name']}** : ${item['total']} ({item['qty']}x{item['price']})")
    else:
        st.info(str(row.get('細目', '無細項資料')))

    st.divider()
    if st.button("🗑️ 刪除紀錄", type="secondary", use_container_width=True):
        try:
            # FIX #4：同步刪除 service_details.csv 中對應細項
            new_m = master_df.drop(index).reset_index(drop=True)
            new_m['日期'] = new_m['日期'].dt.strftime('%Y-%m-%d %H:%M')

            m_latest_file = repo.get_contents("data.csv")
            repo.update_file("data.csv", "Del record", new_m.to_csv(index=False), m_latest_file.sha)

            if row_id and not detail_df.empty:
                new_d = detail_df[detail_df['parent_id'] != row_id].reset_index(drop=True)
                d_latest_file = repo.get_contents("service_details.csv")
                repo.update_file("service_details.csv", "Del details", new_d.to_csv(index=False), d_latest_file.sha)

            st.session_state.edit_idx = None
            st.toast("紀錄已刪除")
            time.sleep(0.5)
            st.rerun()
        except Exception as e:
            st.error(f"刪除失敗：{e}")

# FIX #3：在全域呼叫 dialog（不放在條件式內部定義）
if st.session_state.edit_idx is not None:
    view_dialog(st.session_state.edit_idx)

# ─────────────────────────────────────────
# 7. 主介面
# ─────────────────────────────────────────
tab1, tab2 = st.tabs(["🏠 首頁", "➕ 新增紀錄"])

# ── Tab 1：首頁 ──────────────────────────
with tab1:
    st.write(f"🛵 目前里程：**{latest_km} km**")

    if st.button("🔄 重新載入雲端資料", use_container_width=True):
        st.rerun()

    for index, row in master_df.head(20).iterrows():
        icon  = "⛽" if row['類別'] == '加油' else "🛠️"
        label = f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | ${int(row['金額'])}"
        if st.button(label, key=f"r_{index}", use_container_width=True):
            st.session_state.edit_idx = index
            st.rerun()

# ── Tab 2：新增紀錄 ──────────────────────
with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)
    now  = datetime.now(TAIPEI_TZ)

    # FIX #1：在 form 外預先初始化，避免加油模式下 save_trigger NameError
    save_trigger = False

    with st.form("main_form", clear_on_submit=True):
        c1, c2  = st.columns(2)
        a_date  = c1.date_input("日期", now.date())
        a_time  = c2.time_input("時間", now.time())
        a_km    = st.number_input("里程 (km)", value=latest_km, min_value=0)
        a_shop  = st.text_input("店家") if mode == "🛠️ 保養維修" else ""
        a_note  = st.text_area("備註")

        if mode == "⛽ 加油":
            a_amt = st.number_input("金額", min_value=0)
            if st.form_submit_button("🚀 儲存加油", use_container_width=True):
                try:
                    full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')
                    # 重新抓最新 SHA，避免 race condition
                    m_df_latest, _, m_sha = get_realtime_data()
                    new_row = pd.DataFrame([{
                        "日期": full_dt, "類別": "加油",
                        "里程": a_km, "金額": a_amt,
                        "細目": "加油", "id": str(uuid.uuid4())
                    }])
                    new_m = pd.concat([m_df_latest, new_row], ignore_index=True)
                    repo.update_file("data.csv", "Add Gas", new_m.to_csv(index=False), m_sha)
                    st.toast("加油紀錄存檔成功！")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"儲存失敗：{e}")
        else:
            # FIX #1：save_trigger 在 form 內賦值
            save_trigger = st.form_submit_button("💾 儲存保養紀錄", use_container_width=True)

    # ── 保養項目管理（form 外）────────────
    if mode == "🛠️ 保養維修":
        if st.button("➕ 新增保養項目", use_container_width=True):
            add_item_dialog()

        total_sum = 0
        if st.session_state.temp_items:
            for i, item in enumerate(st.session_state.temp_items):
                col_item, col_del = st.columns([5, 1])
                col_item.markdown(
                    f"""<div class="service-item-box"><b>{item['item_name']}</b> <b>${item['total']}</b></div>""",
                    unsafe_allow_html=True
                )
                # FIX #9：支援刪除單一項目
                if col_del.button("✕", key=f"del_{i}"):
                    st.session_state.temp_items.pop(i)
                    st.rerun()
                total_sum += item['total']

            st.write(f"### 總計：${total_sum}")
            if st.button("🗑️ 清空清單", use_container_width=True, type="secondary"):
                st.session_state.temp_items = []
                st.rerun()

        # FIX #1：save_trigger 已在全域初始化，此處安全使用
        if save_trigger:
            if not st.session_state.temp_items:
                st.error("請先新增保養項目")
            else:
                with st.spinner("同步至 GitHub..."):
                    try:
                        m_df_latest, d_df_latest, m_sha = get_realtime_data()
                        rec_id  = str(uuid.uuid4())
                        full_dt = datetime.combine(a_date, a_time).strftime('%Y-%m-%d %H:%M')

                        summary = ", ".join([i['item_name'] for i in st.session_state.temp_items])
                        new_row = pd.DataFrame([{
                            "日期": full_dt, "類別": "保養",
                            "里程": a_km, "金額": total_sum,
                            "店家": a_shop, "備註": a_note,
                            "細目": summary, "id": rec_id
                        }])
                        new_m = pd.concat([m_df_latest, new_row], ignore_index=True)

                        new_items = [dict(item, parent_id=rec_id) for item in st.session_state.temp_items]
                        new_d = pd.concat([d_df_latest, pd.DataFrame(new_items)], ignore_index=True)

                        # FIX #5：分別取最新 SHA 再推送，降低 race condition 風險
                        repo.update_file("data.csv", "Add Service", new_m.to_csv(index=False), m_sha)
                        d_latest_file = repo.get_contents("service_details.csv")
                        repo.update_file("service_details.csv", "Add Details", new_d.to_csv(index=False), d_latest_file.sha)

                        st.session_state.temp_items = []
                        st.toast("保養紀錄已同步！")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"儲存失敗：{e}")
