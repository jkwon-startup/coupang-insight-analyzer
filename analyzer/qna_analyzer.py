"""Q&A 카테고리 분석기"""

import json

from analyzer.ai_client import AIClient
from analyzer.prompts import QNA_ANALYSIS_PROMPT
from config.settings import MAX_TOKENS_QNA


class QnAAnalyzer:
    def __init__(self, ai_client: AIClient):
        self.ai = ai_client

    def analyze(self, qna_pairs: list[dict]) -> str:
        """Q&A 데이터를 AI로 카테고리 분석"""
        if not qna_pairs:
            return "분석할 Q&A가 없습니다."

        qna_data = self._prepare_data(qna_pairs)
        user_data = (
            f"## Q&A 데이터 ({len(qna_pairs)}건)\n"
            f"```json\n{qna_data}\n```"
        )

        return self.ai.analyze(
            QNA_ANALYSIS_PROMPT,
            user_data,
            MAX_TOKENS_QNA,
        )

    def _prepare_data(self, qna_pairs: list[dict]) -> str:
        clean = []
        for q in qna_pairs:
            clean.append({
                "question": q.get("question", ""),
                "answer": q.get("answer", ""),
                "q_date": q.get("q_date", ""),
                "seller": q.get("seller", ""),
            })

        # 토큰 제한
        if len(clean) > 50:
            clean = clean[:50]

        return json.dumps(clean, ensure_ascii=False, indent=1)
