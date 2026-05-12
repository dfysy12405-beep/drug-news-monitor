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
from modules.similarity import get_grouped_articles


st.markdown("""
<style>
    /* PC 기본 */
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px; }
    [data-testid="stSidebar"] { background: #f8fafc; }

    /* 버튼 스타일 */
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

    /* 모바일 반응형 */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 1rem !important;
        }
        /* 폰트 크기 조절 */
        div[data-testid="stButton"] > button {
            font-size: 0.82rem !important;
            padding: 8px 4px !important;
            height: auto !important;
        }
        /* 카드 내 텍스트 줄임 */
        .stMarkdown p { font-size: 0.88rem !important; }
        /* 사이드바 토글 버튼 크게 */
        [data-testid="collapsedControl"] { top: 0.5rem !important; }
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

st.markdown("##### 📌 버튼을 클릭하면 해당 기사만 표시됩니다")
st.markdown("""
<style>
section[data-testid="stMain"] div[data-testid="stButton"] > button {
    height: 85px; white-space: pre-line; line-height: 1.7; font-size: 1rem; font-weight: 600;
}
</style>""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)

with c1:
    active = st.session_state["dash_filter"] == "all"
    label = "📚 전체 수집 기사\n" + f"{total_articles:,}건"
    if st.button(label, key="btn_all", use_container_width=True,
                 type="primary" if active else "secondary"):
        st.session_state["dash_filter"] = "all"
        st.session_state["dash_keyword"] = None
        st.rerun()

with c2:
    active = st.session_state["dash_filter"] == "today"
    label = "📅 오늘 수집 기사\n" + f"{today_articles:,}건"
    if st.button(label, key="btn_today", use_container_width=True,
                 type="primary" if active else "secondary"):
        st.session_state["dash_filter"] = "today"
        st.session_state["dash_keyword"] = None
        st.rerun()

with c3:
    active = st.session_state["dash_filter"] == "high"
    label = "🟢 중요 기사 (높음)\n" + f"{high_articles:,}건"
    if st.button(label, key="btn_high", use_container_width=True,
                 type="primary" if active else "secondary"):
        st.session_state["dash_filter"] = "high"
        st.session_state["dash_keyword"] = None
        st.rerun()

with c4:
    st.markdown(
        f'<div style="background:white;border:1px solid #e2e8f0;border-radius:8px;'
        f'height:85px;display:flex;flex-direction:column;align-items:center;justify-content:center;">'
        f'<div style="font-size:0.85rem;color:#64748b;">🏷️ 활성 키워드</div>'
        f'<div style="font-size:1.8rem;font-weight:700;color:#8b5cf6;margin-top:4px;">{active_keywords}개</div>'
        f'</div>', unsafe_allow_html=True
    )

# 유사기사 그룹화 통계 소형 KPI
try:
    @st.cache_data(show_spinner=False, ttl=300)
    def _dash_group_stats(df_json):
        import pandas as pd, io
        _df = pd.read_json(io.StringIO(df_json))
        gs = get_grouped_articles(_df, threshold=80.0, date_window=3)
        return (
            sum(1 for g in gs if g["count"] > 1),
            sum(g["count"] - 1 for g in gs if g["count"] > 1),
        )
    _all_df = db.get_articles()
    if not _all_df.empty:
        _grouped_cnt, _dup_cnt = _dash_group_stats(_all_df.to_json())
        g1, g2 = st.columns(2)
        g1.markdown(
            f'<div style="background:#f0fdfa;border:1px solid #99f6e4;border-radius:8px;'
            f'padding:8px;text-align:center;margin-top:8px;">'
            f'<div style="font-size:0.72rem;color:#0f766e;">🗂️ 유사 묶음 그룹</div>'
            f'<div style="font-size:1.2rem;font-weight:700;color:#0d9488;">{_grouped_cnt}건</div>'
            f'</div>', unsafe_allow_html=True
        )
        g2.markdown(
            f'<div style="background:#f0fdfa;border:1px solid #99f6e4;border-radius:8px;'
            f'padding:8px;text-align:center;margin-top:8px;">'
            f'<div style="font-size:0.72rem;color:#0f766e;">📎 중복 기사</div>'
            f'<div style="font-size:1.2rem;font-weight:700;color:#0d9488;">{_dup_cnt}건</div>'
            f'</div>', unsafe_allow_html=True
        )
except Exception:
    pass

st.markdown("<br>", unsafe_allow_html=True)

