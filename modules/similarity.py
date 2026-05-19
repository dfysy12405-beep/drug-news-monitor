"""
==============================================================
 유사 기사 묶기 모듈 (similarity.py)
==============================================================
 - 제목 전처리 + 본문/요약 앞부분 + 키워드 겹침 기반 그룹화
 - 기본 방식: TF-IDF + Cosine Similarity(scikit-learn)
 - fallback: difflib 기반 제목 유사도
 - DB 저장 없이 화면 표시 시점에 실시간 그룹화
==============================================================
"""

from __future__ import annotations

import re
import difflib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

import pandas as pd

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    _USE_SKLEARN = True
except Exception:
    TfidfVectorizer = None
    cosine_similarity = None
    _USE_SKLEARN = False


# ------------------------------------------------------------
# 전처리 패턴
# ------------------------------------------------------------
_BRACKET_TAGS = re.compile(
    r"\[(속보|단독|종합|긴급|업데이트|포토|영상|사진|인터뷰|기고|칼럼|사설|전문|르포)\]",
    re.IGNORECASE,
)
_ROUND_TAGS = re.compile(
    r"\((속보|단독|종합|긴급|업데이트|포토|영상|사진|인터뷰|기고|칼럼|사설|전문|르포)\)",
    re.IGNORECASE,
)
_SPECIAL_CHARS = re.compile(r"[^\uAC00-\uD7A3a-zA-Z0-9\s]")
_MULTI_SPACE = re.compile(r"\s+")
_MEDIA_SUFFIX = re.compile(
    r"[\-\s]+(연합뉴스|뉴시스|뉴스1|한겨레|조선일보|중앙일보|동아일보|경향신문|"
    r"한국일보|서울신문|국민일보|세계일보|문화일보|머니투데이|아시아경제|"
    r"헤럴드경제|이데일리|파이낸셜뉴스|파이낸셜뉴스|fnnews|YTN|MBC|KBS|SBS|JTBC|TV조선|"
    r"채널A|뉴스위크|시사IN|주간경향|강원일보|강원도민일보|춘천MBC|CBS|노컷뉴스)\s*$",
    re.IGNORECASE,
)

_STOPWORDS = {
    "관련", "대해", "위해", "통해", "따르면", "밝혀", "전해", "보도", "기자",
    "특파원", "전", "후", "및", "등", "이번", "지난", "오늘", "내일", "올해", "지난해",
    "서울", "한국", "국내", "정부", "경찰", "검찰", "법원", "혐의", "발표", "추진",
}

# 제목에 자주 섞이는 분절 기호 제거용
_TITLE_PREFIX = re.compile(r"^(속보|단독|종합|긴급|업데이트|포토|영상|사진)\s*")


# ============================================================
# 1. 전처리 함수
# ============================================================
def clean_title(title: str) -> str:
    """기사 제목을 유사도 비교용으로 정리."""
    if not title or not isinstance(title, str):
        return ""

    t = title.strip()
    t = _BRACKET_TAGS.sub(" ", t)
    t = _ROUND_TAGS.sub(" ", t)
    t = _TITLE_PREFIX.sub(" ", t)
    t = _MEDIA_SUFFIX.sub(" ", t)
    t = t.replace("…", " ").replace("·", " ")
    t = _SPECIAL_CHARS.sub(" ", t)
    words = [w for w in t.split() if w not in _STOPWORDS and len(w) > 1]
    t = _MULTI_SPACE.sub(" ", " ".join(words)).strip().lower()
    return t


def _normalize_keywords(value: Any) -> set:
    if value is None:
        return set()
    if isinstance(value, float) and pd.isna(value):
        return set()
    text = str(value)
    # 쉼표, 슬래시, 해시태그 혼용 대응
    parts = re.split(r"[,/#|;\s]+", text)
    return {p.strip().lower() for p in parts if len(p.strip()) > 1}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value)


