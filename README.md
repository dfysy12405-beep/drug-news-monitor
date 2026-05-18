# Drug News Monitor - 가짜뉴스 생성 방지 수정본

이 수정본은 기존 Streamlit Cloud 배포 구조를 유지하면서, 실제 기사처럼 보이는 샘플 기사 자동 생성 기능을 제거한 버전입니다. RSS 수집, CSV 업로드, 수동 등록으로 확인된 기사만 저장됩니다.

# 📰 마약류 언론동향 모니터링 시스템

> AI 기반 마약류 예방사업 언론동향 관리 플랫폼
> 공공기관 내부 업무용 · Streamlit 기반 웹앱

팀원이 **링크 하나로 접속**해서 마약류·약물 오남용 관련 언론 동향을
검색·분석·브리핑할 수 있는 내부 모니터링 시스템입니다.

---

## ✨ 주요 기능

| 영역 | 기능 |
|---|---|
| 📊 대시보드 | KPI 4종, 오늘의 핵심 기사 TOP5, 키워드·분류 통계, 7일 추이 |
| 📰 전체 기사 | 검색·필터(분류/중요도/키워드/기간/즐겨찾기), 카드/표 보기, CSV 내려받기, 상세보기, 수정·삭제 |
| 🏷️ 키워드 관리 | 추가/수정/삭제/활성화 토글, 키워드별 기사 수·최근 수집일 |
| 💡 추천 키워드 | 누적 기사 자동 분석 → 신규 키워드 추천 → **승인해야만** 정식 등록 |
| 📥 기사 수집 | RSS(Google News) 자동 수집 · CSV 업로드 · 수동 등록 |
| 📋 주간 브리핑 | 최근 7일 기사 자동 요약 보고서, 강사 공유용 텍스트 다운로드 |
| 🤖 AI 분석 | 3줄 요약, 핵심 키워드, 카테고리, 중요도, 예방교육 활용 포인트 자동 생성 |

> **💡 OpenAI API 키가 없어도 동작합니다.** 규칙 기반 폴백이 내장되어 있어, 키 없이도 모든 AI 기능이 작동합니다. 키를 등록하면 GPT-4o-mini 기반의 더 정교한 결과로 자동 전환됩니다.

---

## 📂 폴더 구조

```
drug-news-monitor/
├── app.py                        # 메인 대시보드 (Streamlit 진입점)
├── requirements.txt              # 필요 패키지
├── README.md                     # 이 문서
├── .gitignore                    # Git 제외 파일
│
├── .streamlit/
│   ├── config.toml               # 테마 설정
│   └── secrets.toml.example      # API 키 등록 예시
│
├── pages/                        # 사이드바 자동 노출 페이지
│   ├── 1_📰_전체기사.py
│   ├── 2_🏷️_키워드관리.py
│   ├── 3_💡_추천키워드.py
│   ├── 4_📥_기사수집.py
│   └── 5_📋_주간브리핑.py
│
├── modules/                      # 핵심 로직
│   ├── __init__.py
│   ├── database.py               # SQLite + 기본 키워드 + CRUD
│   ├── ai_helper.py              # AI(GPT)/규칙 기반 분석
│   ├── rss_collector.py          # Google News RSS 수집
│   ├── analyzer.py               # 추천 키워드 분석, 트렌드
│   └── utils.py                  # 공통 UI 헬퍼 (배지/태그/카드)
│
└── data/
    └── monitor.db                # SQLite DB (앱 실행 시 자동 생성)
```

---

## 🗄️ 데이터베이스 구조 (SQLite)

### articles
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | 자동 증가 |
| collected_date | TEXT | 수집일자 |
| published_date | TEXT | 발행일자 |
| source | TEXT | 언론사 |
| title | TEXT | 기사 제목 |
| url | TEXT UNIQUE | 원문 링크 |
| summary | TEXT | AI 3줄 요약 |
| keywords | TEXT | 핵심 키워드 (쉼표 구분) |
| category | TEXT | 분류 |
| importance | TEXT | 중요도 (높음/보통/낮음) |
| education_point | TEXT | 예방교육 활용 포인트 |
| memo | TEXT | 내부 메모 |
| is_favorite | INTEGER | 즐겨찾기 |

### keywords
| 컬럼 | 설명 |
|---|---|
| id, keyword, keyword_type, is_active, created_date, last_collected_date, article_count, memo |

### recommended_keywords
| 컬럼 | 설명 |
|---|---|
| id, keyword, occurrence_count, related_article_count, latest_detected_date, **status (pending/approved/rejected)**, created_date |

