"""네이버 스마트스토어 리뷰 수집기

전략: 리뷰 탭 클릭 → DOM에서 직접 추출 → 페이지네이션으로 전체 수집.
클래스명 의존 없이 구조 + 텍스트 패턴 기반으로 추출.
API는 보조 수단 (429 레이트 리밋 빈번).
"""

import asyncio
import re
import time
import random
from typing import Callable

from config.settings import (
    NAVER_MAX_REVIEW_PAGES,
    NAVER_MAX_REVIEWS,
    NAVER_REVIEWS_PER_PAGE,
)


class NaverReviewScraper:
    """네이버 스마트스토어 리뷰 수집기: 탭 클릭 → DOM 추출 → 페이지네이션"""

    async def scrape_all(
        self,
        browser,
        product_info: dict,
        next_data: dict | None,
        progress_cb: Callable[[str, float], None] | None = None,
    ) -> list[dict]:
        """전체 리뷰 수집.

        Args:
            browser: NaverBrowser / NaverBrowserCloud
            product_info: parse_naver_url() 결과
            next_data: 페이지 데이터 (호환용, 실제로는 미사용)
            progress_cb: 진행 상황 콜백 (message, percentage)
        """
        all_reviews = []
        seen = set()

        # 1단계: 스크롤 후 리뷰 탭 클릭
        if progress_cb:
            progress_cb("리뷰 탭 클릭 중...", 0.0)

        # 탭이 보이도록 스크롤 (CAPTCHA 후 렌더링 대기)
        try:
            browser.driver.execute_script("window.scrollBy(0, 500);")
        except Exception:
            pass
        await asyncio.sleep(2)

        tab_clicked = await browser.click_tab("리뷰")
        if not tab_clicked:
            # 재시도: 더 스크롤 후 다시 시도
            try:
                browser.driver.execute_script("window.scrollTo(0, 800);")
            except Exception:
                pass
            await asyncio.sleep(2)
            tab_clicked = await browser.click_tab("리뷰")

        if not tab_clicked:
            if progress_cb:
                progress_cb("리뷰 탭을 찾지 못했습니다", 0.0)
            return []

        # 리뷰 영역 로딩 대기
        await asyncio.sleep(2)
        try:
            browser.driver.execute_script("window.scrollBy(0, 300);")
        except Exception:
            pass
        await asyncio.sleep(1)

        # 2단계: DOM에서 페이지별 리뷰 수집
        for pg in range(1, NAVER_MAX_REVIEW_PAGES + 1):
            if progress_cb:
                pct = (pg / min(NAVER_MAX_REVIEW_PAGES, 10)) * 0.8
                progress_cb(f"리뷰 수집 중... (페이지 {pg})", min(pct, 0.9))

            page_reviews = self._extract_reviews_from_dom(browser.driver)

            if not page_reviews:
                break

            for r in page_reviews:
                key = (r.get("author", ""), r.get("content", "")[:50])
                if key not in seen:
                    seen.add(key)
                    all_reviews.append(r)

            if len(all_reviews) >= NAVER_MAX_REVIEWS:
                break

            # 다음 페이지 클릭
            next_page = pg + 1
            clicked = self._click_page_number(browser.driver, next_page)
            if not clicked:
                break
            await asyncio.sleep(random.uniform(2.0, 3.5))

        # 3단계: API 보조 수집 (DOM에서 적게 수집된 경우)
        if len(all_reviews) < 5:
            if progress_cb:
                progress_cb("API 보조 수집 시도...", 0.8)
            api_reviews = await self._try_api_fallback(
                browser, product_info, next_data
            )
            for r in api_reviews:
                key = (r.get("author", ""), r.get("content", "")[:50])
                if key not in seen:
                    seen.add(key)
                    all_reviews.append(r)

        if progress_cb:
            progress_cb(f"리뷰 {len(all_reviews)}건 수집 완료", 1.0)

        return all_reviews[:NAVER_MAX_REVIEWS]

    def _extract_reviews_from_dom(self, driver) -> list[dict]:
        """현재 페이지 DOM에서 리뷰 추출. 클래스명 의존 없이 구조 기반."""
        try:
            reviews = driver.execute_script("""
                var uls = document.querySelectorAll('ul');
                var reviewUl = null;
                var maxLiCount = 0;

                // 모든 후보 UL 중 li가 가장 많은 것을 선택
                for (var i = 0; i < uls.length; i++) {
                    var lis = uls[i].querySelectorAll(':scope > li');
                    if (lis.length >= 3 && lis.length <= 25) {
                        var text = lis[0].textContent;
                        if (/평점[1-5]/.test(text) && text.length > 80) {
                            if (lis.length > maxLiCount) {
                                maxLiCount = lis.length;
                                reviewUl = uls[i];
                            }
                        }
                    }
                }
                if (!reviewUl) return [];

                var lis = reviewUl.querySelectorAll(':scope > li');
                var results = [];

                for (var idx = 0; idx < lis.length; idx++) {
                    var li = lis[idx];
                    var text = li.textContent;

                    // 별점 (평점1~5)
                    var ratingMatch = text.match(/평점([1-5])/);
                    var rating = ratingMatch ? parseInt(ratingMatch[1]) : null;

                    // 날짜 (YY.MM.DD.)
                    var dateMatch = text.match(/(\\d{2}\\.\\d{2}\\.\\d{2})\\.?/);
                    var date = dateMatch ? '20' + dateMatch[1].replace(/\\./g, '-') : '';

                    // 작성자 (평점 뒤 ~ 날짜 앞)
                    var author = '';
                    var authorMatch = text.match(/평점\\d([\\s\\S]*?)\\d{2}\\.\\d{2}\\.\\d{2}/);
                    if (authorMatch) {
                        author = authorMatch[1].replace(/[\\n\\r\\t]+/g, ' ').trim();
                        // 너무 길면 잘라내기 (마스킹된 닉네임은 보통 짧음)
                        if (author.length > 30) author = author.substring(0, 30);
                    }

                    // 옵션 (콜론 패턴: "옵션명: 값")
                    var option = '';
                    var optionMatch = text.match(/[가-힣]+\\s*:\\s*[가-힣A-Za-z0-9 ]+/);
                    if (optionMatch) option = optionMatch[0].trim();

                    // 본문: 가장 긴 leaf 텍스트 노드
                    var spans = li.querySelectorAll('span, p, div');
                    var content = '';
                    for (var j = 0; j < spans.length; j++) {
                        var s = spans[j];
                        var t = s.textContent.trim();
                        // leaf 노드이고 리뷰 텍스트처럼 긴 것
                        if (t.length > content.length && t.length > 15
                            && s.children.length <= 2
                            && !/평점|리뷰|도움이|신고|더보기|접기/.test(t.substring(0, 10))) {
                            content = t;
                        }
                    }

                    // 최소한 본문이나 작성자가 있어야
                    if (content.length > 10 || author) {
                        results.push({
                            rating: rating,
                            author: author,
                            date: date,
                            content: content,
                            headline: '',
                            helpful: 0,
                            option: option
                        });
                    }
                }
                return results;
            """)
            return reviews or []
        except Exception:
            return []

    def _click_page_number(self, driver, page_num: int) -> bool:
        """페이지 번호 링크 클릭."""
        try:
            clicked = driver.execute_script("""
                var num = arguments[0].toString();
                var links = document.querySelectorAll('a');
                for (var i = 0; i < links.length; i++) {
                    var text = links[i].textContent.trim();
                    if (text === num) {
                        // 페이지네이션 영역 내의 링크인지 확인 (한 자리 숫자)
                        var parent = links[i].parentElement;
                        if (parent) {
                            var siblings = parent.querySelectorAll('a');
                            // 주변에 다른 숫자 링크가 있으면 페이지네이션
                            var numCount = 0;
                            siblings.forEach(function(s) {
                                if (/^\\d+$/.test(s.textContent.trim())) numCount++;
                            });
                            if (numCount >= 2) {
                                links[i].click();
                                return true;
                            }
                        }
                    }
                }
                return false;
            """, page_num)
            return bool(clicked)
        except Exception:
            return False

    async def _try_api_fallback(
        self, browser, product_info: dict, next_data: dict | None
    ) -> list[dict]:
        """API로 보조 수집 (429가 아닌 경우에만)."""
        try:
            merchant_no = browser.get_merchant_no(next_data)
            origin_product_no = browser.get_origin_product_no(next_data)

            if not merchant_no or not origin_product_no:
                return []

            review_api_url = product_info.get("review_api", "")
            if not review_api_url:
                return []

            session = await browser.extract_cookies_session(product_info["full_url"])

            params = {
                "merchantNo": merchant_no,
                "originProductNo": origin_product_no,
                "page": 1,
                "pageSize": NAVER_REVIEWS_PER_PAGE,
                "sortType": "REVIEW_RANKING",
            }

            resp = session.get(review_api_url, params=params, timeout=15)
            if resp.status_code != 200:
                return []

            data = resp.json()
            items = data.get("contents", []) or data.get("reviews", [])
            if not isinstance(items, list):
                return []

            reviews = []
            for item in items:
                r = self._normalize_api_review(item)
                if r:
                    reviews.append(r)
            return reviews
        except Exception:
            return []

    def _normalize_api_review(self, item: dict) -> dict | None:
        """API 리뷰 JSON → 표준 dict 변환."""
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
            or item.get("author", "")
            or ""
        )

        rating = item.get("reviewScore") or item.get("score") or item.get("rating")
        try:
            rating = float(rating) if rating else None
        except (ValueError, TypeError):
            rating = None

        date = item.get("createDate", "") or item.get("writtenDate", "") or ""
        if isinstance(date, str) and len(date) > 10:
            date = date[:10]

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
            "headline": item.get("headline", "") or item.get("title", "") or "",
            "content": content,
            "helpful": item.get("helpCount", 0) or 0,
            "option": option,
        }
