"""
==============================================================
 페이지 1: 전체 기사 조회 / 검색 / 상세보기
==============================================================
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from modules import database as db
from modules.utils import (
    page_header, render_article_card, badge_importance,
    badge_category, keyword_tags, CATEGORY_LIST,
)
from modules.similarity import get_grouped_articles


db.init_db()

page_header(
    "📰", "전체 기사 조회",
    "수집된 모든 기사 검색·필터링 및 상세 정보 관리"
)

# ============================================================
# 상세보기 모드 (쿼리 파라미터로 id 전달 시)
# ============================================================
query_params = st.query_params
article_id = query_params.get("id")

if article_id:
    try:
        article_id = int(article_id)
    except ValueError:
        article_id = None

if article_id:
    art = db.get_article_by_id(article_id)
    if not art:
        st.error("해당 기사를 찾을 수 없습니다.")
        if st.button("← 목록으로 돌아가기"):
            st.query_params.clear()
            st.rerun()
        st.stop()

    # ----- 상세 화면 렌더링 -----
    if st.button("← 목록으로 돌아가기"):
        st.query_params.clear()
        st.rerun()

    st.markdown(f"## {art['title']}")

    meta_cols = st.columns([2, 2, 2, 2])
    meta_cols[0].markdown(f"**📰 언론사** &nbsp; {art.get('source', '')}")
    meta_cols[1].markdown(f"**📅 발행일** &nbsp; {art.get('published_date', '')}")
    meta_cols[2].markdown(f"**🗂️ 수집일** &nbsp; {art.get('collected_date', '')}")
    meta_cols[3].markdown(f"**⭐ 즐겨찾기** &nbsp; {'예' if art.get('is_favorite') else '아니오'}")

    st.markdown(
        f"{badge_importance(art.get('importance', '보통'))} "
        f"&nbsp; {badge_category(art.get('category', '기타'))}",
        unsafe_allow_html=True,
    )
    st.markdown(f"<div style='margin-top:8px;'>{keyword_tags(art.get('keywords', ''), max_tags=20)}</div>",
                unsafe_allow_html=True)

    st.divider()

    if art.get("url"):
        st.link_button("🔗 원문 보기 (새 창)", art["url"])

    st.markdown("### 📝 AI 요약")
    st.info(art.get("summary") or "(요약 없음)")

    st.markdown("### 💡 예방교육 활용 포인트")
    st.success(art.get("education_point") or "(활용 포인트 없음)")

    # ----- 수정 영역 -----
    st.divider()
    st.markdown("### ✏️ 기사 정보 수정")

    with st.form(f"edit_form_{article_id}"):
        c1, c2, c3 = st.columns(3)
        new_importance = c1.selectbox(
            "중요도", ["높음", "보통", "낮음"],
            index=["높음", "보통", "낮음"].index(art.get("importance") or "보통")
        )
        cat_options = CATEGORY_LIST
        current_cat = art.get("category") or "기타"
        if current_cat not in cat_options:
            cat_options = cat_options + [current_cat]
        new_category = c2.selectbox(
            "분류", cat_options,
            index=cat_options.index(current_cat)
        )
        new_favorite = c3.checkbox("⭐ 즐겨찾기", value=bool(art.get("is_favorite")))

        new_summary = st.text_area("요약", value=art.get("summary") or "", height=100)
        new_keywords = st.text_input("핵심 키워드 (쉼표로 구분)", value=art.get("keywords") or "")
        new_edu = st.text_area("예방교육 활용 포인트", value=art.get("education_point") or "", height=80)
        new_memo = st.text_area("📌 내부 메모", value=art.get("memo") or "", height=80,
                                placeholder="강사 공유용 메모, 추가 분석 내용 등")

        col_s, col_d = st.columns([1, 1])
        save = col_s.form_submit_button("💾 저장", use_container_width=True, type="primary")
        delete = col_d.form_submit_button("🗑️ 기사 삭제", use_container_width=True)

    if save:
        db.update_article(
            article_id,
            importance=new_importance,
            category=new_category,
            summary=new_summary,
            keywords=new_keywords,
            education_point=new_edu,
            memo=new_memo,
            is_favorite=1 if new_favorite else 0,
        )
        db.refresh_keyword_stats()
        st.success("저장되었습니다.")
        st.rerun()

    if delete:
        db.delete_article(article_id)
        st.warning("삭제되었습니다. 목록으로 이동합니다.")
        st.query_params.clear()
        st.rerun()

    st.stop()  # 상세보기 모드일 때는 아래 목록 출력하지 않음


# ============================================================
# 검색 / 필터 영역
# ============================================================
with st.container():
    # 첫 줄: 검색어 + 정렬
    c1, c2, c3 = st.columns([4, 2, 2])
    search = c1.text_input("🔍 제목·요약·키워드 검색", placeholder="검색어 입력")
    sort_options = {
        "최신순 (수집일)": "collected_date DESC, id DESC",
        "최신순 (발행일)": "published_date DESC, id DESC",
        "중요도순":        "CASE importance WHEN '높음' THEN 0 WHEN '보통' THEN 1 ELSE 2 END, collected_date DESC",
        "오래된순":        "collected_date ASC, id ASC",
    }
    sort_label = c2.selectbox("🔃 정렬", list(sort_options.keys()), index=1)
    today_only = c3.checkbox("오늘 수집만", value=False)

    # 둘째 줄: 카테고리 / 중요도 / 기간
    c4, c5, c6, c7 = st.columns([2, 2, 2, 2])
    category = c4.selectbox("📂 분류", ["전체"] + CATEGORY_LIST + ["기타"])
    importance = c5.selectbox("⚠️ 중요도", ["전체", "높음", "보통", "낮음"])

    # 키워드 선택 (등록 키워드 중 active)
    kw_df = db.get_keywords(active_only=True)
    kw_options = ["전체"] + (kw_df["keyword"].tolist() if not kw_df.empty else [])
    keyword_filter = c6.selectbox("🏷️ 키워드", kw_options)

    favorite_only = c7.checkbox("⭐ 즐겨찾기만", value=False)

    # 셋째 줄: 기간
    c8, c9, c10 = st.columns([2, 2, 4])
    today_dt = datetime.now().date()
    start_date = c8.date_input("📅 시작일", value=today_dt - timedelta(days=30))
    end_date = c9.date_input("📅 종료일", value=today_dt)

# ============================================================
# 조회 실행
# ============================================================
sd = start_date.strftime("%Y-%m-%d")
ed = end_date.strftime("%Y-%m-%d")
if today_only:
    sd = ed = datetime.now().strftime("%Y-%m-%d")

df = db.get_articles(
    search=search if search else None,
    category=category if category != "전체" else None,
    importance=importance if importance != "전체" else None,
    keyword=keyword_filter if keyword_filter != "전체" else None,
    start_date=sd, end_date=ed,
    favorite_only=favorite_only,
    order_by=sort_options[sort_label],
)

# 조회 결과 헤더 + CSV
rc1, rc2 = st.columns([4, 2])
rc1.markdown(f"##### 📋 조회 결과: **{len(df)}건**")
if not df.empty:
    csv = df.to_csv(index=False).encode("utf-8-sig")
    rc2.download_button(
        "📥 CSV 다운로드", data=csv,
        file_name=f"articles_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )

if df.empty:
    st.info("조건에 맞는 기사가 없습니다.")
    st.stop()

# ============================================================
# 표시 모드 선택 (카드 / 표 / 유사기사 묶기)
# ============================================================
view_mode = st.radio(
    "표시 형식",
    ["📇 개별 기사로 보기", "🗂️ 유사 기사 묶어서 보기", "📊 표형식"],
    index=1,
    horizontal=True,
    label_visibility="collapsed",
)

# ──────────────────────────────────────
# (A) 유사 기사 묶어서 보기
# ──────────────────────────────────────
if view_mode == "🗂️ 유사 기사 묶어서 보기":

    # 유사도 설정 슬라이더
    with st.expander("⚙️ 그룹화 설정", expanded=False):
        col_s1, col_s2 = st.columns(2)
        threshold  = col_s1.slider("제목 유사도 기준 (%)", 60, 95, 80, 5)
        date_window = col_s2.slider("발행일 차이 기준 (일)", 1, 7, 3)

    # 캐시용 해시키 (DataFrame → json 문자열 기반)
    @st.cache_data(show_spinner="유사 기사 그룹화 중...")
    def _cached_group(df_json: str, thr: float, dw: int):
        import pandas as pd, io
        _df = pd.read_json(io.StringIO(df_json))
        return get_grouped_articles(_df, thr, dw)

    groups = _cached_group(df.to_json(), float(threshold), int(date_window))

    grouped_cnt  = sum(1 for g in groups if g["count"] > 1)
    duplicate_cnt = sum(g["count"] - 1 for g in groups if g["count"] > 1)

    st.markdown(
        f"🗂️ **{len(groups)}개 그룹** &nbsp;|&nbsp; "
        f"유사 묶음 **{grouped_cnt}건** &nbsp;|&nbsp; "
        f"중복 기사 **{duplicate_cnt}건** 숨김"
    )
    st.divider()

    for idx, grp in enumerate(groups):
        rep   = grp["representative"]
        count = grp["count"]

        # 대표 기사 카드
        render_article_card(rep)

        # 관련 기사가 2건 이상이면 펼치기 버튼
        if count > 1:
            related = grp["articles"][1:]  # 대표 제외 나머지
            sources_str = " · ".join(grp["sources"][:4])
            kw_str = "  ".join([f"#{k}" for k in grp["top_keywords"][:4]])

            with st.expander(
                f"📎 관련 기사 {len(related)}건 펼치기  |  언론사: {sources_str}  |  {kw_str}",
                expanded=False,
            ):
                for rel in related:
                    url   = rel.get("url", "")
                    title = rel.get("title", "")
                    src   = rel.get("source", "")
                    pub   = rel.get("published_date", "")
                    imp   = rel.get("importance", "보통")
                    cat   = rel.get("category", "")
                    imp_icon = "🟢" if imp == "높음" else ("🟡" if imp == "보통" else "⚪")

                    # 따옴표 충돌 방지를 위해 문자열 연결 방식 사용
                    if url and url.startswith("http"):
                        _title_part = (
                            '<a href="' + url + '" target="_blank" '
                            'style="color:#0f172a;text-decoration:none;'
                            'font-size:0.95rem;font-weight:600;line-height:1.5;">'
                            + imp_icon + ' ' + title + ' 🔗</a>'
                        )
                    else:
                        _title_part = (
                            '<span style="font-size:0.95rem;font-weight:600;color:#0f172a;">'
                            + imp_icon + ' ' + title + '</span>'
                        )

                    st.markdown(
                        '<div style="background:#f8fafc;border-left:3px solid #0d9488;'
                        'border-radius:0 8px 8px 0;padding:12px 16px;margin-bottom:10px;">'
                        + _title_part +
                        '<div style="font-size:0.78rem;color:#64748b;margin-top:6px;">'
                        '📰 <b>' + src + '</b>'
                        ' &nbsp;|&nbsp; 발행 ' + pub +
                        ' &nbsp;|&nbsp; ' + cat +
                        '</div></div>',
                        unsafe_allow_html=True,
                    )
        st.markdown("")  # 간격

# ──────────────────────────────────────
# (B) 표형식
# ──────────────────────────────────────
elif view_mode == "📊 표형식":
    show_df = df[["id", "collected_date", "published_date", "source", "title",
                  "category", "importance", "keywords"]].copy()
    show_df.columns = ["ID", "수집일", "발행일", "언론사", "제목", "분류", "중요도", "키워드"]
    st.dataframe(show_df, use_container_width=True, hide_index=True, height=600)
    st.caption("💡 아래에서 ID 번호를 입력하면 상세 화면으로 이동합니다.")
    sel_id = st.number_input("기사 ID", min_value=1, value=int(df.iloc[0]["id"]), step=1)
    if st.button("👁️ 상세 보기"):
        st.query_params["id"] = str(int(sel_id))
        st.rerun()

# ──────────────────────────────────────
# (C) 개별 기사 카드형 (기존)
# ──────────────────────────────────────
else:
    PAGE_SIZE = 15
    total_pages = (len(df) - 1) // PAGE_SIZE + 1
    page = st.number_input(f"페이지 (총 {total_pages}쪽)", min_value=1, max_value=total_pages, value=1)
    start = (page - 1) * PAGE_SIZE
    sliced = df.iloc[start:start + PAGE_SIZE]

    for _, row in sliced.iterrows():
        col_card, col_btn = st.columns([6, 1])
        with col_card:
            render_article_card(row)
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("👁️ 상세", key=f"detail_{row['id']}", use_container_width=True):
                st.query_params["id"] = str(int(row["id"]))
                st.rerun()
            if row.get("url"):
                st.link_button("🔗 원문", row["url"], use_container_width=True)
