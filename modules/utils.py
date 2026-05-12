"""
==============================================================
 공통 UI 유틸리티 (utils.py)
==============================================================
"""

import streamlit as st

# 중요도별 색상 (높음 → 민트색으로 변경)
IMPORTANCE_COLORS = {
    "높음": ("#0d9488", "#f0fdfa"),   # 민트/틸
    "보통": ("#2563eb", "#dbeafe"),   # 파랑
    "낮음": ("#64748b", "#f1f5f9"),   # 회색
}

CATEGORY_COLORS = {
    "사건·사고": "#ef4444",
    "정책·법률": "#3b82f6",
    "청소년": "#f59e0b",
    "의료용 마약류": "#10b981",
    "예방교육 활용 가능": "#8b5cf6",
    "한국마약퇴치운동본부 관련": "#ec4899",
    "강원지역 관련": "#0ea5e9",
    "기타": "#64748b",
}

CATEGORY_LIST = list(CATEGORY_COLORS.keys())


def badge_importance(importance: str) -> str:
    fg, bg = IMPORTANCE_COLORS.get(importance, IMPORTANCE_COLORS["보통"])
    icon = "🟢" if importance == "높음" else ("🟡" if importance == "보통" else "⚪")
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 10px;'
        f'border-radius:12px;font-size:0.8rem;font-weight:600;'
        f'display:inline-block;">{icon} {importance}</span>'
    )


def badge_category(category: str) -> str:
    color = CATEGORY_COLORS.get(category, "#64748b")
    return (
        f'<span style="background:{color}1a;color:{color};'
        f'padding:2px 10px;border-radius:6px;font-size:0.78rem;'
        f'font-weight:500;border:1px solid {color}40;'
        f'display:inline-block;">{category or "기타"}</span>'
    )


def keyword_tags(keywords_str: str, max_tags: int = 6) -> str:
    if not keywords_str:
        return ""
    kws = [k.strip() for k in keywords_str.split(",") if k.strip()][:max_tags]
    html = ""
    for kw in kws:
        html += (
            f'<span style="background:#e0e7ff;color:#3730a3;padding:2px 8px;'
            f'border-radius:4px;font-size:0.75rem;margin-right:4px;'
            f'display:inline-block;">#{kw}</span>'
        )
    return html


def render_article_card(row, show_summary: bool = True):
    """기사 카드 렌더링 - 제목 클릭 시 원문 링크 새 창으로 이동."""
    if hasattr(row, "to_dict"):
        row = row.to_dict()

    importance = row.get("importance", "보통")
    fg_color = IMPORTANCE_COLORS.get(importance, IMPORTANCE_COLORS["보통"])[0]
    border_left = f"4px solid {fg_color}" if importance == "높음" else "1px solid #e2e8f0"

    title = row.get("title", "(제목 없음)")
    source = row.get("source", "")
    pub_date = row.get("published_date", "")
    col_date = row.get("collected_date", "")
    summary = row.get("summary", "")
    url = row.get("url", "")
    fav = "⭐ " if row.get("is_favorite") else ""

    # 제목: URL 있으면 클릭 시 새 창으로 원문 이동
    if url and url.startswith("http"):
        title_html = (
            f'<a href="{url}" target="_blank" '
            f'style="color:#0f172a;text-decoration:none;font-weight:600;font-size:1.0rem;line-height:1.4;" '
            f'onmouseover="this.style.color=\'#0d9488\';this.style.textDecoration=\'underline\'" '
            f'onmouseout="this.style.color=\'#0f172a\';this.style.textDecoration=\'none\'">'
            f'{fav}{title} 🔗</a>'
        )
    else:
        title_html = f'<span style="font-weight:600;font-size:1.0rem;color:#0f172a;">{fav}{title}</span>'

    card = f"""
    <div style="background:white;border-left:{border_left};
                border-top:1px solid #e2e8f0;border-right:1px solid #e2e8f0;
                border-bottom:1px solid #e2e8f0;border-radius:8px;
                padding:14px 18px;margin-bottom:10px;
                box-shadow:0 1px 2px rgba(0,0,0,0.04);">
        <div style="display:flex;justify-content:space-between;align-items:start;">
            <div style="flex:1;">
                <div>{title_html}</div>
                <div style="font-size:0.78rem;color:#64748b;margin-top:4px;">
                    📰 {source} &nbsp;|&nbsp; 발행 {pub_date} &nbsp;|&nbsp; 수집 {col_date}
                </div>
            </div>
            <div style="margin-left:12px;">{badge_importance(importance)}</div>
        </div>
        {f'<div style="margin-top:8px;color:#475569;font-size:0.88rem;line-height:1.5;">{summary}</div>' if show_summary and summary else ''}
        <div style="margin-top:10px;">
            {badge_category(row.get("category", "기타"))} &nbsp; {keyword_tags(row.get("keywords", ""))}
        </div>
    </div>
    """
    st.markdown(card, unsafe_allow_html=True)


def page_header(icon: str, title: str, desc: str = ""):
    st.markdown(f"""
    <div style="padding:14px 0 6px 0;border-bottom:2px solid #e2e8f0;margin-bottom:18px;">
        <div style="font-size:1.5rem;font-weight:700;color:#0f172a;">{icon} {title}</div>
        {f'<div style="font-size:0.9rem;color:#64748b;margin-top:4px;">{desc}</div>' if desc else ''}
    </div>
    """, unsafe_allow_html=True)
