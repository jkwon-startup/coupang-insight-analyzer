"""통합 AI 클라이언트 (OpenAI o4-mini + Anthropic Claude)"""

import base64
import mimetypes
from abc import ABC, abstractmethod

import requests
from openai import OpenAI
from anthropic import Anthropic

from config.settings import OPENAI_MODEL, CLAUDE_MODEL


def _sanitize_image_urls(urls: list[str]) -> list[str]:
    """이미지 URL을 HTTPS로 정제. 유효하지 않은 URL은 제거."""
    clean = []
    for url in urls:
        if not url:
            continue
        url = url.strip()
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("http://"):
            url = "https://" + url[7:]
        if url.startswith("https://"):
            clean.append(url)
    return clean


def _download_image_as_base64(url: str) -> tuple[str, str] | None:
    """이미지 URL을 다운로드하여 (base64_data, media_type) 반환.

    robots.txt 차단 등으로 URL 직접 전달이 불가능한 경우 사용.
    실패 시 None 반환.
    """
    try:
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 Chrome/145.0.0.0 Safari/537.36",
        })
        if resp.status_code != 200:
            return None

        content_type = resp.headers.get("Content-Type", "")
        if "jpeg" in content_type or "jpg" in content_type:
            media_type = "image/jpeg"
        elif "png" in content_type:
            media_type = "image/png"
        elif "gif" in content_type:
            media_type = "image/gif"
        elif "webp" in content_type:
            media_type = "image/webp"
        else:
            # URL 확장자로 추측
            ext = url.rsplit(".", 1)[-1].split("?")[0].lower()
            type_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                        "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
            media_type = type_map.get(ext, "image/jpeg")

        b64 = base64.standard_b64encode(resp.content).decode("utf-8")
        return b64, media_type
    except Exception:
        return None


class AIClient(ABC):
    @abstractmethod
    def analyze(self, system_prompt: str, user_data: str, max_tokens: int = 2000) -> str:
        pass

    @abstractmethod
    def analyze_with_images(
        self, prompt: str, image_urls: list[str], max_tokens: int = 2000
    ) -> str:
        pass


class OpenAIClient(AIClient):
    """o4-mini (reasoning 모델) 클라이언트.

    reasoning 모델 특성:
    - max_tokens 대신 max_completion_tokens 사용
    - temperature 설정 불가 (고정)
    - system role 대신 developer role 사용
    """

    def __init__(self, api_key: str, model: str = OPENAI_MODEL):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def analyze(self, system_prompt: str, user_data: str, max_tokens: int = 2000) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "developer", "content": system_prompt},
                {"role": "user", "content": user_data},
            ],
            max_completion_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def analyze_with_images(
        self, prompt: str, image_urls: list[str], max_tokens: int = 2000
    ) -> str:
        clean_urls = _sanitize_image_urls(image_urls)
        if not clean_urls:
            return self.analyze("You are an e-commerce analyst.", prompt, max_tokens)

        content = [{"type": "text", "text": prompt}]
        for url in clean_urls[:10]:
            # base64 다운로드 시도, 실패 시 URL 직접 전달
            img = _download_image_as_base64(url)
            if img:
                b64_data, media_type = img
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{b64_data}"},
                })
            else:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": url},
                })

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            max_completion_tokens=max_tokens,
        )
        return response.choices[0].message.content


class ClaudeClient(AIClient):
    def __init__(self, api_key: str, model: str = CLAUDE_MODEL):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def analyze(self, system_prompt: str, user_data: str, max_tokens: int = 2000) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_data}],
        )
        return response.content[0].text

    def analyze_with_images(
        self, prompt: str, image_urls: list[str], max_tokens: int = 2000
    ) -> str:
        clean_urls = _sanitize_image_urls(image_urls)
        if not clean_urls:
            return self.analyze(
                prompt,
                "이미지가 제공되지 않았습니다. 텍스트 정보만으로 분석해주세요.",
                max_tokens,
            )

        # Claude: base64로 다운로드하여 전달 (robots.txt 차단 우회)
        content = [{"type": "text", "text": prompt}]
        image_count = 0
        for url in clean_urls[:10]:
            img = _download_image_as_base64(url)
            if img:
                b64_data, media_type = img
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64_data,
                    },
                })
                image_count += 1

        if image_count == 0:
            return self.analyze(
                prompt,
                "이미지 다운로드에 실패했습니다. 텍스트 정보만으로 분석해주세요.",
                max_tokens,
            )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text


def create_ai_client(provider: str, api_key: str) -> AIClient:
    """팩토리 함수: provider에 맞는 AI 클라이언트 반환"""
    if provider == "openai":
        return OpenAIClient(api_key)
    elif provider == "claude":
        return ClaudeClient(api_key)
    raise ValueError(f"지원하지 않는 AI 제공자: {provider}")
