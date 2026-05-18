"""
==============================================================
 RSS 수집 모듈 (rss_collector.py)
==============================================================
 - Google News RSS 기반 기사 수집
 - Google News 리다이렉트 URL → 실제 원문 URL 자동 변환
 - 기사 발행일은 원문 메타데이터에서 확인 가능한 경우에만 저장
   ※ Google News RSS의 published 값은 실제 기사 발행일이 아니라
      Google News 수집/갱신 시각일 수 있어 옛날 기사가 오늘 기사처럼
      분류되는 문제가 발생할 수 있음
==============================================================
"""

import re
import base64
import json
from urllib.parse import quote, urlparse, parse_qs
from datetime import datetime
import email.utils

import feedparser

try:
    import requests
    from bs4 import BeautifulSoup
except Exception:  # 배포 환경에서 의존성 누락 시에도 앱이 중단되지 않도록 처리
    requests = None
    BeautifulSoup = None

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"


# ------------------------------------------------------------
# 날짜 정규화
# ------------------------------------------------------------
def _normalize_date(value: str) -> str:
    """여러 형식의 날짜 문자열을 YYYY-MM-DD로 변환. 실패 시 빈 문자열."""
    if not value:
        return ""

    raw = str(value).strip()
    if not raw:
        return ""

    # JSON-LD 등에서 리스트로 들어오는 경우 방어
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw.strip("[]").strip('"\' ')

    # 2026. 5. 15. / 2026년 5월 15일 / 2026-05-15 등 우선 처리
    m = re.search(r"(20\d{2})\D{0,3}(\d{1,2})\D{0,3}(\d{1,2})", raw)
    if m:
        y, mo, d = m.groups()
        try:
            return datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
        except Exception:
            pass

    # ISO / RFC 계열 처리
    candidates = [
        raw,
        raw.replace("Z", "+00:00"),
        raw.split("+")[0].strip(),
        raw.split("T")[0].strip(),
    ]
    for c in candidates:
        if not c:
            continue
        try:
            return datetime.fromisoformat(c).strftime("%Y-%m-%d")
        except Exception:
            pass
        try:
            parsed = email.utils.parsedate_to_datetime(c)
            if parsed:
                return parsed.strftime("%Y-%m-%d")
        except Exception:
            pass

    return ""


# ------------------------------------------------------------
# Google News URL 디코딩 (리다이렉트 → 실제 원문 URL)
# ------------------------------------------------------------
def _decode_google_news_url(source_url: str) -> str:
    """
    Google News RSS 링크를 실제 원문 URL로 변환.
    실패하면 원래 URL 그대로 반환.
    """
    try:
        parsed = urlparse(source_url)
        params = parse_qs(parsed.query)
        if "url" in params:
            return params["url"][0]

        if "news.google.com" in source_url and "/articles/" in source_url:
            path = source_url.split("/articles/")[-1].split("?")[0]
            try:
                padding = 4 - len(path) % 4
                if padding != 4:
                    path += "=" * padding
                decoded = base64.b64decode(path.replace("-", "+").replace("_", "/"))
                url_match = re.search(rb'https?://[^\x00-\x1f\x7f-\xff"<> ]+', decoded)
                if url_match:
                    return url_match.group(0).decode("utf-8")
            except Exception:
                pass

        url_match = re.search(r'https?://(?!news\.google\.com)[^\s"<>]+', source_url)
        if url_match:
            return url_match.group(0)

    except Exception:
        pass

    return source_url


