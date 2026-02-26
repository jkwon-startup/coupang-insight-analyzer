"""네이버 스마트스토어 리뷰 수집기 (3단계 fallback)

1단계: __NEXT_DATA__ JSON에서 초기 리뷰 추출
2단계: 내부 API로 전체 페이지 수집
    - smartstore.naver.com → /i/v1/reviews/paged-reviews
    - brand.naver.com → /n/v1/reviews/paged-reviews
3단계: DOM 파싱 fallback
"""

import re
from typing import Callable

from config.settings import (
    NAVER_MAX_REVIEW_PAGES,
    NAVER_MAX_REVIEWS,
    NAVER_REVIEWS_PER_PAGE,
)
from config.naver_selectors import (
    REVIEW_LIST_SELECTORS,
    REVIEW_STAR_SELECTORS,
    REVIEW_CONTENT_SELECTORS,
    REVIEW_AUTHOR_SELECTORS,
    REVIEW_DATE_SELECTORS,
    REVIEW_OPTION_SELECTORS,
)
from crawler.anti_detect import naver_page_transition_delay


class NaverReviewScraper:
    """네이버 스마트스토어 리뷰 수집기: JSON → API → DOM 3단계 fallback"""

    async def scrape_all(
        self,
        browser,
        product_info: dict,
        next_data: dict | None,
        progress_cb: Callable[[str, float], None] | None = None,
    ) -> list[dict]:
        """전체 리뷰 수집.

        Args:
            browser: NaverBrowser
            product_info: parse_naver_url() 결과
            next_data: __NEXT_DATA__ JSON
            progress_cb: 진행 상황 콜백 (message, percentage)
        """
        all_reviews = []
        seen = set()  # 중복 제거용

        merchant_no = None
        origin_product_no = None

        if next_data:
            merchant_no = browser.get_merchant_no(next_data)
            origin_product_no = browser.get_origin_product_no(next_data)

            # 1단계: JSON에서 초기 리뷰 추출
            if progress_cb:
                progress_cb("리뷰 JSON 추출 중...", 0.0)
            json_reviews = self._extract_from_json(next_data)
            for r in json_reviews:
                key = (r.get("author", ""), r.get("content", "")[:50])
                if key not in seen:
                    seen.add(key)
                    all_reviews.append(r)

        # 2단계: 내부 API로 전체 수집
        if merchant_no and origin_product_no:
            if progress_cb:
                progress_cb("리뷰 API 수집 중...", 0.1)

            session = await browser.extract_cookies_session(product_info["full_url"])
            review_api_url = product_info.get("review_api", "")
            api_reviews = self._fetch_all_api(
                session, merchant_no, origin_product_no,
                review_api_url,
                progress_cb,
            )

            for r in api_reviews:
                key = (r.get("author", ""), r.get("content", "")[:50])
                if key not in seen:
                    seen.add(key)
                    all_reviews.append(r)

        # 3단계: DOM fallback (API가 부족하고 브라우저가 있을 때)
        if len(all_reviews) < 5 and browser.page is not None:
            if progress_cb:
                progress_cb("리뷰 DOM 파싱 중...", 0.7)
            dom_reviews = await self._scrape_dom(browser.page)
            for r in dom_reviews:
                key = (r.get("author", ""), r.get("content", "")[:50])
                if key not in seen:
                    seen.add(key)
                    all_reviews.append(r)

        return all_reviews[:NAVER_MAX_REVIEWS]

    # --- 1단계: __NEXT_DATA__ JSON 추출 ---

    def _extract_from_json(self, next_data: dict) -> list[dict]:
        """__NEXT_DATA__에서 초기 리뷰 추출"""
        reviews = []
        try:
            props = next_data.get("props", {}).get("pageProps", {})

            # dehydratedState에서 리뷰 쿼리 찾기
            state = props.get("dehydratedState", {})
            queries = state.get("queries", [])

            for q in queries:
                data = q.get("state", {}).get("data", {})
                if not isinstance(data, dict):
                    continue

                # 리뷰 목록 필드 탐색
                for key in ["contents", "reviews", "items", "list"]:
                    items = data.get(key, [])
                    if isinstance(items, list) and items:
                        for item in items:
                            r = self._normalize_review(item)
                            if r:
                                reviews.append(r)
                        if reviews:
                            return reviews

                # pages 배열 (React Query infinite)
                pages = data.get("pages", [])
                if isinstance(pages, list):
                    for page_data in pages:
                        if isinstance(page_data, dict):
                            for key in ["contents", "reviews", "items"]:
                                items = page_data.get(key, [])
                                if isinstance(items, list):
                                    for item in items:
                                        r = self._normalize_review(item)
                                        if r:
                                            reviews.append(r)

        except Exception:
            pass
        return reviews

    # --- 2단계: 내부 API 수집 ---

    def _fetch_all_api(
        self,
        session,
        merchant_no: str,
        origin_product_no: str,
        review_api_url: str,
        progress_cb: Callable | None,
    ) -> list[dict]:
        """내부 API로 전체 리뷰 페이지 수집."""
        if not review_api_url:
            return []

        all_reviews = []

        for pg in range(1, NAVER_MAX_REVIEW_PAGES + 1):
            if progress_cb:
                pct = 0.1 + (pg / NAVER_MAX_REVIEW_PAGES) * 0.5
                progress_cb(f"리뷰 API 수집 중... (페이지 {pg})", min(pct, 0.6))

            reviews = self._fetch_api_page(
                session, merchant_no, origin_product_no, review_api_url, pg
            )
            if not reviews:
                break

            all_reviews.extend(reviews)

            if len(all_reviews) >= NAVER_MAX_REVIEWS:
                break

            import time
            import random
            time.sleep(random.uniform(2.5, 4.0))

        return all_reviews

    def _fetch_api_page(
        self, session, merchant_no: str, origin_product_no: str,
        review_api_url: str, page: int,
    ) -> list[dict]:
        """리뷰 API 단일 페이지 호출."""
        params = {
            "merchantNo": merchant_no,
            "originProductNo": origin_product_no,
            "page": page,
            "pageSize": NAVER_REVIEWS_PER_PAGE,
            "sortType": "REVIEW_RANKING",
        }
        try:
            resp = session.get(review_api_url, params=params, timeout=15)
            if resp.status_code != 200:
                return []

            data = resp.json()
            items = data.get("contents", []) or data.get("reviews", []) or data.get("items", [])
            if not isinstance(items, list):
                return []

            reviews = []
            for item in items:
                r = self._normalize_review(item)
                if r:
                    reviews.append(r)
            return reviews

        except Exception:
            return []

    # --- 3단계: DOM fallback ---

    async def _scrape_dom(self, page) -> list[dict]:
        """DOM에서 리뷰 파싱 (최후 수단)."""
        reviews = []

        # 리뷰 목록 찾기
        review_els = []
        for sel in REVIEW_LIST_SELECTORS:
            review_els = await page.query_selector_all(sel)
            if review_els:
                break

        for el in review_els:
            r = {
                "rating": None,
                "author": "",
                "date": "",
                "content": "",
                "headline": "",
                "helpful": 0,
                "option": "",
            }

            # 별점
            for sel in REVIEW_STAR_SELECTORS:
                try:
                    star_el = await el.query_selector(sel)
                    if star_el:
                        text = (await star_el.inner_text()).strip()
                        m = re.search(r"[\d.]+", text)
                        if m:
                            r["rating"] = float(m.group(0))
                            break
                except Exception:
                    continue

            # 본문
            for sel in REVIEW_CONTENT_SELECTORS:
                try:
                    content_el = await el.query_selector(sel)
                    if content_el:
                        text = (await content_el.inner_text()).strip()
                        if text and len(text) > 2:
                            r["content"] = text
                            break
                except Exception:
                    continue

            # 작성자
            for sel in REVIEW_AUTHOR_SELECTORS:
                try:
                    author_el = await el.query_selector(sel)
                    if author_el:
                        r["author"] = (await author_el.inner_text()).strip()
                        break
                except Exception:
                    continue

            # 날짜
            for sel in REVIEW_DATE_SELECTORS:
                try:
                    date_el = await el.query_selector(sel)
                    if date_el:
                        r["date"] = (await date_el.inner_text()).strip()
                        break
                except Exception:
                    continue

            # 옵션
            for sel in REVIEW_OPTION_SELECTORS:
                try:
                    opt_el = await el.query_selector(sel)
                    if opt_el:
                        r["option"] = (await opt_el.inner_text()).strip()
                        break
                except Exception:
                    continue

            if r.get("author") or r.get("content"):
                reviews.append(r)

        return reviews

    # --- 공통 ---

    def _normalize_review(self, item) -> dict | None:
        """네이버 JSON 리뷰 → 공유 데이터 구조로 변환."""
        if not isinstance(item, dict):
            return None

        content = (
            item.get("reviewContent", "")
            or item.get("content", "")
            or item.get("body", "")
            or ""
        )

        author = (
            item.get("writerNickname", "")
            or item.get("buyerNickname", "")
            or item.get("reviewer", {}).get("nickname", "")
            if isinstance(item.get("reviewer"), dict) else
            item.get("writerNickname", "")
            or item.get("author", "")
            or ""
        )

        rating = item.get("reviewScore") or item.get("score") or item.get("rating")
        try:
            rating = float(rating) if rating else None
        except (ValueError, TypeError):
            rating = None

        date = item.get("createDate", "") or item.get("writtenDate", "") or item.get("date", "")
        if isinstance(date, str) and len(date) > 10:
            date = date[:10]  # "2024-01-15T..." → "2024-01-15"

        headline = item.get("headline", "") or item.get("title", "") or ""

        option = ""
        product_option = item.get("productOption", "") or item.get("optionText", "")
        if isinstance(product_option, str):
            option = product_option
        elif isinstance(product_option, list):
            option = ", ".join(str(o) for o in product_option)

        if not content and not author:
            return None

        return {
            "rating": rating,
            "author": author,
            "date": date,
            "headline": headline,
            "content": content,
            "helpful": item.get("helpCount", 0) or 0,
            "option": option,
        }
