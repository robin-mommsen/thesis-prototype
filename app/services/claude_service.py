import asyncio
import logging
from typing import AsyncIterator, Optional
import anthropic
from app.config.config import settings

logger = logging.getLogger(__name__)


class ClaudeService:
    def __init__(self):
        self.api_key = settings.claude_api_key
        self.model = settings.claude_model

    def _client(self) -> anthropic.Anthropic:
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY is not configured")
        return anthropic.Anthropic(api_key=self.api_key)

    def _async_client(self) -> anthropic.AsyncAnthropic:
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY is not configured")
        return anthropic.AsyncAnthropic(api_key=self.api_key)

    def _generate_sync(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        kwargs = {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self._client().messages.create(**kwargs)
        return response.content[0].text if response.content else ""

    async def ask_claude(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        logger.info("Claude request (model=%s, stream=False)", self.model)
        return await asyncio.to_thread(self._generate_sync, prompt, system_prompt)

    async def ask_claude_stream(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncIterator[str]:
        logger.info("Claude request (model=%s, stream=True)", self.model)
        kwargs = {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        async with self._async_client().messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text


claude_service = ClaudeService()
