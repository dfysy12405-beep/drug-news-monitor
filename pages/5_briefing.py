"""
==============================================================
 페이지 5: 주간 브리핑
==============================================================
 - 최근 7일 기사 자동 분석
 - 주요 이슈, 키워드, 예방교육 활용 기사, 정책·법률, 강사 공유용 요약
==============================================================
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter

from modules import database as db
from modules.utils import page_header, badge_importance, badge_category

st.set_page_config(page_title="주간 브리핑", page_icon="📋", layout="wide")

db.init_db()

page_header(
    "📋", "주간 브리핑",
    "최근 7일 기사 자동 분석 보고서"
)

# ------------------------------------------------------------
# 기간 선택
# ------------------------------------------------------------
days_range = st.slider("분석 기간 (일)", 3, 30, 7)
today = datetime.now().date()
start_date = (today - timedelta(days=days_range - 1)).strftime("%Y-%m-%d")
end_date = today.strftime("%Y-%m-%d")

st.caption(f"📅 분석 기간: **{start_date} ~ {end_date}**")

df = db.get_articles(start_date=start_date, end_date=end_date)
if df.empty:
    st.warning("해당 기간에 수집된 기사가 없습니다.")
    st.stop()

st.markdown(f"##### 📊 분석 대상 기사: **{len(df)}건**")

# ------------------------------------------------------------
# 1. 이번 주 주요 이슈 (중요도 높음)
# ------------------------------------------------------------
st.markdown("### 1️⃣ 이번 주 주요 이슈")
high_df = df[df["importance"] == "높음"].head(8)
if high_df.empty:
    st.info("중요도 '높음' 기사가 없습니다.")
else:
    for _, row in high_df.iterrows():
        st.markdown(
            f"- **[{row.get('source','')}]** {row['title']} "
            f"<small>({row.get('published_date','')})</small>",
            unsafe_allow_html=True,
        )
        if row.get("summary"):
            st.caption(f"&nbsp;&nbsp;→ {row['summary'][:150]}")

# ------------------------------------------------------------
# 2. 주요 키워드 TOP 10
# ------------------------------------------------------------
st.markdown("### 2️⃣ 주요 키워드 TOP 10")
all_kws = []
for s in df["keywords"].fillna(""):
    all_kws.extend([k.strip() for k in s.split(",") if k.strip()])
counter = Counter(all_kws)
top10 = counter.most_common(10)
if top10:
    kw_html = ""
    for kw, cnt in top10:
        kw_html += (
            f'<span style="display:inline-block;background:#eef2ff;color:#3730a3;'
            f'padding:6px 14px;border-radius:20px;margin:4px 4px 4px 0;'
            f'font-size:0.92rem;font-weight:500;">#{kw} '
            f'<span style="color:#6366f1;font-weight:700;">{cnt}</span></span>'
        )
    st.markdown(kw_html, unsafe_allow_html=True)
else:
    st.info("키워드 데이터가 없습니다.")

# ------------------------------------------------------------
# 3. 예방교육 활용 가능 기사
# ------------------------------------------------------------
st.markdown("### 3️⃣ 예방교육 활용 가능 기사")
edu_df = df[df["category"].isin(["예방교육 활용 가능", "청소년", "한국마약퇴치운동본부 관련"])].head(8)
if edu_df.empty:
    st.info("해당 기사가 없습니다.")
else:
    for _, row in edu_df.iterrows():
        st.markdown(f"**{row['title']}** &nbsp; {badge_category(row.get('category','기타'))}",
                    unsafe_allow_html=True)
        if row.get("education_point"):
            st.success(f"💡 {row['education_point']}")
        else:
            st.caption(row.get("summary", "")[:200])

# ------------------------------------------------------------
# 4. 정책·법률 관련 기사
# ------------------------------------------------------------
st.markdown("### 4️⃣ 정책·법률 관련 기사")
pol_df = df[df["category"] == "정책·법률"].head(6)
if pol_df.empty:
    st.info("정책·법률 기사가 없습니다.")
else:
    for _, row in pol_df.iterrows():
        st.markdown(f"- **{row['title']}** &nbsp; "
                    f"<small>({row.get('source','')} · {row.get('published_date','')})</small>",
                    unsafe_allow_html=True)
        if row.get("summary"):
            st.caption(f"&nbsp;&nbsp;→ {row['summary'][:150]}")

# ------------------------------------------------------------
# 5. 강사 공유용 요약 (텍스트 형식)
# ------------------------------------------------------------
st.markdown("### 5️⃣ 강사 공유용 요약 (텍스트 복사 가능)")

briefing_text = f"""[마약류 언론동향 주간 브리핑]
기간: {start_date} ~ {end_date}
총 기사: {len(df)}건 / 중요 {len(df[df['importance']=='높음'])}건

▣ 주요 이슈
"""
for _, row in high_df.iterrows():
    briefing_text += f"- [{row.get('source','')}] {row['title']}\n"

briefing_text += "\n▣ 주요 키워드\n"
briefing_text += " / ".join([f"{kw}({cnt})" for kw, cnt in top10])

briefing_text += "\n\n▣ 예방교육 활용 가능 기사\n"
for _, row in edu_df.iterrows():
    briefing_text += f"- {row['title']}\n"
    if row.get("education_point"):
        briefing_text += f"  ↳ 활용 포인트: {row['education_point']}\n"

briefing_text += "\n▣ 정책·법률 동향\n"
for _, row in pol_df.iterrows():
    briefing_text += f"- {row['title']}\n"

st.text_area("📋 복사하여 강사·팀원에게 공유", briefing_text, height=400)

st.download_button(
    "📥 브리핑 다운로드 (.txt)",
    briefing_text.encode("utf-8"),
    file_name=f"briefing_{start_date}_{end_date}.txt",
    mime="text/plain",
)
