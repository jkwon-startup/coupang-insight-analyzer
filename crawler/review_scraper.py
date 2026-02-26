"""쿠팡 리뷰 수집기 (API 우선 + UI fallback 하이브리드)

기존 G200 SMABAT/coupang_reviews.py의 검증된 로직을 Playwright로 포팅.
주요 개선: API 우선 전략, content 빈값 문제 fallback 셀렉터 체인.
"""

import re
from typing import Callable

from bs4 import BeautifulSoup

from config.settings import (
    COUPANG_REVIEW_API,
    MAX_REVIEW_PAGES,
    MAX_REVIEWS,
    REVIEWS_PER_PAGE,
    UI_PAGE_LIMIT,
)
from config.selectors import (
    REVIEW_ARTICLE_TW,
    STAR_FULL_TW,
    STAR_HALF_TW,
    AUTHOR_DATE_CONTAINER_TW,
    REVIEW_CONTENT_TW_SELECTORS,
    HELPFUL_TW,
    PAGINATION_TW,
    REVIEW_AREA,
    TAB_REVIEW_XPATH,
    # API 셀렉터
    REVIEW_ARTICLE_API,
    REVIEW_ARTICLE_API_ALT,
    STAR_API,
    AUTHOR_API,
    DATE_API,
    HEADLINE_API,
    CONTENT_API,
    HELPFUL_API,
)
from crawler.anti_detect import page_transition_delay, short_delay


