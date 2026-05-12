"""
==============================================================
 마약류 언론동향 모니터링 시스템 - 메인 대시보드 (app.py)
==============================================================
 - Streamlit 진입점
 - 좌측 사이드바에서 다른 페이지(pages/ 폴더) 자동 노출
 - 메인 화면: 오늘 기사, 중요 기사 TOP5, KPI, 키워드 통계
==============================================================
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from modules import database as db
from modules import analyzer
from modules.utils import (
    page_header, metric_card, render_article_card,
    badge_importance, badge_category, keyword_tags,
)

# ------------------------------------------------------------
# 페이지 기본 설정
# ------------------------------------------------------------
st.set_page_config(
    page_title="마약류 언론동향 모니터링 시스템",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------
# 공통 스타일
# ------------------------------------------------------------
st.markdown("""
<style>
    /* 메인 컨테이너 폭 조절 */
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px; }
    /* 사이드바 헤더 */
    [data-testid="stSidebar"] { background: #f8fafc; }
    /* 헤더 영역 */
    h1, h2, h3 { color: #0f172a; }
    /* 메트릭 영역 */
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    /* 데이터프레임 헤더 */
    .stDataFrame thead tr th { background: #f1f5f9; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# DB 초기화 (앱이 처음 뜰 때 1회)
# ------------------------------------------------------------
db.init_db()

# ------------------------------------------------------------
# 사이드바
# ------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🏢 마약류 언론동향")
    st.markdown("**모니터링 시스템**")
    st.caption("내부 업무용 · v1.0")
    st.divider()
    st.markdown("##### 🧭 메뉴")
    st.caption("좌측 페이지 목록에서 이동하세요")
    st.divider()
    st.markdown("##### ⚙️ 시스템")

    if st.button("🔄 키워드 통계 갱신", use_container_width=True):
        db.refresh_keyword_stats()
        st.success("갱신 완료")
        st.rerun()

    if st.button("💡 추천 키워드 재분석", use_container_width=True):
        n = analyzer.analyze_recommended_keywords()
        st.success(f"분석 완료 ({n}건 갱신)")

    st.divider()
    st.caption(f"오늘: {datetime.now().strftime('%Y-%m-%d (%a)')}")


# ============================================================
# 메인 대시보드
# ============================================================
page_header(
    "📊", "대시보드",
    "마약류 및 약물 오남용 관련 언론 동향 종합 모니터링"
)

# ------------------------------------------------------------
# (1) KPI 영역
# ------------------------------------------------------------
total_articles = db.get_article_count()
today_articles = db.get_today_article_count()
high_articles = db.get_articles(importance="높음").shape[0]
active_keywords = db.get_keywords(active_only=True).shape[0]

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(metric_card("📚 전체 수집 기사", f"{total_articles:,}건", color="#2563eb"), unsafe_allow_html=True)
with c2:
    st.markdown(metric_card("📅 오늘 수집 기사", f"{today_articles:,}건", color="#10b981"), unsafe_allow_html=True)
with c3:
    st.markdown(metric_card("🔴 중요 기사 (높음)", f"{high_articles:,}건", color="#dc2626"), unsafe_allow_html=True)
with c4:
    st.markdown(metric_card("🏷️ 활성 키워드", f"{active_keywords}개", color="#8b5cf6"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ------------------------------------------------------------
# (2) 좌: 중요 기사 TOP5 / 우: 최근 키워드·카테고리 통계
# ------------------------------------------------------------
left, right = st.columns([3, 2])

with left:
    st.markdown("#### 🔥 오늘의 핵심 기사 TOP 5")
    st.caption("중요도 '높음' 기준, 최근 수집 순")

    top5 = db.get_articles(importance="높음", limit=5)
    if top5.empty:
        # 높음이 없으면 최근 5개
        top5 = db.get_articles(limit=5)

    if top5.empty:
        st.info("표시할 기사가 없습니다.")
    else:
        for _, row in top5.iterrows():
            render_article_card(row)


with right:
    st.markdown("#### 🏷️ 최근 많이 등장한 키워드")
    top_kws = analyzer.get_top_keywords(top_n=12)
    if top_kws:
        kw_html = ""
        for kw, cnt in top_kws:
            kw_html += (
                f'<span style="display:inline-block;background:#eef2ff;color:#3730a3;'
                f'padding:6px 12px;border-radius:20px;margin:4px 4px 4px 0;'
                f'font-size:0.85rem;font-weight:500;">#{kw} '
                f'<span style="color:#6366f1;font-weight:700;">{cnt}</span></span>'
            )
        st.markdown(kw_html, unsafe_allow_html=True)
    else:
        st.info("키워드 데이터가 없습니다.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📂 기사 분류별 현황")
    cat_counts = analyzer.get_category_counts()
    if cat_counts:
        cat_df = pd.DataFrame(cat_counts)
        cat_df.columns = ["분류", "기사 수"]
        st.dataframe(
            cat_df, use_container_width=True, hide_index=True,
            column_config={
                "기사 수": st.column_config.ProgressColumn(
                    "기사 수", format="%d건",
                    min_value=0, max_value=int(cat_df["기사 수"].max()),
                )
            }
        )
    else:
        st.info("분류 데이터가 없습니다.")


# ------------------------------------------------------------
# (3) 최근 7일 기사 추이
# ------------------------------------------------------------
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("#### 📈 최근 7일 기사 수집 추이")

# 최근 7일 날짜 범위
today_dt = datetime.now().date()
date_range = [(today_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
trend = analyzer.get_keyword_trend(days=30)
trend_dict = {t["collected_date"]: t["count"] for t in trend}
chart_df = pd.DataFrame({
    "날짜": date_range,
    "수집 기사": [trend_dict.get(d, 0) for d in date_range],
})
st.bar_chart(chart_df, x="날짜", y="수집 기사", height=240)


# ------------------------------------------------------------
# (4) 최근 수집 기사 리스트
# ------------------------------------------------------------
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("#### 📰 최근 수집 기사")
recent = db.get_articles(limit=10)
if recent.empty:
    st.info("기사가 없습니다. 좌측 [📥 기사수집] 페이지에서 RSS로 수집해 보세요.")
else:
    for _, row in recent.iterrows():
        render_article_card(row)

# ------------------------------------------------------------
# 푸터 안내
# ------------------------------------------------------------
st.divider()
st.caption(
    "📌 좌측 사이드바에서 [전체기사 조회], [키워드 관리], [추천 키워드], "
    "[기사 수집], [주간 브리핑] 페이지로 이동할 수 있습니다."
)
