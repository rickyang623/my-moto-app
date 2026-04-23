# --- 介面佈局 ---
tab1, tab2 = st.tabs(["🏠 首頁", "⛽ 新增加油"])

with tab1:
    st.write("🛵 <span style='font-size: 14px; color: gray;'>小迪</span>", unsafe_allow_html=True)
    
    # 儀表板數據 (維持原邏輯)
    avg_eff = "--"
    latest_km = df['里程'].max() if not df.empty else 0
    if len(df) >= 2 and df.iloc[0]['漏記'] == 'No':
        try:
            prev_liters = float(re.findall(r"(\d+\.\d+)L", df.iloc[1]['細目'])[0])
            avg_eff = f"{round((df.iloc[0]['里程'] - df.iloc[1]['里程']) / prev_liters, 2)} km/L"
        except: pass

    m_col1, m_col2 = st.columns(2)
    m_col1.metric("目前里程", f"{latest_km} km")
    m_col2.metric("平均油耗", avg_eff)
    
    st.divider()
    
    # --- 紀錄清單 ---
    items_per_page = 10
    total_pages = (len(df) // items_per_page) + (1 if len(df) % items_per_page > 0 else 0)
    page = st.select_slider("頁碼", options=range(1, total_pages + 1), value=1) if total_pages > 1 else 1
    
    start_idx = (page - 1) * items_per_page
    
    for index, row in df.iloc[start_idx : start_idx + items_per_page].iterrows():
        # 使用一個大的 container 包裹，並利用 columns 的極端比例 [10, 1]
        with st.container():
            c_content, c_btn = st.columns([10, 2])
            
            # 左側：放置所有文字資訊
            dt_str = row['日期'].strftime('%m/%d %H:%M')
            miss_tag = "⚠️" if row['漏記'] == 'Yes' else ""
            oil_type = row['細目'].split('/')[0]
            
            # 用一個簡單的 HTML 組合，讓里程和金額顯示得像標籤
            c_content.markdown(f"""
            <div style='line-height:1.2;'>
                <span style='font-weight:bold; font-size:15px;'>{dt_str}</span> {miss_tag}<br>
                <small style='color:green;background:#e6ffe6;padding:0 4px;'>{row['里程']}k</small>
                <small style='color:blue;background:#e6f3ff;padding:0 4px;'>${row['金額']}</small>
                <small style='color:gray;'>{oil_type}</small>
            </div>
            """, unsafe_allow_html=True)
            
            # 右側：放置編輯按鈕，這次我們不放 Emoji，改用簡單的 Edit 文字縮小
            if c_btn.button("改", key=f"btn_{index}", use_container_width=True):
                st.session_state.edit_index = index
                st.rerun()
            
            st.markdown('<div style="margin-top:-10px;"><hr style="height:1px;border:none;color:#eee;background-color:#eee;" /></div>', unsafe_allow_html=True)
