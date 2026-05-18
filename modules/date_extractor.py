"""
==============================================================
 발행일 추출 전용 모듈 (date_extractor.py)
==============================================================
 한국 뉴스 사이트에 최적화된 발행일 크롤링 모듈.

 [추출 우선순위]
  1. 언론사별 전용 CSS selector (사이트별 구조 대응)
  2. JSON-LD 구조화 데이터 (datePublished / dateCreated)
  3. OpenGraph / 표준 메타태그 (article:published_time 등)
  4. <time> 태그 datetime 속성
  5. <time> 태그 innerText (상대시간 포함)
  6. 한국 언론사 본문 패턴 (입력/등록/승인 등)
  7. 일반 날짜 정규식 (본문 전체)
  8. HTTP 응답 헤더 Last-Modified
  9. RSS pubDate (마지막 fallback)

 [신뢰도 소스 태그]
  "meta_tag", "json_ld", "site_selector", "time_tag",
  "body_pattern", "http_header", "rss_fallback", "unknown"

 [오래된 기사 오탐 방지]
  - 추출된 날짜가 2010년 이전 → 신뢰하지 않음
  - 추출된 날짜가 수집일보다 미래 → 신뢰하지 않음
  - RSS 날짜와 원문 날짜 차이가 7일 초과 시 로그 출력
==============================================================
"""

import re
import json
import logging
import email.utils
from datetime import datetime, timedelta
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 1. 날짜 정규화 공통 함수
# ─────────────────────────────────────────────

# 유효한 날짜 범위 설정 (2010-01-01 ~ 오늘 + 1일 허용)
_MIN_DATE = datetime(2010, 1, 1)


def _get_max_date() -> datetime:
    return datetime.now() + timedelta(days=1)


def normalize_date(raw: str) -> Optional[datetime]:
    """
    다양한 형식의 날짜 문자열을 datetime 객체로 변환.
    실패 시 None 반환.
    """
    if not raw:
        return None
    raw = str(raw).strip()
    if not raw:
        return None

    # JSON-LD 리스트 처리: ["2026-05-18"] → 2026-05-18
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw.strip("[]").strip('"\'').strip()

    # 상대시간 처리 (한국어)
    rel = _parse_relative_time_ko(raw)
    if rel:
        return rel

    # 패턴 1: 한국식 날짜 2026. 5. 18. / 2026년 5월 18일 / 2026-05-18 / 2026/05/18
    m = re.search(r"(20\d{2})\D{0,3}(\d{1,2})\D{0,3}(\d{1,2})", raw)
    if m:
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if _is_valid_date(dt):
                return dt
        except ValueError:
            pass

    # 패턴 2: ISO 8601 / RFC 2822 계열
    for candidate in [
        raw,
        raw.replace("Z", "+00:00"),
        raw.split("+")[0].strip(),
        raw.split("T")[0].strip(),
    ]:
        if not candidate:
            continue
        try:
            dt = datetime.fromisoformat(candidate)
            if _is_valid_date(dt):
                return dt
        except (ValueError, TypeError):
            pass
        try:
            dt = email.utils.parsedate_to_datetime(candidate)
            if dt and _is_valid_date(dt):
                return dt
        except Exception:
            pass

    # 패턴 3: dateparser 활용 (설치된 경우)
    try:
        import dateparser
        dt = dateparser.parse(
            raw,
            languages=["ko", "en"],
            settings={
                "PREFER_DAY_OF_MONTH": "first",
                "RETURN_AS_TIMEZONE_AWARE": False,
                "PREFER_LOCALE_DATE_ORDER": True,
            },
        )
        if dt and _is_valid_date(dt):
            return dt
    except ImportError:
        pass
    except Exception:
        pass

    return None


