"""종합 리포트 생성기"""

from analyzer.ai_client import AIClient
from analyzer.prompts import FULL_REPORT_PROMPT
from config.settings import MAX_TOKENS_FULL


class FullReportAnalyzer:
    def __init__(self, ai_client: AIClient):
        self.ai = ai_client

    def analyze(
        self,
        product_data: dict | None,
        story_result: str,
        review_result: str,
        qna_result: str,
    ) -> str:
        """3개 분석 결과를 통합한 종합 리포트 생성"""
        parts = []

        if product_data:
            parts.append(f"## 상품 정보\n- 상품명: {product_data.get('title', 'N/A')}")
            if product_data.get("price"):
                parts.append(f"- 가격: {product_data['price']}")
            if product_data.get("review_count"):
                parts.append(f"- 리뷰 수: {product_data['review_count']}건")

        if story_result:
            parts.append(f"\n## 상세페이지 스토리 분석 결과\n{story_result}")

        if review_result:
            parts.append(f"\n## 리뷰 분석 결과\n{review_result}")

        if qna_result:
            parts.append(f"\n## Q&A 분석 결과\n{qna_result}")

        if not parts:
            return "통합 분석할 데이터가 없습니다."

        user_data = "\n".join(parts)

        return self.ai.analyze(
            FULL_REPORT_PROMPT,
            user_data,
            MAX_TOKENS_FULL,
        )
