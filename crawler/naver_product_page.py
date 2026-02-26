"""네이버 스마트스토어 상품 페이지 정보 스크래핑

__NEXT_DATA__ JSON 추출 최우선, DOM 파싱은 fallback.
출력 형식은 기존 쿠팡 ProductPageScraper와 동일.
"""

from config.naver_selectors import (
    PRODUCT_TITLE_SELECTORS,
    PRODUCT_PRICE_SELECTORS,
    PRODUCT_RATING_SELECTORS,
    PRODUCT_REVIEW_COUNT_SELECTORS,
    DETAIL_IMAGE_SELECTORS,
)


class NaverProductPageScraper:
    async def scrape(self, page, product_info: dict, next_data: dict | None = None) -> dict:
        """상품 기본 정보 + 상세 이미지 URL 추출.

        Args:
            page: SeleniumPageWrapper
            product_info: parse_naver_url() 결과
            next_data: __NEXT_DATA__ JSON (있으면 우선 사용)

        Returns:
            기존 쿠팡과 동일한 구조의 dict
        """
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

        # 1단계: __NEXT_DATA__ JSON에서 추출
        if next_data:
            self._extract_from_json(next_data, data)

        # 2단계: JSON에서 못 가져온 필드는 DOM fallback (page가 있을 때만)
        if page is not None:
            if not data["title"]:
                data["title"] = await self._extract_text_dom(page, PRODUCT_TITLE_SELECTORS)
            if not data["price"]:
                data["price"] = await self._extract_text_dom(page, PRODUCT_PRICE_SELECTORS)
            if data["rating"] is None:
                rating_text = await self._extract_text_dom(page, PRODUCT_RATING_SELECTORS)
                if rating_text:
                    try:
                        data["rating"] = float(rating_text)
                    except ValueError:
                        pass
            if data["review_count"] is None:
                count_text = await self._extract_text_dom(page, PRODUCT_REVIEW_COUNT_SELECTORS)
                if count_text:
                    try:
                        data["review_count"] = int(count_text.replace(",", ""))
                    except ValueError:
                        pass
            if not data["detail_image_urls"]:
                data["detail_image_urls"] = await self._extract_images_dom(page)

        # title 최후 fallback: 브라우저 title (page가 있을 때만)
        if not data["title"] and page is not None:
            title_tag = await page.title()
            if title_tag:
                data["title"] = title_tag.split(" :")[0].strip()

        return data

    def _extract_from_json(self, next_data: dict, data: dict):
        """__NEXT_DATA__ JSON에서 상품 정보 추출."""
        try:
            props = next_data.get("props", {}).get("pageProps", {})

            # product 객체 탐색
            product = props.get("product", {})
            if not isinstance(product, dict):
                product = {}

            # 제목
            data["title"] = (
                product.get("name", "")
                or product.get("productName", "")
                or props.get("productName", "")
            )

            # 가격
            sale_price = product.get("salePrice") or product.get("discountedSalePrice")
            if sale_price:
                data["price"] = f"{int(sale_price):,}원"

            # 평점
            review_info = product.get("reviewAmount", {})
            if isinstance(review_info, dict):
                avg = review_info.get("averageReviewScore") or review_info.get("totalReviewScore")
                if avg:
                    try:
                        data["rating"] = float(avg)
                    except (ValueError, TypeError):
                        pass
                count = review_info.get("totalReviewCount")
                if count:
                    try:
                        data["review_count"] = int(count)
                    except (ValueError, TypeError):
                        pass

            # 상세 이미지
            detail_content = product.get("detailContents", "")
            if isinstance(detail_content, str) and detail_content:
                import re
                img_urls = re.findall(r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|gif|webp)', detail_content)
                data["detail_image_urls"] = list(dict.fromkeys(img_urls))[:50]

            # 상품 이미지 (detail이 없을 경우)
            if not data["detail_image_urls"]:
                images = product.get("productImages", [])
                if isinstance(images, list):
                    for img in images:
                        url = img.get("url") if isinstance(img, dict) else str(img) if isinstance(img, str) else None
                        if url:
                            if not url.startswith("http"):
                                url = "https:" + url
                            data["detail_image_urls"].append(url)

            # 속성/스펙
            attrs = product.get("productAttributes", [])
            if isinstance(attrs, list):
                for attr in attrs:
                    if isinstance(attr, dict):
                        name = attr.get("attributeName", "")
                        val = attr.get("attributeValue", "")
                        if name and val:
                            data["specifications"].append(f"{name}: {val}")

            # dehydratedState에서 보충 탐색
            if not data["title"]:
                state = props.get("dehydratedState", {})
                queries = state.get("queries", [])
                for q in queries:
                    qdata = q.get("state", {}).get("data", {})
                    if isinstance(qdata, dict):
                        name = qdata.get("name") or qdata.get("productName")
                        if name:
                            data["title"] = name
                            break

        except Exception:
            pass

    async def _extract_text_dom(self, page, selectors: list[str]) -> str:
        """복수 셀렉터를 순서대로 시도하여 텍스트 추출."""
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if text:
                        return text
            except Exception:
                continue
        return ""

    async def _extract_images_dom(self, page) -> list[str]:
        """DOM에서 상세 이미지 URL 추출."""
        urls = []
        for sel in DETAIL_IMAGE_SELECTORS:
            try:
                images = await page.query_selector_all(sel)
                for img in images:
                    src = (
                        await img.get_attribute("src")
                        or await img.get_attribute("data-src")
                        or await img.get_attribute("data-lazy-src")
                    )
                    if src:
                        if not src.startswith("http"):
                            src = "https:" + src
                        if src not in urls:
                            urls.append(src)
            except Exception:
                continue
        return urls[:50]
