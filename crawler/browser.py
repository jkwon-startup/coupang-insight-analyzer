"""undetected-chromedriver 브라우저 관리 (쿠팡 Akamai CDN 우회 검증됨)

Playwright는 쿠팡 Akamai CDN에 의해 차단됨.
G200 SMABAT에서 검증된 undetected-chromedriver 사용.
네이버 스마트스토어용 NaverBrowser 포함.
"""

import asyncio
import json
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

from config.settings import (
    VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
    INITIAL_LOAD_WAIT, NAVER_INITIAL_LOAD_WAIT,
)


class CoupangBrowser:
    """undetected-chromedriver 기반 쿠팡 브라우저."""

    def __init__(self):
        self.driver = None
        self.page = None  # Selenium wrapper for compatibility

    async def launch(self):
        """Chrome 브라우저 시작 (비headless + bot 탐지 우회)"""
        options = uc.ChromeOptions()
        options.add_argument(f"--window-size={VIEWPORT_WIDTH},{VIEWPORT_HEIGHT}")
        options.add_argument("--lang=ko-KR")

        self.driver = uc.Chrome(options=options, headless=False, version_main=145)
        self.page = SeleniumPageWrapper(self.driver)

    async def navigate(self, url: str) -> bool:
        """페이지 이동. Access Denied이면 False 반환."""
        self.driver.get(url)
        await asyncio.sleep(INITIAL_LOAD_WAIT)

        title = self.driver.title
        if "Access Denied" in title:
            return False
        return True

    async def extract_cookies_session(self, referer: str) -> requests.Session:
        """브라우저 쿠키 → requests.Session으로 전달 (API 호출용)"""
        session = requests.Session()
        for cookie in self.driver.get_cookies():
            session.cookies.set(cookie["name"], cookie["value"])

        ua = self.driver.execute_script("return navigator.userAgent;")
        session.headers.update({
            "User-Agent": ua,
            "Accept": "text/html,*/*",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": referer,
            "X-Requested-With": "XMLHttpRequest",
        })
        return session

    async def close(self):
        """브라우저 종료"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass


class SeleniumPageWrapper:
    """Selenium WebDriver를 Playwright page API와 호환되도록 감싸는 래퍼.

    크롤러 모듈(review_scraper, qna_scraper 등)이
    await page.query_selector() 스타일로 호출할 수 있도록 함.
    """

    def __init__(self, driver):
        self.driver = driver

    async def title(self):
        return self.driver.title

    async def wait_for_timeout(self, ms: int):
        await asyncio.sleep(ms / 1000)

    async def wait_for_selector(self, selector: str, timeout: int = 10000):
        """selector로 요소 대기. xpath= 접두사 지원."""
        import time
        end = time.time() + timeout / 1000
        while time.time() < end:
            try:
                if selector.startswith("xpath="):
                    el = self.driver.find_element(By.XPATH, selector[6:])
                else:
                    el = self.driver.find_element(By.CSS_SELECTOR, selector)
                return SeleniumElementWrapper(el, self.driver)
            except Exception:
                await asyncio.sleep(0.5)
        return None

    async def query_selector(self, selector: str):
        try:
            if selector.startswith("xpath="):
                el = self.driver.find_element(By.XPATH, selector[6:])
            else:
                el = self.driver.find_element(By.CSS_SELECTOR, selector)
            return SeleniumElementWrapper(el, self.driver)
        except Exception:
            return None

    async def query_selector_all(self, selector: str):
        try:
            if selector.startswith("xpath="):
                els = self.driver.find_elements(By.XPATH, selector[6:])
            else:
                els = self.driver.find_elements(By.CSS_SELECTOR, selector)
            return [SeleniumElementWrapper(e, self.driver) for e in els]
        except Exception:
            return []

    async def evaluate(self, script: str):
        return self.driver.execute_script(f"return {script}")


class SeleniumElementWrapper:
    """Selenium WebElement를 Playwright ElementHandle API로 감싸는 래퍼."""

    def __init__(self, element, driver):
        self._el = element
        self._driver = driver

    async def inner_text(self):
        return self._el.text

    async def get_attribute(self, name: str):
        return self._el.get_attribute(name)

    async def click(self):
        self._driver.execute_script("arguments[0].click();", self._el)

    async def scroll_into_view_if_needed(self):
        self._driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", self._el
        )

    async def query_selector(self, selector: str):
        try:
            el = self._el.find_element(By.CSS_SELECTOR, selector)
            return SeleniumElementWrapper(el, self._driver)
        except Exception:
            return None

    async def query_selector_all(self, selector: str):
        try:
            if selector.startswith(":scope"):
                # :scope > * 처리
                css = selector.replace(":scope", "")
                els = self._el.find_elements(By.XPATH, "./*")
                return [SeleniumElementWrapper(e, self._driver) for e in els]
            els = self._el.find_elements(By.CSS_SELECTOR, selector)
            return [SeleniumElementWrapper(e, self._driver) for e in els]
        except Exception:
            return []


class NaverBrowser:
    """네이버 스마트스토어 브라우저.

    전략:
    1. 네이버 메인 방문 (쿠키 워밍업)
    2. 상품 페이지 이동
    3. 에러 시 새로고침/모바일 재시도
    4. CAPTCHA 시 사용자 대기 (최대 2분)
    """

    _CAPTCHA_WAIT_MAX = 120  # CAPTCHA 대기 (초)

    def __init__(self):
        self.driver = None
        self.page = None
        self._next_data = None
        self._status_cb = None  # Streamlit 상태 콜백

    async def launch(self):
        """브라우저 시작."""
        options = uc.ChromeOptions()
        options.add_argument(f"--window-size={VIEWPORT_WIDTH},{VIEWPORT_HEIGHT}")
        options.add_argument("--lang=ko-KR")

        self.driver = uc.Chrome(options=options, headless=False, version_main=145)
        self.page = SeleniumPageWrapper(self.driver)

    def set_status_callback(self, cb):
        """Streamlit 상태 업데이트 콜백 설정."""
        self._status_cb = cb

    def _update_status(self, msg):
        print(f"[NaverBrowser] {msg}")
        if self._status_cb:
            try:
                self._status_cb(msg)
            except Exception:
                pass

    async def navigate_with_mobile_fallback(
        self, desktop_url: str, mobile_url: str
    ) -> bool:
        """쿠키 워밍업 → 접속 → 에러 시 재시도."""
        # 1단계: 네이버 메인 방문 (쿠키 워밍업)
        self._update_status("네이버 메인 페이지 방문 중 (쿠키 워밍업)...")
        self.driver.get("https://www.naver.com")
        await asyncio.sleep(3.0)

        # 2단계: 데스크톱 URL 접속
        self._update_status("상품 페이지 접속 중...")
        result = await self._try_navigate(desktop_url)
        if result == "success":
            return True

        # 3단계: 에러 시 새로고침 한 번 시도
        if result == "error":
            self._update_status("에러 감지 — 5초 후 새로고침...")
            await asyncio.sleep(5.0)
            self.driver.refresh()
            await asyncio.sleep(NAVER_INITIAL_LOAD_WAIT)
            result = await self._check_page()
            if result == "success":
                return True

        # 4단계: 모바일 URL 시도
        self._update_status("모바일 URL로 재시도 중...")
        result = await self._try_navigate(mobile_url)
        if result == "success":
            return True

        # 5단계: 모바일에서도 에러 → 새로고침
        if result == "error":
            self._update_status("모바일에서도 에러 — 5초 후 새로고침...")
            await asyncio.sleep(5.0)
            self.driver.refresh()
            await asyncio.sleep(NAVER_INITIAL_LOAD_WAIT)
            result = await self._check_page()
            if result == "success":
                return True

        # 최종 실패
        self._update_status("모든 접속 시도 실패")
        return False

    async def _try_navigate(self, url: str) -> str:
        """URL 접속 후 페이지 상태 확인. 'success'|'captcha'|'error' 반환."""
        self.driver.get(url)
        await asyncio.sleep(NAVER_INITIAL_LOAD_WAIT)
        return await self._check_page()

    async def _check_page(self) -> str:
        """현재 페이지 상태 확인.

        판단 기준 (우선순위):
        1. CAPTCHA 감지 → 사용자 대기
        2. 명백한 에러 페이지 (429, 시스템 에러, 빈 페이지)
        3. __NEXT_DATA__ 존재 → 확실한 성공
        4. URL에 /products/ 포함 + 에러 아님 → 성공 (JSON 없이도 DOM 수집 가능)
        """
        try:
            source = self.driver.page_source or ""
        except Exception:
            return "error"

        # CAPTCHA 감지 (최우선)
        captcha_signs = ["보안 확인", "captcha", "보안확인", "정답을 입력"]
        if any(s in source for s in captcha_signs):
            self._update_status("CAPTCHA 감지 — 브라우저에서 직접 풀어주세요!")
            return await self._wait_for_captcha_solve()

        # 명백한 에러 페이지 판별
        title = ""
        try:
            title = self.driver.title or ""
        except Exception:
            pass

        error_signs = ["429", "시스템 에러", "Error", "에러가 발생", "찾을 수 없", "존재하지 않"]
        if any(s in title for s in error_signs) or any(s in source[:2000] for s in error_signs):
            # 페이지 내용이 거의 없으면 에러
            if len(source) < 500:
                return "error"

        # __NEXT_DATA__ 확인 (page_source + JS 두 가지 방법)
        has_next_data = "__NEXT_DATA__" in source
        if not has_next_data:
            try:
                # JS로 직접 DOM에서 확인 (page_source보다 정확)
                result = self.driver.execute_script(
                    'var el = document.querySelector("script#__NEXT_DATA__");'
                    'return el ? true : false;'
                )
                has_next_data = bool(result)
            except Exception:
                pass

        if has_next_data:
            self._update_status("상품 페이지 로드 성공! (__NEXT_DATA__ 확인)")
            return "success"

        # __NEXT_DATA__가 없어도 상품 페이지로 보이면 성공
        # (brand.naver.com 등 일부 페이지는 __NEXT_DATA__ 없이도 동작)
        current_url = ""
        try:
            current_url = self.driver.current_url or ""
        except Exception:
            pass

        is_product_page = "/products/" in current_url
        has_content = len(source) > 2000  # 최소한의 콘텐츠 존재

        if is_product_page and has_content:
            self._update_status("상품 페이지 로드 성공! (콘텐츠 확인)")
            return "success"

        return "error"

    async def _wait_for_captcha_solve(self) -> str:
        """CAPTCHA를 사용자가 풀 때까지 대기."""
        import time
        start = time.time()

        while time.time() - start < self._CAPTCHA_WAIT_MAX:
            elapsed = int(time.time() - start)
            remaining = self._CAPTCHA_WAIT_MAX - elapsed
            self._update_status(
                f"CAPTCHA 대기 중... 브라우저에서 풀어주세요 (남은 시간: {remaining}초)"
            )
            await asyncio.sleep(3.0)

            try:
                source = self.driver.page_source or ""
                # CAPTCHA 키워드가 사라졌으면 통과
                captcha_signs = ["보안 확인", "captcha", "보안확인", "정답을 입력"]
                if not any(s in source for s in captcha_signs):
                    # 페이지에 콘텐츠가 있으면 성공
                    if len(source) > 2000 or "__NEXT_DATA__" in source:
                        self._update_status("CAPTCHA 통과! 페이지 로드 성공")
                        return "success"
            except Exception:
                pass

        return "error"

    async def extract_page_data_json(self) -> dict | None:
        """<script id="__NEXT_DATA__">에서 JSON 추출."""
        if self._next_data is not None:
            return self._next_data

        try:
            script = self.driver.execute_script(
                'var el = document.querySelector("script#__NEXT_DATA__");'
                'return el ? el.textContent : null;'
            )
            if script:
                self._next_data = json.loads(script)
                return self._next_data
        except Exception:
            pass

        return None

    def get_merchant_no(self, next_data: dict) -> str | None:
        """__NEXT_DATA__에서 merchantNo 추출 (API 호출에 필수)."""
        try:
            props = next_data.get("props", {}).get("pageProps", {})
            # 여러 경로 시도
            for key in ["channel", "store", "merchantInfo"]:
                if key in props:
                    merchant = props[key]
                    if isinstance(merchant, dict):
                        for field in ["merchantNo", "channelNo", "id"]:
                            if field in merchant:
                                return str(merchant[field])
            # dehydratedState에서 탐색
            state = props.get("dehydratedState", {})
            queries = state.get("queries", [])
            for q in queries:
                data = q.get("state", {}).get("data", {})
                if isinstance(data, dict):
                    for field in ["merchantNo", "channelNo"]:
                        if field in data:
                            return str(data[field])
        except Exception:
            pass
        return None

    def get_origin_product_no(self, next_data: dict) -> str | None:
        """__NEXT_DATA__에서 originProductNo 추출."""
        try:
            props = next_data.get("props", {}).get("pageProps", {})
            # 직접 필드
            for key in ["originProductNo", "productNo"]:
                if key in props:
                    return str(props[key])
            # product 객체 내부
            product = props.get("product", {})
            if isinstance(product, dict):
                for key in ["originProductNo", "productNo", "id"]:
                    if key in product:
                        return str(product[key])
            # dehydratedState에서 탐색
            state = props.get("dehydratedState", {})
            queries = state.get("queries", [])
            for q in queries:
                data = q.get("state", {}).get("data", {})
                if isinstance(data, dict):
                    for key in ["originProductNo", "productNo"]:
                        if key in data:
                            return str(data[key])
        except Exception:
            pass
        return None

    async def extract_cookies_session(self, referer: str) -> requests.Session:
        """브라우저 쿠키 → requests.Session으로 전달 (API 호출용)"""
        session = requests.Session()
        for cookie in self.driver.get_cookies():
            session.cookies.set(cookie["name"], cookie["value"])

        ua = self.driver.execute_script("return navigator.userAgent;")
        session.headers.update({
            "User-Agent": ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": referer,
        })
        return session

    async def close(self):
        """브라우저 종료"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
