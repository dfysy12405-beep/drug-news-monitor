"""
==============================================================
 데이터베이스 모듈 (database.py)
==============================================================
 - SQLite DB 생성 및 초기화
 - articles / keywords / recommended_keywords 3개 테이블 관리
 - 기본 키워드 자동 입력
 - 기사/키워드 CRUD 함수 제공
==============================================================
"""

import sqlite3
import os
from datetime import datetime, timedelta
from contextlib import contextmanager
import pandas as pd

# DB 파일 경로 (data 폴더 안에 저장)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "monitor.db")


# ------------------------------------------------------------
# 1. DB 연결 헬퍼 (with 문으로 안전하게 사용)
# ------------------------------------------------------------
@contextmanager
def get_conn():
    """SQLite 연결을 자동으로 열고 닫는 컨텍스트 매니저."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # dict 형태로 조회 가능
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------
# 2. 테이블 생성
# ------------------------------------------------------------
def init_db():
    """DB가 없으면 새로 생성하고 테이블 및 기본 키워드를 초기화."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with get_conn() as conn:
        cur = conn.cursor()

        # 기사 테이블
        cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collected_date TEXT NOT NULL,
                published_date TEXT,
                source TEXT,
                title TEXT NOT NULL,
                url TEXT UNIQUE,
                summary TEXT,
                keywords TEXT,
                category TEXT,
                importance TEXT DEFAULT '보통',
                education_point TEXT,
                memo TEXT,
                is_favorite INTEGER DEFAULT 0
            )
        """)

        # 키워드 테이블
        cur.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT UNIQUE NOT NULL,
                keyword_type TEXT DEFAULT '일반',
                is_active INTEGER DEFAULT 1,
                created_date TEXT,
                last_collected_date TEXT,
                article_count INTEGER DEFAULT 0,
                memo TEXT
            )
        """)

        # 추천 키워드 테이블
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recommended_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT UNIQUE NOT NULL,
                occurrence_count INTEGER DEFAULT 0,
                related_article_count INTEGER DEFAULT 0,
                latest_detected_date TEXT,
                status TEXT DEFAULT 'pending',
                created_date TEXT
            )
        """)

        # 검색 속도 향상을 위한 인덱스
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(collected_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_importance ON articles(importance)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category)")

    # 첫 실행 시 기본 키워드만 입력한다.
    _insert_default_keywords()


# ------------------------------------------------------------
# 3. 기본 키워드 입력
# ------------------------------------------------------------
def _insert_default_keywords():
    """프로그램 첫 실행 시 기본 검색 키워드만 입력.

    주의: 실제 기사처럼 보이는 샘플 데이터는 입력하지 않는다.
    기사 테이블에는 RSS 수집, CSV 업로드, 수동 등록으로 확인된 기사만 저장한다.
    """
    default_keywords = [
        ("마약", "핵심"),
        ("한국마약퇴치운동본부", "기관"),
        ("약물 오남용", "핵심"),
        ("청소년 마약", "대상"),
        ("펜타닐", "약물"),
        ("의료용 마약류", "분야"),
        ("예방교육", "사업"),
        ("강원 마약", "지역"),
    ]
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        cur = conn.cursor()
        for kw, ktype in default_keywords:
            cur.execute("""
                INSERT OR IGNORE INTO keywords (keyword, keyword_type, is_active, created_date)
                VALUES (?, ?, 1, ?)
            """, (kw, ktype, today))


def seed_sample_data():
    """샘플 기사 생성 기능은 비활성화.

    기존 버전의 시연용 샘플 기사 때문에 실제 기사와 혼동될 수 있어
    더 이상 샘플 기사를 생성하지 않는다.
    """
    return 0


# ------------------------------------------------------------
# 4. 기사 관련 함수
# ------------------------------------------------------------
def get_article_count():
    """전체 기사 수 반환."""
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]


def get_today_article_count():
    """오늘 수집된 기사 수 반환."""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM articles WHERE collected_date = ?", (today,)
        ).fetchone()[0]


def get_articles(
    limit=None, order_by="collected_date DESC, id DESC",
    category=None, importance=None, keyword=None,
    search=None, start_date=None, end_date=None,
    favorite_only=False
):
    """다양한 조건으로 기사 조회. DataFrame 반환."""
    query = "SELECT * FROM articles WHERE 1=1"
    params = []

    if category and category != "전체":
        query += " AND category = ?"
        params.append(category)
    if importance and importance != "전체":
        query += " AND importance = ?"
        params.append(importance)
    if keyword:
        query += " AND keywords LIKE ?"
        params.append(f"%{keyword}%")
    if search:
        query += " AND (title LIKE ? OR summary LIKE ? OR keywords LIKE ?)"
        params.extend([f"%{search}%"] * 3)
    if start_date:
        query += " AND collected_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND collected_date <= ?"
        params.append(end_date)
    if favorite_only:
        query += " AND is_favorite = 1"

    query += f" ORDER BY {order_by}"
    if limit:
        query += f" LIMIT {int(limit)}"

    with get_conn() as conn:
        df = pd.read_sql_query(query, conn, params=params)
    return df


def get_article_by_id(article_id):
    """단일 기사 조회."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
        return dict(row) if row else None