def _parse_relative_time_ko(raw: str) -> Optional[datetime]:
    """
    한국어 상대시간 → datetime 변환.
    예: "5시간 전", "1일 전", "30분 전", "방금 전", "어제"
    """
    now = datetime.now()
    raw = raw.strip()

    if "방금" in raw or "금방" in raw:
        return now

    if "어제" in raw:
        return now - timedelta(days=1)

    if "그제" in raw or "그저께" in raw:
        return now - timedelta(days=2)

    patterns = [
        (r"(\d+)\s*분\s*전", lambda n: now - timedelta(minutes=int(n))),
        (r"(\d+)\s*시간\s*전", lambda n: now - timedelta(hours=int(n))),
        (r"(\d+)\s*일\s*전", lambda n: now - timedelta(days=int(n))),
        (r"(\d+)\s*주\s*전", lambda n: now - timedelta(weeks=int(n))),
        (r"(\d+)\s*달\s*전", lambda n: now - timedelta(days=int(n) * 30)),
        (r"(\d+)\s*개월\s*전", lambda n: now - timedelta(days=int(n) * 30)),
        (r"(\d+)\s*년\s*전", lambda n: now - timedelta(days=int(n) * 365)),
        # 영문 상대시간도 처리
        (r"(\d+)\s*hour[s]?\s*ago", lambda n: now - timedelta(hours=int(n))),
        (r"(\d+)\s*minute[s]?\s*ago", lambda n: now - timedelta(minutes=int(n))),
        (r"(\d+)\s*day[s]?\s*ago", lambda n: now - timedelta(days=int(n))),
    ]

    for pattern, calc in patterns:
        m = re.search(pattern, raw, re.IGNORECASE)
        if m:
            try:
                return calc(m.group(1))
            except Exception:
                pass
    return None


def _is_valid_date(dt: datetime) -> bool:
    """추출된 날짜가 유효 범위(2010 ~ 내일) 안에 있는지 확인."""
    try:
        dt_naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
        return _MIN_DATE <= dt_naive <= _get_max_date()
    except Exception:
        return False


def format_date(dt: Optional[datetime]) -> str:
    """datetime → 'YYYY-MM-DD' 문자열 변환. None 이면 빈 문자열."""
    if dt is None:
        return ""
    try:
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


# ─────────────────────────────────────────────
# 2. 언론사별 전용 CSS Selector 맵
#    우선순위: 숫자가 낮을수록 신뢰도 높음
# ─────────────────────────────────────────────

# domain → [(css_selector, datetime_attr_or_None), ...]
# datetime_attr: "datetime" → tag['datetime'] 사용
#                None       → tag.get_text() 사용
SITE_SELECTORS = {
    # 연합뉴스
    "yna.co.kr": [
        ("meta[name='article:published_time']", "content"),
        (".article-dateline time", "datetime"),
        (".update-time", None),
    ],
    # 조선일보
    "chosun.com": [
        ("meta[property='article:published_time']", "content"),
        (".article-body time", "datetime"),
        (".date-time", None),
    ],
    # 중앙일보
    "joongang.co.kr": [
        ("meta[property='article:published_time']", "content"),
        (".byline time", "datetime"),
        (".date", None),
    ],
    # 동아일보
    "donga.com": [
        ("meta[name='article:published_time']", "content"),
        (".article_date", None),
        ("span.date03", None),
    ],
    # 한겨레
    "hani.co.kr": [
        ("meta[property='article:published_time']", "content"),
        (".article-text .date-time", None),
        ("em.publish-date", None),
    ],
    # 경향신문
    "khan.co.kr": [
        ("meta[property='article:published_time']", "content"),
        (".art_info .date", None),
    ],
    # 국민일보
    "kmib.co.kr": [
        ("meta[property='article:published_time']", "content"),
        (".nwview_info span", None),
    ],
    # 세계일보
    "segye.com": [
        ("meta[property='article:published_time']", "content"),
        (".txt_info .date", None),
    ],
    # 문화일보
    "munhwa.com": [
        ("meta[property='article:published_time']", "content"),
        (".article_dateline", None),
    ],
    # MBC
    "imnews.imbc.com": [
        ("meta[property='article:published_time']", "content"),
        (".news_headline .date", None),
    ],
    # KBS
    "news.kbs.co.kr": [
        ("meta[property='article:published_time']", "content"),
        (".article-header .date", None),
        (".info-text .date", None),
    ],
    # SBS
    "news.sbs.co.kr": [
        ("meta[property='article:published_time']", "content"),
        (".article_header .date_time", None),
    ],
    # YTN
    "ytn.co.kr": [
        ("meta[property='article:published_time']", "content"),
        (".news_area .date", None),
    ],
    # 뉴시스
    "newsis.com": [
        ("meta[property='article:published_time']", "content"),
        (".article_title .date", None),
    ],
    # 뉴스1
    "news1.kr": [
        ("meta[property='article:published_time']", "content"),
        (".article-head-info .info-date", None),
    ],
    # 머니투데이
    "mt.co.kr": [
        ("meta[property='article:published_time']", "content"),
        (".view_head .date_wrap em", None),
    ],
    # 헤럴드경제
    "heraldcorp.com": [
        ("meta[property='article:published_time']", "content"),
        (".article-head-info .date", None),
    ],
    # 아시아경제
    "asiae.co.kr": [
        ("meta[property='article:published_time']", "content"),
        (".article_info .update", None),
    ],
    # 파이낸셜뉴스
    "fnnews.com": [
        ("meta[property='article:published_time']", "content"),
        (".article_head .info span:first-child", None),
    ],
    # 서울신문
    "seoul.co.kr": [
        ("meta[property='article:published_time']", "content"),
        (".articleDate", None),
    ],
    # 노컷뉴스
    "nocutnews.co.kr": [
        ("meta[property='article:published_time']", "content"),
        (".info_date", None),
    ],
    # 오마이뉴스
    "ohmynews.com": [
        ("meta[property='article:published_time']", "content"),
        ("#articeBody .article_title .date", None),
    ],
    # 프레시안
    "pressian.com": [
        ("meta[property='article:published_time']", "content"),
        (".article_header .article_date", None),
    ],
    # 한국일보
    "hankookilbo.com": [
        ("meta[property='article:published_time']", "content"),
        (".article-header time", "datetime"),
    ],
    # 데일리메디
    "dailymedi.com": [
        ("meta[property='article:published_time']", "content"),
        (".view_info .date", None),
    ],
    # 메디파나뉴스
    "medipana.com": [
        (".article-info .date", None),
    ],
}