> 📌 추천 키워드는 **승인(approved) 시에만** keywords 테이블로 자동 이동합니다. 자동 등록은 절대 일어나지 않습니다.

---

# 🚀 비개발자용 단계별 설치 가이드

## ① VS Code 설치

1. https://code.visualstudio.com/ 접속
2. 운영체제에 맞는 버전 다운로드(Windows / macOS)
3. 설치 파일 실행 → 기본 옵션으로 설치

## ② Python 설치

1. https://www.python.org/downloads/ 접속
2. **Python 3.11** 또는 **3.12** 다운로드 (3.13 이상은 일부 패키지 호환성 이슈 가능)
3. ⚠️ Windows의 경우 설치 첫 화면에서 **"Add Python to PATH"** 반드시 체크
4. 설치 완료 후 확인:
   - Windows: `cmd` 실행 → `python --version`
   - macOS: `터미널` 실행 → `python3 --version`

## ③ 프로젝트 폴더 준비

1. 바탕화면 등 원하는 곳에 `drug-news-monitor` 폴더 생성
2. 이 프로젝트의 모든 파일을 해당 폴더에 그대로 복사 (폴더 구조 유지)
3. VS Code 실행 → **File → Open Folder** → `drug-news-monitor` 선택

## ④ 터미널 열기

