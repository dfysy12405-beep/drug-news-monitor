"""
==============================================================
 마약류 언론동향 모니터링 시스템 - 메인 대시보드 (app.py)
==============================================================
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from modules import database as db
from modules import analyzer
from modules.utils import page_header, render_article_card, badge_category

st.set_page_config(
    page_title="마약류 언론동향 모니터링 시스템",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px; }
    [data-testid="stSidebar"] { background: #f8fafc; }
    /* 버튼 전체 너비 + 카드 스타일 */
    div[data-testid="stButton"] > button {
        width: 100%;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        padding: 10px 0;
        background: white;
        color: #0f172a;
        font-size: 0.95rem;
        transition: all 0.15s;
    }
    div[data-testid="stButton"] > button:hover {
        border-color: #0d9488;
        color: #0d9488;
    }
</style>
""", unsafe_allow_html=True)

# DB 초기화
db.init_db()

# ------------------------------------------------------------
# Session state 초기화 (클릭 필터 상태 저장)
# ------------------------------------------------------------
if "dash_filter" not in st.session_state:
    st.session_state["dash_filter"] = "all"   # all / today / high / keyword
if "dash_keyword" not in st.session_state:
    st.session_state["dash_keyword"] = None

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
    if st.button("🔄 키워드 통계 갱신", use_container_width=True):
        db.refresh_keyword_stats()
        st.success("갱신 완료")
        st.rerun()
    if st.button("💡 추천 키워드 재분석", use_container_width=True):
        n = analyzer.analyze_recommended_keywords()
        st.success(f"분석 완료 ({n}건 갱신)")
    st.divider()
    st.caption(f"오늘: {datetime.now().strftime('%Y-%m-%d')}")

# ============================================================
# 헤더
# ============================================================
page_header("📊", "대시보드", "마약류 및 약물 오남용 관련 언론 동향 종합 모니터링")

# ============================================================
# (1) KPI 카드 - 클릭하면 아래 기사 목록이 필터됨
# ============================================================
total_articles = db.get_article_count()
today_articles = db.get_today_article_count()
high_articles = db.get_articles(importance="높음").shape[0]
active_keywords = db.get_keywords(active_only=True).shape[0]

st.markdown("##### 📌 클릭하면 해당 기사만 표시됩니다")
c1, c2, c3, c4 = st.columns(4)

with c1:
    active = st.session_state["dash_filter"] == "all"
    bg = "#f0fdfa" if active else "white"
    border = "2px solid #0d9488" if active else "1px solid #e2e8f0"
    st.markdown(
        f'<div style="background:{bg};border:{border};border-radius:8px;'
        f'padding:14px;text-align:center;margin-bottom:4px;">'
        f'<div style="font-size:0.8rem;color:#64748b;">📚 전체 수집 기사</div>'
        f'<div style="font-size:1.8rem;font-weight:700;color:#2563eb;">{total_articles:,}건</div>'
        f'</div>', unsafe_allow_html=True
    )
    if st.button("전체 보기", key="btn_all"):
        st.session_state["dash_filter"] = "all"
        st.session_state["dash_keyword"] = None
        st.rerun()

with c2:
    active = st.session_state["dash_filter"] == "today"
    bg = "#f0fdfa" if active else "white"
    border = "2px solid #0d9488" if active else "1px solid #e2e8f0"
    st.markdown(
        f'<div style="background:{bg};border:{border};border-radius:8px;'
        f'padding:14px;text-align:center;margin-bottom:4px;">'
        f'<div style="font-size:0.8rem;color:#64748b;">📅 오늘 수집 기사</div>'
        f'<div style="font-size:1.8rem;font-weight:700;color:#10b981;">{today_articles:,}건</div>'
        f'</div>', unsafe_allow_html=True
    )
    if st.button("오늘 기사 보기", key="btn_today"):
        st.session_state["dash_filter"] = "today"
        st.session_state["dash_keyword"] = None
        st.rerun()

with c3:
    active = st.session_state["dash_filter"] == "high"
    bg = "#f0fdfa" if active else "white"
    border = "2px solid #0d9488" if active else "1px solid #e2e8f0"
    st.markdown(
        f'<div style="background:{bg};border:{border};border-radius:8px;'
        f'padding:14px;text-align:center;margin-bottom:4px;">'
        f'<div style="font-size:0.8rem;color:#64748b;">🟢 중요 기사 (높음)</div>'
        f'<div style="font-size:1.8rem;font-weight:700;color:#0d9488;">{high_articles:,}건</div>'
        f'</div>', unsafe_allow_html=True
    )
    if st.button("중요 기사 보기", key="btn_high"):
        st.session_state["dash_filter"] = "high"
        st.session_state["dash_keyword"] = None
        st.rerun()

