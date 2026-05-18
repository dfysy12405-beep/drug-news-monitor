"""
==============================================================
 분석 모듈 (analyzer.py)
==============================================================
 - 누적 기사에서 신규 연관 키워드 자동 추천
 - 2회 이상 등장 / 일반어 제외 / 복합어 우선
 - 마약류·예방교육 관련성 높은 단어 우선
==============================================================
"""

import re
from collections import Counter
from datetime import datetime

from modules import database as db
from modules.ai_helper import STOPWORDS


# 마약류·예방교육 관련성 높은 단어가 포함된 키워드는 가중치 부여
RELEVANCE_HINTS = [
    "마약", "약물", "오남용", "중독", "처방", "투약", "유통", "단속",
    "청소년", "학생", "10대", "수험생", "재활", "치료", "예방",
    "캠페인", "교육", "강사", "위장", "신종", "합성",
    "ADHD", "펜타닐", "프로포폴", "옥시코돈", "졸피뎀", "대마", "코카인",
    "필로폰", "케타민", "MDMA", "엑스터시", "허브",
]


def _extract_candidates(text: str) -> list:
    """텍스트에서 후보 키워드 추출.
    - 한글 2글자 이상 또는 영문 2글자 이상
    - 복합어(공백 없는 명사구) 우선
    """
    # 한글/영문 토큰 추출
    tokens = re.findall(r"[가-힣]{2,}|[A-Za-z]{2,}", text)
    return [t for t in tokens if t not in STOPWORDS]


def analyze_recommended_keywords(min_occurrence: int = 2):
    """
    전체 기사에서 신규 추천 키워드 분석 → recommended_keywords 테이블에 저장.

    기준:
    - 2회 이상 반복 등장
    - 일반어(STOPWORDS) 제외
    - 마약류·예방교육 관련성 높은 단어 우선
    - 이미 keywords 테이블에 등록된 단어는 제외
    """
    # 등록된 키워드 (활성/비활성 모두 제외 대상)
    registered = set(db.get_keywords()["keyword"].tolist()) if not db.get_keywords().empty else set()

    # 전체 기사 합치기
    df = db.get_articles()
    if df.empty:
        return 0

    text_all = " ".join(
        (df["title"].fillna("") + " " + df["summary"].fillna("") + " " + df["keywords"].fillna(""))
        .tolist()
    )

    # 후보 추출
    candidates = _extract_candidates(text_all)
    counter = Counter(candidates)

    new_count = 0
    for word, cnt in counter.most_common(200):
        if cnt < min_occurrence:
            break
        if word in registered:
            continue
        if len(word) < 2:
            continue

        # 관련 기사 수 계산
        related = df[
            df["title"].str.contains(word, na=False) |
            df["summary"].str.contains(word, na=False) |
            df["keywords"].str.contains(word, na=False)
        ].shape[0]

        # 관련성 가중치 적용 (관련 힌트 포함 단어는 점수 보정)
        is_relevant = any(hint in word or word in hint for hint in RELEVANCE_HINTS)

        # 관련성이 낮고 등장 횟수도 적으면 스킵
        if not is_relevant and cnt < 3:
            continue

        db.upsert_recommended_keyword(word, cnt, related)
        new_count += 1

    return new_count


def get_keyword_trend(days: int = 7):
    """최근 N일 기사 수 추이 (날짜별)."""
    df = db.get_articles()
    if df.empty:
        return []
    df["collected_date"] = df["collected_date"].fillna("")
    counts = df.groupby("collected_date").size().reset_index(name="count")
    return counts.sort_values("collected_date").tail(days).to_dict("records")


def get_top_keywords(top_n: int = 10):
    """기사들의 keywords 필드를 합쳐 빈출 키워드 추출."""
    df = db.get_articles()
    if df.empty:
        return []
    all_kws = []
    for kws in df["keywords"].fillna(""):
        all_kws.extend([k.strip() for k in kws.split(",") if k.strip()])
    counter = Counter(all_kws)
    return counter.most_common(top_n)


def get_category_counts():
    """카테고리별 기사 수."""
    df = db.get_articles()
    if df.empty:
        return []
    return df["category"].fillna("기타").value_counts().reset_index().to_dict("records")
