"""用于通过视觉模型把 JD 图片识别成纯文本。"""

from __future__ import annotations

import base64
import re

from app.infra.config import settings
from app.services.llm import ChatService


class JDOcrService:
    """用于封装 JD 图片 OCR 的视觉模型调用。"""

    async def extract_text_from_image(self, image_bytes: bytes, mime_type: str) -> str:
        """用于把单张 JD 图片识别成尽量原样的纯文本。"""
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{image_base64}"
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "请对这张图片做 OCR，只提取图片里可见的文字。"
                            "要求："
                            "1. 不要总结，不要改写，不要补充解释；"
                            "2. 尽量保留原有段落和换行；"
                            "3. 如果图片里没有可识别文字，返回空字符串。"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ],
            }
        ]

        async with ChatService(model=settings.OPENROUTER_VISION_MODEL) as chat_service:
            response = await chat_service.chat_completion(
                messages=messages,
                temperature=0,
                max_tokens=4000,
                stream=False,
            )

        content = (
            ChatService._coerce_content_text(
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            or ""
        )
        return self._normalize_ocr_text(content)

    @staticmethod
    def _normalize_ocr_text(text: str) -> str:
        """用于清理模型偶发附带的代码块包裹和多余空白。"""
        normalized = re.sub(
            r"^```(?:text|markdown)?\s*|\s*```$", "", text.strip(), flags=re.DOTALL
        )
        return normalized.strip()


__all__ = ["JDOcrService"]
