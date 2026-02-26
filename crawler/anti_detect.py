"""봇 탐지 우회 유틸리티: User-Agent 풀, 랜덤 딜레이"""

import asyncio
import random

from config.settings import (
    COUPANG_PAGE_DELAY_MIN, COUPANG_PAGE_DELAY_MAX,
    NAVER_PAGE_DELAY_MIN, NAVER_PAGE_DELAY_MAX,
)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
]


def get_random_user_agent() -> str:
    return random.choice(USER_AGENTS)


async def human_delay(min_s: float = 1.8, max_s: float = 2.5):
    """PRD 규정 랜덤 딜레이"""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def page_transition_delay():
    """쿠팡 페이지 전환 딜레이 (1.8~2.5초)"""
    await human_delay(COUPANG_PAGE_DELAY_MIN, COUPANG_PAGE_DELAY_MAX)


async def naver_page_transition_delay():
    """네이버 페이지 전환 딜레이 (2.5~4.0초, 보수적)"""
    await human_delay(NAVER_PAGE_DELAY_MIN, NAVER_PAGE_DELAY_MAX)


async def short_delay():
    """짧은 대기 (0.5~1.5초)"""
    await human_delay(0.5, 1.5)
