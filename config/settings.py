"""앱 전체 상수 및 설정"""

# === 쿠팡 ===
COUPANG_BASE_URL = "https://www.coupang.com"
COUPANG_REVIEW_API = "https://www.coupang.com/vp/product/reviews"
COUPANG_PAGE_DELAY_MIN = 1.8
COUPANG_PAGE_DELAY_MAX = 2.5
COUPANG_INITIAL_LOAD_WAIT = 5.0
COUPANG_MAX_REVIEW_PAGES = 50
COUPANG_MAX_REVIEWS = 500
COUPANG_MAX_QNA_PAGES = 20
COUPANG_REVIEWS_PER_PAGE = 10
COUPANG_UI_PAGE_LIMIT = 10

# === 네이버 스마트스토어 ===
NAVER_SMARTSTORE_BASE = "https://smartstore.naver.com"
NAVER_BRAND_BASE = "https://brand.naver.com"
NAVER_MOBILE_SMARTSTORE_BASE = "https://m.smartstore.naver.com"
NAVER_MOBILE_BRAND_BASE = "https://m.brand.naver.com"

# API 경로가 도메인마다 다름: smartstore=/i/v1, brand=/n/v1
NAVER_SMARTSTORE_REVIEW_API = "https://smartstore.naver.com/i/v1/reviews/paged-reviews"
NAVER_SMARTSTORE_QNA_API = "https://smartstore.naver.com/i/v1/inquiries/paged-inquiries"
NAVER_BRAND_REVIEW_API = "https://brand.naver.com/n/v1/reviews/paged-reviews"
NAVER_BRAND_QNA_API = "https://brand.naver.com/n/v1/inquiries/paged-inquiries"

# 하위 호환 (기존 참조용)
NAVER_REVIEW_API = NAVER_SMARTSTORE_REVIEW_API
NAVER_QNA_API = NAVER_SMARTSTORE_QNA_API
NAVER_PAGE_DELAY_MIN = 2.5
NAVER_PAGE_DELAY_MAX = 4.0
NAVER_INITIAL_LOAD_WAIT = 6.0
NAVER_MAX_REVIEW_PAGES = 50
NAVER_MAX_REVIEWS = 500
NAVER_MAX_QNA_PAGES = 20
NAVER_REVIEWS_PER_PAGE = 20

# === 공통 (하위 호환) ===
PAGE_DELAY_MIN = 1.8
PAGE_DELAY_MAX = 2.5
INITIAL_LOAD_WAIT = 5.0
TAB_CLICK_WAIT = 3.0
MAX_REVIEW_PAGES = 50
MAX_REVIEWS = 500
MAX_QNA_PAGES = 20
REVIEWS_PER_PAGE = 10
UI_PAGE_LIMIT = 10

# AI 모델
OPENAI_MODEL = "o4-mini"
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# AI 토큰 제한
MAX_TOKENS_STORY = 2000
MAX_TOKENS_REVIEW = 3000
MAX_TOKENS_QNA = 2000
MAX_TOKENS_FULL = 4000

# 브라우저
VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080
LOCALE = "ko-KR"