def update_article(article_id, **fields):
    """기사 필드 업데이트."""
    if not fields:
        return
    set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
    params = list(fields.values()) + [article_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE articles SET {set_clause} WHERE id = ?", params)


def insert_article(article: dict):
    """기사 1건 추가. 중복 URL은 무시."""
    with get_conn() as conn:
        try:
            conn.execute("""
                INSERT INTO articles
                (collected_date, published_date, source, title, url, summary,
                 keywords, category, importance, education_point, memo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.get("collected_date", datetime.now().strftime("%Y-%m-%d")),
                article.get("published_date", datetime.now().strftime("%Y-%m-%d")),
                article.get("source", ""),
                article.get("title", ""),
                article.get("url", ""),
                article.get("summary", ""),
                article.get("keywords", ""),
                article.get("category", "기타"),
                article.get("importance", "보통"),
                article.get("education_point", ""),
                article.get("memo", ""),
            ))
            return True
        except sqlite3.IntegrityError:
            return False  # 중복 URL


def delete_article(article_id):
    """기사 삭제."""
    with get_conn() as conn:
        conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))


# ------------------------------------------------------------
# 5. 키워드 관련 함수
# ------------------------------------------------------------
def get_keywords(active_only=False):
    """키워드 전체 조회."""
    query = "SELECT * FROM keywords"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY article_count DESC, id ASC"
    with get_conn() as conn:
        return pd.read_sql_query(query, conn)


def add_keyword(keyword, keyword_type="일반", memo=""):
    """키워드 추가."""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        try:
            conn.execute("""
                INSERT INTO keywords (keyword, keyword_type, is_active, created_date, memo)
                VALUES (?, ?, 1, ?, ?)
            """, (keyword, keyword_type, today, memo))
            return True
        except sqlite3.IntegrityError:
            return False


def update_keyword(keyword_id, **fields):
    """키워드 업데이트."""
    if not fields:
        return
    set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
    params = list(fields.values()) + [keyword_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE keywords SET {set_clause} WHERE id = ?", params)


def delete_keyword(keyword_id):
    """키워드 삭제."""
    with get_conn() as conn:
        conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))


def refresh_keyword_stats():
    """각 키워드별 기사 수, 마지막 수집일을 재계산."""
    with get_conn() as conn:
        kws = conn.execute("SELECT id, keyword FROM keywords").fetchall()
        for row in kws:
            count = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE keywords LIKE ?",
                (f"%{row['keyword']}%",)
            ).fetchone()[0]
            last = conn.execute(
                "SELECT MAX(collected_date) FROM articles WHERE keywords LIKE ?",
                (f"%{row['keyword']}%",)
            ).fetchone()[0]
            conn.execute(
                "UPDATE keywords SET article_count = ?, last_collected_date = ? WHERE id = ?",
                (count, last, row["id"])
            )


# ------------------------------------------------------------
# 6. 추천 키워드 관련 함수
# ------------------------------------------------------------
def get_recommended_keywords(status=None):
    query = "SELECT * FROM recommended_keywords"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY occurrence_count DESC, id DESC"
    with get_conn() as conn:
        return pd.read_sql_query(query, conn, params=params)


def upsert_recommended_keyword(keyword, occurrence_count, related_article_count):
    """추천 키워드 등록 또는 통계 업데이트."""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, status FROM recommended_keywords WHERE keyword = ?", (keyword,)
        ).fetchone()
        if existing:
            # 거절된 키워드는 다시 등록하지 않음
            if existing["status"] == "rejected":
                return
            conn.execute("""
                UPDATE recommended_keywords
                SET occurrence_count = ?, related_article_count = ?, latest_detected_date = ?
                WHERE id = ?
            """, (occurrence_count, related_article_count, today, existing["id"]))
        else:
            conn.execute("""
                INSERT INTO recommended_keywords
                (keyword, occurrence_count, related_article_count, latest_detected_date,
                 status, created_date)
                VALUES (?, ?, ?, ?, 'pending', ?)
            """, (keyword, occurrence_count, related_article_count, today, today))


def update_recommended_status(rec_id, status):
    """추천 키워드 상태 변경 (pending/approved/rejected).
    approved 처리 시 keywords 테이블로 자동 이동."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT keyword FROM recommended_keywords WHERE id = ?", (rec_id,)
        ).fetchone()
        if not row:
            return
        conn.execute(
            "UPDATE recommended_keywords SET status = ? WHERE id = ?",
            (status, rec_id)
        )
        if status == "approved":
            today = datetime.now().strftime("%Y-%m-%d")
            try:
                conn.execute("""
                    INSERT INTO keywords (keyword, keyword_type, is_active, created_date, memo)
                    VALUES (?, '추천', 1, ?, '추천 키워드에서 승인됨')
                """, (row["keyword"], today))
            except sqlite3.IntegrityError:
                pass  # 이미 존재
