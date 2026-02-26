"""URL 검증 및 상품 ID 추출 (쿠팡 + 네이버 스마트스토어/브랜드스토어)"""

import re
from urllib.parse import urlparse, parse_qs

from config.settings import (
    NAVER_SMARTSTORE_BASE, NAVER_BRAND_BASE,
    NAVER_MOBILE_SMARTSTORE_BASE, NAVER_MOBILE_BRAND_BASE,
    NAVER_SMARTSTORE_REVIEW_API, NAVER_SMARTSTORE_QNA_API,
    NAVER_BRAND_REVIEW_API, NAVER_BRAND_QNA_API,
)

COUPANG_URL_PATTERN = re.compile(r"coupang\.com/vp/products/(\d+)")
# smartstore.naver.com 또는 brand.naver.com 둘 다 지원
NAVER_URL_PATTERN = re.compile(
    r"(?:smartstore|brand)\.naver\.com/([^/]+)/products/(\d+)"
)


def parse_url(url: str, platform: str) -> dict:
    """통합 디스패처: 플랫폼에 맞는 파서 호출."""
    if platform == "coupang":
        return parse_coupang_url(url)
    elif platform == "naver":
        return parse_naver_url(url)
    raise ValueError(f"지원하지 않는 플랫폼: {platform}")


def parse_coupang_url(url: str) -> dict:
    """쿠팡 상품 URL에서 productId, itemId, vendorItemId를 추출한다.

    Returns:
        {
            "platform": "coupang",
            "product_id": str,
            "item_id": str | None,
            "vendor_item_id": str | None,
            "full_url": str,
        }

    Raises:
        ValueError: 유효하지 않은 쿠팡 URL
    """
    url = url.strip()
    match = COUPANG_URL_PATTERN.search(url)
    if not match:
        raise ValueError(
            "유효한 쿠팡 상품 URL이 아닙니다. "
            "예: https://www.coupang.com/vp/products/12345678"
        )

    product_id = match.group(1)
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    return {
        "platform": "coupang",
        "product_id": product_id,
        "item_id": params.get("itemId", [None])[0],
        "vendor_item_id": params.get("vendorItemId", [None])[0],
        "full_url": url,
    }


def parse_naver_url(url: str) -> dict:
    """네이버 스마트스토어/브랜드스토어 URL에서 store_name, product_id를 추출.

    쿼리 파라미터(?nl-query=... 등)는 자동 제거하여 깨끗한 URL로 정제.
    brand.naver.com은 원래 도메인을 그대로 유지.

    Returns:
        {
            "platform": "naver",
            "product_id": str,
            "store_name": str,
            "full_url": str,
            "desktop_url": str,
            "mobile_url": str,
        }

    Raises:
        ValueError: 유효하지 않은 네이버 URL
    """
    url = url.strip()
    match = NAVER_URL_PATTERN.search(url)
    if not match:
        raise ValueError(
            "유효한 네이버 스마트스토어 URL이 아닙니다. "
            "예: https://smartstore.naver.com/storename/products/12345678 "
            "또는 https://brand.naver.com/brandname/products/12345678"
        )

    store_name = match.group(1)
    product_id = match.group(2)

    # 원래 도메인 감지 (brand.naver.com vs smartstore.naver.com)
    parsed = urlparse(url)
    host = parsed.hostname or ""

    is_brand = "brand.naver.com" in host

    if is_brand:
        base_desktop = NAVER_BRAND_BASE
        base_mobile = NAVER_MOBILE_BRAND_BASE
        review_api = NAVER_BRAND_REVIEW_API
        qna_api = NAVER_BRAND_QNA_API
    else:
        base_desktop = NAVER_SMARTSTORE_BASE
        base_mobile = NAVER_MOBILE_SMARTSTORE_BASE
        review_api = NAVER_SMARTSTORE_REVIEW_API
        qna_api = NAVER_SMARTSTORE_QNA_API

    # 쿼리 파라미터 제거한 깨끗한 URL 생성
    desktop_url = f"{base_desktop}/{store_name}/products/{product_id}"
    mobile_url = f"{base_mobile}/{store_name}/products/{product_id}"

    return {
        "platform": "naver",
        "product_id": product_id,
        "store_name": store_name,
        "is_brand": is_brand,
        "full_url": desktop_url,
        "desktop_url": desktop_url,
        "mobile_url": mobile_url,
        "review_api": review_api,
        "qna_api": qna_api,
    }