def _get_site_selectors(url: str):
    """URL 도메인에 매칭되는 site selector 목록 반환."""
    try:
        domain = urlparse(url).netloc.lower()
        # www. 제거 후 매칭
        domain = domain.replace("www.", "")
        for key, selectors in SITE_SELECTORS.items():
            if key in domain:
                return selectors
    except Exception:
        pass
    return []


# ─────────────────────────────────────────────
# 3. 핵심: 원문 페이지에서 발행일 추출
# ─────────────────────────────────────────────

def extract_published_date(
    url: str,
    soup=None,            # 이미 파싱된 BeautifulSoup 객체가 있으면 재사용
    response=None,        # requests.Response 객체 (HTTP 헤더용)
    rss_date: str = "",   # fallback 용 RSS pubDate (YYYY-MM-DD)
    max_body_chars: int = 3000,  # 본문 텍스트 탐색 최대 길이
) -> Tuple[str, str]:
    """
    원문 URL에서 발행일을 추출한다.

    Returns:
        (date_str, source_tag)
        date_str   : "YYYY-MM-DD" or "" (실패)
        source_tag : "site_selector" | "json_ld" | "meta_tag" | "time_tag"
                   | "body_pattern" | "http_header" | "rss_fallback" | ""
    """
    if not url:
        return _rss_fallback(rss_date, url)

    # soup 없으면 직접 fetch
    _fetched_response = None
    if soup is None:
        soup, _fetched_response = _fetch_soup(url)
        if soup is None:
            logger.warning(f"[날짜추출] HTML 수신 실패: {url}")
            return _rss_fallback(rss_date, url)
    if response is None and _fetched_response is not None:
        response = _fetched_response

    # ── Step 1: 언론사별 전용 selector ──
    site_selectors = _get_site_selectors(url)
    for selector, attr in site_selectors:
        try:
            tag = soup.select_one(selector)
            if not tag:
                continue
            raw = tag.get(attr, "") if attr else tag.get_text(" ", strip=True)
            dt = normalize_date(raw)
            if dt and _is_valid_date(dt):
                logger.info(f"[날짜추출] site_selector 성공: {format_date(dt)} | {url}")
                return format_date(dt), "site_selector"
        except Exception as e:
            logger.debug(f"[날짜추출] site_selector 오류 ({selector}): {e}")

    # ── Step 2: JSON-LD 구조화 데이터 ──
    result = _extract_from_json_ld(soup, url)
    if result:
        return result, "json_ld"

    # ── Step 3: 표준 메타태그 ──
    result = _extract_from_meta(soup, url)
    if result:
        return result, "meta_tag"

    # ── Step 4: <time> 태그 ──
    result = _extract_from_time_tag(soup, url)
    if result:
        return result, "time_tag"

    # ── Step 5: 본문 텍스트 패턴 ──
    result = _extract_from_body_text(soup, url, max_body_chars)
    if result:
        return result, "body_pattern"

    # ── Step 6: HTTP 헤더 Last-Modified ──
    if response is not None:
        result = _extract_from_http_header(response, url)
        if result:
            return result, "http_header"

    # ── Step 7: RSS pubDate 최후 fallback ──
    return _rss_fallback(rss_date, url)