def _article_text(row: Dict[str, Any]) -> str:
    """
    TF-IDF 비교용 텍스트 구성.
    제목을 가장 크게 반영하고, 요약/활용포인트/키워드를 보조로 반영.
    """
    title = clean_title(_safe_text(row.get("title")))
    summary = _safe_text(row.get("summary"))[:700]
    edu = _safe_text(row.get("education_point"))[:300]
    kws = " ".join(sorted(_normalize_keywords(row.get("keywords"))))

    # 제목을 여러 번 반복해 제목 유사도가 그룹화에 더 크게 작용하도록 함
    return _MULTI_SPACE.sub(" ", f"{title} {title} {title} {kws} {summary} {edu}").strip()


def _parse_date(d: Any) -> Optional[datetime]:
    if d is None:
        return None
    s = str(d).strip()
    if not s:
        return None
    # YYYY-MM-DD / YYYY.MM.DD / YYYY/MM/DD / YYYY-MM-DD HH:MM 대응
    s10 = s[:10].replace(".", "-").replace("/", "-")
    for fmt in ("%Y-%m-%d",):
        try:
            return datetime.strptime(s10, fmt)
        except Exception:
            pass
    return None


def _date_diff_ok(d1: Optional[datetime], d2: Optional[datetime], window: int) -> bool:
    if d1 and d2:
        return abs((d1 - d2).days) <= window
    # 둘 중 하나라도 날짜가 없으면 제목/본문 기준으로 판단하도록 허용
    return True


# ============================================================
# 2. 점수 계산
# ============================================================
def _keyword_overlap_score(k1: set, k2: set) -> float:
    """키워드 Jaccard 점수(0~1)."""
    if not k1 or not k2:
        return 0.0
    inter = len(k1 & k2)
    union = len(k1 | k2)
    return inter / union if union else 0.0


def calculate_similarity(title1: str, title2: str) -> float:
    """호환용: 제목 difflib 유사도를 0~100으로 반환."""
    t1, t2 = clean_title(title1), clean_title(title2)
    if not t1 or not t2:
        return 0.0
    return difflib.SequenceMatcher(None, t1, t2).ratio() * 100


def _combined_score(
    title_score: float,
    body_score: float,
    keyword_score: float,
    same_source: bool = False,
) -> float:
    """
    최종 점수(0~1).
    - 제목/본문 TF-IDF를 중심으로 하되 키워드 겹침을 가산
    - 같은 언론사라고 해서 무조건 같은 기사로 묶지 않도록 가중치는 낮게 적용
    """
    score = (title_score * 0.58) + (body_score * 0.30) + (keyword_score * 0.12)
    if same_source:
        score -= 0.03  # 같은 언론사의 서로 다른 기사 오묶음 방지
    return max(0.0, min(1.0, score))