# ------------------------------------------------------------
# 원문 기사 발행일 추출
# ------------------------------------------------------------
def _extract_published_date_from_article(url: str) -> str:
    """
    원문 페이지의 메타태그/JSON-LD에서 실제 발행일을 추출한다.
    추출 실패 시 빈 문자열을 반환한다.

    주의: Google News RSS의 published 값은 실제 발행일이 아닐 수 있으므로
    일간 브리핑 기준일로 사용하지 않는다.
    """
    if not url or requests is None or BeautifulSoup is None:
        return ""

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=7, allow_redirects=True)
        if resp.status_code >= 400 or not resp.text:
            return ""

        soup = BeautifulSoup(resp.text, "html.parser")

        meta_keys = [
            ("property", "article:published_time"),
            ("property", "og:article:published_time"),
            ("name", "article:published_time"),
            ("name", "pubdate"),
            ("name", "publishdate"),
            ("name", "publish_date"),
            ("name", "date"),
            ("name", "dc.date"),
            ("name", "dc.date.issued"),
            ("name", "dcterms.created"),
            ("itemprop", "datePublished"),
        ]
        for attr, key in meta_keys:
            tag = soup.find("meta", attrs={attr: key})
            if tag:
                date = _normalize_date(tag.get("content", ""))
                if date:
                    return date

        time_tag = soup.find("time")
        if time_tag:
            date = _normalize_date(time_tag.get("datetime", "") or time_tag.get_text(" ", strip=True))
            if date:
                return date

        # 국내 언론사 본문에 자주 노출되는 날짜 문구 보완
        # 예: 입력 2026.05.18 14:20 / 승인 2026년 5월 18일 / 기사입력 2026-05-18
        page_text = soup.get_text(" ", strip=True)
        date_patterns = [
            r"(?:입력|등록|승인|발행|기사입력|최초입력)\s*[:：]?\s*(20\d{2}[\.\-/년\s]+\d{1,2}[\.\-/월\s]+\d{1,2})",
            r"(20\d{2}[\.\-/년\s]+\d{1,2}[\.\-/월\s]+\d{1,2})\s*(?:입력|등록|승인|발행)",
        ]
        for pattern in date_patterns:
            m = re.search(pattern, page_text)
            if m:
                date = _normalize_date(m.group(1))
                if date:
                    return date

        # JSON-LD 기사 구조에서 datePublished/dateCreated 추출
        for script in soup.find_all("script", type="application/ld+json"):
            text = script.string or script.get_text(" ", strip=True)
            if not text:
                continue
            try:
                data = json.loads(text)
            except Exception:
                continue

            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                graph = item.get("@graph")
                if isinstance(graph, list):
                    items.extend([g for g in graph if isinstance(g, dict)])
                for key in ("datePublished", "dateCreated", "uploadDate"):
                    date = _normalize_date(item.get(key, ""))
                    if date:
                        return date

    except Exception:
        return ""

    return ""


def fetch_google_news(keyword: str, max_items: int = 10) -> list:
    """Google News RSS에서 키워드 기반 기사 수집."""
    url = GOOGLE_NEWS_RSS.format(query=quote(keyword))
    feed = feedparser.parse(url)

    results = []
    for entry in feed.entries[:max_items]:
        # Google News RSS의 published_parsed는 '구글 뉴스 노출/갱신일'일 수 있으므로
        # 일간 브리핑용 발행일로 저장하지 않는다. 참고용 필드로만 보관한다.
        try:
            rss_pub = entry.published_parsed
            rss_date = datetime(*rss_pub[:6]).strftime("%Y-%m-%d")
        except Exception:
            rss_date = ""

        title = entry.title
        source = ""
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            title = parts[0]
            source = parts[1]

        summary = ""
        if hasattr(entry, "summary"):
            summary = re.sub(r"<[^>]+>", " ", entry.summary)
            summary = re.sub(r"\s+", " ", summary).strip()

        real_url = _decode_google_news_url(entry.link)
        real_published_date = _extract_published_date_from_article(real_url)

        # 원문 발행일이 확인되면 우선 사용하고, 실패한 경우 Google News RSS 날짜를 보조값으로 사용한다.
        # RSS 날짜는 원문 발행일과 다를 수 있으므로, 대시보드 판단 시 원문 확인이 필요한 보조값이다.
        published_date = real_published_date or rss_date

        results.append({
            "title": title.strip(),
            "url": real_url,
            "source": source.strip() or "Google News",
            "published_date": published_date,
            "rss_date": rss_date,
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
