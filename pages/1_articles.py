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
    sort_label = c2.selectbox("🔃 정렬", list(sort_options.keys()))
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

st.markdown(f"##### 📋 조회 결과: **{len(df)}건**")

# CSV 다운로드 버튼
if not df.empty:
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 CSV 다운로드", data=csv,
        file_name=f"articles_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )

if df.empty:
    st.info("조건에 맞는 기사가 없습니다.")
    st.stop()

# ============================================================
# 표시 모드 선택 (카드 / 표)
# ============================================================
view_mode = st.radio("표시 형식", ["📇 카드형", "📊 표형식"], horizontal=True, label_visibility="collapsed")

if view_mode == "📊 표형식":
    show_df = df[["id", "collected_date", "published_date", "source", "title",
                  "category", "importance", "keywords"]].copy()
    show_df.columns = ["ID", "수집일", "발행일", "언론사", "제목", "분류", "중요도", "키워드"]
    st.dataframe(show_df, use_container_width=True, hide_index=True, height=600)

    # 상세보기 안내
    st.caption("💡 아래에서 ID 번호를 입력하면 상세 화면으로 이동합니다.")
    sel_id = st.number_input("기사 ID", min_value=1, value=int(df.iloc[0]["id"]), step=1)
    if st.button("👁️ 상세 보기"):
        st.query_params["id"] = str(int(sel_id))
        st.rerun()
else:
    # 카드형 - 페이지네이션
    PAGE_SIZE = 15
    total_pages = (len(df) - 1) // PAGE_SIZE + 1
    page = st.number_input(f"페이지 (총 {total_pages}쪽)", min_value=1, max_value=total_pages, value=1)
    start = (page - 1) * PAGE_SIZE
    sliced = df.iloc[start:start + PAGE_SIZE]

    for _, row in sliced.iterrows():
        # 카드 + 상세보기 버튼
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
