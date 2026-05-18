"""
==============================================================
 데이터베이스 모듈 (database.py)
==============================================================
 - Supabase DB 연결
 - articles / keywords / recommended_keywords 3개 테이블 관리
 - 기사/키워드 CRUD 함수 제공

※ 기존 SQLite(data/monitor.db) 방식은 Streamlit Cloud 재시작/재배포 시
  데이터가 유실될 수 있어 Supabase 저장 방식으로 전환함.
==============================================================
"""

from datetime import datetime
import pandas as pd
import streamlit as st
from supabase import create_client

from modules.date_extractor import safe_date_for_db


# ------------------------------------------------------------
# 1. Supabase 연결
# ------------------------------------------------------------
@st.cache_resource
def get_client():
    """Streamlit Secrets에 등록된 Supabase 정보로 클라이언트 생성."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        st.error(
            "Supabase 연결 정보가 없습니다. Streamlit Cloud의 Settings → Secrets에 "
            "SUPABASE_URL, SUPABASE_KEY를 등록해 주세요."
        )
        st.stop()

    return create_client(url, key)


def _client():
    return get_client()


def _to_df(data, columns=None):
    """Supabase 응답(list[dict])을 pandas DataFrame으로 변환."""
    if not data:
        return pd.DataFrame(columns=columns or [])
    df = pd.DataFrame(data)
    if columns:
        for col in columns:
            if col not in df.columns:
                df[col] = None
        df = df[columns]
    return df


ARTICLE_COLUMNS = [
    "id", "collected_date", "published_date", "source", "title", "url",
    "summary", "keywords", "category", "importance", "education_point",
    "memo", "is_favorite"
]

KEYWORD_COLUMNS = [
    "id", "keyword", "keyword_type", "is_active", "created_date",
    "last_collected_date", "article_count", "memo"
]

RECOMMENDED_COLUMNS = [
    "id", "keyword", "occurrence_count", "related_article_count",
    "latest_detected_date", "status", "created_date"
]


# ------------------------------------------------------------
# 2. 초기화
# ------------------------------------------------------------
def init_db():
    """
    Supabase는 SQL Editor에서 테이블을 한 번 생성해두면 됨.
    앱 실행 시 별도 테이블 생성 작업은 하지 않음.
    """
    return


def seed_sample_data():
    """샘플 기사 생성 기능 비활성화."""
    return 0


# ------------------------------------------------------------
# 3. 기사 관련 함수
# ------------------------------------------------------------
def get_article_count():
    """전체 기사 수 반환."""
    res = _client().table("articles").select("id", count="exact").execute()
    return res.count or 0


def get_today_article_count():
    """오늘 수집된 기사 수 반환."""
    today = datetime.now().strftime("%Y-%m-%d")
    res = (
        _client().table("articles")
        .select("id", count="exact")
        .eq("collected_date", today)
        .execute()
    )
    return res.count or 0


def get_articles(
    limit=None, order_by="collected_date DESC, id DESC",
    category=None, importance=None, keyword=None,
    search=None, start_date=None, end_date=None,
    favorite_only=False
):
    """다양한 조건으로 기사 조회. DataFrame 반환."""
    q = _client().table("articles").select("*")

    if category and category != "전체":
        q = q.eq("category", category)
    if importance and importance != "전체":
        q = q.eq("importance", importance)
    if keyword:
        q = q.ilike("keywords", f"%{keyword}%")
    if search:
        safe = str(search).replace(",", " ")
        q = q.or_(
            f"title.ilike.%{safe}%,summary.ilike.%{safe}%,keywords.ilike.%{safe}%"
        )
    if start_date:
        q = q.gte("collected_date", start_date)
    if end_date:
        q = q.lte("collected_date", end_date)
    if favorite_only:
        q = q.eq("is_favorite", True)

    # 기존 SQLite order_by 문자열을 Supabase order 호출로 변환
    order_parts = [p.strip() for p in str(order_by).split(",") if p.strip()]
    for part in order_parts:
        tokens = part.split()
        col = tokens[0]
        desc = len(tokens) > 1 and tokens[1].upper() == "DESC"
        q = q.order(col, desc=desc)

    if limit:
        q = q.limit(int(limit))

    res = q.execute()
    return _to_df(res.data, ARTICLE_COLUMNS)


def get_article_by_id(article_id):
    """단일 기사 조회."""
    res = (
        _client().table("articles")
        .select("*")
        .eq("id", int(article_id))
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def update_article(article_id, **fields):
    """기사 필드 업데이트."""
    if not fields:
        return

    data = dict(fields)
    if "is_favorite" in data:
        data["is_favorite"] = bool(data["is_favorite"])

    _client().table("articles").update(data).eq("id", int(article_id)).execute()


def insert_article(article: dict):
    """기사 1건 추가. 중복 URL은 저장하지 않음."""
    url = article.get("url", "")
    if url:
        existing = (
            _client().table("articles")
            .select("id")
            .eq("url", url)
            .limit(1)
            .execute()
        )
        if existing.data:
            return False

    # published_date: 빈 문자열 대신 None(DB NULL)으로 저장하여 날짜 타입 오류 방지
    raw_pub_date = article.get("published_date") or ""
    safe_pub_date = safe_date_for_db(raw_pub_date)  # None or "YYYY-MM-DD"

    data = {
        "collected_date": article.get("collected_date", datetime.now().strftime("%Y-%m-%d")),
        "published_date": safe_pub_date,
        "source": article.get("source", ""),
        "title": article.get("title", ""),
        "url": url,
        "summary": article.get("summary", ""),
        "keywords": article.get("keywords", ""),
        "category": article.get("category", "기타"),
        "importance": article.get("importance", "보통"),
        "education_point": article.get("education_point", ""),
        "memo": article.get("memo", ""),
        "is_favorite": bool(article.get("is_favorite", False)),
    }

    # date_source 컬럼이 Supabase에 추가된 경우에만 포함
    date_source = article.get("date_source", "")
    if date_source:
        data["date_source"] = date_source

    try:
        _client().table("articles").insert(data).execute()
    except Exception as e:
        # date_source 컬럼이 없는 경우 해당 필드 제거 후 재시도
        if "date_source" in data and "column" in str(e).lower():
            data.pop("date_source", None)
            _client().table("articles").insert(data).execute()
        else:
            raise
    return True


def delete_article(article_id):
    """기사 삭제."""
    _client().table("articles").delete().eq("id", int(article_id)).execute()


# ------------------------------------------------------------
# 4. 키워드 관련 함수
# ------------------------------------------------------------
def get_keywords(active_only=False):
    """키워드 전체 조회."""
    q = _client().table("keywords").select("*")
    if active_only:
        q = q.eq("is_active", True)

    res = q.order("article_count", desc=True).order("id", desc=False).execute()
    return _to_df(res.data, KEYWORD_COLUMNS)


def add_keyword(keyword, keyword_type="일반", memo=""):
    """키워드 추가. 중복 키워드는 False 반환."""
    keyword = (keyword or "").strip()
    if not keyword:
        return False

    existing = (
        _client().table("keywords")
        .select("id")
        .eq("keyword", keyword)
        .limit(1)
        .execute()
    )
    if existing.data:
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    _client().table("keywords").insert({
        "keyword": keyword,
        "keyword_type": keyword_type or "일반",
        "is_active": True,
        "created_date": today,
        "last_collected_date": None,
        "article_count": 0,
        "memo": memo or "",
    }).execute()
    return True


def update_keyword(keyword_id, **fields):
    """키워드 업데이트."""
    if not fields:
        return

    data = dict(fields)
    if "is_active" in data:
        data["is_active"] = bool(data["is_active"])

    _client().table("keywords").update(data).eq("id", int(keyword_id)).execute()


def delete_keyword(keyword_id):
    """키워드 삭제."""
    _client().table("keywords").delete().eq("id", int(keyword_id)).execute()


def refresh_keyword_stats():
    """각 키워드별 기사 수, 마지막 수집일을 재계산."""
    kw_res = _client().table("keywords").select("id, keyword").execute()
    keywords = kw_res.data or []

    for row in keywords:
        kw = row.get("keyword", "")
        if not kw:
            continue

        count_res = (
            _client().table("articles")
            .select("id", count="exact")
            .ilike("keywords", f"%{kw}%")
            .execute()
        )

        last_res = (
            _client().table("articles")
            .select("collected_date")
            .ilike("keywords", f"%{kw}%")
            .order("collected_date", desc=True)
            .limit(1)
            .execute()
        )

        last = None
        if last_res.data:
            last = last_res.data[0].get("collected_date")

        _client().table("keywords").update({
            "article_count": count_res.count or 0,
            "last_collected_date": last
        }).eq("id", int(row["id"])).execute()


# ------------------------------------------------------------
# 5. 추천 키워드 관련 함수
# ------------------------------------------------------------
def get_recommended_keywords(status=None):
    q = _client().table("recommended_keywords").select("*")
    if status:
        q = q.eq("status", status)

    res = q.order("occurrence_count", desc=True).order("id", desc=True).execute()
    return _to_df(res.data, RECOMMENDED_COLUMNS)


def upsert_recommended_keyword(keyword, occurrence_count, related_article_count):
    """추천 키워드 등록 또는 통계 업데이트."""
    keyword = (keyword or "").strip()
    if not keyword:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    existing = (
        _client().table("recommended_keywords")
        .select("*")
        .eq("keyword", keyword)
        .limit(1)
        .execute()
    )

    if existing.data:
        row = existing.data[0]
        if row.get("status") == "rejected":
            return

        _client().table("recommended_keywords").update({
            "occurrence_count": int(occurrence_count or 0),
            "related_article_count": int(related_article_count or 0),
            "latest_detected_date": today,
        }).eq("id", int(row["id"])).execute()
    else:
        _client().table("recommended_keywords").insert({
            "keyword": keyword,
            "occurrence_count": int(occurrence_count or 0),
            "related_article_count": int(related_article_count or 0),
            "latest_detected_date": today,
            "status": "pending",
            "created_date": today,
        }).execute()


def update_recommended_status(rec_id, status):
    """
    추천 키워드 상태 변경.
    approved 처리 시 keywords 테이블로 자동 이동하되, 이미 있으면 중복 등록하지 않음.
    """
    res = (
        _client().table("recommended_keywords")
        .select("keyword")
        .eq("id", int(rec_id))
        .limit(1)
        .execute()
    )
    if not res.data:
        return

    keyword = res.data[0].get("keyword", "")
    _client().table("recommended_keywords").update(
        {"status": status}
    ).eq("id", int(rec_id)).execute()

    if status == "approved" and keyword:
        today = datetime.now().strftime("%Y-%m-%d")
        existing = (
            _client().table("keywords")
            .select("id")
            .eq("keyword", keyword)
            .limit(1)
            .execute()
        )
        if not existing.data:
            _client().table("keywords").insert({
                "keyword": keyword,
                "keyword_type": "추천",
                "is_active": True,
                "created_date": today,
                "last_collected_date": None,
                "article_count": 0,
                "memo": "추천 키워드에서 승인됨",
            }).execute()
