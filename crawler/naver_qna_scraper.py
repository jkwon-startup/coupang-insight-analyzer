"""네이버 스마트스토어 Q&A(상품문의) 수집기

전략: Q&A 탭 클릭 → DOM에서 직접 추출 → 페이지네이션으로 전체 수집.
클래스명 의존 없이 구조 + 텍스트 패턴 기반으로 추출.
API는 보조 수단 (429 레이트 리밋 빈번).
"""

import asyncio
import time
import random
from typing import Callable

from config.settings import (
    NAVER_MAX_QNA_PAGES,
)


class NaverQnAScraper:
    """네이버 Q&A 수집기: 탭 클릭 → DOM 추출 → 페이지네이션"""

    async def scrape(
        self,
        browser,
        product_info: dict,
        next_data: dict | None,
        progress_cb: Callable[[str], None] | None = None,
    ) -> list[dict]:
        """전체 Q&A 수집.

        Args:
            browser: NaverBrowser / NaverBrowserCloud
            product_info: parse_naver_url() 결과
            next_data: 페이지 데이터 (호환용, 실제로는 미사용)
            progress_cb: 진행 상황 콜백
        """
        all_pairs = []
        seen = set()

        # 1단계: 스크롤 후 Q&A 탭 클릭
        if progress_cb:
            progress_cb("Q&A 탭 클릭 중...")

        # 탭이 보이도록 스크롤
        try:
            browser.driver.execute_script("window.scrollBy(0, 500);")
        except Exception:
            pass
        await asyncio.sleep(2)

        tab_clicked = await browser.click_tab("Q&A")
        if not tab_clicked:
            tab_clicked = await browser.click_tab("문의")

        if not tab_clicked:
            # 재시도: 더 스크롤 후 다시 시도
            try:
                browser.driver.execute_script("window.scrollTo(0, 800);")
            except Exception:
                pass
            await asyncio.sleep(2)
            tab_clicked = await browser.click_tab("Q&A")

        if not tab_clicked:
            if progress_cb:
                progress_cb("Q&A 탭을 찾지 못했습니다")
            return []

        # Q&A 영역 로딩 대기
        await asyncio.sleep(2)
        try:
            browser.driver.execute_script("window.scrollBy(0, 300);")
        except Exception:
            pass
        await asyncio.sleep(1)

        # 2단계: DOM에서 페이지별 Q&A 수집
        for pg in range(1, NAVER_MAX_QNA_PAGES + 1):
            if progress_cb:
                progress_cb(f"Q&A 수집 중... (페이지 {pg})")

            page_pairs = self._extract_qna_from_dom(browser.driver)

            if not page_pairs:
                break

            for p in page_pairs:
                key = p.get("question", "")[:50]
                if key and key not in seen:
                    seen.add(key)
                    all_pairs.append(p)

            # 다음 페이지 클릭
            next_page = pg + 1
            clicked = self._click_page_number(browser.driver, next_page)
            if not clicked:
                break
            await asyncio.sleep(random.uniform(2.0, 3.5))

        # 3단계: API 보조 수집 (DOM에서 적게 수집된 경우)
        if len(all_pairs) < 3:
            if progress_cb:
                progress_cb("Q&A API 보조 수집 시도...")
            api_pairs = await self._try_api_fallback(
                browser, product_info, next_data
            )
            for p in api_pairs:
                key = p.get("question", "")[:50]
                if key and key not in seen:
                    seen.add(key)
                    all_pairs.append(p)

        if progress_cb:
            progress_cb(f"Q&A {len(all_pairs)}건 수집 완료")

        return all_pairs

    def _extract_qna_from_dom(self, driver) -> list[dict]:
        """현재 페이지 DOM에서 Q&A 추출. 클래스명 의존 없이 구조 기반.

        네이버 Q&A DOM 구조:
        ul > li > div(컨테이너) > div*4:
          - [0] 상태 ("답변완료"/"답변대기")
          - [1] 질문 텍스트 (childCount=1, leaf-like)
          - [2] 작성자 닉네임 (childCount=0)
          - [3] 날짜 (childCount=0, "YYYY.MM.DD.")
        """
        try:
            pairs = driver.execute_script("""
                var uls = document.querySelectorAll('ul');
                var qnaUl = null;

                for (var i = 0; i < uls.length; i++) {
                    var lis = uls[i].querySelectorAll(':scope > li');
                    if (lis.length >= 1 && lis.length <= 30) {
                        var text = lis[0].textContent;
                        if ((/답변(완료|대기)/.test(text) || /비밀글/.test(text))
                            && text.length > 20) {
                            qnaUl = uls[i];
                            break;
                        }
                    }
                }
                if (!qnaUl) return [];

                var lis = qnaUl.querySelectorAll(':scope > li');
                var results = [];

                for (var idx = 0; idx < lis.length; idx++) {
                    var li = lis[idx];
                    var text = li.textContent;

                    var question = '';
                    var author = '';
                    var qDate = '';
                    var hasAnswer = /답변완료/.test(text);
                    var isSecret = /비밀글/.test(text);

                    // 방법 1: leaf div 구조에서 추출
                    // 각 li 안에 div들이 있고, childCount=0인 것이 leaf
                    var divs = li.querySelectorAll('div');
                    var questionDiv = null;
                    var authorDiv = null;
                    var dateDiv = null;

                    for (var j = 0; j < divs.length; j++) {
                        var d = divs[j];
                        var t = d.textContent.trim();
                        if (!t) continue;

                        // 날짜 패턴 (YY.MM.DD. 또는 YYYY.MM.DD.)
                        if (/^\\d{2,4}\\.\\d{2}\\.\\d{2}\\.?$/.test(t) && d.children.length === 0) {
                            dateDiv = t;
                            continue;
                        }
                        // 닉네임 패턴 (짧고 leaf, 마스킹 포함)
                        if (d.children.length === 0 && t.length <= 20 && t.length >= 3
                            && /\\*/.test(t) && !/답변|비밀|신고/.test(t)) {
                            authorDiv = t;
                            continue;
                        }
                        // 질문 텍스트 (가장 길고, 상태/메타가 아닌 것)
                        if (d.children.length <= 1 && t.length > 10
                            && !/^답변(완료|대기)$/.test(t)
                            && !/비밀글입니다/.test(t.substring(0, 10))
                            && !/신고|수정|삭제/.test(t.substring(0, 5))) {
                            if (!questionDiv || t.length > questionDiv.length) {
                                questionDiv = t;
                            }
                        }
                    }

                    // 날짜 변환
                    if (dateDiv) {
                        var d = dateDiv.replace(/\\./g, '-').replace(/-$/, '');
                        if (d.length <= 8) d = '20' + d;
                        qDate = d;
                    }

                    // 질문 설정
                    if (questionDiv) {
                        question = questionDiv;
                    } else if (isSecret) {
                        question = '(비공개 문의)';
                    }

                    // 작성자
                    author = authorDiv || '';

                    if (question) {
                        results.push({
                            question: question,
                            answer: hasAnswer ? '(답변완료)' : '',
                            q_date: qDate,
                            a_date: '',
                            seller: '',
                            author: author
                        });
                    }
                }
                return results;
            """)
            return pairs or []
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
                        var parent = links[i].parentElement;
                        if (parent) {
                            var siblings = parent.querySelectorAll('a');
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

            qna_api_url = product_info.get("qna_api", "")
            if not qna_api_url:
                return []

            session = await browser.extract_cookies_session(product_info["full_url"])

            params = {
                "merchantNo": merchant_no,
                "originProductNo": origin_product_no,
                "page": 1,
                "pageSize": 20,
                "sortType": "RECENT",
            }

            time.sleep(2)  # 레이트 리밋 방지
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
                p = self._normalize_api_qna(item)
                if p:
                    pairs.append(p)
            return pairs
        except Exception:
            return []

    def _normalize_api_qna(self, item: dict) -> dict | None:
        """API Q&A JSON → 표준 dict 변환."""
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
