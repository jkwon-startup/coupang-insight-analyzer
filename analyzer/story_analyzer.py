"""상세페이지 스토리 플로우 분석기"""

import json

from analyzer.ai_client import AIClient
from analyzer.prompts import STORY_FLOW_PROMPT
from config.settings import MAX_TOKENS_STORY


class StoryAnalyzer:
    def __init__(self, ai_client: AIClient):
        self.ai = ai_client

    def analyze(self, product_data: dict) -> str:
        """상품 정보 + 이미지로 스토리 플로우 분석"""
        image_urls = product_data.get("detail_image_urls", [])

        # 상품 텍스트 정보 구성
        text_info = self._build_text_info(product_data)

        # 이미지가 있으면 멀티모달 분석
        if image_urls:
            prompt = (
                f"{STORY_FLOW_PROMPT}\n\n"
                f"## 상품 기본 정보\n{text_info}\n\n"
                f"아래 상세페이지 이미지들을 분석하여 스토리 플로우를 파악해주세요."
            )
            return self.ai.analyze_with_images(
                prompt, image_urls, MAX_TOKENS_STORY
            )

        # 이미지가 없으면 텍스트만으로 분석
        return self.ai.analyze(
            STORY_FLOW_PROMPT,
            f"## 상품 정보\n{text_info}",
            MAX_TOKENS_STORY,
        )

    def _build_text_info(self, data: dict) -> str:
        parts = []
        if data.get("title"):
            parts.append(f"- 상품명: {data['title']}")
        if data.get("price"):
            parts.append(f"- 가격: {data['price']}")
        if data.get("rating"):
            parts.append(f"- 평점: {data['rating']}")
        if data.get("review_count"):
            parts.append(f"- 리뷰 수: {data['review_count']}건")
        if data.get("specifications"):
            parts.append(f"- 스펙: {', '.join(data['specifications'])}")
        return "\n".join(parts) if parts else "상품 텍스트 정보 없음"
