"""
==============================================================
 AI 헬퍼 모듈 (ai_helper.py)
==============================================================
 - OpenAI API 사용 가능 시: GPT 호출
 - API 키 없을 때: 규칙 기반(rule-based) 폴백 자동 동작

 ★ OpenAI API 키 연결 위치:
   - Streamlit Cloud 배포 시: Settings → Secrets 에
     OPENAI_API_KEY = "sk-xxxxx" 형식으로 입력
   - 로컬 실행 시: .streamlit/secrets.toml 파일에 동일하게 입력
   - 또는 환경변수 OPENAI_API_KEY 로도 인식됨
==============================================================
"""

import os
import re
from collections import Counter

# Streamlit secrets 안전하게 시도
try:
    import streamlit as st
    _has_st = True
except Exception:
    _has_st = False


# ------------------------------------------------------------
# API 키 가져오기
# ------------------------------------------------------------
def _get_api_key():
    """OpenAI API 키를 Streamlit secrets 또는 환경변수에서 가져옴."""
    if _has_st:
        try:
            return st.secrets.get("OPENAI_API_KEY", None)
        except Exception:
            pass
    return os.environ.get("OPENAI_API_KEY")


def is_ai_enabled():
    """OpenAI API 키가 등록돼 있는지 확인."""
    return bool(_get_api_key())


# ------------------------------------------------------------
# 카테고리 / 중요도 룰 정의 (규칙 기반 폴백용)
# ------------------------------------------------------------
CATEGORY_RULES = [
    ("사건·사고", ["검거", "체포", "적발", "압수", "사망", "단속", "수사"]),
    ("정책·법률", ["정책", "법률", "법안", "개정", "정부", "식약처", "경찰청", "처벌", "예산", "심의위"]),
    ("청소년", ["청소년", "10대", "학생", "초등", "중학", "고등", "수험생", "학교"]),
    ("의료용 마약류", ["펜타닐", "프로포폴", "옥시코돈", "졸피뎀", "처방", "의료용", "병원", "약국"]),
    ("한국마약퇴치운동본부 관련", ["한국마약퇴치운동본부", "마퇴", "노엑시트"]),
    ("강원지역 관련", ["강원", "춘천", "원주", "강릉", "속초", "동해", "삼척"]),
    ("예방교육 활용 가능", ["예방교육", "캠페인", "강사", "교육 자료", "사례교육"]),
]

IMPORTANCE_RULES = {
    "높음": ["청소년", "사망", "긴급", "10대", "한국마약퇴치운동본부", "예방교육", "강원", "펜타닐", "급증", "확대"],
    "낮음": ["논의", "의견", "기고", "칼럼", "전망"],
}

# 일반어 제외 (추천 키워드 추출 시 제외)
STOPWORDS = set([
    "이", "그", "저", "것", "수", "등", "및", "들", "의", "에", "은", "는", "이다", "다",
    "있다", "없다", "하다", "한다", "있다", "관련", "위한", "위해", "통해", "대한",
    "기자", "오늘", "어제", "내일", "올해", "작년", "지난", "최근", "이번", "다음",
    "기사", "보도", "발표", "공개", "지적", "강조", "확인", "조사", "발생", "출현",
    "사용", "포함", "이상", "이하", "이후", "이전", "동안", "이상에", "한편",
    "기록", "전망", "예상", "추진", "운영", "시작", "종료", "마무리", "진행",
    "마약", "약물", "기관", "전국", "지역", "사업", "사회", "사람", "정도", "경우",
    "분야", "수준", "방안", "방법", "필요", "가능", "확대", "증가", "감소",
])


# ------------------------------------------------------------
# 1. 기사 요약 (3줄)
# ------------------------------------------------------------
def summarize_article(title: str, content: str) -> str:
    """기사 본문에서 핵심 3줄 요약 생성."""
    if is_ai_enabled():
        try:
            return _gpt_summarize(title, content)
        except Exception as e:
            print(f"[AI 요약 실패, 룰 기반으로 대체] {e}")

    # 규칙 기반 폴백: 첫 3문장 추출
    if not content:
        return title
    sentences = re.split(r"(?<=[.!?。])\s+", content.strip())
    summary = " ".join(sentences[:3])
    return summary[:300]


