"""
==============================================================
 RSS 수집 모듈 (rss_collector.py)
==============================================================
 - Google News RSS 기반 기사 수집
 - Google News 리다이렉트 URL → 실제 원문 URL 자동 변환
 - date_extractor 모듈을 통해 발행일 정확도 대폭 개선
   ※ Google News RSS의 published 값은 실제 기사 발행일이 아니라
      Google News 수집/갱신 시각일 수 있어 최후 fallback으로만 사용
==============================================================
"""

import re
import base64
import logging
from urllib.parse import quote, urlparse, parse_qs
from datetime import datetime

import feedparser

from modules.date_extractor import (
    extract_published_date,
    safe_date_for_db,
    validate_date_against_rss,
    normalize_date,
    format_date,
)

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"


# -----------------------------------------------------------------
# Google News URL 디코딩
# -----------------------------------------------------------------

def _decode_google_news_url(source_url: str) -> str:
    """Google News URL → 실제 원문 URL 변환. 실패 시 원본 반환."""
    if "news.google.com" not in source_url:
        return source_url

    try:
        # 방법 1: requests로 리다이렉트 따라가기
        if requests is not None:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            }
            resp = requests.get(
                source_url, headers=headers,
                timeout=5, allow_redirects=True
            )
            final_url = resp.url
            if "news.google.com" not in final_url:
                return final_url

            # 리다이렉트 후에도 Google이면 HTML에서 원문 URL 추출
            if BeautifulSoup is not None:
                soup = BeautifulSoup(resp.text, "html.parser")
                # canonical 링크 확인
                canonical = soup.find("link", rel="canonical")
                if canonical and "news.google.com" not in canonical.get("href", ""):
                    return canonical["href"]
                # meta refresh 확인
                meta = soup.find("meta", attrs={"http-equiv": "refresh"})
                if meta:
                    content = meta.get("content", "")
                    m = re.search(r"url=(.+)", content, re.IGNORECASE)
                    if m:
                        return m.group(1).strip()

    except Exception as e:
        logger.debug(f"[URL디코딩] 실패 ({source_url}): {e}")

    # 방법 2: base64 디코딩 시도 (구버전 호환)
    try:
        if "/articles/" in source_url:
            path = source_url.split("/articles/")[-1].split("?")[0]
            padding = 4 - len(path) % 4
            if padding != 4:
                path += "=" * padding
            decoded = base64.b64decode(
                path.replace("-", "+").replace("_", "/")
            )
            url_match = re.search(
                rb"https?://[^\x00-\x1f\x7f-\xff\"<> ]+", decoded
            )
            if url_match:
                candidate = url_match.group(0).decode("utf-8")
                if "news.google.com" not in candidate:
                    return candidate
    except Exception:
        pass

    return source_url

def _parse_rss_date(entry) -> str:
    """feedparser entry에서 RSS pubDate를 YYYY-MM-DD로 파싱."""
    try:
        rss_pub = entry.published_parsed
        if rss_pub:
            return datetime(*rss_pub[:6]).strftime("%Y-%m-%d")
    except Exception:
        pass
    try:
        raw = getattr(entry, "published", "") or ""
        if raw:
            dt = normalize_date(raw)
            if dt:
                return format_date(dt)
    except Exception:
        pass
    return ""


# -----------------------------------------------------------------
# 단일 기사 발행일 추출
# -----------------------------------------------------------------

def get_article_published_date(url: str, rss_date: str = "") -> tuple:
    """
    원문 URL에서 발행일을 추출한다.

    Returns:
        (date_str, source_tag)
    """
    date_str, source = extract_published_date(url=url, rss_date=rss_date)

    if date_str and rss_date and source != "rss_fallback":
        date_str = validate_date_against_rss(date_str, rss_date, url)

    return date_str, source


# -----------------------------------------------------------------
# Google News RSS 수집
# -----------------------------------------------------------------

def fetch_google_news(keyword: str, max_items: int = 10) -> list:
    """Google News RSS에서 키워드 기반 기사 수집."""
    url = GOOGLE_NEWS_RSS.format(query=quote(keyword))

    try:
        feed = feedparser.parse(url)
    except Exception as e:
        logger.error(f"[RSS수집] feedparser 실패 (keyword={keyword}): {e}")
        return []

    results = []
    for entry in feed.entries[:max_items]:
        rss_date = _parse_rss_date(entry)

        title = getattr(entry, "title", "") or ""
        source = ""
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            title = parts[0]
            source = parts[1]

        summary = ""
        if hasattr(entry, "summary"):
            summary = re.sub(r"<[^>]+>", " ", entry.summary)
            summary = re.sub(r"\s+", " ", summary).strip()

        real_url = _decode_google_news_url(getattr(entry, "link", "") or "")

        published_date, date_source = get_article_published_date(
            url=real_url,
            rss_date=rss_date,
        )

        results.append({
            "title": title.strip(),
            "url": real_url,
            "source": source.strip() or "Google News",
            "published_date": published_date,
            "rss_date": rss_date,
            "date_source": date_source,
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
            logger.error(f"[RSS수집] keyword={kw}, error={e}")

    return all_articles
