"""
==============================================================
 유사 기사 묶기 모듈 (similarity.py)
==============================================================
 - 제목 전처리 → 유사도 계산 → 그룹화 → 대표 기사 선정
 - difflib 기본 사용 (rapidfuzz 설치 시 자동 전환)
 - Streamlit 캐싱 적용
==============================================================
"""

import re
import difflib
from datetime import datetime, timedelta
from typing import List, Dict, Any

import pandas as pd

# rapidfuzz 있으면 더 빠르게 동작 (없어도 정상 동작)
try:
    from rapidfuzz import fuzz as _rfuzz
    _USE_RAPIDFUZZ = True
except ImportError:
    _USE_RAPIDFUZZ = False


# ------------------------------------------------------------
# 불필요 패턴 정의
# ------------------------------------------------------------
_BRACKET_TAGS = re.compile(
    r'\[(속보|단독|종합|긴급|업데이트|포토|영상|사진|인터뷰|기고|칼럼|사설)\]',
    re.IGNORECASE
)
_SPECIAL_CHARS = re.compile(r'[^\uAC00-\uD7A3a-zA-Z0-9\s]')  # 한글·영문·숫자·공백 외 제거
_MULTI_SPACE   = re.compile(r'\s+')

# 흔한 언론사명 패턴 (제목 끝에 붙는 경우 제거)
_MEDIA_SUFFIX = re.compile(
    r'[\-\s]+(연합뉴스|뉴시스|뉴스1|한겨레|조선일보|중앙일보|동아일보|경향신문|'
    r'한국일보|서울신문|국민일보|세계일보|문화일보|머니투데이|아시아경제|'
    r'헤럴드경제|이데일리|파이낸셜뉴스|YTN|MBC|KBS|SBS|JTBC|TV조선|'
    r'채널A|뉴스위크|시사IN|주간경향|강원일보|강원도민일보|춘천MBC)\s*$'
)

# 반복 등장 불필요 단어
_STOPWORDS = {
    '관련', '대해', '위해', '통해', '따르면', '밝혀', '전해',
    '보도', '기자', '특파원', '전', '후', '및', '등',
}


# ============================================================
# 1. 제목 전처리
# ============================================================
def clean_title(title: str) -> str:
    """
    기사 제목을 유사도 비교에 적합하게 전처리.

    처리 순서:
    1) [속보] [단독] 등 태그 제거
    2) 언론사명 suffix 제거
    3) 특수문자 제거
    4) 불필요 단어 제거
    5) 공백 정리 및 소문자화
    """
    if not title or not isinstance(title, str):
        return ""

    t = title.strip()
    t = _BRACKET_TAGS.sub('', t)        # [속보] 등 제거
    t = _MEDIA_SUFFIX.sub('', t)         # 끝 언론사명 제거
    t = _SPECIAL_CHARS.sub(' ', t)       # 특수문자 → 공백
    # 불필요 단어 제거
    words = [w for w in t.split() if w not in _STOPWORDS and len(w) > 0]
    t = ' '.join(words)
    t = _MULTI_SPACE.sub(' ', t).strip() # 다중 공백 정리
    return t.lower()


# ============================================================
# 2. 유사도 계산
# ============================================================
def calculate_similarity(title1: str, title2: str) -> float:
    """
    두 제목의 유사도를 0~100 점수로 반환.
    rapidfuzz 설치 시 token_sort_ratio 사용 (어순 무관),
    없으면 difflib SequenceMatcher 사용.
    """
    t1 = clean_title(title1)
    t2 = clean_title(title2)

    if not t1 or not t2:
        return 0.0

    if _USE_RAPIDFUZZ:
        # token_sort_ratio: 단어 순서 달라도 유사하면 높은 점수
        return _rfuzz.token_sort_ratio(t1, t2)
    else:
        ratio = difflib.SequenceMatcher(None, t1, t2).ratio()
        return ratio * 100


