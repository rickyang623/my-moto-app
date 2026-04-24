import streamlit as st
from google.oauth2.service_account import Credentials
import gspread

st.set_page_config(page_title="Deep Debug", layout="centered")

try:
    # 1. 讀取與顯示 (為了確認 Secrets 真的有更新)
    creds_info = st.secrets["gsheet"]
    st.write(f"📡 目前嘗試連線的 ID: `{creds_info['spreadsheet_id'][:10]}...`")
    
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    client = gspread.authorize(creds)
    st.success("✅ 授權通過")

    # --- 測試 A：直接開啟 ---
    st.write("🔄 測試 A: 直接用 ID 開啟...")
    try:
        sh = client.open_by_key(creds_info["spreadsheet_id"])
        st.success(f"🎊 成功！檔案標題為: {sh.title}")
        st.write(f"工作表清單: {[w.title for w in sh.worksheets()]}")
        st.balloons()
    except Exception as e:
        st.error(f"❌ 測試 A 失敗: {str(e)}")

    # --- 測試 B：列出清單 (這最準) ---
    st.write("🔄 測試 B: 掃描帳號內所有可見檔案...")
    try:
        all_files = client.list_spreadsheet_files()
        if not all_files:
            st.warning("⚠️ 帳號內空無一物。請檢查 Google Sheet 的『共用人員』Email 是否貼對。")
            st.code(creds_info['client_email'])
        else:
            for f in all_files:
                st.info(f"📂 發現檔案: {f['name']} (ID: {f['id']})")
    except Exception as e:
        st.error(f"❌ 測試 B 失敗: {str(e)}")

except Exception as e:
    st.critical(f"💥 核心崩潰: {e}")
