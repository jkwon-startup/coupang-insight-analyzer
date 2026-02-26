# E-Commerce Insight Analyzer

쿠팡 / 네이버 스마트스토어 상품의 상세페이지, 리뷰, Q&A를 자동 수집하고 AI로 분석하는 도구입니다.

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)

> **온라인 버전**: [Streamlit Community Cloud에서 바로 사용하기](https://coupang-insight-analyzer.streamlit.app/) (설치 없이 웹에서 실행)

## 주요 기능

| 기능 | 설명 |
|------|------|
| **상세페이지 스토리 분석** | 상품 이미지 + 텍스트를 AI가 마케팅 관점에서 분석 |
| **리뷰 분석** | 전체 리뷰를 수집하여 감성 분석, 키워드, 개선점 도출 |
| **Q&A 분석** | 상품문의를 분석하여 고객 관심사와 판매자 응대 품질 평가 |
| **전체 통합 분석** | 위 3가지를 종합한 인사이트 리포트 생성 |
| **다운로드** | Excel / Word / JSON 형식으로 결과 다운로드 |

## 지원 플랫폼

- **쿠팡** (`coupang.com/vp/products/...`)
- **네이버 스마트스토어** (`smartstore.naver.com/.../products/...`)
- **네이버 브랜드스토어** (`brand.naver.com/.../products/...`)

URL을 입력하면 플랫폼이 자동 감지됩니다.

## 지원 AI 모델

- **OpenAI o4-mini** - 빠르고 비용 효율적인 분석
- **Anthropic Claude** - 정밀한 분석

두 모델을 동시에 사용하여 결과를 비교할 수도 있습니다.

## 실행 방법

두 가지 모드로 사용할 수 있습니다.

### 방법 1: 온라인 (Cloud) — 설치 없이 바로 사용

[https://coupang-insight-analyzer.streamlit.app/](https://coupang-insight-analyzer.streamlit.app/)

- 웹 브라우저에서 바로 사용 가능
- 별도 설치 불필요
- **제한사항**: 네이버 CAPTCHA 발생 시 자동 수집이 중단됩니다

### 방법 2: 로컬 설치 — 전체 기능 사용

#### 사전 요구사항

- **Python 3.10** 이상
- **Google Chrome** 브라우저 (최신 버전)
- OpenAI 또는 Anthropic API 키

#### 1. 저장소 클론

```bash
git clone https://github.com/jkwon-startup/coupang-insight-analyzer.git
cd coupang-insight-analyzer
```

#### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

#### 3. 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501`이 자동으로 열립니다.

#### 4. 사용 방법

1. 상품 URL을 입력합니다
2. AI 모델을 선택하고 API 키를 입력합니다
3. 분석 옵션을 선택합니다
4. **분석 시작** 버튼을 클릭합니다
5. Chrome 브라우저가 자동으로 열려 데이터를 수집합니다
6. 네이버에서 CAPTCHA가 뜨면 브라우저에서 직접 풀어주세요
7. 분석이 완료되면 결과를 확인하고 다운로드합니다

### 로컬 vs 클라우드 비교

| | 로컬 (`app.py`) | 클라우드 (`app_cloud.py`) |
|---|---|---|
| **설치** | Python + Chrome 필요 | 불필요 (웹 접속만) |
| **봇 탐지 우회** | undetected-chromedriver | headless Chromium |
| **CAPTCHA** | 브라우저에서 직접 해결 가능 | 자동 수집 중단 + 안내 |
| **쿠팡 수집** | 안정적 | Access Denied 가능성 있음 |
| **네이버 수집** | 안정적 | CAPTCHA 발생 시 제한 |

## 프로젝트 구조

```
coupang-insight-analyzer/
├── app.py                      # Streamlit 메인 앱 (로컬용)
├── app_cloud.py                # Streamlit 메인 앱 (클라우드용)
├── config/
│   ├── settings.py             # 상수 및 설정
│   ├── selectors.py            # 쿠팡 CSS 셀렉터
│   └── naver_selectors.py      # 네이버 CSS 셀렉터
├── crawler/
│   ├── browser.py              # 브라우저 관리 - 로컬 (undetected-chromedriver)
│   ├── browser_cloud.py        # 브라우저 관리 - 클라우드 (headless Chromium)
│   ├── url_parser.py           # URL 파싱
│   ├── product_page.py         # 쿠팡 상품 정보 수집
│   ├── review_scraper.py       # 쿠팡 리뷰 수집
│   ├── qna_scraper.py          # 쿠팡 Q&A 수집
│   ├── naver_product_page.py   # 네이버 상품 정보 수집
│   ├── naver_review_scraper.py # 네이버 리뷰 수집 (JSON→API→DOM)
│   ├── naver_qna_scraper.py    # 네이버 Q&A 수집 (JSON→API→DOM)
│   └── anti_detect.py          # 봇 탐지 우회 딜레이
├── analyzer/
│   ├── ai_client.py            # AI 클라이언트 (OpenAI/Claude)
│   ├── prompts.py              # AI 프롬프트
│   ├── story_analyzer.py       # 상세페이지 분석
│   ├── review_analyzer.py      # 리뷰 분석
│   ├── qna_analyzer.py         # Q&A 분석
│   └── full_report.py          # 종합 리포트
├── exporter/
│   ├── excel_exporter.py       # Excel 내보내기
│   └── word_exporter.py        # Word 내보내기
├── utils/
│   ├── validators.py           # URL/API 키 검증
│   └── text_cleaner.py         # 텍스트 정제
├── packages.txt                # Streamlit Cloud용 apt 패키지
└── requirements.txt
```

## 기술 스택

- **크롤링**: undetected-chromedriver + Selenium (봇 탐지 우회)
- **네이버 데이터 수집**: `__NEXT_DATA__` JSON 추출 → 내부 API → DOM 파싱 (3단계 fallback)
- **AI 분석**: OpenAI API (o4-mini) / Anthropic Claude API
- **UI**: Streamlit
- **내보내기**: openpyxl (Excel), python-docx (Word)

## 주의사항

- 로컬 실행 시 Chrome 브라우저 GUI 창이 열립니다
- 네이버 CAPTCHA 발생 시: 로컬은 직접 풀기 가능, 클라우드는 수집 중단
- API 키는 코드에 저장되지 않으며, 실행 시 직접 입력합니다
- 과도한 크롤링은 IP 차단 원인이 될 수 있으니 적절히 사용해주세요

## 라이선스

MIT License
