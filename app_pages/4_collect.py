"""
==============================================================
 페이지 4: 기사 수집
==============================================================
 - CSV 업로드
 - 수동 기사 등록
 - RSS 자동 수집 (Google News)

 ★ RSS 연동 위치: modules/rss_collector.py
==============================================================
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from modules import database as db
from modules import rss_collector
from modules import ai_helper
from modules.utils import page_header, CATEGORY_LIST


db.init_db()

page_header(
    "📥", "기사 수집",
    "RSS · CSV 업로드 · 수동 등록 3가지 방식 지원"
)

# AI 상태 표시
if ai_helper.is_ai_enabled():
    st.success("🤖 OpenAI API 연결됨 — 수집 시 GPT 기반 요약·분류가 자동 적용됩니다.")
else:
    st.info(
        "💡 OpenAI API 키가 등록되어 있지 않습니다. **규칙 기반 분석으로 자동 동작**합니다. "
        "(키 등록 위치는 README 참조)"
    )

tab_rss, tab_csv, tab_manual = st.tabs(["📡 RSS 자동 수집", "📂 CSV 업로드", "✍️ 수동 등록"])


# ============================================================
# (1) RSS 자동 수집
# ============================================================
with tab_rss:
    st.markdown("##### Google News RSS 기반 자동 수집")
    st.caption("[키워드 관리]에 등록된 활성 키워드를 사용합니다.")

    kw_df = db.get_keywords(active_only=True)
    if kw_df.empty:
        st.warning("활성 키워드가 없습니다. 먼저 [🏷️ 키워드 관리] 에서 키워드를 등록하세요.")
    else:
        selected_kws = st.multiselect(
            "수집할 키워드 선택",
            kw_df["keyword"].tolist(),
            default=kw_df["keyword"].tolist(),
        )
        max_per = st.slider("키워드당 최대 수집 건수", 5, 30, 10)
        do_ai = st.checkbox("AI 자동 분석 적용 (요약·분류·키워드·중요도·활용포인트)", value=True)

        if st.button("🚀 RSS 수집 시작", type="primary", disabled=not selected_kws):
            with st.spinner(f"{len(selected_kws)}개 키워드로 RSS 수집 중..."):
                try:
                    articles = rss_collector.fetch_for_all_keywords(selected_kws, max_per)
                except Exception as e:
                    st.error(f"RSS 수집 중 오류: {e}")
                    st.stop()

            st.info(f"수집된 후보 기사: **{len(articles)}건** (중복 URL 제거 완료)")

            if not articles:
                st.warning("수집된 기사가 없습니다.")
            else:
                # 등록된 키워드 (AI 키워드 추출 시 활용)
                all_registered_kws = db.get_keywords()["keyword"].tolist()
                inserted = 0
                skipped = 0
                unknown_date = 0
                rss_date_used = 0
                progress = st.progress(0)

                for i, a in enumerate(articles):
                    if do_ai:
                        analysis = ai_helper.analyze_article(
                            a["title"], a.get("summary", ""), all_registered_kws
                        )
                    else:
                        analysis = {
                            "summary": a.get("summary", ""),
                            "keywords": a.get("matched_keyword", ""),
                            "category": "기타",
                            "importance": "보통",
                            "education_point": "",
                        }

                    success = db.insert_article({
                        "collected_date": datetime.now().strftime("%Y-%m-%d"),
                        "published_date": a.get("published_date"),
                        "date_source": a.get("date_source", ""),
                        "source": a.get("source", ""),
                        "title": a["title"],
                        "url": a["url"],
                        "summary": analysis["summary"],
                        "keywords": analysis["keywords"],
                        "category": analysis["category"],
                        "importance": analysis["importance"],
                        "education_point": analysis["education_point"],
                    })
                    ds = a.get("date_source", "")
                    if not a.get("published_date") or ds == "unknown":
                        unknown_date += 1
                    elif ds == "rss_fallback":
                        rss_date_used += 1

                    if success:
                        inserted += 1
                    else:
                        skipped += 1
                    progress.progress((i + 1) / len(articles))

                db.refresh_keyword_stats()
                st.success(f"✅ 신규 등록: **{inserted}건** / 중복 스킵: {skipped}건")
                if rss_date_used:
                    st.info(
                        f"원문 발행일 확인이 어려워 Google News RSS 날짜를 보조 발행일로 저장한 기사: "
                        f"**{rss_date_used}건**입니다. 일부 기사는 실제 원문 발행일과 차이가 있을 수 있습니다."
                    )
                if unknown_date:
                    st.info(
                        f"발행일을 확인하지 못한 기사 **{unknown_date}건**은 발행일을 비워두었습니다. "
                        "해당 기사는 일간 브리핑에 포함되지 않습니다."
                    )


# ============================================================
# (2) CSV 업로드
# ============================================================
with tab_csv:
    st.markdown("##### CSV 파일 업로드")
    st.caption("필수 컬럼: title, url / 선택: source, published_date, summary, keywords, category, importance")

    # 샘플 CSV 다운로드
    sample = pd.DataFrame([
        {"title": "예시 기사 제목", "url": "https://example.com/1",
         "source": "예시일보", "published_date": "2025-01-01",
         "summary": "기사 요약", "keywords": "마약,청소년", "category": "청소년",
         "importance": "보통"}
    ])
    st.download_button(
        "📥 샘플 CSV 다운로드",
        sample.to_csv(index=False).encode("utf-8-sig"),
        file_name="sample_articles_template.csv",
        mime="text/csv",
    )

    uploaded = st.file_uploader("CSV 파일 선택", type=["csv"])
    if uploaded:
        try:
            df = pd.read_csv(uploaded)
        except Exception:
            uploaded.seek(0)
            df = pd.read_csv(uploaded, encoding="cp949")

        st.dataframe(df.head(10), use_container_width=True)
        st.caption(f"총 {len(df)}건 미리보기")

        do_ai = st.checkbox("AI 자동 분석 적용 (빈 필드만 자동 채움)", value=True, key="csv_ai")

        if st.button("📥 CSV 데이터 등록", type="primary"):
            inserted = 0
            skipped = 0
            registered_kws = db.get_keywords()["keyword"].tolist()
            progress = st.progress(0)
            for i, row in df.iterrows():
                if not row.get("title") or not row.get("url"):
                    skipped += 1
                    continue
                summary = str(row.get("summary") or "")
                keywords = str(row.get("keywords") or "")
                category = str(row.get("category") or "")
                importance = str(row.get("importance") or "")
                edu = ""

                if do_ai and (not summary or not category or not importance):
                    analysis = ai_helper.analyze_article(row["title"], summary, registered_kws)
                    summary = summary or analysis["summary"]
                    keywords = keywords or analysis["keywords"]
                    category = category or analysis["category"]
                    importance = importance or analysis["importance"]
                    edu = analysis["education_point"]

                success = db.insert_article({
                    "collected_date": datetime.now().strftime("%Y-%m-%d"),
                    "published_date": str(row.get("published_date") or datetime.now().strftime("%Y-%m-%d")),
                    "source": str(row.get("source") or ""),
                    "title": str(row["title"]),
                    "url": str(row["url"]),
                    "summary": summary,
                    "keywords": keywords,
                    "category": category or "기타",
                    "importance": importance or "보통",
                    "education_point": edu,
                })
                if success:
                    inserted += 1
                else:
                    skipped += 1
                progress.progress((i + 1) / len(df))
            db.refresh_keyword_stats()
            st.success(f"✅ 신규 등록: **{inserted}건** / 스킵: {skipped}건")


# ============================================================
# (3) 수동 등록
# ============================================================
with tab_manual:
    st.markdown("##### 기사 수동 등록")
    with st.form("manual_form"):
        c1, c2 = st.columns(2)
        title = c1.text_input("제목 *", placeholder="기사 제목")
        url = c2.text_input("원문 URL *", placeholder="https://...")
        c3, c4, c5 = st.columns(3)
        source = c3.text_input("언론사", placeholder="예: 연합뉴스")
        pub_date = c4.date_input("발행일자", value=datetime.now().date())
        col_date = c5.date_input("수집일자", value=datetime.now().date())

        content = st.text_area("기사 본문 / 요약 (AI 분석용)", height=120,
                                placeholder="본문을 붙여넣으면 AI가 요약·분류를 자동 생성합니다.")
        do_ai = st.checkbox("AI 자동 분석 적용", value=True, key="manual_ai")

        submit = st.form_submit_button("➕ 등록", type="primary")

    if submit:
        if not title or not url:
            st.error("제목과 URL은 필수입니다.")
        else:
            if do_ai:
                registered_kws = db.get_keywords()["keyword"].tolist()
                analysis = ai_helper.analyze_article(title, content, registered_kws)
            else:
                analysis = {
                    "summary": content[:300], "keywords": "",
                    "category": "기타", "importance": "보통",
                    "education_point": "",
                }
            success = db.insert_article({
                "collected_date": col_date.strftime("%Y-%m-%d"),
                "published_date": pub_date.strftime("%Y-%m-%d"),
                "source": source, "title": title, "url": url,
                **analysis,
            })
            if success:
                db.refresh_keyword_stats()
                st.success("✅ 등록되었습니다.")
                st.balloons()
            else:
                st.warning("이미 등록된 URL입니다.")
