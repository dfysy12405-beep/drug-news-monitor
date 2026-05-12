"""
==============================================================
 페이지 3: 추천 키워드 관리
==============================================================
 - 누적 기사에서 자동 추출된 연관 키워드 검토
 - 승인 시 keywords 테이블로 자동 이동
 - 자동 등록 절대 금지 - 반드시 관리자 승인 필요
==============================================================
"""

import streamlit as st

from modules import database as db
from modules import analyzer
from modules.utils import page_header

st.set_page_config(page_title="추천 키워드", page_icon="💡", layout="wide")

db.init_db()

page_header(
    "💡", "AI 추천 키워드 관리",
    "누적 기사 분석을 통해 자동 추출된 연관 키워드 검토·승인"
)

# ------------------------------------------------------------
# 분석 실행 버튼
# ------------------------------------------------------------
c1, c2 = st.columns([1, 6])
if c1.button("🔍 추천 키워드 재분석", type="primary"):
    with st.spinner("기사 분석 중..."):
        n = analyzer.analyze_recommended_keywords()
    st.success(f"분석 완료: {n}건의 추천 키워드를 갱신했습니다.")
    st.rerun()

c2.info(
    "📌 추천 기준: 2회 이상 반복 등장 / 일반어 제외 / 마약류·예방교육 관련성 있는 단어 우선. "
    "**승인하지 않으면 실제 키워드로 등록되지 않습니다.**"
)

# ------------------------------------------------------------
# 상태 필터
# ------------------------------------------------------------
status_tabs = st.tabs(["⏳ 검토 대기 (pending)", "✅ 승인됨 (approved)", "❌ 거절됨 (rejected)"])
status_map = {"⏳ 검토 대기 (pending)": "pending",
              "✅ 승인됨 (approved)": "approved",
              "❌ 거절됨 (rejected)": "rejected"}

for tab, label in zip(status_tabs, status_map.keys()):
    with tab:
        status = status_map[label]
        df = db.get_recommended_keywords(status=status)
        if df.empty:
            st.info(f"{status} 상태의 추천 키워드가 없습니다.")
            continue

        st.markdown(f"##### 총 **{len(df)}건**")

        # 헤더
        hdr = st.columns([0.4, 2.5, 1.2, 1.2, 1.4, 2])
        hdr[0].markdown("**ID**")
        hdr[1].markdown("**키워드**")
        hdr[2].markdown("**등장 횟수**")
        hdr[3].markdown("**관련 기사**")
        hdr[4].markdown("**최근 감지일**")
        hdr[5].markdown("**처리**")
        st.divider()

        for _, row in df.iterrows():
            cols = st.columns([0.4, 2.5, 1.2, 1.2, 1.4, 2])
            cols[0].write(f"#{row['id']}")
            cols[1].markdown(f"**{row['keyword']}**")
            cols[2].write(f"{row.get('occurrence_count', 0)}회")
            cols[3].write(f"{row.get('related_article_count', 0)}건")
            cols[4].caption(row.get("latest_detected_date") or "-")

            with cols[5]:
                bc1, bc2 = st.columns(2)
                if status != "approved":
                    if bc1.button("✅ 승인", key=f"appr_{row['id']}", use_container_width=True):
                        db.update_recommended_status(row["id"], "approved")
                        db.refresh_keyword_stats()
                        st.success(f"'{row['keyword']}' 키워드를 승인하여 등록했습니다.")
                        st.rerun()
                if status != "rejected":
                    if bc2.button("❌ 거절", key=f"rej_{row['id']}", use_container_width=True):
                        db.update_recommended_status(row["id"], "rejected")
                        st.warning(f"'{row['keyword']}' 키워드를 거절했습니다.")
                        st.rerun()
