import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import requests
import base64
import pytz
import uuid
import time

# ─────────────────────────────────────────
# 1. 頁面配置
# ─────────────────────────────────────────
st.set_page_config(page_title="MyMoto99 v24.4", page_icon="🛵", layout="centered")

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

REPO_NAME  = "rickyang623/my-moto-app"
TAIPEI_TZ  = pytz.timezone('Asia/Taipei')
GAS_PRICES = {"92無鉛": 32.4, "95無鉛": 33.9, "98無鉛": 35.9}

# ─────────────────────────────────────────
# 2. GitHub 連線（PyGithub，僅用於寫入）
# ─────────────────────────────────────────
try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    g    = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error(f"GitHub 驗證失敗：{e}")
    st.stop()

# ─────────────────────────────────────────
# 3. 資料讀取：直接打 REST API + 禁用快取
#    ✅ 完全繞過 PyGithub 物件快取
# ─────────────────────────────────────────
def get_atomic_data(file_name: str):
    """
    使用 requests 直接呼叫 GitHub Contents API，
    並帶 Cache-Control: no-cache 確保每次都拿到最新版本。
    回傳 (DataFrame, sha)
    """
    url     = f"https://api.github.com/repos/{REPO_NAME}/contents/{file_name}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Cache-Control": "no-cache",
        "Pragma":        "no-cache",
    }
    try:
params = {"_": int(time.time() * 1000)}
resp   = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data    = resp.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        df      = pd.read_csv(io.StringIO(content))
        return df, data["sha"]
    except Exception as e:
        st.error(f"讀取 {file_name} 失敗：{e}")
        return pd.DataFrame(), None

def load_master(df: pd.DataFrame) -> pd.DataFrame:
    """清洗主表：型別轉換、排序"""
    if df.empty:
        return df
    df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    df = df.dropna(subset=["日期"]).sort_values("日期", ascending=False).reset_index(drop=True)
    df["里程"] = pd.to_numeric(df["里程"], errors="coerce").fillna(0).astype(int)
    if "id" in df.columns:
        df["id"] = df["id"].astype(str)
    return df

def load_detail(df: pd.DataFrame) -> pd.DataFrame:
    """清洗細項表：確保 parent_id 為字串"""
    if not df.empty and "parent_id" in df.columns:
        df["parent_id"] = df["parent_id"].astype(str)
    return df

# 啟動時讀取
raw_master, master_sha = get_atomic_data("data.csv")
raw_detail, detail_sha = get_atomic_data("service_details.csv")

master_df = load_master(raw_master)
detail_df = load_detail(raw_detail)

# FIX #2：全域計算 latest_km，tab1 / tab2 都可使用
latest_km = int(master_df["里程"].max()) if not master_df.empty else 0

# ─────────────────────────────────────────
# 4. Session State 初始化
# ─────────────────────────────────────────
if "temp_items" not in st.session_state: st.session_state.temp_items = []
if "edit_idx"   not in st.session_state: st.session_state.edit_idx   = None

# ─────────────────────────────────────────
# 5. Dialog：新增保養項目
# ─────────────────────────────────────────
@st.dialog("➕ 新增項目")
def add_item_dialog():
    PRESET = ["機油", "齒輪油", "空氣濾芯", "火星塞",
              "煞車來令片", "傳動皮帶（CVT）", "輪胎",
              "電瓶", "煞車油", "維修/自訂項目"]
    item_type = st.selectbox("項目名稱", PRESET)

    custom_name = ""
    if item_type == "維修/自訂項目":
        custom_name = st.text_input("請輸入自訂項目名稱")

    c1, c2  = st.columns(2)
    u_price = c1.number_input("單價", min_value=0, step=10)
    u_qty   = c2.number_input("數量", min_value=1, value=1)

    if st.button("確認加入", use_container_width=True):
        final_name = (custom_name.strip()
                      if item_type == "維修/自訂項目" and custom_name.strip()
                      else item_type)
        st.session_state.temp_items.append({
            "item_name": final_name,
            "price":     u_price,
            "qty":       u_qty,
            "total":     u_price * u_qty,
        })
        st.rerun()

