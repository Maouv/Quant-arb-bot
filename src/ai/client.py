"""OpenAI-compatible async HTTP client."""

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class AiClient:
    """
    OpenAI-compatible API client.
    Accepts any provider with OpenAI base URL format:
    - OpenAI, Groq, Together, Ollama, LM Studio, etc.
    """

    def __init__(self, baseUrl: str, apiKey: str, model: str) -> None:
        """
        baseUrl: e.g. "https://api.openai.com/v1"
                      "https://api.groq.com/openai/v1"
                      "http://localhost:11434/v1"
        """
        self._baseUrl = baseUrl.rstrip("/")
        self._model = model
        self._headers = {"Authorization": f"Bearer {apiKey}", "Content-Type": "application/json"}

    async def chat(self, messages: list[dict[str, str]], maxTokens: int = 4096) -> str:
        """
        POST {baseUrl}/chat/completions
        Standard OpenAI chat format.
        Return: assistant message content (falls back to reasoning_content for thinking models).
        """
        totalChars = sum(len(m["content"]) for m in messages)
        logger.info(
            "AI request: %d messages, %d chars, ~%d tokens",
            len(messages), totalChars, totalChars // 4,
        )
        for i, m in enumerate(messages):
            logger.info("  msg[%d] role=%s chars=%d", i, m["role"], len(m["content"]))
        payload = {"model": self._model, "messages": messages, "max_tokens": maxTokens}
        async with httpx.AsyncClient(timeout=settings.AI_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{self._baseUrl}/chat/completions",
                headers=self._headers,
                json=payload,
            )
        response.raise_for_status()
        data: dict[str, list[dict[str, dict[str, str]]]] = response.json()
        message: dict[str, str] = data["choices"][0]["message"]
        content: str = message.get("content") or message.get("reasoning_content", "")
        logger.debug("AI response received: %d chars", len(content))
        return content