class ReviewScraper:
    """하이브리드 리뷰 수집기: API 우선, UI fallback"""

    async def scrape_all(
        self,
        browser,
        product_info: dict,
        progress_cb: Callable[[str, float], None] | None = None,
    ) -> list[dict]:
        """전체 리뷰 수집. API → UI fallback 순서."""
        all_reviews = []
        total_expected = None

        # 상품평 탭 클릭
        await self._click_review_tab(browser.page)

        # 총 리뷰 수 파악
        total_expected = await self._get_total_count(browser.page)

        # --- Phase 1: API로 전체 수집 시도 ---
        session = await browser.extract_cookies_session(product_info["full_url"])
        api_success = False

        for pg in range(1, MAX_REVIEW_PAGES + 1):
            if progress_cb:
                pct = min(pg / max((total_expected or 100) / REVIEWS_PER_PAGE, 1), 1.0)
                progress_cb(f"리뷰 수집 중... (API 페이지 {pg})", pct)

            reviews = self._fetch_and_parse_api(session, product_info, pg)
            if not reviews:
                if pg == 1:
                    # API 첫 페이지부터 실패 → UI fallback
                    break
                # 더 이상 리뷰 없음
                api_success = True
                break

            all_reviews.extend(reviews)
            api_success = True

            if total_expected and len(all_reviews) >= total_expected:
                break
            if len(all_reviews) >= MAX_REVIEWS:
                break

            await page_transition_delay()

        # --- Phase 2: API 실패 시 UI로 fallback (최대 10페이지) ---
        if not api_success:
            all_reviews = await self._scrape_ui(
                browser.page, total_expected, progress_cb
            )

        return all_reviews

    # --- API 기반 수집 (기존 coupang_reviews.py 로직 재활용) ---

    def _fetch_and_parse_api(
        self, session, product_info: dict, page: int
    ) -> list[dict]:
        """Review API 호출 후 파싱"""
        params = {
            "productId": product_info["product_id"],
            "itemId": product_info.get("item_id", ""),
            "vendorItemId": product_info.get("vendor_item_id", ""),
            "page": page,
            "size": REVIEWS_PER_PAGE,
            "sortBy": "ORDER_SCORE_ASC",
            "ratings": "",
            "q": "",
            "viRoleCode": "3",
            "ratingSummary": "true",
        }
        try:
            resp = session.get(COUPANG_REVIEW_API, params=params, timeout=10)
            if resp.status_code != 200:
                return []
            return self._parse_reviews_api(resp.text)
        except Exception:
            return []

    def _parse_reviews_api(self, html_text: str) -> list[dict]:
        """API 응답 HTML 파싱 (sdp-review 전통 구조)"""
        soup = BeautifulSoup(html_text, "html.parser")
        reviews = []

        articles = soup.select(REVIEW_ARTICLE_API)
        if not articles:
            articles = soup.select(REVIEW_ARTICLE_API_ALT)

        for art in articles:
            r = {}

            # 별점 (width 퍼센트 → 5점 만점)
            try:
                star = art.select_one(STAR_API)
                if star:
                    style = star.get("style", "")
                    if "width:" in style:
                        w = style.split("width:")[1].split("%")[0].strip()
                        r["rating"] = round(float(w) / 20, 1)
            except Exception:
                r["rating"] = None

            # 작성자
            try:
                r["author"] = art.select_one(AUTHOR_API).get_text(strip=True)
            except Exception:
                r["author"] = ""

            # 날짜
            try:
                r["date"] = art.select_one(DATE_API).get_text(strip=True)
            except Exception:
                r["date"] = ""

            # 헤드라인
            try:
                r["headline"] = art.select_one(HEADLINE_API).get_text(strip=True)
            except Exception:
                r["headline"] = ""

            # 본문
            try:
                r["content"] = art.select_one(CONTENT_API).get_text(strip=True)
            except Exception:
                r["content"] = ""

            # 도움이 돼요
            r["helpful"] = 0
            try:
                help_text = art.select_one(HELPFUL_API).get_text(strip=True)
                m = re.search(r"(\d+)", help_text)
                if m:
                    r["helpful"] = int(m.group(1))
            except Exception:
                pass

            if r.get("author") or r.get("content"):
                reviews.append(r)

        return reviews

    # --- UI 기반 수집 (Playwright, 최대 10페이지) ---

    async def _scrape_ui(
        self, page, total_expected, progress_cb
    ) -> list[dict]:
        """Playwright UI 파싱으로 리뷰 수집 (fallback)"""
        all_reviews = []

        for pg in range(1, UI_PAGE_LIMIT + 1):
            if progress_cb:
                pct = pg / UI_PAGE_LIMIT
                progress_cb(f"리뷰 수집 중... (UI 페이지 {pg}/{UI_PAGE_LIMIT})", pct)

            # 리뷰 영역으로 스크롤
            try:
                area = await page.query_selector(REVIEW_AREA)
                if area:
                    await area.scroll_into_view_if_needed()
            except Exception:
                pass
            await short_delay()

            reviews = await self._parse_page_ui(page)
            if not reviews:
                break

            all_reviews.extend(reviews)

            if total_expected and len(all_reviews) >= total_expected:
                break

            # 다음 페이지
            if pg < UI_PAGE_LIMIT:
                if not await self._go_next_page_ui(page, pg):
                    break

        return all_reviews

    async def _parse_page_ui(self, page) -> list[dict]:
        """현재 페이지의 리뷰를 Playwright로 파싱"""
        reviews = []
        articles = await page.query_selector_all(REVIEW_ARTICLE_TW)

        for art in articles:
            r = {}

            # 별점
            try:
                full = await art.query_selector_all(STAR_FULL_TW)
                half = await art.query_selector_all(STAR_HALF_TW)
                r["rating"] = len(full) + len(half) * 0.5
            except Exception:
                r["rating"] = None

            # 작성자 & 날짜
            r["author"] = ""
            r["date"] = ""
            try:
                info = await art.query_selector(AUTHOR_DATE_CONTAINER_TW)
                if info:
                    children = await info.query_selector_all(":scope > *")
                    if len(children) >= 1:
                        r["author"] = (await children[0].inner_text()).strip()
                    if len(children) >= 2:
                        r["date"] = (await children[1].inner_text()).strip()
            except Exception:
                pass

            # 본문 (fallback 셀렉터 체인 — 빈값 61% 문제 해결)
            r["content"] = ""
            for sel in REVIEW_CONTENT_TW_SELECTORS:
                try:
                    el = await art.query_selector(sel)
                    if el:
                        text = (await el.inner_text()).strip()
                        if text and len(text) > 4 and text != r["author"]:
                            r["content"] = text
                            break
                except Exception:
                    continue

            # 도움이 돼요
            r["helpful"] = 0
            try:
                help_el = await art.query_selector(HELPFUL_TW)
                if help_el:
                    m = re.search(r"(\d+)", (await help_el.inner_text()).strip())
                    if m:
                        r["helpful"] = int(m.group(1))
            except Exception:
                pass

            if r.get("author") or r.get("content"):
                reviews.append(r)

        return reviews

    async def _go_next_page_ui(self, page, current_page: int) -> bool:
        """UI에서 다음 페이지로 이동"""
        try:
            paging = await page.query_selector(PAGINATION_TW)
            if not paging:
                return False
            await paging.scroll_into_view_if_needed()
            await short_delay()

            buttons = await paging.query_selector_all("button")
            for btn in buttons:
                text = (await btn.inner_text()).strip()
                if text == str(current_page + 1):
                    await btn.click()
                    await page_transition_delay()
                    return True
        except Exception:
            pass
        return False

    async def _click_review_tab(self, page):
        """상품평 탭 클릭"""
        try:
            tab = await page.wait_for_selector(
                f"xpath={TAB_REVIEW_XPATH}", timeout=10000
            )
            if tab:
                await tab.scroll_into_view_if_needed()
                await short_delay()
                await tab.click()
                await page.wait_for_timeout(3000)
        except Exception:
            pass

    async def _get_total_count(self, page) -> int | None:
        """총 리뷰 수 추출"""
        try:
            tabs = await page.query_selector_all("a")
            for tab in tabs:
                text = (await tab.inner_text()).strip()
                if "상품평" in text:
                    m = re.search(r"\((\d[\d,]*)\)", text)
                    if m:
                        return int(m.group(1).replace(",", ""))
        except Exception:
            pass
        return None
