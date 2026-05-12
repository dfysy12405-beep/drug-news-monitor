"""
==============================================================
 데이터베이스 모듈 (database.py)
==============================================================
 - SQLite DB 생성 및 초기화
 - articles / keywords / recommended_keywords 3개 테이블 관리
 - 샘플 데이터 자동 입력
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
    """DB가 없으면 새로 생성하고 테이블 및 샘플 데이터를 초기화."""
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

    # 데이터가 비어있을 때만 샘플 데이터 입력
    if get_article_count() == 0:
        _insert_sample_data()


# ------------------------------------------------------------
# 3. 샘플 데이터 입력
# ------------------------------------------------------------
def _insert_sample_data():
    """프로그램 첫 실행 시 시연용 샘플 기사/키워드를 입력."""

    # ----- 기본 키워드 -----
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

    # ----- 샘플 기사 30건 -----
    sample_articles = [
        {
            "title": "10대 청소년 사이 SNS 통한 마약 거래 급증… 텔레그램 활용 사례 적발",
            "source": "연합뉴스",
            "days_ago": 0,
            "summary": "최근 청소년들이 SNS와 텔레그램을 통해 마약류를 손쉽게 구매하는 사례가 늘고 있다. 경찰은 미성년자 대상 유통 조직 일부를 검거했으며, 학교 예방교육 강화가 시급하다는 지적이 나온다.",
            "keywords": "청소년,SNS,텔레그램,마약유통,예방교육",
            "category": "청소년",
            "importance": "높음",
            "education_point": "청소년 대상 SNS 기반 마약 접근 사례 교육 / 텔레그램 등 비대면 유통 경고 사례로 활용 가능",
        },
        {
            "title": "펜타닐 처방 관리 강화… 식약처, 의료기관 점검 확대",
            "source": "메디컬타임즈",
            "days_ago": 1,
            "summary": "식품의약품안전처가 의료용 마약류 펜타닐의 과다 처방 의심 의료기관을 대상으로 현장 점검을 확대한다. 마약류통합관리시스템 데이터 기반으로 처방 패턴을 분석한다.",
            "keywords": "펜타닐,식약처,의료용마약류,처방관리",
            "category": "정책·법률",
            "importance": "높음",
            "education_point": "의료용 마약류 오남용의 사회적 위험성 / 처방약 관리 제도 변화 안내 자료로 활용",
        },
        {
            "title": "한국마약퇴치운동본부, 전국 중고등학교 찾아가는 예방교육 확대 시행",
            "source": "뉴시스",
            "days_ago": 1,
            "summary": "한국마약퇴치운동본부가 올해 전국 중고등학교를 대상으로 한 찾아가는 예방교육을 작년 대비 30% 확대한다. 강사 양성과정도 함께 운영된다.",
            "keywords": "한국마약퇴치운동본부,예방교육,청소년,강사양성",
            "category": "한국마약퇴치운동본부 관련",
            "importance": "높음",
            "education_point": "본부 사업 홍보 / 강사 양성 안내 / 학교 예방교육 신청 안내에 활용 가능",
        },
        {
            "title": "강원도 춘천서 마약류 유통 일당 검거… 클럽가 중심 유통",
            "source": "강원일보",
            "days_ago": 2,
            "summary": "강원경찰청은 춘천 일대 클럽가를 중심으로 마약류를 유통한 20대 일당 5명을 검거했다고 밝혔다. 압수된 마약류는 시가 1억원 상당이다.",
            "keywords": "강원,춘천,클럽,마약유통,경찰",
            "category": "강원지역 관련",
            "importance": "높음",
            "education_point": "강원 지역 사례 교육 자료 / 클럽·유흥업소 약물 위험성 경고에 활용",
        },
        {
            "title": "ADHD 치료제 오남용 우려… '공부 잘하는 약' 인식 확산",
            "source": "한겨레",
            "days_ago": 2,
            "summary": "수험생 사이에서 ADHD 치료제가 집중력 향상에 도움이 된다는 잘못된 인식이 퍼지면서 오남용 사례가 늘고 있다. 의료계는 처방 없는 복용의 위험성을 경고했다.",
            "keywords": "ADHD,치료제,오남용,수험생,공부잘하는약",
            "category": "예방교육 활용 가능",
            "importance": "보통",
            "education_point": "처방약 오남용 위험성 강조 / 수험생·학부모 대상 교육에 활용",
        },
        {
            "title": "졸피뎀 의존 환자 5년새 1.8배 증가… 수면제 오남용 경각심",
            "source": "동아일보",
            "days_ago": 3,
            "summary": "건강보험심사평가원 자료에 따르면 졸피뎀 등 수면진정제 처방 환자가 지난 5년간 1.8배 증가했다. 장기 복용에 따른 의존성이 사회 문제로 떠오르고 있다.",
            "keywords": "졸피뎀,수면제,의존성,오남용",
            "category": "의료용 마약류",
            "importance": "보통",
            "education_point": "수면제·신경안정제 오남용 사례 / 처방약 관리 필요성 교육에 활용",
        },
        {
            "title": "정부, 마약류 관리법 개정 추진… 처벌 강화 및 재활 지원 확대",
            "source": "조선일보",
            "days_ago": 3,
            "summary": "정부는 마약류 관리법 개정안을 통해 단순 투약자에 대한 재활 치료 연계를 강화하고, 유통 사범에 대한 처벌은 한층 강화할 방침이다.",
            "keywords": "마약류관리법,개정,처벌강화,재활지원",
            "category": "정책·법률",
            "importance": "높음",
            "education_point": "최신 법률 동향 안내 / 처벌·재활 제도 변화 설명 자료로 활용",
        },
        {
            "title": "대학가 합성대마 적발 잇따라… 일명 '허브'로 위장 유통",
            "source": "국민일보",
            "days_ago": 4,
            "summary": "주요 대학가에서 합성대마가 '허브'나 '향료'로 위장돼 유통되는 사례가 잇따라 적발됐다. 외형이 일반 식물과 유사해 적발이 어렵다는 지적이다.",
            "keywords": "합성대마,대학가,허브위장,신종마약",
            "category": "사건·사고",
            "importance": "보통",
            "education_point": "신종 마약 사례 / 대학생 대상 위장 유통 경고에 활용",
        },
        {
            "title": "강원지역 마약사범 전년比 25% 증가… 도내 첫 마약전담수사팀 운영",
            "source": "강원도민일보",
            "days_ago": 4,
            "summary": "강원경찰청은 도내 마약사범이 전년 대비 25% 증가했다고 발표하고, 도내 첫 마약전담수사팀을 신설해 본격 운영에 들어간다고 밝혔다.",
            "keywords": "강원,마약사범,전담수사팀,경찰",
            "category": "강원지역 관련",
            "importance": "높음",
            "education_point": "지역 통계 자료 / 강원도 내 예방교육 필요성 강조에 활용",
        },
        {
            "title": "마약 예방 캠페인 '노 엑시트(NO EXIT)' 전국 확산",
            "source": "헬스조선",
            "days_ago": 5,
            "summary": "한국마약퇴치운동본부와 경찰청이 공동 추진하는 청소년 마약 예방 캠페인 '노 엑시트'가 전국 학교로 확산되고 있다.",
            "keywords": "노엑시트,캠페인,청소년,한국마약퇴치운동본부,예방교육",
            "category": "한국마약퇴치운동본부 관련",
            "importance": "높음",
            "education_point": "캠페인 소개 자료 / 학교·지역사회 협력 모델 안내에 활용",
        },
        {
            "title": "전자담배형 대마 '액상대마' SNS 통해 청소년에게 유통",
            "source": "SBS",
            "days_ago": 5,
            "summary": "전자담배 형태의 액상대마가 SNS를 통해 청소년에게 판매되는 사례가 확인됐다. 외형이 일반 전자담배와 동일해 단속이 쉽지 않은 상황이다.",
            "keywords": "액상대마,전자담배,청소년,SNS,신종마약",
            "category": "청소년",
            "importance": "높음",
            "education_point": "전자담배 위장 약물 사례 / 청소년 대상 위험성 경고 교육에 활용",
        },
        {
            "title": "의료용 마약류 처방 1위 '프로포폴'… 미용업계 오남용 적발",
            "source": "메디게이트뉴스",
            "days_ago": 6,
            "summary": "의료용 마약류 중 프로포폴 처방 건수가 가장 많은 가운데, 일부 미용시술 의료기관의 오남용 사례가 적발됐다.",
            "keywords": "프로포폴,의료용마약류,미용,오남용",
            "category": "의료용 마약류",
            "importance": "보통",
            "education_point": "의료용 마약류 오남용 실태 / 의료기관 종사자 교육 자료로 활용",
        },
        {
            "title": "대마 젤리·초콜릿 등 식품 위장 신종마약 적발 증가",
            "source": "YTN",
            "days_ago": 6,
            "summary": "관세청은 대마 성분이 포함된 젤리·초콜릿 등 식품 위장 신종마약의 통관 적발이 작년 대비 2배 늘었다고 밝혔다.",
            "keywords": "대마젤리,신종마약,식품위장,관세청",
            "category": "사건·사고",
            "importance": "높음",
            "education_point": "식품 위장 마약 사례 / 외국산 식품 구매 시 주의사항 교육에 활용",
        },
        {
            "title": "춘천 시민단체, 마약 예방 거리 캠페인 전개",
            "source": "춘천MBC",
            "days_ago": 7,
            "summary": "춘천 지역 시민단체가 명동 일대에서 마약 예방 거리 캠페인을 전개했다. 한국마약퇴치운동본부 강원지부도 함께 참여했다.",
            "keywords": "춘천,캠페인,한국마약퇴치운동본부,강원,예방교육",
            "category": "강원지역 관련",
            "importance": "보통",
            "education_point": "지역 캠페인 사례 / 지역사회 연계 활동 안내에 활용",
        },
        {
            "title": "마약 재범률 35%… 재활 인프라 확충 시급",
            "source": "경향신문",
            "days_ago": 8,
            "summary": "마약사범 재범률이 35%에 달하지만 전국 재활시설은 부족한 실정이다. 전문가들은 치료·재활 인프라 확충이 시급하다고 지적했다.",
            "keywords": "재범률,재활시설,인프라,치료",
            "category": "정책·법률",
            "importance": "보통",
            "education_point": "재활 제도 안내 / 재범 방지 교육 자료로 활용",
        },
        {
            "title": "마약류 예방교육 강사 양성과정 모집 시작",
            "source": "메디파나뉴스",
            "days_ago": 9,
            "summary": "한국마약퇴치운동본부가 마약류 예방교육 전문강사 양성과정 수강생을 모집한다. 교육 이수 후 학교·기업 강의에 투입될 예정이다.",
            "keywords": "강사양성,예방교육,한국마약퇴치운동본부,수강생모집",
            "category": "한국마약퇴치운동본부 관련",
            "importance": "높음",
            "education_point": "강사 양성 사업 홍보 / 신규 강사 모집 안내에 활용",
        },
        {
            "title": "초등학생 대상 마약 호기심 조사… '안전하다' 응답 12%",
            "source": "KBS",
            "days_ago": 10,
            "summary": "초등학생 대상 설문조사에서 마약이 안전하다고 응답한 비율이 12%로 나타났다. 조기 예방교육의 필요성이 다시 강조됐다.",
            "keywords": "초등학생,설문조사,예방교육,청소년",
            "category": "청소년",
            "importance": "높음",
            "education_point": "조기 예방교육 필요성 / 초등 대상 교육 콘텐츠 개발 근거 자료",
        },
        {
            "title": "마약류 통합관리시스템 고도화… AI 기반 이상처방 탐지",
            "source": "디지털타임스",
            "days_ago": 11,
            "summary": "식약처는 마약류통합관리시스템(NIMS)에 AI 기반 이상처방 탐지 기능을 도입한다. 의료기관별 처방 패턴을 자동 분석한다.",
            "keywords": "NIMS,AI,이상처방,식약처,의료용마약류",
            "category": "정책·법률",
            "importance": "보통",
            "education_point": "디지털 기반 마약류 관리 정책 / 의료기관 종사자 안내 자료",
        },
        {
            "title": "원주 클럽 일대 마약 단속… 4명 현장 검거",
            "source": "강원일보",
            "days_ago": 12,
            "summary": "원주 시내 일부 클럽에서 마약을 투약·유통한 혐의로 4명이 현장 검거됐다. 압수품에는 MDMA와 케타민이 포함됐다.",
            "keywords": "원주,클럽,MDMA,케타민,강원",
            "category": "강원지역 관련",
            "importance": "보통",
            "education_point": "강원 클럽가 사례 / 향정신성 약물 위험성 교육에 활용",
        },
        {
            "title": "한국마약퇴치운동본부 강원지부, 학부모 대상 교육 프로그램 신설",
            "source": "강원도민일보",
            "days_ago": 13,
            "summary": "한국마약퇴치운동본부 강원지부는 학부모 대상 마약 예방교육 프로그램을 신설한다. 자녀의 이상 징후 관찰법 등이 포함된다.",
            "keywords": "한국마약퇴치운동본부,강원,학부모,예방교육",
            "category": "한국마약퇴치운동본부 관련",
            "importance": "높음",
            "education_point": "학부모 교육 사업 홍보 / 가정 내 예방 활동 안내에 활용",
        },
        {
            "title": "마약성 진통제 옥시코돈 처방 5년새 40% 증가",
            "source": "메디컬옵저버",
            "days_ago": 14,
            "summary": "마약성 진통제 옥시코돈의 처방 건수가 5년새 40% 증가한 것으로 나타났다. 미국 오피오이드 사태와 비교하며 우려가 제기된다.",
            "keywords": "옥시코돈,마약성진통제,처방,오피오이드",
            "category": "의료용 마약류",
            "importance": "보통",
            "education_point": "마약성 진통제 위험성 / 미국 사례 비교 교육에 활용",
        },
        {
            "title": "청소년 마약 검거 작년比 50% 증가… 10대 비중 확대",
            "source": "MBC",
            "days_ago": 15,
            "summary": "10대 청소년 마약사범 검거 건수가 작년 같은 기간 대비 50% 증가했다. 다크웹·SNS 등을 통한 접근이 주된 경로다.",
            "keywords": "청소년,10대,마약사범,SNS,다크웹",
            "category": "청소년",
            "importance": "높음",
            "education_point": "최신 청소년 통계 / 디지털 환경 위험성 교육 자료",
        },
        {
            "title": "강원도, 마약류 예방교육 예산 확대 편성",
            "source": "강원일보",
            "days_ago": 17,
            "summary": "강원도는 내년도 마약류 예방교육 예산을 올해 대비 60% 확대 편성한다고 밝혔다. 학교·지역사회 교육이 중점 추진된다.",
            "keywords": "강원,예산,예방교육,지자체",
            "category": "강원지역 관련",
            "importance": "보통",
            "education_point": "지자체 예방교육 정책 / 강원지역 사업 안내 자료",
        },
        {
            "title": "마약 중독 재활시설 운영 인력난 심각… 전문가 양성 필요",
            "source": "한국일보",
            "days_ago": 19,
            "summary": "마약 중독 재활시설들이 전문 운영 인력 부족으로 어려움을 겪고 있다. 의료·심리·사회복지 통합 전문가 양성이 시급하다는 지적이다.",
            "keywords": "재활시설,인력난,전문가양성",
            "category": "정책·법률",
            "importance": "낮음",
            "education_point": "재활 인프라 현황 / 관련 직업·진로 안내에 활용",
        },
        {
            "title": "유튜브에 마약 후기 영상 다수… 플랫폼 책임론 부상",
            "source": "한겨레",
            "days_ago": 20,
            "summary": "유튜브 등 동영상 플랫폼에 마약 후기성 영상이 다수 게시돼 청소년 노출 위험이 제기되고 있다. 플랫폼의 적극적 모니터링이 요구된다.",
            "keywords": "유튜브,플랫폼,청소년,SNS",
            "category": "청소년",
            "importance": "보통",
            "education_point": "디지털 콘텐츠 위험성 / 미디어 리터러시 교육에 활용",
        },
        {
            "title": "마약류 광고 SNS 차단 강화… 방심위, 모니터링 확대",
            "source": "전자신문",
            "days_ago": 22,
            "summary": "방송통신심의위원회는 SNS상 마약류 거래 광고에 대한 모니터링을 확대하고 신속 차단 체계를 구축한다.",
            "keywords": "SNS,광고,방심위,모니터링",
            "category": "정책·법률",
            "importance": "보통",
            "education_point": "온라인 유통 차단 정책 / 신고 절차 안내에 활용",
        },
        {
            "title": "병원 내 의료용 마약류 도난 사건… 관리 부실 도마",
            "source": "청년의사",
            "days_ago": 24,
            "summary": "수도권 한 종합병원에서 의료용 마약류가 도난당하는 사건이 발생했다. 병원 내 약품 관리 시스템의 허점이 드러났다.",
            "keywords": "의료용마약류,도난,병원,관리부실",
            "category": "의료용 마약류",
            "importance": "보통",
            "education_point": "의료기관 관리 책임 / 약품 보관 교육 자료로 활용",
        },
        {
            "title": "한국마약퇴치운동본부, 2025년 예방교육 콘텐츠 전면 개편",
            "source": "데일리메디",
            "days_ago": 26,
            "summary": "한국마약퇴치운동본부는 2025년부터 청소년·성인·노인 대상 맞춤형 예방교육 콘텐츠를 전면 개편 운영한다.",
            "keywords": "한국마약퇴치운동본부,예방교육,콘텐츠개편,맞춤형",
            "category": "한국마약퇴치운동본부 관련",
            "importance": "높음",
            "education_point": "신규 교육 콘텐츠 안내 / 강사 대상 정보 공유에 활용",
        },
        {
            "title": "마약 예방 뮤지컬 전국 순회… 청소년 호응 높아",
            "source": "문화일보",
            "days_ago": 28,
            "summary": "청소년 대상 마약 예방 뮤지컬이 전국 순회 공연을 시작했다. 한국마약퇴치운동본부와 문화예술단체가 공동 제작했다.",
            "keywords": "뮤지컬,청소년,한국마약퇴치운동본부,캠페인,예방교육",
            "category": "한국마약퇴치운동본부 관련",
            "importance": "보통",
            "education_point": "문화 예술 활용 예방교육 사례 / 학교 단체관람 안내에 활용",
        },
        {
            "title": "대마 합법화 논의 재점화… 의료용 한정 도입 주장도",
            "source": "중앙일보",
            "days_ago": 29,
            "summary": "일부 국가의 대마 합법화 흐름 속에 국내에서도 의료용 한정 도입 주장이 다시 제기되고 있다. 다만 사회적 합의 필요성도 강조된다.",
            "keywords": "대마,합법화,의료용,사회논의",
            "category": "정책·법률",
            "importance": "낮음",
            "education_point": "국제 동향 / 사회 논쟁점 토론식 교육 자료로 활용",
        },
    ]

    today_dt = datetime.now()
    rows = []
    for i, art in enumerate(sample_articles):
        pub_date = (today_dt - timedelta(days=art["days_ago"])).strftime("%Y-%m-%d")
        col_date = (today_dt - timedelta(days=max(art["days_ago"] - 1, 0))).strftime("%Y-%m-%d")
        url = f"https://example.com/news/sample-{i+1}"
        rows.append((
            col_date, pub_date, art["source"], art["title"], url,
            art["summary"], art["keywords"], art["category"],
            art["importance"], art["education_point"], "", 0
        ))

    with get_conn() as conn:
        cur = conn.cursor()
        cur.executemany("""
            INSERT OR IGNORE INTO articles
            (collected_date, published_date, source, title, url, summary,
             keywords, category, importance, education_point, memo, is_favorite)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

    # 키워드 통계 업데이트
    refresh_keyword_stats()


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