with c4:
    st.markdown(
        f'<div style="background:white;border:1px solid #e2e8f0;border-radius:8px;'
        f'padding:14px;text-align:center;margin-bottom:4px;">'
        f'<div style="font-size:0.8rem;color:#64748b;">🏷️ 활성 키워드</div>'
        f'<div style="font-size:1.8rem;font-weight:700;color:#8b5cf6;">{active_keywords}개</div>'
        f'</div>', unsafe_allow_html=True
    )

st.markdown("<br>", unsafe_allow_html=True)

# ============================================================
# (2) 클릭형 키워드 태그
# ============================================================
st.markdown("#### 🏷️ 키워드별 보기 — 클릭하면 해당 기사만 표시")
top_kws = analyzer.get_top_keywords(top_n=12)
if top_kws:
    kw_cols = st.columns(len(top_kws))
    for i, (kw, cnt) in enumerate(top_kws):
        with kw_cols[i]:
            is_active = (st.session_state["dash_filter"] == "keyword"
                         and st.session_state["dash_keyword"] == kw)
            bg = "#0d9488" if is_active else "#eef2ff"
            color = "white" if is_active else "#3730a3"
            st.markdown(
                f'<div style="background:{bg};color:{color};text-align:center;'
                f'padding:6px 4px;border-radius:16px;font-size:0.78rem;'
                f'font-weight:500;margin-bottom:4px;">'
                f'#{kw}<br><span style="font-size:0.72rem;opacity:0.8;">{cnt}건</span></div>',
                unsafe_allow_html=True
            )
            if st.button(kw, key=f"kw_{kw}", label_visibility="collapsed"):
                if is_active:
                    # 다시 누르면 해제
                    st.session_state["dash_filter"] = "all"
                    st.session_state["dash_keyword"] = None
                else:
                    st.session_state["dash_filter"] = "keyword"
                    st.session_state["dash_keyword"] = kw
                st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ============================================================
# (3) 필터 상태에 따른 기사 목록
# ============================================================
today_str = datetime.now().strftime("%Y-%m-%d")
dash_filter = st.session_state["dash_filter"]
dash_keyword = st.session_state["dash_keyword"]

if dash_filter == "today":
    articles = db.get_articles(start_date=today_str, end_date=today_str)
    section_title = f"📅 오늘 수집 기사 ({today_str})"
elif dash_filter == "high":
    articles = db.get_articles(importance="높음")
    section_title = "🟢 중요도 높음 기사"
elif dash_filter == "keyword" and dash_keyword:
    articles = db.get_articles(keyword=dash_keyword)
    section_title = f"🏷️ #{dash_keyword} 관련 기사"
else:
    articles = db.get_articles(limit=15)
    section_title = "📰 최근 수집 기사"

st.markdown(f"#### {section_title} &nbsp; <span style='font-size:0.9rem;color:#64748b;font-weight:400;'>({len(articles)}건)</span>", unsafe_allow_html=True)

if articles.empty:
    st.info("해당 조건의 기사가 없습니다.")
else:
    for _, row in articles.iterrows():
        render_article_card(row)

st.markdown("<br>", unsafe_allow_html=True)

# ============================================================
# (4) 기사 분류별 현황 | 최근 7일 추이 (나란히 배치)
# ============================================================
st.divider()
left_chart, right_chart = st.columns(2)

with left_chart:
    st.markdown("#### 📂 기사 분류별 현황")
    cat_counts = analyzer.get_category_counts()
    if cat_counts:
        cat_df = pd.DataFrame(cat_counts)
        cat_df.columns = ["분류", "기사 수"]
        st.dataframe(
            cat_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "기사 수": st.column_config.ProgressColumn(
                    "기사 수", format="%d건",
                    min_value=0,
                    max_value=int(cat_df["기사 수"].max()),
                )
            },
            height=300,
        )

with right_chart:
    st.markdown("#### 📈 최근 7일 기사 수집 추이")
    today_dt = datetime.now().date()
    date_range = [(today_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    trend = analyzer.get_keyword_trend(days=30)
    trend_dict = {t["collected_date"]: t["count"] for t in trend}
    chart_df = pd.DataFrame({
        "날짜": date_range,
        "수집 기사": [trend_dict.get(d, 0) for d in date_range],
    })
    st.bar_chart(chart_df, x="날짜", y="수집 기사", height=280, color="#0d9488")

st.divider()
st.caption("📌 좌측 사이드바에서 전체기사 조회, 키워드 관리, 추천 키워드, 기사 수집, 주간 브리핑 페이지로 이동할 수 있습니다.")
