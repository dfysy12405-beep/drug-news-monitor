"""
==============================================================
 RSS 수집 모듈 (rss_collector.py)
==============================================================
 - Google News RSS 기반 기사 수집
 - Google News 리다이렉트 URL → 실제 원문 URL 자동 변환
==============================================================
"""

import re
import base64
import struct
from urllib.parse import quote, urlparse, parse_qs
from datetime import datetime
import feedparser

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"


# ------------------------------------------------------------
# Google News URL 디코딩 (리다이렉트 → 실제 원문 URL)
# ------------------------------------------------------------
def _decode_google_news_url(source_url: str) -> str:
    """
    Google News RSS 링크를 실제 원문 URL로 변환.
    실패하면 원래 URL 그대로 반환.
    """
    try:
        # 방법 1: URL 파라미터에 직접 URL이 있는 경우
        parsed = urlparse(source_url)
        params = parse_qs(parsed.query)
        if "url" in params:
            return params["url"][0]

        # 방법 2: Google News 인코딩된 URL 디코딩
        # https://news.google.com/rss/articles/CBMi... 형태
        if "news.google.com" in source_url and "/articles/" in source_url:
            path = source_url.split("/articles/")[-1].split("?")[0]
            # Base64 디코딩 시도
            try:
                # 패딩 맞추기
                padding = 4 - len(path) % 4
                if padding != 4:
                    path += "=" * padding
                decoded = base64.b64decode(path.replace("-", "+").replace("_", "/"))
                # 디코딩된 바이트에서 URL 패턴 추출
                url_match = re.search(rb'https?://[^\x00-\x1f\x7f-\xff"<> ]+', decoded)
                if url_match:
                    return url_match.group(0).decode("utf-8")
            except Exception:
                pass

        # 방법 3: source_url 안의 http 패턴 직접 추출
        url_match = re.search(r'https?://(?!news\.google\.com)[^\s"<>]+', source_url)
        if url_match:
            return url_match.group(0)

    except Exception:
        pass

    # 변환 실패 시 원래 URL 반환
    return source_url


def fetch_google_news(keyword: str, max_items: int = 10) -> list:
    """Google News RSS에서 키워드 기반 기사 수집."""
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

        # 제목에서 언론사 분리 ("제목 - 언론사" 형식)
        title = entry.title
        source = ""
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            title = parts[0]
            source = parts[1]

        # 요약문 HTML 태그 제거
        summary = ""
        if hasattr(entry, "summary"):
            summary = re.sub(r"<[^>]+>", " ", entry.summary)
            summary = re.sub(r"\s+", " ", summary).strip()

        # ★ 핵심: Google News 리다이렉트 URL → 실제 원문 URL 변환
        real_url = _decode_google_news_url(entry.link)

        results.append({
            "title": title.strip(),
            "url": real_url,
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
