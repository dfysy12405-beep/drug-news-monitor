"""
==============================================================
 RSS 수집 모듈 (rss_collector.py)
==============================================================
 - Google News RSS 기반 기사 수집
 - 추후 네이버 뉴스 RSS 등으로 확장 가능

 ★ RSS 연동 위치:
   - "기사수집" 페이지에서 사용
   - 키워드 관리에 등록된 키워드 중 is_active=1 인 항목을 자동 순회
==============================================================
"""

from urllib.parse import quote
from datetime import datetime
import feedparser  # RSS 파서

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"


def fetch_google_news(keyword: str, max_items: int = 10) -> list:
    """Google News RSS에서 키워드 기반 기사 수집.

    Returns:
        list of dict {title, url, source, published_date, summary}
    """
    url = GOOGLE_NEWS_RSS.format(query=quote(keyword))
    feed = feedparser.parse(url)

    results = []
    for entry in feed.entries[:max_items]:
        # 발행일 파싱
        try:
            pub = entry.published_parsed
            pub_date = datetime(*pub[:6]).strftime("%Y-%m-%d")
        except Exception:
            pub_date = datetime.now().strftime("%Y-%m-%d")

        # Google News는 "제목 - 언론사" 형식이라 분리
        title = entry.title
        source = ""
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            title = parts[0]
            source = parts[1]

        # summary 필드(요약문)
        summary = ""
        if hasattr(entry, "summary"):
            # HTML 태그 단순 제거
            import re
            summary = re.sub(r"<[^>]+>", " ", entry.summary)
            summary = re.sub(r"\s+", " ", summary).strip()

        results.append({
            "title": title.strip(),
            "url": entry.link,
            "source": source.strip() or "Google News",
            "published_date": pub_date,
            "summary": summary[:500],
        })

    return results


def fetch_for_all_keywords(keywords: list, max_per_keyword: int = 10) -> list:
    """등록된 모든 키워드에 대해 기사 수집."""
    all_articles = []
    seen_urls = set()
    for kw in keywords:
        try:
            articles = fetch_google_news(kw, max_per_keyword)
            for a in articles:
                if a["url"] not in seen_urls:
                    seen_urls.add(a["url"])
                    a["matched_keyword"] = kw
                    all_articles.append(a)
        except Exception as e:
            print(f"[RSS 수집 실패] keyword={kw}, error={e}")
    return all_articles