VS Code 상단 메뉴: **Terminal → New Terminal** (단축키: `Ctrl + ` `)

## ⑤ 가상환경 만들기 (선택이지만 권장)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

## ⑥ 필요한 패키지 설치

```bash
pip install -r requirements.txt
```

> 약 1~2분 소요됩니다.

## ⑦ 실행

```bash
streamlit run app.py
```

- 자동으로 브라우저에서 `http://localhost:8501` 가 열립니다.
- 처음 실행 시 자동으로 `data/monitor.db` 가 생성되고, **기본 검색 키워드 8개만** 입력됩니다. 실제 기사처럼 보이는 샘플 기사는 생성하지 않습니다.
- 중단할 때는 터미널에서 `Ctrl + C`

## ⑧ (선택) OpenAI API 키 등록

키가 있으면 더 정교한 AI 분석이 가능합니다. 없어도 모든 기능 정상 동작.

1. `.streamlit/secrets.toml.example` 파일을 같은 폴더에 복사
2. 파일명을 `.streamlit/secrets.toml` 로 변경
3. 파일 안에 본인의 OpenAI API 키 입력:
   ```toml
   OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxx"
   ```
4. Streamlit 앱 재시작

---

# 🌐 GitHub 업로드 (배포를 위한 필수 단계)

## ① GitHub 계정 만들기
- https://github.com/signup → 무료 계정 가입

## ② Git 설치 (PC에 설치)
- https://git-scm.com/downloads → 운영체제에 맞게 설치 (기본 옵션)

## ③ GitHub에 새 저장소(Repository) 만들기
1. GitHub 로그인 → 우측 상단 `+` → **New repository**
2. Repository name: `drug-news-monitor`
3. **Public** 또는 **Private** 선택 (Streamlit Cloud 무료 플랜은 Public 권장)
4. README 추가 옵션은 **체크 해제** (이미 README.md가 있음)
5. **Create repository** 클릭

## ④ 코드 업로드 (VS Code 터미널에서 실행)

GitHub 저장소 페이지에 표시된 명령어를 그대로 따라 하면 됩니다. 일반적으로:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/본인계정/drug-news-monitor.git
git push -u origin main
```

> 첫 push 시 GitHub 로그인 창이 뜹니다. 인증 후 진행.

> ⚠️ `secrets.toml` 은 `.gitignore` 에 등록되어 있어 자동 제외됩니다. API 키가 GitHub에 노출되지 않습니다.

---

# ☁️ Streamlit Community Cloud 배포 (가장 쉬움 · 무료)

> 팀원에게 **링크 하나로 접속** 가능한 상태가 됩니다.

## ① 가입
1. https://streamlit.io/cloud 접속
2. **Continue with GitHub** 클릭 → 위에서 만든 GitHub 계정으로 로그인

## ② 앱 배포
1. **New app** 클릭
2. 다음 정보 입력:
   - Repository: `본인계정/drug-news-monitor`
   - Branch: `main`
   - Main file path: `app.py`
3. **Deploy** 클릭

약 2~5분 후 배포 완료. 다음과 같은 URL이 생성됩니다:

```
https://drug-news-monitor-xxxxx.streamlit.app
```

## ③ OpenAI API 키 등록 (Streamlit Cloud)
1. 앱 대시보드 → **⋮ (점 세 개)** → **Settings** → **Secrets**
2. 다음 내용 입력 후 저장:
   ```toml
   OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxx"
   ```
3. 앱이 자동으로 재시작됩니다.

## ④ 팀원에게 링크 공유
- 위 `https://...streamlit.app` 주소를 사내 메신저로 공유
- 누구나 접속 가능 (별도 로그인 불필요)
- **계정 보안이 필요하면** 앱 대시보드 → Settings → Sharing → "Only specific people can view this app" 옵션 활용 (이메일 화이트리스트)

---

# 🚀 Render 배포 (대안)

Streamlit Cloud 외에 Render도 가능합니다.

1. https://render.com 가입 (GitHub 연동)
2. **New +** → **Web Service**
3. 본인의 `drug-news-monitor` 저장소 선택
4. 설정:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true`
   - **Instance Type**: Free
5. **Environment Variables** 에 `OPENAI_API_KEY` 추가 (선택)
6. **Create Web Service** 클릭 → 5~10분 후 배포 완료

> ⚠️ Render 무료 플랜은 15분간 미접속 시 잠자기 상태로 전환되어 첫 접속이 느려질 수 있습니다. 앱 깨우기 문제를 줄이려면 Starter 이상 유료 인스턴스를 권장합니다.

---

# 📖 화면별 사용 안내

## 📊 메인 대시보드 (`app.py`)
- 좌측 사이드바에 메뉴 위치, 우측에 KPI 4종 + TOP5 + 키워드/분류 통계 + 7일 추이
- 사이드바에서 [🔄 키워드 통계 갱신], [💡 추천 키워드 재분석] 실행 가능

## 📰 전체 기사 조회
- 검색어 + 분류 + 중요도 + 키워드 + 기간 + 즐겨찾기 다중 필터
- **카드형 / 표형식** 2가지 보기
- **CSV 다운로드** 가능
- 카드의 **[👁️ 상세]** 버튼 → 상세 페이지로 이동 → 거기서 중요도/분류/메모 등 수정 가능
- 원문 링크는 **새 창**으로 열림

## 🏷️ 키워드 관리
- 새 키워드 추가, 토글로 활성/비활성 즉시 전환
- 키워드별 누적 기사 수와 최근 수집일 표시
- 수정/삭제 가능

## 💡 추천 키워드
- 누적 기사를 분석해 자동 추출된 신규 후보 키워드 표시
- pending / approved / rejected 탭으로 구분
- **승인(✅) 누를 때만** 정식 키워드로 등록됨 (자동 등록 절대 없음)

## 📥 기사 수집
- **RSS 자동 수집** 탭: 활성 키워드 선택 후 [🚀 RSS 수집 시작]
- **CSV 업로드** 탭: 샘플 양식 다운로드 가능
- **수동 등록** 탭: 단건 직접 입력
- 모든 탭에서 [AI 자동 분석 적용] 체크박스로 요약/분류/중요도/활용포인트 자동 생성

## 📋 주간 브리핑
- 최근 N일(기본 7일) 기사 자동 분석
- 5개 섹션 보고서: 주요 이슈 / 주요 키워드 / 예방교육 활용 / 정책·법률 / 강사 공유용 요약
- 텍스트 다운로드(.txt) 가능

---

# 🔧 OpenAI API · RSS 연결 위치 안내

## OpenAI API 연결 위치
- **파일**: `modules/ai_helper.py`
- **함수**:
  - `summarize_article()` — 3줄 요약 (GPT 호출)
  - `generate_education_point()` — 예방교육 활용 포인트 (GPT 호출)
  - `analyze_article()` — 통합 분석 (위 함수들을 한 번에 실행)
- **모델**: 기본 `gpt-4o-mini` (코드 내 변경 가능)
- **키 인식 순서**: ① `st.secrets["OPENAI_API_KEY"]` → ② 환경변수 `OPENAI_API_KEY` → ③ 없으면 규칙 기반 폴백

## RSS 연결 위치
- **파일**: `modules/rss_collector.py`
- **함수**: `fetch_google_news(keyword, max_items)`
- **사용 위치**: `pages/4_📥_기사수집.py` 의 "RSS 자동 수집" 탭
- **확장 방법**: 네이버 뉴스 RSS, 다음 뉴스 RSS 등은 같은 파일에 `fetch_naver_news()` 같은 함수를 추가하고 4번 페이지에 옵션을 늘리면 됩니다.

---

# 🛣️ 향후 확장 방향

1. **DB 확장**: SQLite → PostgreSQL 전환 시 `modules/database.py` 의 connection 부분만 SQLAlchemy 또는 psycopg2 로 교체하면 동일 구조 유지 가능
2. **로그인 / 권한**: `streamlit-authenticator` 패키지 추가로 팀원 계정·권한 분리
3. **자동 수집 스케줄러**: GitHub Actions + cron으로 매일 자정 자동 RSS 수집
4. **추가 RSS 소스**: 네이버 뉴스 검색 API, 다음 뉴스, 정부 보도자료 RSS
5. **기사 본문 크롤링**: `requests` + `BeautifulSoup` 으로 RSS의 summary 대신 본문 전체 수집
6. **임베딩 기반 유사 기사 추천**: OpenAI embeddings + ChromaDB
7. **알림 기능**: 중요 기사 발생 시 Slack/이메일 자동 발송 (사용자 요청대로 메일 일괄 발송은 제외하되, 긴급 알림용은 별도 고려 가능)

---

# ❓ 문제 해결 (Troubleshooting)

| 증상 | 해결 |
|---|---|
| `streamlit: command not found` | `pip install streamlit` 후 가상환경 활성화 확인 |
| `ModuleNotFoundError: feedparser` | `pip install -r requirements.txt` 다시 실행 |
| 한글 깨짐 (CSV) | CSV는 UTF-8 BOM(`utf-8-sig`) 으로 저장되어 있음 → Excel은 자동 인식 |
| Streamlit Cloud에서 DB 초기화됨 | Cloud의 파일 시스템은 임시 저장이라 재배포 시 초기화됨 → 영구 보관은 PostgreSQL 등 외부 DB로 확장 필요 |
| RSS 수집 시 0건 | Google News RSS는 일시적으로 차단되는 경우가 있음 → 잠시 후 재시도 |

---

# 📝 라이선스 / 사용 안내

이 코드는 공공기관 내부 업무용으로 자유롭게 수정·활용 가능합니다.
OpenAI API 사용 시 API 비용은 사용자 부담입니다.

문의/개선 사항이 있으면 담당자에게 전달해 주세요.


---

# ✅ 이번 Render 배포용 수정 사항

- 첫 실행 시 생성되던 시연용 샘플 기사 30건을 제거했습니다.
- 기사 목록에는 RSS 수집, CSV 업로드, 수동 등록으로 입력된 기사만 저장됩니다.
- OpenAI 요약 프롬프트를 보수적으로 수정하여, 원문에 없는 수치·기관명·사건 내용을 추가하지 않도록 했습니다.
- Render 배포용 `render.yaml`, `Procfile`, `runtime.txt`를 추가했습니다.
- 기존 `data/monitor.db`는 포함하지 않았습니다. 배포 후 새 DB가 생성됩니다.

## Render 설정값

- Build Command: `pip install -r requirements.txt`
- Start Command: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true`
- Environment: Python


## Supabase 전환 적용 안내

이 수정본은 기존 SQLite(`data/monitor.db`) 저장 방식을 Supabase 저장 방식으로 변경한 버전입니다.

### 1. Supabase에서 테이블 생성
Supabase 프로젝트 → SQL Editor → New query에서 `supabase_setup.sql` 내용을 붙여넣고 실행합니다.  
보안 팝업이 뜨면 현재 내부용 앱 기준으로 `Run without RLS`를 선택합니다.

### 2. Streamlit Cloud Secrets 등록
Streamlit Cloud → 해당 앱 → Manage app → Settings → Secrets에 아래 형식으로 입력합니다.

```toml
SUPABASE_URL = "https://프로젝트주소.supabase.co"
SUPABASE_KEY = "anon public key"
```

기존 OpenAI 키를 쓰고 있다면 함께 유지합니다.

```toml
OPENAI_API_KEY = "sk-..."
SUPABASE_URL = "https://프로젝트주소.supabase.co"
SUPABASE_KEY = "anon public key"
```

### 3. GitHub 업로드
수정된 전체 파일을 GitHub에 업로드하면 Streamlit Cloud가 자동 재배포합니다.

### 4. 주의
기존 `data/monitor.db`에 있던 과거 기사/키워드는 자동 이전되지 않습니다.  
필요하면 기존 DB를 CSV로 뽑아 Supabase에 별도 업로드해야 합니다.
