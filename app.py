"""
==============================================================
 마약류 언론동향 모니터링 시스템 - 네비게이션 (app.py)
==============================================================
 - st.navigation 으로 사이드바 메뉴를 한글로 표시
 - 파일명은 영문 유지 (Windows 호환)
==============================================================
"""

import streamlit as st

st.set_page_config(
    page_title="마약류 언론동향 모니터링 시스템",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation([
    st.Page("pages/0_dashboard.py",   title="대시보드",   icon="📊", default=True),
    st.Page("pages/1_articles.py",    title="전체기사",   icon="📰"),
    st.Page("pages/2_keywords.py",    title="키워드관리", icon="🏷️"),
    st.Page("pages/3_recommended.py", title="추천키워드", icon="💡"),
    st.Page("pages/4_collect.py",     title="기사수집",   icon="📥"),
    st.Page("pages/5_briefing.py",    title="주간브리핑", icon="📋"),
])

pg.run()
