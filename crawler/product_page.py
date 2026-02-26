"""상품 페이지 정보 스크래핑 (제목, 가격, 평점, 상세 이미지 URL)"""

import re

from config.selectors import (
    PRODUCT_TITLE,
    PRODUCT_PRICE,
    DETAIL_IMAGE,
    TAB_REVIEW_XPATH,
)


class ProductPageScraper:
    async def scrape(self, page, product_info: dict) -> dict:
        """상품 기본 정보 + 상세 이미지 URL 추출"""
        data = {
            "product_id": product_info.get("product_id"),
            "url": product_info.get("full_url"),
            "title": "",
            "price": "",
            "rating": None,
            "review_count": None,
            "detail_image_urls": [],
            "specifications": [],
        }

        # 제목 (title 태그에서 추출)
        title_tag = await page.title()
        if title_tag:
            # "상품명 - 카테고리 | 쿠팡" 형식에서 상품명만 추출
            data["title"] = title_tag.split(" | ")[0].strip()

        # 제목 (buy 섹션에서 추출 시도)
        try:
            title_el = await page.query_selector(PRODUCT_TITLE)
            if title_el:
                data["title"] = (await title_el.inner_text()).strip()
        except Exception:
            pass

        # 가격
        try:
            price_el = await page.query_selector(PRODUCT_PRICE)
            if price_el:
                data["price"] = (await price_el.inner_text()).strip()
        except Exception:
            pass

        # 리뷰 수 (탭에서 추출)
        try:
            tabs = await page.query_selector_all("a")
            for tab in tabs:
                text = (await tab.inner_text()).strip()
                if "상품평" in text:
                    m = re.search(r"\((\d[\d,]*)\)", text)
                    if m:
                        data["review_count"] = int(m.group(1).replace(",", ""))
                    break
        except Exception:
            pass

        # 상세페이지 이미지 URL
        try:
            images = await page.query_selector_all(DETAIL_IMAGE)
            for img in images:
                src = await img.get_attribute("src") or await img.get_attribute("data-img-src")
                if src and ("vendor_inventory" in src or "product" in src):
                    if not src.startswith("http"):
                        src = "https:" + src
                    data["detail_image_urls"].append(src)
        except Exception:
            pass

        # 상품 속성 / 스펙
        try:
            spec_rows = await page.query_selector_all(".prod-attr-item")
            for row in spec_rows:
                text = (await row.inner_text()).strip()
                if text:
                    data["specifications"].append(text)
        except Exception:
            pass

        return data
