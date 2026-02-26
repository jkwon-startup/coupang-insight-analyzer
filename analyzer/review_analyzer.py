"""리뷰 감성 분석기"""

import json

from analyzer.ai_client import AIClient
from analyzer.prompts import REVIEW_SENTIMENT_PROMPT
from config.settings import MAX_TOKENS_REVIEW


class ReviewAnalyzer:
    def __init__(self, ai_client: AIClient):
        self.ai = ai_client

    def analyze(self, reviews: list[dict]) -> str:
        """리뷰 데이터를 AI로 감성 분석"""
        if not reviews:
            return "분석할 리뷰가 없습니다."

        # 리뷰 데이터를 JSON으로 정리 (토큰 절약 위해 핵심 필드만)
        review_data = self._prepare_data(reviews)

        # 별점 분포 통계 추가
        stats = self._calc_stats(reviews)
        user_data = (
            f"## 별점 분포\n{stats}\n\n"
            f"## 리뷰 데이터 ({len(reviews)}건)\n"
            f"```json\n{review_data}\n```"
        )

        return self.ai.analyze(
            REVIEW_SENTIMENT_PROMPT,
            user_data,
            MAX_TOKENS_REVIEW,
        )

    def _prepare_data(self, reviews: list[dict]) -> str:
        """AI에 전달할 리뷰 데이터 정리 (토큰 절약)"""
        clean = []
        for r in reviews:
            entry = {
                "rating": r.get("rating"),
                "date": r.get("date", ""),
                "content": r.get("content", ""),
            }
            # headline이 있으면 content에 합치기
            if r.get("headline"):
                entry["content"] = f"{r['headline']} {entry['content']}".strip()
            clean.append(entry)

        # 토큰 제한: 리뷰가 너무 많으면 앞뒤 50개씩만
        if len(clean) > 100:
            clean = clean[:50] + clean[-50:]

        return json.dumps(clean, ensure_ascii=False, indent=1)

    def _calc_stats(self, reviews: list[dict]) -> str:
        """별점 분포 통계"""
        dist = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        for r in reviews:
            rating = r.get("rating")
            if rating is not None:
                key = int(round(rating))
                if key in dist:
                    dist[key] += 1

        total = sum(dist.values())
        lines = []
        for star in [5, 4, 3, 2, 1]:
            count = dist[star]
            pct = (count / total * 100) if total > 0 else 0
            lines.append(f"- {star}점: {count}건 ({pct:.1f}%)")
        lines.append(f"- 합계: {total}건")
        return "\n".join(lines)
