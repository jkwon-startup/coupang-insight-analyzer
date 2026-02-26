"""입력 값 검증 유틸리티"""

import re


def detect_platform(url: str) -> str:
    """URL에서 플랫폼 자동 감지.

    Returns:
        "coupang" | "naver" | "unknown"
    """
    url = url.strip().lower()
    if "coupang.com" in url:
        return "coupang"
    # brand.naver.com = 브랜드스토어, smartstore.naver.com = 스마트스토어
    if any(d in url for d in [
        "smartstore.naver.com",
        "brand.naver.com",
        "shopping.naver.com",
    ]):
        return "naver"
    return "unknown"


def validate_product_url(url: str) -> tuple[bool, str, str]:
    """통합 URL 검증. (valid, message, platform) 반환."""
    url = url.strip()
    if not url:
        return False, "URL을 입력해주세요.", ""

    platform = detect_platform(url)

    if platform == "coupang":
        return validate_coupang_url(url) + ("coupang",)
    elif platform == "naver":
        return validate_naver_url(url) + ("naver",)
    else:
        return False, "지원하지 않는 URL입니다. 쿠팡 또는 네이버 스마트스토어 URL을 입력해주세요.", ""


def validate_coupang_url(url: str) -> tuple[bool, str]:
    """쿠팡 URL 형식 검증. (valid, message) 반환."""
    url = url.strip()
    if not url:
        return False, "URL을 입력해주세요."
    if not re.search(r"coupang\.com/vp/products/\d+", url):
        return False, "유효한 쿠팡 상품 URL이 아닙니다."
    return True, ""


def validate_naver_url(url: str) -> tuple[bool, str]:
    """네이버 스마트스토어/브랜드스토어 URL 형식 검증. (valid, message) 반환."""
    url = url.strip()
    if not url:
        return False, "URL을 입력해주세요."
    # smartstore.naver.com 또는 brand.naver.com /{store_name}/products/{product_id}
    if not re.search(r"(?:smartstore|brand)\.naver\.com/[^/]+/products/\d+", url):
        return False, "유효한 네이버 스마트스토어 상품 URL이 아닙니다."
    return True, ""


def validate_api_key(api_key: str, provider: str) -> tuple[bool, str]:
    """API Key 기본 형식 검증. (valid, message) 반환."""
    api_key = api_key.strip()
    if not api_key:
        return False, "API Key를 입력해주세요."

    if provider == "openai":
        if not api_key.startswith("sk-"):
            return False, "OpenAI API Key는 'sk-'로 시작해야 합니다."
    elif provider == "claude":
        if not api_key.startswith("sk-ant-"):
            return False, "Anthropic API Key는 'sk-ant-'로 시작해야 합니다."

    return True, ""
