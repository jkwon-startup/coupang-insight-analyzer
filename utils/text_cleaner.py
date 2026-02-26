"""텍스트 정제 유틸리티"""

import re


def clean_html_text(text: str) -> str:
    """HTML 태그 제거 및 공백 정리"""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate_text(text: str, max_length: int = 500) -> str:
    """텍스트를 max_length로 잘라서 반환"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