# ─────────────────────────────────────────
# 6. Dialog：紀錄詳情 & 刪除
#    FIX #3：全域定義，條件式內只呼叫
# ─────────────────────────────────────────
@st.dialog("📋 紀錄管理")
def view_dialog(index: int):
    row    = master_df.iloc[index]
    row_id = str(row.get("id", ""))

    st.write(f"📅 {row['日期'].strftime('%Y-%m-%d %H:%M')} | 📍 {row['里程']} km")
    st.divider()

    items = detail_df[detail_df["parent_id"] == row_id] if row_id else pd.DataFrame()
    if not items.empty:
        for _, item in items.iterrows():
            st.markdown(f"**{item['item_name']}** : ${item['total']} ({item['qty']}x{item['price']})")
    else:
        st.info(str(row.get("細目", "無細項資料")))

    st.divider()
    if st.button("🗑️ 刪除這筆紀錄", type="secondary", use_container_width=True):
        with st.spinner("刪除同步中..."):
            try:
                # FIX #4：同步刪除 service_details.csv 對應細項
                latest_m, sha_m = get_atomic_data("data.csv")
                latest_m = load_master(latest_m)

                new_m = latest_m[latest_m["id"].astype(str) != row_id].reset_index(drop=True)
                new_m["日期"] = new_m["日期"].dt.strftime("%Y-%m-%d %H:%M")
                repo.update_file("data.csv", "Delete record", new_m.to_csv(index=False), sha_m)

                if row_id:
                    latest_d, sha_d = get_atomic_data("service_details.csv")
                    latest_d = load_detail(latest_d)
                    new_d = latest_d[latest_d["parent_id"] != row_id].reset_index(drop=True)
                    repo.update_file("service_details.csv", "Delete details", new_d.to_csv(index=False), sha_d)

                st.session_state.edit_idx = None
                st.toast("紀錄已刪除")
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"刪除失敗：{e}")

# FIX #3：全域呼叫
if st.session_state.edit_idx is not None:
    view_dialog(st.session_state.edit_idx)

# ─────────────────────────────────────────
# 7. 主介面
# ─────────────────────────────────────────
tab1, tab2 = st.tabs(["🏠 首頁", "➕ 新增紀錄"])

# ── Tab 1：首頁 ──────────────────────────
with tab1:
    st.write(f"🛵 目前里程：**{latest_km} km**")

    if st.button("🔄 同步雲端最新紀錄", use_container_width=True):
        st.rerun()

    for index, row in master_df.head(20).iterrows():
        icon  = "⛽" if str(row["類別"]).strip() == "加油" else "🛠️"
        label = f"{icon} {row['日期'].strftime('%m/%d %H:%M')} | ${int(row['金額'])}"
        if st.button(label, key=f"r_{index}", use_container_width=True):
            st.session_state.edit_idx = index
            st.rerun()