# ============================================================
# 3. 유사 기사 그룹화
# ============================================================
def group_similar_articles(
    articles: pd.DataFrame,
    threshold: float = 80.0,
    date_window: int = 3,
) -> List[List[Dict]]:
    """
    기사 목록을 유사 기사 그룹으로 묶어 반환.

    Args:
        articles:    DB에서 가져온 DataFrame
        threshold:   유사도 기준 (0~100, 기본 80)
        date_window: 발행일 차이 기준 (일, 기본 3)

    Returns:
        List of groups. 각 group = List of article dicts.
        단독 기사(유사 기사 없음)도 길이 1인 그룹으로 포함.
    """
    if articles.empty:
        return []

    rows = articles.to_dict('records')
    n = len(rows)
    group_id = list(range(n))  # 유니온-파인드 초기화

    def find(i):
        while group_id[i] != i:
            group_id[i] = group_id[group_id[i]]
            i = group_id[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            group_id[ri] = rj

    # 날짜 파싱 캐시
    def parse_date(d):
        if not d or not isinstance(d, str):
            return None
        for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'):
            try:
                return datetime.strptime(d[:10], fmt)
            except Exception:
                continue
        return None

    dates = [parse_date(r.get('published_date', '')) for r in rows]

    # O(n²) 비교 — 기사 수가 많아질 경우 블록 단위로 최적화 가능
    for i in range(n):
        for j in range(i + 1, n):
            # 날짜 차이 필터 (먼저 체크해서 유사도 계산 생략)
            if dates[i] and dates[j]:
                diff = abs((dates[i] - dates[j]).days)
                if diff > date_window:
                    continue

            sim = calculate_similarity(
                rows[i].get('title', ''),
                rows[j].get('title', '')
            )
            if sim >= threshold:
                union(i, j)

    # 그룹 ID별로 묶기
    groups_dict: Dict[int, List[Dict]] = {}
    for i, row in enumerate(rows):
        root = find(i)
        groups_dict.setdefault(root, []).append(row)

    # 각 그룹 내부 정렬: 중요도순 → 최신 발행일순 → 본문 길이순
    importance_order = {'높음': 0, '보통': 1, '낮음': 2}

    def sort_key(a):
        imp = importance_order.get(a.get('importance', '보통'), 1)
        date = a.get('published_date') or '0000-00-00'
        length = len(a.get('summary', '') or '')
        return (imp, date, length)

    result = []
    for group in groups_dict.values():
        group.sort(key=sort_key)
        result.append(group)

    # 전체 그룹 정렬: 대표 기사 최신 발행일순
    result.sort(
        key=lambda g: g[0].get('published_date') or '0000-00-00',
        reverse=True
    )
    return result


# ============================================================
# 4. 대표 기사 선정
# ============================================================
def select_representative_article(group: List[Dict]) -> Dict:
    """
    그룹에서 대표 기사 1건 선정.
    기준: 중요도 높음 > 최신 발행일 > 본문 길이
    (group_similar_articles 에서 이미 정렬됨 → 첫 번째 반환)
    """
    if not group:
        return {}
    return group[0]


# ============================================================
# 5. 그룹 메타 정보 생성
# ============================================================
def build_group_meta(group: List[Dict]) -> Dict:
    """그룹 요약 정보 딕셔너리 반환."""
    rep = select_representative_article(group)
    sources = list({a.get('source', '') for a in group if a.get('source')})
    dates = [a.get('published_date', '') for a in group if a.get('published_date')]
    latest_date = max(dates) if dates else ''

    # 키워드 합산
    all_kws = []
    for a in group:
        for kw in (a.get('keywords') or '').split(','):
            kw = kw.strip()
            if kw:
                all_kws.append(kw)
    from collections import Counter
    top_kws = [k for k, _ in Counter(all_kws).most_common(5)]

    return {
        'representative': rep,
        'articles': group,
        'count': len(group),
        'sources': sources,
        'latest_date': latest_date,
        'top_keywords': top_kws,
        'is_group': len(group) > 1,
    }


# ============================================================
# 6. Streamlit 캐시 래퍼
# ============================================================
def get_grouped_articles(
    articles: pd.DataFrame,
    threshold: float = 80.0,
    date_window: int = 3,
) -> List[Dict]:
    """
    group_similar_articles + build_group_meta 를 합쳐
    캐시 가능한 형태로 반환.

    ※ DataFrame은 해시 불가능하므로 캐시는 호출부에서
      st.cache_data + to_json 변환으로 처리.
    """
    groups = group_similar_articles(articles, threshold, date_window)
    return [build_group_meta(g) for g in groups]