def _gpt_summarize(title, content):
    """OpenAI GPT 기반 요약."""
    from openai import OpenAI
    client = OpenAI(api_key=_get_api_key())

    prompt = f"""다음 기사를 3줄 이내로 요약해주세요. 반드시 제공된 제목과 본문에 있는 사실만 사용하고, 원문에 없는 수치·기관명·사건 내용은 절대 추가하지 마세요.

[제목]
{title}

[본문]
{content[:3000]}

[요약 규칙]
- 한국어 3문장 이내
- 핵심 사실 위주
- 원문에 명시되지 않은 해석, 추정, 배경 설명 금지
- 본문 정보가 부족하면 "본문 정보 부족: 제목 기준 확인 필요"라고 표시"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 마약류 예방사업 담당 분석가입니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
    )
    return res.choices[0].message.content.strip()


# ------------------------------------------------------------
# 2. 핵심 키워드 추출
# ------------------------------------------------------------
def extract_keywords(title: str, content: str, registered_keywords: list = None) -> list:
    """등록된 키워드 + 본문 빈출 단어 기준으로 핵심 키워드 추출."""
    text = f"{title} {content}"
    found = []

    # 1) 등록된 키워드 매칭
    if registered_keywords:
        for kw in registered_keywords:
            if kw and kw in text:
                found.append(kw)

    # 2) 본문 기반 보조 키워드 추출 (2글자 이상 한글 명사 추정)
    words = re.findall(r"[가-힣]{2,}", text)
    counter = Counter([w for w in words if w not in STOPWORDS])
    for word, cnt in counter.most_common(20):
        if cnt >= 2 and word not in found:
            found.append(word)
        if len(found) >= 8:
            break

    return found[:8]


# ------------------------------------------------------------
# 3. 기사 카테고리 분류
# ------------------------------------------------------------
def classify_category(title: str, content: str) -> str:
    """기사 분류."""
    text = f"{title} {content}"
    scores = {}
    for cat, keywords in CATEGORY_RULES:
        score = sum(text.count(k) for k in keywords)
        if score > 0:
            scores[cat] = score
    if not scores:
        return "기타"
    return max(scores, key=scores.get)


# ------------------------------------------------------------
# 4. 중요도 분류 (높음 / 보통 / 낮음)
# ------------------------------------------------------------
def classify_importance(title: str, content: str) -> str:
    """중요도 자동 산정."""
    text = f"{title} {content}"
    high_score = sum(text.count(k) for k in IMPORTANCE_RULES["높음"])
    low_score = sum(text.count(k) for k in IMPORTANCE_RULES["낮음"])

    if high_score >= 2:
        return "높음"
    if low_score >= 2 and high_score == 0:
        return "낮음"
    return "보통"


# ------------------------------------------------------------
# 5. 예방교육 활용 포인트 생성
# ------------------------------------------------------------
def generate_education_point(title: str, content: str, category: str) -> str:
    """예방교육 활용 포인트 생성 (규칙 기반)."""
    if is_ai_enabled():
        try:
            return _gpt_education_point(title, content, category)
        except Exception as e:
            print(f"[AI 활용 포인트 실패, 룰 기반으로 대체] {e}")

    templates = {
        "청소년": "청소년 대상 사례교육 활용 가능 / SNS·디지털 환경 기반 약물 접근 위험성 경고",
        "의료용 마약류": "처방약 오남용 위험성 설명 / 의료기관 종사자·환자 대상 교육 자료",
        "정책·법률": "최신 법률·정책 변화 안내 / 처벌·재활 제도 변화 설명 자료",
        "한국마약퇴치운동본부 관련": "본부 사업 홍보 / 강사·교육생 안내 자료로 활용",
        "강원지역 관련": "강원 지역 사례 교육 자료 / 지역사회 협력 안내",
        "사건·사고": "실제 사건 사례 / 위험성 경고 교육 자료",
        "예방교육 활용 가능": "교육 콘텐츠 직접 활용 가능 / 학교·기업 교육 자료로 인용",
    }
    return templates.get(category, "관련 사례 교육 자료로 활용 가능")


def _gpt_education_point(title, content, category):
    from openai import OpenAI
    client = OpenAI(api_key=_get_api_key())

    prompt = f"""다음 기사 내용을 바탕으로 예방교육 활용 가능성을 2~3줄로 정리해주세요. 반드시 제공된 기사 내용에서 확인되는 범위 안에서만 작성하고, 확인되지 않은 사실은 추가하지 마세요.

[기사 제목] {title}
[분류] {category}
[내용 요약] {content[:1500]}

규칙:
- 교육 대상(청소년/성인/노인/학부모 등) 지정
- 어떤 메시지 전달에 활용 가능한지 명시
- 기사에 없는 사실·수치·기관명 추가 금지
- 정보가 부족하면 "본문 확인 후 활용 필요"라고 표시
- 한국어 2~3문장"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 마약류 예방교육 콘텐츠 개발자입니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
    )
    return res.choices[0].message.content.strip()


# ------------------------------------------------------------
# 6. 통합 분석 (한 번에 모든 AI 처리)
# ------------------------------------------------------------
def analyze_article(title: str, content: str, registered_keywords: list = None) -> dict:
    """기사 1건을 받아 모든 AI 분석 결과를 반환."""
    category = classify_category(title, content)
    importance = classify_importance(title, content)
    summary = summarize_article(title, content)
    keywords = extract_keywords(title, content, registered_keywords)
    edu_point = generate_education_point(title, content, category)

    return {
        "summary": summary,
        "keywords": ",".join(keywords),
        "category": category,
        "importance": importance,
        "education_point": edu_point,
    }
