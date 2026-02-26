"""네이버 스마트스토어 Q&A(상품문의) 수집기 (3단계 fallback)

1단계: __NEXT_DATA__ JSON에서 초기 Q&A 추출
2단계: 내부 API로 전체 페이지 수집
    - smartstore.naver.com → /i/v1/inquiries/paged-inquiries
    - brand.naver.com → /n/v1/inquiries/paged-inquiries
3단계: DOM 파싱 fallback
"""

import time
import random
from typing import Callable

from config.settings import (
    NAVER_MAX_QNA_PAGES,
)
from config.naver_selectors import (
    QNA_LIST_SELECTORS,
    QNA_QUESTION_SELECTORS,
    QNA_ANSWER_SELECTORS,
    QNA_DATE_SELECTORS,
)


class NaverQnAScraper:
    """네이버 Q&A 수집기: JSON → API → DOM 3단계 fallback"""

    async def scrape(
        self,
        browser,
        product_info: dict,
        next_data: dict | None,
        progress_cb: Callable[[str], None] | None = None,
    ) -> list[dict]:
        """전체 Q&A 수집.

        Args:
            browser: NaverBrowser
            product_info: parse_naver_url() 결과
            next_data: __NEXT_DATA__ JSON
            progress_cb: 진행 상황 콜백
        """
        all_pairs = []
        seen = set()

        merchant_no = None
        origin_product_no = None

        if next_data:
            merchant_no = browser.get_merchant_no(next_data)
            origin_product_no = browser.get_origin_product_no(next_data)

            # 1단계: JSON에서 초기 Q&A 추출
            if progress_cb:
                progress_cb("Q&A JSON 추출 중...")
            json_pairs = self._extract_from_json(next_data)
            for p in json_pairs:
                key = p.get("question", "")[:50]
                if key and key not in seen:
                    seen.add(key)
                    all_pairs.append(p)

        # 2단계: 내부 API로 전체 수집
        if merchant_no and origin_product_no:
            if progress_cb:
                progress_cb("Q&A API 수집 중...")

            session = await browser.extract_cookies_session(product_info["full_url"])
            qna_api_url = product_info.get("qna_api", "")
            api_pairs = self._fetch_all_api(
                session, merchant_no, origin_product_no,
                qna_api_url,
                progress_cb,
            )

            for p in api_pairs:
                key = p.get("question", "")[:50]
                if key and key not in seen:
                    seen.add(key)
                    all_pairs.append(p)

        # 3단계: DOM fallback (브라우저가 있을 때만)
        if len(all_pairs) < 3 and browser.page is not None:
            if progress_cb:
                progress_cb("Q&A DOM 파싱 중...")
            dom_pairs = await self._scrape_dom(browser.page)
            for p in dom_pairs:
                key = p.get("question", "")[:50]
                if key and key not in seen:
                    seen.add(key)
                    all_pairs.append(p)

        return all_pairs

    # --- 1단계: __NEXT_DATA__ JSON 추출 ---

    def _extract_from_json(self, next_data: dict) -> list[dict]:
        """__NEXT_DATA__에서 Q&A 추출"""
        pairs = []
        try:
            props = next_data.get("props", {}).get("pageProps", {})
            state = props.get("dehydratedState", {})
            queries = state.get("queries", [])

            for q in queries:
                data = q.get("state", {}).get("data", {})
                if not isinstance(data, dict):
                    continue

                for key in ["contents", "inquiries", "items", "list"]:
                    items = data.get(key, [])
                    if isinstance(items, list) and items:
                        for item in items:
                            p = self._normalize_qna(item)
                            if p:
                                pairs.append(p)
                        if pairs:
                            return pairs

                # pages 배열 (React Query infinite)
                pages = data.get("pages", [])
                if isinstance(pages, list):
                    for page_data in pages:
                        if isinstance(page_data, dict):
                            for key in ["contents", "inquiries", "items"]:
                                items = page_data.get(key, [])
                                if isinstance(items, list):
                                    for item in items:
                                        p = self._normalize_qna(item)
                                        if p:
                                            pairs.append(p)

        except Exception:
            pass
        return pairs

    # --- 2단계: 내부 API 수집 ---

    def _fetch_all_api(
        self, session, merchant_no: str, origin_product_no: str,
        qna_api_url: str, progress_cb: Callable | None,
    ) -> list[dict]:
        """내부 API로 전체 Q&A 수집."""
        if not qna_api_url:
            return []

        all_pairs = []

        for pg in range(1, NAVER_MAX_QNA_PAGES + 1):
            if progress_cb:
                progress_cb(f"Q&A API 수집 중... (페이지 {pg})")

            pairs = self._fetch_api_page(
                session, merchant_no, origin_product_no, qna_api_url, pg
            )
            if not pairs:
                break

            all_pairs.extend(pairs)
            time.sleep(random.uniform(2.5, 4.0))

        return all_pairs

    def _fetch_api_page(
        self, session, merchant_no: str, origin_product_no: str,
        qna_api_url: str, page: int,
    ) -> list[dict]:
        """Q&A API 단일 페이지 호출."""
        params = {
            "merchantNo": merchant_no,
            "originProductNo": origin_product_no,
            "page": page,
            "pageSize": 20,
            "sortType": "RECENT",
        }
        try:
            resp = session.get(qna_api_url, params=params, timeout=15)
            if resp.status_code != 200:
                return []

            data = resp.json()
            items = (
                data.get("contents", [])
                or data.get("inquiries", [])
                or data.get("items", [])
            )
            if not isinstance(items, list):
                return []

            pairs = []
            for item in items:
                p = self._normalize_qna(item)
                if p:
                    pairs.append(p)
            return pairs

        except Exception:
            return []

    # --- 3단계: DOM fallback ---

    async def _scrape_dom(self, page) -> list[dict]:
        """DOM에서 Q&A 파싱."""
        pairs = []

        # Q&A 목록 찾기
        qna_els = []
        for sel in QNA_LIST_SELECTORS:
            qna_els = await page.query_selector_all(sel)
            if qna_els:
                break

        for el in qna_els:
            question = ""
            answer = ""
            date = ""

            # 질문
            for sel in QNA_QUESTION_SELECTORS:
                try:
                    q_el = await el.query_selector(sel)
                    if q_el:
                        question = (await q_el.inner_text()).strip()
                        break
                except Exception:
                    continue

            # 답변
            for sel in QNA_ANSWER_SELECTORS:
                try:
                    a_el = await el.query_selector(sel)
                    if a_el:
                        answer = (await a_el.inner_text()).strip()
                        break
                except Exception:
                    continue

            # 날짜
            for sel in QNA_DATE_SELECTORS:
                try:
                    d_el = await el.query_selector(sel)
                    if d_el:
                        date = (await d_el.inner_text()).strip()
                        break
                except Exception:
                    continue

            if question:
                pairs.append({
                    "question": question,
                    "answer": answer,
                    "q_date": date,
                    "a_date": "",
                    "seller": "",
                })

        return pairs

    # --- 공통 ---

    def _normalize_qna(self, item) -> dict | None:
        """네이버 JSON Q&A → 공유 데이터 구조로 변환."""
        if not isinstance(item, dict):
            return None

        question = (
            item.get("inquiryContent", "")
            or item.get("content", "")
            or item.get("question", "")
            or item.get("body", "")
            or ""
        )

        if not question:
            return None

        # 답변
        answer_obj = item.get("answer") or item.get("reply") or {}
        if isinstance(answer_obj, dict):
            answer = (
                answer_obj.get("answerContent", "")
                or answer_obj.get("content", "")
                or answer_obj.get("body", "")
                or ""
            )
            a_date = answer_obj.get("createDate", "") or answer_obj.get("answerDate", "")
            seller = answer_obj.get("writerNickname", "") or answer_obj.get("sellerName", "")
        elif isinstance(answer_obj, str):
            answer = answer_obj
            a_date = ""
            seller = ""
        else:
            answer = ""
            a_date = ""
            seller = ""

        q_date = item.get("createDate", "") or item.get("inquiryDate", "") or ""
        if isinstance(q_date, str) and len(q_date) > 10:
            q_date = q_date[:10]
        if isinstance(a_date, str) and len(a_date) > 10:
            a_date = a_date[:10]

        return {
            "question": question,
            "answer": answer,
            "q_date": q_date,
            "a_date": a_date,
            "seller": seller,
        }