# ── Tab 2：新增紀錄 ──────────────────────
with tab2:
    mode = st.radio("類別", ["⛽ 加油", "🛠️ 保養維修"], horizontal=True)

    # FIX #1：save_trigger 在 form 外預先初始化
    save_trigger = False
    total_sum    = 0

    with st.form("main_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        a_date = c1.date_input("日期", datetime.now(TAIPEI_TZ).date())
        a_time = c2.time_input("時間", datetime.now(TAIPEI_TZ).time())
        a_km   = st.number_input("里程 (km)", value=latest_km, min_value=0)
        a_shop = st.text_input("店家 (選填)") if mode == "🛠️ 保養維修" else ""
        a_note = st.text_area("備註 (選填)")

        if mode == "⛽ 加油":
            a_type = st.selectbox("油種", list(GAS_PRICES.keys()))
            a_amt  = st.number_input("金額 ($)", min_value=0)
            if st.form_submit_button("🚀 儲存加油", use_container_width=True):
                with st.spinner("存檔同步中..."):
                    try:
                        real_m, sha_m = get_atomic_data("data.csv")
                        real_m = load_master(real_m)
                        full_dt = datetime.combine(a_date, a_time).strftime("%Y-%m-%d %H:%M")
                        calc_L  = round(a_amt / GAS_PRICES[a_type], 2) if a_amt > 0 else 0.0
                        new_row = {
                            "日期": full_dt, "類別": "加油",
                            "里程": a_km,    "金額": a_amt,
                            "細目": f"{a_type}/{calc_L}L",
                            "漏記": "No",    "備註": a_note,
                            "店家": "",      "id": str(uuid.uuid4()),
                        }
                        updated_m = pd.concat([real_m, pd.DataFrame([new_row])], ignore_index=True)
                        repo.update_file("data.csv", "Add Gas", updated_m.to_csv(index=False), sha_m)
                        st.toast("加油紀錄存檔成功！")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"儲存失敗：{e}")
        else:
            # FIX #1：在 form 內賦值
            save_trigger = st.form_submit_button("💾 儲存保養紀錄", use_container_width=True)

    # ── 保養項目管理（form 外）────────────
    if mode == "🛠️ 保養維修":
        if st.button("➕ 新增零件項目", use_container_width=True):
            add_item_dialog()

        if st.session_state.temp_items:
            for i, item in enumerate(st.session_state.temp_items):
                col_item, col_del = st.columns([5, 1])
                col_item.markdown(
                    f'<div class="service-item-box">'
                    f'<b>{item["item_name"]}</b> <b>${item["total"]}</b>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                # FIX #9：支援刪除單一項目
                if col_del.button("✕", key=f"del_{i}"):
                    st.session_state.temp_items.pop(i)
                    st.rerun()
                total_sum += item["total"]

            st.write(f"### 總計：${total_sum}")
            if st.button("🗑️ 清空暫存項目", type="secondary", use_container_width=True):
                st.session_state.temp_items = []
                st.rerun()

        # FIX #1：save_trigger 已安全初始化，此處不會 NameError
        if save_trigger:
            if not st.session_state.temp_items:
                st.error("清單為空，請先新增零件")
            else:
                with st.spinner("📦 雙檔案同步存檔中..."):
                    try:
                        real_m, sha_m = get_atomic_data("data.csv")
                        real_d, sha_d = get_atomic_data("service_details.csv")
                        real_m = load_master(real_m)
                        real_d = load_detail(real_d)

                        rec_id  = str(uuid.uuid4())
                        full_dt = datetime.combine(a_date, a_time).strftime("%Y-%m-%d %H:%M")
                        summary = ", ".join([i["item_name"] for i in st.session_state.temp_items])

                        new_m_row = {
                            "日期": full_dt, "類別": "保養",
                            "里程": a_km,    "金額": total_sum,
                            "細目": summary, "漏記": "No",
                            "備註": a_note,  "店家": a_shop,
                            "id":   rec_id,
                        }
                        updated_m = pd.concat([real_m, pd.DataFrame([new_m_row])], ignore_index=True)

                        new_details = [dict(item, parent_id=rec_id)
                                       for item in st.session_state.temp_items]
                        updated_d = pd.concat([real_d, pd.DataFrame(new_details)], ignore_index=True)

                        # FIX #5：各自取最新 SHA 再推送
                        repo.update_file("data.csv",            "Sync Master",  updated_m.to_csv(index=False), sha_m)
                        repo.update_file("service_details.csv", "Sync Details", updated_d.to_csv(index=False), sha_d)

                        st.session_state.temp_items = []
                        st.toast("保養紀錄同步成功！")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"儲存失敗：{e}")
