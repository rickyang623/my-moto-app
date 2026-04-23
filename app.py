with tab1:
    st.title("🛵 資料庫管理")
    
    # 策略 1：搜尋過濾器
    search_query = st.text_input("🔍 搜尋紀錄 (輸入日期、里程或細目)：", placeholder="例如：2026-04 或 80km")
    
    # 根據關鍵字篩選資料
    if search_query:
        mask = df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
        filtered_df = df[mask]
    else:
        filtered_df = df

    st.write(f"共找到 {len(filtered_df)} 筆符合的紀錄")

    # 策略 2：互動式表格選擇 (取代長長的下拉選單)
    # 我們利用 st.dataframe 的 selection 功能，或者用按鈕陣列
    st.subheader("📝 點擊下方『編輯』按鈕載入資料")
    
    # 建立一個清爽的顯示表格
    # 為了方便操作，我們只顯示最新的 10-20 筆，其餘可透過搜尋找
    display_limit = 15
    for index, row in filtered_df.sort_values("日期", ascending=False).head(display_limit).iterrows():
        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.write(f"📅 {row['日期']} | 📍 {row['里程']} km | 💰 {row['金額']} 元 | 📝 {row['細目']}")
        with col_btn:
            if st.button(f"編輯 #{index}", key=f"edit_{index}"):
                st.session_state.editing_index = index
                st.success(f"已載入 #{index} 紀錄，請切換分頁。")
                st.rerun()
    
    if len(filtered_df) > display_limit:
        st.info(f"💡 還有 {len(filtered_df) - display_limit} 筆較舊的紀錄，請使用上方的搜尋框尋找。")

    st.divider()
    # 保留原始表格預覽
    with st.expander("👀 查看原始完整數據表"):
        st.dataframe(df, use_container_width=True)
