"""네이버 스마트스토어 HTML 셀렉터 중앙 관리

네이버 스마트스토어는 Next.js 앱으로, CSS 클래스명이 빌드 해시로 난독화됨.
__NEXT_DATA__ JSON 추출이 최우선 전략이며, 여기 정의된 셀렉터는 DOM fallback용.
복수 fallback 셀렉터를 제공하여 UI 리디자인에 대응.
"""

# === __NEXT_DATA__ JSON 추출 ===
NEXT_DATA_SCRIPT = "script#__NEXT_DATA__"

# === 상품 정보 (DOM fallback) ===
PRODUCT_TITLE_SELECTORS = [
    "h3._22kNQuEXmb",          # 난독화 클래스 (변경 가능)
    "._3oDkSBFl5e h3",
    "[class*='headingArea'] h3",
    "h3[class*='product']",
    ".top_summary_title h3",
]

PRODUCT_PRICE_SELECTORS = [
    "span._1LY7DqCnwR",
    "[class*='totalPrice'] span",
    "span[class*='sale_price']",
    ".total_price span strong",
]

PRODUCT_ORIGINAL_PRICE_SELECTORS = [
    "span._2FXtMlJ6VI del",
    "[class*='originalPrice'] del",
    "del[class*='origin_price']",
]

PRODUCT_RATING_SELECTORS = [
    "span._2pgHN-ntx6",
    "[class*='reviewScore']",
    "span[class*='avg_score']",
]

PRODUCT_REVIEW_COUNT_SELECTORS = [
    "a._2FeLrDP75i em",
    "[class*='reviewCount'] em",
    "em[class*='review_count']",
]

PRODUCT_IMAGE_SELECTORS = [
    "img._3hDkXiLm_j",
    "[class*='productImage'] img",
    ".product_thumb img",
    "img[class*='thumbnail']",
]

# === 상품 상세 이미지 ===
DETAIL_IMAGE_SELECTORS = [
    "div._1b-GsMllMv img",      # 상세 설명 영역
    "[class*='detailContent'] img",
    ".se-module-image img",
    "div[class*='detail'] img",
]

# === 리뷰 (DOM fallback) ===
REVIEW_LIST_SELECTORS = [
    "ul._1eY1iFkjHa li",
    "[class*='reviewList'] li",
    "ul[class*='review_list'] > li",
]

REVIEW_STAR_SELECTORS = [
    "em._15NU42F3kT",
    "[class*='reviewStar'] em",
    "em[class*='star_score']",
]

REVIEW_CONTENT_SELECTORS = [
    "div._3z6gI4vI6l span._3QDEeS6NLn",
    "[class*='reviewContent'] span",
    "span[class*='review_text']",
    "div[class*='content'] span",
]

REVIEW_AUTHOR_SELECTORS = [
    "span._3QDEeS6NLn._2FIDGBqNMr",
    "[class*='reviewerName']",
    "span[class*='user_id']",
]

REVIEW_DATE_SELECTORS = [
    "span._3QDEeS6NLn._1hR3urpB6W",
    "[class*='reviewDate']",
    "span[class*='date']",
]

REVIEW_OPTION_SELECTORS = [
    "div._1uRMhBLW0P",
    "[class*='reviewOption']",
    "span[class*='option']",
]

# === 리뷰 페이지네이션 ===
REVIEW_PAGINATION_SELECTORS = [
    "a._2Ar8-aEUTq",
    "[class*='pagination'] a",
    "a[class*='page_num']",
]

REVIEW_NEXT_PAGE_SELECTORS = [
    "a._2Ar8-aEUTq._2UJgMsSAkp",
    "[class*='pagination'] a[class*='next']",
    "a[class*='page_next']",
]

# === Q&A (DOM fallback) ===
QNA_LIST_SELECTORS = [
    "ul._1eY1iFkjHa li",       # 문의 리스트 (리뷰와 유사 구조)
    "[class*='inquiryList'] li",
    "ul[class*='qna_list'] > li",
]

QNA_QUESTION_SELECTORS = [
    "div._3z6gI4vI6l",
    "[class*='inquiryQuestion']",
    "div[class*='question']",
]

QNA_ANSWER_SELECTORS = [
    "div._1R_Resfly3",
    "[class*='inquiryAnswer']",
    "div[class*='answer']",
]

QNA_DATE_SELECTORS = [
    "span._1hR3urpB6W",
    "[class*='inquiryDate']",
    "span[class*='date']",
]

# === 탭 셀렉터 ===
TAB_REVIEW_SELECTORS = [
    "a[href*='review']",
    "[class*='tab'] a:nth-child(2)",
]

TAB_QNA_SELECTORS = [
    "a[href*='inquiry']",
    "a[href*='qna']",
    "[class*='tab'] a:nth-child(3)",
]