# ============================================================
# (2) 클릭형 키워드 태그
# ============================================================
st.markdown("#### 🏷️ 키워드별 보기 — 클릭하면 해당 기사만 표시")
top_kws = analyzer.get_top_keywords(top_n=12)
if top_kws:
    kw_cols = st.columns(min(len(top_kws), 12))
    for i, (kw, cnt) in enumerate(top_kws):
        with kw_cols[i]:
            is_active = (st.session_state["dash_filter"] == "keyword"
                         and st.session_state["dash_keyword"] == kw)
            # 활성화된 키워드는 라벨에 ✅ 표시
            label = f"✅ #{kw}\n{cnt}건" if is_active else f"#{kw}\n{cnt}건"
            if st.button(label, key=f"kw_{kw}", use_container_width=True):
                if is_active:
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

# 정렬 옵션
sort_options = {
    "최신순 (수집일)":  "collected_date DESC, id DESC",
    "최신순 (발행일)":  "published_date DESC, id DESC",
    "중요도순":         "CASE importance WHEN '높음' THEN 0 WHEN '보통' THEN 1 ELSE 2 END, collected_date DESC",
    "오래된순":         "collected_date ASC, id ASC",
}
sort_col, _ = st.columns([2, 5])
sort_label = sort_col.selectbox("🔃 정렬", list(sort_options.keys()), index=1, label_visibility="collapsed")
order_by = sort_options[sort_label]

if dash_filter == "today":
    articles = db.get_articles(start_date=today_str, end_date=today_str, order_by=order_by)
    section_title = f"📅 오늘 수집 기사 ({today_str})"
elif dash_filter == "high":
    articles = db.get_articles(importance="높음", order_by=order_by)
    section_title = "🟢 중요도 높음 기사"
elif dash_filter == "keyword" and dash_keyword:
    articles = db.get_articles(keyword=dash_keyword, order_by=order_by)
    section_title = f"🏷️ #{dash_keyword} 관련 기사"
else:
    articles = db.get_articles(order_by=order_by)
    section_title = "📰 전체 수집 기사"

# 유사기사 묶기 토글
t1, t2, t3 = st.columns([4, 2, 2])
t1.markdown(f"#### {section_title} &nbsp; <span style='font-size:0.9rem;color:#64748b;font-weight:400;'>({len(articles)}건)</span>", unsafe_allow_html=True)
t2.markdown(f"<div style='text-align:right;padding-top:8px;color:#64748b;font-size:0.85rem;'>🔃 {sort_label}</div>", unsafe_allow_html=True)
group_mode = t3.toggle("🗂️ 유사 기사 묶기", value=False, key="dash_group_toggle")

if articles.empty:
    st.info("해당 조건의 기사가 없습니다.")
elif group_mode:
    # ── 유사 기사 묶어서 보기 ──
    @st.cache_data(show_spinner="유사 기사 그룹화 중...", ttl=120)
    def _dash_groups(df_json):
        import pandas as pd, io
        _df = pd.read_json(io.StringIO(df_json))
        return get_grouped_articles(_df, threshold=80.0, date_window=3)

    groups = _dash_groups(articles.to_json())
    dup_cnt = sum(g["count"] - 1 for g in groups if g["count"] > 1)
    st.caption(f"🗂️ {len(groups)}개 그룹으로 표시 중 (중복 {dup_cnt}건 숨김)")

    for grp in groups:
        rep   = grp["representative"]
        count = grp["count"]
        render_article_card(rep)

        if count > 1:
            related = grp["articles"][1:]
            sources_str = " · ".join(grp["sources"][:3])
            with st.expander(f"📎 관련 기사 {len(related)}건 펼치기 &nbsp;|&nbsp; {sources_str}", expanded=False):
                for rel in related:
                    url   = rel.get("url", "")
                    title = rel.get("title", "")
                    src   = rel.get("source", "")
                    pub   = rel.get("published_date", "")
                    imp   = rel.get("importance", "보통")
                    imp_icon = "🟢" if imp == "높음" else ("🟡" if imp == "보통" else "⚪")

                    if url and url.startswith("http"):
                        title_html = (
                            f'<a href="{url}" target="_blank" '
                            f'style="color:#0f172a;text-decoration:none;font-size:0.93rem;font-weight:500;" '
                            f'onmouseover="this.style.color='#0d9488'" '
                            f'onmouseout="this.style.color='#0f172a'">'
                            f'{imp_icon} {title} 🔗</a>'
                        )
                    else:
                        title_html = f'<span style="font-size:0.93rem;font-weight:500;">{imp_icon} {title}</span>'

                    st.markdown(
                        f'<div style="background:#f8fafc;border-left:3px solid #cbd5e1;'
                        f'border-radius:0 6px 6px 0;padding:10px 14px;margin-bottom:8px;">'
                        f'{title_html}'
                        f'<div style="font-size:0.76rem;color:#94a3b8;margin-top:4px;">'
                        f'📰 {src} &nbsp;|&nbsp; {pub}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
else:
    # ── 개별 기사 보기 (기존) ──
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
