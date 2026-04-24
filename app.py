import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

st.set_page_config(page_title="Debug Mode", layout="centered")

try:
    # 測試 1: 讀取 Secrets
    st.write("🔍 正在讀取 Secrets...")
    creds_info = st.secrets["gsheet"]
    st.write("✅ Secrets 讀取成功")

    # 測試 2: 建立授權
    st.write("🔍 正在嘗試 Google 授權...")
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    client = gspread.authorize(creds)
    st.write("✅ Google 授權成功")

    # 測試 3: 開啟檔案
    st.write(f"🔍 正在開啟試算表 ID: {creds_info['spreadsheet_id']}...")
    sh = client.open_by_key(creds_info['spreadsheet_id'])
    st.write(f"✅ 成功開啟試算表: {sh.title}")

    # 測試 4: 讀取分頁
    st.write("🔍 正在讀取 master 分頁...")
    wks = sh.worksheet("master")
    data = wks.get_all_records()
    st.write(f"✅ 讀取成功！目前有 {len(data)} 筆紀錄")
    st.balloons()

except Exception as e:
    st.error(f"❌ 發生錯誤！類型：{type(e).__name__}")
    st.code(str(e)) # 這裡會印出最關鍵的錯誤訊息
    st.info("如果是 'WorksheetNotFound'，代表你分頁名稱不是 master")
    st.info("如果是 'APIError'，通常是 client_email 沒加共用人員")
