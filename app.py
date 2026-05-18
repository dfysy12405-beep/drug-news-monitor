"""
==============================================================
 마약류 언론동향 모니터링 시스템 - 네비게이션 (app.py)
==============================================================
 - st.navigation 으로 사이드바 메뉴를 한글로 표시
 - 파일명은 영문 유지 (Windows 호환)
 - app_pages 폴더 사용: Streamlit 기본 pages 자동탐색 충돌 방지
==============================================================
"""

import streamlit as st

from PIL import Image
import os

# 아이콘 파일 로드
_icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
try:
    _icon = Image.open(_icon_path)
except Exception:
    _icon = "📰"

st.set_page_config(
    page_title="마약류 언론동향 모니터링 시스템",
    page_icon=_icon,
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation([
    st.Page("app_pages/0_dashboard.py",   title="대시보드",   icon="📊", default=True),
    st.Page("app_pages/1_articles.py",    title="전체기사",   icon="📰"),
    st.Page("app_pages/2_keywords.py",    title="키워드관리", icon="🏷️"),
    st.Page("app_pages/3_recommended.py", title="추천키워드", icon="💡"),
    st.Page("app_pages/4_collect.py",     title="기사수집",   icon="📥"),
    st.Page("app_pages/5_briefing.py",    title="주간브리핑", icon="📋"),
])

pg.run()
