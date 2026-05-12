"""
==============================================================
 페이지 2: 키워드 관리
==============================================================
 - 키워드 추가/수정/삭제/활성화
 - 키워드별 기사 수, 마지막 수집일 표시
==============================================================
"""

import streamlit as st
from datetime import datetime

from modules import database as db
from modules.utils import page_header


db.init_db()

page_header(
    "🏷️", "키워드 관리",
    "기사 수집·필터링에 사용되는 키워드 등록 및 관리"
)

# ------------------------------------------------------------
# 새 키워드 추가
# ------------------------------------------------------------
with st.expander("➕ 새 키워드 추가", expanded=False):
    with st.form("add_keyword_form"):
        c1, c2, c3 = st.columns([3, 2, 5])
        new_kw = c1.text_input("키워드", placeholder="예: 펜타닐")
        new_type = c2.selectbox("유형", ["핵심", "약물", "대상", "분야", "기관", "사업", "지역", "일반"])
        new_memo = c3.text_input("메모 (선택)", placeholder="키워드 등록 사유 등")
        submit = st.form_submit_button("추가", type="primary")

    if submit:
        if not new_kw.strip():
            st.error("키워드를 입력해 주세요.")
        else:
            success = db.add_keyword(new_kw.strip(), new_type, new_memo)
            if success:
                db.refresh_keyword_stats()
                st.success(f"'{new_kw}' 키워드가 추가되었습니다.")
                st.rerun()
            else:
                st.warning("이미 등록된 키워드입니다.")

# ------------------------------------------------------------
# 키워드 통계 갱신 버튼
# ------------------------------------------------------------
c_refresh, _ = st.columns([1, 6])
if c_refresh.button("🔄 통계 갱신"):
    db.refresh_keyword_stats()
    st.success("키워드 통계가 갱신되었습니다.")
    st.rerun()

# ------------------------------------------------------------
# 키워드 목록
# ------------------------------------------------------------
kw_df = db.get_keywords()

if kw_df.empty:
    st.info("등록된 키워드가 없습니다.")
    st.stop()

st.markdown(f"##### 📋 등록 키워드 총 **{len(kw_df)}개** "
            f"(활성 {int(kw_df['is_active'].sum())} / 비활성 {len(kw_df) - int(kw_df['is_active'].sum())})")

# 헤더 표시
hdr = st.columns([0.4, 2, 1, 0.8, 1, 1, 0.7, 0.7])
hdr[0].markdown("**ID**")
hdr[1].markdown("**키워드**")
hdr[2].markdown("**유형**")
hdr[3].markdown("**활성**")
hdr[4].markdown("**기사 수**")
hdr[5].markdown("**최근 수집일**")
hdr[6].markdown("**수정**")
hdr[7].markdown("**삭제**")
st.divider()

for _, row in kw_df.iterrows():
    cols = st.columns([0.4, 2, 1, 0.8, 1, 1, 0.7, 0.7])
    cols[0].write(f"#{row['id']}")
    cols[1].markdown(f"**{row['keyword']}**")
    cols[2].caption(row.get("keyword_type") or "-")

    new_active = cols[3].toggle("", value=bool(row.get("is_active")), key=f"act_{row['id']}",
                                 label_visibility="collapsed")
    if bool(new_active) != bool(row.get("is_active")):
        db.update_keyword(row["id"], is_active=1 if new_active else 0)
        st.rerun()

    cols[4].write(f"{int(row.get('article_count') or 0)}건")
    cols[5].caption(row.get("last_collected_date") or "-")

    if cols[6].button("✏️", key=f"edit_{row['id']}", help="수정"):
        st.session_state[f"editing_{row['id']}"] = True

    if cols[7].button("🗑️", key=f"del_{row['id']}", help="삭제"):
        db.delete_keyword(row["id"])
        st.success(f"'{row['keyword']}' 키워드가 삭제되었습니다.")
        st.rerun()

    # 수정 폼
    if st.session_state.get(f"editing_{row['id']}"):
        with st.form(f"edit_form_{row['id']}"):
            e1, e2, e3 = st.columns([3, 2, 4])
            ed_kw = e1.text_input("키워드", value=row["keyword"])
            ed_type = e2.selectbox(
                "유형", ["핵심", "약물", "대상", "분야", "기관", "사업", "지역", "일반"],
                index=(["핵심", "약물", "대상", "분야", "기관", "사업", "지역", "일반"]
                       .index(row.get("keyword_type") or "일반")
                       if (row.get("keyword_type") in ["핵심", "약물", "대상", "분야", "기관", "사업", "지역", "일반"])
                       else 7)
            )
            ed_memo = e3.text_input("메모", value=row.get("memo") or "")
            c_save, c_cancel = st.columns(2)
            do_save = c_save.form_submit_button("💾 저장", type="primary")
            do_cancel = c_cancel.form_submit_button("취소")
        if do_save:
            db.update_keyword(row["id"], keyword=ed_kw, keyword_type=ed_type, memo=ed_memo)
            del st.session_state[f"editing_{row['id']}"]
            st.success("수정되었습니다.")
            st.rerun()
        if do_cancel:
            del st.session_state[f"editing_{row['id']}"]
            st.rerun()
