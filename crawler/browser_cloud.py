"""Selenium headless Chromium 브라우저 관리 (클라우드 배포용)

Streamlit Community Cloud 등 headless 환경에서 동작.
CAPTCHA 발생 시 안내 메시지를 반환하고 graceful하게 중단.
로컬 GUI 버전은 browser.py 참조.
"""

import asyncio
import json
import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

from config.settings import (
    VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
    INITIAL_LOAD_WAIT, NAVER_INITIAL_LOAD_WAIT,
)

# 로컬 browser.py의 래퍼 클래스 재사용
from crawler.browser import SeleniumPageWrapper, SeleniumElementWrapper


def _create_chrome_options() -> Options:
    """클라우드 headless Chrome 옵션 생성."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={VIEWPORT_WIDTH},{VIEWPORT_HEIGHT}")
    options.add_argument("--lang=ko-KR")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Streamlit Cloud Chromium 경로 자동 감지
    for path in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]:
        if os.path.exists(path):
            options.binary_location = path
            break

    return options


def _create_driver() -> webdriver.Chrome:
    """headless Chrome WebDriver 생성."""
    options = _create_chrome_options()

    for driver_path in ["/usr/bin/chromedriver", "/usr/lib/chromium/chromedriver"]:
        if os.path.exists(driver_path):
            service = Service(executable_path=driver_path)
            return webdriver.Chrome(service=service, options=options)

    return webdriver.Chrome(options=options)


class CoupangBrowserCloud:
    """headless 기반 쿠팡 브라우저 (클라우드용)."""

    def __init__(self):
        self.driver = None
        self.page = None

    async def launch(self):
        self.driver = _create_driver()
        self.page = SeleniumPageWrapper(self.driver)

    async def navigate(self, url: str) -> bool:
        self.driver.get(url)
        await asyncio.sleep(INITIAL_LOAD_WAIT)
        title = self.driver.title
        if "Access Denied" in title:
            return False
        return True

    async def extract_cookies_session(self, referer: str) -> requests.Session:
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
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass


class NaverBrowserCloud:
    """네이버 스마트스토어 headless 브라우저 (클라우드용).

    CAPTCHA 발생 시 풀 수 없으므로 안내 메시지 반환 후 중단.
    """

    def __init__(self):
        self.driver = None
        self.page = None
        self._next_data = None
        self._status_cb = None
        self.captcha_detected = False

    async def launch(self):
        self.driver = _create_driver()
        self.page = SeleniumPageWrapper(self.driver)

    def set_status_callback(self, cb):
        self._status_cb = cb

    def _update_status(self, msg):
        print(f"[NaverBrowserCloud] {msg}")
        if self._status_cb:
            try:
                self._status_cb(msg)
            except Exception:
                pass

    async def navigate_with_mobile_fallback(
        self, desktop_url: str, mobile_url: str
    ) -> bool:
        # 1단계: 쿠키 워밍업
        self._update_status("네이버 메인 페이지 방문 중 (쿠키 워밍업)...")
        self.driver.get("https://www.naver.com")
        await asyncio.sleep(3.0)

        # 2단계: 데스크톱
        self._update_status("상품 페이지 접속 중...")
        result = await self._try_navigate(desktop_url)
        if result == "success":
            return True
        if result == "captcha":
            self.captcha_detected = True
            return False

        # 3단계: 새로고침
        if result == "error":
            self._update_status("에러 감지 — 5초 후 새로고침...")
            await asyncio.sleep(5.0)
            self.driver.refresh()
            await asyncio.sleep(NAVER_INITIAL_LOAD_WAIT)
            result = await self._check_page()
            if result == "success":
                return True
            if result == "captcha":
                self.captcha_detected = True
                return False

        # 4단계: 모바일
        self._update_status("모바일 URL로 재시도 중...")
        result = await self._try_navigate(mobile_url)
        if result == "success":
            return True
        if result == "captcha":
            self.captcha_detected = True
            return False

        # 5단계: 모바일 새로고침
        if result == "error":
            self._update_status("모바일에서도 에러 — 5초 후 새로고침...")
            await asyncio.sleep(5.0)
            self.driver.refresh()
            await asyncio.sleep(NAVER_INITIAL_LOAD_WAIT)
            result = await self._check_page()
            if result == "success":
                return True
            if result == "captcha":
                self.captcha_detected = True
                return False

        self._update_status("모든 접속 시도 실패")
        return False

    async def _try_navigate(self, url: str) -> str:
        self.driver.get(url)
        await asyncio.sleep(NAVER_INITIAL_LOAD_WAIT)
        return await self._check_page()

    async def _check_page(self) -> str:
        """페이지 상태: 'success' | 'captcha' | 'error'"""
        try:
            source = self.driver.page_source or ""
        except Exception:
            return "error"

        # CAPTCHA → 즉시 반환 (headless에서 풀 수 없음)
        captcha_signs = ["보안 확인", "captcha", "보안확인", "정답을 입력"]
        if any(s in source for s in captcha_signs):
            self._update_status("CAPTCHA 감지됨")
            return "captcha"

        # 에러 페이지
        title = ""
        try:
            title = self.driver.title or ""
        except Exception:
            pass

        error_signs = ["429", "시스템 에러", "Error", "에러가 발생", "찾을 수 없", "존재하지 않"]
        if any(s in title for s in error_signs) or any(s in source[:2000] for s in error_signs):
            if len(source) < 500:
                return "error"

        # __NEXT_DATA__
        has_next_data = "__NEXT_DATA__" in source
        if not has_next_data:
            try:
                result = self.driver.execute_script(
                    'var el = document.querySelector("script#__NEXT_DATA__");'
                    'return el ? true : false;'
                )
                has_next_data = bool(result)
            except Exception:
                pass

        if has_next_data:
            self._update_status("상품 페이지 로드 성공!")
            return "success"

        # URL + 콘텐츠 기반 판단
        current_url = ""
        try:
            current_url = self.driver.current_url or ""
        except Exception:
            pass

        if "/products/" in current_url and len(source) > 2000:
            self._update_status("상품 페이지 로드 성공!")
            return "success"

        return "error"

    async def extract_page_data_json(self) -> dict | None:
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
        try:
            props = next_data.get("props", {}).get("pageProps", {})
            for key in ["channel", "store", "merchantInfo"]:
                if key in props:
                    merchant = props[key]
                    if isinstance(merchant, dict):
                        for field in ["merchantNo", "channelNo", "id"]:
                            if field in merchant:
                                return str(merchant[field])
            state = props.get("dehydratedState", {})
            for q in state.get("queries", []):
                data = q.get("state", {}).get("data", {})
                if isinstance(data, dict):
                    for field in ["merchantNo", "channelNo"]:
                        if field in data:
                            return str(data[field])
        except Exception:
            pass
        return None

    def get_origin_product_no(self, next_data: dict) -> str | None:
        try:
            props = next_data.get("props", {}).get("pageProps", {})
            for key in ["originProductNo", "productNo"]:
                if key in props:
                    return str(props[key])
            product = props.get("product", {})
            if isinstance(product, dict):
                for key in ["originProductNo", "productNo", "id"]:
                    if key in product:
                        return str(product[key])
            state = props.get("dehydratedState", {})
            for q in state.get("queries", []):
                data = q.get("state", {}).get("data", {})
                if isinstance(data, dict):
                    for key in ["originProductNo", "productNo"]:
                        if key in data:
                            return str(data[key])
        except Exception:
            pass
        return None

    async def extract_cookies_session(self, referer: str) -> requests.Session:
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
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