# ============================================================
# 3. 그룹화
# ============================================================
def group_similar_articles(
    articles: pd.DataFrame,
    threshold: float = 68.0,
    date_window: int = 3,
    min_title_score: float = 0.42,
) -> List[List[Dict[str, Any]]]:
    """
    기사 목록을 유사기사 그룹으로 묶어 반환.

    Args:
        articles: DataFrame
        threshold: 최종 유사도 기준. 0~100 입력을 권장.
                   기존 UI 호환을 위해 60~95 값이 들어오면 내부에서 0.60~0.95로 변환.
        date_window: 발행일 차이 허용 범위(일)
        min_title_score: 제목 최소 유사도. 본문이 비슷해도 제목이 너무 다르면 제외.
    """
    if articles is None or articles.empty:
        return []

    df = articles.copy().reset_index(drop=True)
    rows: List[Dict[str, Any]] = df.to_dict("records")
    n = len(rows)
    if n == 1:
        return [rows]

    # 60, 70 같은 UI 값을 0.60으로 변환
    thr = float(threshold)
    if thr > 1:
        thr = thr / 100.0

    dates = [_parse_date(r.get("published_date")) for r in rows]
    keywords = [_normalize_keywords(r.get("keywords")) for r in rows]
    clean_titles = [clean_title(_safe_text(r.get("title"))) for r in rows]
    full_texts = [_article_text(r) for r in rows]

    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    # TF-IDF 벡터 생성. 한국어 형태소 분석 없이도 char n-gram이 제목 유사도에 꽤 안정적임.
    if _USE_SKLEARN:
        try:
            title_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1)
            body_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, max_features=6000)
            title_matrix = title_vectorizer.fit_transform(clean_titles)
            body_matrix = body_vectorizer.fit_transform(full_texts)
            title_sim = cosine_similarity(title_matrix)
            body_sim = cosine_similarity(body_matrix)
        except Exception:
            title_sim = body_sim = None
    else:
        title_sim = body_sim = None

    # pairwise 비교
    for i in range(n):
        for j in range(i + 1, n):
            if not _date_diff_ok(dates[i], dates[j], int(date_window)):
                continue

            if title_sim is not None and body_sim is not None:
                ts = float(title_sim[i, j])
                bs = float(body_sim[i, j])
            else:
                ts = calculate_similarity(clean_titles[i], clean_titles[j]) / 100.0
                bs = difflib.SequenceMatcher(None, full_texts[i], full_texts[j]).ratio()

            kw = _keyword_overlap_score(keywords[i], keywords[j])
            same_source = _safe_text(rows[i].get("source")) == _safe_text(rows[j].get("source"))
            score = _combined_score(ts, bs, kw, same_source=same_source)

            # 강한 제목 유사도는 바로 묶고, 중간 유사도는 키워드/본문이 함께 받쳐줄 때만 묶음
            strong_title_match = ts >= max(0.74, thr)
            balanced_match = (score >= thr and ts >= min_title_score)
            keyword_assisted = (ts >= 0.50 and bs >= 0.38 and kw >= 0.20)

            if strong_title_match or balanced_match or keyword_assisted:
                union(i, j)
                rows[i].setdefault("_similarity_debug", {})
                rows[j].setdefault("_similarity_debug", {})
                rows[j]["_similarity_debug"] = {
                    "score": round(score, 3),
                    "title": round(ts, 3),
                    "body": round(bs, 3),
                    "keyword": round(kw, 3),
                }

    groups_dict: Dict[int, List[Dict[str, Any]]] = {}
    for i, row in enumerate(rows):
        root = find(i)
        groups_dict.setdefault(root, []).append(row)

    importance_order = {"높음": 0, "보통": 1, "낮음": 2}

    def article_sort_key(a: Dict[str, Any]) -> Tuple[int, str, int]:
        imp = importance_order.get(_safe_text(a.get("importance")) or "보통", 1)
        date = _safe_text(a.get("published_date")) or "0000-00-00"
        summary_len = len(_safe_text(a.get("summary")))
        return (imp, date, summary_len)

    result: List[List[Dict[str, Any]]] = []
    for group in groups_dict.values():
        # 최신/중요 기사 대표로 올라오도록 정렬
        group.sort(key=article_sort_key, reverse=False)
        result.append(group)

    result.sort(key=lambda g: _safe_text(g[0].get("published_date")) or "0000-00-00", reverse=True)
    return result


# ============================================================
# 4. 대표 기사 및 그룹 메타
# ============================================================
def select_representative_article(group: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not group:
        return {}
    return group[0]


def build_group_meta(group: List[Dict[str, Any]]) -> Dict[str, Any]:
    rep = select_representative_article(group)
    sources = list(dict.fromkeys([_safe_text(a.get("source")) for a in group if _safe_text(a.get("source"))]))
    dates = [_safe_text(a.get("published_date")) for a in group if _safe_text(a.get("published_date"))]
    latest_date = max(dates) if dates else ""

    all_kws = []
    for a in group:
        all_kws.extend(list(_normalize_keywords(a.get("keywords"))))
    top_kws = [k for k, _ in Counter(all_kws).most_common(6)]

    # 그룹 대표 제목은 대표 기사 제목 사용
    return {
        "representative": rep,
        "articles": group,
        "count": len(group),
        "sources": sources,
        "latest_date": latest_date,
        "top_keywords": top_kws,
        "is_group": len(group) > 1,
    }


def get_grouped_articles(
    articles: pd.DataFrame,
    threshold: float = 68.0,
    date_window: int = 3,
) -> List[Dict[str, Any]]:
    """group_similar_articles + build_group_meta."""
    groups = group_similar_articles(articles, threshold=threshold, date_window=date_window)
    return [build_group_meta(g) for g in groups]
