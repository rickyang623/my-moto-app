import streamlit as st
from google.oauth2.service_account import Credentials
import gspread

st.set_page_config(page_title="Final Debug", layout="centered")

try:
    creds_info = st.secrets["gsheet"]
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    client = gspread.authorize(creds)
    st.success("✅ 第一步：Google 授權成功")

    ss_id = creds_info["spreadsheet_id"]
    sh = client.open_by_key(ss_id)
    st.success(f"✅ 第二步：成功開啟檔案「{sh.title}」")

    # 列出所有分頁名稱
    worksheets = [w.title for w in sh.worksheets()]
    st.write(f"目前檔案裡的分頁有： {worksheets}")

    if "master" in worksheets:
        wks = sh.worksheet("master")
        st.balloons()
        st.success("🎉 第三步：成功連線到 master 分頁！你可以換回正式版代碼了。")
    else:
        st.error(f"❌ 找不到名為 master 的分頁。請把左下角的 {worksheets[0]} 改名為 master")

except Exception as e:
    st.error(f"❌ 錯誤細節：{e}")
    if "Permission denied" in str(e):
        st.info("請確認 Sheet 共用設定裡有加入 client_email 並設為編輯者")
