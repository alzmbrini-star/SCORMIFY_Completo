"""Compatibility API backed by LiteLLM.

The application was originally coupled to a private ``emergentintegrations``
package.  This module preserves the small public surface used by Scormify while
allowing local and independent deployments to use normal provider API keys.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass
class FileContent:
    content_type: str
    file_content_base64: str


@dataclass
class FileContentWithMimeType:
    file_path: str
    mime_type: str


@dataclass
class ImageContent:
    data: str
    mime_type: str = "image/png"


@dataclass
class UserMessage:
    text: str
    file_contents: list[Any] | None = None


class LlmChat:
    """Small fluent chat client compatible with the API used by Scormify."""

    def __init__(self, api_key: str, session_id: str, system_message: str = ""):
        self.api_key = (api_key or "").strip()
        self.session_id = session_id
        self.system_message = system_message
        self.provider = "openai"
        self.model = "gpt-4o"
        self.params: dict[str, Any] = {}
        self._history: list[dict[str, Any]] = []

    def with_model(self, provider: str, model: str) -> "LlmChat":
        self.provider = (provider or "openai").lower()
        self.model = model
        return self

    def with_params(self, **params: Any) -> "LlmChat":
        self.params.update(params)
        return self

    def _litellm_model(self) -> str:
        if "/" in self.model:
            return self.model
        prefixes = {
            "anthropic": "anthropic",
            "gemini": "gemini",
            "google": "gemini",
            "openai": "openai",
        }
        prefix = prefixes.get(self.provider)
        return f"{prefix}/{self.model}" if prefix else self.model

    def _provider_api_key(self) -> str:
        """Prefer a provider-specific secret and retain the legacy fallback."""
        variable_by_provider = {
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "google": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        variable = variable_by_provider.get(self.provider)
        return (os.environ.get(variable, "") if variable else "").strip() or self.api_key

    @staticmethod
    def _encode_file(item: Any) -> tuple[str, str]:
        if isinstance(item, FileContent):
            return item.content_type, item.file_content_base64
        if isinstance(item, FileContentWithMimeType):
            raw = Path(item.file_path).read_bytes()
            return item.mime_type, base64.b64encode(raw).decode("ascii")
        if isinstance(item, ImageContent):
            return item.mime_type, item.data
        raise TypeError(f"Unsupported file content type: {type(item).__name__}")

    def _user_content(self, message: UserMessage) -> str | list[dict[str, Any]]:
        if not message.file_contents:
            return message.text
        content: list[dict[str, Any]] = [{"type": "text", "text": message.text}]
        for item in message.file_contents:
            mime_type, encoded = self._encode_file(item)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                }
            )
        return content

    def _messages(self, message: UserMessage) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if self.system_message:
            messages.append({"role": "system", "content": self.system_message})
        messages.extend(self._history)
        messages.append({"role": "user", "content": self._user_content(message)})
        return messages

    async def _completion(self, message: UserMessage) -> Any:
        api_key = self._provider_api_key()
        if not api_key:
            raise RuntimeError(
                "LLM API key is not configured. Set OPENAI_API_KEY, "
                "GEMINI_API_KEY or ANTHROPIC_API_KEY for the selected provider."
            )
        from litellm import acompletion

        kwargs = dict(self.params)
        response = await acompletion(
            model=self._litellm_model(),
            messages=self._messages(message),
            api_key=api_key,
            **kwargs,
        )
        return response

    @staticmethod
    def _message_text(response: Any) -> str:
        message = response.choices[0].message
        content = getattr(message, "content", "") or ""
        if isinstance(content, str):
            return content
        if isinstance(content, Iterable):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif getattr(item, "type", None) == "text":
                    parts.append(str(getattr(item, "text", "")))
            return "".join(parts)
        return str(content)

    async def send_message(self, message: UserMessage) -> str:
        response = await self._completion(message)
        text = self._message_text(response)
        self._history.append({"role": "user", "content": self._user_content(message)})
        self._history.append({"role": "assistant", "content": text})
        return text

    @staticmethod
    def _extract_images(response: Any) -> list[dict[str, str]]:
        message = response.choices[0].message
        candidates = getattr(message, "images", None) or []
        content = getattr(message, "content", None)
        if isinstance(content, list):
            candidates = [*candidates, *content]

        images: list[dict[str, str]] = []
        for candidate in candidates:
            if hasattr(candidate, "model_dump"):
                candidate = candidate.model_dump()
            if not isinstance(candidate, dict):
                continue
            value = candidate.get("data")
            image_url = candidate.get("image_url") or {}
            if isinstance(image_url, dict):
                value = value or image_url.get("url")
            elif isinstance(image_url, str):
                value = value or image_url
            if not value:
                continue
            if isinstance(value, str) and ";base64," in value:
                value = value.split(";base64,", 1)[1]
            images.append({"data": str(value)})
        return images

    async def send_message_multimodal_response(
        self, message: UserMessage
    ) -> tuple[str, list[dict[str, str]]]:
        response = await self._completion(message)
        text = self._message_text(response)
        images = self._extract_images(response)
        self._history.append({"role": "user", "content": self._user_content(message)})
        self._history.append({"role": "assistant", "content": text})
        return text, images
