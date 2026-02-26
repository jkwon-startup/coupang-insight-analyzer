"""쿠팡 HTML 셀렉터 중앙 관리 (Tailwind UI + API 응답용)"""

# === Tailwind UI 셀렉터 (브라우저 렌더링 페이지) ===
REVIEW_ARTICLE_TW = "article.twc-pt-\\[16px\\]"
STAR_FULL_TW = "i.twc-bg-full-star"
STAR_HALF_TW = "i.twc-bg-half-star"
STAR_EMPTY_TW = "i.twc-bg-empty-star"
AUTHOR_DATE_CONTAINER_TW = ".twc-flex.twc-flex-col.twc-gap-\\[6px\\]"
REVIEW_CONTENT_TW_SELECTORS = [
    ".twc-text-bluegray-900.twc-break-all",
    ".twc-text-bluegray-900.twc-break-all span",
    ".twc-text-bluegray-900",
    ".twc-break-all",
]
HELPFUL_TW = ".sdp-review__article__list__help"
PAGINATION_TW = "[data-page]"
REVIEW_AREA = ".sdp-review"

# === API 응답 셀렉터 (전통 sdp-review 구조) ===
REVIEW_ARTICLE_API = "article.sdp-review__article__list"
REVIEW_ARTICLE_API_ALT = ".js_reviewArticle"
STAR_API = ".sdp-review__article__list__info__product-info__star-orange"
AUTHOR_API = ".sdp-review__article__list__info__user__name"
DATE_API = ".sdp-review__article__list__info__product-info__reg-date"
HEADLINE_API = ".sdp-review__article__list__headline"
CONTENT_API = ".sdp-review__article__list__review__content"
HELPFUL_API = ".sdp-review__article__list__help__count"

# === Q&A 셀렉터 ===
QNA_ENTRY = "div.qna"
QNA_CONTENT = "span[translate='no']"

# === 상품 상세 셀렉터 ===
PRODUCT_DETAIL_CONTENT = ".product-detail-content"
DETAIL_IMAGE = ".subType-IMAGE img, .vendor-item img"
PRODUCT_TITLE = "h1.prod-buy-header__title, h2.prod-buy-header__title"
PRODUCT_PRICE = ".total-price strong"

# === 탭 XPath ===
TAB_REVIEW_XPATH = "//a[contains(text(), '상품평')]"
TAB_QNA_XPATH = "//a[contains(text(), '상품문의')]"