# ─────────────────────────────────────────────
# 내부 추출 함수들
# ─────────────────────────────────────────────

def _fetch_soup(url: str):
    """URL에서 HTML 수신 후 BeautifulSoup 반환. 실패 시 (None, None)."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("[날짜추출] requests 또는 beautifulsoup4가 설치되지 않았습니다.")
        return None, None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
        if resp.status_code >= 400:
            logger.warning(f"[날짜추출] HTTP {resp.status_code}: {url}")
            return None, resp
        # 인코딩 자동 감지 (한국 언론사 EUC-KR 대응)
        if resp.encoding and resp.encoding.lower() in ("euc-kr", "cp949"):
            resp.encoding = "euc-kr"
        elif not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding or "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")
        return soup, resp
    except Exception as e:
        logger.warning(f"[날짜추출] fetch 실패 ({url}): {e}")
        return None, None


def _extract_from_json_ld(soup, url: str) -> Optional[str]:
    """JSON-LD 스크립트에서 datePublished / dateCreated 추출."""
    try:
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            raw_text = script.string or script.get_text(" ", strip=True)
            if not raw_text:
                continue
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                # JSON이 깨진 경우 정규식으로 직접 추출 시도
                m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', raw_text)
                if m:
                    dt = normalize_date(m.group(1))
                    if dt:
                        logger.info(f"[날짜추출] json_ld(regex) 성공: {format_date(dt)} | {url}")
                        return format_date(dt)
                continue

            items = data if isinstance(data, list) else [data]
            # @graph 배열 포함 처리
            expanded = []
            for item in items:
                if isinstance(item, dict):
                    expanded.append(item)
                    graph = item.get("@graph")
                    if isinstance(graph, list):
                        expanded.extend([g for g in graph if isinstance(g, dict)])

            for item in expanded:
                for key in ("datePublished", "dateCreated", "dateModified", "uploadDate"):
                    raw_val = item.get(key, "")
                    if raw_val:
                        dt = normalize_date(str(raw_val))
                        if dt:
                            logger.info(f"[날짜추출] json_ld({key}) 성공: {format_date(dt)} | {url}")
                            return format_date(dt)
    except Exception as e:
        logger.debug(f"[날짜추출] json_ld 오류 ({url}): {e}")
    return None


def _extract_from_meta(soup, url: str) -> Optional[str]:
    """표준 메타태그에서 발행일 추출 (우선순위 순서)."""
    meta_targets = [
        # (attribute_name, attribute_value)
        ("property", "article:published_time"),
        ("property", "og:article:published_time"),
        ("name", "article:published_time"),
        ("name", "DC.date.issued"),
        ("name", "DC.date"),
        ("name", "dcterms.created"),
        ("name", "pubdate"),
        ("name", "publishdate"),
        ("name", "publish_date"),
        ("name", "date"),
        ("itemprop", "datePublished"),
        ("itemprop", "dateCreated"),
        # 수정일은 낮은 우선순위 (발행일 추출 실패 시에만 사용)
        ("property", "article:modified_time"),
        ("name", "article:modified_time"),
        ("itemprop", "dateModified"),
    ]
    for attr, val in meta_targets:
        try:
            tag = soup.find("meta", attrs={attr: re.compile(re.escape(val), re.IGNORECASE)})
            if tag:
                raw = tag.get("content", "")
                dt = normalize_date(raw)
                if dt:
                    logger.info(f"[날짜추출] meta_tag({val}) 성공: {format_date(dt)} | {url}")
                    return format_date(dt)
        except Exception as e:
            logger.debug(f"[날짜추출] meta 오류 ({val}): {e}")
    return None


def _extract_from_time_tag(soup, url: str) -> Optional[str]:
    """<time> 태그에서 발행일 추출."""
    try:
        time_tags = soup.find_all("time")
        for tag in time_tags:
            # datetime 속성 우선
            raw = tag.get("datetime", "") or tag.get("data-datetime", "")
            if not raw:
                # 텍스트 fallback (상대시간 포함)
                raw = tag.get_text(" ", strip=True)
            if raw:
                dt = normalize_date(raw)
                if dt:
                    logger.info(f"[날짜추출] time_tag 성공: {format_date(dt)} | {url}")
                    return format_date(dt)
    except Exception as e:
        logger.debug(f"[날짜추출] time_tag 오류 ({url}): {e}")
    return None


# 한국 언론사 본문 날짜 패턴
# 주의: 본문 내 사건 날짜와 구별하기 위해 "입력/등록/기사입력" 등 날짜 라벨이 있는 문장만 우선 사용
_BODY_DATE_LABELS_PRIMARY = [
    "기사입력", "최초입력", "입력", "등록", "승인", "게재", "발행", "송고", "게시"
]
_BODY_DATE_LABELS_SECONDARY = [
    "수정", "최종수정", "업데이트"
]

_DATE_CORE_PATTERN = (
    r"20\d{2}\s*(?:[.\-/년]\s*)\d{1,2}\s*(?:[.\-/월]\s*)\d{1,2}"
    r"(?:\s*일)?"
    r"(?:\s*(?:오전|오후|AM|PM|am|pm)?\s*\d{1,2}\s*[:：]\s*\d{2}(?:\s*[:：]\s*\d{2})?)?"
)

_BODY_DATE_PATTERNS = [
    # "입력 2026.05.18 14:20" / "기사입력 : 2026-05-18 09:10"
    rf"(?:{'|'.join(_BODY_DATE_LABELS_PRIMARY)})\s*[:：]?\s*({_DATE_CORE_PATTERN})",
    # "2026.05.18 14:20 입력" 등 날짜 먼저, 라벨 나중
    rf"({_DATE_CORE_PATTERN})\s*(?:{'|'.join(_BODY_DATE_LABELS_PRIMARY)})",
    # "기사 날짜: 2026.05.18"
    rf"기사\s*날짜\s*[:：]\s*({_DATE_CORE_PATTERN})",
]

_BODY_DATE_SECONDARY_PATTERNS = [
    rf"(?:{'|'.join(_BODY_DATE_LABELS_SECONDARY)})\s*[:：]?\s*({_DATE_CORE_PATTERN})",
    rf"({_DATE_CORE_PATTERN})\s*(?:{'|'.join(_BODY_DATE_LABELS_SECONDARY)})",
]


def _clean_visible_text(soup) -> str:
    """script/style/nav 등 불필요 영역을 제거하고 화면에 보이는 텍스트 중심으로 정리."""
    soup_copy = soup
    try:
        # 원본 soup를 직접 훼손하지 않기 위해 copy가 가능하면 복제
        import copy
        soup_copy = copy.copy(soup)
    except Exception:
        soup_copy = soup

    try:
        for tag in soup_copy(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()
    except Exception:
        pass

    text = soup_copy.get_text("\n", strip=True)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _find_date_in_text(text: str, patterns) -> Optional[str]:
    """문자열에서 날짜 패턴을 찾고 YYYY-MM-DD로 정규화."""
    if not text:
        return None
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            raw = m.group(1)
            dt = normalize_date(raw)
            if dt:
                return format_date(dt)
    return None


def _extract_from_body_text(soup, url: str, max_chars: int = 12000) -> Optional[str]:
    """
    본문/화면 텍스트에서 발행일을 추출한다.

    개선 기준:
    1) 기사 상단·메타 영역의 "입력/등록/기사입력" 라벨 우선
    2) 전체 visible text 앞부분에서 동일 라벨 재탐색
    3) 수정일은 낮은 우선순위로만 사용
    4) 라벨 없는 날짜 단독은 사건 날짜 오탐 가능성이 높아 사용하지 않음
    """
    try:
        candidate_texts = []

        # 국내 언론사에서 날짜가 들어가는 헤더/바이라인/메타 영역을 넓게 탐색
        header_selectors = [
            "header", "article header",
            ".article-head", ".article_head", ".article-header", ".articleHeader",
            ".news_head", ".news-head", ".headline", ".head_view", ".view_head",
            ".article_info", ".article-info", ".articleInfo", ".info_area",
            ".view_info", ".news_info", ".date_info", ".byline", ".byline_area",
            ".writer_info", ".reporter_area", ".article-date", ".article_date",
            ".date", ".time", ".meta", ".metadata", ".cont_info", ".viewTime",
            "#article-view-content-div", "#articleBody", "#news_body_area",
        ]
        for sel in header_selectors:
            try:
                for tag in soup.select(sel):
                    text = tag.get_text(" ", strip=True)
                    if text and len(text) >= 8:
                        candidate_texts.append(text[:3000])
            except Exception:
                continue

        visible_text = _clean_visible_text(soup)
        if visible_text:
            # 앞부분만 보지 않고 충분히 넓게 보되, 라벨 없는 날짜는 사용하지 않아 오탐을 줄임
            candidate_texts.append(visible_text[:max_chars])

            # "입력/등록/기사입력" 단어가 포함된 주변 문맥을 잘라 추가 탐색
            for label in _BODY_DATE_LABELS_PRIMARY + _BODY_DATE_LABELS_SECONDARY:
                for m in re.finditer(label, visible_text):
                    start = max(0, m.start() - 120)
                    end = min(len(visible_text), m.end() + 180)
                    candidate_texts.append(visible_text[start:end])

        # 1차: 최초 입력/등록 계열
        for text in candidate_texts:
            result = _find_date_in_text(text, _BODY_DATE_PATTERNS)
            if result:
                logger.info(f"[날짜추출] body_pattern(입력/등록) 성공: {result} | {url}")
                return result

        # 2차: 수정/업데이트 계열. 발행일이 전혀 없을 때만 사용
        for text in candidate_texts:
            result = _find_date_in_text(text, _BODY_DATE_SECONDARY_PATTERNS)
            if result:
                logger.info(f"[날짜추출] body_pattern(수정/업데이트) 성공: {result} | {url}")
                return result

    except Exception as e:
        logger.debug(f"[날짜추출] body_pattern 오류 ({url}): {e}")
    return None


def _extract_from_http_header(response, url: str) -> Optional[str]:
    """HTTP 응답 헤더 Last-Modified에서 날짜 추출."""
    try:
        last_modified = response.headers.get("Last-Modified", "")
        if last_modified:
            dt = normalize_date(last_modified)
            if dt:
                logger.info(f"[날짜추출] http_header(Last-Modified) 성공: {format_date(dt)} | {url}")
                return format_date(dt)
    except Exception as e:
        logger.debug(f"[날짜추출] http_header 오류 ({url}): {e}")
    return None


def _rss_fallback(rss_date: str, url: str) -> Tuple[str, str]:
    """RSS pubDate를 최후 fallback으로 사용."""
    if rss_date:
        dt = normalize_date(rss_date)
        if dt:
            logger.warning(f"[날짜추출] rss_fallback 사용 (원문 추출 실패): {format_date(dt)} | {url}")
            return format_date(dt), "rss_fallback"
    logger.warning(f"[날짜추출] 발행일 추출 완전 실패 (NULL 저장됨): {url}")
    return "", "unknown"


# ─────────────────────────────────────────────
# 4. 오래된 기사 오탐 방지 검증
# ─────────────────────────────────────────────

def validate_date_against_rss(
    extracted_date: str,
    rss_date: str,
    url: str,
    max_diff_days: int = 30,
) -> str:
    """
    원문에서 추출한 날짜와 RSS 날짜를 비교하여 신뢰성 검증.

    - RSS 날짜와 차이가 max_diff_days 초과 시 경고 로그 출력
    - 오래된 기사 오탐 여부는 로그로만 기록하고 날짜 자체는 반환
      (날짜 자동 교정은 하지 않음 - 실제 기사 날짜가 옛날일 수도 있음)

    Returns:
        검증된 날짜 문자열 (변경 없음)
    """
    if not extracted_date or not rss_date:
        return extracted_date

    try:
        dt_extracted = datetime.strptime(extracted_date, "%Y-%m-%d")
        dt_rss = datetime.strptime(rss_date, "%Y-%m-%d")
        diff = abs((dt_extracted - dt_rss).days)
        if diff > max_diff_days:
            logger.warning(
                f"[날짜검증] 원문 날짜({extracted_date})와 RSS 날짜({rss_date}) 차이 {diff}일 초과. "
                f"오래된 기사 오탐 가능성 있음: {url}"
            )
    except Exception:
        pass

    return extracted_date


# ─────────────────────────────────────────────
# 5. Supabase 저장용 날짜 문자열 안전 변환
# ─────────────────────────────────────────────

def safe_date_for_db(date_str: str) -> Optional[str]:
    """
    Supabase(PostgreSQL) DATE 컬럼에 저장 가능한 형태로 변환.
    - 유효한 'YYYY-MM-DD' 이면 그대로 반환
    - 빈 문자열 또는 파싱 불가 → None 반환 (DB에 NULL 저장)
    """
    if not date_str or not date_str.strip():
        return None
    dt = normalize_date(date_str)
    if dt:
        return format_date(dt)
    return None
