"""쿠팡 Q&A(상품문의) 수집기"""

import re
from typing import Callable

from config.selectors import TAB_QNA_XPATH, QNA_ENTRY, QNA_CONTENT
from config.settings import MAX_QNA_PAGES
from crawler.anti_detect import page_transition_delay, short_delay


class QnAScraper:
    async def scrape(
        self,
        page,
        progress_cb: Callable[[str], None] | None = None,
    ) -> list[dict]:
        """Q&A 탭 클릭 후 질문-답변 페어 수집"""

        # Q&A 탭 클릭
        await self._click_qna_tab(page)

        all_pairs = []
        pg = 1

        while pg <= MAX_QNA_PAGES:
            if progress_cb:
                progress_cb(f"Q&A 수집 중... (페이지 {pg})")

            pairs = await self._parse_qna_page(page)
            if not pairs:
                break

            all_pairs.extend(pairs)
            pg += 1

            # 다음 페이지
            if not await self._go_next_qna_page(page, pg):
                break

            await page_transition_delay()

        return all_pairs

    async def _parse_qna_page(self, page) -> list[dict]:
        """현재 페이지의 Q&A 엔트리 파싱"""
        entries = await page.query_selector_all(QNA_ENTRY)
        if not entries:
            return []

        pairs = []
        current_question = None

        for entry in entries:
            entry_type = await self._detect_type(entry)
            content = await self._extract_content(entry)
            date = await self._extract_date(entry)

            if entry_type == "question":
                # 이전 질문이 답변 없이 남아있으면 저장
                if current_question:
                    pairs.append(current_question)
                current_question = {
                    "question": content,
                    "answer": "",
                    "q_date": date,
                    "a_date": "",
                    "seller": "",
                }
            elif entry_type == "answer" and current_question:
                current_question["answer"] = content
                current_question["a_date"] = date
                current_question["seller"] = await self._extract_seller(entry)
                pairs.append(current_question)
                current_question = None

        # 마지막 질문이 답변 없이 남은 경우
        if current_question:
            pairs.append(current_question)

        return pairs

    async def _detect_type(self, entry) -> str:
        """Q&A 엔트리가 질문인지 답변인지 판별"""
        try:
            full_text = await entry.inner_text()
            # 배지 텍스트로 판별
            if "질문" in full_text[:10]:
                return "question"
            if "답변" in full_text[:10]:
                return "answer"
        except Exception:
            pass
        return "unknown"

    async def _extract_content(self, entry) -> str:
        """Q&A 본문 텍스트 추출"""
        try:
            content_el = await entry.query_selector(QNA_CONTENT)
            if content_el:
                return (await content_el.inner_text()).strip()
        except Exception:
            pass

        # fallback: 전체 텍스트에서 배지/날짜 제거
        try:
            text = await entry.inner_text()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            # 첫 줄(배지)과 마지막 줄(날짜) 제외
            if len(lines) > 2:
                return " ".join(lines[1:-1])
            elif len(lines) > 1:
                return lines[1]
        except Exception:
            pass
        return ""

    async def _extract_date(self, entry) -> str:
        """날짜 추출"""
        try:
            text = await entry.inner_text()
            m = re.search(r"\d{4}/\d{2}/\d{2}", text)
            if m:
                return m.group(0)
        except Exception:
            pass
        return ""

    async def _extract_seller(self, entry) -> str:
        """판매자 정보 추출"""
        try:
            bold = await entry.query_selector(".twc-font-bold")
            if bold:
                return (await bold.inner_text()).strip()
        except Exception:
            pass
        return ""

    async def _click_qna_tab(self, page):
        """상품문의 탭 클릭"""
        try:
            tab = await page.wait_for_selector(
                f"xpath={TAB_QNA_XPATH}", timeout=10000
            )
            if tab:
                await tab.scroll_into_view_if_needed()
                await short_delay()
                await tab.click()
                await page.wait_for_timeout(3000)
        except Exception:
            pass

    async def _go_next_qna_page(self, page, target_page: int) -> bool:
        """Q&A 다음 페이지 이동"""
        try:
            # Q&A 페이지네이션도 [data-page] 사용
            paging = await page.query_selector("[data-page]")
            if not paging:
                return False
            buttons = await paging.query_selector_all("button")
            for btn in buttons:
                text = (await btn.inner_text()).strip()
                if text == str(target_page):
                    await btn.click()
                    await page_transition_delay()
                    return True
        except Exception:
            pass
        return False
